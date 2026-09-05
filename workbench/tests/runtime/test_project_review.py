"""Offline multi-document, checkpoint, budget, import and visual boundaries."""

from __future__ import annotations

import base64
import copy
import importlib.util
import io
import json
import os
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from awt.cross_review import CHECK_SCHEMA, validate_review
from awt.documents import DocumentError, compare_layout, digest, import_document, render_pdf_page
from awt.providers import ModelResult, ProviderError, load_provider_config, run_api
from awt.review_jobs import JobManager
from test_providers import envelope, server_fixture

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=")


def upload(name, value):
    data = value.encode() if isinstance(value, str) else value
    return {"filename": name, "content_base64": base64.b64encode(data).decode()}


def fixture_call(config, instructions, context, schema, images):
    request = json.JSONDecoder().raw_decode(context)[0]
    blocks = request["materials"]
    claim = [{"locator": blocks[0]["locator"], "quote": blocks[0]["text"], "evidence": [], "note": "Offline fixture"}] if blocks else []
    if claim and len(blocks) > 1:
        claim[0]["evidence"] = [{"locator": blocks[-1]["locator"], "quote": blocks[-1]["text"], "relation": "context_only"}]
    return ModelResult({"summary": "Offline contract fixture", "claims": claim, "findings": [], "limitations": []},
                       {"provider": config.provider, "returned_model": "offline-fixture", "usage": {"input_tokens": 100, "output_tokens": 80}})


def docx_bytes():
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Results</w:t></w:r></w:p>
<w:p><w:r><w:t>The response rate was 70%.</w:t></w:r><w:r><w:drawing><a:blip r:embed="rId1"/></w:drawing></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Response rate</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>70%</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>''')
        archive.writestr("word/_rels/document.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="media/image1.png"/><Relationship Id="external" TargetMode="External" Target="https://example.invalid/private"/></Relationships>')
        archive.writestr("word/media/image1.png", PNG)
    return output.getvalue()


class ProjectReviewTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.environment = patch.dict(os.environ, {**{k:v for k,v in os.environ.items() if not k.startswith("AWT_")},
            "AWT_PROVIDER":"ollama", "AWT_MODEL":"old-text-fixture"}, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.calls = []
        self.block = None
        def call(*args):
            self.calls.append(args)
            if self.block:
                self.block.wait(5)
            return fixture_call(*args)
        self.manager = JobManager(Path(self.directory.name), call=call)
        self.addCleanup(self.manager.close)

    def create(self, **overrides):
        return self.manager.create({"files":[upload("abstract.md", "# Abstract\nThe response rate was 90%."),
            upload("methods.md", "# Methods\nTen participants were followed for one week."),
            upload("results.md", "# Results\nThe response rate was 70%."),
            upload("discussion.md", "# Discussion\nThe response rate improved.")], "goal":"Check consistency", **overrides})

    def wait(self, identifier, *, calls=None):
        limit = time.monotonic() + 12
        while time.monotonic() < limit:
            value = self.manager.snapshot(identifier)
            if calls is not None and len(self.calls) >= calls:
                return value
            if calls is None and value["state"] not in {"running", "pause_requested", "cancel_requested"}:
                worker = self.manager.workers.get(identifier)
                if worker:
                    worker.join(1)
                return value
            time.sleep(.01)
        self.fail("Local fixture worker did not reach the expected checkpoint")

    def test_import_is_local_and_cross_section_checks_bind_both_sides(self):
        job = self.create()
        self.assertFalse(self.calls)
        self.assertTrue(all(row["checked_blocks"] == 0 for row in job["coverage"]))
        self.manager.start({"job_id":job["id"]})
        result = self.wait(job["id"])
        self.assertEqual(result["state"], "completed", result["error"])
        self.assertEqual(len(result["cross_coverage"]), 5)
        self.assertTrue(all(row["status"] == "anchors_reviewed" for row in result["cross_coverage"]))
        self.assertTrue(all(row["checked_blocks"] == row["total_blocks"] for row in result["coverage"]))
        self.assertTrue(result["claims"])
        for config, _, context, schema, images in self.calls:
            self.assertEqual(config.response_format, "prompt")
            self.assertEqual(config.max_output_tokens, 1200)
            self.assertEqual(schema, CHECK_SCHEMA)
            self.assertFalse(images)
        count = len(self.calls)
        self.manager.snapshot(job["id"])
        self.assertEqual(len(self.calls), count)

    def test_budget_pause_and_restart_reuse_completed_batches(self):
        job = self.create(budget={"max_calls":1})
        self.manager.start({"job_id":job["id"]})
        first = self.wait(job["id"])
        self.assertEqual(first["state"], "budget_paused")
        self.assertEqual(len(self.calls), 1)
        completed_id = first["steps"][0]["id"]
        self.manager.close()
        self.manager = JobManager(Path(self.directory.name), call=self.manager.call)
        self.addCleanup(self.manager.close)
        restored = self.manager.snapshot(job["id"])
        self.assertEqual(restored["steps"][0]["status"], "completed")
        self.manager.start({"job_id":job["id"], "max_calls":12})
        result = self.wait(job["id"])
        self.assertEqual(result["state"], "completed")
        self.assertEqual(len(next(step for step in result["steps"] if step["id"]==completed_id)["attempts"]), 1)
        self.assertEqual(len(self.calls), 9)

    def test_cancel_and_steering_during_a_call_checkpoint_before_stopping(self):
        self.block = threading.Event()
        job = self.create()
        self.manager.start({"job_id":job["id"]})
        self.wait(job["id"], calls=1)
        stopped = self.manager.control({"job_id":job["id"], "action":"cancel"})
        self.assertEqual(stopped["state"], "cancel_requested")
        self.block.set()
        result = self.wait(job["id"])
        self.assertEqual(result["state"], "cancelled")
        self.assertEqual(result["progress"]["completed"], 1)
        self.assertEqual(len(self.calls), 1)
        revised = self.manager.control({"job_id":job["id"], "action":"steer", "goal":"Check sample-size consistency only"})
        self.assertEqual(revised["revision"], 2)
        self.assertEqual(revised["calls_reserved"], 1)
        self.assertTrue(any(row["stale_blocks"] for row in revised["coverage"]))
        self.assertFalse(revised["claims"])
        self.assertEqual(len(self.calls), 1)

    def test_in_flight_steering_keeps_old_result_out_of_new_coverage(self):
        self.block = threading.Event()
        job = self.create()
        self.manager.start({"job_id":job["id"]})
        self.wait(job["id"], calls=1)
        self.manager.control({"job_id":job["id"], "action":"steer", "goal":"Focus on outcomes"})
        self.block.set()
        result = self.wait(job["id"])
        self.assertEqual(result["state"], "paused")
        self.assertEqual(result["revision"], 2)
        self.assertEqual(result["progress"]["completed"], 0)
        self.assertEqual(len(self.calls), 1)

    def test_crash_with_unknown_outcome_requires_explicit_retry(self):
        job = self.create()
        with self.manager.lock:
            state = self.manager._load(job["id"])
            state["state"] = "running"
            state["steps"][0]["status"] = "running"
            state["steps"][0]["attempts"] = [{"status":"in_flight", "input_estimate":1500, "output_limit":1200}]
            state.update(calls_reserved=1, tokens_reserved=2700)
            self.manager._save(state)
        self.manager.close()
        self.manager = JobManager(Path(self.directory.name), call=self.manager.call)
        self.addCleanup(self.manager.close)
        restored = self.manager.snapshot(job["id"])
        self.assertEqual(restored["state"], "interrupted")
        self.assertEqual(restored["uncertain_requests"], 1)
        with self.assertRaisesRegex(DocumentError, "可能已计费"):
            self.manager.start({"job_id":job["id"]})
        self.assertFalse(self.calls)
        self.manager.start({"job_id":job["id"],"retry_uncertain":True})
        result = self.wait(job["id"])
        self.assertEqual(result["calls_reserved"], 10)

    def test_restart_preserves_pending_steering_without_replaying_old_request(self):
        job = self.create()
        with self.manager.lock:
            state = self.manager._load(job["id"])
            state.update(state="pause_requested", pending_goal="Check participant counts only", calls_reserved=1, tokens_reserved=2700)
            state["steps"][0].update(status="running", attempts=[{"status":"in_flight", "input_estimate":1500, "output_limit":1200}])
            self.manager._save(state)
        self.manager.close()
        self.manager = JobManager(Path(self.directory.name), call=self.manager.call)
        self.addCleanup(self.manager.close)
        restored = self.manager.snapshot(job["id"])
        self.assertEqual((restored["state"],restored["revision"]),("paused",2))
        self.assertEqual(restored["goal"],"Check participant counts only")
        self.assertEqual(restored["calls_reserved"],1)
        self.assertFalse(self.calls)
        self.assertEqual(restored["progress"]["completed"],0)
        state = self.manager._load(job["id"])
        self.assertEqual(state["history"][0]["attempts"][0]["status"],"outcome_unknown")
        self.manager.start({"job_id":job["id"]})
        result = self.wait(job["id"])
        self.assertEqual(result["state"],"completed")
        self.assertEqual(result["calls_reserved"],10)
        self.assertTrue(all("Check participant counts only" in call[2] for call in self.calls))

    def test_unknown_locators_and_invented_quotes_fail_without_coverage(self):
        job = self.create()
        def invalid(*args):
            result = fixture_call(*args)
            result["claims"][0]["quote"] = "Invented evidence"
            return result
        self.manager.call = invalid
        self.manager.start({"job_id":job["id"]})
        result = self.wait(job["id"])
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["progress"]["completed"], 0)
        self.assertEqual(result["calls_reserved"], 1)
        self.assertFalse(result["claims"])

    def test_small_budget_never_hides_unchecked_sections_or_cross_anchors(self):
        job = self.create(budget={"total_tokens":3000})
        self.manager.start({"job_id":job["id"]})
        result = self.wait(job["id"])
        self.assertEqual(result["state"], "budget_paused")
        self.assertTrue(any(row["unchecked"] for row in result["coverage"]))
        self.assertLess(len(self.calls), 2)

    def test_legacy_profile_and_provider_output_cap_are_respected(self):
        with patch.dict(os.environ, {"AWT_MAX_OUTPUT_TOKENS":"512"}):
            job = self.create(budget={"profile":"legacy"})
        self.assertEqual(job["budget"]["input_tokens"],2400)
        self.assertEqual(job["budget"]["output_tokens"],512)
        self.manager.start({"job_id":job["id"],"max_calls":12})
        result=self.wait(job["id"])
        self.assertEqual(result["state"],"completed",result["error"])
        self.assertTrue(all(attempt["input_estimate"]<=2400 and attempt["output_limit"]==512 for step in result["steps"] for attempt in step["attempts"]))

    def test_missing_section_and_custom_heading_classification_are_explicit(self):
        job = self.manager.create({"files":[upload("chapter1.md","# Research protocol\nTen participants."),upload("results.md","# Results\nSeven improved.")],"goal":"Compare"})
        first = job["coverage"][0]
        self.manager.classify({"job_id":job["id"],"document_id":first["document_id"],"section":first["section"],"role":"methods"})
        self.manager.start({"job_id":job["id"]})
        result = self.wait(job["id"])
        self.assertTrue(any(row["status"]=="missing_section" for row in result["cross_coverage"]))
        with self.assertRaises(DocumentError):
            self.manager.classify({"job_id":job["id"],"role":"results"})

    def test_root_lock_and_hash_bound_source_prevent_duplicate_or_drifted_runs(self):
        with self.assertRaises(DocumentError):
            JobManager(Path(self.directory.name))
        job = self.create()
        path = Path(self.directory.name) / job["id"] / (job["documents"][0]["id"] + ".bin")
        path.write_text("Changed", encoding="utf-8")
        with self.assertRaisesRegex(DocumentError, "哈希"):
            self.manager.start({"job_id":job["id"]})
        self.assertFalse(self.calls)

    def test_docx_preserves_paragraph_table_and_image_locations(self):
        data = docx_bytes()
        document = import_document("results.docx", data)
        self.assertEqual(document["sha256"], digest(data))
        self.assertTrue(any(block["locator"] == "段落 2" and "70%" in block["text"] for block in document["blocks"]))
        self.assertTrue(any(block["locator"] == "表 1，第 1 行第 2 格" and block["text"] == "70%" for block in document["blocks"]))
        self.assertTrue(all(block["page"] is None for block in document["blocks"]))
        self.assertEqual(len(document["assets"]), 1)
        job = self.manager.create({"files":[upload("results.docx", data)],"goal":"Check the table"})
        with self.assertRaisesRegex(DocumentError, "文字模型"):
            self.manager.start({"job_id":job["id"],"image_ids":[job["documents"][0]["assets"][0]["id"]]})
        self.assertFalse(self.calls)

    def test_images_are_opt_in_for_all_three_api_protocols(self):
        review = {"summary":"fixture", "claims":[], "findings":[], "limitations":[]}
        image = {"id":"image-1", "mime_type":"image/png", "data_base64":base64.b64encode(PNG).decode()}
        for provider, protocol in (("openai","responses"),("anthropic","anthropic-messages"),("ollama","chat-completions")):
            with server_fixture(envelope(protocol, review)) as (url, requests):
                environment = {"AWT_PROVIDER":provider,"AWT_MODEL":"fixture","AWT_BASE_URL":url,"AWT_RESPONSE_FORMAT":"prompt"}
                with self.assertRaisesRegex(ProviderError, "explicitly"):
                    run_api(load_provider_config(environment), "JSON", "fixture", CHECK_SCHEMA, images=[image])
                self.assertFalse(requests)
                run_api(load_provider_config({**environment,"AWT_SUPPORTS_IMAGES":"1"}), "JSON", "fixture", CHECK_SCHEMA, images=[image])
                payload = requests[0][1]
                contents = payload["input"][0]["content"] if protocol=="responses" else payload["messages"][-1]["content"]
                self.assertEqual(len(contents), 2)
                self.assertNotIn("tools", payload)


@unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdfium2"), "Optional PDF rendering dependencies are unavailable")
class PdfLayoutTests(unittest.TestCase):
    def pdf(self, text, pages=1):
        from reportlab.pdfgen import canvas
        output = io.BytesIO()
        value = canvas.Canvas(output, pagesize=(400,500))
        for _ in range(pages):
            value.drawString(40,450,"Results")
            value.drawString(40,420,text)
            value.rect(40,250,250,120)
            value.showPage()
        value.save()
        return output.getvalue()

    def test_pdf_page_region_locators_and_actual_render(self):
        data = self.pdf("Response rate: 70%", 2)
        document = import_document("results.pdf", data)
        self.assertEqual(len(document["pages"]), 2)
        self.assertTrue(all(block["bounds"] and block["page"] in (1,2) for block in document["blocks"]))
        self.assertTrue(any("70%" in block["text"] for block in document["blocks"]))
        self.assertTrue(render_pdf_page(data, 1).startswith(b"\x89PNG"))

    def test_layout_changes_require_hash_bound_human_review(self):
        before, after = self.pdf("Response rate: 90%"), self.pdf("Response rate: 70%",2)
        report, previews = compare_layout("before.pdf",before,"after.pdf",after)
        self.assertEqual((report["before_pages"],report["after_pages"]),(1,2))
        self.assertTrue(all(page["changed"] for page in report["pages"]))
        self.assertEqual(report["status"],"awaiting_human_review")
        self.assertFalse(any(page["human_checked"] for page in report["pages"]))
        self.assertEqual(set(previews),{"before-1.png","after-1.png","after-2.png"})
        with tempfile.TemporaryDirectory() as directory:
            manager = JobManager(Path(directory), call=fixture_call)
            try:
                job = manager.create({"files":[upload("before.pdf",before)],"goal":"Check"})
                result = manager.layout({"job_id":job["id"],"document_id":job["documents"][0]["id"],"revised":upload("after.pdf",after)})
                layout = result["layouts"][0]
                payload={"job_id":job["id"],"layout_id":layout["id"],"checked_pages":[1,2],"after_sha256":digest(before)}
                with self.assertRaises(DocumentError):
                    manager.layout_check(payload)
                checked=manager.layout_check({**payload,"after_sha256":digest(after)})
                self.assertEqual(checked["layouts"][0]["status"],"human_review_recorded")
                self.assertEqual(checked["calls_reserved"],0)
            finally:
                manager.close()

    def test_selected_pdf_image_is_the_only_visual_coverage(self):
        clean={key:value for key,value in os.environ.items() if not key.startswith("AWT_")}
        clean.update(AWT_PROVIDER="ollama",AWT_MODEL="visual-fixture",AWT_SUPPORTS_IMAGES="1")
        with patch.dict(os.environ,clean,clear=True), tempfile.TemporaryDirectory() as directory:
            requests=[]
            def call(*args):
                requests.append(args)
                return fixture_call(*args)
            manager=JobManager(Path(directory),call=call)
            try:
                job=manager.create({"files":[upload("paper.pdf",self.pdf("Response: 70%",2))],"goal":"Compare visible chart and text"})
                first=job["documents"][0]["assets"][0]["id"]
                manager.start({"job_id":job["id"],"image_ids":[first]})
                manager.workers[job["id"]].join(10)
                result=manager.snapshot(job["id"])
                self.assertEqual(result["state"],"completed",result["error"])
                assets=result["documents"][0]["assets"]
                self.assertEqual([asset["status"] for asset in assets],["image_reviewed","not_checked"])
                image_calls=[args for args in requests if args[-1]]
                self.assertEqual(len(image_calls),1)
                self.assertEqual(image_calls[0][-1][0]["id"],first)
                self.assertTrue(base64.b64decode(image_calls[0][-1][0]["data_base64"]).startswith(b"\x89PNG"))
            finally:
                manager.close()


if __name__ == "__main__":
    unittest.main()
