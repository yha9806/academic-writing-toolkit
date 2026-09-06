#!/usr/bin/env python3
"""Deterministic check that claims and named methods carry sources.

This script does not judge whether a citation is the right one. It finds three
things a manuscript can be inconsistent about entirely from the inside, without
any knowledge of the field:

  unsourced-keyword   a term the manuscript advertises -- in its keywords, its
                      title, or a contribution statement -- that appears in the
                      body with no citation anywhere near it. A paper whose
                      keywords name a concept while its bibliography contains
                      no source for that concept is using a field's vocabulary
                      without its literature.

  uncited-method      a named statistical or experimental procedure used in the
                      body with no citation in the same paragraph. Papers whose
                      contribution is methodological rigour are the ones that
                      most often forget these.

  dangling-entry      a bibliography entry nothing cites.

  bare-novelty        a novelty claim ("to our knowledge", "we are not aware of
                      prior work") in a paragraph with no citation. The strength
                      of such a claim is the strength of the search behind it,
                      and an unsourced paragraph shows no search.

Python 3.8 stdlib only. Reads LaTeX or Markdown. Citations are recognised as
LaTeX \\cite{...}, pandoc [@key], and Harvard author-year in prose — "Smith
(2024)", "(Smith and Doe, 2024, p. 12)" — the two forms the AWT guards accept;
Markdown advertises terms with a "Keywords:" line.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

SCHEMA_VERSION = 1

# Procedures whose names are proper nouns or fixed terms: if the manuscript runs
# one, a reader expects a source. Deliberately conservative -- generic words
# like "mean" or "correlation" are not here.
METHODS = [
    "Benjamini", "Hochberg", "Bonferroni", "Holm", "Clopper", "Pearson correlation",
    "McNemar", "Friedman", "Wilcoxon", "Kruskal", "Mann-Whitney", "Fisher's exact",
    "Cohen's kappa", "Krippendorff", "Fleiss", "bootstrap", "permutation test",
    "equivalence test", "TOST", "preregistration", "preregistered",
    "Shapiro", "Levene", "ANOVA", "mixed-effects", "Cronbach",
]
NOVELTY = re.compile(
    r"\b(?:to our knowledge|to the best of our knowledge|we are not aware of|"
    r"no prior work|first to (?:show|demonstrate|report|propose)|novel(?:ty)?\b)",
    re.I,
)
# The numeric form [12] belongs to rendered text. In LaTeX source it collides
# with set and interval notation -- $K \in \{1,5,10\}$ matched it, and a
# manuscript full of such notation looked fully cited when it cited nothing.
CITE_TEX = re.compile(r"\\cite\w*\{[^}]*\}")
CITE_MD = re.compile(r"\[@[^\]]+\]|\[\d+(?:,\s*\d+)*\]")
# Harvard author-year, the two shapes the AWT guards' extractor accepts (plus
# an optional "et al."): parenthetical "(Smith, 2024, p. 12)" / "(Smith and
# Doe, 2024)" and narrative "Smith (2024)". Set notation cannot match: both
# need a capitalised surname beside a four-digit year.
_SURNAME = r"[A-Z][A-Za-z'’-]+(?:\s+(?:and|&)\s+[A-Z][A-Za-z'’-]+)?(?:\s+et al\.?)?"
HARVARD_PAREN = re.compile(r"\((" + _SURNAME + r"),?\s+(\d{4})[a-z]?(?:,\s*pp?\.?\s*[\d,\s–-]+)?\)")
HARVARD_NARR = re.compile(r"\b(" + _SURNAME + r")\s+\((\d{4})[a-z]?\)")
CITE = re.compile("|".join([CITE_TEX.pattern, r"\[@[^\]]+\]", HARVARD_PAREN.pattern, HARVARD_NARR.pattern]))


def strip_comments(text: str, suffix: str) -> str:
    if suffix == ".tex":
        text = re.sub(r"(?m)(?<!\\)%.*$", "", text)
        # Abstracts do not carry citations by convention; flagging a method
        # named there produces a finding no author can act on.
        text = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", " ", text, flags=re.S)
    return text


def paragraphs(text: str) -> List[Dict]:
    out, pos = [], 0
    for block in re.split(r"\n\s*\n", text):
        line = text.count("\n", 0, pos) + 1
        pos += len(block) + 2
        flat = re.sub(r"\s+", " ", block).strip()
        if len(flat) > 40:
            out.append({"line": line, "text": flat})
    return out


def bib_keys(path: Path) -> Set[str]:
    return {e["key"] for e in bib_entries(path)}


def bib_entries(path: Path) -> List[Dict]:
    """Each entry's key plus its first author's surname and year, for
    matching Harvard citations that never name a key."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    starts = [m for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,", text)]
    out: List[Dict] = []
    for i, m in enumerate(starts):
        body = text[m.end(): starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        author = re.search(r"author\s*=\s*[{\"](.*?)[}\"]\s*,?\s*\n?", body, re.S | re.I)
        year = re.search(r"year\s*=\s*[{\"]?\s*(\d{4})", body, re.I)
        surname = ""
        if author:
            first = re.split(r"\s+and\s+", author.group(1).strip(), maxsplit=1)[0].strip()
            surname = first.split(",")[0].strip() if "," in first else first.split()[-1]
            surname = surname.strip("{} ")
        out.append({"key": m.group(1), "surname": surname.lower(), "year": year.group(1) if year else ""})
    return out


def cited_harvard(text: str) -> Set[Tuple[str, str]]:
    pairs: Set[Tuple[str, str]] = set()
    for rx in (HARVARD_PAREN, HARVARD_NARR):
        for m in rx.finditer(text):
            first = re.split(r"\s+(?:and|&)\s+|\s+et al", m.group(1))[0]
            pairs.add((first.strip().lower(), m.group(2)))
    return pairs


def cited_keys(text: str) -> Set[str]:
    keys = set()
    for m in re.finditer(r"\\cite\w*\{([^}]*)\}", text):
        keys |= {k.strip() for k in m.group(1).split(",") if k.strip()}
    return keys


def declared_terms(text: str) -> List[str]:
    """Terms the manuscript advertises: keywords, title, and contribution lines."""
    terms: List[str] = []
    for m in re.finditer(r"\\keywords\{([^}]*)\}", text):
        terms += [t.strip() for t in re.split(r"[,;]", m.group(1)) if t.strip()]
    # Markdown advertises terms with a "Keywords:" line (a thesis chapter has
    # no \keywords). Titles are not mined from Markdown headings: "Chapter 1"
    # is not a technical phrase.
    for m in re.finditer(r"(?im)^\**keywords\**\s*[:：]\s*(.+?)\s*$", text):
        terms += [t.strip() for t in re.split(r"[,;]", m.group(1)) if t.strip()]
    for m in re.finditer(r"\\title\{([^}]*)\}", text):
        # only multi-word technical phrases from the title, not every word
        terms += [p.strip(" .,:") for p in re.split(r"[:,]", m.group(1)) if len(p.split()) >= 2]
    return [t for t in terms if 1 <= len(t.split()) <= 5]


def audit(base: Path, tex_files: List[Path], bib: Path) -> List[dict]:
    whole = ""
    per_file = []
    for p in tex_files:
        t = strip_comments(p.read_text(encoding="utf-8", errors="replace"), p.suffix.lower())
        per_file.append((p, t))
        whole += "\n\n" + t

    issues: List[dict] = []
    # A named procedure needs one source in the manuscript, not one per mention.
    sourced_methods: Set[str] = set()
    for para in paragraphs(whole):
        if not CITE.search(para["text"]):
            continue
        for meth in METHODS:
            if re.search(r"\b" + re.escape(meth), para["text"], re.I):
                sourced_methods.add(meth)
    first_use: Dict[str, str] = {}

    cited, harvard = cited_keys(whole), cited_harvard(whole)
    for e in bib_entries(bib):
        if e["key"] in cited or (e["surname"] and (e["surname"], e["year"]) in harvard):
            continue
        issues.append({"kind": "dangling-entry", "location": str(bib.name), "detail": e["key"]})

    terms = declared_terms(whole)
    body_low = whole.lower()
    for term in terms:
        tl = term.lower()
        if body_low.count(tl) == 0:
            # A term the paper advertises and never uses is a stronger signal
            # than one used without a source: check its head words instead.
            heads = [w for w in re.findall(r"[a-z-]{5,}", tl) if w not in
                     {"based", "using", "towards", "における"}]
            if heads and not any(body_low.count(h) for h in heads):
                issues.append({"kind": "unsourced-keyword", "location": "keywords/title",
                               "detail": term + "  (advertised, absent from body)"})
                continue
            tl = max(heads, key=len) if heads else tl
        # is there any citation within 400 characters of any mention?
        supported = False
        for m in re.finditer(re.escape(tl), body_low):
            window = whole[max(0, m.start() - 400): m.end() + 400]
            if CITE.search(window):
                supported = True
                break
        if not supported:
            issues.append({"kind": "unsourced-keyword", "location": "keywords/title",
                           "detail": term})

    for p, t in per_file:
        for para in paragraphs(t):
            has_cite = bool(CITE.search(para["text"]))
            loc = "{}:{}".format(p.relative_to(base) if base in p.parents or base == p.parent else p.name,
                                 para["line"])
            for meth in METHODS:
                if meth in sourced_methods:
                    continue
                if re.search(r"\b" + re.escape(meth), para["text"], re.I):
                    first_use.setdefault(meth, loc)
            if NOVELTY.search(para["text"]) and not has_cite:
                m = NOVELTY.search(para["text"])
                issues.append({"kind": "bare-novelty", "location": loc,
                               "detail": para["text"][max(0, m.start() - 30): m.end() + 60]})
    for meth, loc in sorted(first_use.items()):
        issues.append({"kind": "uncited-method", "location": loc, "detail": meth})
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Audit whether advertised claims and named methods carry sources.")
    ap.add_argument("--base-dir", required=True)
    ap.add_argument("--bib", help="bibliography file (default: first .bib under --base-dir)")
    ap.add_argument("--json", action="store_true", dest="emit_json")
    args = ap.parse_args()

    base = Path(args.base_dir)
    if not base.is_dir():
        sys.stderr.write("error: --base-dir is not a directory\n")
        return 2
    SKIP = {"release", "audit", "submission", "ref_pdfs", "tmp", "scripts",
            ".git", "node_modules", "chapters_backup"}
    files = sorted(p for p in base.rglob("*")
                   if p.suffix.lower() in {".tex", ".md"} and p.is_file()
                   and not (SKIP & set(p.relative_to(base).parts[:-1]))
                   and not p.name.endswith(("_audit.md", "_audit_full.md")))
    if not files:
        sys.stderr.write("error: no .tex or .md files under --base-dir\n")
        return 2
    bib = Path(args.bib) if args.bib else next(iter(sorted(base.rglob("*.bib"))), base / "none.bib")

    issues = audit(base, files, bib)
    payload = {"schema_version": SCHEMA_VERSION, "issues": issues, "issue_count": len(issues)}
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        if not issues:
            print("no unsourced claims, uncited methods, or dangling entries found")
        for kind in ("unsourced-keyword", "bare-novelty", "uncited-method", "dangling-entry"):
            group = [i for i in issues if i["kind"] == kind]
            if not group:
                continue
            print("\n{} ({})".format(kind, len(group)))
            for i in group:
                print("  {location}: {detail}".format(**i))
        print("\nNote: this checks that a source is present, never that it is the "
              "right one.\nA term the paper advertises with no citation near it is "
              "the signal that matters:\nit means the vocabulary of a field is in "
              "use while its literature is not.")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
