#!/usr/bin/env python3
"""Upgrade a schema-v3 thesis-control packet to a blocked schema-v4 draft.

The helper never infers or approves scholarly intent. It adds the project-level
link columns and creates AUTHOR_REVIEW_REQUIRED draft objects atomically. Any
previously approved or applied edit remains blocked until the author completes
and approves the new layer.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from check_thesis_control import validate_packet
from project_intent_control import (
    GLOBAL_THESIS_AUDIT_COLUMNS,
    MANUSCRIPT_CONTRACT_COLUMNS,
    PROJECT_INTENT_COLUMNS,
)
from thesis_control_io import (
    atomic_write_batch,
    ensure_internal_paths,
    read_csv_table,
    render_csv_table,
)


SPINE_BASE_COLUMNS = [
    "unit_id",
    "path",
    "section_title",
    "spine_sentence",
    "scope_boundary",
    "core_claims",
    "do_not_change",
]
CONTRACT_BASE_COLUMNS = [
    "contract_id",
    "unit_id",
    "revision_issue_id",
    "attempt_no",
    "change_scope",
    "allowed_changes",
    "forbidden_changes",
    "adjacent_context",
    "acceptance_checks",
    "human_approved",
    "status",
]
AUDIT_COLUMNS = [
    "audit_id",
    "contract_id",
    "changed_claims",
    "changed_boundaries",
    "new_unsupported_claims",
    "missed_adjacent_updates",
    "drift_decision",
    "human_review_required",
    "status",
]
ESCALATION_COLUMNS = [
    "escalation_id",
    "revision_issue_id",
    "escalation_kind",
    "trigger_contracts",
    "approved_after_attempt",
    "primary_category",
    "writing_scope",
    "valid_requirements",
    "missing_or_conflicting_information",
    "latest_author_approved_version",
    "recommended_next_action",
    "human_approved",
    "status",
]
AUTHOR_REVIEW = "AUTHOR_REVIEW_REQUIRED"
ALLOWED_BLOCKING_ISSUES = {
    "global-thesis-gate-required",
    "active-project-intent-required",
    "active-manuscript-contract-required",
}


def review_required(label: str) -> str:
    return f"{AUTHOR_REVIEW}: {label}"


def read_required(path: Path, required: Sequence[str]) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing required control file: {path}")
    fieldnames, rows = read_csv_table(path)
    missing = [column for column in required if column not in fieldnames]
    if missing:
        raise ValueError(f"{path} missing column(s): {', '.join(missing)}")
    return fieldnames, rows


def insert_after(columns: Sequence[str], anchor: str, column: str) -> List[str]:
    output = list(columns)
    output.insert(output.index(anchor) + 1, column)
    return output


def upgrade(project_root: Path) -> dict:
    control_dir = project_root / "thesis_control"
    intent_path = control_dir / "project_intent.csv"
    manuscript_path = control_dir / "manuscript_contracts.csv"
    global_audit_path = control_dir / "global_thesis_audits.csv"
    spine_path = control_dir / "spine_cards.csv"
    contract_path = control_dir / "edit_contracts.csv"
    audit_path = control_dir / "drift_audits.csv"
    escalation_path = control_dir / "revision_escalations.csv"
    targets = [
        intent_path,
        manuscript_path,
        global_audit_path,
        spine_path,
        contract_path,
        audit_path,
        escalation_path,
    ]
    ensure_internal_paths(project_root, targets)

    spine_columns, spine_rows = read_required(spine_path, SPINE_BASE_COLUMNS)
    contract_columns, contract_rows = read_required(contract_path, CONTRACT_BASE_COLUMNS)
    audit_columns, audit_rows = read_required(audit_path, AUDIT_COLUMNS)
    escalation_columns, escalation_rows = read_required(escalation_path, ESCALATION_COLUMNS)

    new_files = [intent_path, manuscript_path, global_audit_path]
    file_presence = [path.exists() for path in new_files]
    has_spine_link = "manuscript_id" in spine_columns
    has_contract_link = "global_audit_id" in contract_columns
    if all(file_presence) and has_spine_link and has_contract_link:
        return {
            "schema_version": 4,
            "status": "unchanged",
            "author_action_required": True,
            "message": "project-intent layer already exists; validate and resolve its current author gates",
        }
    if any(file_presence) or has_spine_link or has_contract_link:
        raise ValueError(
            "partial project-intent schema detected; no files were changed and an author decision is required"
        )

    manuscript_id = "mc-project-001"
    global_audit_id = "ga-project-001"
    intent_id = "pi-project-001"
    output_spine_columns = insert_after(spine_columns, "unit_id", "manuscript_id")
    output_contract_columns = insert_after(contract_columns, "unit_id", "global_audit_id")
    output_spine_rows = []
    for row in spine_rows:
        output = dict(row)
        output["manuscript_id"] = manuscript_id
        output_spine_rows.append(output)
    output_contract_rows = []
    for row in contract_rows:
        output = dict(row)
        output["global_audit_id"] = global_audit_id
        output_contract_rows.append(output)

    intent_rows = [
        {
            "intent_id": intent_id,
            "intent_version": "1",
            "supersedes_intent_id": "",
            "primary_domain": review_required("Name the manuscript's primary scholarly domain."),
            "research_object": review_required("Define the project-level research object."),
            "core_research_question": review_required("State the author-approved research question."),
            "target_venue": review_required("Name the target venue or audience."),
            "must_include_concepts": review_required("List concepts that must remain visible."),
            "excluded_reframes": review_required("List reframes that need a new approved intent version."),
            "amendment_reason": review_required("Record that this is the initial intent contract."),
            "approval_evidence": review_required("Record explicit author approval."),
            "human_approved": "false",
            "status": "draft",
        }
    ]
    manuscript_rows = [
        {
            "manuscript_id": manuscript_id,
            "intent_id": intent_id,
            "manuscript_version": "1",
            "supersedes_manuscript_id": "",
            "title": review_required("Record the current manuscript title."),
            "abstract_focus": review_required("Summarise the current abstract focus."),
            "primary_domain": review_required("Record the domain currently treated as primary."),
            "research_object": review_required("Record the current research object."),
            "research_question": review_required("Record the current research question."),
            "contribution_scope": review_required("Record the current contribution boundary."),
            "structure_summary": review_required("Summarise the current manuscript structure."),
            "change_summary": review_required("Record that this is the initial manuscript contract."),
            "human_approved": "false",
            "status": "draft",
        }
    ]
    global_audit_rows = [
        {
            "global_audit_id": global_audit_id,
            "intent_id": intent_id,
            "manuscript_id": manuscript_id,
            "manuscript_version": "1",
            "title_alignment": "not_assessed",
            "abstract_alignment": "not_assessed",
            "primary_domain_alignment": "not_assessed",
            "research_object_alignment": "not_assessed",
            "research_question_alignment": "not_assessed",
            "contribution_alignment": "not_assessed",
            "structure_alignment": "not_assessed",
            "detected_reframe": "false",
            "reframe_summary": review_required("Compare the current manuscript with the project intent."),
            "human_review_required": "true",
            "human_decision": "pending",
            "status": "needs_review",
        }
    ]

    candidate = validate_packet(
        project_root,
        strict=False,
        table_overrides={
            "project_intent.csv": (PROJECT_INTENT_COLUMNS, intent_rows),
            "manuscript_contracts.csv": (MANUSCRIPT_CONTRACT_COLUMNS, manuscript_rows),
            "global_thesis_audits.csv": (GLOBAL_THESIS_AUDIT_COLUMNS, global_audit_rows),
            "spine_cards.csv": (output_spine_columns, output_spine_rows),
            "edit_contracts.csv": (output_contract_columns, output_contract_rows),
            "drift_audits.csv": (audit_columns, audit_rows),
            "revision_escalations.csv": (escalation_columns, escalation_rows),
        },
    )
    unexpected = [
        issue for issue in candidate["issues"] if issue["kind"] not in ALLOWED_BLOCKING_ISSUES
    ]
    if unexpected:
        issue = unexpected[0]
        raise ValueError(
            "candidate packet has a pre-existing or unrelated issue: "
            f"{issue['kind']} at {issue['location']}: {issue['message']}"
        )

    atomic_write_batch(
        {
            intent_path: render_csv_table(PROJECT_INTENT_COLUMNS, intent_rows),
            manuscript_path: render_csv_table(MANUSCRIPT_CONTRACT_COLUMNS, manuscript_rows),
            global_audit_path: render_csv_table(GLOBAL_THESIS_AUDIT_COLUMNS, global_audit_rows),
            spine_path: render_csv_table(output_spine_columns, output_spine_rows),
            contract_path: render_csv_table(output_contract_columns, output_contract_rows),
        }
    )
    return {
        "schema_version": 4,
        "status": "upgraded_blocked",
        "author_action_required": True,
        "project_intent": str(intent_path),
        "manuscript_contracts": str(manuscript_path),
        "global_thesis_audits": str(global_audit_path),
        "blocking_issue_count": len(candidate["issues"]),
        "blocking_issue_kinds": sorted({issue["kind"] for issue in candidate["issues"]}),
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Upgrade a schema-v3 thesis-control packet to a blocked schema-v4 project-intent draft."
    )
    parser.add_argument("project_root", nargs="?", default=".")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        payload = upgrade(Path(args.project_root).expanduser().resolve())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Project-intent upgrade: {payload['status']}")
        print("- author action required before approved or applied edits can pass strict validation")
    return 0


if __name__ == "__main__":
    sys.exit(main())
