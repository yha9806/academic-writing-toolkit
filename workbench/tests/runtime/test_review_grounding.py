"""Source-choice contracts and rejected-call accounting, without live models."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from awt.cross_review import (
    CHECK_SCHEMA, SOURCE_SCHEMA, _candidates, decode_grounded_review,
    grounded_request, input_estimate, source_payload, tokens, validate_review,
)
from awt.documents import import_document
from awt.providers import ModelResult, ProviderError, load_provider_config
from awt.review_jobs import JobManager, default_call
from test_project_review import upload
from test_providers import envelope, server_fixture


def wire_result():
    return {"checks": [{"source_id": "S1", "observation": "The source reports 90%."}],
            "claims": [], "findings": [], "limitations": []}


class ReviewGroundingTests(unittest.TestCase):
    def setUp(self):
        self.blocks = [
            {"id": "long-document-block-1", "locator": "p1, paragraph 1", "section": "Abstract",
             "kind": "paragraph", "text": "The response rate was 90%."},
            {"id": "long-document-block-2", "locator": "p2, paragraph 4", "section": "Results",
             "kind": "paragraph", "text": "The response rate was 70%."},
        ]
        self.context = source_payload(self.blocks, "Compare response rates", "cross")
        self.instructions, self.wire, self.sources = grounded_request(self.context)

    def test_model_selects_ids_and_program_preserves_exact_source(self):
        request = json.loads(self.wire)
        self.assertEqual([b["source_id"] for b in request["materials"]], ["S1", "S2"])
        self.assertNotIn("long-document-block-", self.wire)
        value = wire_result()
        value["findings"] = [{"severity": "medium", "message": "The reported rates differ.",
                              "source_ids": ["S1", "S2"], "needs_visual": False}]
        result = decode_grounded_review(value, self.sources)
        validate_review(result, self.blocks)
        self.assertEqual(result["findings"][0]["anchors"], [
            {"locator": b["id"], "quote": b["text"]} for b in self.blocks])
        self.assertIn("不代表全文结论", result["summary"])
        self.assertNotIn("summary", SOURCE_SCHEMA["properties"])

    def test_duplicate_text_is_not_searched_or_reassigned(self):
        self.blocks[1]["text"] = self.blocks[0]["text"]
        _, _, sources = grounded_request(source_payload(self.blocks, "Check", "text"))
        value = wire_result()
        value["checks"][0]["source_id"] = "S2"
        result = decode_grounded_review(value, sources)
        self.assertEqual(result["checks"][0]["locator"], self.blocks[1]["id"])

    def test_unknown_identifiers_fail_at_every_anchor_position(self):
        for position in ("check", "claim", "evidence", "finding"):
            for identifier in ("S3", "s1", " S1", self.blocks[0]["id"]):
                with self.subTest(position=position, identifier=identifier):
                    value = wire_result()
                    if position == "check":
                        value["checks"][0]["source_id"] = identifier
                    elif position in {"claim", "evidence"}:
                        value["claims"] = [{"source_id": identifier if position == "claim" else "S1",
                            "note": "Compare", "evidence": [] if position == "claim" else [
                                {"source_id": identifier, "relation": "context_only"}]}]
                    else:
                        value["findings"] = [{"severity": "low", "message": "Compare",
                            "source_ids": [identifier], "needs_visual": False}]
                    with self.assertRaises(ProviderError):
                        decode_grounded_review(value, self.sources)

    def test_empty_observations_fail_but_no_findings_is_valid(self):
        validate_review(decode_grounded_review(wire_result(), self.sources), self.blocks)
        for checks in ([], [{"source_id": "S1", "observation": " \n"}]):
            value = wire_result()
            value["checks"] = checks
            with self.assertRaises(ProviderError):
                decode_grounded_review(value, self.sources)
        for summary in ("", " \n"):
            with self.assertRaises(ProviderError):
                validate_review({"summary": summary, "claims": [], "findings": [], "limitations": []}, self.blocks)

    def test_only_offered_excerpt_is_quoted_and_tampering_still_fails(self):
        excerpt = {**self.blocks[0], "text": "response rate was 90%"}
        _, _, sources = grounded_request(source_payload([excerpt], "Check", "chapter"))
        result = decode_grounded_review(wire_result(), sources)
        self.assertEqual(result["checks"][0]["quote"], excerpt["text"])
        result["checks"][0]["quote"] = self.blocks[0]["text"]
        with self.assertRaises(ProviderError):
            validate_review(result, [excerpt])

    def test_reservation_covers_actual_wire_schema_and_prompt(self):
        for phase in ("text", "chapter", "cross"):
            instructions, context, _ = grounded_request(source_payload(self.blocks, "Check", phase))
            estimate = tokens(instructions + context + json.dumps(SOURCE_SCHEMA, ensure_ascii=False, separators=(",", ":")))
            self.assertGreaterEqual(input_estimate(self.blocks, "Check", phase), estimate + 150)

    def test_production_transport_returns_canonical_result_and_wire_audit(self):
        with server_fixture(envelope("chat-completions", wire_result())) as (url, requests):
            config = load_provider_config({"AWT_PROVIDER": "ollama", "AWT_MODEL": "offline-fixture", "AWT_BASE_URL": url})
            result = default_call(config, "unused", self.context, CHECK_SCHEMA, [])
        validate_review(result, self.blocks)
        self.assertEqual(len(requests), 1)
        self.assertEqual(result.review_wire, wire_result())
        self.assertEqual(result.metadata["review_protocol"], "source-ids-v2")
        self.assertEqual(len(result.metadata["source_map_sha256"]), 64)
        self.assertEqual(len(result.metadata["wire_response_sha256"]), 64)

    def test_rejected_choices_retain_usage_and_do_not_advance_coverage(self):
        invalid = wire_result()
        invalid["checks"][0]["source_id"] = "S9999"
        clean = {k: v for k, v in os.environ.items() if not k.startswith("AWT_")}
        clean.update(AWT_PROVIDER="ollama", AWT_MODEL="offline-fixture")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, clean, clear=True):
            manager = JobManager(Path(directory))
            try:
                job = manager.create({"files": [upload("paper.md", "# Abstract\nThe rate was 90%.")], "goal": "Check"})
                with patch("awt.review_jobs.run_api", return_value=ModelResult(invalid, {"usage": {"input_tokens": 100, "output_tokens": 40}})) as call:
                    manager.start({"job_id": job["id"]})
                    manager.workers[job["id"]].join(5)
                snapshot = manager.snapshot(job["id"])
                self.assertEqual(snapshot["state"], "failed", snapshot["error"])
                self.assertEqual(call.call_count, 1)
                self.assertEqual(snapshot["calls_reserved"], 1)
                self.assertEqual(snapshot["progress"]["completed"], 0)
                self.assertTrue(all(row["checked_blocks"] == 0 for row in snapshot["coverage"]))
                attempt = manager._load(job["id"])["steps"][0]["attempts"][0]
                self.assertEqual(attempt["review_wire"], invalid)
                self.assertEqual(attempt["model_run"]["usage"]["output_tokens"], 40)
                self.assertNotIn("review_wire", snapshot["steps"][0]["attempts"][0])
            finally:
                manager.close()

    def test_schema_rejection_retains_original_object_and_measured_usage(self):
        invalid = {"checks": [], "claims": [], "findings": [], "limitations": []}
        with server_fixture(envelope("chat-completions", invalid)) as (url, requests):
            config = load_provider_config({"AWT_PROVIDER": "ollama", "AWT_MODEL": "offline-fixture", "AWT_BASE_URL": url})
            with self.assertRaises(ProviderError) as rejected:
                default_call(config, "unused", self.context, CHECK_SCHEMA, [])
        result = rejected.exception.model_result
        self.assertEqual(len(requests), 1)
        self.assertEqual(result.review_wire, invalid)
        self.assertEqual(result.metadata["usage"], {"input_tokens": 100, "output_tokens": 40})

    def test_overlong_observations_fail_instead_of_silently_truncating(self):
        value = wire_result()
        value["checks"][0]["observation"] = "x" * 65
        with self.assertRaises(ProviderError):
            decode_grounded_review(value, self.sources)

    def test_malformed_json_is_not_recorded_as_an_original_empty_object(self):
        response = envelope("chat-completions", wire_result())
        response["choices"][0]["message"]["content"] = '{"checks":'
        with server_fixture(response) as (url, requests):
            config = load_provider_config({"AWT_PROVIDER": "ollama", "AWT_MODEL": "offline-fixture", "AWT_BASE_URL": url})
            with self.assertRaises(ProviderError) as rejected:
                default_call(config, "unused", self.context, CHECK_SCHEMA, [])
        result = rejected.exception.model_result
        self.assertEqual(len(requests), 1)
        self.assertFalse(hasattr(result, "review_wire"))
        self.assertFalse(result.metadata["rejected_response_parseable"])
        self.assertNotIn("wire_response_sha256", result.metadata)

    def test_local_schema_default_and_explicit_prompt_override(self):
        clean = {k: v for k, v in os.environ.items() if not k.startswith("AWT_")}
        clean.update(AWT_PROVIDER="ollama", AWT_MODEL="offline-fixture")
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, clean, clear=True):
            manager = JobManager(Path(directory))
            try:
                payload = {"files": [upload("paper.md", "# Abstract\nThe rate was 90%.")], "goal": "Check"}
                job = manager.create(payload)
                self.assertEqual(manager._load(job["id"])["config"]["response_format"], "json_schema")
                with patch.dict(os.environ, {"AWT_RESPONSE_FORMAT": "prompt"}):
                    job = manager.create(payload)
                self.assertEqual(manager._load(job["id"])["config"]["response_format"], "prompt")
            finally:
                manager.close()

    def test_observations_are_carried_to_later_stages_without_claims(self):
        doc = import_document("paper.md", ("# Results\n" + "\n".join(
            "Paragraph %d reports a rate of 70%%." % n for n in range(40))).encode())
        block = doc["blocks"][17]
        result = {"summary": "Local observation", "checks": [{"locator": block["id"], "quote": block["text"], "note": "70%"}],
                  "claims": [], "findings": [], "limitations": []}
        job = {"documents": [doc], "revision": 1, "steps": [{"id": "text-1", "revision": 1, "phase": "text",
            "block_ids": [b["id"] for b in doc["blocks"]],
            "status": "completed", "result": result}]}
        self.assertIn(block["id"], [b["id"] for b in _candidates(job)])


if __name__ == "__main__":
    unittest.main()
