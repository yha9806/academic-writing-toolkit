#!/usr/bin/env python3
"""Validate thesis-control packets.

The checker is intentionally structural. It verifies that a project has
spine cards, edit contracts, drift audits, and human-gate consistency for
AI-assisted thesis edits. It does not judge whether the academic argument is
true or well written.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


REQUIRED_FILES = {
    "spine_cards.csv": [
        "unit_id",
        "path",
        "section_title",
        "spine_sentence",
        "scope_boundary",
        "core_claims",
        "do_not_change",
    ],
    "edit_contracts.csv": [
        "contract_id",
        "unit_id",
        "change_scope",
        "allowed_changes",
        "forbidden_changes",
        "adjacent_context",
        "acceptance_checks",
        "human_approved",
        "status",
    ],
    "drift_audits.csv": [
        "audit_id",
        "contract_id",
        "changed_claims",
        "changed_boundaries",
        "new_unsupported_claims",
        "missed_adjacent_updates",
        "drift_decision",
        "human_review_required",
        "status",
    ],
}

CONTRACT_STATUSES = {"draft", "approved", "applied", "rejected"}
DRIFT_DECISIONS = {"accept", "partial_accept", "revise", "rollback"}
AUDIT_STATUSES = {"passed", "needs_review", "failed"}
EMPTY_MARKERS = {"", "none", "n/a", "na", "no", "not applicable"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,118}[A-Za-z0-9])?$")


def is_empty(value: str) -> bool:
    return value.strip().lower() in EMPTY_MARKERS


def parse_bool(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered in {"true", "yes", "y", "1"}:
        return True
    if lowered in {"false", "no", "n", "0"}:
        return False
    return None


def is_valid_identifier(value: str) -> bool:
    stripped = value.strip()
    return bool(IDENTIFIER_RE.fullmatch(stripped)) and ".." not in stripped


def validate_source_path(root: Path, value: str) -> str | None:
    path_text = value.strip()
    if not path_text:
        return None
    source_path = Path(path_text)
    if source_path.is_absolute():
        return "source path must be relative to the packet root"
    if ".." in source_path.parts:
        return "source path must not contain '..'"
    candidate = (root / source_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return "source path must stay inside the packet root"
    if not candidate.is_file():
        return "source path does not exist"
    return None


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    issues: List[str] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
    except csv.Error as exc:
        return [], [f"{path}: CSV parse error: {exc}"]
    except OSError as exc:
        return [], [f"{path}: cannot read file: {exc}"]

    if reader.fieldnames is None:
        return [], [f"{path}: missing header row"]

    return rows, issues


def validate_columns(root: Path, filename: str) -> Tuple[List[Dict[str, str]], List[dict]]:
    path = root / "thesis_control" / filename
    issues: List[dict] = []
    if not path.is_file():
        return [], [{"kind": "missing-file", "location": str(path), "message": f"missing {filename}"}]

    rows, read_issues = read_csv(path)
    for message in read_issues:
        issues.append({"kind": "csv-error", "location": str(path), "message": message})
    if issues:
        return rows, issues

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []

    missing = [column for column in REQUIRED_FILES[filename] if column not in fieldnames]
    for column in missing:
        issues.append(
            {
                "kind": "missing-column",
                "location": str(path),
                "message": f"{filename} missing column: {column}",
            }
        )

    if not rows and filename != "drift_audits.csv":
        issues.append({"kind": "empty-file", "location": str(path), "message": f"{filename} has no data rows"})

    return rows, issues


def row_location(filename: str, index: int) -> str:
    return f"thesis_control/{filename}:row {index + 2}"


def add_issue(issues: List[dict], kind: str, location: str, message: str) -> None:
    issues.append({"kind": kind, "location": location, "message": message})


def validate_packet(root: Path, strict: bool = False) -> dict:
    issues: List[dict] = []
    spine_rows, spine_issues = validate_columns(root, "spine_cards.csv")
    contract_rows, contract_issues = validate_columns(root, "edit_contracts.csv")
    audit_rows, audit_issues = validate_columns(root, "drift_audits.csv")
    issues.extend(spine_issues + contract_issues + audit_issues)

    spine_ids = set()
    for index, row in enumerate(spine_rows):
        location = row_location("spine_cards.csv", index)
        unit_id = row.get("unit_id", "").strip()
        if not unit_id:
            add_issue(issues, "missing-unit-id", location, "spine card has no unit_id")
        elif not is_valid_identifier(unit_id):
            add_issue(
                issues,
                "invalid-unit-id",
                location,
                "unit_id must be 1-120 safe ASCII characters and must not contain path segments",
            )
        elif unit_id in spine_ids:
            add_issue(issues, "duplicate-unit-id", location, f"duplicate unit_id: {unit_id}")
        else:
            spine_ids.add(unit_id)

        for column in ["path", "section_title", "spine_sentence", "scope_boundary", "core_claims", "do_not_change"]:
            if is_empty(row.get(column, "")):
                add_issue(issues, "empty-spine-field", location, f"spine card field is empty: {column}")
        path_issue = validate_source_path(root, row.get("path", ""))
        if path_issue:
            add_issue(issues, "invalid-source-path", location, path_issue)

    contract_ids = set()
    applied_contracts = set()
    for index, row in enumerate(contract_rows):
        location = row_location("edit_contracts.csv", index)
        contract_id = row.get("contract_id", "").strip()
        unit_id = row.get("unit_id", "").strip()
        status = row.get("status", "").strip().lower()
        approved = parse_bool(row.get("human_approved", ""))

        if not contract_id:
            add_issue(issues, "missing-contract-id", location, "edit contract has no contract_id")
        elif not is_valid_identifier(contract_id):
            add_issue(
                issues,
                "invalid-contract-id",
                location,
                "contract_id must be 1-120 safe ASCII characters and must not contain path segments",
            )
        elif contract_id in contract_ids:
            add_issue(issues, "duplicate-contract-id", location, f"duplicate contract_id: {contract_id}")
        else:
            contract_ids.add(contract_id)

        if unit_id and not is_valid_identifier(unit_id):
            add_issue(
                issues,
                "invalid-unit-id",
                location,
                "unit_id must be 1-120 safe ASCII characters and must not contain path segments",
            )
        if unit_id and unit_id not in spine_ids:
            add_issue(issues, "unknown-unit-id", location, f"contract references unknown unit_id: {unit_id}")

        if status not in CONTRACT_STATUSES:
            add_issue(issues, "invalid-contract-status", location, f"invalid contract status: {status}")

        if approved is None:
            add_issue(issues, "invalid-human-approved", location, "human_approved must be true or false")
        if status in {"approved", "applied"} and approved is not True:
            add_issue(issues, "missing-human-approval", location, "approved/applied contracts require human_approved=true")

        for column in ["change_scope", "allowed_changes", "forbidden_changes", "adjacent_context", "acceptance_checks"]:
            if is_empty(row.get(column, "")):
                add_issue(issues, "empty-contract-field", location, f"edit contract field is empty: {column}")

        if status == "applied" and contract_id:
            applied_contracts.add(contract_id)

    audit_ids = set()
    audited_contracts = set()
    for index, row in enumerate(audit_rows):
        location = row_location("drift_audits.csv", index)
        audit_id = row.get("audit_id", "").strip()
        contract_id = row.get("contract_id", "").strip()
        decision = row.get("drift_decision", "").strip().lower()
        status = row.get("status", "").strip().lower()
        review_required = parse_bool(row.get("human_review_required", ""))
        changed_claims = row.get("changed_claims", "")
        changed_boundaries = row.get("changed_boundaries", "")
        new_claims = row.get("new_unsupported_claims", "")
        missed_adjacent = row.get("missed_adjacent_updates", "")

        if not audit_id:
            add_issue(issues, "missing-audit-id", location, "drift audit has no audit_id")
        elif not is_valid_identifier(audit_id):
            add_issue(
                issues,
                "invalid-audit-id",
                location,
                "audit_id must be 1-120 safe ASCII characters and must not contain path segments",
            )
        elif audit_id in audit_ids:
            add_issue(issues, "duplicate-audit-id", location, f"duplicate audit_id: {audit_id}")
        else:
            audit_ids.add(audit_id)

        if contract_id:
            audited_contracts.add(contract_id)
            if not is_valid_identifier(contract_id):
                add_issue(
                    issues,
                    "invalid-contract-id",
                    location,
                    "contract_id must be 1-120 safe ASCII characters and must not contain path segments",
                )
            if contract_id not in contract_ids:
                add_issue(issues, "unknown-contract-id", location, f"audit references unknown contract_id: {contract_id}")
        else:
            add_issue(issues, "missing-contract-id", location, "drift audit has no contract_id")

        if decision not in DRIFT_DECISIONS:
            add_issue(issues, "invalid-drift-decision", location, f"invalid drift_decision: {decision}")
        if status not in AUDIT_STATUSES:
            add_issue(issues, "invalid-audit-status", location, f"invalid audit status: {status}")
        if review_required is None:
            add_issue(issues, "invalid-human-review-required", location, "human_review_required must be true or false")

        high_risk = any(
            not is_empty(value)
            for value in [changed_claims, changed_boundaries, new_claims, missed_adjacent]
        )
        if high_risk and review_required is not True:
            add_issue(issues, "missing-human-review", location, "claim/boundary/adjacent drift requires human_review_required=true")
        if high_risk and decision == "accept":
            add_issue(issues, "unsafe-accept", location, "high-risk drift cannot be accepted without revision or partial acceptance")
        if not is_empty(new_claims) and status == "passed":
            add_issue(issues, "unsupported-claim-passed", location, "new unsupported claims cannot have status=passed")
        if not is_empty(missed_adjacent) and status == "passed":
            add_issue(issues, "missed-adjacent-passed", location, "missed adjacent updates cannot have status=passed")

    if strict:
        missing_audits = sorted(applied_contracts - audited_contracts)
        for contract_id in missing_audits:
            add_issue(
                issues,
                "missing-drift-audit",
                "thesis_control/drift_audits.csv",
                f"applied contract has no drift audit: {contract_id}",
            )

    return {
        "schema_version": 1,
        "base_dir": str(root),
        "strict": strict,
        "summary": {
            "spine_cards": len(spine_rows),
            "edit_contracts": len(contract_rows),
            "drift_audits": len(audit_rows),
        },
        "issues": issues,
        "issue_count": len(issues),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate thesis-control spine, contract, and drift-audit files.")
    parser.add_argument("base_dir", nargs="?", default=".", help="Project root containing thesis_control/")
    parser.add_argument("--strict", action="store_true", help="Require every applied contract to have a drift audit")
    parser.add_argument("--json", action="store_true", dest="emit_json", help="Emit JSON output")
    args = parser.parse_args(list(argv) if argv is not None else None)

    root = Path(args.base_dir).resolve()
    payload = validate_packet(root, strict=args.strict)

    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Thesis-control root: {root}")
        if payload["issues"]:
            for issue in payload["issues"]:
                print(f"- {issue['location']}: {issue['kind']}: {issue['message']}")
        else:
            print("- no thesis-control issues detected")

    return 1 if payload["issues"] else 0


if __name__ == "__main__":
    sys.exit(main())
