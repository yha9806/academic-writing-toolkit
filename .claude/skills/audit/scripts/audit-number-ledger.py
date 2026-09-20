#!/usr/bin/env python3
r"""Bind the numbers a manuscript reports to the artifacts they come from.

    python3 audit-number-ledger.py --base-dir <manuscript> --ledger <numbers.tsv> [--json] [--pairs] [--allow-empty]

The gap this closes. A manuscript already has one guard on its numbers: a
frequency table of numeric tokens taken before and after a prose pass, so an
edit that moves a number shows up. That answers "did this pass change a
number". It cannot answer either of the two questions that have actually gone
wrong:

  - is this the artifact's number? Hand-copied figures drift, and three
    hand-counted totals in one day were each wrong by one or two.
  - is the sentence carrying the scope the number is only true within? A ratio
    true of 15 cells was written as if it held for all of them, and a pooled
    share was quoted alone against the manuscript's own warning not to.

A row binds one reported number to one artifact:

    printed<TAB>in_artifact<TAB>scope<TAB>artifact<TAB>locator
    63.5<TAB>0.635<TAB>pooled<TAB>figures/fig.tex<TAB>explained variance 0.635

`printed` is the value as the prose prints it; `in_artifact` is the value as the
file writes it. They are two columns because on a real manuscript they differ:
the figure carries `0.635` and the text prints `63.5\%`. A version with one
column reported that as a broken binding. Converting silently would have been
worse — the conversion is recorded and shown, never inferred. `scope` is the
qualifier every sentence reporting the number must carry, or `-`. `locator` is
the verbatim string in the artifact, so the binding can be re-read.

  locator-not-in-artifact    the locator is not verbatim in the artifact
  value-not-in-locator       the locator does not itself carry in_artifact, so
                             the row looks bound and binds nothing
  printed-artifact-mismatch  printed and in_artifact are neither equal nor the
                             same value as a proportion and a percentage
  number-not-in-manuscript   the printed value is no longer reported; the row
                             is stale
  artifact-missing           the artifact is not on disk
  scope-missing              a sentence reports the number without its scope
  unledgered-number          PROMPT: a number reported with no row. Years,
                             counts of sections and sample sizes all land here,
                             so this is a coverage list, not a finding.

`scope` is matched literally, and that is its limit. On the real manuscript,
the first scope token tried flagged two sentences that carry the scope in
other words; a token those sentences actually contain passed both. Pick
a token the correct sentences actually contain, or the column produces noise
rather than a guard. A scope of `-` switches the check off for that row.

What this does NOT do: decide whether the artifact is the right one, or whether
a number is correctly derived from it. It checks that the value printed in the
prose is the value written in a file, under the scope the ledger records.

Exit: 1 on a hard finding, 2 when no row was checked at all unless
--allow-empty, 0 otherwise.
"""
import argparse
import json
import re
import sys
from pathlib import Path

COLUMNS = ["printed", "in_artifact", "scope", "artifact", "locator"]
# A reported number: a decimal, a percentage or an integer of two digits or
# more. Single digits are almost always prose ("the three requirements") and
# would drown the coverage list.
REPORTED = re.compile(r"(?<![\w.])(\d+\.\d+|\d{2,})(?![\w.])")


def clean_tex(text):
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
    text = re.sub(r"\\(?:label|ref|eqref|cite|citep|citet|input|include)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|paragraph)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:emph|textbf|textit|texttt|text)\{([^}]*)\}", r"\1", text)
    text = text.replace("~", " ").replace("\\%", "%").replace("$", "")
    return re.sub(r"\s+", " ", text)


def norm(text):
    return re.sub(r"\s+", " ", text).strip().lower()


def source_files(base):
    out = []
    for suffix in ("*.tex", "*.md"):
        out += [p for p in sorted(base.rglob(suffix))
                if not any(part.startswith(".") or part in {"node_modules", "build", "results", "audit"}
                           for part in p.relative_to(base).parts)]
    return out


def sentences(base):
    """[(file, sentence)] over the manuscript prose."""
    out = []
    for path in source_files(base):
        text = clean_tex(path.read_text(encoding="utf-8", errors="replace"))
        for sentence in re.split(r"(?<=[.])\s+(?=[A-Z\\])", text):
            if sentence.strip():
                out.append((str(path.relative_to(base)), sentence.strip()))
    return out


def read_ledger(path):
    rows = []
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return rows
    if lines[0].split("\t")[:len(COLUMNS)] != COLUMNS:
        sys.exit(f"LEDGER_COLUMNS: expected {COLUMNS}, found {lines[0].split(chr(9))}")
    for n, line in enumerate(lines[1:], 2):
        parts = line.split("\t")
        if len(parts) < len(COLUMNS):
            sys.exit(f"LEDGER_COLUMNS: line {n} has {len(parts)} columns, expected {len(COLUMNS)}")
        row = dict(zip(COLUMNS, parts))
        row["line"] = n
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pairs", action="store_true", help="print number/locator pairs for reading")
    ap.add_argument("--allow-empty", action="store_true")
    a = ap.parse_args(argv)
    base = Path(a.base_dir).expanduser().resolve()
    ledger_path = Path(a.ledger).expanduser().resolve()
    if not base.is_dir():
        sys.exit(f"BASE_MISSING: {base}")
    if not ledger_path.is_file():
        sys.exit(f"LEDGER_MISSING: {ledger_path}")

    prose = sentences(base)
    rows = read_ledger(ledger_path)
    findings, pairs = [], []
    ledgered_numbers = set()

    for row in rows:
        where = f"{ledger_path.name}:{row['line']}"
        number = row["printed"].strip()
        in_artifact = row["in_artifact"].strip()
        scope = row["scope"].strip()
        ledgered_numbers.add(number)

        relation = None
        if number == in_artifact:
            relation = "identical"
        else:
            try:
                printed_value, artifact_value = float(number), float(in_artifact)
                if artifact_value and abs(printed_value - artifact_value * 100) < 1e-6:
                    relation = "printed as a percentage of the artifact's proportion"
                elif printed_value and abs(artifact_value - printed_value * 100) < 1e-6:
                    relation = "printed as a proportion of the artifact's percentage"
            except ValueError:
                pass
        if relation is None:
            findings.append({"kind": "printed-artifact-mismatch", "location": where, "number": number,
                             "detail": f"the prose prints {number} and the artifact writes {in_artifact}; "
                                       "record them as equal, or as a proportion and its percentage, or look again"})

        artifact = base / row["artifact"]
        if not artifact.is_file():
            artifact = ledger_path.parent / row["artifact"]
        if not artifact.is_file():
            findings.append({"kind": "artifact-missing", "location": where, "number": number,
                             "detail": f"artifact not found: {row['artifact']}"})
        else:
            text = norm(artifact.read_text(encoding="utf-8", errors="replace"))
            if norm(row["locator"]) not in text:
                findings.append({"kind": "locator-not-in-artifact", "location": where, "number": number,
                                 "detail": f'"{row["locator"][:70]}" is not verbatim in {row["artifact"]}'})
        if in_artifact not in row["locator"]:
            findings.append({"kind": "value-not-in-locator", "location": where, "number": number,
                             "detail": f'the locator "{row["locator"][:60]}" does not carry {in_artifact}'})

        reporting = [(f, s) for f, s in prose if re.search(rf"(?<![\w.]){re.escape(number)}(?![\w.])", s)]
        if not reporting:
            findings.append({"kind": "number-not-in-manuscript", "location": where, "number": number,
                             "detail": f"{number} is no longer reported anywhere in the manuscript"})
        elif scope and scope != "-":
            for f, s in reporting:
                if norm(scope) not in norm(s):
                    findings.append({"kind": "scope-missing", "location": f, "number": number,
                                     "detail": f'reports {number} without "{scope}", which it is only true within: {s[:90]}'})
        pairs.append({"printed": number, "in_artifact": in_artifact, "relation": relation,
                      "scope": scope, "artifact": row["artifact"], "locator": row["locator"]})

    seen = set()
    for f, s in prose:
        for m in REPORTED.finditer(s):
            value = m.group(1)
            if value in ledgered_numbers or (f, value) in seen:
                continue
            seen.add((f, value))
            findings.append({"kind": "unledgered-number", "prompt": True, "location": f, "number": value,
                             "detail": f"reported with no ledger row: {s[:90]}"})

    hard_kinds = {"locator-not-in-artifact", "value-not-in-locator", "printed-artifact-mismatch",
                  "number-not-in-manuscript", "artifact-missing", "scope-missing"}
    hard = [f for f in findings if f["kind"] in hard_kinds]
    nothing = not rows
    payload = {
        "schema_version": 1,
        "base": str(base),
        "ledger": str(ledger_path),
        "prose_sentences": len(prose),
        "ledger_rows": len(rows),
        "findings": findings,
        "hard_finding_count": len(hard),
        "unledgered_count": sum(1 for f in findings if f["kind"] == "unledgered-number"),
        "nothing_checked": nothing,
        "limits": {
            "derivation": "not decided here: whether the artifact is the right one, or whether the number is correctly derived from it. This checks that the printed value is a value written in a file, under the scope the ledger records.",
            "coverage": "unledgered-number ignores single digits, so counts written as words or as one digit are invisible to it",
            "scope": "matched literally: a sentence that carries the scope in other words is flagged, so the token has to be one the correct sentences contain",
        },
    }
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        unledgered = payload["unledgered_count"]
        covered = len(rows) + unledgered
        print(f"number ledger: {len(rows)} row(s) against {len(prose)} sentence(s) under {base}")
        print(f"coverage: {len(rows)} of {covered} reported number(s) carry a row; "
              f"{unledgered} do not, and nothing here checks them")
        for kind in ["locator-not-in-artifact", "value-not-in-locator", "printed-artifact-mismatch",
                     "number-not-in-manuscript", "artifact-missing", "scope-missing", "unledgered-number"]:
            group = [f for f in findings if f["kind"] == kind]
            if not group:
                continue
            print(f"\n{kind}{' (prompt, not a finding)' if group[0].get('prompt') else ''} ({len(group)})")
            for f in group[:40]:
                print(f"  {f['location']}  [{f['number']}]\n    {f['detail']}")
            if len(group) > 40:
                print(f"  … {len(group) - 40} more")
        if nothing:
            print("\nNOTHING CHECKED: no ledger row. This is not a pass.")
        print(f"\nNot decided here: {payload['limits']['derivation']}")
    if a.pairs:
        for p in pairs:
            print(f"\n[{p['printed']} printed · {p['in_artifact']} in the artifact · {p['relation']}]"
                  f"\n  scope:    {p['scope']}\n  artifact: {p['artifact']}\n  locator:  {p['locator']}")
    return 1 if hard else (2 if nothing and not a.allow_empty else 0)


if __name__ == "__main__":
    sys.exit(main())
