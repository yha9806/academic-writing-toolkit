#!/usr/bin/env python3
"""Validate thesis-control packets.

The checker is intentionally structural. It verifies that a project has
spine cards, edit contracts, drift audits, revision-escalation records, and
human-gate consistency for AI-assisted thesis edits. It does not judge whether
the academic argument is true or well written.
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

REVISION_CONTRACT_COLUMNS = ["revision_issue_id", "attempt_no"]
REVISION_ESCALATION_COLUMNS = [
    "escalation_id",
    "revision_issue_id",
    "trigger_contracts",
    "primary_category",
    "writing_scope",
    "valid_requirements",
    "missing_or_conflicting_information",
    "latest_author_approved_version",
    "recommended_next_action",
    "human_approved",
    "status",
]

CONTRACT_STATUSES = {"draft", "approved", "applied", "rejected"}
DRIFT_DECISIONS = {"accept", "partial_accept", "revise", "rollback"}
AUDIT_STATUSES = {"passed", "needs_review", "failed"}
ESCALATION_CATEGORIES = {
    "underspecified_or_conflicting_intent",
    "local_execution_failure",
    "structural_mismatch",
    "evidence_gap",
    "version_contamination",
}
WRITING_SCOPES = {"local_patch", "section_level_restructure", "full_reframing"}
ESCALATION_STATUSES = {"draft", "approved", "rejected"}
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


def read_fieldnames(path: Path) -> List[str]:
    if not path.is_file():
        return []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle).fieldnames or [])
    except (csv.Error, OSError):
        return []


def validate_columns(
    root: Path,
    filename: str,
    required_columns: Iterable[str],
    allow_empty: bool = False,
) -> Tuple[List[Dict[str, str]], List[dict]]:
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

    missing = [column for column in required_columns if column not in fieldnames]
    for column in missing:
        issues.append(
            {
                "kind": "missing-column",
                "location": str(path),
                "message": f"{filename} missing column: {column}",
            }
        )

    if not rows and not allow_empty:
        issues.append({"kind": "empty-file", "location": str(path), "message": f"{filename} has no data rows"})

    return rows, issues


def row_location(filename: str, index: int) -> str:
    return f"thesis_control/{filename}:row {index + 2}"


def add_issue(issues: List[dict], kind: str, location: str, message: str) -> None:
    issues.append({"kind": kind, "location": location, "message": message})


def validate_packet(root: Path, strict: bool = False) -> dict:
    issues: List[dict] = []
    control_dir = root / "thesis_control"
    contract_path = control_dir / "edit_contracts.csv"
    escalation_path = control_dir / "revision_escalations.csv"
    contract_fields = read_fieldnames(contract_path)
    revision_tracking = strict or escalation_path.is_file() or all(
        column in contract_fields for column in REVISION_CONTRACT_COLUMNS
    )

    spine_rows, spine_issues = validate_columns(
        root,
        "spine_cards.csv",
        REQUIRED_FILES["spine_cards.csv"],
    )
    contract_columns = list(REQUIRED_FILES["edit_contracts.csv"])
    if revision_tracking:
        contract_columns.extend(REVISION_CONTRACT_COLUMNS)
    contract_rows, contract_issues = validate_columns(
        root,
        "edit_contracts.csv",
        contract_columns,
    )
    audit_rows, audit_issues = validate_columns(
        root,
        "drift_audits.csv",
        REQUIRED_FILES["drift_audits.csv"],
        allow_empty=True,
    )
    escalation_rows: List[Dict[str, str]] = []
    escalation_issues: List[dict] = []
    if revision_tracking:
        escalation_rows, escalation_issues = validate_columns(
            root,
            "revision_escalations.csv",
            REVISION_ESCALATION_COLUMNS,
            allow_empty=True,
        )
    issues.extend(spine_issues + contract_issues + audit_issues + escalation_issues)

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
    contract_issues_by_id: Dict[str, str] = {}
    contract_attempts: Dict[str, int] = {}
    contract_statuses: Dict[str, str] = {}
    contract_locations: Dict[str, str] = {}
    issue_attempts: Dict[str, Dict[int, str]] = {}
    for index, row in enumerate(contract_rows):
        location = row_location("edit_contracts.csv", index)
        contract_id = row.get("contract_id", "").strip()
        unit_id = row.get("unit_id", "").strip()
        status = row.get("status", "").strip().lower()
        approved = parse_bool(row.get("human_approved", ""))
        revision_issue_id = row.get("revision_issue_id", "").strip()
        attempt_text = row.get("attempt_no", "").strip()

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

        if not unit_id:
            add_issue(issues, "missing-unit-id", location, "edit contract has no unit_id")
        elif not is_valid_identifier(unit_id):
            add_issue(
                issues,
                "invalid-unit-id",
                location,
                "unit_id must be 1-120 safe ASCII characters and must not contain path segments",
            )
        elif unit_id not in spine_ids:
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

        if contract_id:
            contract_statuses[contract_id] = status
            contract_locations[contract_id] = location

        if revision_tracking:
            if not revision_issue_id:
                add_issue(issues, "missing-revision-issue-id", location, "edit contract has no revision_issue_id")
            elif not is_valid_identifier(revision_issue_id):
                add_issue(
                    issues,
                    "invalid-revision-issue-id",
                    location,
                    "revision_issue_id must be a safe identifier",
                )

            attempt_no = None
            try:
                attempt_no = int(attempt_text)
            except ValueError:
                pass
            if attempt_no is None or attempt_no < 1:
                add_issue(issues, "invalid-attempt-no", location, "attempt_no must be a positive integer")
            elif revision_issue_id and is_valid_identifier(revision_issue_id):
                attempts = issue_attempts.setdefault(revision_issue_id, {})
                if attempt_no in attempts:
                    add_issue(
                        issues,
                        "duplicate-revision-attempt",
                        location,
                        f"revision issue {revision_issue_id} repeats attempt_no {attempt_no}",
                    )
                else:
                    attempts[attempt_no] = contract_id
                if contract_id:
                    contract_issues_by_id[contract_id] = revision_issue_id
                    contract_attempts[contract_id] = attempt_no

    if revision_tracking:
        for revision_issue_id, attempts in issue_attempts.items():
            numbers = sorted(attempts)
            if numbers and numbers != list(range(1, numbers[-1] + 1)):
                add_issue(
                    issues,
                    "nonsequential-revision-attempt",
                    "thesis_control/edit_contracts.csv",
                    f"revision issue {revision_issue_id} attempt numbers must be sequential from 1",
                )

    audit_ids = set()
    audited_contracts = set()
    unsuccessful_contracts = set()
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
        if decision in DRIFT_DECISIONS and status in AUDIT_STATUSES:
            resolved_decisions = {
                "passed": {"accept", "partial_accept"},
                "failed": {"revise", "rollback"},
            }
            if status in resolved_decisions and decision not in resolved_decisions[status]:
                add_issue(
                    issues,
                    "invalid-audit-outcome",
                    location,
                    f"audit status={status} is inconsistent with drift_decision={decision}",
                )
            if (
                decision in {"revise", "rollback"}
                and status == "failed"
                and contract_statuses.get(contract_id) == "applied"
            ):
                unsuccessful_contracts.add(contract_id)
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
        if (
            strict
            and contract_statuses.get(contract_id) == "applied"
            and status == "needs_review"
        ):
            add_issue(
                issues,
                "pending-human-review",
                location,
                "applied contract requires the author to resolve this drift audit before strict validation can pass",
            )
        if not is_empty(new_claims) and status == "passed":
            add_issue(issues, "unsupported-claim-passed", location, "new unsupported claims cannot have status=passed")
        if not is_empty(missed_adjacent) and status == "passed":
            add_issue(issues, "missed-adjacent-passed", location, "missed adjacent updates cannot have status=passed")

    escalations_by_issue: Dict[str, List[dict]] = {}
    escalation_ids = set()
    escalation_trigger_sets = set()
    if revision_tracking:
        for index, row in enumerate(escalation_rows):
            location = row_location("revision_escalations.csv", index)
            escalation_id = row.get("escalation_id", "").strip()
            revision_issue_id = row.get("revision_issue_id", "").strip()
            trigger_contracts = [
                value.strip()
                for value in row.get("trigger_contracts", "").split(";")
                if value.strip()
            ]
            trigger_set = set(trigger_contracts)
            category = row.get("primary_category", "").strip().lower()
            writing_scope = row.get("writing_scope", "").strip().lower()
            approved = parse_bool(row.get("human_approved", ""))
            status = row.get("status", "").strip().lower()

            if not escalation_id:
                add_issue(issues, "missing-escalation-id", location, "revision escalation has no escalation_id")
            elif not is_valid_identifier(escalation_id):
                add_issue(issues, "invalid-escalation-id", location, "escalation_id must be a safe identifier")
            elif escalation_id in escalation_ids:
                add_issue(issues, "duplicate-escalation-id", location, f"duplicate escalation_id: {escalation_id}")
            else:
                escalation_ids.add(escalation_id)

            if not revision_issue_id:
                add_issue(issues, "missing-revision-issue-id", location, "revision escalation has no revision_issue_id")
            elif not is_valid_identifier(revision_issue_id):
                add_issue(issues, "invalid-revision-issue-id", location, "revision_issue_id must be a safe identifier")
            elif revision_issue_id not in issue_attempts:
                add_issue(issues, "unknown-revision-issue-id", location, f"unknown revision_issue_id: {revision_issue_id}")

            if not trigger_contracts:
                add_issue(issues, "missing-trigger-contracts", location, "revision escalation has no trigger contracts")
            elif len(trigger_contracts) != len(trigger_set):
                add_issue(
                    issues,
                    "duplicate-trigger-contract",
                    location,
                    "revision escalation trigger_contracts must not repeat a contract",
                )
            for trigger_contract in trigger_contracts:
                if trigger_contract not in contract_ids:
                    add_issue(
                        issues,
                        "unknown-trigger-contract",
                        location,
                        f"unknown trigger contract: {trigger_contract}",
                    )
                elif contract_issues_by_id.get(trigger_contract) != revision_issue_id:
                    add_issue(
                        issues,
                        "trigger-contract-issue-mismatch",
                        location,
                        f"trigger contract {trigger_contract} is not part of {revision_issue_id}",
                    )

            if category not in ESCALATION_CATEGORIES:
                add_issue(issues, "invalid-escalation-category", location, f"invalid primary_category: {category}")
            if writing_scope not in WRITING_SCOPES:
                add_issue(issues, "invalid-writing-scope", location, f"invalid writing_scope: {writing_scope}")
            if approved is None:
                add_issue(issues, "invalid-human-approved", location, "human_approved must be true or false")
            if status not in ESCALATION_STATUSES:
                add_issue(issues, "invalid-escalation-status", location, f"invalid escalation status: {status}")
            if status == "approved" and approved is not True:
                add_issue(issues, "missing-human-approval", location, "approved escalation requires human_approved=true")

            for column in [
                "valid_requirements",
                "missing_or_conflicting_information",
                "latest_author_approved_version",
                "recommended_next_action",
            ]:
                if is_empty(row.get(column, "")):
                    add_issue(issues, "empty-escalation-field", location, f"revision escalation field is empty: {column}")

            if revision_issue_id and trigger_set:
                trigger_key = (revision_issue_id, frozenset(trigger_set))
                if trigger_key in escalation_trigger_sets:
                    add_issue(
                        issues,
                        "duplicate-escalation-trigger-set",
                        location,
                        "revision issue must not repeat an escalation trigger set",
                    )
                else:
                    escalation_trigger_sets.add(trigger_key)
                escalations_by_issue.setdefault(revision_issue_id, []).append(
                    {
                        "triggers": trigger_set,
                        "approved": approved is True and status == "approved",
                    }
                )

        unsuccessful_by_issue: Dict[str, List[Tuple[int, str]]] = {}
        for contract_id in unsuccessful_contracts:
            revision_issue_id = contract_issues_by_id.get(contract_id)
            attempt_no = contract_attempts.get(contract_id)
            if revision_issue_id and attempt_no is not None:
                unsuccessful_by_issue.setdefault(revision_issue_id, []).append((attempt_no, contract_id))

        for revision_issue_id, attempts in unsuccessful_by_issue.items():
            ordered = sorted(attempts)
            complete_groups = len(ordered) // 3
            for group_index in range(complete_groups):
                trigger_group = ordered[group_index * 3 : (group_index + 1) * 3]
                required_triggers = {contract_id for _, contract_id in trigger_group}
                threshold_attempt = max(attempt_no for attempt_no, _ in trigger_group)
                matching = [
                    escalation
                    for escalation in escalations_by_issue.get(revision_issue_id, [])
                    if required_triggers == escalation["triggers"]
                ]
                trigger_list = ", ".join(contract_id for _, contract_id in trigger_group)
                if not matching:
                    add_issue(
                        issues,
                        "missing-revision-escalation",
                        "thesis_control/revision_escalations.csv",
                        f"revision issue {revision_issue_id} needs an escalation record for {trigger_list}",
                    )
                approved_escalation = any(escalation["approved"] for escalation in matching)
                if approved_escalation:
                    continue
                for contract_id, attempt_no in contract_attempts.items():
                    if contract_issues_by_id.get(contract_id) != revision_issue_id:
                        continue
                    if attempt_no <= threshold_attempt:
                        continue
                    if contract_statuses.get(contract_id) in {"approved", "applied"}:
                        add_issue(
                            issues,
                            "revision-escalation-required",
                            contract_locations.get(contract_id, "thesis_control/edit_contracts.csv"),
                            f"contract {contract_id} cannot proceed before revision issue {revision_issue_id} has an approved escalation for {trigger_list}",
                        )

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
            "revision_escalations": len(escalation_rows),
            "revision_tracking": revision_tracking,
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
