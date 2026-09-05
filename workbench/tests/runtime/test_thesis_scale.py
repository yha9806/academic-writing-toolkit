"""Thesis-scale contracts; all model calls are local, deterministic fixtures."""
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
from pathlib import Path
from unittest.mock import patch

from awt.cross_review import budget_settings, text_steps
from awt.documents import DocumentError, import_document
from awt.review_jobs import JobManager, read_json
from test_project_review import fixture_call, upload, PNG


def pdf_fixture(pages=200, lines=42, changed_page=None):
    from reportlab.pdfgen import canvas
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(595, 842))
    for number in range(1, pages + 1):
        section = "Abstract" if number <= 2 else "Methods" if number <= 70 else "Results" if number <= 140 else "Discussion"
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, 795, section)
        pdf.setFont("Helvetica", 10)
        for line in range(lines):
            text = f"Page {number}, record {line + 1}: participants completed the assessment under the specified protocol."
            if number == changed_page and line == 10:
                text = "The revised response rate was 70%, rather than 90%."
            pdf.drawString(48, 770 - line * 16, text)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


class ThesisJobsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        clean = {k:v for k,v in os.environ.items() if not k.startswith("AWT_")}
        clean.update(AWT_PROVIDER="ollama", AWT_MODEL="thesis-fixture")
        self.environment = patch.dict(os.environ, clean, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.calls = []
        def call(*args):
            self.calls.append(args)
            return fixture_call(*args)
        self.manager = JobManager(Path(self.directory.name), call=call)
        self.addCleanup(self.manager.close)

    def files(self):
        return [upload(name + ".md", "# " + name + "\n" + "\n".join(
            f"Paragraph {i}: " + ("Ten participants completed the assessment. " * 7)
            for i in range(80))) for name in ("Abstract", "Methods", "Results", "Discussion")]

    def create(self):
        return self.manager.create({"files":self.files(), "goal":"Check consistency",
            "budget":{"max_calls":500, "total_tokens":3000000}})

    def run_job(self, identifier):
        self.manager.start({"job_id":identifier})
        self.manager.workers[identifier].join(30)
        value = self.manager.snapshot(identifier)
        self.assertEqual(value["state"], "completed", value["error"])
        return value

    def test_manifest_and_paginated_source_are_separate_from_progress(self):
        job = self.create()
        path = Path(self.directory.name) / job["id"] / "job.json"
        checkpoint = read_json(path)
        self.assertNotIn("documents", checkpoint)
        self.assertEqual(checkpoint["schema_version"], 2)
        compact = self.manager.snapshot(job["id"], compact=True)
        self.assertLess(len(json.dumps(compact)), 15000)
        self.assertTrue(all(not doc["blocks"] for doc in compact["documents"]))
        self.assertEqual(compact["totals"]["blocks"], 324)
        ids = []
        for offset in range(0, 324, 50):
            page = self.manager.page({"job_id":job["id"], "kind":"blocks", "limit":50, "offset":offset})
            ids.extend(item["id"] for item in page["items"])
        self.assertEqual(len(set(ids)), 324)
        found = self.manager.page({"job_id":job["id"], "kind":"blocks", "search":"Paragraph 79:"})
        self.assertEqual(found["total"], 4)
        self.assertFalse(self.calls)
        self.manager.close()
        self.manager = JobManager(Path(self.directory.name), call=self.manager.call)
        self.addCleanup(self.manager.close)
        self.assertEqual(self.manager.snapshot(job["id"], compact=True)["totals"]["blocks"], 324)
        self.assertFalse(self.calls)

    def test_subsection_inherits_chapter_and_manual_role_survives_restart(self):
        job = self.manager.create({"files":[upload("thesis.md", "# Chapter 4\n## Participants\nTen adults.\n## Follow-up\nOne week.")], "goal":"Check"})
        nodes = self.manager.page({"job_id":job["id"], "kind":"chapters"})["items"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["sections"], ["Chapter 4", "Participants", "Follow-up"])
        for role in ("abstract", "introduction", "results", "discussion", "references", "methods"):
            self.manager.classify({"job_id":job["id"], "document_id":job["documents"][0]["id"], "section":"Participants", "role":role})
        self.assertLessEqual(len(self.manager.materials_cache), 4)
        self.manager.close()
        self.manager = JobManager(Path(self.directory.name), call=self.manager.call)
        self.addCleanup(self.manager.close)
        restored = self.manager.page({"job_id":job["id"], "kind":"blocks", "section":"Participants"})
        self.assertTrue(all(b["role"] == "methods" for b in restored["items"]))

    def test_hierarchy_has_grounded_chapter_reviews_and_complete_navigation(self):
        result = self.run_job(self.create()["id"])
        phases = {step["phase"] for step in result["steps"]}
        self.assertEqual(phases, {"text", "chapter", "cross"})
        nodes = self.manager.page({"job_id":result["id"], "kind":"chapters"})["items"]
        self.assertEqual(len(nodes), 4)
        self.assertTrue(all(n["checked_blocks"] == n["total_blocks"] and n["summaries"] for n in nodes))
        self.assertTrue(all(row["status"] == "anchors_reviewed" for row in result["cross_coverage"]))
        self.assertTrue(any(row["omitted"] for row in result["cross_coverage"]))

    def test_one_paragraph_revision_reuses_most_text_and_invalidates_dependents(self):
        job = self.create()
        first = self.run_job(job["id"])
        old_count = len(self.calls)
        revised = self.files()[2]
        revised["content_base64"] = base64.b64encode(base64.b64decode(revised["content_base64"]).replace(b"Paragraph 40:", b"Changed paragraph 40:")).decode()
        second = self.manager.revise({"job_id":job["id"], "files":[revised]})
        self.assertEqual(len(self.calls), old_count)
        self.assertEqual(second["revision"], 2)
        self.assertGreater(second["revision_change"]["reused_blocks"], 290)
        self.assertGreater(second["revision_change"]["pending_blocks"], 0)
        self.assertEqual(second["calls_reserved"], first["calls_reserved"])
        final = self.run_job(job["id"])
        self.assertLess(len(self.calls) - old_count, old_count // 2)
        history = self.manager._load(job["id"])["history"]
        self.assertTrue(history)
        current_ids = {b["id"] for d in final["documents"] for b in d["blocks"]}
        self.assertTrue(all(c["locator"] in current_ids for c in final["claims"]))
        self.assertTrue(any(s.get("reused_from") for s in self.manager._load(job["id"])["steps"] if s["phase"] == "cross"))

    def test_identical_revision_and_changed_requirements_never_hide_new_work(self):
        job = self.create()
        first = self.run_job(job["id"])
        identical = self.manager.revise({"job_id":job["id"], "files":[self.files()[0]]})
        self.assertEqual(identical["revision"], 1)
        self.assertEqual(identical["calls_reserved"], first["calls_reserved"])
        steered = self.manager.control({"job_id":job["id"], "action":"steer", "goal":"Check participant counts only"})
        self.assertEqual(steered["progress"]["completed"], 0)
        self.assertTrue(any(row["stale_blocks"] for row in steered["coverage"]))
        old_calls = len(self.calls)
        self.run_job(job["id"])
        self.assertGreater(len(self.calls), old_calls)

    def test_inserted_paragraph_invalidates_the_old_batch_context(self):
        original = "# Methods\nOne adult.\nTwo visits.\nSeven days."
        job = self.manager.create({"files":[upload("methods.md", original)], "goal":"Check"})
        self.run_job(job["id"])
        revised = self.manager.revise({"job_id":job["id"], "files":[upload("methods.md", original.replace("Two visits.", "Important new exclusion.\nTwo visits."))]})
        self.assertEqual(revised["revision_change"]["reused_batches"], 0)
        self.assertGreater(revised["revision_change"]["pending_blocks"], 0)

    def test_chunk_upload_is_bounded_and_duplicate_chunks_are_idempotent(self):
        data = b"x" * 1_000_000 + b"tail"
        transfer = self.manager.upload_start({"filename":"large.txt", "size":len(data)})
        payload = {"upload_id":transfer["upload_id"], "offset":0, "content_base64":base64.b64encode(data[:1_000_000]).decode()}
        self.manager.upload_chunk(payload)
        self.assertEqual(self.manager.upload_chunk(payload)["offset"], 1_000_000)
        with self.assertRaises(DocumentError):
            self.manager.decode_material({"upload_id":transfer["upload_id"]})
        with self.assertRaises(DocumentError):
            self.manager.upload_chunk({**payload, "content_base64":base64.b64encode(b"wrong").decode()})
        self.manager.upload_chunk({"upload_id":transfer["upload_id"], "offset":1_000_000, "content_base64":base64.b64encode(b"tail").decode()})
        self.assertEqual(self.manager.decode_material({"upload_id":transfer["upload_id"]}), ("large.txt", data))
        self.assertFalse(self.calls)
        with self.assertRaises(DocumentError):
            self.manager.upload_start({"filename":"../escape.pdf", "size":10})
        with self.assertRaises(DocumentError):
            self.manager.upload_start({"filename":"oversized.pdf", "size":80_000_001})

    def test_chinese_legacy_profile_and_explicit_large_budget(self):
        document = import_document("论文.md", ("# 方法\n" + "参与者接受相同随访流程，并记录预先定义的结局。" * 70).encode())
        plan = text_steps([document], budget_settings({"profile":"legacy"}), "检查方法和结论是否一致", 1)
        self.assertTrue(plan)
        self.assertEqual(budget_settings({"max_calls":1000, "total_tokens":4000000})["max_calls"], 1000)


@unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdfium2"), "Optional PDF dependencies unavailable")
class ThesisPdfTests(unittest.TestCase):
    def test_200_page_pdf_coalesces_lines_without_losing_page_locators(self):
        doc = import_document("thesis.pdf", pdf_fixture())
        self.assertEqual(len(doc["pages"]), 200)
        self.assertLess(len(doc["blocks"]), 1200)
        self.assertEqual(sum(len(b["source_spans"]) for b in doc["blocks"]), 8600)
        self.assertTrue(any(b["page"] == 200 and "record 42:" in b["text"] for b in doc["blocks"]))
        for profile, old in (("legacy",472), ("economy",221), ("balanced",95)):
            self.assertLess(len(text_steps([doc], budget_settings({"profile":profile}), "Check consistency between sections", 1)), old * .8)

    def test_200_page_layout_checkpoints_resume_and_page_checks_are_bound(self):
        from awt.documents import digest
        from awt import layout_jobs
        calls, entered, release = [], threading.Event(), threading.Event()
        def fake_page(before, after, number, *counts):
            calls.append(number)
            if number == 2:
                entered.set()
                release.wait(5)
            return {"page":number, "rendered":True, "changed":False, "after_blank":False, "text_outside_page":[],
                "before_available":True, "after_available":True, "human_checked":False, "image_hashes":{"before":digest(PNG),"after":digest(PNG)}}, {"before":PNG,"after":PNG}
        with tempfile.TemporaryDirectory() as directory, patch.object(layout_jobs, "compare_pdf_page", side_effect=fake_page):
            manager = JobManager(Path(directory), call=fixture_call)
            try:
                data = pdf_fixture(lines=1)
                job = manager.create({"files":[upload("before.pdf",data)],"goal":"Check"})
                value = manager.layout({"job_id":job["id"],"document_id":job["documents"][0]["id"],"revised":upload("after.pdf",data),"background":True})
                layout = value["layouts"][0]["id"]
                self.assertTrue(entered.wait(10))
                manager.layout_control({"job_id":job["id"],"layout_id":layout,"action":"pause"})
                release.set()
                manager.layout_manager.workers[layout].join(10)
                self.assertEqual(calls,[1,2])
                manager.close()
                manager = JobManager(Path(directory),call=fixture_call)
                manager.layout_control({"job_id":job["id"],"layout_id":layout,"action":"resume"})
                manager.layout_manager.workers[layout].join(30)
                self.assertEqual(calls,list(range(1,201)))
                result = manager.snapshot(job["id"])
                self.assertEqual(result["layouts"][0]["state"],"completed")
                self.assertEqual(result["calls_reserved"],0)
                page = manager.layout_page({"job_id":job["id"],"layout_id":layout,"page":200})
                self.assertTrue(page["before"]["available"])
                with self.assertRaises(DocumentError):
                    manager.layout_check({"job_id":job["id"],"layout_id":layout,"page":200,"checked":True,"after_sha256":"wrong"})
                checked = manager.layout_check({"job_id":job["id"],"layout_id":layout,"page":200,"checked":True,"after_sha256":digest(data)})
                self.assertTrue(checked["layouts"][0]["pages"][-1]["human_checked"])
            finally:
                release.set()
                manager.close()

    def test_layout_can_target_original_page_numbers_beyond_sixty(self):
        with tempfile.TemporaryDirectory() as directory:
            manager = JobManager(Path(directory), call=fixture_call)
            try:
                before, after = pdf_fixture(lines=12), pdf_fixture(lines=12, changed_page=200)
                job = manager.create({"files":[upload("thesis.pdf",before)],"goal":"Check"})
                result = manager.layout({"job_id":job["id"],"document_id":job["documents"][0]["id"],
                    "revised":upload("changed.pdf",after),"page_start":199,"page_end":200})
                layout = result["layouts"][0]
                self.assertEqual(layout["state"],"completed",layout["error"])
                self.assertEqual([p["page"] for p in layout["pages"]],[199,200])
                self.assertFalse(layout["pages"][0]["changed"])
                self.assertTrue(layout["pages"][1]["changed"])
            finally:
                manager.close()
