#!/usr/bin/env python3
"""Deterministic paragraph-level writing logic audit.

This script does not rewrite prose. It identifies paragraphs that deserve
agent review before a human approves any edit.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Iterable, List

TRANSITIONS = {"furthermore", "moreover", "however", "therefore", "nevertheless", "consequently"}


def chapter_files(base_dir: Path) -> Iterable[Path]:
    root = base_dir / "chapters"
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*.md") if p.is_file())


def paragraphs(text: str) -> List[dict]:
    out: List[dict] = []
    start = 0
    for block in re.split(r"\n\s*\n", text):
        raw = block.strip()
        line = text.count("\n", 0, start) + 1
        start += len(block) + 2
        if not raw or raw.startswith("#") or raw.startswith("|") or raw.startswith("```"):
            continue
        out.append({"line": line, "text": raw})
    return out


def first_word(text: str) -> str:
    m = re.match(r"[\W_]*([A-Za-z]+)", text)
    return m.group(1).lower() if m else ""


def audit_file(path: Path, base_dir: Path) -> List[dict]:
    text = path.read_text(encoding="utf-8")
    paras = paragraphs(text)
    issues: List[dict] = []
    previous_transition = ""
    for para in paras:
        words = re.findall(r"[A-Za-z0-9']+", para["text"])
        loc = "{}:{}".format(path.relative_to(base_dir), para["line"])
        if len(words) < 12:
            issues.append({
                "kind": "short-paragraph",
                "severity": "medium",
                "location": loc,
                "message": "Paragraph is very short and may need integration with neighbouring prose.",
            })
        fw = first_word(para["text"])
        if fw in TRANSITIONS and fw == previous_transition:
            issues.append({
                "kind": "repeated-transition",
                "severity": "medium",
                "location": loc,
                "message": "Adjacent paragraphs start with the same transition.",
            })
        if fw in TRANSITIONS:
            previous_transition = fw
        else:
            previous_transition = ""
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit paragraph-level writing logic.")
    parser.add_argument("--base-dir", required=True)
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()
    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2
    issues: List[dict] = []
    for path in chapter_files(base_dir):
        issues.extend(audit_file(path, base_dir))
    payload = {"schema_version": 1, "issues": issues, "issue_count": len(issues)}
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            print("{location}: {kind}: {message}".format(**issue))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
