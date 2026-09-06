#!/usr/bin/env python3
"""Run one bounded real-PDF experiment against an explicitly selected local model.

Requires a new checkpoint directory and never retries a failed request. The
public report contains counts and hashes; original responses stay in the local
checkpoint. Technical completion is distinct from a real author's review cycle.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from awt.cross_review import GROUNDING_PROTOCOL, grounded_request, source_payload, step_materials, validate_review
from awt.review_index import fingerprint
from awt.review_jobs import JobManager

GOAL = ("Check whether the main numerical claims and conclusions are consistent across "
        "the abstract, experiments, results, limitations and appendices. Report only "
        "issues supported by exact source quotes; do not rewrite the paper.")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--live-root", type=Path, required=True, help="New directory; opts into local Ollama calls")
    parser.add_argument("--model", default="awt-e1-qwen3vl4b-32k:20260905")
    parser.add_argument("--response-format", choices=("prompt", "json_schema"), default="json_schema")
    parser.add_argument("--roles", type=Path, help="Optional explicit JSON section-to-role mapping, recorded in the report")
    parser.add_argument("--max-calls", type=int, default=80)
    parser.add_argument("--total-tokens", type=int, default=800000)
    args = parser.parse_args()
    if args.live_root.exists() or args.output.exists():
        raise ValueError("Use new output and checkpoint paths; retain every prior experiment")
    data = args.pdf.read_bytes()
    roles = json.loads(args.roles.read_text(encoding="utf-8")) if args.roles else {}
    for key in list(os.environ):
        if key.startswith("AWT_"):
            del os.environ[key]
    os.environ.update(AWT_PROVIDER="ollama", AWT_MODEL=args.model,
        AWT_BASE_URL="http://127.0.0.1:11434/v1", AWT_RESPONSE_FORMAT=args.response_format,
        AWT_MAX_OUTPUT_TOKENS="1600", AWT_REQUEST_TIMEOUT="120")
    runtime = Path(__file__).resolve().parents[1] / "awt"
    report = {"schema_version": 1, "kind": "real_pdf_review_reliability",
        "protocol": GROUNDING_PROTOCOL, "model": args.model, "goal": GOAL, "response_format": args.response_format,
        "source": {"filename": args.pdf.name, "sha256": sha(args.pdf)},
        "runtime_sha256": {p.name: sha(p) for p in sorted(runtime.glob("*.py"))},
        "script_sha256": sha(Path(__file__)), "python": sys.version.split()[0],
        "pdfium": importlib.metadata.version("pypdfium2"), "explicit_role_overrides": roles,
        "role_override_operator": "agent_experiment_configuration" if roles else None,
        "criteria_frozen_before_calls": ["all text blocks in completed batches exactly once",
            "at least one source-bound observation in every completed batch",
            "chapter and cross stages reached", "all selected IDs and quotations match offered sources",
            "no automatic retry and no hosted provider", "all attempts remain in a fresh checkpoint"],
        "real_author_cycle_complete": False, "review_quality_established": False,
        "publicSanitisation": {"local_paths_included": False, "raw_checkpoints_published": False,
            "source_text_or_model_responses_published": False}}
    manager = JobManager(args.live_root)
    started = time.monotonic()
    try:
        snapshot = manager.create({"files": [{"filename": args.pdf.name, "content_base64": base64.b64encode(data).decode()}],
            "goal": GOAL, "budget": {"input_tokens": 8000, "output_tokens": 1600,
                "max_calls": args.max_calls, "total_tokens": args.total_tokens}})
        identifier = snapshot["id"]
        document = manager._load(identifier)["documents"][0]
        for section, role in roles.items():
            manager.classify({"job_id": identifier, "document_id": document["id"], "section": section, "role": role})
        report.update(initial_plan=snapshot["plan"], budget=snapshot["budget"], state="prepared")
        report["source"].update(pages=len(document["pages"]), blocks=len(document["blocks"]))
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        manager.start({"job_id": identifier})
        worker = manager.workers[identifier]
        previous = None
        while worker.is_alive():
            worker.join(1)
            progress = manager.snapshot(identifier, compact=True)
            current = (progress["state"], progress["calls_reserved"] // 5)
            if current != previous:
                print(json.dumps({"state": progress["state"], "calls": progress["calls_reserved"]}), flush=True)
                previous = current
        job = manager._load(identifier)
        completed = [step for step in job["steps"] if step["status"] == "completed"]
        attempts = [a for step in job["steps"] for a in step["attempts"]]
        ids = [i for step in completed if step["phase"] == "text" for i in step["block_ids"]]
        all_ids = [b["id"] for d in job["documents"] for b in d["blocks"]]
        observations = 0
        audit = []
        for step in completed:
            materials = step_materials(job, step)
            validate_review(step["result"], materials)
            observations += len(step["result"].get("checks", []))
            _, _, sources = grounded_request(source_payload(materials, job["goal"], step["phase"]))
            for attempt in step["attempts"]:
                metadata = attempt.get("model_run", {})
                valid = (metadata.get("source_map_sha256") == fingerprint(sources)
                         and metadata.get("wire_response_sha256") == fingerprint(attempt.get("review_wire")))
                if not valid:
                    raise ValueError("Source map or original model-choice audit mismatch")
                audit.append({"phase": step["phase"], "source_map_sha256": metadata["source_map_sha256"],
                              "wire_response_sha256": metadata["wire_response_sha256"]})
        all_observed = bool(completed) and all(s["result"].get("checks") for s in completed)
        complete = (job["state"] == "completed" and ids == all_ids and all_observed
                    and bool(job.get("chapter_built")) and bool(job["cross_built"]))
        report.update(state=job["state"], error=job["error"], technical_completion=complete,
            elapsed_seconds=round(time.monotonic() - started, 3), calls_reserved=job["calls_reserved"],
            tokens_reserved_estimate=job["tokens_reserved"], actual_attempts=len(attempts),
            completed_by_phase=dict(Counter(s["phase"] for s in completed)),
            checked_blocks=len(set(ids)), total_blocks=len(all_ids), each_text_block_once_in_order=ids == all_ids,
            chapter_stage_reached=job.get("chapter_built", False), cross_stage_reached=job["cross_built"],
            cross_pairs=[{"pair": row["pair"], "status": row["status"], "included": len(row["included"]),
                          "omitted": len(row["omitted"])} for row in manager.snapshot(identifier)["cross_coverage"]],
            observations=observations, every_completed_batch_has_observations=all_observed,
            claims=sum(len(s["result"]["claims"]) for s in completed),
            findings=sum(len(s["result"]["findings"]) for s in completed),
            empty_reports=sum(not any(s["result"].get(k) for k in ("summary", "checks", "claims", "findings", "limitations")) for s in completed),
            observed_provider_usage=[a["model_run"] for a in attempts if a.get("model_run")],
            attempts_with_missing_provider_usage=sum(not a.get("model_run", {}).get("usage") for a in attempts),
            source_choice_audit=audit, automatic_retries=0, hosted_calls=0)
        report["source"]["source_unchanged_after_run"] = sha(args.pdf) == report["source"]["sha256"]
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("state", "error", "technical_completion", "calls_reserved",
            "completed_by_phase", "checked_blocks", "total_blocks", "observations", "claims", "findings")}, ensure_ascii=False), flush=True)
    finally:
        manager.close()


if __name__ == "__main__":
    main()
