#!/usr/bin/env python3
"""Deterministic prose-fingerprint audit against a corpus of published papers.

This script does not rewrite prose. It measures a small set of stylistic
constructions and reports where the target sits relative to a baseline corpus.

The point is the *distribution*, not the count. A construction used twelve
times as often as published work is a problem; so is one used at exactly the
right rate but spread perfectly evenly, because human writers cluster. Every
metric that can be distributed is therefore reported three ways: how often, how
bunched (coefficient of variation of the gaps between occurrences, which is
rate-independent), and how long the longest stretch without one runs.

Baseline percentiles are only shown when a baseline corpus is supplied. Without
one the numbers are still reported, but nothing here says what a good value is:
"published papers in your own bibliography" is the only reference this tool
trusts, and pooling gaps across papers of different rates inflates CV, so
dispersion baselines are computed per document and never pooled.

Python 3.8 stdlib only. PDF baselines require `pdftotext` on PATH; without it,
PDFs are skipped and named in the report.
"""

import argparse
import json
import math
import re
import shutil
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1

# --- constructions -----------------------------------------------------------
# Each is a family of surface forms, not a single string. The corrective
# diptych in particular has five common shapes and counting only "rather than"
# understates it by roughly half.
CONTRAST = (
    r"\brather than\b|\band not\b|\b, not\b|\bnot\b[^.]{0,40}\bbut\b|\binstead of\b"
)
EXPLANATORY_COLON = r"[a-z]:\s+[a-z]"
SEMICOLON = r";"
DISCOURSE = (
    r"\b(?:[Hh]owever|[Mm]oreover|[Ff]urthermore|[Tt]hus|[Tt]herefore"
    r"|[Nn]evertheless|[Cc]onsequently|[Nn]onetheless)\b"
)
NOMINALISATION = r"\b\w+(?:tion|ment|ness|ity)s?\b"
HEDGE = r"\b(?:may|might|could|appears?|suggests?|seems?|likely|plausibl\w+)\b"

DISTRIBUTED = ("contrast", "explanatory_colon", "semicolon", "discourse_marker")
PATTERNS = {
    "contrast": CONTRAST,
    "explanatory_colon": EXPLANATORY_COLON,
    "semicolon": SEMICOLON,
    "discourse_marker": DISCOURSE,
    "nominalisation": NOMINALISATION,
    "hedge": HEDGE,
}

TEXT_SUFFIXES = {".md", ".tex", ".txt"}
STOP_HEADINGS = re.compile(r"\n\s*(?:References|REFERENCES|Bibliography|Works Cited)\s*\n")


# --- extraction --------------------------------------------------------------
def read_pdf(path: Path) -> Optional[str]:
    if not shutil.which("pdftotext"):
        return None
    try:
        out = subprocess.run(
            ["pdftotext", "-q", str(path), "-"],
            capture_output=True, text=True, timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout or None


def strip_markup(text: str, suffix: str) -> str:
    """Remove markup that is not prose the reader sees."""
    if suffix == ".tex":
        text = re.sub(r"(?m)^\s*%.*$", "", text)
        # Alt text and comments are not read aloud in the flow of the argument,
        # but they do drift, so they are measured separately by --include-alt.
        text = re.sub(r"\\Description\{(?:[^{}]|\{[^{}]*\})*\}", " ", text)
        text = re.sub(r"\\(?:label|ref|eqref|cite\w*)\{[^}]*\}", " ", text)
        text = re.sub(r"\\begin\{(?:tabular|table|figure|itemize|enumerate|description|equation|align)\*?\}"
                      r".*?\\end\{(?:tabular|table|figure|itemize|enumerate|description|equation|align)\*?\}",
                      " ", text, flags=re.S)
        text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)
        text = re.sub(r"[{}$&~\\]", " ", text)
    elif suffix == ".md":
        text = re.sub(r"```.*?```", " ", text, flags=re.S)
        text = re.sub(r"(?m)^\s*\|.*$", " ", text)
        text = re.sub(r"(?m)^#+\s*", "", text)
    m = list(STOP_HEADINGS.finditer(text))
    if m:
        text = text[: m[-1].start()]
    return re.sub(r"\s+", " ", text).strip()


def load(path: Path) -> Optional[str]:
    if path.suffix.lower() == ".pdf":
        raw = read_pdf(path)
        return strip_markup(raw, ".txt") if raw else None
    if path.suffix.lower() in TEXT_SUFFIXES:
        return strip_markup(path.read_text(encoding="utf-8", errors="replace"), path.suffix.lower())
    return None


def collect(target: Path) -> List[Tuple[str, str]]:
    if target.is_file():
        t = load(target)
        return [(target.name, t)] if t else []
    out = []
    for p in sorted(target.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix.lower() in TEXT_SUFFIXES or p.suffix.lower() == ".pdf":
            t = load(p)
            if t and len(t.split()) >= 400:
                out.append((str(p.relative_to(target)), t))
    return out


# --- statistics --------------------------------------------------------------
def word_positions(text: str, pattern: str) -> List[int]:
    """Occurrence positions measured in words, so gaps are rate-comparable."""
    words = text.split()
    offsets, cursor = [], 0
    for w in words:
        cursor = text.find(w, cursor)
        offsets.append(cursor)
        cursor += len(w)
    positions, j = [], 0
    for m in re.finditer(pattern, text):
        while j + 1 < len(offsets) and offsets[j + 1] <= m.start():
            j += 1
        positions.append(j)
    return positions


def cv(values: Sequence[float]) -> Optional[float]:
    if len(values) < 3:
        return None
    mean = statistics.mean(values)
    return statistics.pstdev(values) / mean if mean else None


def sentences(text: str) -> List[int]:
    out = []
    for s in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
        n = len(s.split())
        if 4 <= n <= 90:
            out.append(n)
    return out


def lag1(values: Sequence[int]) -> Optional[float]:
    """Positive: long sentences cluster with long ones, as in human drafts.
    Near zero: each length drawn independently.
    Negative: systematic long-short alternation, a manufactured rhythm."""
    if len(values) < 30:
        return None
    mean = statistics.mean(values)
    den = sum((v - mean) ** 2 for v in values)
    if not den:
        return None
    num = sum((values[i] - mean) * (values[i + 1] - mean) for i in range(len(values) - 1))
    return num / den


def repeat_ngram_rate(text: str, n: int = 4) -> float:
    words = re.findall(r"[a-z']+", text.lower())
    if len(words) <= n:
        return 0.0
    grams: Dict[str, int] = {}
    for i in range(len(words) - n + 1):
        g = " ".join(words[i:i + n])
        grams[g] = grams.get(g, 0) + 1
    repeated = sum(v - 1 for v in grams.values() if v > 1)
    return 1000.0 * repeated / (len(words) - n + 1)


def measure(text: str) -> Dict[str, Optional[float]]:
    total = len(text.split())
    out: Dict[str, Optional[float]] = {"words": total}
    for name, pat in PATTERNS.items():
        pos = word_positions(text, pat)
        out[name + "_per_1k"] = 1000.0 * len(pos) / total if total else 0.0
        if name in DISTRIBUTED:
            gaps = [b - a for a, b in zip(pos, pos[1:]) if b > a]
            out[name + "_gap_cv"] = cv(gaps)
            out[name + "_longest_dry_fraction"] = (max(gaps) / total) if gaps else None
    lengths = sentences(text)
    out["sentence_length_cv"] = cv(lengths)
    out["sentence_length_lag1"] = lag1(lengths)
    out["repeat_4gram_per_1k"] = repeat_ngram_rate(text)
    verbs = re.findall(r"\b[Ww]e ([a-z]+)\b", text)
    out["first_person_verb_diversity"] = (len(set(verbs)) / len(verbs)) if verbs else None
    return out


def sections(text: str, suffix: str, raw: str) -> Dict[str, str]:
    """Per-section rates are the uniformity signal that needs no baseline:
    when a rhetorical device runs at the same rate in the dataset section and
    the discussion, that evenness is itself the finding."""
    if suffix == ".tex":
        parts = re.split(r"\\section\*?\{([^}]*)\}", raw)
    elif suffix == ".md":
        parts = re.split(r"(?m)^#{1,2}\s+(.+)$", raw)
    else:
        return {}
    if len(parts) < 3:
        return {}
    out = {}
    for i in range(1, len(parts) - 1, 2):
        body = strip_markup(parts[i + 1], suffix)
        if len(body.split()) >= 200:
            out[parts[i].strip()[:60]] = body
    return out


def percentile(value: Optional[float], population: List[float]) -> Optional[float]:
    if value is None or not population:
        return None
    return 100.0 * sum(1 for x in population if x < value) / len(population)


# --- reporting ---------------------------------------------------------------
KEY_ORDER = [
    ("contrast_per_1k", "corrective diptych  /1k"),
    ("contrast_gap_cv", "  gap CV (bunching)"),
    ("contrast_longest_dry_fraction", "  longest dry run"),
    ("explanatory_colon_per_1k", "explanatory colon  /1k"),
    ("semicolon_per_1k", "semicolon  /1k"),
    ("discourse_marker_per_1k", "discourse marker  /1k"),
    ("sentence_length_cv", "sentence length CV"),
    ("sentence_length_lag1", "sentence length lag-1"),
    ("repeat_4gram_per_1k", "repeated 4-gram  /1k"),
    ("nominalisation_per_1k", "nominalisation  /1k"),
    ("hedge_per_1k", "hedging  /1k"),
    ("first_person_verb_diversity", "we+verb diversity"),
]


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit prose fingerprint against a baseline corpus of published work.")
    ap.add_argument("--target", required=True,
                    help="manuscript file, or a directory of .md/.tex/.txt/.pdf")
    ap.add_argument("--baseline",
                    help="directory of published papers to compare against "
                         "(a project's own literature/ is the intended corpus)")
    ap.add_argument("--min-baseline", type=int, default=5,
                    help="refuse to report percentiles below this many baseline documents")
    ap.add_argument("--json", action="store_true", dest="emit_json")
    args = ap.parse_args()

    target = Path(args.target)
    if not target.exists():
        sys.stderr.write("error: --target does not exist\n")
        return 2
    docs = collect(target)
    if not docs:
        sys.stderr.write("error: no readable prose found in --target\n")
        return 2
    text = " ".join(t for _, t in docs)
    mine = measure(text)

    base_rows: List[Dict[str, Optional[float]]] = []
    skipped: List[str] = []
    if args.baseline:
        bdir = Path(args.baseline)
        if not bdir.is_dir():
            sys.stderr.write("error: --baseline is not a directory\n")
            return 2
        for p in sorted(bdir.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in TEXT_SUFFIXES | {".pdf"}:
                continue
            t = load(p)
            if t is None:
                skipped.append(p.name)
            elif len(t.split()) >= 1500:
                base_rows.append(measure(t))

    enough = len(base_rows) >= args.min_baseline
    report = {"schema_version": SCHEMA_VERSION, "target": str(target),
              "target_words": mine["words"], "baseline_documents": len(base_rows),
              "baseline_sufficient": enough, "baseline_skipped": skipped, "metrics": {}}

    outliers = []
    for key, _ in KEY_ORDER:
        pop = [r[key] for r in base_rows if r.get(key) is not None]
        entry = {"value": mine.get(key)}
        if enough and pop and mine.get(key) is not None:
            pop_sorted = sorted(pop)
            entry.update({
                "baseline_median": statistics.median(pop_sorted),
                "baseline_min": pop_sorted[0],
                "baseline_max": pop_sorted[-1],
                "percentile": percentile(mine[key], pop_sorted),
                "outside_range": not (pop_sorted[0] <= mine[key] <= pop_sorted[-1]),
            })
            if entry["outside_range"]:
                outliers.append(key)
        report["metrics"][key] = entry

    # Per-section evenness needs no baseline at all.
    if target.is_file() and target.suffix.lower() in {".tex", ".md"}:
        raw = target.read_text(encoding="utf-8", errors="replace")
        secs = sections(text, target.suffix.lower(), raw)
        if len(secs) >= 3:
            rates = {}
            for name, body in secs.items():
                w = len(body.split())
                rates[name] = 1000.0 * len(re.findall(CONTRAST, body)) / w
            spread = cv(list(rates.values()))
            report["per_section_contrast_per_1k"] = rates
            report["per_section_cv"] = spread
            report["per_section_note"] = (
                "A low cross-section CV means the device runs at the same rate in the "
                "dutiful sections as in the discussion. That evenness is the signature; "
                "the fix is to redistribute, not merely to reduce.")
    report["outliers"] = outliers

    if args.emit_json:
        print(json.dumps(report, indent=2))
    else:
        print("target: {}  ({:,} words)".format(target, int(mine["words"])))
        if args.baseline:
            print("baseline: {} documents{}".format(
                len(base_rows), "" if enough else "  [too few for percentiles]"))
            if skipped:
                print("  unreadable (install pdftotext?): {}".format(", ".join(skipped[:6])))
        print()
        head = "{:<26}{:>10}".format("metric", "target")
        if enough:
            head += "{:>10}{:>18}{:>8}".format("median", "range", "pct")
        print(head)
        for key, label in KEY_ORDER:
            e = report["metrics"][key]
            if e["value"] is None:
                continue
            line = "{:<26}{:>10.3f}".format(label, e["value"])
            if "baseline_median" in e:
                line += "{:>10.3f}{:>18}{:>8.0f}".format(
                    e["baseline_median"],
                    "{:.2f}-{:.2f}".format(e["baseline_min"], e["baseline_max"]),
                    e["percentile"])
                if e["outside_range"]:
                    line += "  *"
            print(line)
        if "per_section_cv" in report and report["per_section_cv"] is not None:
            print("\nper-section corrective-diptych rate  (cross-section CV {:.2f})".format(
                report["per_section_cv"]))
            for name, r in report["per_section_contrast_per_1k"].items():
                print("  {:<44}{:>7.1f}".format(name, r))
        if outliers:
            print("\noutside the baseline range: {}".format(", ".join(outliers)))
        print("\nNote: none of these values is a target to hit. Editing to move a "
              "number\nrather than to fix a sentence produces a different artefact, "
              "not a better one.")

    return 1 if outliers else 0


if __name__ == "__main__":
    sys.exit(main())
