"""Small, opt-in model transports; manuscript authority stays in workflow_io.

No SDK dependency, provider fallback, remote tools, or persisted credentials.
The caller supplies the same instructions and schema to every transport.
"""

from __future__ import annotations

import ipaddress
import base64
import json
import os
import re
import time
from http.client import HTTPException
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ProviderError(ValueError):
    """A configuration or model response cannot safely enter the review flow."""


class ModelResult(dict):
    """Keep transport evidence separate from model-authored review fields."""

    def __init__(self, value: dict, metadata: dict):
        super().__init__(value)
        self.metadata = metadata


PRESETS = {
    "codex": ("codex-cli", "", "", "json_schema"),
    "openai": ("responses", "https://api.openai.com/v1", "OPENAI_API_KEY", "json_schema"),
    "anthropic": ("anthropic-messages", "https://api.anthropic.com/v1", "ANTHROPIC_API_KEY", "json_schema"),
    "deepseek": ("chat-completions", "https://api.deepseek.com", "DEEPSEEK_API_KEY", "json_object"),
    "glm": ("chat-completions", "https://open.bigmodel.cn/api/paas/v4", "ZHIPU_API_KEY", "json_object"),
    "zai": ("chat-completions", "https://api.z.ai/api/paas/v4", "ZAI_API_KEY", "json_object"),
    "gemini": ("chat-completions", "https://generativelanguage.googleapis.com/v1beta/openai", "GEMINI_API_KEY", "json_schema"),
    "qwen": ("chat-completions", "https://dashscope.aliyuncs.com/compatible-mode/v1", "DASHSCOPE_API_KEY", "prompt"),
    "kimi": ("chat-completions", "https://api.moonshot.ai/v1", "MOONSHOT_API_KEY", "prompt"),
    "minimax": ("chat-completions", "https://api.minimax.io/v1", "MINIMAX_API_KEY", "prompt"),
    "mistral": ("chat-completions", "https://api.mistral.ai/v1", "MISTRAL_API_KEY", "json_object"),
    "xai": ("chat-completions", "https://api.x.ai/v1", "XAI_API_KEY", "prompt"),
    "groq": ("chat-completions", "https://api.groq.com/openai/v1", "GROQ_API_KEY", "prompt"),
    "together": ("chat-completions", "https://api.together.ai/v1", "TOGETHER_API_KEY", "prompt"),
    "fireworks": ("chat-completions", "https://api.fireworks.ai/inference/v1", "FIREWORKS_API_KEY", "prompt"),
    "openrouter": ("chat-completions", "https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "prompt"),
    "ollama": ("chat-completions", "http://localhost:11434/v1", "AWT_API_KEY", "prompt"),
    "lmstudio": ("chat-completions", "http://localhost:1234/v1", "AWT_API_KEY", "prompt"),
    "openai-compatible": ("chat-completions", "", "AWT_API_KEY", "json_object"),
}
MAX_RESPONSE_BYTES = 2_000_000


def _loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@dataclass(frozen=True)
class ProviderConfig:
    provider: str
    protocol: str
    model: str
    base_url: str
    api_key_env: str
    response_format: str
    max_output_tokens: int = 8192
    timeout_seconds: int = 300
    supports_images: bool = False

    def public_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "protocol": self.protocol,
            "requested_model": self.model or None,
            "base_url": self.base_url or None,
            "response_format": self.response_format,
            "max_output_tokens": self.max_output_tokens if self.provider != "codex" else None,
            "supports_images": self.supports_images,
        }

    def api_key(self) -> str:
        key = os.environ.get(self.api_key_env, "").strip()
        if not key and not _loopback(urlsplit(self.base_url).hostname or ""):
            raise ProviderError(f"Set the API key in environment variable {self.api_key_env}.")
        if any(ord(character) < 32 or ord(character) > 126 for character in key):
            raise ProviderError("The API key contains invalid header characters.")
        return key


def load_provider_config(environ: Mapping[str, str] | None = None) -> ProviderConfig:
    env = os.environ if environ is None else environ
    provider = env.get("AWT_PROVIDER", "codex").strip().lower()
    if provider not in PRESETS:
        raise ProviderError("Unknown AWT_PROVIDER; run awt --list-providers for supported presets.")
    protocol, default_url, default_key, default_format = PRESETS[provider]
    protocol = env.get("AWT_PROTOCOL", protocol).strip()
    valid_protocols = {"codex-cli"} if provider == "codex" else {"chat-completions", "anthropic-messages", "responses"}
    if protocol not in valid_protocols:
        raise ProviderError("AWT_PROTOCOL is incompatible with the selected provider.")
    model = env.get("AWT_MODEL", "").strip()
    if not model and provider != "codex":
        raise ProviderError("Set AWT_MODEL to the exact model ID available in your provider account.")
    if len(model) > 200 or (model and not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9._:/@+-]*", model)):
        raise ProviderError("AWT_MODEL must be a model ID using letters, digits, or . _ : / @ + - characters.")
    base_url = env.get("AWT_BASE_URL", default_url).strip().rstrip("/")
    key_env = env.get("AWT_API_KEY_ENV", default_key).strip()
    output_format = env.get("AWT_RESPONSE_FORMAT", default_format).strip()
    formats = {"json_schema", "prompt"} if protocol == "anthropic-messages" else {"json_schema", "json_object", "prompt"}
    if output_format not in formats:
        raise ProviderError("Unsupported AWT_RESPONSE_FORMAT for this provider.")
    if provider == "codex":
        if base_url or key_env or output_format != "json_schema":
            raise ProviderError("Codex uses its CLI authentication; clear API-only AWT settings or select an API provider.")
    else:
        try:
            url = urlsplit(base_url)
            valid = (
                bool(url.hostname) and url.port != 0
                and (url.scheme == "https" or (url.scheme == "http" and _loopback(url.hostname)))
                and not (url.username or url.password or url.query or url.fragment)
                and not re.search(r"[\s\\]", base_url)
                and not url.path.endswith(("/chat/completions", "/messages", "/responses"))
            )
        except ValueError:
            valid = False
        if not valid:
            raise ProviderError("AWT_BASE_URL requires HTTPS (HTTP only for loopback), without credentials, query, fragment, or a completion endpoint suffix.")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key_env):
            raise ProviderError("AWT_API_KEY_ENV must name an environment variable, not contain a key.")
    try:
        max_tokens = int(env.get("AWT_MAX_OUTPUT_TOKENS", "8192"))
        timeout = int(env.get("AWT_REQUEST_TIMEOUT", "300"))
    except ValueError:
        raise ProviderError("Output-token and timeout settings must be integers.") from None
    if not 256 <= max_tokens <= 128_000 or not 1 <= timeout <= 1800:
        raise ProviderError("AWT_MAX_OUTPUT_TOKENS must be 256..128000; AWT_REQUEST_TIMEOUT must be 1..1800 seconds.")
    image_setting = env.get("AWT_SUPPORTS_IMAGES", "0")
    if image_setting not in {"0", "1"} or (provider == "codex" and image_setting == "1"):
        raise ProviderError("AWT_SUPPORTS_IMAGES must be 0 or 1; image requests require an API provider.")
    return ProviderConfig(provider, protocol, model, base_url, key_env, output_format, max_tokens, timeout, image_setting == "1")


def validate_schema(value: Any, schema: Mapping[str, Any], path: str = "$", depth: int = 0) -> None:
    """Validate the JSON Schema subset used by AWT, independently of providers."""
    if depth > 30:
        raise ProviderError("Model JSON is nested too deeply.")
    if "anyOf" in schema:
        for candidate in schema["anyOf"]:
            try:
                validate_schema(value, candidate, path, depth + 1)
                return
            except ProviderError:
                pass
        raise ProviderError(f"Model JSON does not match the allowed types at {path}.")
    expected = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None)}
    if expected not in types or type(value) is not types[expected]:
        raise ProviderError(f"Model JSON has the wrong type at {path}.")
    if "enum" in schema and value not in schema["enum"]:
        raise ProviderError(f"Model JSON has an invalid enum at {path}.")
    if expected == "object":
        properties = schema.get("properties", {})
        if any(key not in value for key in schema.get("required", [])):
            raise ProviderError(f"Model JSON is missing required fields at {path}.")
        if schema.get("additionalProperties") is False and set(value) - set(properties):
            raise ProviderError(f"Model JSON contains unexpected fields at {path}.")
        for key, child in value.items():
            if key in properties:
                validate_schema(child, properties[key], f"{path}.{key}", depth + 1)
    elif expected == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)):
            raise ProviderError(f"Model JSON has an invalid list length at {path}.")
        for index, child in enumerate(value):
            validate_schema(child, schema["items"], f"{path}[{index}]", depth + 1)


def parse_model_json(content: str, schema: Mapping[str, Any]) -> tuple[dict, list[str]]:
    normalizations = []
    text = content.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1)
        normalizations.append("whole_response_json_fence_removed")

    def object_pairs(pairs: list) -> dict:
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=object_pairs)
    except (ValueError, RecursionError):
        raise ProviderError("Model did not return one complete JSON object; no review was generated.") from None
    validate_schema(value, schema)
    return value, normalizations


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _anthropic_schema(value: Any) -> Any:
    """Translate unsupported wire constraints; retain the full local schema.

    Anthropic accepts minItems 0/1, but not maxItems. This follows its documented
    SDK transformation without introducing a dependency on an SDK.
    """
    if isinstance(value, list):
        return [_anthropic_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {key: _anthropic_schema(item) for key, item in value.items() if key != "maxItems"}
    constraints = []
    if "maxItems" in value:
        constraints.append(f"At most {value['maxItems']} items.")
    if value.get("minItems", 0) > 1:
        result.pop("minItems")
        constraints.append(f"At least {value['minItems']} items.")
    if constraints:
        result["description"] = " ".join([value.get("description", ""), *constraints]).strip()
    return result


def _post_json(url: str, payload: dict, headers: dict, timeout: int) -> dict:
    request = Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                      headers={"Content-Type": "application/json", **headers}, method="POST")
    try:
        with build_opener(_NoRedirects()).open(request, timeout=timeout) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        code = error.code
        error.close()
        raise ProviderError(f"Model provider returned HTTP {code}; response body withheld. No retry or fallback was made.") from None
    except (OSError, URLError, HTTPException, ValueError):
        raise ProviderError("Model provider connection failed or timed out. No retry or fallback was made.") from None
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("Model provider response exceeded the size limit.")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (ValueError, RecursionError):
        raise ProviderError("Model provider returned an invalid JSON envelope.") from None
    if not isinstance(result, dict):
        raise ProviderError("Model provider returned an invalid response envelope.")
    return result


def run_api(config: ProviderConfig, instructions: str, source_context: str, schema: dict, *, images: list[dict] | None = None) -> ModelResult:
    images = images or []
    if images and (not config.supports_images or len(images) > 2):
        raise ProviderError("Image review requires an explicitly enabled image-capable API model; at most two images per request.")
    for item in images:
        try:
            raw = base64.b64decode(item["data_base64"], validate=True)
            valid = (item["mime_type"] == "image/png" and raw.startswith(b"\x89PNG\r\n\x1a\n")) or (item["mime_type"] == "image/jpeg" and raw.startswith(b"\xff\xd8\xff"))
            if not valid or len(raw) > 3_000_000:
                raise ValueError()
        except (KeyError, TypeError, ValueError):
            raise ProviderError("Invalid or oversized image input.") from None
    key = config.api_key()
    system = instructions
    if config.response_format != "json_schema":
        system += "\n<output-schema>\n" + json.dumps(schema, ensure_ascii=False, separators=(",", ":")) + "\n</output-schema>"
    source = "<source>\n" + source_context + "\n</source>"
    payload: dict[str, Any] = {"model": config.model, "max_tokens": config.max_output_tokens, "stream": False}
    if config.protocol == "responses":
        endpoint = config.base_url + "/responses"
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        payload.pop("max_tokens")
        payload.update(max_output_tokens=config.max_output_tokens, instructions=system, input=source, store=False)
        if images:
            payload["input"] = [{"role": "user", "content": [{"type": "input_text", "text": source}] + [
                {"type": "input_image", "image_url": "data:" + item["mime_type"] + ";base64," + item["data_base64"]} for item in images]}]
        if config.response_format == "json_schema":
            payload["text"] = {"format": {"type": "json_schema", "name": "awt_review", "strict": True, "schema": schema}}
        elif config.response_format == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}
    elif config.protocol == "anthropic-messages":
        endpoint = config.base_url + "/messages"
        headers = {"anthropic-version": "2023-06-01"}
        if key:
            headers["x-api-key"] = key
        payload.update(system=system, messages=[{"role": "user", "content": source}])
        if images:
            payload["messages"][0]["content"] = [{"type": "text", "text": source}] + [
                {"type": "image", "source": {"type": "base64", "media_type": item["mime_type"], "data": item["data_base64"]}} for item in images]
        if config.response_format == "json_schema":
            payload["output_config"] = {"format": {"type": "json_schema", "schema": _anthropic_schema(schema)}}
    else:
        endpoint = config.base_url + "/chat/completions"
        headers = {"Authorization": f"Bearer {key}"} if key else {}
        payload["messages"] = [{"role": "system", "content": system}, {"role": "user", "content": source}]
        if images:
            payload["messages"][1]["content"] = [{"type": "text", "text": source}] + [
                {"type": "image_url", "image_url": {"url": "data:" + item["mime_type"] + ";base64," + item["data_base64"]}} for item in images]
        if config.response_format == "json_schema":
            payload["response_format"] = {"type": "json_schema", "json_schema": {"name": "awt_review", "strict": True, "schema": schema}}
        elif config.response_format == "json_object":
            payload["response_format"] = {"type": "json_object"}
        if config.provider == "minimax":
            payload["reasoning_split"] = True
    started = time.monotonic()
    envelope = _post_json(endpoint, payload, headers, config.timeout_seconds)
    if envelope.get("error"):
        raise ProviderError("Model provider reported an error; response body withheld.")
    if config.protocol == "responses":
        output = envelope.get("output")
        if envelope.get("status") != "completed" or not isinstance(output, list):
            raise ProviderError("Responses API returned an incomplete response; no review was generated.")
        text_parts = []
        for item in output:
            if not isinstance(item, dict):
                raise ProviderError("Responses API returned an invalid output item.")
            if item.get("type") == "reasoning":
                continue
            if item.get("type") != "message" or item.get("role") != "assistant" or not isinstance(item.get("content"), list):
                raise ProviderError("Responses API returned an unsupported item or tool request.")
            for block in item["content"]:
                if not isinstance(block, dict) or block.get("type") != "output_text" or not isinstance(block.get("text"), str):
                    raise ProviderError("Responses API returned a refusal or invalid output text.")
                text_parts.append(block["text"])
        content = "\n".join(text_parts)
    elif config.protocol == "anthropic-messages":
        blocks = envelope.get("content")
        if envelope.get("stop_reason") != "end_turn" or not isinstance(blocks, list):
            raise ProviderError("Claude response was refused, truncated, or incomplete; no review was generated.")
        if any(not isinstance(block, dict) or block.get("type") not in {"text", "thinking", "redacted_thinking"} for block in blocks):
            raise ProviderError("Claude returned an unsupported content block or tool request.")
        text_parts = [block.get("text") for block in blocks if block["type"] == "text"]
        if not text_parts or any(not isinstance(part, str) for part in text_parts):
            raise ProviderError("Claude response contained no final review text.")
        content = "\n".join(text_parts)
    else:
        choices = envelope.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ProviderError("Model provider returned no unique completion.")
        choice = choices[0]
        message = choice.get("message")
        if choice.get("finish_reason") != "stop" or not isinstance(message, dict):
            raise ProviderError("Model response was truncated or incomplete; no review was generated.")
        if message.get("refusal") or message.get("tool_calls") or message.get("function_call"):
            raise ProviderError("Model refused the request or requested tools; no review was generated.")
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderError("Model response contained no final review text.")
    value, normalizations = parse_model_json(content, schema)
    usage = envelope.get("usage", {})
    usage = usage if isinstance(usage, dict) else {}
    metadata = config.public_metadata()
    metadata.update(
        returned_model=envelope.get("model") if isinstance(envelope.get("model"), str) else None,
        elapsed_seconds=round(time.monotonic() - started, 3),
        usage={field: usage[field] for field in ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "total_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
               if type(usage.get(field)) is int and usage[field] >= 0},
        normalizations=normalizations,
        live_response_received=True,
        images_sent=len(images),
        wire_schema_constraints_validated_locally=config.protocol == "anthropic-messages" and config.response_format == "json_schema",
    )
    return ModelResult(value, metadata)
