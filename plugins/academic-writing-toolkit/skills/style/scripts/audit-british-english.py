#!/usr/bin/env python3
"""Detect and optionally fix common US spellings in thesis text.

Python 3.8 stdlib only. The fixer is intentionally conservative: it only
replaces whole words in Markdown text files and preserves simple title case.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List

REPLACEMENTS: Dict[str, str] = {
    "analyze": "analyse",
    "analyzed": "analysed",
    "analyzing": "analysing",
    "behavior": "behaviour",
    "behaviors": "behaviours",
    "center": "centre",
    "color": "colour",
    "colors": "colours",
    "emphasize": "emphasise",
    "emphasized": "emphasised",
    "favor": "favour",
    "favors": "favours",
    "labor": "labour",
    "modeling": "modelling",
    "organize": "organise",
    "organized": "organised",
    "theorize": "theorise",
    "utilize": "utilise",
}


def markdown_files(base_dir: Path) -> Iterable[Path]:
    roots = [base_dir / "chapters", base_dir / "literature" / "reading_notes"]
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.md")):
            if path.is_file():
                yield path


def replacement_for(word: str) -> str:
    repl = REPLACEMENTS[word.lower()]
    if word[:1].isupper():
        return repl[:1].upper() + repl[1:]
    return repl


def audit_file(path: Path, base_dir: Path) -> List[dict]:
    text = path.read_text(encoding="utf-8")
    issues: List[dict] = []
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in REPLACEMENTS) + r")\b", re.IGNORECASE)
    for m in pattern.finditer(text):
        line = text.count("\n", 0, m.start()) + 1
        current = m.group(0)
        issues.append({
            "kind": "us-spelling",
            "severity": "low",
            "location": "{}:{}".format(path.relative_to(base_dir), line),
            "current": current,
            "replacement": replacement_for(current),
        })
    return issues


def fix_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(r"\b(" + "|".join(re.escape(k) for k in REPLACEMENTS) + r")\b", re.IGNORECASE)
    new_text = pattern.sub(lambda m: replacement_for(m.group(0)), text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit British English spelling in toolkit projects.")
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    parser.add_argument("--fix", action="store_true")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2

    files = list(markdown_files(base_dir))
    if args.fix:
        changed = [str(p.relative_to(base_dir)) for p in files if fix_file(p)]
        payload = {"schema_version": 1, "changed": changed}
        if args.emit_json:
            print(json.dumps(payload, indent=2))
        else:
            print("changed files: {}".format(len(changed)))
        return 0

    issues: List[dict] = []
    for path in files:
        issues.extend(audit_file(path, base_dir))
    payload = {"schema_version": 1, "issues": issues, "issue_count": len(issues)}
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            print("{location}: {current} -> {replacement}".format(**issue))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
