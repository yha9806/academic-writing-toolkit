"""User-facing submission contracts, offline and with fictional source materials."""
from __future__ import annotations

import base64
import copy
import importlib.util
import io
import json
import os
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from awt.documents import DocumentError, digest, import_document
from awt.review_jobs import JobManager, read_json
from awt.submission_checks import Findings, Source, bib_entries, build_report, default_profile, normalise_profile
from test_project_review import upload


PAPER = """# Abstract
We compare two methods.
# Methods
Two groups were assessed. The protocol follows \\cite{known,missing}.
See Figure 1(a), Figure 9 and Table 1.
# Results
Figure 1. Comparison of two groups.
Figure 2. An unreferenced analysis.
Table 1. Evaluation scores.
TODO explain the failed cases.
# Discussion
The selected methods need further evaluation.
"""
BIB = '@article{known, title={A {nested} title}, author={Smith, Jane}, year={2024}, journal={Fictional Journal}, doi={10.1234/example}}'


class SubmissionCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        env = {k: v for k, v in os.environ.items() if not k.startswith("AWT_")}
        env.update(AWT_PROVIDER="ollama", AWT_MODEL="offline-submission-fixture")
        self.environment = patch.dict(os.environ, env, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.manager = JobManager(Path(self.temporary.name), call=lambda *args: self.fail("pre-submission check called a model"))
        self.addCleanup(self.manager.close)

    def job(self, files=None):
        return self.manager.create({"files": files or [upload("paper.md", PAPER), upload("refs.bib", BIB)], "goal": "Review the fictional manuscript"})

    def profile(self, job, **changes):
        return {**default_profile(job["documents"]), "target": "Fictional journal", "requirements_source": "Local test instructions",
                "requirements_confirmed": True, **changes}

    def run_report(self, job, profile):
        manager = self.manager.submission_manager
        manager.run({"job_id": job["id"], "profile": profile})
        manager.workers[job["id"]].join(15)
        status = manager.status({"job_id": job["id"]})
        self.assertEqual(status["state"], "completed", status)
        report = manager.export({"job_id": job["id"]})
        self.assertEqual(report["model_calls"], 0)
        self.assertEqual(self.manager.snapshot(job["id"])["calls_reserved"], 0)
        return report


class SubmissionTests(SubmissionCase):
    def test_local_rules_find_missing_materials_without_paid_calls(self):
        job = self.job()
        with patch("urllib.request.urlopen", side_effect=AssertionError("network forbidden")):
            report = self.run_report(job, self.profile(job, max_words=5, declarations=["Data availability"], required_files=["cover-letter.docx"],
                outline=[{"heading": "Methods", "task": "Explain comparison and failed cases", "keywords": ["failed cases"]},
                         {"heading": "Conclusion", "task": "", "keywords": []}]))
        codes = {item["code"] for item in report["items"]}
        self.assertTrue({"required_file", "max_words", "declaration", "outline_missing", "outline_task", "outline_keyword", "citation_missing"} <= codes)
        self.assertEqual(report["state"], "blocked")
        self.assertEqual(report["source_manifest"][1]["role"], "references")
        self.assertFalse(report["stale"])
        markdown = self.manager.submission_manager.export({"job_id": job["id"], "format": "markdown"})["content"]
        self.assertIn(report["report_sha256"], markdown)
        self.assertIn("规则快照", markdown)
        self.assertIn("missing", markdown)

    def test_bibtex_nested_fields_single_line_and_duplicate_records(self):
        rows, errors = bib_entries(BIB + '\n@book{second, title="Another title", author={Lee, K}, year=2023, publisher={Test}}')
        self.assertFalse(errors)
        self.assertEqual(rows[0]["fields"]["title"], "A {nested} title")
        self.assertEqual(rows[1]["fields"]["year"], "2023")
        job = self.job([upload("paper.md", "# Methods\nWe used \\cite{known}."), upload("refs.bib", BIB + "\n" + BIB)])
        report = self.run_report(job, self.profile(job))
        self.assertTrue(any(i["code"] == "bib_duplicate" and i["status"] == "block" for i in report["items"]))
        self.assertFalse(any(i["code"] == "citation_missing" for i in report["items"]))
        _, errors = bib_entries('@article{bad, title={unclosed}')
        self.assertTrue(errors)

    def test_figure_subpanels_orphans_and_missing_references_are_distinct(self):
        job = self.job()
        report = self.run_report(job, self.profile(job, max_figures=1))
        rows = report["items"]
        self.assertEqual(report["metrics"]["figure"], 2)
        self.assertTrue(any(i["code"] == "figure_missing" and "9" in i["title"] for i in rows))
        self.assertTrue(any(i["code"] == "figure_orphan" and "2" in i["title"] for i in rows))
        self.assertFalse(any(i["code"] == "figure_missing" and "1(a)" in i["title"] for i in rows))
        self.assertTrue(any(i["code"] == "figure_semantics" and i["status"] == "manual" for i in rows))

    def test_outline_child_content_and_attachment_roles_do_not_contaminate_checks(self):
        job = self.job([upload("paper.md", "# Methods\n## Sample\nTwo adult groups.\n# Results\nAn exploratory result."),
                        upload("letter.md", "Professor Identity\n" + "confidential author " * 40)])
        profile = self.profile(job, files={"paper.md": "manuscript", "letter.md": "attachment"}, anonymous=True, anonymous_terms=["Professor Identity"],
                               outline=[{"heading": "Methods", "task": "Describe sampling", "keywords": ["adult groups"]}], citation_mode="none")
        report = self.run_report(job, profile)
        self.assertFalse(any(i["code"] == "anonymous_term" for i in report["items"]))
        self.assertTrue(any(i["code"] == "outline_keyword" and i["status"] == "pass" for i in report["items"]))
        self.assertLess(report["metrics"]["text_count"], 20)

    def test_numbered_reference_matching_and_unsupported_styles_remain_visible(self):
        job = self.job([upload("paper.md", "# Methods\nBased on [1, 3].\n# References\n[1] Smith. Example study. 2024.")])
        report = self.run_report(job, self.profile(job, citation_mode="numbered"))
        missing = [i for i in report["items"] if i["code"] == "numbered_citation"]
        self.assertEqual(len(missing), 1)
        self.assertIn("未匹配 3", missing[0]["detail"])
        self.assertEqual(missing[0]["status"], "warning")

    def test_manual_decisions_are_bound_and_cannot_override_blocks(self):
        job = self.job()
        report = self.run_report(job, self.profile(job))
        manual = next(i for i in report["items"] if i["status"] == "manual")
        request = {"job_id": job["id"], "report_id": report["id"], "binding": report["binding"], "item_id": manual["id"],
                   "reviewer": "Fixture reviewer", "note": "Checked against fictional instructions."}
        self.manager.submission_manager.confirm(request)
        after = self.manager.submission_manager.export({"job_id": job["id"]})
        item = next(i for i in after["items"] if i["id"] == manual["id"])
        self.assertEqual(item["status"], "recorded")
        self.assertEqual(after["report_sha256"], report["report_sha256"])
        blocked = next(i for i in report["items"] if i["status"] == "block")
        with self.assertRaises(DocumentError):
            self.manager.submission_manager.confirm({**request, "item_id": blocked["id"]})
        self.manager.submission_manager.confirm({**request, "decision": "reopen"})
        after = self.manager.submission_manager.export({"job_id": job["id"]})
        self.assertEqual(next(i["status"] for i in after["items"] if i["id"] == manual["id"]), "manual")

    def test_changed_rules_or_manuscript_invalidate_old_reports(self):
        job = self.job()
        profile = self.profile(job)
        report = self.run_report(job, profile)
        self.manager.submission_manager.configure({"job_id": job["id"], "profile": {**profile, "max_words": 500}})
        self.assertTrue(self.manager.submission_manager.report({"job_id": job["id"]})["stale"])
        self.manager.submission_manager.configure({"job_id": job["id"], "profile": profile})
        self.assertFalse(self.manager.submission_manager.report({"job_id": job["id"]})["stale"])
        self.manager.revise({"job_id": job["id"], "files": [upload("paper.md", PAPER + "\nA changed conclusion.")]})
        self.assertTrue(self.manager.submission_manager.export({"job_id": job["id"]})["stale"])
        item = next(i for i in report["items"] if i["status"] == "manual")
        with self.assertRaises(DocumentError):
            self.manager.submission_manager.confirm({"job_id": job["id"], "report_id": report["id"], "binding": report["binding"],
                "item_id": item["id"], "reviewer": "Fixture", "note": "Old result"})

    def test_report_restore_and_pagination_do_not_rerun_checks(self):
        job = self.job()
        report = self.run_report(job, self.profile(job))
        first = self.manager.submission_manager.report({"job_id": job["id"], "limit": 2})
        second = self.manager.submission_manager.report({"job_id": job["id"], "offset": 2, "limit": 2})
        self.assertEqual(len(first["items"]), 2)
        self.assertFalse(set(i["id"] for i in first["items"]) & set(i["id"] for i in second["items"]))
        self.manager.close()
        self.manager = JobManager(Path(self.temporary.name), call=lambda *args: self.fail("restore called model"))
        self.addCleanup(self.manager.close)
        with patch("awt.submission_jobs.build_report", side_effect=AssertionError("restore reran checks")):
            self.assertEqual(self.manager.submission_manager.export({"job_id": job["id"]})["report_sha256"], report["report_sha256"])

    def test_cancel_retains_previous_report_and_restart_marks_interrupted(self):
        from awt import submission_jobs
        job = self.job()
        initial = self.run_report(job, self.profile(job))
        entered, release = threading.Event(), threading.Event()
        original = submission_jobs.build_report
        def waiting(*args):
            entered.set()
            release.wait(5)
            args[3]("after wait")
            return original(*args)
        with patch.object(submission_jobs, "build_report", side_effect=waiting):
            self.manager.submission_manager.run({"job_id": job["id"]})
            self.assertTrue(entered.wait(5))
            self.manager.submission_manager.cancel({"job_id": job["id"]})
            release.set()
            self.manager.submission_manager.workers[job["id"]].join(10)
        self.assertEqual(self.manager.submission_manager.status({"job_id": job["id"]})["state"], "cancelled")
        self.assertEqual(self.manager.submission_manager.export({"job_id": job["id"]})["id"], initial["id"])
        saved = self.manager._load(job["id"])
        saved["submission"]["state"] = "running"
        self.manager._save(saved)
        self.manager.close()
        self.manager = JobManager(Path(self.temporary.name))
        self.addCleanup(self.manager.close)
        self.assertEqual(self.manager.submission_manager.status({"job_id": job["id"]})["state"], "interrupted")

    def test_source_and_report_tampering_stop_export(self):
        job = self.job()
        report = self.run_report(job, self.profile(job))
        directory = Path(self.temporary.name) / job["id"]
        saved = self.manager._load(job["id"])
        source = saved["documents"][0]
        source_path = directory / (source["id"] + ".bin")
        # Use the same durable source-path contract as JobManager._source.
        self.assertTrue(source_path.is_file())
        original = source_path.read_bytes()
        source_path.write_bytes(b"modified outside the Workbench")
        with self.assertRaises(DocumentError):
            self.manager.submission_manager.export({"job_id": job["id"]})
        source_path.write_bytes(original)
        report_path = directory / ("submission-" + report["id"] + ".json")
        report_path.write_text('{}', encoding="utf-8")
        with self.assertRaises(DocumentError):
            self.manager.submission_manager.export({"job_id": job["id"]})

    def test_invalid_limits_unknown_files_and_incomplete_dimensions_are_rejected(self):
        job = self.job()
        for values in ({"max_words": True}, {"max_pages": 0}, {"page_width_mm": 210}, {"files": {"unknown.pdf": "manuscript"}}, {"required_files": ["../secret.txt"]}, {"kind": []}, {"files": {"paper.md": []}}):
            with self.subTest(values=values), self.assertRaises(DocumentError):
                normalise_profile(self.profile(job, **values), job["documents"])

    def test_report_item_bound_never_hides_the_total_failure_count(self):
        out = Findings()
        for i in range(2100):
            out.add("fixture", "block", "Missing " + str(i), "Fixture")
        self.assertEqual(out.counts["block"], 2100)
        self.assertEqual(out.total, 2100)
        self.assertEqual(len(out.items), 2000)
        self.assertEqual(len({i["id"] for i in out.items}), 2000)

    def test_planned_cross_review_is_not_completed_review(self):
        job = self.job()
        saved = self.manager._load(job["id"])
        for step in saved["steps"]:
            step.update(status="completed", result={"findings": []})
        saved["cross_built"] = True
        saved["steps"].append({**saved["steps"][0], "id": "pending-cross", "phase": "cross", "status": "pending"})
        profile = self.profile(job, require_model_review=True, require_layout=True)
        report = build_report(saved, profile, lambda d: self.manager._source(saved, d))
        self.assertTrue(any(i["code"] == "review_coverage" and i["status"] == "unchecked" for i in report["items"]))
        self.assertTrue(any(i["code"] == "layout_missing" and i["status"] == "unchecked" for i in report["items"]))

    def test_layout_records_require_current_file_and_all_pages(self):
        from test_project_review import docx_bytes
        job = self.job([upload("paper.docx", docx_bytes())])
        saved = self.manager._load(job["id"])
        profile = self.profile(job, require_layout=True)
        full = {"id": "fixture", "state": "completed", "after_sha256": saved["documents"][0]["sha256"], "page_start": 1,
                "after_pages": 2, "pages": [{"page": n, "rendered": True, "human_checked": True} for n in (1, 2)]}
        for layout in ({**full, "after_sha256": "old-copy"}, {**full, "page_start": 2, "pages": full["pages"][1:]},
                       {**full, "pages": [{**full["pages"][0], "human_checked": False}, full["pages"][1]]}, full):
            saved["layouts"] = [layout]
            report = build_report(saved, profile, lambda d: self.manager._source(saved, d))
            item = next(i for i in report["items"] if i["code"] == "layout_record")
            self.assertEqual(item["status"], "pass" if layout is full else "unchecked")

    def test_docx_tracked_changes_are_reported_without_a_renderer(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Methods</w:t></w:r></w:p><w:p><w:ins><w:r><w:t>Two groups.</w:t></w:r></w:ins></w:p></w:body></w:document>')
        job = self.job([upload("paper.docx", buffer.getvalue())])
        report = self.run_report(job, self.profile(job, citation_mode="none", max_pages=10))
        self.assertTrue(any(i["code"] == "docx_revisions" and i["status"] == "warning" for i in report["items"]))
        self.assertTrue(any(i["code"] == "page_limit" and i["status"] == "unchecked" for i in report["items"]))


@unittest.skipUnless(importlib.util.find_spec("reportlab") and importlib.util.find_spec("pypdfium2") and importlib.util.find_spec("pypdf"), "Optional PDF dependencies unavailable")
class SubmissionPdfTests(SubmissionCase):
    def test_pdf_scanned_pages_and_font_rules_are_not_false_passes(self):
        from reportlab.pdfgen import canvas
        output = io.BytesIO()
        pdf = canvas.Canvas(output)
        pdf.drawString(50, 750, "Methods: fictional results")
        pdf.showPage()
        pdf.showPage()
        pdf.save()
        job = self.job([upload("paper.pdf", output.getvalue())])
        report = self.run_report(job, self.profile(job, embedded_fonts=True, max_words=100, citation_mode="none", page_width_mm=100, page_height_mm=100))
        self.assertTrue(any(i["code"] == "text_missing" for i in report["items"]))
        self.assertTrue(any(i["code"] == "max_words" and i["status"] == "unchecked" for i in report["items"]))
        self.assertTrue(any(i["code"] == "pdf_fonts" and i["status"] == "block" for i in report["items"]))
        self.assertTrue(any(i["code"] == "pdf_size" and i["status"] == "block" for i in report["items"]))

    def test_two_hundred_page_pre_submission_remains_local_and_bounded(self):
        from test_thesis_scale import pdf_fixture
        job = self.job([upload("thesis.pdf", pdf_fixture())])
        report = self.run_report(job, self.profile(job, kind="thesis", citation_mode="none", max_pages=1000,
            outline=[{"heading": "Discussion", "task": "Explain the study limits", "keywords": ["Page 200"]}]))
        self.assertEqual(report["metrics"]["pdf_pages"], 200)
        self.assertTrue(any(i["code"] == "outline_keyword" and i["status"] == "pass" for i in report["items"]))
        self.assertLess(len(json.dumps(report)), 100000)


if __name__ == "__main__":
    unittest.main()
