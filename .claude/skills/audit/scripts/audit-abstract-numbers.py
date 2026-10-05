#!/usr/bin/env python3
"""Abstract numbers: how many quantities the abstract carries, against the abstracts its venue publishes.

    python3 audit-abstract-numbers.py --baseline <dir> [--json] <draft file> [<draft file> ...]

An author asked that an abstract not carry too many numbers, after a revision had rewritten one to hold nearly twice
as many quantities as any abstract in its venue's corpus, and more than twice as many per word. The prose
fingerprint measures the whole manuscript and the number ledger checks whether each number is right; neither asks
whether the abstract should hold it.

A quantity is a number not attached to letters: 0.85, 23%, 2,417, and 12.5x or 12.5× as a multiple. Names with
digits (BM25, GPT-4o, Recall@10) and four-digit years are counted apart. List markers ((1), (ii), 1)), numbered
citations ([62]) and calendar dates are removed first, on both sides. A regex cannot tell a result from a sample
size, so the count is "quantities in the abstract", not "result numbers": on fourteen hand-classified abstracts it
found every number classed as a result, and counted the setup numbers too. Which ones carry the main finding is the
author's call; the report lists each with its context and does not choose.

Baseline: a directory of the venue's papers (PDF through pdftotext, or text). Each abstract is found the same way as
the target's, measured on its own, and an abstract the extractor cannot find is listed as missed, never counted as
zero. Fewer than --min-baseline abstracts is no baseline.

Known bias, repeated in the output: PDF text can keep running-header numbers and spelled-out list markers the
cleaning does not catch, so the corpus side is overestimated and the prompt fires late, not early.

Exit: 0 at or below the 90th percentile on both count and count per 100 words; 1 above it on either (a prompt to
read, not a failure); 2 nothing to measure (no abstract in the draft, a thin baseline, pdftotext missing for PDFs)
or an argument it does not recognise.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

MIN_BASELINE = 20
CONTEXT_WORDS = 5

# A figure not attached to a word, a path or a metric name: 7, 2,417, 12.5, 12.5%, 12.5x. Recall@10 and COVID-19
# are names. Without the x a "12.5x" would backtrack to a quantity "12" and a name "5x".
QTY = re.compile(r"(?<![\w@./\-])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s?%|[x×])?(?![\w/\-])")
NAME = re.compile(r"[A-Za-z][A-Za-z\-/]*@?\d|@\d|\d+[A-Za-z]")
YEAR = re.compile(r"^(?:19|20)\d\d$")
MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
         r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
MARKERS = [
    re.compile(r"\[\s*\d+(?:\s*[,\u2013\-]\s*\d+)*\s*\]"),                    # [62] [3, 7] [4-6]: citations
    re.compile(r"\(\s*(?:\d{1,2}|[ivx]{1,4}|[a-h])\s*\)"),                 # (1) (ii) (a)
    re.compile(r"(?:(?<=^)|(?<=[\s;:,]))(?:\d{1,2}|[ivx]{1,4})\)"),          # 1) ii)
    re.compile(MONTH + r"\.?\s+\d{1,2},?\s+(?:19|20)\d\d"),                  # March 28, 2019
    re.compile(r"\b\d{1,2}\s+" + MONTH + r"\.?\s+(?:19|20)\d\d"),            # 28 March 2019
]
WORD = re.compile(r"[A-Za-z]+(?:['\-][A-Za-z]+)*")
# Where a paper's abstract ends: the next block a PDF's first pages carry. "A BSTRACT" is small caps set letter by
# letter, a heading the first measurement missed.
HEAD = re.compile(r"(?i)\ba ?bstract\b[\s.:\u2014\-]*")
# A newline first: the stop is never the heading's own line (on a two-column page the left column's "Keywords" can
# share it).
STOP = re.compile(r"(?i)\n\s*(?:key\s?words?|index terms|ccs concepts|(?:1|i)\.?\s+introduction|introduction)\b")
MD_STOP = re.compile(r"^(?:#|\d+(?:\.\d+)*\s+\S|key\s?words?\b)", re.I)
TEX_ABSTRACT = re.compile(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", re.S)
NOTE = ("PDF text can keep running-header numbers and list markers the cleaning does not catch: the corpus side is "
        "overestimated, so the prompt fires late, not early. Names with digits and years are not quantities.")


def die(msg: str) -> int:
    sys.stderr.write(f"audit-abstract-numbers: {msg}\n")
    return 2


def plain_tex(t: str) -> str:
    t = re.sub(r"(?<!\\)%.*", "", t)
    t = re.sub(r"\\(?:cite[tp]?|citeauthor|ref|eqref|autoref|cref|Cref|label)\*?(?:\[[^\]]*\])*\{[^}]*\}", "", t)
    t = t.replace("{,}", ",").replace("\\%", "%").replace("~", " ").replace("\\,", " ")
    t = re.sub(r"\\times\b", "\u00d7", t)
    t = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", " ", t)
    t = t.replace("{", "").replace("}", "").replace("$", "")
    return re.sub(r"\s+", " ", t).strip()


def md_abstract(text: str) -> Optional[str]:
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if re.match(r"^\s*(?:#+\s*)?(?:\*\*)?abstract(?:\*\*)?\s*[:.]?\s*$", ln, re.I):
            body = []
            for nxt in lines[i + 1:]:
                if MD_STOP.match(nxt.strip()):
                    break
                body.append(nxt)
            got = re.sub(r"\s+", " ", " ".join(body)).strip()
            return got or None
    return None


def draft_abstract(path: Path) -> Optional[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".tex":
        m = TEX_ABSTRACT.search(text)
        return plain_tex(m.group(1)) if m else None
    return md_abstract(text)


def pdf_text(path: Path) -> str:
    r = subprocess.run(["pdftotext", "-l", "2", "-layout", str(path), "-"], capture_output=True, text=True)
    return r.stdout


def paper_abstract(text: str) -> Optional[str]:
    flat = re.sub(r"[ \t]+", " ", text)
    m = HEAD.search(flat)
    if not m:
        return None
    rest = flat[m.end():]
    s = STOP.search(rest, 1)
    if not s:
        return None
    got = re.sub(r"\s+", " ", rest[:s.start()]).strip()
    n = len(got.split())
    return got if 40 <= n <= 600 else None


def measure(text: str) -> Dict:
    for rx in MARKERS:
        text = rx.sub(" ", text)
    words = WORD.findall(text)
    found = []
    for m in QTY.finditer(text):
        before = WORD.findall(text[:m.start()])[-CONTEXT_WORDS:]
        after = WORD.findall(text[m.end():])[:CONTEXT_WORDS]
        found.append({"text": m.group(0), "context": " ".join(before + ["[" + m.group(0) + "]"] + after)})
    years = [q for q in found if YEAR.match(q["text"])]
    qty = [q for q in found if not YEAR.match(q["text"])]
    names = NAME.findall(QTY.sub(" ", text))  # a quantity is not also a name
    return {"words": len(words), "qty": len(qty), "per100": round(100.0 * len(qty) / max(len(words), 1), 2),
            "years": len(years), "names_with_digits": len(names), "quantities": qty}


def percentile(v: float, xs: List[float]) -> float:
    below = sum(1 for x in xs if x < v)
    ties = sum(1 for x in xs if x == v)
    return round(100.0 * (below + 0.5 * ties) / len(xs), 1)


def nearest_rank(xs: List[float], p: float) -> float:
    s = sorted(xs)
    return s[int(p * (len(s) - 1))]


def summary_of(xs: List[float]) -> Dict:
    s = sorted(xs)
    mid = len(s) // 2
    median = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    return {"min": s[0], "median": median, "p90": nearest_rank(s, 0.9), "max": s[-1]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Quantities in the abstract against the venue's abstracts.")
    ap.add_argument("drafts", nargs="*", help="draft files (.tex or .md); the first abstract found is measured")
    ap.add_argument("--baseline", required=True, help="directory of the venue's papers (.pdf or .txt)")
    ap.add_argument("--min-baseline", type=int, default=MIN_BASELINE)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    found = []
    for d in a.drafts:
        p = Path(d)
        if p.is_file() and p.suffix.lower() in {".tex", ".md", ".txt"}:
            got = draft_abstract(p)
            if got:
                found.append((str(d), got))
    if not found:
        return die("no abstract found in the draft (\\begin{abstract} in LaTeX, an 'Abstract' heading in Markdown); "
                   "nothing measured is not a pass")

    base = Path(a.baseline).expanduser()
    files = sorted(p for p in base.iterdir() if p.is_file() and p.suffix.lower() in {".pdf", ".txt"}) \
        if base.is_dir() else []
    if any(p.suffix.lower() == ".pdf" for p in files) and not shutil.which("pdftotext"):
        return die("the baseline holds PDFs and pdftotext is not on PATH")
    rows, missed = [], []
    for p in files:
        text = pdf_text(p) if p.suffix.lower() == ".pdf" else p.read_text(encoding="utf-8", errors="replace")
        ab = paper_abstract(text)
        if ab is None:
            missed.append(p.name)
            continue
        m = measure(ab)
        rows.append({"file": p.name, "words": m["words"], "qty": m["qty"], "per100": m["per100"]})
    if len(rows) < a.min_baseline:
        return die(f"{len(rows)} baseline abstracts extracted ({len(missed)} missed) under {base}; "
                   f"no percentile below {a.min_baseline}")

    file, text = found[0]
    m = measure(text)
    q = [r["qty"] for r in rows]
    p100 = [r["per100"] for r in rows]
    m["pct_qty"] = percentile(m["qty"], q)
    m["pct_per100"] = percentile(m["per100"], p100)
    m["file"] = file
    corpus = {"n": len(rows), "missed": missed, "qty": summary_of(q), "per100": summary_of(p100), "rows": rows}
    above = [k for k, pct in (("qty", m["pct_qty"]), ("per100", m["pct_per100"])) if pct > 90]
    findings = []
    if above:
        findings.append({"kind": "abstract-numbers-above-venue", "above": above,
                         "ask": "which of these quantities carry the main finding? the rest can go to the body"})
    cq = corpus["qty"]
    head = (f"摘要 {m['qty']} 个量（每百词 {m['per100']}），刊物 {len(rows)} 篇摘要中位 {cq['median']}、"
            f"P90 {cq['p90']}、最多 {cq['max']}；第 {m['pct_qty']} 百分位")
    summary = head + ("：超过 P90，请看哪几个是主结果" if above else "")
    out = {"abstract": m, "also_found": [f for f, _ in found[1:]], "corpus": corpus, "findings": findings,
           "summary_zh": summary, "note": NOTE}
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        print(summary)
        for item in m["quantities"]:
            print(f"  {item['text']:>10}  {item['context']}")
        if missed:
            print(f"  baseline abstracts missed: {len(missed)}")
        print("  " + NOTE)
    return 1 if above else 0


if __name__ == "__main__":
    sys.exit(main())
