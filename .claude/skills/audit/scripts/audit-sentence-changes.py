#!/usr/bin/env python3
"""Check each rewritten sentence against the sentence it replaced, and against the venue's own sentences.

    python3 audit-sentence-changes.py --target <file or dir> --base <file or dir> [--baseline <dir>] [--json]
    python3 audit-sentence-changes.py --pairs <tsv with columns id, old, new> [--baseline <dir>] [--json]

audit-prose-fingerprint.py and audit-prose-structure.py measure a whole document: rates per 1,000 words and
distributions across sections. A dozen rewritten sentences barely move those rates, and neither audit reads a
proposal that has not yet been applied. On one real round of proposed corrections most rewrites came back longer
than the sentences they replaced, several added an explanatory colon or a semicolon (the construction the venue
audit had already flagged in that manuscript), and two added a relative clause. Neither document audit could see
it: the rewrites sat in a separate file, and once applied they were a few sentences in fifteen thousand words.

So this reads sentences one at a time, and only the ones that changed. A sentence of the target that does not occur
in the base is a change. It is paired with the most similar base sentence that no longer occurs (a revision) or
stands alone (an addition). For a revision it reports what the rewrite added: words, a colon, a semicolon, a dash,
a parenthesis, a subordinate clause, an -ly adverb, prepositional phrases, a subordinate opener. With --baseline
it also places every changed sentence in the venue's distribution of sentences, pooled across its documents
(one sentence's length is compared with published sentences, not with published documents).

The --pairs form is for proposals: run it on the rewrites before anyone reads them. A rewrite that splits one
sentence into several is judged piece by piece against the sentence it replaces. The --target/--base form is
for a draft after the edit; the writing loop runs it on every commit against the previous version.

"that" is not counted as a clause, for the reason audit-prose-structure.py gives. Prepositions stand in for the
noun-modifier load a parser would measure; "to" and "as" are left out because they are mostly not prepositions.
The flags are prompts to re-read a sentence, not targets: a revision may need a clause to stay faithful to its
source, and then the flag is the reason to check that it earns it.

Exit: 0 no changed sentence is flagged (including no change at all, reported as such); 1 at least one flagged;
2 nothing to compare (no prose in the target or the base, an empty pairs file, a baseline too small to give
percentiles) or an argument it does not recognise.
"""
import argparse
import csv
import difflib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUB = re.compile(r"\b(?:which|where|when|while|whereas|although|though|because|since|unless|whether|if|after|"
                 r"before|until|who|whom|whose)\b", re.I)
OPENER = re.compile(r"^(?:Where|When|If|Whether|Although|Though|While|Because|Since|Unless|Once|Whereas)\b")
PREP = re.compile(r"\b(?:of|in|for|with|by|between|from|on|at|into|across|against|within|without|under|over|"
                  r"through|about|among|beyond|via)\b", re.I)
LY = re.compile(r"\b[A-Za-z]{3,}ly\b")
NOT_ADVERB = {"only", "early", "family", "apply", "supply", "reply", "rely", "assembly", "anomaly", "italy", "july",
              "daily", "weekly", "monthly", "yearly", "ply", "multiply", "comply", "imply", "poly", "holy", "belly",
              "rally", "tally", "ally", "fly", "jelly", "bully", "lily", "folly"}
DASH = re.compile(r"---|—|\s--\s|\s–\s")
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")
FEATURES = ["words", "clauses", "commas", "colons", "semicolons", "dashes", "parentheses", "adverbs",
            "prepositions", "opener"]
# A revision is "longer" when it gains at least this many words and this share.
LONGER_WORDS, LONGER_SHARE = 5, 0.20
# Prepositional phrases gained before a revision is flagged: one is often the fact the correction adds.
MORE_PREPOSITIONS = 2
MATCH_MIN = 0.40
VENUE_PCT = 90
FP = None
MIN_VENUE_SENTENCES = 1000
MIN_VENUE_DOCUMENTS = 5


def die(msg):
    sys.stderr.write(f"audit-sentence-changes: {msg}\n")
    sys.exit(2)


def fingerprint():
    path = HERE / "audit-prose-fingerprint.py"
    if not path.is_file():
        die(f"the fingerprint audit is not beside this script ({path}); both must read prose the same way")
    spec = importlib.util.spec_from_file_location("fingerprint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sentences(text):
    return [s.strip() for s in SPLIT.split(re.sub(r"\s+", " ", text or "")) if len(s.split()) >= 3]


def features(s):
    return {
        "words": len(s.split()),
        "clauses": len(SUB.findall(s)),
        "commas": s.count(","),
        "colons": len(re.findall(r":(?!\d)", s)),
        "semicolons": s.count(";"),
        "dashes": len(DASH.findall(s)),
        "parentheses": s.count("("),
        "adverbs": sum(1 for w in LY.findall(s) if w.lower() not in NOT_ADVERB),
        "prepositions": len(PREP.findall(s)),
        "opener": 1 if OPENER.match(s) else 0,
    }


def read_prose(fp, path):
    """{file: [sentences]} for a file, or for every prose file under a directory. Directories whose names start with
    a dot are skipped: the loop puts the previous version beside the draft in one."""
    path = Path(path)
    files = [path] if path.is_file() else sorted(
        p for p in path.rglob("*") if p.is_file() and not any(part.startswith(".") for part in p.relative_to(path).parts))
    out = {}
    for p in files:
        if p.suffix.lower() not in fp.TEXT_SUFFIXES:
            continue
        t = fp.load(p)
        if t and t.strip():
            out[p.name if path.is_file() else str(p.relative_to(path))] = sentences(t)
    return out


def norm(s):
    return re.sub(r"\s+", " ", s).strip().lower()


def pair_changes(target, base):
    """[(file, old or None, new)] for every target sentence that does not occur in the base."""
    base_all = {norm(s) for ss in base.values() for s in ss}
    target_all = {norm(s) for ss in target.values() for s in ss}
    removed = {f: [s for s in ss if norm(s) not in target_all] for f, ss in base.items()}
    pool = [(f, s) for f, ss in removed.items() for s in ss]
    used = set()
    out = []
    for f, ss in target.items():
        for s in ss:
            if norm(s) in base_all:
                continue
            best, score = None, 0.0
            words = s.split()
            # prefer the same file, then anywhere
            for pf, ps in sorted(pool, key=lambda x: x[0] != f):
                if (pf, ps) in used:
                    continue
                r = difflib.SequenceMatcher(None, words, ps.split(), autojunk=False).ratio()
                if r > score:
                    best, score = (pf, ps), r
            if best and score >= MATCH_MIN:
                used.add(best)
                out.append((f, best[1], s))
            else:
                out.append((f, None, s))
    return out, sum(len(v) for v in removed.values()) - len(used)


def prose(cell):
    """A proposal is usually written in the draft's markup; read it the way the draft is read."""
    cell = (cell or "").strip()
    if "\\" in cell or "~" in cell or "$" in cell:
        cell = FP.strip_markup(cell, ".tex")
    return re.sub(r"\s+", " ", cell).strip()


def read_pairs(path):
    rows = []
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            if not {"id", "old", "new"} <= set(r):
                die(f"{path}: the header must name the columns id, old, new")
            if (r["new"] or "").strip():
                rows.append((r["id"], prose(r["old"]) or None, prose(r["new"])))
    return rows


def venue_distribution(fp, baseline):
    docs = fp.collect(Path(baseline))
    kept, sents = 0, []
    for _, text, _ in docs:
        if hasattr(fp, "word_share") and fp.word_share(text) < getattr(fp, "MIN_WORD_SHARE", 0.3):
            continue
        ss = [s for s in sentences(text) if 5 <= len(s.split()) <= 120]
        if ss:
            kept += 1
            sents.extend(ss)
    if kept < MIN_VENUE_DOCUMENTS or len(sents) < MIN_VENUE_SENTENCES:
        die(f"the baseline {baseline} gave {len(sents)} sentences from {kept} documents; percentiles need at least "
            f"{MIN_VENUE_SENTENCES} sentences from {MIN_VENUE_DOCUMENTS} documents")
    cols = {k: sorted(features(s)[k] for s in sents) for k in FEATURES}
    return {"documents": kept, "sentences": len(sents), "columns": cols}


def percentile(col, x):
    below = sum(1 for v in col if v < x)
    equal = sum(1 for v in col if v == x)
    return round(100 * (below + equal / 2) / len(col))


def at(col, pct):
    return col[int(pct / 100 * (len(col) - 1))]


def judge(old, new, venue):
    fn = features(new)
    fo = features(old) if old else None
    flags = []
    if fo:
        if fn["words"] - fo["words"] >= LONGER_WORDS and fn["words"] >= fo["words"] * (1 + LONGER_SHARE):
            flags.append("longer")
        for k, name in (("colons", "colon"), ("semicolons", "semicolon"), ("dashes", "dash"),
                        ("parentheses", "parenthesis"), ("clauses", "clause"), ("adverbs", "adverb")):
            if fn[k] > fo[k]:
                flags.append(name)
        if fn["prepositions"] - fo["prepositions"] >= MORE_PREPOSITIONS:
            flags.append("prepositions")
        if fn["opener"] and not fo["opener"]:
            flags.append("opener")
    else:
        for k, name in (("colons", "colon"), ("semicolons", "semicolon"), ("dashes", "dash")):
            if fn[k]:
                flags.append(name)
    pct = {}
    if venue:
        cols = venue["columns"]
        pct = {k: percentile(cols[k], fn[k]) for k in ("words", "clauses", "commas", "prepositions")}
        grew = fo is None or fn["words"] > fo["words"]
        if fn["words"] > at(cols["words"], VENUE_PCT) and grew:
            flags.append("long_for_venue")
        dense = [k for k in ("clauses", "commas", "prepositions") if fn[k] > at(cols[k], VENUE_PCT)]
        if dense and (fo is None or any(fn[k] > fo[k] for k in dense)):
            flags.append("dense_for_venue")
    return {"old": old, "new": new, "kind": "revised" if old else "added", "features_old": fo, "features_new": fn,
            "venue_percentile": pct, "flags": flags}


def main():
    ap = argparse.ArgumentParser(description="Check rewritten sentences one by one.")
    ap.add_argument("--target")
    ap.add_argument("--base")
    ap.add_argument("--pairs")
    ap.add_argument("--baseline")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    global FP
    fp = FP = fingerprint()
    removed = 0
    if a.pairs:
        if a.target or a.base:
            die("give --pairs, or --target with --base, not both")
        if not Path(a.pairs).is_file():
            die(f"no pairs file at {a.pairs}")
        rows = read_pairs(a.pairs)
        if not rows:
            die(f"{a.pairs} holds no rewritten sentence")
        changes = [(rid, old, new) for rid, old, new in rows if old is None or norm(old) != norm(new)]
        compared = {"pairs": len(rows)}
    else:
        if not (a.target and a.base):
            die("give --target and --base (the version before the edit), or --pairs")
        target = read_prose(fp, a.target) if Path(a.target).exists() else {}
        base = read_prose(fp, a.base) if Path(a.base).exists() else {}
        if not any(target.values()):
            die(f"no prose in the target {a.target}")
        if not any(base.values()):
            die(f"no prose in the base {a.base}: nothing to compare the draft with")
        changes, removed = pair_changes(target, base)
        compared = {"target_sentences": sum(map(len, target.values())), "base_sentences": sum(map(len, base.values()))}
    venue = venue_distribution(fp, a.baseline) if a.baseline else None
    results = []
    for where, old, new in changes:
        pieces = sentences(new) if a.pairs else [new]
        if len(pieces) > 1:
            # A rewrite that splits one sentence into several is judged piece by piece against the old one: each
            # new sentence must not carry more than the sentence it came from.
            parts = [judge(old, piece, venue) for piece in pieces]
            r = judge(old, new, venue)
            r["pieces"] = parts
            r["flags"] = sorted({f for part in parts for f in part["flags"]})
        else:
            r = judge(old, new, venue)
        r["where"] = where
        results.append(r)
    flagged = [r for r in results if r["flags"]]
    compared.update({"changed": len(results), "revised": sum(r["kind"] == "revised" for r in results),
                     "added": sum(r["kind"] == "added" for r in results), "removed": removed})
    out = {"schema_version": 1, "compared": compared, "changed": len(results), "flagged": len(flagged),
           "venue": ({"documents": venue["documents"], "sentences": venue["sentences"],
                      "p90": {k: at(venue["columns"][k], VENUE_PCT) for k in ("words", "clauses", "commas",
                                                                               "prepositions")}}
                     if venue else None),
           "sentences": results,
           "issues": [{"where": r["where"], "flags": r["flags"], "new": r["new"]} for r in flagged]}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(f"changed sentences: {len(results)} ({compared['revised']} revised, {compared['added']} added); "
              f"flagged: {len(flagged)}")
        if venue:
            print(f"venue: {venue['sentences']} sentences from {venue['documents']} documents; p90 "
                  + ", ".join(f"{k} {v}" for k, v in out["venue"]["p90"].items()))
        for r in flagged:
            fo, fn = r["features_old"], r["features_new"]
            size = f"{fo['words']}->{fn['words']} words" if fo else f"{fn['words']} words, added"
            print(f"\n[{r['where']}] {', '.join(r['flags'])}  ({size})")
            if r["old"]:
                print(f"  was: {r['old']}")
            print(f"  now: {r['new']}")
        if not results:
            print("no sentence changed")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
