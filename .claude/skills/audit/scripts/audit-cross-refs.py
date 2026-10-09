#!/usr/bin/env python3
"""A \\label that \\ref will print the wrong number for.

    python3 audit-cross-refs.py [--root DIR] [--json] FILE...

LaTeX gives a \\label the number of the last thing that stepped a counter. A heading that is not numbered steps
none: a starred heading, or a heading deeper than secnumdepth (\\paragraph and \\subparagraph in the standard classes
and in acmart). A label placed on such a heading takes the number of the section around it, and every \\ref, \\cref
or \\autoref to it prints that number; \\nameref and \\pageref are unaffected. On one manuscript several run-in
paragraphs carried labels, two of them printed the same section number, and no check read it.

Reads each FILE and every file it pulls in with \\input, \\include or \\subfile (relative to --root, ".tex" added when
missing). secnumdepth is the last \\setcounter{secnumdepth}{N} in the files read; without one, the class's default.
A label counts as placed on a heading when it is inside the heading's title or follows it with only space between.

Reports, as issues of kind label-after-unnumbered-heading: the label, the heading, where it is, and every reference
that prints its number. A label that nothing in the files read refers to by number is not an issue.

Exit: 0 no issue; 1 at least one; 2 nothing read (no FILE could be read).
"""
import argparse
import json
import re
import sys
from pathlib import Path

INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")
LEVELS = {"part": -1, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4,
          "subparagraph": 5}
HEADING = re.compile(r"\\(" + "|".join(LEVELS) + r")(\*?)\s*(?:\[[^\]]*\])?\s*\{")
LABEL = re.compile(r"\\label\s*\{([^}]+)\}")
LABEL_AFTER = re.compile(r"\s*\\label\s*\{([^}]+)\}")
# commands that print the label's number; \nameref prints the title and \pageref the page
NUMBER_REF = re.compile(r"\\(?:ref|cref|Cref|autoref|Autoref|vref|Vref|labelcref|subref)\*?\s*\{([^}]+)\}")
SECNUMDEPTH = re.compile(r"\\setcounter\s*\{secnumdepth\}\s*\{\s*(-?\d+)\s*\}")
DOCCLASS = re.compile(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}")
CHAPTER_CLASSES = {"report", "book", "memoir", "scrbook", "scrreprt"}
ACMART = {"sigchi": 1, "sigchi-a": 0, "acmcp": -1}


def read_tree(files, root):
    """[(path, text without comments)] for the files given and everything they input, each file once."""
    out, seen, unresolved = [], set(), []
    stack = [Path(f) for f in reversed(files)]
    while stack:
        p = stack.pop()
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        try:
            text = COMMENT.sub("", p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            unresolved.append(str(p))
            continue
        out.append((p, text))
        for m in reversed(list(INPUT.finditer(text))):
            q = Path(root) / m.group(1).strip()
            if not q.suffix:
                q = q.with_suffix(".tex")
            if q.exists():
                stack.append(q)
            else:
                unresolved.append(m.group(1).strip())
    return out, unresolved


def secnumdepth(files):
    """(depth, where it came from)."""
    found = None
    for path, text in files:
        for m in SECNUMDEPTH.finditer(text):
            found = (int(m.group(1)), f"{path}:{text.count(chr(10), 0, m.start()) + 1}")
    if found:
        return found
    for _, text in files:
        m = DOCCLASS.search(text)
        if m:
            cls, opts = m.group(2).strip(), {o.strip() for o in (m.group(1) or "").split(",")}
            if cls in CHAPTER_CLASSES:
                return 2, f"default of {cls}"
            if cls == "acmart":
                for opt, depth in ACMART.items():
                    if opt in opts:
                        return depth, f"default of acmart with {opt}"
            return 3, f"default of {cls}"
    return 3, "default of the standard classes"


def closing(text, start):
    """Index of the brace closing the group that opens just before start."""
    depth = 1
    for i in range(start, len(text)):
        c = text[i]
        if c == "\\":
            continue
        if c == "{" and text[i - 1] != "\\":
            depth += 1
        elif c == "}" and text[i - 1] != "\\":
            depth -= 1
            if depth == 0:
                return i
    return len(text)


def unnumbered_labels(files, depth):
    """{label: (heading, file, line, why)} for labels placed on a heading that steps no counter."""
    out = {}
    for path, text in files:
        for m in HEADING.finditer(text):
            name, star = m.group(1), m.group(2)
            if not star and LEVELS[name] <= depth:
                continue
            end = closing(text, m.end())
            title = text[m.end():end]
            labels = [x.group(1).strip() for x in LABEL.finditer(title)]
            after = LABEL_AFTER.match(text, end + 1)
            if after:
                labels.append(after.group(1).strip())
            why = "starred" if star else f"\\{name} is level {LEVELS[name]}, deeper than secnumdepth {depth}"
            heading = f"\\{name}{star}{{{LABEL.sub('', title).strip()}}}"
            line = text.count(chr(10), 0, m.start()) + 1
            for label in labels:
                out.setdefault(label, (heading, str(path), line, why))
    return out


def main():
    ap = argparse.ArgumentParser(description="Labels on unnumbered headings that \\ref prints the wrong number for.")
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    files, unresolved = read_tree(a.files, a.root)
    if not files:
        sys.stderr.write("audit-cross-refs: none of the files given could be read\n")
        return 2
    depth, depth_from = secnumdepth(files)
    placed = unnumbered_labels(files, depth)
    refs = {}
    for path, text in files:
        for m in NUMBER_REF.finditer(text):
            for k in (x.strip() for x in m.group(1).split(",")):
                if k:
                    refs.setdefault(k, []).append(f"{path}:{text.count(chr(10), 0, m.start()) + 1}")
    issues = [{"kind": "label-after-unnumbered-heading", "severity": "high", "label": k, "heading": h,
               "location": f"{f}:{line}", "why": why, "refs": refs[k],
               "message": f"The heading has no number ({why}), so every \\ref to {k} prints the number of the section "
                          f"around it."}
              for k, (h, f, line, why) in sorted(placed.items(), key=lambda kv: kv[1][1:3]) if k in refs]
    payload = {"schema_version": 1, "secnumdepth": depth, "secnumdepth_from": depth_from,
               "labels_on_unnumbered_headings": len(placed), "files_read": [str(p) for p, _ in files],
               "unresolved_inputs": sorted(set(unresolved)), "issues": issues, "issue_count": len(issues)}
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for i in issues:
            print(f"{i['location']}: {i['label']} on {i['heading']}: {i['why']}; printed by {len(i['refs'])} reference(s)")
        print(f"read {len(files)} file(s); secnumdepth {depth} ({depth_from}); {len(issues)} issue(s)"
              + (f"; unresolved inputs: {', '.join(sorted(set(unresolved)))}" if unresolved else ""))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
