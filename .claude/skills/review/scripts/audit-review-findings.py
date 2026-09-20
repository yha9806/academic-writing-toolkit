#!/usr/bin/env python3
"""Resolve the anchors in a review's findings.

    python3 audit-review-findings.py --base-dir <manuscript> --findings <findings.tsv> [--json] [--allow-empty]

What this replaces. /review advertised "anchored findings", where the anchor was
a section name or a quoted span. Nothing checked that the anchor existed, and an
author acting on the report could not tell a real location from a plausible one.
A review is the one output in this toolkit written to be acted on without being
re-derived, so its anchors have to resolve.

Format. A declaration line naming every file the review read, then rows of
`location` (file:line), `source` (the archived original or evidence file the
finding rests on, or `-` when the finding is about the text itself) and
`problem` (one sentence):

    # reviewed: chapters/ch2.md, chapters/ch3.md
    location<TAB>source<TAB>problem
    chapters/ch2.md:142<TAB>evidence/foo.txt<TAB>The sentence says more than the passage it rests on.

Checked here:

  reviewed-declaration-missing  no `# reviewed:` line, so the review does not
                                say what it read
  reviewed-file-missing         a declared file is not on disk
  anchor-malformed              the location is not file:line
  anchor-file-missing           the anchored file is not on disk
  anchor-line-out-of-range      the line does not exist in that file
  finding-outside-reviewed-set  a finding about a file the review never declared
  source-missing                the named source is not on disk, so the finding
                                rests on the reviewer's memory
  problem-empty                 a finding with no sentence
  problem-not-one-sentence      PROMPT: more than one sentence in the problem

The declaration is what separates "read the chapters and found nothing" from
"examined nothing". The first is a pass; the second exits 2.

What this does NOT do: judge whether a finding is right, or whether the source
supports it. It resolves locations. A finding that points at a real line and a
real file can still be wrong, and that still needs a reader.

Exit: 1 on a hard finding, 2 when the review declares no reviewed file (unless
--allow-empty), 0 otherwise.
"""
import argparse
import json
import re
import sys
from pathlib import Path

COLUMNS = ["location", "source", "problem"]
REVIEWED = re.compile(r"^#\s*reviewed:\s*(.*)$", re.I)
SENTENCE_END = re.compile(r"[.!?](?:\s|$)")


def read_findings(path):
    """(reviewed, rows). Comment lines other than the declaration are ignored."""
    reviewed, rows, header_seen = [], [], False
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        declaration = REVIEWED.match(line.strip())
        if declaration:
            reviewed += [p.strip() for p in declaration.group(1).split(",") if p.strip()]
            continue
        if line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if not header_seen:
            if parts[:len(COLUMNS)] != COLUMNS:
                sys.exit(f"FINDINGS_COLUMNS: expected {COLUMNS}, found {parts}")
            header_seen = True
            continue
        if len(parts) < len(COLUMNS):
            sys.exit(f"FINDINGS_COLUMNS: line {n} has {len(parts)} columns, expected {len(COLUMNS)}")
        row = dict(zip(COLUMNS, parts))
        row["line"] = n
        rows.append(row)
    if not header_seen:
        sys.exit(f"FINDINGS_COLUMNS: no header row; expected {COLUMNS}")
    return reviewed, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--findings", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-empty", action="store_true")
    a = ap.parse_args(argv)
    base = Path(a.base_dir).expanduser().resolve()
    findings_path = Path(a.findings).expanduser().resolve()
    if not base.is_dir():
        sys.exit(f"BASE_MISSING: {base}")
    if not findings_path.is_file():
        sys.exit(f"FINDINGS_MISSING: {findings_path}")

    reviewed, rows = read_findings(findings_path)
    problems = []

    if not reviewed:
        problems.append({"kind": "reviewed-declaration-missing", "location": findings_path.name,
                         "detail": "the report does not say which files it read, so no finding count means anything"})
    for rel in reviewed:
        if not (base / rel).is_file():
            problems.append({"kind": "reviewed-file-missing", "location": rel,
                             "detail": f"declared as reviewed but not on disk under {base}"})

    reviewed_set = set(reviewed)
    for row in rows:
        where = f"{findings_path.name}:{row['line']}"
        location = row["location"].strip()
        file_part, _, line_part = location.rpartition(":")
        if not file_part or not line_part.isdigit() or int(line_part) < 1:
            problems.append({"kind": "anchor-malformed", "location": where,
                             "detail": f"expected file:line, found {location!r}"})
        else:
            target = base / file_part
            if not target.is_file():
                problems.append({"kind": "anchor-file-missing", "location": where,
                                 "detail": f"{file_part} is not on disk under {base}"})
            else:
                total = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
                if int(line_part) > total:
                    problems.append({"kind": "anchor-line-out-of-range", "location": where,
                                     "detail": f"{file_part} has {total} line(s); the finding points at line {line_part}"})
            if file_part not in reviewed_set:
                problems.append({"kind": "finding-outside-reviewed-set", "location": where,
                                 "detail": f"{file_part} is not in the reviewed declaration"})
        source = row["source"].strip()
        if source and source != "-" and not (base / source).is_file() and not Path(source).is_file():
            problems.append({"kind": "source-missing", "location": where,
                             "detail": f"{source} is not on disk, so this finding rests on the reviewer's memory"})
        problem = row["problem"].strip()
        if not problem:
            problems.append({"kind": "problem-empty", "location": where,
                             "detail": "a finding with no sentence states nothing the author can act on"})
        elif len(SENTENCE_END.findall(problem)) > 1:
            problems.append({"kind": "problem-not-one-sentence", "prompt": True, "location": where,
                             "detail": f"more than one sentence; the format is one: {problem[:80]}"})

    # A missing declaration is not a hard finding but a "nothing checked": it
    # takes the exit 2 path the rest of this toolkit uses for that state.
    hard_kinds = {"reviewed-file-missing", "anchor-malformed",
                  "anchor-file-missing", "anchor-line-out-of-range", "finding-outside-reviewed-set",
                  "source-missing", "problem-empty"}
    hard = [p for p in problems if p["kind"] in hard_kinds]
    nothing = not reviewed
    payload = {
        "schema_version": 1,
        "base": str(base),
        "findings_file": str(findings_path),
        "reviewed_files": len(reviewed),
        "finding_rows": len(rows),
        "findings": problems,
        "hard_finding_count": len(hard),
        "nothing_checked": nothing,
        "limits": {
            "correctness": "a finding that resolves to a real line and a real source can still be wrong. This resolves locations, nothing else.",
        },
    }
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"review findings: {len(rows)} finding(s) against {len(reviewed)} reviewed file(s) under {base}")
        for kind in ["reviewed-declaration-missing", "reviewed-file-missing", "anchor-malformed",
                     "anchor-file-missing", "anchor-line-out-of-range", "finding-outside-reviewed-set",
                     "source-missing", "problem-empty", "problem-not-one-sentence"]:
            group = [p for p in problems if p["kind"] == kind]
            if not group:
                continue
            print(f"\n{kind}{' (prompt, not a finding)' if group[0].get('prompt') else ''} ({len(group)})")
            for p in group:
                print(f"  {p['location']}\n    {p['detail']}")
        if nothing:
            print("\nNOTHING CHECKED: the report does not say what it read. This is not a clean review.")
        print(f"\nNot decided here: {payload['limits']['correctness']}")
    return 1 if hard else (2 if nothing and not a.allow_empty else 0)


if __name__ == "__main__":
    sys.exit(main())
