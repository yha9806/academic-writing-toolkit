#!/usr/bin/env python3
"""Reconcile a LaTeX manuscript's citations with its BibTeX file, both ways.

    python3 reconcile-cites.py --bib references.bib [--root DIR] [--json] FILE...

Reads each FILE and every file it pulls in with \\input, \\include or \\subfile (relative to --root, ".tex" added
when missing), and collects the keys of every citation command (\\cite, \\citet, \\citep, \\citeauthor, \\nocite,
\\parencite, \\textcite, \\autocite ...). \\nocite{*} cites every entry. Reports:

- cited-not-in-bib: a key the text cites that the bibliography does not define (with where it is first cited);
- bib-not-cited:    an entry the bibliography defines that nothing reads.

Duplicate keys and malformed entries are verify-refs.py's job and are not repeated here; this uses its parser.
A \\input it cannot find is listed under unresolved_inputs, not counted as an issue (a generated file is often
missing from a clean tree), and the report says so.

Exit: 0 both lists empty; 1 at least one issue; 2 nothing to reconcile (no FILE could be read, or the
bibliography is unreadable or defines no entry).
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CITE = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?(?:\s*\[[^\]]*\]){0,2}\s*\{([^}]*)\}")
INPUT = re.compile(r"\\(?:input|include|subfile)\s*\{([^}]+)\}")
COMMENT = re.compile(r"(?<!\\)%.*")


def _parser():
    spec = importlib.util.spec_from_file_location("verify_refs", HERE / "verify-refs.py")
    mod = importlib.util.module_from_spec(spec)
    saved = sys.argv
    sys.argv = ["verify-refs.py"]
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.argv = saved
    return mod.parse_bibtex


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
            name = m.group(1).strip()
            q = Path(root) / name
            if not q.suffix:
                q = q.with_suffix(".tex")
            if q.exists():
                stack.append(q)
            else:
                unresolved.append(name)
    return out, unresolved


def main():
    ap = argparse.ArgumentParser(description="Reconcile LaTeX citations with a BibTeX file.")
    ap.add_argument("--bib", required=True)
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("files", nargs="+")
    a = ap.parse_args()
    try:
        entries = _parser()(Path(a.bib).read_text(encoding="utf-8", errors="replace"))
    except OSError as e:
        sys.stderr.write(f"reconcile-cites: cannot read the bibliography {a.bib}: {e}\n")
        return 2
    defined = [e["key"] for e in entries]
    if not defined:
        sys.stderr.write(f"reconcile-cites: {a.bib} defines no entry\n")
        return 2
    files, unresolved = read_tree(a.files, a.root)
    if not files:
        sys.stderr.write("reconcile-cites: none of the files given could be read\n")
        return 2
    first = {}
    everything = False
    for path, text in files:
        for m in CITE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            for k in (x.strip() for x in m.group(1).split(",")):
                if k == "*":
                    everything = True
                elif k:
                    first.setdefault(k, f"{path}:{line}")
    bib = set(defined)
    issues = [{"kind": "cited-not-in-bib", "severity": "high", "key": k, "location": loc,
               "message": "Cited in the text, not defined in the bibliography."}
              for k, loc in sorted(first.items()) if k not in bib]
    if not everything:
        issues += [{"kind": "bib-not-cited", "severity": "medium", "key": k, "location": a.bib,
                    "message": "Defined in the bibliography, cited nowhere in the files read."}
                   for k in sorted(bib - set(first))]
    payload = {"schema_version": 1, "bib_entries": len(bib), "cited_keys": len(first), "nocite_all": everything,
               "files_read": [str(p) for p, _ in files], "unresolved_inputs": sorted(set(unresolved)),
               "issues": issues, "issue_count": len(issues)}
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for i in issues:
            print(f"{i['location']}: {i['kind']}: {i['key']}")
        print(f"read {len(files)} file(s); {len(first)} cited key(s), {len(bib)} bibliography entries; "
              f"{len(issues)} issue(s)" + (f"; unresolved inputs: {', '.join(sorted(set(unresolved)))}" if unresolved else ""))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
