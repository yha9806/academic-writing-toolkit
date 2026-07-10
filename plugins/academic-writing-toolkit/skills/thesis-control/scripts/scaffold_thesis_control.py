#!/usr/bin/env python3
"""Scaffold a thesis-control draft packet from a real manuscript unit.

The scaffold is deliberately conservative. It creates a spine-card row and a
draft edit-contract row, but it does not mark any prose change as approved or
audited. The author still owns the scholarly judgement.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

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


SPINE_COLUMNS = [
    "unit_id",
    "manuscript_id",
    "path",
    "section_title",
    "spine_sentence",
    "scope_boundary",
    "core_claims",
    "do_not_change",
]

CONTRACT_COLUMNS = [
    "contract_id",
    "unit_id",
    "global_audit_id",
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
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9._-]{0,118}[A-Za-z0-9])?$")


def review_required(label: str) -> str:
    return f"{AUTHOR_REVIEW}: {label}"


def validate_identifier(label: str, value: str) -> None:
    if not IDENTIFIER_RE.fullmatch(value) or ".." in value:
        raise ValueError(
            f"{label} must be 1-120 ASCII letters, numbers, dots, underscores, or hyphens; "
            "it must start and end with a letter or number and must not contain '..'"
        )


def resolve_source(project_root: Path, source: str) -> Path:
    candidate = Path(source).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    return candidate.resolve()


def relative_display(path: Path, base: Path) -> str:
    try:
        return path.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def infer_unit_id(source: Path, start_line: Optional[int], end_line: Optional[int]) -> str:
    stem = re.sub(r"[^A-Za-z0-9]+", "-", source.stem).strip("-").lower() or "unit"
    if start_line is not None or end_line is not None:
        return f"{stem}-l{start_line or 1}-l{end_line or 'end'}"
    return stem


def read_excerpt(path: Path, start_line: Optional[int], end_line: Optional[int]) -> str:
    if start_line is not None and start_line < 1:
        raise ValueError("--start-line must be >= 1")
    if end_line is not None and end_line < 1:
        raise ValueError("--end-line must be >= 1")
    if start_line is not None and end_line is not None and end_line < start_line:
        raise ValueError("--end-line must be greater than or equal to --start-line")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError(f"source file is empty: {path}")
    total_lines = len(lines)
    if start_line is not None and start_line > total_lines:
        raise ValueError(f"--start-line {start_line} is beyond end of file ({total_lines} lines)")
    if end_line is not None and end_line > total_lines:
        raise ValueError(f"--end-line {end_line} is beyond end of file ({total_lines} lines)")

    start = (start_line - 1) if start_line is not None else 0
    end = end_line if end_line is not None else len(lines)
    excerpt = "\n".join(lines[start:end]).rstrip()
    if not excerpt.strip():
        raise ValueError("selected source excerpt is empty")
    return excerpt + "\n"


def infer_section_title(excerpt: str, source: Path) -> str:
    for line in excerpt.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip() or source.stem
    return source.stem.replace("_", " ").replace("-", " ").strip() or source.name


def read_owned_csv(path: Path, columns: Sequence[str]) -> List[Dict[str, str]]:
    """Read one scaffold-owned CSV without changing the project tree."""

    if not path.exists():
        return []

    fieldnames, rows = read_csv_table(path)
    missing = [column for column in columns if column not in fieldnames]
    if missing:
        raise ValueError(f"{path} missing column(s): {', '.join(missing)}")
    unsupported = [column for column in fieldnames if column not in columns]
    if unsupported:
        raise ValueError(f"{path} unsupported column(s): {', '.join(unsupported)}")
    return rows


def upsert_row_candidate(
    path: Path,
    rows: Sequence[Dict[str, str]],
    key: str,
    row: Dict[str, str],
    force: bool,
) -> Tuple[List[Dict[str, str]], str]:
    matches = sum(1 for existing in rows if existing.get(key) == row[key])
    if matches > 1:
        raise ValueError(f"{path} contains duplicate {key}={row[key]}")
    if matches == 1 and not force:
        raise ValueError(f"{path} already contains {key}={row[key]}; pass --force to replace it")

    output: List[Dict[str, str]] = []
    for existing in rows:
        if existing.get(key) == row[key]:
            output.append(row)
        else:
            output.append(existing)
    if matches == 0:
        output.append(row)
    return output, "replaced" if matches == 1 else "added"


def validate_revision_attempt(
    path: Path,
    rows: Sequence[Dict[str, str]],
    contract_id: str,
    revision_issue_id: str,
    attempt_no: int,
    force: bool,
) -> None:
    candidate_rows: List[Dict[str, str]] = []
    for row in rows:
        if row.get("contract_id", "").strip() == contract_id:
            if not force:
                raise ValueError(
                    f"{path} already contains contract_id={contract_id}; pass --force to replace it"
                )
            continue
        candidate_rows.append(row)

    candidate_rows.append(
        {
            "contract_id": contract_id,
            "revision_issue_id": revision_issue_id,
            "attempt_no": str(attempt_no),
        }
    )
    attempts_by_issue: Dict[str, List[int]] = {}
    for row in candidate_rows:
        issue_id = row.get("revision_issue_id", "").strip()
        validate_identifier("revision_issue_id", issue_id)
        attempt_text = row.get("attempt_no", "").strip()
        try:
            row_attempt = int(attempt_text)
        except ValueError as exc:
            raise ValueError(f"attempt_no must be a positive integer: {attempt_text}") from exc
        if row_attempt < 1:
            raise ValueError(f"attempt_no must be a positive integer: {attempt_text}")
        attempts_by_issue.setdefault(issue_id, []).append(row_attempt)

    for issue_id, attempts in attempts_by_issue.items():
        ordered = sorted(attempts)
        expected = list(range(1, len(ordered) + 1))
        if ordered != expected:
            raise ValueError(
                f"revision issue {issue_id} attempts must be unique and sequential from 1"
            )


def render_review_packet(
    unit_id: str,
    section_title: str,
    excerpt_path: str,
    intent_id: str,
    manuscript_id: str,
    global_audit_id: str,
    spine_row: Dict[str, str],
    contract_row: Dict[str, str],
) -> str:
    return f"""# Thesis-Control Review Packet: {unit_id}

## Unit

- Source: `{excerpt_path}`
- Section: {section_title}
- Contract: `{contract_row['contract_id']}`
- Project intent: `{intent_id}`
- Manuscript contract: `{manuscript_id}`
- Global thesis audit: `{global_audit_id}`
- Revision issue: `{contract_row['revision_issue_id']}`
- Attempt: {contract_row['attempt_no']}
- Status: draft, not approved

## Spine Card Draft

- Spine sentence: {spine_row['spine_sentence']}
- Scope boundary: {spine_row['scope_boundary']}
- Core claims: {spine_row['core_claims']}
- Do not change: {spine_row['do_not_change']}

## Edit Contract Draft

- Change scope: {contract_row['change_scope']}
- Allowed changes: {contract_row['allowed_changes']}
- Forbidden changes: {contract_row['forbidden_changes']}
- Adjacent context: {contract_row['adjacent_context']}
- Acceptance checks: {contract_row['acceptance_checks']}

## Author Gate

- Approve the project intent and manuscript contract before approving any edit contract.
- Resolve the global thesis audit as `passed` only when every alignment field is `aligned` and no reframe is detected.
- If title, abstract, primary domain, research object, research question, contribution, or structure drifts, revise or roll back the manuscript, or create an explicitly approved new intent version. Never overwrite the earlier intent row.
- Before editing prose, replace every `{AUTHOR_REVIEW}` field with a concrete judgement.
- Keep `human_approved=false` until the author explicitly approves the contract.
- After any applied edit, add a drift-audit row before accepting the prose.
- Reuse the same revision issue id and increment the attempt number when a new contract retries the same unresolved problem.
- Count an attempt as unsuccessful only after an applied contract receives a resolved `revise` or `rollback` audit with `status=failed`.
- An `early_diagnostic` escalation may record one or two warning triggers, but it never closes or pre-authorises a failure cycle.
- After three unsuccessful attempts, create a distinct `cycle_gate` that lists exactly those three trigger contracts, records the third attempt as its approval boundary, and receives explicit author approval before applying a later contract.
"""


def scaffold(args: argparse.Namespace) -> dict:
    project_root = Path(args.project_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_root
    source = resolve_source(project_root, args.source)
    if not source.is_file():
        raise FileNotFoundError(f"source file not found: {source}")

    excerpt = read_excerpt(source, args.start_line, args.end_line)
    unit_id = args.unit_id or infer_unit_id(source, args.start_line, args.end_line)
    section_title = args.section_title or infer_section_title(excerpt, source)
    attempt_no = args.attempt_no
    contract_id = args.contract_id or f"ec-{unit_id}-{attempt_no:03d}"
    revision_issue_id = args.revision_issue_id or f"ri-{contract_id}"
    validate_identifier("unit_id", unit_id)
    validate_identifier("contract_id", contract_id)
    validate_identifier("revision_issue_id", revision_issue_id)
    if attempt_no < 1:
        raise ValueError("--attempt-no must be >= 1")

    control_dir = output_dir / "thesis_control"
    intent_path = control_dir / "project_intent.csv"
    manuscript_path = control_dir / "manuscript_contracts.csv"
    global_audit_path = control_dir / "global_thesis_audits.csv"
    spine_path = control_dir / "spine_cards.csv"
    contract_path = control_dir / "edit_contracts.csv"
    audit_path = control_dir / "drift_audits.csv"
    escalation_path = control_dir / "revision_escalations.csv"
    packet_path = control_dir / f"{unit_id}_review_packet.md"

    excerpt_file: Optional[Path] = None
    if args.copy_source:
        excerpt_dir = output_dir / "source_excerpts"
        excerpt_file = excerpt_dir / f"{unit_id}.md"
    else:
        try:
            source.resolve().relative_to(output_dir)
        except ValueError as exc:
            raise ValueError("source must be inside output-dir when --copy-source is not used") from exc
        source_display = relative_display(source, output_dir)

    output_targets = [
        intent_path,
        manuscript_path,
        global_audit_path,
        spine_path,
        contract_path,
        audit_path,
        escalation_path,
        packet_path,
    ]
    if excerpt_file is not None:
        output_targets.append(excerpt_file)
    ensure_internal_paths(output_dir, output_targets)

    if excerpt_file is not None:
        if excerpt_file.exists() and not args.force:
            raise ValueError(f"{excerpt_file} already exists; pass --force to replace it")
        source_display = relative_display(excerpt_file, output_dir)

    if packet_path.exists() and not args.force:
        raise ValueError(f"{packet_path} already exists; pass --force to replace it")

    intent_rows = read_owned_csv(intent_path, PROJECT_INTENT_COLUMNS)
    manuscript_rows = read_owned_csv(manuscript_path, MANUSCRIPT_CONTRACT_COLUMNS)
    global_audit_rows = read_owned_csv(global_audit_path, GLOBAL_THESIS_AUDIT_COLUMNS)
    intent_needs_write = not intent_rows
    manuscript_needs_write = not manuscript_rows
    global_audit_needs_write = not global_audit_rows
    spine_rows = read_owned_csv(spine_path, SPINE_COLUMNS)
    contract_rows = read_owned_csv(contract_path, CONTRACT_COLUMNS)
    audit_rows = read_owned_csv(audit_path, AUDIT_COLUMNS)
    escalation_rows = read_owned_csv(escalation_path, ESCALATION_COLUMNS)
    validate_revision_attempt(
        contract_path,
        contract_rows,
        contract_id,
        revision_issue_id,
        attempt_no,
        args.force,
    )

    if not intent_rows:
        intent_id = args.intent_id or "pi-project-001"
        validate_identifier("intent_id", intent_id)
        intent_rows = [
            {
                "intent_id": intent_id,
                "intent_version": "1",
                "supersedes_intent_id": "",
                "primary_domain": review_required("Name the manuscript's primary scholarly domain."),
                "research_object": review_required("Define the object being studied or reviewed."),
                "core_research_question": review_required("State the author-approved project-level research question."),
                "target_venue": review_required("Name the intended venue or audience."),
                "must_include_concepts": review_required("List concepts that must remain visible in the title or abstract."),
                "excluded_reframes": review_required("List reframes that require a new approved intent version."),
                "amendment_reason": review_required("Record that this is the initial intent contract."),
                "approval_evidence": review_required("Record how and when the author approved this intent."),
                "human_approved": "false",
                "status": "draft",
            }
        ]
    else:
        intent_candidates = [
            row
            for row in intent_rows
            if args.intent_id
            and row.get("intent_id", "").strip() == args.intent_id
        ]
        if not args.intent_id:
            active = [row for row in intent_rows if row.get("status", "").strip().lower() == "active"]
            intent_candidates = active or [
                row for row in intent_rows if row.get("status", "").strip().lower() == "draft"
            ]
        if len(intent_candidates) != 1:
            raise ValueError("select exactly one current project intent with --intent-id")
        intent_id = intent_candidates[0].get("intent_id", "").strip()
        validate_identifier("intent_id", intent_id)

    if not manuscript_rows:
        manuscript_id = args.manuscript_id or "mc-project-001"
        validate_identifier("manuscript_id", manuscript_id)
        manuscript_rows = [
            {
                "manuscript_id": manuscript_id,
                "intent_id": intent_id,
                "manuscript_version": "1",
                "supersedes_manuscript_id": "",
                "title": review_required("Record the current manuscript title."),
                "abstract_focus": review_required("Summarise the current abstract's primary focus."),
                "primary_domain": review_required("Record the domain currently treated as primary."),
                "research_object": review_required("Record the manuscript's current research object."),
                "research_question": review_required("Record the manuscript's current research question."),
                "contribution_scope": review_required("Record the current contribution boundary."),
                "structure_summary": review_required("Summarise the manuscript's current section logic."),
                "change_summary": review_required("Record that this is the initial manuscript contract."),
                "human_approved": "false",
                "status": "draft",
            }
        ]
    else:
        manuscript_candidates = [
            row
            for row in manuscript_rows
            if args.manuscript_id
            and row.get("manuscript_id", "").strip() == args.manuscript_id
        ]
        if not args.manuscript_id:
            active = [
                row
                for row in manuscript_rows
                if row.get("status", "").strip().lower() == "active"
                and row.get("intent_id", "").strip() == intent_id
            ]
            manuscript_candidates = active or [
                row
                for row in manuscript_rows
                if row.get("status", "").strip().lower() == "draft"
                and row.get("intent_id", "").strip() == intent_id
            ]
        if len(manuscript_candidates) != 1:
            raise ValueError("select exactly one current manuscript contract with --manuscript-id")
        manuscript_id = manuscript_candidates[0].get("manuscript_id", "").strip()
        validate_identifier("manuscript_id", manuscript_id)

    manuscript_version = next(
        row.get("manuscript_version", "").strip()
        for row in manuscript_rows
        if row.get("manuscript_id", "").strip() == manuscript_id
    )
    if not global_audit_rows:
        global_audit_id = args.global_audit_id or "ga-project-001"
        validate_identifier("global_audit_id", global_audit_id)
        global_audit_rows = [
            {
                "global_audit_id": global_audit_id,
                "intent_id": intent_id,
                "manuscript_id": manuscript_id,
                "manuscript_version": manuscript_version,
                "title_alignment": "not_assessed",
                "abstract_alignment": "not_assessed",
                "primary_domain_alignment": "not_assessed",
                "research_object_alignment": "not_assessed",
                "research_question_alignment": "not_assessed",
                "contribution_alignment": "not_assessed",
                "structure_alignment": "not_assessed",
                "detected_reframe": "false",
                "reframe_summary": review_required("Compare the manuscript contract with the approved project intent."),
                "human_review_required": "true",
                "human_decision": "pending",
                "status": "needs_review",
            }
        ]
    else:
        audit_candidates = [
            row
            for row in global_audit_rows
            if args.global_audit_id
            and row.get("global_audit_id", "").strip() == args.global_audit_id
        ]
        if not args.global_audit_id:
            audit_candidates = [
                row
                for row in global_audit_rows
                if row.get("intent_id", "").strip() == intent_id
                and row.get("manuscript_id", "").strip() == manuscript_id
                and row.get("manuscript_version", "").strip() == manuscript_version
            ]
        if len(audit_candidates) != 1:
            raise ValueError("select exactly one current global thesis audit with --global-audit-id")
        global_audit_id = audit_candidates[0].get("global_audit_id", "").strip()
        validate_identifier("global_audit_id", global_audit_id)

    spine_row = {
        "unit_id": unit_id,
        "manuscript_id": manuscript_id,
        "path": source_display,
        "section_title": section_title,
        "spine_sentence": args.spine_sentence or review_required("State the one-sentence argument spine for this unit."),
        "scope_boundary": args.scope_boundary or review_required("State what this unit is allowed to claim and what belongs elsewhere."),
        "core_claims": args.core_claims or review_required("List the claims that must survive the edit."),
        "do_not_change": args.do_not_change or review_required("List caveats, citations, scope limits, and terms that must not be changed."),
    }
    contract_row = {
        "contract_id": contract_id,
        "unit_id": unit_id,
        "global_audit_id": global_audit_id,
        "revision_issue_id": revision_issue_id,
        "attempt_no": str(attempt_no),
        "change_scope": args.change_scope or review_required("Specify exact paragraphs, lines, or local issue before editing."),
        "allowed_changes": args.allowed_changes or review_required("Specify what the edit may change."),
        "forbidden_changes": args.forbidden_changes or review_required("Specify claims, evidence, caveats, and boundaries the edit must preserve."),
        "adjacent_context": args.adjacent_context or review_required("Name neighbouring paragraphs or sections that must be checked."),
        "acceptance_checks": args.acceptance_checks or review_required("Define concrete checks for accepting, revising, or rolling back the edit."),
        "human_approved": "false",
        "status": "draft",
    }

    spine_rows, spine_action = upsert_row_candidate(
        spine_path, spine_rows, "unit_id", spine_row, args.force
    )
    contract_rows, contract_action = upsert_row_candidate(
        contract_path, contract_rows, "contract_id", contract_row, args.force
    )
    review_packet = render_review_packet(
        unit_id,
        section_title,
        source_display,
        intent_id,
        manuscript_id,
        global_audit_id,
        spine_row,
        contract_row,
    )

    validation = validate_packet(
        output_dir,
        strict=True,
        table_overrides={
            "project_intent.csv": (PROJECT_INTENT_COLUMNS, intent_rows),
            "manuscript_contracts.csv": (MANUSCRIPT_CONTRACT_COLUMNS, manuscript_rows),
            "global_thesis_audits.csv": (GLOBAL_THESIS_AUDIT_COLUMNS, global_audit_rows),
            "spine_cards.csv": (SPINE_COLUMNS, spine_rows),
            "edit_contracts.csv": (CONTRACT_COLUMNS, contract_rows),
            "drift_audits.csv": (AUDIT_COLUMNS, audit_rows),
            "revision_escalations.csv": (ESCALATION_COLUMNS, escalation_rows),
        },
        prospective_files=[excerpt_file] if excerpt_file is not None else None,
    )
    if validation["issues"]:
        issue = validation["issues"][0]
        raise ValueError(
            "candidate packet is not strict-valid: "
            f"{issue['kind']} at {issue['location']}: {issue['message']}"
        )

    contents = {
        spine_path: render_csv_table(SPINE_COLUMNS, spine_rows),
        contract_path: render_csv_table(CONTRACT_COLUMNS, contract_rows),
        packet_path: review_packet.encode("utf-8"),
    }
    if intent_needs_write:
        contents[intent_path] = render_csv_table(PROJECT_INTENT_COLUMNS, intent_rows)
    if manuscript_needs_write:
        contents[manuscript_path] = render_csv_table(
            MANUSCRIPT_CONTRACT_COLUMNS, manuscript_rows
        )
    if global_audit_needs_write:
        contents[global_audit_path] = render_csv_table(
            GLOBAL_THESIS_AUDIT_COLUMNS, global_audit_rows
        )
    if not audit_path.exists():
        contents[audit_path] = render_csv_table(AUDIT_COLUMNS, audit_rows)
    if not escalation_path.exists():
        contents[escalation_path] = render_csv_table(ESCALATION_COLUMNS, escalation_rows)
    if excerpt_file is not None:
        contents[excerpt_file] = excerpt.encode("utf-8")
    atomic_write_batch(contents)

    return {
        "schema_version": 4,
        "output_dir": str(output_dir),
        "unit_id": unit_id,
        "contract_id": contract_id,
        "revision_issue_id": revision_issue_id,
        "attempt_no": attempt_no,
        "source": str(source),
        "source_recorded_as": source_display,
        "spine_cards": str(spine_path),
        "edit_contracts": str(contract_path),
        "drift_audits": str(audit_path),
        "revision_escalations": str(escalation_path),
        "project_intent": str(intent_path),
        "manuscript_contracts": str(manuscript_path),
        "global_thesis_audits": str(global_audit_path),
        "review_packet": str(packet_path),
        "actions": {
            "spine_card": spine_action,
            "edit_contract": contract_action,
            "drift_audits": "ensured-header",
            "revision_escalations": "ensured-header",
            "project_intent": "ensured-current-contract",
            "manuscript_contracts": "ensured-current-contract",
            "global_thesis_audits": "ensured-current-audit",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a draft thesis-control packet for one manuscript unit."
    )
    parser.add_argument("project_root", nargs="?", default=".", help="Project root used to resolve --source")
    parser.add_argument("--source", required=True, help="Markdown source file, absolute or relative to project_root")
    parser.add_argument("--output-dir", help="Directory where thesis_control/ should be written; defaults to project_root")
    parser.add_argument("--unit-id", help="Stable unit id; defaults to source stem plus line range")
    parser.add_argument(
        "--contract-id",
        help="Stable contract id; defaults to ec-<unit-id>-<attempt-no padded to three digits>",
    )
    parser.add_argument(
        "--revision-issue-id",
        help="Stable issue id shared by contract versions for the same unresolved problem",
    )
    parser.add_argument("--intent-id", help="Project intent id to bind this section to")
    parser.add_argument("--manuscript-id", help="Manuscript contract id to bind this section to")
    parser.add_argument("--global-audit-id", help="Global thesis audit id that must gate this edit")
    parser.add_argument("--attempt-no", type=int, default=1, help="Positive attempt number within the revision issue")
    parser.add_argument("--section-title", help="Section title; defaults to first Markdown heading in the excerpt")
    parser.add_argument("--start-line", type=int, help="1-based start line for a source excerpt")
    parser.add_argument("--end-line", type=int, help="1-based end line for a source excerpt")
    parser.add_argument("--copy-source", action="store_true", help="Copy the selected excerpt into output-dir/source_excerpts/")
    parser.add_argument("--force", action="store_true", help="Replace existing rows or review packet with the same ids")
    parser.add_argument("--json", action="store_true", dest="emit_json", help="Emit JSON output")

    parser.add_argument("--spine-sentence", help="Concrete spine sentence for the unit")
    parser.add_argument("--scope-boundary", help="Concrete scope boundary for the unit")
    parser.add_argument("--core-claims", help="Concrete core claims that must survive editing")
    parser.add_argument("--do-not-change", help="Concrete do-not-change list")
    parser.add_argument("--change-scope", help="Concrete edit scope")
    parser.add_argument("--allowed-changes", help="Concrete allowed changes")
    parser.add_argument("--forbidden-changes", help="Concrete forbidden changes")
    parser.add_argument("--adjacent-context", help="Concrete adjacent context to inspect")
    parser.add_argument("--acceptance-checks", help="Concrete checks for accepting the edit")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        payload = scaffold(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Thesis-control draft created: {payload['output_dir']}")
        print(f"- unit_id: {payload['unit_id']}")
        print(f"- contract_id: {payload['contract_id']}")
        print(f"- revision_issue_id: {payload['revision_issue_id']}")
        print(f"- attempt_no: {payload['attempt_no']}")
        print(f"- review packet: {payload['review_packet']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
