#!/usr/bin/env python3
"""Every check in this toolkit must fail closed on an empty target.

    python3 scripts/check-fails-closed.py [--json]

Why this exists. Three times this toolkit reported a pass for work it had not
done: the citation fidelity audit examined zero Markdown files in a LaTeX
manuscript and exited 0; `verify-refs` read an empty bibliography and exited 0;
`count-words` was handed an unrecognised positional argument, silently counted a
different directory, and exited 0. Each was found by hand, one at a time, months
apart. A check that examines nothing and returns 0 is worse than no check,
because a green result is read as "looked and found nothing wrong".

So this runs every check script against an empty directory and requires a
non-zero exit. It is the regression test for the property itself: a new script
that forgets to fail closed turns this red.

The registry is the other half. Discovery alone cannot tell a check from a
converter, so every script under `.claude/skills/*/scripts/` must be listed in
CHECKS or in NOT_CHECKS with a reason. A script in neither is an error, which is
what keeps this list from rotting as the toolkit grows.

Scope: every script under `.claude/skills/*/scripts/`, and every
`scripts/audit-*.py`. The three project audits under `scripts/` (citations,
British English, paragraph logic) were outside the first version of this
registry and all three exited 0 on an empty base-dir, the same shape this file
exists to catch; found 2026-09-20, four days after the registry was written.
`session-scan.py` (empty targets: a directory that is not a repository, a
repository with no remote) and this script carry the property in their own
tests (T178, T157) rather than here.

Exit: 0 when every check failed closed and every script is accounted for, 1
otherwise.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / ".claude" / "skills"
SCRIPTS = ROOT / "scripts"

# Each entry builds the argv for running that check against an empty target.
# EMPTY is a directory with no manuscript, no bibliography and no notes.
CHECKS = {
    "audit/audit-citation-fidelity.mjs":
        lambda s, empty: ["node", str(s), "--base-dir", str(empty)],
    "audit/audit-claim-ledger.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty),
                          "--ledger", str(empty / "ledger.tsv")],
    "audit/audit-number-ledger.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty),
                          "--ledger", str(empty / "numbers.tsv")],
    "audit/audit-claim-positioning.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty)],
    "audit/audit-prose-fingerprint.py":
        lambda s, empty: ["python3", str(s), "--target", str(empty)],
    "review/audit-review-findings.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty),
                          "--findings", str(empty / "findings.tsv")],
    "map/count-words.mjs":
        lambda s, empty: ["node", str(s), "--base-dir", str(empty)],
    "verify-refs/verify-refs.py":
        lambda s, empty: ["python3", str(s), "--bib", str(empty / "empty.bib")],
    # No file to lint: nothing linted is not a pass (exit 2).
    "note/notes-lint.mjs":
        lambda s, empty: ["node", str(s)],
    "scripts/audit-citations.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty), "--json"],
    "scripts/audit-british-english.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty), "--json"],
    "scripts/audit-logic.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty), "--json"],
    "scripts/audit-public-content.py":
        lambda s, empty: ["python3", str(s), "--base-dir", str(empty), "--json"],
}

NOT_CHECKS = {
    "export/convert_to_docx.py": "converter: Markdown to .docx, makes no pass/fail claim",
    "audit/citations.mjs": "library: citation extraction and notes-source parsing used by the fidelity audit; no claim of its own",
    "audit/quote-fidelity.mjs": "library: quote graders (pure functions) used by the fidelity audit; no claim of its own",
    "audit/pdf-pages.mjs": "library: page labelling of pdftotext output used by the fidelity audit; no claim of its own",
    "audit/build-venue-baseline.py": "corpus builder: fetches a venue's papers from arXiv and writes a manifest; makes no pass/fail claim about a manuscript, and its own corpus floor exits 2 (T176)",
}


def discovered():
    out = {}
    for path in sorted(SKILLS.glob("*/scripts/*")):
        if path.suffix not in {".py", ".mjs"} or "__pycache__" in path.parts:
            continue
        out[f"{path.parent.parent.name}/{path.name}"] = path
    for path in sorted(SCRIPTS.glob("audit-*.py")):
        out[f"scripts/{path.name}"] = path
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    scripts = discovered()
    problems, results = [], []

    for name in sorted(set(scripts) - set(CHECKS) - set(NOT_CHECKS)):
        problems.append({"kind": "unregistered-script", "script": name,
                         "detail": "add it to CHECKS with an empty-target invocation, "
                                   "or to NOT_CHECKS with the reason it makes no pass/fail claim"})
    for name in sorted((set(CHECKS) | set(NOT_CHECKS)) - set(scripts)):
        problems.append({"kind": "registered-script-missing", "script": name,
                         "detail": "listed in this registry but not on disk"})

    with tempfile.TemporaryDirectory() as tmp:
        empty = Path(tmp)
        (empty / "empty.bib").write_text("", encoding="utf-8")
        (empty / "ledger.tsv").write_text("claim\tcite_key\tsnippet\tsource_file\tlevel\n", encoding="utf-8")
        (empty / "findings.tsv").write_text("location\tsource\tproblem\n", encoding="utf-8")
        (empty / "numbers.tsv").write_text("number\tscope\tartifact\tlocator\n", encoding="utf-8")
        for name in sorted(set(CHECKS) & set(scripts)):
            argv_ = CHECKS[name](scripts[name], empty)
            run = subprocess.run(argv_, capture_output=True, text=True, cwd=ROOT)
            head = (run.stdout or run.stderr).strip().splitlines()
            results.append({"script": name, "exit": run.returncode,
                            "first_line": head[0][:110] if head else ""})
            if run.returncode == 0:
                problems.append({"kind": "passes-on-an-empty-target", "script": name,
                                 "detail": f"exited 0 with nothing to examine: {head[0][:90] if head else '(no output)'}"})
            # The other way a check reports on work it did not do: it is handed
            # an argument it does not recognise, quietly examines something else
            # and exits 0. `count-words` did this with an unknown positional and
            # counted the toolkit's own template instead of the manuscript.
            bogus = subprocess.run(argv_[:2] + ["--zzz-not-a-real-flag"],
                                   capture_output=True, text=True, cwd=ROOT)
            results[-1]["exit_on_unknown_argument"] = bogus.returncode
            if bogus.returncode == 0:
                problems.append({"kind": "accepts-an-unknown-argument", "script": name,
                                 "detail": "exited 0 when given an argument it does not recognise, "
                                           "so a mistyped invocation reports on whatever it examined instead"})

    payload = {"schema_version": 1, "scripts_found": len(scripts),
               "checks_run": len(results), "results": results,
               "problems": problems, "problem_count": len(problems)}
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"fails-closed: {len(results)} check(s) run against an empty target, "
              f"{len(NOT_CHECKS)} script(s) registered as not-a-check")
        for r in results:
            print(f"  exit {r['exit']}  {r['script']}")
        if problems:
            print()
            for p in problems:
                print(f"{p['kind']}: {p['script']}\n    {p['detail']}")
        else:
            print("\nOK: every check fails closed, and every script is accounted for.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
