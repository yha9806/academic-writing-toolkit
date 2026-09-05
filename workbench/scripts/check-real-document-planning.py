#!/usr/bin/env python3
"""Measure a real PDF locally; --live-root explicitly opts into local Ollama calls.

No PDF text, local paths or model responses are copied into the public report.
An optional original job directory proves extraction-region preservation without
modifying its checkpoints. Model results and usage remain in a separate new job.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from dataclasses import replace
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from awt.context_pack import estimate_tokens
from awt.cross_review import budget_settings, input_estimate, text_steps
from awt.documents import import_document
from awt.providers import load_provider_config
from awt.review_jobs import JobManager, read_json
from awt.review_index import fingerprint

GOAL = ("Check whether the main numerical claims and conclusions are consistent across "
        "the abstract, experiments, results, limitations and appendices. Report only "
        "issues supported by exact source quotes; do not rewrite the paper.")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regions(document):
    """Reassemble split spans using the original PDF rectangle and locator."""
    result = {}
    for block in document["blocks"]:
        for span in block["source_spans"]:
            key = (block["page"], span["locator"], tuple(span["bounds"]))
            result[key] = result.get(key, "") + block["text"][span["start"]:span["end"]]
    return result


def region_hash(values):
    return fingerprint([[key, values[key]] for key in sorted(values)])


def inventory(document):
    values = regions(document)
    return {"blocks":len(document["blocks"]), "original_regions":len(values),
            "sections":len({b["section"] for b in document["blocks"]}),
            "chapters":len({b["chapter"] for b in document["blocks"]}),
            "extracted_chars":sum(len(b["text"]) for b in document["blocks"]),
            "region_text_chars":sum(len(text) for text in values.values()),
            "region_text_and_geometry_sha256":region_hash(values)}


def planning(document, goal):
    lookup = {b["id"]:b for b in document["blocks"]}
    result = []
    for limit in (2400, 4000, 8000, 16000):
        budget = budget_settings({"input_tokens":limit, "output_tokens":1600})
        steps = text_steps([document], budget, goal, 1)
        estimates = [input_estimate([lookup[i] for i in s["block_ids"]], goal, "text") for s in steps]
        ordered = [i for step in steps for i in step["block_ids"]]
        if ordered != list(lookup) or any(n > limit for n in estimates):
            raise ValueError("Planning lost or reordered source blocks, or exceeded an input limit")
        result.append({"input_tokens":limit, "text_calls":len(steps),
                       "input_tokens_estimated":sum(estimates),
                       "max_input_tokens_estimated":max(estimates, default=0),
                       "each_block_once_in_source_order":True,
                       "future_chapter_and_cross_calls_included":False})
    return result


def live(args, data, goal):
    if args.live_root.exists():
        raise ValueError("The live job root must be new; prior attempts are preserved")
    environment = {"AWT_PROVIDER":"ollama", "AWT_MODEL":args.model,
        "AWT_BASE_URL":"http://127.0.0.1:11434/v1", "AWT_RESPONSE_FORMAT":"prompt",
        "AWT_MAX_OUTPUT_TOKENS":"1600", "AWT_REQUEST_TIMEOUT":"120"}
    # This standalone process uses only the explicitly named loopback model.
    # Do not inherit a hosted provider, credentials or a transport override.
    for key in list(os.environ):
        if key.startswith("AWT_"):
            del os.environ[key]
    os.environ.update(environment)
    config = load_provider_config()
    manager = JobManager(args.live_root)
    started = time.monotonic()
    try:
        job = manager.create({"files":[{"filename":args.pdf.name,
            "content_base64":base64.b64encode(data).decode()}], "goal":goal,
            "budget":{"input_tokens":8000, "output_tokens":1600,
                      "max_calls":args.max_calls, "total_tokens":args.total_tokens}})
        identifier = job["id"]
        initial_plan = job["plan"]
        manager.start({"job_id":identifier})
        worker = manager.workers[identifier]
        last = None
        while worker.is_alive():
            worker.join(1)
            snapshot = manager.snapshot(identifier, compact=True)
            progress = (snapshot["state"], snapshot["calls_reserved"] // 5)
            if progress != last:
                print(json.dumps({"state":snapshot["state"], "calls":snapshot["calls_reserved"]}), flush=True)
                last = progress
        job = manager._load(identifier)
        completed = [s for s in job["steps"] if s["status"] == "completed"]
        attempts = [a for s in job["steps"] for a in s["attempts"]]
        used = [a["model_run"] for a in attempts if a.get("model_run")]
        checked = {i for s in completed if s["phase"] == "text" for i in s["block_ids"]}
        all_ids = {b["id"] for d in job["documents"] for b in d["blocks"]}
        empty = sum(not any(s["result"].get(key) for key in ("summary", "claims", "findings", "limitations"))
                    for s in completed)
        return {"state":job["state"], "error":job["error"],
            "provider":replace(config, max_output_tokens=1600).public_metadata(),
            "budget":job["budget"], "initial_plan":initial_plan,
            "elapsed_seconds":round(time.monotonic() - started, 3),
            "calls_reserved":job["calls_reserved"], "tokens_reserved_estimate":job["tokens_reserved"],
            "observed_provider_usage":used, "completed_by_phase":dict(Counter(s["phase"] for s in completed)),
            "checked_blocks":len(checked), "total_blocks":len(all_ids), "all_text_sent":checked == all_ids,
            "chapter_stage_reached":job.get("chapter_built", False), "cross_stage_reached":job["cross_built"],
            "cross_pair_statuses":dict(Counter(row["status"] for row in job["cross_coverage"])),
            "empty_reports":empty, "claims":sum(len(s["result"]["claims"]) for s in completed),
            "findings":sum(len(s["result"]["findings"]) for s in completed),
            "automatic_retries":0, "human_review_completed":False,
            "real_author_cycle_complete":False, "review_quality_established":False}
    finally:
        manager.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline-job-dir", type=Path)
    parser.add_argument("--live-root", type=Path, help="New checkpoint directory; explicitly run local Ollama")
    parser.add_argument("--model", default="awt-e1-qwen3vl4b-32k:20260905")
    parser.add_argument("--max-calls", type=int, default=80)
    parser.add_argument("--total-tokens", type=int, default=800000)
    args = parser.parse_args()
    data = args.pdf.read_bytes()
    document = import_document(args.pdf.name, data)
    if not regions(document):
        raise ValueError("This comparison requires PDF region geometry; install the documents extras")
    goal = GOAL
    report = {"schema_version":1, "kind":"real_pdf_planning_optimisation", "planning_version":3,
        "source":{"filename":args.pdf.name, "sha256":sha(args.pdf), "pages":len(document["pages"])},
        "python":sys.version.split()[0], "pdfium":importlib.metadata.version("pypdfium2"),
        "estimator":{k:v for k,v in estimate_tokens("Estimator identity").items() if k != "tokens"},
        "current":inventory(document), "publicSanitisation":{"local_paths_included":False,
            "raw_checkpoints_published":False, "source_text_or_model_responses_published":False},
        "runtime_sha256":{name:sha(Path(__file__).resolve().parents[1] / "awt" / name)
            for name in ("documents.py", "cross_review.py", "review_jobs.py", "review_index.py", "providers.py", "context_pack.py")},
        "script_sha256":sha(Path(__file__))}
    if args.baseline_job_dir:
        job = read_json(args.baseline_job_dir / "job.json")
        documents = read_json(args.baseline_job_dir / ("materials-" + job["materials_ref"] + ".json"))
        if fingerprint(documents) != job["materials_ref"]:
            raise ValueError("Baseline material hash mismatch")
        old = next(d for d in documents if d["filename"] == args.pdf.name)
        if old["sha256"] != document["sha256"] or regions(old) != regions(document):
            raise ValueError("Source bytes or extracted PDF regions changed")
        goal = job["goal"]
        report["baseline"] = {**inventory(old), "planning_version":job.get("planning_version", 1),
            "text_calls":sum(s["phase"] == "text" for s in job["steps"]), "budget":job["budget"],
            "state":job["state"], "calls_reserved":job["calls_reserved"],
            "all_original_region_text_and_geometry_identical":True}
    report["goal"] = goal
    report["plans"] = planning(document, goal)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"current":report["current"], "plans":report["plans"]}), flush=True)
    if args.live_root:
        report["live"] = live(args, data, goal)
        report["source"]["source_unchanged_after_run"] = sha(args.pdf) == document["sha256"]
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k:v for k,v in report["live"].items()
                          if k not in {"observed_provider_usage", "provider", "initial_plan"}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
