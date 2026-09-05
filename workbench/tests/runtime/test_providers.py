"""Offline transport contracts, never a claim of live model quality."""

from __future__ import annotations

import base64
import copy
import io
import json
import os
import tempfile
import threading
import unittest
from contextlib import contextmanager, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from awt.mvp import (
    MvpApplication, MvpError, OUTPUT_SCHEMA, SessionStore, _print_runtime_check,
    analyse_document, configured_runner,
)
from awt.providers import (
    PRESETS, ModelResult, ProviderError, load_provider_config, parse_model_json,
    run_api, validate_schema,
)
from test_mvp_runtime import SOURCE, empty_runner, replacement_runner


REVIEW = empty_runner("", "", "")
KEY = "offline-test-key-not-a-real-credential"


def envelope(protocol, review=REVIEW):
    content = json.dumps(review)
    common = {"model": "server-returned-fixture-model", "usage": {"input_tokens": 100, "output_tokens": 40, "secret": KEY}}
    if protocol == "anthropic-messages":
        return {**common, "stop_reason": "end_turn", "content": [{"type": "thinking", "thinking": "fixture reasoning"}, {"type": "text", "text": content}]}
    if protocol == "responses":
        return {**common, "status": "completed", "output": [{"type": "reasoning"}, {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": content}]}]}
    return {**common, "choices": [{"finish_reason": "stop", "message": {"role": "assistant", "content": content, "reasoning_content": "fixture reasoning"}}]}


@contextmanager
def server_fixture(response, status=200, headers=None):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, request, dict(self.headers)))
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            data = json.dumps(response).encode()
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        clean = {key: value for key, value in os.environ.items() if not key.startswith("AWT_")}
        clean["AWT_TEST_KEY"] = KEY
        self.environment = patch.dict(os.environ, clean, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def config(self, provider="deepseek", **overrides):
        values = {"AWT_PROVIDER": provider, "AWT_MODEL": "public-fixture-model", "AWT_API_KEY_ENV": "AWT_TEST_KEY", **overrides}
        return load_provider_config(values)

    def test_all_api_presets_use_the_expected_transport_and_auth(self):
        for provider, (protocol, _, _, mode) in PRESETS.items():
            if provider == "codex":
                continue
            with self.subTest(provider=provider), server_fixture(envelope(protocol)) as (url, requests):
                config = self.config(provider, AWT_BASE_URL=url)
                result = run_api(config, "Return a JSON review.", "SOURCE IS DATA", OUTPUT_SCHEMA)
                self.assertEqual(result, REVIEW)
                self.assertIsInstance(result, ModelResult)
                self.assertEqual(result.metadata["returned_model"], "server-returned-fixture-model")
                self.assertNotIn(KEY, json.dumps(result.metadata))
                path, payload, headers = requests[0]
                self.assertEqual(len(requests), 1)
                self.assertEqual(payload["model"], "public-fixture-model")
                self.assertNotIn("temperature", payload)
                self.assertNotIn("tools", payload)
                if protocol == "anthropic-messages":
                    self.assertEqual(path, "/v1/messages")
                    self.assertEqual(headers["X-Api-Key"], KEY)
                    wire = payload["output_config"]["format"]["schema"]
                    self.assertNotIn('"maxItems"', json.dumps(wire))
                    self.assertIn('"maxItems"', json.dumps(OUTPUT_SCHEMA))
                    self.assertIn("At most 3 items.", json.dumps(wire))
                    self.assertNotIn("SOURCE IS DATA", payload["system"])
                elif protocol == "responses":
                    self.assertEqual(path, "/v1/responses")
                    self.assertFalse(payload["store"])
                    self.assertNotIn("max_tokens", payload)
                    self.assertEqual(payload["text"]["format"]["schema"], OUTPUT_SCHEMA)
                else:
                    self.assertEqual(path, "/v1/chat/completions")
                    self.assertEqual(headers["Authorization"], "Bearer " + KEY)
                    self.assertNotIn("SOURCE IS DATA", payload["messages"][0]["content"])
                    self.assertIn("SOURCE IS DATA", payload["messages"][1]["content"])
                    if mode == "prompt":
                        self.assertNotIn("response_format", payload)
                        self.assertIn("output-schema", payload["messages"][0]["content"])
                    else:
                        self.assertEqual(payload["response_format"]["type"], mode)
                    if provider == "minimax":
                        self.assertTrue(payload["reasoning_split"])

    def test_defaults_and_custom_protocol(self):
        self.assertEqual(load_provider_config({}).provider, "codex")
        self.assertEqual(load_provider_config({}).model, "")
        config = self.config("openai-compatible", AWT_BASE_URL="https://example.org/v1/", AWT_PROTOCOL="responses", AWT_RESPONSE_FORMAT="json_schema")
        self.assertEqual(config.base_url, "https://example.org/v1")
        self.assertEqual(config.protocol, "responses")

    def test_invalid_configuration_is_rejected_without_exposing_values(self):
        bad_values = [
            {"AWT_PROVIDER": "unknown"}, {"AWT_MODEL": ""},
            {"AWT_MODEL": "model&command"}, {"AWT_MODEL": "model%VARIABLE%"},
            {"AWT_BASE_URL": "https://user:" + KEY + "@example.org/v1"},
            {"AWT_BASE_URL": "https://example.org/v1?key=" + KEY},
            {"AWT_BASE_URL": "http://example.org/v1"},
            {"AWT_BASE_URL": "https://example.org/v1/chat/completions"},
            {"AWT_MAX_OUTPUT_TOKENS": "-1"}, {"AWT_REQUEST_TIMEOUT": "0"},
            {"AWT_PROTOCOL": "codex-cli"}, {"AWT_API_KEY_ENV": "not a variable"},
        ]
        for values in bad_values:
            with self.subTest(values=values), self.assertRaises(ProviderError) as caught:
                self.config(**values)
            self.assertNotIn(KEY, str(caught.exception))

    def test_missing_remote_key_stops_before_request_but_local_keys_are_optional(self):
        config = self.config(AWT_API_KEY_ENV="ABSENT_AWT_TEST_KEY")
        with patch("awt.providers._post_json") as post, self.assertRaises(ProviderError):
            run_api(config, "JSON", "fixture", OUTPUT_SCHEMA)
        post.assert_not_called()
        self.assertEqual(self.config("ollama", AWT_API_KEY_ENV="ABSENT_AWT_TEST_KEY").api_key(), "")

    def test_schema_is_local_in_all_format_modes(self):
        invalid = copy.deepcopy(REVIEW)
        invalid["author_approved"] = True
        for mode in ("json_object", "json_schema", "prompt"):
            with self.subTest(mode=mode), server_fixture(envelope("chat-completions", invalid)) as (url, requests):
                with self.assertRaisesRegex(ProviderError, "unexpected fields"):
                    run_api(self.config(AWT_BASE_URL=url, AWT_RESPONSE_FORMAT=mode), "JSON", "fixture", OUTPUT_SCHEMA)
                self.assertEqual(len(requests), 1)

    def test_json_normalisation_is_bounded_and_recorded(self):
        result, notes = parse_model_json("```json\n" + json.dumps(REVIEW) + "\n```", OUTPUT_SCHEMA)
        self.assertEqual(result, REVIEW)
        self.assertEqual(len(notes), 1)
        for text in ("Explanation\n" + json.dumps(REVIEW), '<think>hidden</think>' + json.dumps(REVIEW), '{"status":"pass","status":"warn"}'):
            with self.subTest(text=text), self.assertRaises(ProviderError):
                parse_model_json(text, OUTPUT_SCHEMA)
        invalid = replacement_runner(SOURCE.decode(), "audit", "preprint")
        invalid["issues"][0]["action_options"][0]["canonical"] = "false"
        with self.assertRaises(ProviderError):
            validate_schema(invalid, OUTPUT_SCHEMA)

    def test_anthropic_wire_schema_does_not_relax_local_array_constraints(self):
        invalid = replacement_runner(SOURCE.decode(), "audit", "preprint")
        invalid["issues"][0]["action_options"] *= 4
        with server_fixture(envelope("anthropic-messages", invalid)) as (url, _):
            with self.assertRaisesRegex(ProviderError, "list length"):
                run_api(self.config("anthropic", AWT_BASE_URL=url), "JSON", "fixture", OUTPUT_SCHEMA)

    def test_incomplete_or_refused_responses_are_never_repaired_or_retried(self):
        for provider, protocol, field, value in (
            ("anthropic", "anthropic-messages", "stop_reason", "refusal"),
            ("anthropic", "anthropic-messages", "stop_reason", "max_tokens"),
            ("openai", "responses", "status", "incomplete"),
            ("deepseek", "chat-completions", "finish_reason", "length"),
            ("deepseek", "chat-completions", "finish_reason", "tool_calls"),
        ):
            response = envelope(protocol)
            (response["choices"][0] if protocol == "chat-completions" else response)[field] = value
            with self.subTest(provider=provider, value=value), server_fixture(response) as (url, requests):
                with self.assertRaises(ProviderError):
                    run_api(self.config(provider, AWT_BASE_URL=url), "JSON", "fixture", OUTPUT_SCHEMA)
                self.assertEqual(len(requests), 1)

    def test_http_errors_and_redirects_do_not_leak_credentials(self):
        for status in (401, 429, 500, 307):
            with self.subTest(status=status), server_fixture({"error": KEY}, status, {"Location": "https://example.org/"}) as (url, requests):
                with self.assertRaises(ProviderError) as caught:
                    run_api(self.config(AWT_BASE_URL=url), "JSON", "fixture", OUTPUT_SCHEMA)
                self.assertNotIn(KEY, str(caught.exception))
                self.assertIn(str(status), str(caught.exception))
                self.assertEqual(len(requests), 1)

    def test_real_transport_still_runs_source_and_evidence_validation(self):
        review = replacement_runner(SOURCE.decode(), "audit", "preprint")
        review["issues"][0]["source_refs"] = ["invented-evidence-id"]
        with server_fixture(envelope("chat-completions", review)) as (url, _):
            with patch.dict(os.environ, {"AWT_PROVIDER": "deepseek", "AWT_MODEL": "fixture", "AWT_BASE_URL": url, "AWT_API_KEY_ENV": "AWT_TEST_KEY"}):
                with self.assertRaisesRegex(MvpError, "source_refs"):
                    analyse_document(SOURCE, "paper.md", "audit", "preprint")

    def test_provider_metadata_survives_session_restore_without_another_call(self):
        with tempfile.TemporaryDirectory() as directory, server_fixture(envelope("chat-completions")) as (url, requests):
            with patch.dict(os.environ, {"AWT_PROVIDER": "glm", "AWT_MODEL": "fixture", "AWT_BASE_URL": url, "AWT_API_KEY_ENV": "AWT_TEST_KEY"}):
                store = SessionStore(Path(directory))
                app = MvpApplication(store=store)
                result = app.analyse({"filename": "paper.md", "content_base64": base64.b64encode(SOURCE).decode(), "workflow_id": "audit", "manuscript_purpose": "preprint"})
                restored = store.load(result["session_id"])["analysis"]
                self.assertEqual(restored["model_run"]["provider"], "glm")
                self.assertEqual(restored["model_run"]["returned_model"], "server-returned-fixture-model")
                self.assertTrue(restored["source_unchanged"])
                self.assertFalse(restored["writing_effect_proven"])
                self.assertEqual(len(requests), 1)
                self.assertNotIn(KEY, json.dumps(restored))

    def test_codex_remains_the_default_and_accepts_an_explicit_model(self):
        with patch("awt.mvp.codex_runner", return_value=REVIEW) as runner:
            result = configured_runner("fixture", "audit", "preprint")
            self.assertEqual(result.metadata["provider"], "codex")
            self.assertIsNone(result.metadata["returned_model"])
            self.assertIsNone(runner.call_args.kwargs["model"])
        with patch.dict(os.environ, {"AWT_MODEL": "explicit-cli-model"}), patch("awt.mvp.codex_runner", return_value=REVIEW) as runner:
            configured_runner("fixture", "audit", "preprint")
            self.assertEqual(runner.call_args.kwargs["model"], "explicit-cli-model")

    def test_api_preflight_is_offline_and_never_prints_the_key(self):
        with patch.dict(os.environ, {"AWT_PROVIDER": "anthropic", "AWT_MODEL": "claude-fable-5-1", "AWT_API_KEY_ENV": "AWT_TEST_KEY"}):
            output = io.StringIO()
            with redirect_stdout(output), patch("awt.providers._post_json") as post:
                self.assertEqual(_print_runtime_check(), 0)
            post.assert_not_called()
            self.assertNotIn(KEY, output.getvalue())
            self.assertIn("untested", output.getvalue())


if __name__ == "__main__":
    unittest.main()
