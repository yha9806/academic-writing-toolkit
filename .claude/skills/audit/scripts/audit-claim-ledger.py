#!/usr/bin/env python3
"""Claim ledger audit for LaTeX manuscripts.

    python3 audit-claim-ledger.py --base-dir <manuscript> --ledger <ledger.tsv> [--json] [--pairs] [--allow-empty]

The gap this closes: the citation fidelity audit reads `chapters/**/*.md`
against reading notes. A LaTeX manuscript's claims about its sources were
checked by nothing at all.

A ledger row binds one manuscript sentence to one verbatim snippet in one
archived source, and the audit checks that binding in both directions:

  snippet-not-in-source          the snippet is not verbatim in the archived source
  claim-not-in-manuscript        the sentence was edited; the binding is stale
  key-not-in-claim-sentence      the row names a key the sentence does not cite
  source-file-missing            the archived source is not on disk
  negative-claim-without-fulltext  "X did not do Y" recorded against an abstract
  unledgered-assertion           a citing sentence that asserts something about
                                 its source and has no ledger row
  qualifier-dropped              PROMPT: a hedge in the snippet that the claim
                                 does not carry ("expected", "some", "may")

What it does NOT do: judge whether a claim says more than its snippet in
words the snippet never used. Machine judgement of that was measured on a
small red-check set: with the claim and its passage paired it caught 7 of 8,
and it missed a dropped "expected" every time. So the audit binds and prompts;
a reader still decides. `--pairs` prints claim/snippet pairs for that reading.

Exit: 1 on a hard finding, 2 when no ledger row was checked at all (an empty
ledger verifies nothing, whatever the coverage list says) unless --allow-empty,
0 otherwise.
"""
import argparse
import json
import re
import sys
from pathlib import Path

COLUMNS = ["claim", "cite_key", "snippet", "source_file", "level"]
LEVELS = {"fulltext", "abstract-only", "metadata"}
# Verbs that make a citing sentence a claim about its source rather than a
# credit line ("we use X~\cite{y}").
REPORTING = re.compile(
    r"\b(show|shows|showed|shown|find|finds|found|report|reports|reported|document|documents|documented"
    r"|demonstrate\w*|establish\w*|catalogu\w*|argue\w*|observe[sd]?|note[sd]?|propose[sd]?|examine[sd]?"
    r"|conclude[sd]?|reveal\w*|suggest\w*|claim[sd]?|describe[sd]?|warn[sd]?)\b", re.I)
NEGATIVE = re.compile(
    r"\b(did not|does not|do not|never|no prior|nobody|none of|neither|is not|are not|was not|were not"
    r"|first to|the only)\b", re.I)
HEDGE = ["expected", "may", "might", "can", "could", "some", "many", "often", "typically", "likely",
         "possibly", "approximately", "about", "partly", "partially", "only", "largely", "mostly"]
CITE = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")


def clean_tex(text):
    text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
    text = re.sub(r"\\(?:label|ref|eqref|input|include)\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:section|subsection|subsubsection|paragraph)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:emph|textbf|textit|texttt|text)\{([^}]*)\}", r"\1", text)
    text = text.replace("~", " ").replace("--", "-").replace("\\%", "%")
    return re.sub(r"\s+", " ", text)


def norm(text):
    """Whitespace, hyphenated line breaks and quotation marks normalised for matching."""
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.replace("\u2019", "'").replace("\u2018", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = text.replace("--", "-").replace("\u2013", "-").replace("\u2014", "-")
    return re.sub(r"\s+", " ", text).strip().lower()


def tex_files(base):
    return [p for p in sorted(base.rglob("*.tex"))
            if not any(part.startswith(".") or part in {"node_modules", "build"} for part in p.relative_to(base).parts)]


def citing_sentences(base):
    """[(file, sentence, keys)] for every sentence that carries a \\cite."""
    out = []
    for path in tex_files(base):
        text = clean_tex(path.read_text(encoding="utf-8", errors="replace"))
        for sentence in re.split(r"(?<=[.])\s+(?=[A-Z\\])", text):
            keys = [k.strip() for group in CITE.findall(sentence) for k in group.split(",") if k.strip()]
            if keys:
                out.append((str(path.relative_to(base)), sentence.strip(), keys))
    return out


def read_ledger(path):
    rows = []
    lines = [l.rstrip("\n") for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not lines:
        return rows
    header = lines[0].split("\t")
    if header[:len(COLUMNS)] != COLUMNS:
        sys.exit(f"LEDGER_COLUMNS: expected {COLUMNS}, found {header}")
    for n, line in enumerate(lines[1:], 2):
        parts = line.split("\t")
        if len(parts) < len(COLUMNS):
            sys.exit(f"LEDGER_COLUMNS: line {n} has {len(parts)} columns, expected {len(COLUMNS)}")
        row = dict(zip(COLUMNS, parts))
        row["line"] = n
        if row["level"] not in LEVELS:
            sys.exit(f"LEDGER_LEVEL: line {n} has level {row['level']!r}, expected one of {sorted(LEVELS)}")
        rows.append(row)
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-dir", default=".")
    ap.add_argument("--ledger", required=True)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--pairs", action="store_true", help="print claim/snippet pairs for reading")
    ap.add_argument("--allow-empty", action="store_true")
    a = ap.parse_args(argv)
    base = Path(a.base_dir).expanduser().resolve()
    ledger_path = Path(a.ledger).expanduser().resolve()
    if not base.is_dir():
        sys.exit(f"BASE_MISSING: {base}")
    if not ledger_path.is_file():
        sys.exit(f"LEDGER_MISSING: {ledger_path}")

    sentences = citing_sentences(base)
    rows = read_ledger(ledger_path)
    findings, pairs = [], []

    for row in rows:
        loc = f"{ledger_path.name}:{row['line']}"
        claim_n = norm(row["claim"])
        bound = [(f, s, k) for f, s, k in sentences if claim_n and claim_n in norm(s)]
        if not bound:
            findings.append({"kind": "claim-not-in-manuscript", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"the ledger's claim is not a sentence in the manuscript: {row['claim'][:90]}"})
        elif row["cite_key"] not in {k for _, _, keys in bound for k in keys}:
            findings.append({"kind": "key-not-in-claim-sentence", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"the bound sentence does not cite {row['cite_key']}"})
        source = (base / row["source_file"]) if not Path(row["source_file"]).is_absolute() else Path(row["source_file"])
        if not source.is_file():
            source = ledger_path.parent / row["source_file"]
        if not source.is_file():
            findings.append({"kind": "source-file-missing", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"archived source not found: {row['source_file']}"})
        else:
            text = norm(source.read_text(encoding="utf-8", errors="replace"))
            if norm(row["snippet"]) not in text:
                findings.append({"kind": "snippet-not-in-source", "location": loc, "cite_key": row["cite_key"],
                                 "detail": f'"{row["snippet"][:90]}" is not verbatim in {row["source_file"]}'})
        if NEGATIVE.search(row["claim"]) and row["level"] != "fulltext":
            findings.append({"kind": "negative-claim-without-fulltext", "location": loc, "cite_key": row["cite_key"],
                             "detail": f"a negative claim recorded against level={row['level']}; read the full text or scope the sentence to what was read"})
        dropped = [h for h in HEDGE
                   if re.search(rf"\b{re.escape(h)}\b", row["snippet"], re.I)
                   and not re.search(rf"\b{re.escape(h)}\b", row["claim"], re.I)]
        if dropped:
            findings.append({"kind": "qualifier-dropped", "prompt": True, "location": loc, "cite_key": row["cite_key"],
                             "detail": f"the snippet hedges with {dropped}; the claim does not — read the pair before trusting it"})
        pairs.append({"cite_key": row["cite_key"], "claim": row["claim"], "snippet": row["snippet"],
                      "source_file": row["source_file"], "level": row["level"]})

    ledgered = {norm(r["claim"]) for r in rows if norm(r["claim"])}
    for f, s, keys in sentences:
        if any(c and c in norm(s) for c in ledgered):
            continue
        kind = "unledgered-assertion" if REPORTING.search(s) else "unledgered-credit"
        findings.append({"kind": kind, "prompt": kind == "unledgered-credit", "location": f,
                         "cite_key": ",".join(keys),
                         "detail": f"{'asserts something about' if kind == 'unledgered-assertion' else 'credits'} {','.join(keys)} with no ledger row: {s[:90]}"})

    hard_kinds = {"snippet-not-in-source", "claim-not-in-manuscript", "key-not-in-claim-sentence",
                  "source-file-missing", "negative-claim-without-fulltext"}
    hard = [f for f in findings if f["kind"] in hard_kinds]
    # Nothing verified is not a pass: an empty ledger over a citing manuscript
    # produces a coverage list and no verification at all.
    nothing = not rows
    payload = {
        "schema_version": 1,
        "base": str(base),
        "ledger": str(ledger_path),
        "citing_sentences": len(sentences),
        "ledger_rows": len(rows),
        "findings": findings,
        "hard_finding_count": len(hard),
        "nothing_checked": nothing,
        "limits": {
            "semantic_overreach": "NOT decided here: a claim that says more than its snippet in words the snippet never used passes every check. Measured on a small red-check set, a paired machine judge caught 7 of 8 and missed a dropped 'expected' every time; read the pairs.",
            "coverage": "unledgered-assertion uses a reporting-verb heuristic, so it both misses claims phrased without one and flags some credit lines",
        },
    }
    if a.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"claim ledger: {len(rows)} row(s) against {len(sentences)} citing sentence(s) under {base}")
        for kind in ["snippet-not-in-source", "claim-not-in-manuscript", "key-not-in-claim-sentence",
                     "source-file-missing", "negative-claim-without-fulltext", "unledgered-assertion",
                     "qualifier-dropped", "unledgered-credit"]:
            group = [f for f in findings if f["kind"] == kind]
            if not group:
                continue
            print(f"\n{kind}{' (prompt, not a finding)' if group[0].get('prompt') else ''} ({len(group)})")
            for f in group:
                print(f"  {f['location']}\n    {f['detail']}")
        if nothing:
            print("\nNOTHING CHECKED: no citing sentence and no ledger row. This is not a pass.")
        print(f"\nNot decided here: {payload['limits']['semantic_overreach']}")
    if a.pairs:
        for p in pairs:
            print(f"\n[{p['cite_key']} · {p['level']}]\n  claim:   {p['claim']}\n  snippet: {p['snippet']}\n  source:  {p['source_file']}")
    return 1 if hard else (2 if nothing and not a.allow_empty else 0)


if __name__ == "__main__":
    sys.exit(main())
