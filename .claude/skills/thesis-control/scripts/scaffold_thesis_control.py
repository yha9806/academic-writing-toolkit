#!/usr/bin/env python3
"""Scaffold a thesis-control draft packet from a real manuscript unit.

The scaffold is deliberately conservative. It creates a spine-card row and a
draft edit-contract row, but it does not mark any prose change as approved or
audited. The author still owns the scholarly judgement.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


SPINE_COLUMNS = [
    "unit_id",
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

AUTHOR_REVIEW = "AUTHOR_REVIEW_REQUIRED"


def review_required(label: str) -> str:
    return f"{AUTHOR_REVIEW}: {label}"


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


def ensure_csv(path: Path, columns: Sequence[str]) -> List[Dict[str, str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(columns))
            writer.writeheader()
        return []

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in columns if column not in fieldnames]
        if missing:
            raise ValueError(f"{path} missing column(s): {', '.join(missing)}")
        return list(reader)


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)


def upsert_row(
    path: Path,
    columns: Sequence[str],
    key: str,
    row: Dict[str, str],
    force: bool,
) -> str:
    rows = ensure_csv(path, columns)
    found = False
    output: List[Dict[str, str]] = []
    for existing in rows:
        if existing.get(key) == row[key]:
            if not force:
                raise ValueError(f"{path} already contains {key}={row[key]}; pass --force to replace it")
            output.append(row)
            found = True
        else:
            output.append(existing)
    if not found:
        output.append(row)
    write_csv(path, columns, output)
    return "replaced" if found else "added"


def write_review_packet(
    output_dir: Path,
    unit_id: str,
    section_title: str,
    excerpt_path: str,
    spine_row: Dict[str, str],
    contract_row: Dict[str, str],
    force: bool,
) -> Path:
    packet_path = output_dir / "thesis_control" / f"{unit_id}_review_packet.md"
    if packet_path.exists() and not force:
        raise ValueError(f"{packet_path} already exists; pass --force to replace it")

    body = f"""# Thesis-Control Review Packet: {unit_id}

## Unit

- Source: `{excerpt_path}`
- Section: {section_title}
- Contract: `{contract_row['contract_id']}`
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

- Before editing prose, replace every `{AUTHOR_REVIEW}` field with a concrete judgement.
- Keep `human_approved=false` until the author explicitly approves the contract.
- After any applied edit, add a drift-audit row before accepting the prose.
"""
    packet_path.write_text(body, encoding="utf-8")
    return packet_path


def scaffold(args: argparse.Namespace) -> dict:
    project_root = Path(args.project_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else project_root
    source = resolve_source(project_root, args.source)
    if not source.is_file():
        raise FileNotFoundError(f"source file not found: {source}")

    excerpt = read_excerpt(source, args.start_line, args.end_line)
    unit_id = args.unit_id or infer_unit_id(source, args.start_line, args.end_line)
    section_title = args.section_title or infer_section_title(excerpt, source)
    contract_id = args.contract_id or f"ec-{unit_id}-001"

    if args.copy_source:
        excerpt_dir = output_dir / "source_excerpts"
        excerpt_dir.mkdir(parents=True, exist_ok=True)
        excerpt_file = excerpt_dir / f"{unit_id}.md"
        if excerpt_file.exists() and not args.force:
            raise ValueError(f"{excerpt_file} already exists; pass --force to replace it")
        excerpt_file.write_text(excerpt, encoding="utf-8")
        source_display = relative_display(excerpt_file, output_dir)
    else:
        source_display = relative_display(source, project_root)

    control_dir = output_dir / "thesis_control"
    spine_path = control_dir / "spine_cards.csv"
    contract_path = control_dir / "edit_contracts.csv"
    audit_path = control_dir / "drift_audits.csv"

    ensure_csv(audit_path, AUDIT_COLUMNS)

    spine_row = {
        "unit_id": unit_id,
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
        "change_scope": args.change_scope or review_required("Specify exact paragraphs, lines, or local issue before editing."),
        "allowed_changes": args.allowed_changes or review_required("Specify what the edit may change."),
        "forbidden_changes": args.forbidden_changes or review_required("Specify claims, evidence, caveats, and boundaries the edit must preserve."),
        "adjacent_context": args.adjacent_context or review_required("Name neighbouring paragraphs or sections that must be checked."),
        "acceptance_checks": args.acceptance_checks or review_required("Define concrete checks for accepting, revising, or rolling back the edit."),
        "human_approved": "false",
        "status": "draft",
    }

    spine_action = upsert_row(spine_path, SPINE_COLUMNS, "unit_id", spine_row, args.force)
    contract_action = upsert_row(contract_path, CONTRACT_COLUMNS, "contract_id", contract_row, args.force)
    packet_path = write_review_packet(
        output_dir,
        unit_id,
        section_title,
        source_display,
        spine_row,
        contract_row,
        args.force,
    )

    return {
        "schema_version": 1,
        "output_dir": str(output_dir),
        "unit_id": unit_id,
        "contract_id": contract_id,
        "source": str(source),
        "source_recorded_as": source_display,
        "spine_cards": str(spine_path),
        "edit_contracts": str(contract_path),
        "drift_audits": str(audit_path),
        "review_packet": str(packet_path),
        "actions": {
            "spine_card": spine_action,
            "edit_contract": contract_action,
            "drift_audits": "ensured-header",
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
    parser.add_argument("--contract-id", help="Stable contract id; defaults to ec-<unit-id>-001")
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
        print(f"- review packet: {payload['review_packet']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
