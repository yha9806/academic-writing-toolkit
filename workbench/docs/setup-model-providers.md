# Model providers in the local Workbench

Run the commands in this guide from the repository's `workbench/` directory.
See [the component README](../README.md) for installation from the repository root.

This guide describes the current source checkout. The published v0.5.0 wheel
does not contain these adapters. Install the checkout with `python -m pip install -e .`.
Run `awt --list-providers` to inspect the provider presets without a network call.

## What is shared, and what varies

All providers receive the same lean instruction kernel, one task card, and the
selected manuscript/evidence context. API messages separate instructions from
source data. Providers may propose a review; AWT validates its schema, evidence
references, verification states, and exact replacements locally. The author
still reviews findings and explicitly confirms an exported copy.

The provider profile selects a protocol and output format. A weaker output
format does not weaken local validation. No transport executes model-requested
tools, automatically retries, changes provider after failure, or saves API keys.
Only an entire JSON code fence can be removed, with that normalisation recorded.
Extra prose, inline reasoning, malformed JSON, incomplete responses, refusals,
unknown evidence IDs, and invalid edits fail visibly.

Anthropic's wire schema omits unsupported array bounds such as `maxItems` and
describes them in text; the original schema still enforces those bounds locally.
This follows the documented [Claude schema transformation](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

## Configure a provider

Set credentials in the named environment variable using your normal local
secret-management method. Do not put keys in profiles, command-line arguments,
manuscripts, browser forms, or Git. No additional Python SDK is required.

PowerShell, assuming `ANTHROPIC_API_KEY` is already set:

```powershell
$env:AWT_PROVIDER = 'anthropic'
$env:AWT_MODEL = 'claude-fable-5-1'
awt --check
awt
```

For DeepSeek, use `AWT_PROVIDER=deepseek` and an account-available model ID such
as `deepseek-v4-flash`, with `DEEPSEEK_API_KEY`. For GLM, use `AWT_PROVIDER=glm`
and your account's model ID, with `ZHIPU_API_KEY`. International Z.AI credentials
use the separate `zai` preset and `ZAI_API_KEY`.

POSIX shell, assuming `DEEPSEEK_API_KEY` is already set:

```sh
export AWT_PROVIDER=deepseek
export AWT_MODEL=deepseek-v4-flash
awt --check
awt
```

`--check` validates local configuration and credential presence only. It does
not validate account access, model availability, request compatibility, or
writing quality. The browser displays the configured provider and endpoint
before a review. Run records preserve the requested model, the model ID returned
by an API when present, numeric usage, and timing. A provider's returned ID is
reported metadata, not independent proof of the model behind a gateway.

## Provider presets

Endpoints were checked against the linked primary documentation on 2026-09-05.
They are connection presets, not a claim that every hosted model was tested.
Choose the exact model ID your account or local server exposes.

| AWT_PROVIDER | Protocol | Default base URL | Key environment variable | Default format |
|---|---|---|---|---|
| codex | Codex CLI | local authenticated CLI | CLI authentication | json_schema |
| openai | Responses | https://api.openai.com/v1 | OPENAI_API_KEY | json_schema |
| anthropic | Messages | https://api.anthropic.com/v1 | ANTHROPIC_API_KEY | json_schema |
| deepseek | Chat Completions | https://api.deepseek.com | DEEPSEEK_API_KEY | json_object |
| glm | Chat Completions | https://open.bigmodel.cn/api/paas/v4 | ZHIPU_API_KEY | json_object |
| zai | Chat Completions | https://api.z.ai/api/paas/v4 | ZAI_API_KEY | json_object |
| gemini | Chat Completions | https://generativelanguage.googleapis.com/v1beta/openai | GEMINI_API_KEY | json_schema |
| qwen | Chat Completions | https://dashscope.aliyuncs.com/compatible-mode/v1 | DASHSCOPE_API_KEY | prompt |
| kimi | Chat Completions | https://api.moonshot.ai/v1 | MOONSHOT_API_KEY | prompt |
| minimax | Chat Completions | https://api.minimax.io/v1 | MINIMAX_API_KEY | prompt |
| mistral | Chat Completions | https://api.mistral.ai/v1 | MISTRAL_API_KEY | json_object |
| xai | Chat Completions | https://api.x.ai/v1 | XAI_API_KEY | prompt |
| groq | Chat Completions | https://api.groq.com/openai/v1 | GROQ_API_KEY | prompt |
| together | Chat Completions | https://api.together.ai/v1 | TOGETHER_API_KEY | prompt |
| fireworks | Chat Completions | https://api.fireworks.ai/inference/v1 | FIREWORKS_API_KEY | prompt |
| openrouter | Chat Completions | https://openrouter.ai/api/v1 | OPENROUTER_API_KEY | prompt |
| ollama | Chat Completions | http://localhost:11434/v1 | AWT_API_KEY, optional locally | prompt |
| lmstudio | Chat Completions | http://localhost:1234/v1 | AWT_API_KEY, optional locally | prompt |
| openai-compatible | Chat Completions | set AWT_BASE_URL | AWT_API_KEY | json_object |

The `prompt` presets intentionally omit provider-specific constrained-decoding
parameters because available models differ. If your chosen model supports
`json_schema` or `json_object`, select it explicitly with `AWT_RESPONSE_FORMAT`.

The multi-document Workbench text route uses a separate source-choice schema.
For newly created local Ollama jobs, it defaults to `json_schema`; an explicit
`AWT_RESPONSE_FORMAT` overrides this choice. Other API models retain the portable
prompt default unless explicitly configured. Image review keeps its existing
prompt transport. There is no automatic format fallback or retry.
[Ollama documents native schema constraints](https://docs.ollama.com/capabilities/structured-outputs)
through its OpenAI-compatible `response_format`. AWT still validates every
selected source ID, exact source-owned quote, required observation and length
limit locally; structured JSON is not a review-quality guarantee.
For MiniMax Chat Completions, AWT sets the documented `reasoning_split=true` so
reasoning stays outside the final review. It does not strip `<think>` tags from
model-authored content to make a malformed review appear valid.

### Regional and custom endpoints

Set `AWT_BASE_URL` to the API root, without `/messages`, `/responses`, or
`/chat/completions`. Qwen's preset is the shared Beijing endpoint. Alibaba also
documents workspace-specific and regional endpoints; use the base URL matching
your key. A custom Workbench is an API client, so use credentials and an endpoint
that permit that use rather than assuming a coding subscription covers it.
Set a custom gateway's key variable with `AWT_API_KEY_ENV`.

`AWT_PROTOCOL` can explicitly select `responses`, `anthropic-messages`, or
`chat-completions` for an API preset. It changes the wire format, not model
behaviour. For a new Anthropic-compatible gateway, for example:

```powershell
$env:AWT_PROVIDER = 'openai-compatible'
$env:AWT_PROTOCOL = 'anthropic-messages'
$env:AWT_BASE_URL = 'https://your-authorised-gateway.example/v1'
$env:AWT_MODEL = 'your-model-id'
$env:AWT_RESPONSE_FORMAT = 'prompt'
$env:AWT_API_KEY_ENV = 'MY_GATEWAY_KEY'
```

Remote endpoints require HTTPS. HTTP is accepted only for loopback servers.
Redirects are rejected instead of forwarding credentials to a different endpoint.
Ollama and LM Studio models must already be installed/loaded and configured with
enough context for the selected materials. The 20,000-token local input ceiling
is a budget, not a statement about a particular model's context capacity; select
smaller materials for smaller models. Token estimates are not provider bills.

## Optional settings

| Variable | Meaning |
|---|---|
| AWT_MODEL | Explicit API model ID; optional Codex `--model` override |
| AWT_RESPONSE_FORMAT | `json_schema`, `json_object`, or `prompt`; Messages supports the first and last |
| AWT_MAX_OUTPUT_TOKENS | API output budget, default 8192, allowed 256–128000; provider limits still apply |
| AWT_REQUEST_TIMEOUT | API socket timeout in seconds, default 300, allowed 1–1800 |
| AWT_CODEX_BIN | Existing Codex executable override |

Reasoning, temperature, and tool parameters are not assumed to be interchangeable
across models. The initial adapters leave reasoning and sampling at provider
defaults. API failures report status without displaying response bodies, which
may echo private content. No repair request is sent automatically.

To return to Codex, set `AWT_PROVIDER=codex` and clear API-only `AWT_BASE_URL`,
`AWT_PROTOCOL`, `AWT_API_KEY_ENV`, and `AWT_RESPONSE_FORMAT` overrides. Clear
`AWT_MODEL` too if you want the CLI default. AWT never treats the Codex desktop
model picker as the Workbench's active model selection.

## Test compatibility

The cross-document route also provides [small-context, economical and balanced
job profiles](setup-project-review.md), checkpoint reuse, request limits and
opt-in image review. `AWT_SUPPORTS_IMAGES=1` explicitly enables API image inputs
for a model you know supports them; its default is `0`. Clear this setting when
returning to Codex or a text-only model. No current pricing table or automatic
stronger-model fallback is assumed.

Run the offline HTTP/schema/evidence/session tests with:

```sh
python -m unittest discover -s tests/runtime -p 'test_*.py' -v
```

The optional `scripts/check-model-compatibility.py` loads profiles from
`examples/model-compatibility/profiles.json`. Its default is a dry run. With
`--live`, it sends only a fixed public fictional manuscript through the chosen
profiles. The report distinguishes output-contract success from writing quality.
No production manuscript is read by this script.

## Primary interface references

- [OpenAI Responses](https://developers.openai.com/api/docs/guides/text)
- [Claude Messages](https://platform.claude.com/docs/en/api/http/messages/create) and [Fable 5.1](https://platform.claude.com/docs/en/models/fable-5-1/overview)
- [DeepSeek API](https://api-docs.deepseek.com/) and [GLM HTTP API](https://docs.bigmodel.cn/cn/guide/develop/http/introduction)
- [Z.AI compatibility](https://docs.z.ai/guides/develop/openai/python) and [Gemini compatibility](https://ai.google.dev/gemini-api/docs/openai)
- [Qwen endpoints](https://www.alibabacloud.com/help/en/model-studio/base-url) and [Kimi quickstart](https://platform.kimi.ai/docs/overview)
- [MiniMax compatibility](https://platform.minimax.io/docs/api-reference/text-openai-api), [Mistral Chat](https://docs.mistral.ai/api/endpoint/chat), and [xAI Chat](https://docs.x.ai/developers/rest-api-reference/inference/chat)
- [Groq](https://console.groq.com/docs/openai), [Together](https://docs.together.ai/docs/inference/openai-compatibility), [Fireworks](https://docs.fireworks.ai/tools-sdks/openai-compatibility), and [OpenRouter](https://openrouter.ai/docs/api_reference/overview)
- [Ollama](https://docs.ollama.com/api/openai-compatibility) and [LM Studio](https://lmstudio.ai/docs/developer/openai-compat)
