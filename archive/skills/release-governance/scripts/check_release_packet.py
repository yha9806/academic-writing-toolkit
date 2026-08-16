#!/usr/bin/env python3
"""Lightweight validation for release-governance packets."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ALLOWED_EVIDENCE_STATES = {"draft_advisory", "verified_artifact", "human_final"}

REQUIRED_FILES: Dict[str, Sequence[str]] = {
    "release/release_scope.md": (),
    "release/canonical_refs.csv": ("ref_name", "sha", "date", "status", "canonical_for", "caveat"),
    "release/local_asset_inventory.csv": ("path", "status", "file_count", "size", "role", "release_action"),
    "release/artifact_anchors.csv": (
        "artifact_id",
        "source_ref",
        "source_path",
        "count_or_checksum",
        "evidence_state",
        "verified_by",
        "claim_supported",
    ),
    "release/evidence_gates.csv": (
        "gate_id",
        "artifact_id",
        "evidence_state",
        "human_confirmed",
        "reviewer",
        "review_date",
        "validator",
        "status",
    ),
    "release/claim_ledger.csv": (
        "claim_id",
        "claim_text",
        "artifact_ids",
        "evidence_state",
        "denominator",
        "scope_boundary",
        "human_gate_required",
        "status",
    ),
    "release/verification_report.md": (),
}

TEXT_EXTENSIONS = {".csv", ".json", ".md", ".txt", ".yaml", ".yml"}
STRUCTURED_EXTENSIONS = {".csv", ".json", ".yaml", ".yml"}

UNRESOLVED_CJK_MARKERS = "|".join((chr(0x5F85) + chr(0x8865), chr(0x5F85) + chr(0x5B9A)))
MARKER_RE = re.compile(
    r"\b(to\s*do|tbd|fix\s*me|xxx|replace me|fill in|pending update|placeholder|path/to|sample only)\b|"
    + UNRESOLVED_CJK_MARKERS,
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(
    r"(^|[\s'\"(,;:])((/[Uu]sers|/[Hh]ome|/[Pp]rivate|/[Tt]mp|/[Vv]ar/[Ff]olders)(/|\b)|[A-Za-z]:\\)"
)


def issue(kind: str, path: str, detail: str, line: Optional[int] = None) -> Dict[str, object]:
    item: Dict[str, object] = {"kind": kind, "path": path, "detail": detail}
    if line is not None:
        item["line"] = line
    return item


def iter_packet_files(root: Path) -> Iterable[Path]:
    release_dir = root / "release"
    if not release_dir.is_dir():
        return []
    return (path for path in sorted(release_dir.rglob("*")) if path.is_file())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def check_text(path: Path, rel: str) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return issues
    try:
        text = read_text(path)
    except UnicodeDecodeError as exc:
        return [issue("decode-error", rel, str(exc))]
    for line_no, line in enumerate(text.splitlines(), start=1):
        if MARKER_RE.search(line):
            issues.append(issue("placeholder-text", rel, "remove unresolved template marker or working note", line_no))
        if LOCAL_PATH_RE.search(line):
            issues.append(issue("local-absolute-path", rel, "replace local absolute path with a relative path or external artifact identifier", line_no))
    return issues


def read_csv(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    if reader.fieldnames is None:
        raise ValueError("no header row")
    return list(reader.fieldnames), rows


def parse_yaml_fallback(text: str) -> None:
    stack = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            stack.append(line)
            continue
        if ":" not in line:
            raise ValueError("line is not a simple yaml mapping or list item")


def parse_structured(path: Path) -> None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        read_csv(path)
    elif suffix == ".json":
        json.loads(read_text(path))
    elif suffix in {".yaml", ".yml"}:
        text = read_text(path)
        try:
            import yaml  # type: ignore
        except Exception:
            parse_yaml_fallback(text)
        else:
            yaml.safe_load(text)


def check_required_file(root: Path, rel: str, columns: Sequence[str]) -> List[Dict[str, object]]:
    path = root / rel
    if not path.exists():
        return [issue("missing-file", rel, "required release packet file is missing")]
    if not path.is_file():
        return [issue("not-file", rel, "required path is not a file")]
    if path.suffix.lower() != ".csv":
        return []
    try:
        fieldnames, rows = read_csv(path)
    except Exception as exc:
        return [issue("csv-parse-error", rel, str(exc))]
    missing = [column for column in columns if column not in fieldnames]
    issues: List[Dict[str, object]] = []
    if missing:
        issues.append(issue("missing-columns", rel, ", ".join(missing)))
    issues.extend(check_evidence_states(rel, rows))
    issues.extend(check_human_final_gate(rel, rows))
    return issues


def check_evidence_states(rel: str, rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    for index, row in enumerate(rows, start=2):
        value = (row.get("evidence_state") or "").strip()
        if value and value not in ALLOWED_EVIDENCE_STATES:
            issues.append(issue("invalid-evidence-state", rel, value, index))
    return issues


def truthy(value: str) -> bool:
    return value.strip().lower() in {"true", "yes", "y", "1", "confirmed", "passed"}


def check_human_final_gate(rel: str, rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    for index, row in enumerate(rows, start=2):
        if (row.get("evidence_state") or "").strip() != "human_final":
            continue
        if "human_confirmed" in row and not truthy(row.get("human_confirmed", "")):
            issues.append(issue("human-final-gate-missing", rel, "human_final row needs human_confirmed=true", index))
        if "reviewer" in row and not row.get("reviewer", "").strip():
            issues.append(issue("human-final-gate-missing", rel, "human_final row needs reviewer", index))
        if "review_date" in row and not row.get("review_date", "").strip():
            issues.append(issue("human-final-gate-missing", rel, "human_final row needs review_date", index))
    return issues


def validate(root: Path) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    release_dir = root / "release"
    if not release_dir.is_dir():
        issues.append(issue("missing-directory", "release", "release packet directory is missing"))

    for rel, columns in REQUIRED_FILES.items():
        issues.extend(check_required_file(root, rel, columns))

    for path in iter_packet_files(root):
        rel = path.relative_to(root).as_posix()
        issues.extend(check_text(path, rel))
        if path.suffix.lower() in STRUCTURED_EXTENSIONS:
            try:
                parse_structured(path)
            except Exception as exc:
                issues.append(issue("parse-error", rel, str(exc)))
    return issues


def emit_text(root: Path, issues: List[Dict[str, object]]) -> None:
    print("Release packet root: {}".format(root))
    if not issues:
        print("- no release packet issues detected")
        return
    print("- issues: {}".format(len(issues)))
    for item in issues:
        location = item["path"]
        if "line" in item:
            location = "{}:{}".format(location, item["line"])
        print("- {kind}: {location}: {detail}".format(location=location, **item))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a release-governance packet.")
    parser.add_argument("root", nargs="?", default=".", help="project root containing release/")
    parser.add_argument("--json", action="store_true", dest="emit_json", help="emit machine-readable output")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write("error: root is not a directory\n")
        return 2

    issues = validate(root)
    payload = {
        "schema_version": 1,
        "root": str(root),
        "issues": issues,
        "issue_count": len(issues),
        "allowed_evidence_states": sorted(ALLOWED_EVIDENCE_STATES),
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        emit_text(root, issues)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
