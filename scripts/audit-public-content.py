#!/usr/bin/env python3
"""Scan public toolkit surfaces for private or project-specific residues.

The report says what it read. `issue_count: 0` on its own could not be told
apart from a run that read nothing: a --base-dir beside the toolkit, or a tree
whose public surfaces had been renamed, printed the same line and exited 0
(found 2026-09-20; the same shape as a check that examined zero objects). So
the payload carries `files_scanned`, `roots_present` and `roots_missing`, a
run that read no file exits 2, and files are compared as bytes against ASCII
tokens so that no file is skipped for its encoding (a Latin-1 file used to be
skipped without a word).

Exit: 0 clean, 1 residues found, 2 nothing checked or a bad --base-dir.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Tuple

PUBLIC_ROOTS = [
    "README.md", "CLAUDE.md", "AGENTS.md", "GEMINI.md", "Makefile",
    "docs", "examples", ".claude/skills", ".cursor", "templates", "scripts", "tests",
    "plugins/academic-writing-toolkit",
]


def tokens() -> List[bytes]:
    # Each token is split in two so that this file does not match itself.
    parts = [
        ("EM", "NLP"),
        ("VU", "LCA"),
        ("self-", "cite"),
        ("fire_", "imagery"),
        ("art_", "critique"),
        ("L1_", "L5"),
        ("60,000-", "word"),
        ("52 ", "sources"),
        ("Ben", "nett"),
        ("Good", "man"),
        ("Pano", "fsky"),
        ("Spi", "noza"),
        ("De", "leuze"),
        ("Vibrant ", "Matter"),
        ("thing-", "power"),
        ("P", "UR"),
        ("V", "LM"),
        ("Rad", "ford"),
        ("C", "LIP"),
        ("Judge", "++"),
        ("Anch", "ored"),
        ("Yu", ","),
        ("Hao", "rui"),
    ]
    return [(a + b).encode("ascii") for a, b in parts]


def public_files(base_dir: Path) -> Tuple[List[Path], List[str], List[str]]:
    """Every file under the public roots, and which roots were there at all."""
    files: List[Path] = []
    present: List[str] = []
    missing: List[str] = []
    for item in PUBLIC_ROOTS:
        path = base_dir / item
        if path.is_file():
            present.append(item)
            files.append(path)
        elif path.is_dir():
            present.append(item)
            for child in sorted(path.rglob("*")):
                if child.is_file() and "__pycache__" not in child.parts:
                    files.append(child)
        else:
            missing.append(item)
    return files, present, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit public toolkit content.")
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()
    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2

    files, present, missing = public_files(base_dir)
    issues = []
    if (base_dir / "docs" / "superpowers").exists():
        issues.append({"kind": "internal-docs", "location": "docs/superpowers", "token": "internal planning docs"})
    forbidden = tokens()
    for path in files:
        data = path.read_bytes()
        for token in forbidden:
            index = data.find(token)
            if index >= 0:
                line = data.count(b"\n", 0, index) + 1
                issues.append({
                    "kind": "private-token",
                    "location": "{}:{}".format(path.relative_to(base_dir).as_posix(), line),
                    "token": token.decode("ascii"),
                })
    nothing_checked = not files
    payload = {
        "schema_version": 2,
        "base_dir": str(base_dir),
        "files_scanned": len(files),
        "roots_present": present,
        "roots_missing": missing,
        "nothing_checked": nothing_checked,
        "issues": issues,
        "issue_count": len(issues),
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            print("{location}: {kind}: {token}".format(**issue))
        print("scanned {} file(s) under {} of {} public root(s); {} issue(s)".format(
            len(files), len(present), len(PUBLIC_ROOTS), len(issues)))
        if missing:
            print("not present: " + ", ".join(missing))
    if nothing_checked:
        sys.stderr.write("nothing checked: no public surface under {} (looked for {})\n".format(
            base_dir, ", ".join(PUBLIC_ROOTS)))
        return 2
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
