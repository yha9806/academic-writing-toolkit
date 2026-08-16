#!/usr/bin/env python3
"""Validate the project-intent and manuscript-level thesis-control layer.

This module is deliberately structural. It validates durable author-approved
objects and their gates; it does not infer whether manuscript prose is
semantically aligned with the recorded intent.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from thesis_control_io import CsvShapeError, read_csv_table


PROJECT_INTENT_COLUMNS = [
    "intent_id",
    "intent_version",
    "supersedes_intent_id",
    "primary_domain",
    "research_object",
    "core_research_question",
    "target_venue",
    "must_include_concepts",
    "excluded_reframes",
    "amendment_reason",
    "approval_evidence",
    "human_approved",
    "status",
]

MANUSCRIPT_CONTRACT_COLUMNS = [
    "manuscript_id",
    "intent_id",
    "manuscript_version",
    "supersedes_manuscript_id",
    "title",
    "abstract_focus",
    "primary_domain",
    "research_object",
    "research_question",
    "contribution_scope",
    "structure_summary",
    "change_summary",
    "human_approved",
    "status",
]

GLOBAL_THESIS_AUDIT_COLUMNS = [
    "global_audit_id",
    "intent_id",
    "manuscript_id",
    "manuscript_version",
    "title_alignment",
    "abstract_alignment",
    "primary_domain_alignment",
    "research_object_alignment",
    "research_question_alignment",
    "contribution_alignment",
    "structure_alignment",
    "detected_reframe",
    "reframe_summary",
    "human_review_required",
    "human_decision",
    "status",
]

PROJECT_INTENT_FILES = {
    "project_intent.csv": PROJECT_INTENT_COLUMNS,
    "manuscript_contracts.csv": MANUSCRIPT_CONTRACT_COLUMNS,
    "global_thesis_audits.csv": GLOBAL_THESIS_AUDIT_COLUMNS,
}

INTENT_STATUSES = {"draft", "active", "superseded", "rejected"}
MANUSCRIPT_STATUSES = {"draft", "active", "superseded", "rejected"}
GLOBAL_AUDIT_STATUSES = {"passed", "needs_review", "failed"}
ALIGNMENT_STATUSES = {"aligned", "drifted", "not_assessed"}
GLOBAL_DECISIONS = {
    "accept",
    "revise_manuscript",
    "rollback",
    "amend_intent",
    "pending",
}
EMPTY_MARKERS = {"", "none", "n/a", "na", "no", "not applicable"}
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,118}[A-Za-z0-9])?$")
ALIGNMENT_COLUMNS = [
    "title_alignment",
    "abstract_alignment",
    "primary_domain_alignment",
    "research_object_alignment",
    "research_question_alignment",
    "contribution_alignment",
    "structure_alignment",
]


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


def row_location(filename: str, index: int) -> str:
    return f"thesis_control/{filename}:row {index + 2}"


def add_issue(issues: List[dict], kind: str, location: str, message: str) -> None:
    issues.append({"kind": kind, "location": location, "message": message})


def read_control_table(
    root: Path,
    filename: str,
    required_columns: Sequence[str],
    table: Optional[Tuple[Sequence[str], Sequence[Mapping[str, str]]]] = None,
) -> Tuple[List[Dict[str, str]], List[dict]]:
    path = root / "thesis_control" / filename
    issues: List[dict] = []
    if table is None:
        if not path.is_file():
            return [], [
                {
                    "kind": "missing-file",
                    "location": str(path),
                    "message": f"missing {filename}",
                }
            ]
        try:
            fieldnames, rows = read_csv_table(path)
        except CsvShapeError as exc:
            return [], [
                {"kind": exc.kind, "location": exc.location, "message": exc.message}
            ]
        except OSError as exc:
            return [], [
                {
                    "kind": "csv-error",
                    "location": str(path),
                    "message": f"cannot read file: {exc}",
                }
            ]
    else:
        fieldnames = list(table[0])
        rows = [dict(row) for row in table[1]]

    for column in required_columns:
        if column not in fieldnames:
            add_issue(
                issues,
                "missing-column",
                str(path),
                f"{filename} missing column: {column}",
            )
    if not rows:
        add_issue(
            issues,
            "empty-file",
            str(path),
            f"{filename} has no data rows",
        )
    return rows, issues


def parse_positive_version(
    issues: List[dict], value: str, kind: str, location: str, label: str
) -> Optional[int]:
    try:
        version = int(value.strip())
    except ValueError:
        version = 0
    if version < 1:
        add_issue(issues, kind, location, f"{label} must be a positive integer")
        return None
    return version


def validate_project_intent_layer(
    root: Path,
    required: bool,
    table_overrides: Optional[
        Mapping[str, Tuple[Sequence[str], Sequence[Mapping[str, str]]]]
    ] = None,
) -> Tuple[dict, List[dict]]:
    """Return validated intent-layer state and located structural issues."""

    overrides = table_overrides or {}
    enabled = required or any(
        filename in overrides or (root / "thesis_control" / filename).exists()
        for filename in PROJECT_INTENT_FILES
    )
    empty_state = {
        "enabled": False,
        "intent_rows": [],
        "manuscript_rows": [],
        "audit_rows": [],
        "intents_by_id": {},
        "manuscripts_by_id": {},
        "audits_by_id": {},
        "active_intent_ids": set(),
        "active_manuscript_ids": set(),
        "ready_audit_ids": set(),
    }
    if not enabled:
        return empty_state, []

    issues: List[dict] = []
    tables: Dict[str, List[Dict[str, str]]] = {}
    for filename, columns in PROJECT_INTENT_FILES.items():
        rows, table_issues = read_control_table(
            root,
            filename,
            columns,
            table=overrides.get(filename),
        )
        tables[filename] = rows
        issues.extend(table_issues)

    intent_rows = tables["project_intent.csv"]
    manuscript_rows = tables["manuscript_contracts.csv"]
    audit_rows = tables["global_thesis_audits.csv"]

    intents_by_id: Dict[str, dict] = {}
    intent_versions: Dict[int, str] = {}
    active_intent_ids = set()
    for index, row in enumerate(intent_rows):
        location = row_location("project_intent.csv", index)
        intent_id = row.get("intent_id", "").strip()
        status = row.get("status", "").strip().lower()
        approved = parse_bool(row.get("human_approved", ""))
        version = parse_positive_version(
            issues,
            row.get("intent_version", ""),
            "invalid-intent-version",
            location,
            "intent_version",
        )
        if not intent_id:
            add_issue(issues, "missing-intent-id", location, "project intent has no intent_id")
        elif not is_valid_identifier(intent_id):
            add_issue(issues, "invalid-intent-id", location, "intent_id must be a safe identifier")
        elif intent_id in intents_by_id:
            add_issue(issues, "duplicate-intent-id", location, f"duplicate intent_id: {intent_id}")
        else:
            intents_by_id[intent_id] = {
                "row": row,
                "status": status,
                "approved": approved,
                "version": version,
                "location": location,
            }
        if version is not None:
            if version in intent_versions:
                add_issue(
                    issues,
                    "duplicate-intent-version",
                    location,
                    f"intent_version {version} is already used by {intent_versions[version]}",
                )
            else:
                intent_versions[version] = intent_id
        if status not in INTENT_STATUSES:
            add_issue(issues, "invalid-intent-status", location, f"invalid project intent status: {status}")
        if approved is None:
            add_issue(issues, "invalid-human-approved", location, "human_approved must be true or false")
        if status in {"active", "superseded"} and approved is not True:
            add_issue(
                issues,
                "missing-intent-approval",
                location,
                "active/superseded project intent requires human_approved=true",
            )
        if status == "active" and intent_id:
            active_intent_ids.add(intent_id)
        for column in [
            "primary_domain",
            "research_object",
            "core_research_question",
            "target_venue",
            "must_include_concepts",
            "excluded_reframes",
            "amendment_reason",
            "approval_evidence",
        ]:
            if is_empty(row.get(column, "")):
                add_issue(
                    issues,
                    "empty-intent-field",
                    location,
                    f"project intent field is empty: {column}",
                )

    if len(active_intent_ids) > 1:
        add_issue(
            issues,
            "multiple-active-intents",
            "thesis_control/project_intent.csv",
            "project intent history must have at most one active row",
        )

    for intent_id, record in intents_by_id.items():
        row = record["row"]
        version = record["version"]
        supersedes = row.get("supersedes_intent_id", "").strip()
        location = record["location"]
        if version == 1 and supersedes:
            add_issue(
                issues,
                "invalid-intent-lineage",
                location,
                "intent_version 1 must not supersede another intent",
            )
        if version is not None and version > 1:
            if not supersedes:
                add_issue(
                    issues,
                    "missing-intent-amendment",
                    location,
                    "later project intent versions must name supersedes_intent_id",
                )
            elif supersedes not in intents_by_id:
                add_issue(
                    issues,
                    "unknown-superseded-intent",
                    location,
                    f"unknown supersedes_intent_id: {supersedes}",
                )
            else:
                previous = intents_by_id[supersedes]
                if previous["version"] != version - 1:
                    add_issue(
                        issues,
                        "nonsequential-intent-lineage",
                        location,
                        "project intent amendments must supersede the immediately previous version",
                    )
                if record["status"] == "active" and previous["status"] != "superseded":
                    add_issue(
                        issues,
                        "unsuperseded-prior-intent",
                        location,
                        "an active amendment requires the previous intent status=superseded",
                    )

    manuscripts_by_id: Dict[str, dict] = {}
    manuscript_versions: Dict[int, str] = {}
    active_manuscript_ids = set()
    for index, row in enumerate(manuscript_rows):
        location = row_location("manuscript_contracts.csv", index)
        manuscript_id = row.get("manuscript_id", "").strip()
        intent_id = row.get("intent_id", "").strip()
        status = row.get("status", "").strip().lower()
        approved = parse_bool(row.get("human_approved", ""))
        version = parse_positive_version(
            issues,
            row.get("manuscript_version", ""),
            "invalid-manuscript-version",
            location,
            "manuscript_version",
        )
        if not manuscript_id:
            add_issue(issues, "missing-manuscript-id", location, "manuscript contract has no manuscript_id")
        elif not is_valid_identifier(manuscript_id):
            add_issue(issues, "invalid-manuscript-id", location, "manuscript_id must be a safe identifier")
        elif manuscript_id in manuscripts_by_id:
            add_issue(
                issues,
                "duplicate-manuscript-id",
                location,
                f"duplicate manuscript_id: {manuscript_id}",
            )
        else:
            manuscripts_by_id[manuscript_id] = {
                "row": row,
                "intent_id": intent_id,
                "status": status,
                "approved": approved,
                "version": version,
                "location": location,
            }
        if version is not None:
            if version in manuscript_versions:
                add_issue(
                    issues,
                    "duplicate-manuscript-version",
                    location,
                    f"manuscript_version {version} is already used by {manuscript_versions[version]}",
                )
            else:
                manuscript_versions[version] = manuscript_id
        if not intent_id:
            add_issue(issues, "missing-intent-id", location, "manuscript contract has no intent_id")
        elif intent_id not in intents_by_id:
            add_issue(issues, "unknown-intent-id", location, f"unknown intent_id: {intent_id}")
        if status not in MANUSCRIPT_STATUSES:
            add_issue(issues, "invalid-manuscript-status", location, f"invalid manuscript status: {status}")
        if approved is None:
            add_issue(issues, "invalid-human-approved", location, "human_approved must be true or false")
        if status in {"active", "superseded"} and approved is not True:
            add_issue(
                issues,
                "missing-manuscript-approval",
                location,
                "active/superseded manuscript contract requires human_approved=true",
            )
        if status == "active" and manuscript_id:
            active_manuscript_ids.add(manuscript_id)
            if intent_id not in active_intent_ids:
                add_issue(
                    issues,
                    "inactive-intent-reference",
                    location,
                    "active manuscript contract must reference the active project intent",
                )
        for column in [
            "title",
            "abstract_focus",
            "primary_domain",
            "research_object",
            "research_question",
            "contribution_scope",
            "structure_summary",
            "change_summary",
        ]:
            if is_empty(row.get(column, "")):
                add_issue(
                    issues,
                    "empty-manuscript-field",
                    location,
                    f"manuscript contract field is empty: {column}",
                )

    if len(active_manuscript_ids) > 1:
        add_issue(
            issues,
            "multiple-active-manuscripts",
            "thesis_control/manuscript_contracts.csv",
            "manuscript contract history must have at most one active row",
        )

    for manuscript_id, record in manuscripts_by_id.items():
        row = record["row"]
        version = record["version"]
        supersedes = row.get("supersedes_manuscript_id", "").strip()
        location = record["location"]
        if version == 1 and supersedes:
            add_issue(
                issues,
                "invalid-manuscript-lineage",
                location,
                "manuscript_version 1 must not supersede another manuscript contract",
            )
        if version is not None and version > 1:
            if not supersedes:
                add_issue(
                    issues,
                    "missing-manuscript-amendment",
                    location,
                    "later manuscript versions must name supersedes_manuscript_id",
                )
            elif supersedes not in manuscripts_by_id:
                add_issue(
                    issues,
                    "unknown-superseded-manuscript",
                    location,
                    f"unknown supersedes_manuscript_id: {supersedes}",
                )
            else:
                previous = manuscripts_by_id[supersedes]
                if previous["version"] != version - 1:
                    add_issue(
                        issues,
                        "nonsequential-manuscript-lineage",
                        location,
                        "manuscript amendments must supersede the immediately previous version",
                    )
                if record["status"] == "active" and previous["status"] != "superseded":
                    add_issue(
                        issues,
                        "unsuperseded-prior-manuscript",
                        location,
                        "an active manuscript amendment requires the previous status=superseded",
                    )

    audits_by_id: Dict[str, dict] = {}
    ready_audit_ids = set()
    for index, row in enumerate(audit_rows):
        location = row_location("global_thesis_audits.csv", index)
        audit_id = row.get("global_audit_id", "").strip()
        intent_id = row.get("intent_id", "").strip()
        manuscript_id = row.get("manuscript_id", "").strip()
        status = row.get("status", "").strip().lower()
        decision = row.get("human_decision", "").strip().lower()
        detected_reframe = parse_bool(row.get("detected_reframe", ""))
        review_required = parse_bool(row.get("human_review_required", ""))
        version = parse_positive_version(
            issues,
            row.get("manuscript_version", ""),
            "invalid-audit-manuscript-version",
            location,
            "manuscript_version",
        )
        if not audit_id:
            add_issue(issues, "missing-global-audit-id", location, "global thesis audit has no global_audit_id")
        elif not is_valid_identifier(audit_id):
            add_issue(issues, "invalid-global-audit-id", location, "global_audit_id must be a safe identifier")
        elif audit_id in audits_by_id:
            add_issue(
                issues,
                "duplicate-global-audit-id",
                location,
                f"duplicate global_audit_id: {audit_id}",
            )
        else:
            audits_by_id[audit_id] = {
                "row": row,
                "intent_id": intent_id,
                "manuscript_id": manuscript_id,
                "status": status,
                "location": location,
            }
        if intent_id not in intents_by_id:
            add_issue(issues, "unknown-intent-id", location, f"unknown intent_id: {intent_id}")
        if manuscript_id not in manuscripts_by_id:
            add_issue(issues, "unknown-manuscript-id", location, f"unknown manuscript_id: {manuscript_id}")
        else:
            manuscript = manuscripts_by_id[manuscript_id]
            if manuscript["intent_id"] != intent_id:
                add_issue(
                    issues,
                    "audit-intent-mismatch",
                    location,
                    "global thesis audit intent_id does not match its manuscript contract",
                )
            if version is not None and manuscript["version"] != version:
                add_issue(
                    issues,
                    "stale-global-audit-version",
                    location,
                    "global thesis audit manuscript_version does not match its manuscript contract",
                )
        alignments = [row.get(column, "").strip().lower() for column in ALIGNMENT_COLUMNS]
        for column, value in zip(ALIGNMENT_COLUMNS, alignments):
            if value not in ALIGNMENT_STATUSES:
                add_issue(
                    issues,
                    "invalid-global-alignment",
                    location,
                    f"invalid {column}: {value}",
                )
        if detected_reframe is None:
            add_issue(issues, "invalid-detected-reframe", location, "detected_reframe must be true or false")
        if review_required is None:
            add_issue(
                issues,
                "invalid-human-review-required",
                location,
                "human_review_required must be true or false",
            )
        if decision not in GLOBAL_DECISIONS:
            add_issue(issues, "invalid-global-decision", location, f"invalid human_decision: {decision}")
        if status not in GLOBAL_AUDIT_STATUSES:
            add_issue(issues, "invalid-global-audit-status", location, f"invalid global audit status: {status}")
        if is_empty(row.get("reframe_summary", "")):
            add_issue(issues, "empty-reframe-summary", location, "global thesis audit needs reframe_summary")

        has_drift = detected_reframe is True or "drifted" in alignments
        not_assessed = "not_assessed" in alignments
        if has_drift and review_required is not True:
            add_issue(
                issues,
                "missing-global-human-review",
                location,
                "global thesis drift or reframing requires human_review_required=true",
            )
        if has_drift and (status == "passed" or decision == "accept"):
            add_issue(
                issues,
                "unsafe-global-pass",
                location,
                "global thesis drift cannot pass or be accepted; revise, rollback, or amend intent",
            )
        if not_assessed and status != "needs_review":
            add_issue(
                issues,
                "unassessed-global-audit",
                location,
                "not_assessed alignment requires status=needs_review",
            )
        if status == "needs_review" and decision != "pending":
            add_issue(
                issues,
                "invalid-pending-global-decision",
                location,
                "status=needs_review requires human_decision=pending",
            )
        if status == "passed":
            passed_shape = (
                all(value == "aligned" for value in alignments)
                and detected_reframe is False
                and decision == "accept"
                and intent_id in active_intent_ids
                and manuscript_id in active_manuscript_ids
            )
            if not passed_shape:
                add_issue(
                    issues,
                    "invalid-global-pass",
                    location,
                    "passed audit requires complete alignment and active approved intent/manuscript contracts",
                )
            elif audit_id:
                ready_audit_ids.add(audit_id)

    return {
        "enabled": True,
        "intent_rows": intent_rows,
        "manuscript_rows": manuscript_rows,
        "audit_rows": audit_rows,
        "intents_by_id": intents_by_id,
        "manuscripts_by_id": manuscripts_by_id,
        "audits_by_id": audits_by_id,
        "active_intent_ids": active_intent_ids,
        "active_manuscript_ids": active_manuscript_ids,
        "ready_audit_ids": ready_audit_ids,
    }, issues
