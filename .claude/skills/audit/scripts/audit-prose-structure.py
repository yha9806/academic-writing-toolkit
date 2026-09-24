#!/usr/bin/env python3
"""Audit sentence structure against a baseline corpus: what makes prose hard to read that punctuation counts miss.

    python3 audit-prose-structure.py --target <file or dir> --baseline <dir> [--exclude GLOB ...] [--json]

audit-prose-fingerprint.py counts marks. This counts structure. On a real manuscript every mark-based rate sat in the
published range while readers still called the prose hard: the sentences were shorter than most published papers',
and carried more subordinate clauses per comma than any of them. A sentence that makes the reader hold a condition
before the claim, or a clause between subject and verb, is hard at any length.

Measured per document:
  median_len       median sentence length in words
  long_share       share of words in sentences of 35 words or more
  sub_per_100w     subordinate clauses per 100 words
  sub_per_comma    subordinate clauses per comma: the same structure with fewer places to breathe
  comma_per_100w   commas per 100 words
  dash_per_100w    em dashes per 100 words
  opens_with_sub   share of sentences that open with a subordinator (Where / When / If / Whether / Although ...)
  length_lag1      lag-1 autocorrelation of sentence length (published prose is positive: long sentences cluster)

"that" is not counted: it is a determiner, a complementiser and a relativiser, and telling them apart needs a
parser; counting it inflates whichever side one set out to find. Every subordinator below is unambiguous.

Text is read by audit-prose-fingerprint.py's own `load` (markup stripped from .tex/.md, pdftotext for PDFs), so the
two audits read the same prose. A target that is a directory is read whole, every file joined; each baseline
document is measured on its own, never pooled, and is kept only with 25 sentences or more.

Output: each metric with the baseline's min / median / max and the target's percentile; `outliers` names the ones
outside the baseline's range. These are measurements, not targets: edit a sentence because it is hard to read,
not to move a number.

Exit: 0 inside the range on every metric; 1 at least one outside; 2 nothing to measure (no target prose, fewer
baseline documents than --min-baseline, the fingerprint reader missing) or an argument it does not recognise.
"""
import argparse
import fnmatch
import importlib.util
import json
import re
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SUB = re.compile(r"\b(?:which|where|when|while|whereas|although|though|because|since|unless|whether|if|after|"
                 r"before|until|who|whom|whose)\b", re.I)
OPENER = re.compile(r"^(?:Where|When|If|Whether|Although|Though|While|Because|Since|Unless|Once|Whereas)\b")
DASH = re.compile(r"---|—")
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
MIN_SENTENCES = 25
KEYS = ["median_len", "long_share", "sub_per_100w", "sub_per_comma", "comma_per_100w", "dash_per_100w",
        "opens_with_sub", "length_lag1"]


def die(msg):
    sys.stderr.write(f"audit-prose-structure: {msg}\n")
    sys.exit(2)


def reader():
    path = HERE / "audit-prose-fingerprint.py"
    if not path.is_file():
        die(f"the fingerprint audit is not beside this script ({path}); both must read prose the same way")
    spec = importlib.util.spec_from_file_location("fingerprint", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.load


def spans(text):
    return [s.strip() for s in SPLIT.split(text)]


def lag1(lengths):
    """Only adjacent sentences both kept count: a dropped span breaks the chain rather than joining its neighbours."""
    kept = [v for v in lengths if v is not None]
    if len(kept) < 30:
        return None
    mean = statistics.mean(kept)
    den = sum((v - mean) ** 2 for v in kept)
    if not den:
        return None
    num = sum((lengths[i] - mean) * (lengths[i + 1] - mean) for i in range(len(lengths) - 1)
              if lengths[i] is not None and lengths[i + 1] is not None)
    return num / den


def measure(text):
    raw = spans(text)
    lengths = [(len(s.split()) if 4 <= len(s.split()) <= 120 else None) for s in raw]
    sents = [s for s, n in zip(raw, lengths) if n is not None]
    if len(sents) < MIN_SENTENCES:
        return None
    words = sum(len(s.split()) for s in sents)
    sub = sum(len(SUB.findall(s)) for s in sents)
    commas = sum(s.count(",") for s in sents)
    return {"sentences": len(sents), "words": words,
            "median_len": statistics.median(len(s.split()) for s in sents),
            "long_share": sum(len(s.split()) for s in sents if len(s.split()) >= 35) / words,
            "sub_per_100w": 100 * sub / words,
            "sub_per_comma": sub / max(1, commas),
            "comma_per_100w": 100 * commas / words,
            "dash_per_100w": 100 * sum(len(DASH.findall(s)) for s in sents) / words,
            "opens_with_sub": sum(1 for s in sents if OPENER.match(s)) / len(sents),
            "length_lag1": lag1(lengths)}


def read_target(load, target):
    """(whole text, {file: text}). A pattern concentrated in one section averages away over the whole paper, so the
    per-file figures are reported beside it; they are descriptive, and never outliers on their own."""
    files = [target] if target.is_file() else sorted(p for p in target.rglob("*") if p.is_file())
    parts = {}
    for p in files:
        t = load(p)
        # None: not a text file this reader handles. "" : a text file with no prose (a stub kept so the main file
        # need not change), kept so that per_file lists it instead of losing it.
        if t is not None:
            parts[str(p.relative_to(target)) if target.is_dir() else p.name] = t
    return " ".join(parts.values()), parts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--target", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--exclude", action="append", default=[], help="skip baseline files whose name matches")
    ap.add_argument("--min-baseline", type=int, default=20)
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        sys.exit(2 if e.code else 0)
    load = reader()
    target, base = Path(a.target), Path(a.baseline)
    if not target.exists():
        die(f"target not found: {target}")
    if not base.is_dir():
        die(f"baseline is not a directory: {base}")
    whole, parts = read_target(load, target)
    tm = measure(whole)
    if tm is None:
        die(f"fewer than {MIN_SENTENCES} measurable sentences in the target: nothing measured is not a pass")
    rows, skipped, excluded = [], [], []
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in {".pdf", ".tex", ".md", ".txt"}:
            continue
        if any(fnmatch.fnmatch(p.name, g) for g in a.exclude):
            excluded.append(p.name)
            continue
        m = measure(load(p) or "")
        (rows.append({"doc": p.name, **m}) if m else skipped.append(p.name))
    if len(rows) < a.min_baseline:
        die(f"{len(rows)} baseline document(s) measurable (skipped {len(skipped)}, excluded {len(excluded)}); "
            f"no percentile below {a.min_baseline}")
    metrics, outliers = {}, []
    for k in KEYS:
        vals = sorted(r[k] for r in rows if r[k] is not None)
        v = tm[k]
        if v is None or not vals:
            metrics[k] = {"value": v, "note": "not measurable"}
            continue
        pct = round(100 * sum(x < v for x in vals) / len(vals))
        out = v < vals[0] or v > vals[-1]
        metrics[k] = {"value": v, "min": vals[0], "median": statistics.median(vals), "max": vals[-1],
                      "percentile": pct, "outside": out}
        if out:
            outliers.append(k)
    per_file = {}
    for name, t in parts.items():
        m = measure(t)
        if m:
            per_file[name] = {"short": False, **{k: m[k] for k in ("sentences", "median_len", "sub_per_comma",
                                                                    "opens_with_sub")}}
        else:
            # Below the sentence floor: listed and marked, not dropped, so an unmeasured file is not mistaken for
            # one that was never read.
            per_file[name] = {"short": True,
                              "sentences": sum(1 for s in spans(t) if 4 <= len(s.split()) <= 120)}
    # Where the structure is densest. Descriptive, like the rest of per_file: the baseline's range is built from
    # whole papers and a paper's value is an average of its sections, so no single section is an outlier on its own.
    judged = {n: f for n, f in per_file.items() if not f["short"] and f.get("sub_per_comma") is not None}
    densest = None
    if len(judged) >= 2:
        top = max(judged, key=lambda n: judged[n]["sub_per_comma"])
        densest = {"metric": "sub_per_comma", "file": top, "value": judged[top]["sub_per_comma"]}
    report = {"target": str(target), "target_sentences": tm["sentences"], "target_words": tm["words"],
              "per_file": per_file, "densest": densest,
              "baseline_documents": len(rows), "baseline_skipped": skipped, "baseline_excluded": excluded,
              "metrics": metrics, "outliers": outliers}
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    else:
        print(f"target: {target} ({tm['sentences']} sentences, {tm['words']} words)   baseline: {len(rows)} documents")
        for k in KEYS:
            m = metrics[k]
            if "min" in m:
                flag = "  *" if m["outside"] else ""
                print(f"  {k:<16}{m['value']:>9.3f}   median {m['median']:.3f}   range {m['min']:.3f}–{m['max']:.3f}"
                      f"   pct {m['percentile']:>3}{flag}")
            else:
                print(f"  {k:<16}not measurable")
        print("outside the baseline range: " + (", ".join(outliers) or "none"))
        if len(per_file) > 1:
            print("per file (descriptive): sentences / median length / clauses per comma / opens with a subordinator")
            for name, m in per_file.items():
                if m["short"]:
                    print(f"  {name:<40}{m['sentences']:>5}   too few sentences to measure")
                    continue
                print(f"  {name:<40}{m['sentences']:>5}{m['median_len']:>6.0f}{m['sub_per_comma']:>8.3f}"
                      f"{m['opens_with_sub']:>8.3f}")
            if densest:
                print(f"  densest (clauses per comma): {densest['file']} {densest['value']:.3f} (descriptive)")
    return 1 if outliers else 0


if __name__ == "__main__":
    sys.exit(main())
