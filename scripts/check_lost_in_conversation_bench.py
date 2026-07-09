#!/usr/bin/env python3
"""Validate the lost-in-conversation writing-control bench fixture.

The checker is structural. It verifies that the public-safe fixture contains
the three comparison workflows and that the treatment workflow records the
control artifacts needed for author review. It does not judge prose quality.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Iterable, List


REQUIRED_FILES = [
    "README.md",
    "chapters/desensitized_section.md",
    "requirements/multi_turn_requirements.md",
    "requirements/consolidated_prompt.md",
    "baselines/baseline_a_edited_section.md",
    "baselines/baseline_a_review.md",
    "baselines/baseline_b_edited_section.md",
    "baselines/baseline_b_review.md",
    "comparison_report.md",
    "treatment/source_excerpts/lost-conversation-section.md",
    "treatment/edited_section.md",
    "treatment/review_report.md",
    "treatment/thesis_control/spine_cards.csv",
    "treatment/thesis_control/edit_contracts.csv",
    "treatment/thesis_control/drift_audits.csv",
]

REQUIRED_METRICS = [
    "Spine preservation",
    "Claim drift",
    "Evidence boundary",
    "Scope discipline",
    "Author control recovery",
]

REQUIRED_REVIEW_HEADINGS = [
    "## Workflow",
    "## Metric Review",
    "## Control Finding",
]

REQUIRED_COMPARISON_HEADINGS = [
    "## Summary",
    "## Three-Way Metric Comparison",
    "## Human Review Decision",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def add_issue(issues: List[dict], kind: str, location: str, message: str) -> None:
    issues.append({"kind": kind, "location": location, "message": message})


def read_csv_rows(path: Path) -> List[dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_required_files(root: Path, issues: List[dict]) -> None:
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if not path.is_file():
            add_issue(issues, "missing-file", rel_path, "required bench file is missing")


def validate_prompt_files(root: Path, issues: List[dict]) -> None:
    multi_turn = root / "requirements/multi_turn_requirements.md"
    consolidated = root / "requirements/consolidated_prompt.md"
    if multi_turn.is_file():
        text = read_text(multi_turn)
        for label in ["Turn 1", "Turn 2", "Turn 3", "Turn 4", "Turn 5"]:
            if label not in text:
                add_issue(issues, "missing-turn", str(multi_turn.relative_to(root)), f"missing {label}")
    if consolidated.is_file():
        text = read_text(consolidated)
        for metric in REQUIRED_METRICS:
            if metric not in text:
                add_issue(
                    issues,
                    "missing-consolidated-metric",
                    str(consolidated.relative_to(root)),
                    f"consolidated prompt does not name {metric}",
                )


def validate_review(path: Path, root: Path, issues: List[dict]) -> None:
    if not path.is_file():
        return
    text = read_text(path)
    rel = str(path.relative_to(root))
    for heading in REQUIRED_REVIEW_HEADINGS:
        if heading not in text:
            add_issue(issues, "missing-review-heading", rel, f"review is missing heading {heading}")
    for metric in REQUIRED_METRICS:
        if metric not in text:
            add_issue(issues, "missing-review-metric", rel, f"review does not address {metric}")


def validate_comparison_report(root: Path, issues: List[dict]) -> None:
    path = root / "comparison_report.md"
    if not path.is_file():
        return
    text = read_text(path)
    rel = str(path.relative_to(root))
    for heading in REQUIRED_COMPARISON_HEADINGS:
        if heading not in text:
            add_issue(issues, "missing-comparison-heading", rel, f"comparison report is missing heading {heading}")
    for workflow in ["Baseline A", "Baseline B", "Treatment"]:
        if workflow not in text:
            add_issue(issues, "missing-comparison-workflow", rel, f"comparison report does not address {workflow}")
    for metric in REQUIRED_METRICS:
        if metric not in text:
            add_issue(issues, "missing-comparison-metric", rel, f"comparison report does not address {metric}")


def validate_treatment_packet(root: Path, issues: List[dict]) -> None:
    treatment = root / "treatment"
    spine_path = treatment / "thesis_control" / "spine_cards.csv"
    contract_path = treatment / "thesis_control" / "edit_contracts.csv"
    audit_path = treatment / "thesis_control" / "drift_audits.csv"
    if not (spine_path.is_file() and contract_path.is_file() and audit_path.is_file()):
        return

    spine_rows = read_csv_rows(spine_path)
    contract_rows = read_csv_rows(contract_path)
    audit_rows = read_csv_rows(audit_path)
    if len(spine_rows) != 1:
        add_issue(issues, "unexpected-spine-count", str(spine_path.relative_to(root)), "bench treatment should have exactly one spine row")
    if len(contract_rows) != 1:
        add_issue(issues, "unexpected-contract-count", str(contract_path.relative_to(root)), "bench treatment should have exactly one contract row")
    if len(audit_rows) != 1:
        add_issue(issues, "unexpected-audit-count", str(audit_path.relative_to(root)), "bench treatment should have exactly one audit row")
    if contract_rows:
        row = contract_rows[0]
        if row.get("status", "").strip().lower() != "applied":
            add_issue(issues, "contract-not-applied", str(contract_path.relative_to(root)), "treatment contract must be status=applied")
        if row.get("human_approved", "").strip().lower() != "true":
            add_issue(issues, "contract-not-approved", str(contract_path.relative_to(root)), "treatment contract must have human_approved=true")
    if audit_rows:
        row = audit_rows[0]
        if row.get("drift_decision", "").strip().lower() not in {"accept", "partial_accept", "revise", "rollback"}:
            add_issue(issues, "invalid-treatment-decision", str(audit_path.relative_to(root)), "treatment audit needs a valid drift_decision")
        if row.get("status", "").strip().lower() not in {"passed", "needs_review", "failed"}:
            add_issue(issues, "invalid-treatment-status", str(audit_path.relative_to(root)), "treatment audit needs a valid status")


def validate_bench(root: Path) -> dict:
    issues: List[dict] = []
    validate_required_files(root, issues)
    validate_prompt_files(root, issues)
    validate_review(root / "baselines" / "baseline_a_review.md", root, issues)
    validate_review(root / "baselines" / "baseline_b_review.md", root, issues)
    validate_review(root / "treatment" / "review_report.md", root, issues)
    validate_comparison_report(root, issues)
    validate_treatment_packet(root, issues)
    return {
        "schema_version": 1,
        "bench_root": str(root),
        "issues": issues,
        "issue_count": len(issues),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the lost-in-conversation writing-control bench fixture.")
    parser.add_argument("bench_root", nargs="?", default="examples/lost-in-conversation-bench")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.bench_root).resolve()
    payload = validate_bench(root)
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    elif payload["issues"]:
        print(f"Lost-in-conversation bench root: {root}")
        for issue in payload["issues"]:
            print(f"- {issue['location']}: {issue['kind']}: {issue['message']}")
    else:
        print(f"Lost-in-conversation bench root: {root}")
        print("- no bench issues detected")
    return 1 if payload["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
