#!/usr/bin/env python3
"""Validate the lightweight three-file author-control profile."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence


REQUIRED_HEADINGS: Dict[str, Sequence[str]] = {
    "00_AUTHOR_INTENT.md": (
        "# Author Intent",
        "## Real-world problem",
        "## Intended use",
        "## Current validation boundary",
        "## Research object",
        "## Core scientific question",
        "## Primary experiment",
        "## Supporting analyses",
        "## Headline claim",
        "## Evidence boundary",
        "## Must-preserve title or abstract concepts",
        "## Reframes requiring new author approval",
    ),
    "01_EVIDENCE_AND_CLAIMS.md": (
        "# Evidence And Claims",
        "## Evidence baseline",
        "## Argument baseline",
        "## Method task",
        "## Claim licence",
        "## Experiment and analysis admission",
        "## Explicitly unlicensed claims",
    ),
    "02_REVISION_LOG.md": (
        "# Revision Log",
    ),
}

NONEMPTY_SECTIONS: Dict[str, Sequence[str]] = {
    "00_AUTHOR_INTENT.md": tuple(REQUIRED_HEADINGS["00_AUTHOR_INTENT.md"][1:]),
    "01_EVIDENCE_AND_CLAIMS.md": tuple(
        REQUIRED_HEADINGS["01_EVIDENCE_AND_CLAIMS.md"][1:]
    ),
}

REQUIRED_REVISION_FIELDS = (
    "Date",
    "Why change",
    "Scope",
    "Allowed changes",
    "Must preserve",
    "Forbidden changes",
    "Evidence baseline",
    "Argument baseline",
    "Author pre-edit decision",
    "Actual changes",
    "Research spine changed",
    "Drift-audit result",
    "Reader-comprehension gate",
    "Argument-function audit",
    "Author post-edit decision",
)

PLACEHOLDER = "AUTHOR_REVIEW_REQUIRED"
REVISION_RE = re.compile(r"^##\s+Revision\s+(.+?)\s*$", re.MULTILINE)


def issue(kind: str, path: str, detail: str, line: Optional[int] = None) -> Dict[str, object]:
    item: Dict[str, object] = {"kind": kind, "path": path, "detail": detail}
    if line is not None:
        item["line"] = line
    return item


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def section_body(text: str, heading: str) -> str:
    lines = text.splitlines()
    try:
        start = next(index for index, line in enumerate(lines) if line.strip() == heading)
    except StopIteration:
        return ""
    body: List[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("#"):
            break
        body.append(line)
    return "\n".join(body).strip()


def metadata_value(text: str, label: str) -> Optional[str]:
    match = re.search(r"^{}:\s*(.*?)\s*$".format(re.escape(label)), text, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip()


def latest_revision(text: str) -> Optional[str]:
    matches = list(REVISION_RE.finditer(text))
    if not matches:
        return None
    return text[matches[-1].start() :]


def check_structure(path: Path, rel: str, strict: bool) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    if not path.exists():
        return [issue("missing-file", rel, "required author-control file is missing")]
    if not path.is_file():
        return [issue("not-file", rel, "required path is not a file")]
    try:
        text = read_text(path)
    except UnicodeDecodeError as exc:
        return [issue("decode-error", rel, str(exc))]

    lines = [line.strip() for line in text.splitlines()]
    for heading in REQUIRED_HEADINGS[rel]:
        count = lines.count(heading)
        if count == 0:
            issues.append(issue("missing-heading", rel, heading))
        elif count > 1:
            issues.append(issue("duplicate-heading", rel, heading))

    for heading in NONEMPTY_SECTIONS.get(rel, ()):
        body = section_body(text, heading)
        if not body:
            issues.append(issue("empty-section", rel, heading))

    if strict and PLACEHOLDER in text:
        for line_no, line in enumerate(text.splitlines(), start=1):
            if PLACEHOLDER in line:
                issues.append(
                    issue("unresolved-author-review", rel, "replace author-review placeholder", line_no)
                )

    if rel in {"00_AUTHOR_INTENT.md", "01_EVIDENCE_AND_CLAIMS.md"} and strict:
        if metadata_value(text, "Status") != "active":
            issues.append(issue("inactive-control-file", rel, "Status must be active"))
        if metadata_value(text, "Human approved") != "true":
            issues.append(issue("missing-human-approval", rel, "Human approved must be true"))

    if rel == "02_REVISION_LOG.md":
        revision = latest_revision(text)
        if revision is None:
            issues.append(issue("missing-revision-entry", rel, "add at least one ## Revision entry"))
            return issues
        for label in REQUIRED_REVISION_FIELDS:
            value = metadata_value(revision, label)
            if value is None:
                issues.append(issue("missing-revision-field", rel, label))
            elif not value:
                issues.append(issue("empty-revision-field", rel, label))
        if strict:
            allowed_values = {
                "Scope": {"local_patch", "section_restructure", "full_reframe"},
                "Author pre-edit decision": {"approved"},
                "Research spine changed": {"yes", "no"},
                "Drift-audit result": {"pending", "passed", "failed"},
                "Reader-comprehension gate": {"not_required", "not_run", "passed", "failed"},
                "Argument-function audit": {"not_required", "not_run", "passed", "failed"},
                "Author post-edit decision": {
                    "pending", "accept", "partial_accept", "revise", "rollback"
                },
            }
            for label, allowed in allowed_values.items():
                value = metadata_value(revision, label)
                if value is not None and value not in allowed:
                    issues.append(
                        issue(
                            "invalid-revision-value",
                            rel,
                            "{} must be one of {}".format(label, ", ".join(sorted(allowed))),
                        )
                    )
    return issues


def validate(root: Path, strict: bool) -> List[Dict[str, object]]:
    issues: List[Dict[str, object]] = []
    for rel in REQUIRED_HEADINGS:
        issues.extend(check_structure(root / rel, rel, strict))
    return issues


def emit_text(root: Path, issues: List[Dict[str, object]]) -> None:
    print("Author-control root: {}".format(root))
    if not issues:
        print("- no structural author-control issues detected")
        return
    print("- issues: {}".format(len(issues)))
    for item in issues:
        location = item["path"]
        if "line" in item:
            location = "{}:{}".format(location, item["line"])
        print("- {kind}: {location}: {detail}".format(location=location, **item))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the lightweight three-file author-control profile."
    )
    parser.add_argument("root", nargs="?", default=".", help="project root")
    parser.add_argument("--strict", action="store_true", help="require active human-approved files")
    parser.add_argument("--json", action="store_true", dest="emit_json", help="emit JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not root.is_dir():
        sys.stderr.write("error: root is not a directory\n")
        return 2
    issues = validate(root, args.strict)
    payload = {
        "schema_version": 1,
        "root": str(root),
        "strict": args.strict,
        "issues": issues,
        "issue_count": len(issues),
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        emit_text(root, issues)
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
