#!/usr/bin/env python3
"""Shared strict CSV and atomic file I/O for thesis-control scripts."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple


class CsvShapeError(ValueError):
    """A structural CSV error with a stable issue kind and location."""

    def __init__(self, kind: str, location: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind
        self.location = location
        self.message = message


def read_csv_table(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    """Read a CSV only when its header is unique and every row has full width."""

    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                fieldnames = next(reader)
            except StopIteration as exc:
                raise CsvShapeError("missing-header", str(path), "missing header row") from exc

            if not fieldnames:
                raise CsvShapeError("missing-header", str(path), "missing header row")

            empty_columns = [index + 1 for index, name in enumerate(fieldnames) if not name.strip()]
            if empty_columns:
                positions = ", ".join(str(position) for position in empty_columns)
                raise CsvShapeError(
                    "empty-column",
                    str(path),
                    f"header contains empty column name(s) at position(s): {positions}",
                )

            duplicates = sorted(name for name, count in Counter(fieldnames).items() if count > 1)
            if duplicates:
                raise CsvShapeError(
                    "duplicate-column",
                    str(path),
                    f"header contains duplicate column(s): {', '.join(duplicates)}",
                )

            rows: List[Dict[str, str]] = []
            for row_number, values in enumerate(reader, start=2):
                if len(values) != len(fieldnames):
                    raise CsvShapeError(
                        "row-width-mismatch",
                        f"{path}:row {row_number}",
                        f"row has {len(values)} cell(s); expected {len(fieldnames)}",
                    )
                rows.append(dict(zip(fieldnames, values)))
    except csv.Error as exc:
        raise CsvShapeError("csv-parse-error", str(path), f"CSV parse error: {exc}") from exc

    return fieldnames, rows
