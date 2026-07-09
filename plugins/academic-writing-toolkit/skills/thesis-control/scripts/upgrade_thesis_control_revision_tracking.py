#!/usr/bin/env python3
"""Upgrade a complete thesis-control packet to revision-tracking schema v3."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from check_thesis_control import is_valid_identifier, validate_packet
from thesis_control_io import (
    atomic_write_batch,
    ensure_internal_paths,
    read_csv_table,
    render_csv_table,
)


REVISION_COLUMNS = ["revision_issue_id", "attempt_no"]
ESCALATION_V2_COLUMNS = [
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
ESCALATION_V3_COLUMNS = [
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


def read_required_csv(path: Path, label: str) -> Tuple[List[str], List[Dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    return read_csv_table(path)


def require_columns(path: Path, fieldnames: Sequence[str], required: Sequence[str]) -> None:
    missing = [column for column in required if column not in fieldnames]
    if missing:
        raise ValueError(f"{path} missing column(s): {', '.join(missing)}")


def prepare_contracts(
    path: Path,
    fieldnames: Sequence[str],
    input_rows: Sequence[Dict[str, str]],
) -> Tuple[List[str], List[Dict[str, str]], int, bool]:
    require_columns(path, fieldnames, ["contract_id"])
    has_issue = "revision_issue_id" in fieldnames
    has_attempt = "attempt_no" in fieldnames
    if has_issue != has_attempt:
        raise ValueError(
            f"{path} has a partial revision schema; an author decision is required "
            "to establish historical issue grouping and attempt order"
        )

    rows = [dict(row) for row in input_rows]
    output_columns = list(fieldnames)
    legacy = not has_issue
    if legacy:
        insertion_point = (
            output_columns.index("unit_id") + 1 if "unit_id" in output_columns else 1
        )
        for column in reversed(REVISION_COLUMNS):
            output_columns.insert(insertion_point, column)

    contract_ids = set()
    attempts_by_issue: Dict[str, List[int]] = {}
    for row in rows:
        contract_id = row.get("contract_id", "").strip()
        if not contract_id:
            raise ValueError("cannot upgrade a contract row without contract_id")
        if contract_id in contract_ids:
            raise ValueError(f"duplicate contract_id requires an author decision: {contract_id}")
        contract_ids.add(contract_id)

        if legacy:
            row["revision_issue_id"] = default_revision_issue_id(contract_id)
            row["attempt_no"] = "1"
        else:
            revision_issue_id = row.get("revision_issue_id", "").strip()
            attempt_text = row.get("attempt_no", "").strip()
            if not revision_issue_id or not attempt_text:
                raise ValueError(
                    f"contract {contract_id} has partial revision values; an author decision "
                    "is required to establish historical issue grouping and attempt order"
                )

        revision_issue_id = row.get("revision_issue_id", "").strip()
        if not is_valid_identifier(revision_issue_id):
            raise ValueError(
                f"contract {contract_id} has an unsafe revision_issue_id: {revision_issue_id}"
            )
        attempt_text = row.get("attempt_no", "").strip()
        try:
            attempt_no = int(attempt_text)
        except ValueError as exc:
            raise ValueError(
                f"contract {contract_id} attempt_no must be a positive integer: {attempt_text}"
            ) from exc
        if attempt_no < 1:
            raise ValueError(
                f"contract {contract_id} attempt_no must be a positive integer: {attempt_text}"
            )
        attempts_by_issue.setdefault(revision_issue_id, []).append(attempt_no)

    for revision_issue_id, attempts in attempts_by_issue.items():
        ordered = sorted(attempts)
        expected = list(range(1, len(ordered) + 1))
        if ordered != expected:
            raise ValueError(
                f"revision issue {revision_issue_id} attempts are missing, duplicate, or "
                "non-sequential; an author decision is required"
            )

    return output_columns, rows, len(rows) if legacy else 0, legacy


def completed_failure_groups(
    contract_rows: Sequence[Dict[str, str]],
    audit_rows: Sequence[Dict[str, str]],
) -> Dict[str, List[Tuple[set, int, List[str]]]]:
    contracts: Dict[str, Tuple[str, int, str]] = {}
    for row in contract_rows:
        contract_id = row.get("contract_id", "").strip()
        contracts[contract_id] = (
            row.get("revision_issue_id", "").strip(),
            int(row.get("attempt_no", "").strip()),
            row.get("status", "").strip().lower(),
        )

    unsuccessful = set()
    for row in audit_rows:
        contract_id = row.get("contract_id", "").strip()
        decision = row.get("drift_decision", "").strip().lower()
        status = row.get("status", "").strip().lower()
        contract = contracts.get(contract_id)
        if (
            contract is not None
            and contract[2] == "applied"
            and decision in {"revise", "rollback"}
            and status == "failed"
        ):
            unsuccessful.add(contract_id)

    ordered_by_issue: Dict[str, List[Tuple[int, str]]] = {}
    for contract_id in unsuccessful:
        revision_issue_id, attempt_no, _ = contracts[contract_id]
        ordered_by_issue.setdefault(revision_issue_id, []).append((attempt_no, contract_id))

    groups: Dict[str, List[Tuple[set, int, List[str]]]] = {}
    for revision_issue_id, attempts in ordered_by_issue.items():
        ordered = sorted(attempts)
        for start in range(0, (len(ordered) // 3) * 3, 3):
            group = ordered[start : start + 3]
            groups.setdefault(revision_issue_id, []).append(
                (
                    {contract_id for _, contract_id in group},
                    max(attempt for attempt, _ in group),
                    [contract_id for _, contract_id in group],
                )
            )
    return groups


def classify_v2_escalation(
    path: Path,
    row: Dict[str, str],
    contracts: Dict[str, Tuple[str, int]],
    failure_groups: Dict[str, List[Tuple[set, int, List[str]]]],
) -> None:
    escalation_id = row.get("escalation_id", "").strip() or "<missing>"
    revision_issue_id = row.get("revision_issue_id", "").strip()
    triggers = [
        value.strip()
        for value in row.get("trigger_contracts", "").split(";")
        if value.strip()
    ]
    trigger_set = set(triggers)
    prefix = f"{path} escalation {escalation_id} has ambiguous v2 data:"

    if not triggers or len(triggers) != len(trigger_set):
        raise ValueError(f"{prefix} trigger contracts must be non-empty and unique")
    if len(triggers) > 3:
        raise ValueError(f"{prefix} oversized trigger sets cannot be classified")
    if revision_issue_id not in {value[0] for value in contracts.values()}:
        raise ValueError(f"{prefix} unknown revision_issue_id {revision_issue_id}")
    for trigger in triggers:
        contract = contracts.get(trigger)
        if contract is None:
            raise ValueError(f"{prefix} unknown trigger contract {trigger}")
        if contract[0] != revision_issue_id:
            raise ValueError(f"{prefix} trigger contracts cross revision issues")

    if len(triggers) <= 2:
        row["escalation_kind"] = "early_diagnostic"
        row["approved_after_attempt"] = ""
        return

    matching_group = next(
        (
            (group, boundary, ordered)
            for group, boundary, ordered in failure_groups.get(revision_issue_id, [])
            if group == trigger_set
        ),
        None,
    )
    if matching_group is None:
        raise ValueError(
            f"{prefix} three triggers do not match one completed unsuccessful group"
        )
    row["escalation_kind"] = "cycle_gate"
    row["approved_after_attempt"] = str(matching_group[1])
    row["trigger_contracts"] = ";".join(matching_group[2])


def prepare_escalations(
    path: Path,
    contract_rows: Sequence[Dict[str, str]],
    audit_rows: Sequence[Dict[str, str]],
) -> Tuple[List[str], List[Dict[str, str]], str, bool]:
    if not path.exists():
        return list(ESCALATION_V3_COLUMNS), [], "created", True
    if not path.is_file():
        raise FileNotFoundError(f"revision escalation target is not a file: {path}")

    fieldnames, input_rows = read_csv_table(path)
    has_kind = "escalation_kind" in fieldnames
    has_boundary = "approved_after_attempt" in fieldnames
    if has_kind != has_boundary:
        raise ValueError(
            f"{path} has a partial escalation schema; an author decision is required"
        )

    if has_kind:
        require_columns(path, fieldnames, ESCALATION_V3_COLUMNS)
        return list(fieldnames), [dict(row) for row in input_rows], "unchanged", False

    require_columns(path, fieldnames, ESCALATION_V2_COLUMNS)
    output_columns = list(fieldnames)
    trigger_index = output_columns.index("trigger_contracts")
    output_columns.insert(trigger_index, "escalation_kind")
    trigger_index = output_columns.index("trigger_contracts")
    output_columns.insert(trigger_index + 1, "approved_after_attempt")

    rows = [dict(row) for row in input_rows]
    contracts = {
        row.get("contract_id", "").strip(): (
            row.get("revision_issue_id", "").strip(),
            int(row.get("attempt_no", "").strip()),
        )
        for row in contract_rows
    }
    failure_groups = completed_failure_groups(contract_rows, audit_rows)
    for row in rows:
        classify_v2_escalation(path, row, contracts, failure_groups)
    return output_columns, rows, "upgraded", True


def validate_candidate(
    project_root: Path,
    spine_table: Tuple[Sequence[str], Sequence[Dict[str, str]]],
    contract_table: Tuple[Sequence[str], Sequence[Dict[str, str]]],
    audit_table: Tuple[Sequence[str], Sequence[Dict[str, str]]],
    escalation_table: Tuple[Sequence[str], Sequence[Dict[str, str]]],
) -> None:
    payload = validate_packet(
        project_root,
        strict=True,
        table_overrides={
            "spine_cards.csv": spine_table,
            "edit_contracts.csv": contract_table,
            "drift_audits.csv": audit_table,
            "revision_escalations.csv": escalation_table,
        },
    )
    if payload["issues"]:
        issue = payload["issues"][0]
        raise ValueError(
            "candidate packet is not strict-valid: "
            f"{issue['kind']} at {issue['location']}: {issue['message']}"
        )


def upgrade(project_root: Path) -> dict:
    control_dir = project_root / "thesis_control"
    spine_path = control_dir / "spine_cards.csv"
    contract_path = control_dir / "edit_contracts.csv"
    audit_path = control_dir / "drift_audits.csv"
    escalation_path = control_dir / "revision_escalations.csv"

    ensure_internal_paths(
        project_root,
        [spine_path, contract_path, audit_path, escalation_path],
    )

    contract_fields, contract_input_rows = read_required_csv(
        contract_path, "edit contracts"
    )
    contract_columns, contract_rows, upgraded, contract_changed = prepare_contracts(
        contract_path, contract_fields, contract_input_rows
    )

    spine_fields, spine_rows = read_required_csv(spine_path, "spine cards")
    audit_fields, audit_rows = read_required_csv(audit_path, "drift audits")
    (
        escalation_columns,
        escalation_rows,
        escalation_action,
        escalation_changed,
    ) = prepare_escalations(escalation_path, contract_rows, audit_rows)

    validate_candidate(
        project_root,
        (spine_fields, spine_rows),
        (contract_columns, contract_rows),
        (audit_fields, audit_rows),
        (escalation_columns, escalation_rows),
    )

    contents = {}
    if contract_changed:
        contents[contract_path] = render_csv_table(contract_columns, contract_rows)
    if escalation_changed:
        contents[escalation_path] = render_csv_table(escalation_columns, escalation_rows)
    atomic_write_batch(contents)

    return {
        "schema_version": 3,
        "project_root": str(project_root),
        "edit_contracts": str(contract_path),
        "revision_escalations": str(escalation_path),
        "contracts_upgraded": upgraded,
        "escalation_file": escalation_action,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Upgrade a complete thesis-control packet to strict revision schema v3."
    )
    parser.add_argument(
        "project_root", nargs="?", default=".", help="Packet root containing thesis_control/"
    )
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
