#!/usr/bin/env python3
"""Upgrade a legacy thesis-control packet to revision-tracking schema v2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


REVISION_COLUMNS = ["revision_issue_id", "attempt_no"]
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


def default_revision_issue_id(contract_id: str) -> str:
    candidate = f"ri-{contract_id}"
    if len(candidate) <= 120:
        return candidate
    digest = hashlib.sha256(contract_id.encode("utf-8")).hexdigest()[:24]
    return f"ri-{digest}"


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing edit contracts: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    if not fieldnames:
        raise ValueError(f"missing CSV header: {path}")
    if "contract_id" not in fieldnames:
        raise ValueError(f"{path} missing column: contract_id")
    return fieldnames, rows


def write_csv(path: Path, columns: Sequence[str], rows: Sequence[Dict[str, str]]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def ensure_escalation_file(path: Path) -> str:
    if not path.exists():
        write_csv(path, ESCALATION_COLUMNS, [])
        return "created"
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
    missing = [column for column in ESCALATION_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"{path} missing column(s): {', '.join(missing)}")
    return "unchanged"


def upgrade(project_root: Path) -> dict:
    control_dir = project_root / "thesis_control"
    contract_path = control_dir / "edit_contracts.csv"
    escalation_path = control_dir / "revision_escalations.csv"
    fieldnames, rows = read_csv(contract_path)

    output_columns = list(fieldnames)
    insertion_point = output_columns.index("unit_id") + 1 if "unit_id" in output_columns else 1
    for column in reversed(REVISION_COLUMNS):
        if column not in output_columns:
            output_columns.insert(insertion_point, column)

    upgraded = 0
    for row in rows:
        contract_id = row.get("contract_id", "").strip()
        if not contract_id:
            raise ValueError("cannot upgrade a contract row without contract_id")
        changed = False
        if not row.get("revision_issue_id", "").strip():
            row["revision_issue_id"] = default_revision_issue_id(contract_id)
            changed = True
        if not row.get("attempt_no", "").strip():
            row["attempt_no"] = "1"
            changed = True
        if changed:
            upgraded += 1

    write_csv(contract_path, output_columns, rows)
    escalation_action = ensure_escalation_file(escalation_path)
    return {
        "schema_version": 2,
        "project_root": str(project_root),
        "edit_contracts": str(contract_path),
        "revision_escalations": str(escalation_path),
        "contracts_upgraded": upgraded,
        "escalation_file": escalation_action,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Add revision issue identity and escalation records to a legacy thesis-control packet."
    )
    parser.add_argument("project_root", nargs="?", default=".", help="Packet root containing thesis_control/")
    parser.add_argument("--json", action="store_true", dest="emit_json", help="Emit JSON output")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        payload = upgrade(Path(args.project_root).expanduser().resolve())
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"Thesis-control revision tracking upgraded: {payload['project_root']}")
        print(f"- contracts upgraded: {payload['contracts_upgraded']}")
        print(f"- escalation file: {payload['escalation_file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
