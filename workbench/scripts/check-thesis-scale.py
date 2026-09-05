#!/usr/bin/env python3
"""Offline thesis benchmark. Generates fictional PDFs; never calls a model API."""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from awt.cross_review import budget_settings, input_estimate, text_steps
from awt.documents import import_document
from awt.providers import ModelResult
from awt.review_jobs import JobManager


def fixture_pdf(pages, changed=False):
    from reportlab.pdfgen import canvas
    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=(595, 842))
    for number in range(1, pages + 1):
        section = "Abstract" if number <= 2 else "Methods" if number <= pages * .35 else "Results" if number <= pages * .7 else "Discussion"
        pdf.setFont("Helvetica-Bold", 12)
        pdf.drawString(48, 795, section)
        pdf.setFont("Helvetica", 10)
        for line in range(42):
            text = f"Page {number}, record {line + 1}: participants completed the assessment under the specified protocol."
            if changed and number == pages - 1 and line == 10:
                text = "The revised response rate was 70%, rather than 90%."
            pdf.drawString(48, 770 - line * 16, text)
        pdf.showPage()
    pdf.save()
    return output.getvalue()


def unmerged(fragments):
    for item in fragments:
        yield {**item, "source_spans":[{"start":0, "end":len(item["text"]), "locator":item["locator"], "bounds":item["bounds"]}]}


def plans(document):
    available = {b["id"]:b for b in document["blocks"]}
    result = {}
    for profile in ("legacy","economy","balanced"):
        budget = budget_settings({"profile":profile})
        start = time.perf_counter()
        steps = text_steps([document], budget, "Check consistency between sections", 1)
        result[profile] = {"text_batches":len(steps), "text_reservation_estimate":sum(
            input_estimate([available[i] for i in s["block_ids"]], "Check consistency between sections", "text") + budget["output_tokens"] for s in steps),
            "planning_seconds":round(time.perf_counter() - start, 3)}
    return result


def upload(name, data):
    return {"filename":name, "content_base64":base64.b64encode(data).decode()}


def offline_call(config, instructions, context, schema, images):
    blocks = json.JSONDecoder().raw_decode(context)[0]["materials"]
    claims = [{"locator":b["locator"], "quote":b["text"][:200], "evidence":[], "note":"Fictional transport fixture"} for b in blocks[:2] if b["text"]]
    return ModelResult({"summary":"Offline engineering fixture; no academic-quality judgment", "claims":claims, "findings":[], "limitations":[]},
                       {"provider":"offline-fixture", "usage":{}, "returned_model":"deterministic-fixture"})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=int, default=200)
    parser.add_argument("--run-fixture", action="store_true", help="Execute the local mock review and one-file incremental revision")
    parser.add_argument("--layout", action="store_true", help="Actually render every before/after page locally; may take minutes")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 3 <= args.pages <= 1000:
        parser.error("--pages must be 3–1000")
    data = fixture_pdf(args.pages)
    start = time.perf_counter()
    document = import_document("thesis.pdf", data)
    extraction = time.perf_counter() - start
    with patch("awt.documents._pdf_groups", side_effect=unmerged):
        raw = import_document("thesis.pdf", data)
    report = {"at":datetime.now(timezone.utc).isoformat(), "scope":"Synthetic single-column PDF, 42 lines/page; no hosted model calls",
        "pages":args.pages, "file_bytes":len(data), "characters":sum(len(b["text"]) for b in document["blocks"]),
        "unmerged_regions":len(raw["blocks"]), "merged_regions":len(document["blocks"]),
        "extraction_seconds":round(extraction,3), "unmerged":plans(raw), "merged":plans(document)}
    if args.run_fixture or args.layout:
        clean = {k:v for k,v in os.environ.items() if not k.startswith("AWT_")}
        clean.update(AWT_PROVIDER="ollama", AWT_MODEL="offline-scale-fixture")
        with patch.dict(os.environ, clean, clear=True), tempfile.TemporaryDirectory(prefix="awt-thesis-scale-") as directory:
            manager = JobManager(Path(directory), call=offline_call)
            try:
                start = time.perf_counter()
                job = manager.create({"files":[upload("thesis.pdf",data)], "goal":"Check consistency between sections",
                    "budget":{"max_calls":5000, "total_tokens":20000000}})
                report["import_and_plan_seconds"] = round(time.perf_counter() - start,3)
                report["compact_status_bytes"] = len(json.dumps(manager.snapshot(job["id"], compact=True), ensure_ascii=False).encode())
                revised = fixture_pdf(args.pages, True)
                if args.run_fixture:
                    start = time.perf_counter()
                    manager.start({"job_id":job["id"]})
                    manager.workers[job["id"]].join(600)
                    first = manager.snapshot(job["id"])
                    if first["state"] != "completed":
                        raise RuntimeError(first["error"] or first["state"])
                    report["first_review"] = {"mock_calls":first["calls_reserved"], "local_seconds":round(time.perf_counter()-start,3)}
                    changed = manager.revise({"job_id":job["id"], "files":[upload("thesis.pdf",revised)]})
                    start = time.perf_counter()
                    manager.start({"job_id":job["id"]})
                    manager.workers[job["id"]].join(600)
                    final = manager.snapshot(job["id"])
                    if final["state"] != "completed":
                        raise RuntimeError(final["error"] or final["state"])
                    report["incremental_review"] = {**changed["revision_change"], "additional_mock_calls":final["calls_reserved"]-first["calls_reserved"],
                        "local_seconds":round(time.perf_counter()-start,3)}
                if args.layout:
                    # The revised model job may now reference the new source, so
                    # make a fresh, zero-call baseline for the actual layout test.
                    baseline = manager.create({"files":[upload("thesis.pdf",data)], "goal":"Local layout only"})
                    start = time.perf_counter()
                    value = manager.layout({"job_id":baseline["id"], "document_id":baseline["documents"][0]["id"],
                        "revised":upload("revised.pdf",revised), "background":True})
                    layout = value["layouts"][0]["id"]
                    manager.layout_manager.workers[layout].join(600)
                    final = manager.snapshot(baseline["id"])
                    result = final["layouts"][0]
                    if result["state"] != "completed":
                        raise RuntimeError(result["error"] or result["state"])
                    report["actual_layout"] = {"rendered_page_pairs":sum(p["rendered"] for p in result["pages"]),
                        "changed_pages":[p["page"] for p in result["pages"] if p["changed"]],
                        "local_seconds":round(time.perf_counter()-start,3), "model_calls":final["calls_reserved"]}
            finally:
                manager.close()
    encoded = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
