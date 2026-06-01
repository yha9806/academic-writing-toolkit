#!/usr/bin/env python3
"""Scan public toolkit surfaces for private or project-specific residues."""

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, List


def tokens() -> List[str]:
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
    return [a + b for a, b in parts]


def public_files(base_dir: Path) -> Iterable[Path]:
    roots = [
        "README.md", "CLAUDE.md", "AGENTS.md", "GEMINI.md", "Makefile",
        "docs", ".claude/skills", ".cursor", "templates", "scripts", "tests",
        "plugins/academic-writing-toolkit",
    ]
    for item in roots:
        path = base_dir / item
        if path.is_file():
            yield path
        elif path.is_dir():
            for child in sorted(path.rglob("*")):
                if child.is_file() and "__pycache__" not in child.parts:
                    yield child


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit public toolkit content.")
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()
    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2

    issues = []
    if (base_dir / "docs" / "superpowers").exists():
        issues.append({"kind": "internal-docs", "location": "docs/superpowers", "token": "internal planning docs"})
    forbidden = tokens()
    for path in public_files(base_dir):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for token in forbidden:
            index = text.find(token)
            if index >= 0:
                line = text.count("\n", 0, index) + 1
                issues.append({"kind": "private-token", "location": "{}:{}".format(path.relative_to(base_dir), line), "token": token})
    payload = {"schema_version": 1, "issues": issues, "issue_count": len(issues)}
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            print("{location}: {kind}: {token}".format(**issue))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
