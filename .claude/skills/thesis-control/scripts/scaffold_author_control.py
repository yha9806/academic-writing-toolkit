#!/usr/bin/env python3
"""Create the lightweight author-control Markdown files without overwriting."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple


FILENAMES = (
    "00_AUTHOR_INTENT.md",
    "01_EVIDENCE_AND_CLAIMS.md",
    "02_REVISION_LOG.md",
)


def scaffold(root: Path) -> List[Path]:
    skill_dir = Path(__file__).resolve().parents[1]
    assets_dir = skill_dir / "assets"
    destinations = [root / name for name in FILENAMES]
    collisions = [path for path in destinations if path.exists() or path.is_symlink()]
    if collisions:
        raise ValueError(
            "refusing to overwrite existing control file(s): {}".format(
                ", ".join(path.name for path in collisions)
            )
        )

    sources = [assets_dir / name for name in FILENAMES]
    for source in sources:
        if not source.is_file():
            raise ValueError("missing bundled template: {}".format(source))

    staged: List[Tuple[Path, Path]] = []
    created: List[Path] = []
    try:
        for source, destination in zip(sources, destinations):
            text = source.read_text(encoding="utf-8")
            handle = tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                delete=False,
                dir=str(root),
                prefix=".author-control-",
                suffix=".tmp",
            )
            temp_path = Path(handle.name)
            try:
                handle.write(text)
                handle.flush()
                os.fsync(handle.fileno())
            finally:
                handle.close()
            staged.append((temp_path, destination))
        for temp_path, destination in staged:
            os.replace(str(temp_path), str(destination))
            created.append(destination)
        return created
    except Exception:
        for temp_path, _ in staged:
            if temp_path.exists():
                temp_path.unlink()
        for destination in created:
            if destination.exists():
                destination.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the three lightweight author-control Markdown files."
    )
    parser.add_argument("root", nargs="?", default=".", help="project root")
    parser.add_argument("--json", action="store_true", dest="emit_json", help="emit JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write("error: root is not a directory\n")
        return 2
    try:
        created = scaffold(root)
    except (OSError, UnicodeError, ValueError) as exc:
        if args.emit_json:
            print(json.dumps({"ok": False, "root": str(root), "error": str(exc)}, indent=2))
        else:
            sys.stderr.write("error: {}\n".format(exc))
        return 1

    payload: Dict[str, object] = {
        "ok": True,
        "root": str(root),
        "created": [path.name for path in created],
        "human_review_required": True,
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print("Created lightweight author-control files:")
        for path in created:
            print("- {}".format(path))
        print("Replace AUTHOR_REVIEW_REQUIRED fields before substantive editing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
