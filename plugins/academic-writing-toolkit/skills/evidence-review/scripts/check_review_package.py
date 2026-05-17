#!/usr/bin/env python3
"""Lightweight checks for an evidence-controlled review project."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


COMMON_FILES = [
    "evidence/evidence_matrix.csv",
    "evidence/claim_register.csv",
    "evidence/citation_plan.csv",
    "evidence/overclaim_risk_register.csv",
]

COMMON_DIRS = ["docs", "evidence", "reports", "summaries"]
OPTIONAL_DIRS = ["literature", "literature/reading_notes", "chapters", "outputs", "final_output"]


def read_csv(path: Path) -> tuple[bool, str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
        if reader.fieldnames is None:
            return False, "no header row"
        return True, f"{len(rows)} rows"
    except Exception as exc:
        return False, str(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".", help="review project root")
    parser.add_argument("--strict", action="store_true", help="exit 1 if expected files are missing")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    missing: list[str] = []

    print(f"Review project root: {root}")
    print("\nDirectory check:")
    for rel in COMMON_DIRS:
        path = root / rel
        status = "ok" if path.is_dir() else "missing"
        print(f"- {rel}: {status}")
        if status == "missing":
            missing.append(rel)

    print("\nOptional academic-writing workflow directories:")
    for rel in OPTIONAL_DIRS:
        status = "ok" if (root / rel).is_dir() else "not present"
        print(f"- {rel}: {status}")

    print("\nCommon file check:")
    for rel in COMMON_FILES:
        path = root / rel
        if not path.exists():
            print(f"- {rel}: missing")
            missing.append(rel)
            continue
        ok, detail = read_csv(path)
        status = "ok" if ok else "csv_error"
        print(f"- {rel}: {status} ({detail})")
        if not ok:
            missing.append(rel)

    print("\nSummary:")
    if missing:
        print(f"- warnings: {len(missing)} issue(s)")
        for item in missing:
            print(f"  - {item}")
        return 1 if args.strict else 0

    print("- no common package issues detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

