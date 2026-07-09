#!/usr/bin/env python3
"""Shared strict CSV and atomic file I/O for thesis-control scripts."""

from __future__ import annotations

import csv
import io
import os
import stat
import tempfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple


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


def render_csv_table(fieldnames: Sequence[str], rows: Sequence[Mapping[str, str]]) -> bytes:
    """Render a validated CSV table with stable LF line endings."""

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(fieldnames),
        extrasaction="raise",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def _stage_bytes(path: Path, content: bytes, mode: int) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def atomic_write_batch(contents: Mapping[Path, bytes]) -> None:
    """Stage and replace a set of files, restoring prior bytes on failure."""

    if not contents:
        return

    targets = sorted((Path(path), content) for path, content in contents.items())
    originals: Dict[Path, Tuple[bytes, int]] = {}
    created_directories: List[Path] = []
    staged: Dict[Path, Path] = {}
    replaced: List[Path] = []

    for target, _ in targets:
        if target.is_symlink():
            raise ValueError(f"refusing to replace symlink target: {target}")
        if target.exists() and not target.is_file():
            raise ValueError(f"output target is not a regular file: {target}")
        if target.exists():
            originals[target] = (
                target.read_bytes(),
                stat.S_IMODE(target.stat().st_mode),
            )

    try:
        known_directories = set()
        for target, _ in targets:
            missing: List[Path] = []
            parent = target.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            if not parent.is_dir():
                raise ValueError(f"output parent is not a directory: {parent}")
            for directory in reversed(missing):
                if directory in known_directories:
                    continue
                directory.mkdir()
                created_directories.append(directory)
                known_directories.add(directory)

        for target, content in targets:
            mode = originals.get(target, (b"", 0o644))[1]
            staged[target] = _stage_bytes(target, content, mode)

        for target, _ in targets:
            os.replace(staged[target], target)
            staged.pop(target, None)
            replaced.append(target)
    except Exception as exc:
        rollback_errors = []
        for target in reversed(replaced):
            try:
                if target in originals:
                    original_bytes, original_mode = originals[target]
                    restore = _stage_bytes(target, original_bytes, original_mode)
                    os.replace(restore, target)
                else:
                    target.unlink(missing_ok=True)
            except Exception as rollback_exc:
                rollback_errors.append(f"{target}: {rollback_exc}")
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError:
                pass
        if rollback_errors:
            details = "; ".join(rollback_errors)
            raise OSError(f"{exc}; rollback failed: {details}") from exc
        raise
    finally:
        for temporary in staged.values():
            temporary.unlink(missing_ok=True)
