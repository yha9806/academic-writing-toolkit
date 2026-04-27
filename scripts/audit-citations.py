#!/usr/bin/env python3
"""audit-citations.py — Tier 0-3 citation auditor for the academic-writing-toolkit.

Python 3.8 stdlib only. Spec: docs/superpowers/specs/2026-04-27-c-rest-citation-design.md (v2).

Usage:
    audit-citations.py --base-dir DIR [--style STYLE] [--json]

Exit codes:
    0  no issues at any tier
    1  issues found at any tier
    2  invalid arguments (unknown --style, --base-dir not a directory, etc.)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

EXIT_OK = 0
EXIT_ISSUES = 1
EXIT_USAGE = 2

RE_FLAGS = re.UNICODE

# --- Registry ----------------------------------------------------------------
# Each row populated incrementally as tasks T3-T9 add styles.
# Lastname character class: Latin + Latin Extended (À-ɏ) + CJK Unified
# Ideographs (一-鿿) + hyphen + apostrophe. Used by every author regex.
LASTNAME_CLASS = r"[\wÀ-ɏ一-鿿\-']"

# Permissive Source-line lint used when --style is absent: requires the
# **Source**: prefix, single line, and at least one 4-digit year.
PERMISSIVE_SOURCE_RE = re.compile(
    r"^\*\*Source\*\*:\s+.+\b\d{4}\b.+$",
    RE_FLAGS,
)

CITATION_STYLES: Dict[str, dict] = {
    "harvard": {
        "name": "Harvard",
        "mode": "author-year",
        "intext_paren_punct": "no-comma",
        "etal_threshold": 4,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and", "&"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+(?P<authors>[\wÀ-ɏ一-鿿\-'][\wÀ-ɏ一-鿿\-' ,&.]*?)"
            r"\s+\((?P<year>\d{4}[a-z]?)\)\s+.+\*[^*]+\*\.?\s*$"
        ),
        "source_sample": "Smith, J. and Jones, K. (2024) Title in sentence case. *Publisher*.",
        "accepts_cjk_punct": False,
    },
    "apa": {
        "name": "APA 7th",
        "mode": "author-year",
        "intext_paren_punct": "comma",
        "etal_threshold": 3,
        "etal_first_cite_only": True,
        "multi_author_connectors": ["&"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+(?P<authors>[\wÀ-ɏ一-鿿\-'][\wÀ-ɏ一-鿿\-' ,&.]*?)"
            r"\s+\((?P<year>\d{4}[a-z]?)\)\.\s+.+\*[^*]+\*\.?.*$"
        ),
        "source_sample": "Smith, J., & Jones, K. (2024). Title in sentence case. *Publisher*. https://doi.org/...",
        "accepts_cjk_punct": False,
    },
    "chicago-author-date": {
        "name": "Chicago Author-Date (17th)",
        "mode": "author-year",
        "intext_paren_punct": "no-comma",
        "etal_threshold": 4,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+(?P<authors>[\wÀ-ɏ一-鿿\-'][\wÀ-ɏ一-鿿\-' ,.]*?)"
            r"\.\s+(?P<year>\d{4}[a-z]?)\.\s+.+$"
        ),
        "source_sample": "Smith, John, and Kim Jones. 2024. *Title in Title Case*. Publisher.",
        "accepts_cjk_punct": False,
    },
    "mla": {
        "name": "MLA 9",
        "mode": "author-page",
        "intext_paren_punct": "n/a",
        "etal_threshold": 3,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+(?P<authors>[\wÀ-ɏ一-鿿\-'][\wÀ-ɏ一-鿿\-' ,.]*?)"
            r"\.\s+\*[^*]+\*\.\s+.+,\s*(?P<year>\d{4}[a-z]?)\.?\s*$"
        ),
        "source_sample": "Smith, John, and Kim Jones. *Title in Title Case*. Publisher, 2024.",
        "accepts_cjk_punct": False,
    },
    "ieee": {
        "name": "IEEE",
        "mode": "numeric",
        "intext_paren_punct": "n/a",
        "etal_threshold": 7,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+\[(?P<num>\d+)\]\s+.+,\s*(?P<year>\d{4}[a-z]?)\.?\s*$"
        ),
        "source_sample": "[1] J. Smith and K. Jones, \"Title in title case,\" *Journal*, vol. 12, no. 3, pp. 45-67, 2024.",
        "accepts_cjk_punct": False,
        "numeric_bracket_pattern": r"\[(?P<num>\d+)\]",
    },
    "vancouver": {
        "name": "Vancouver",
        "mode": "numeric",
        "intext_paren_punct": "n/a",
        "etal_threshold": 7,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+(?P<num>\d+)\.\s+.+\.\s*(?P<year>\d{4}[a-z]?).*$"
        ),
        "source_sample": "1. Smith J, Jones K. Title in sentence case. Journal. 2024;12(3):45-67.",
        "accepts_cjk_punct": False,
        "numeric_bracket_pattern": r"\[(\d+)\]|\((\d+)\)",
    },
    "gb-t-7714-2015": {
        "name": "GB/T 7714-2015 (Author-Year)",
        "mode": "author-year",
        "intext_paren_punct": "comma",
        "etal_threshold": 4,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and"],
        "source_pattern": (
            r"^\*\*Source\*\*:\s+(?P<authors>[\wÀ-ɏ一-鿿\-'][\wÀ-ɏ一-鿿\-' ,.]*?)"
            r"\.\s+.+\[[A-Z]\]\.\s*\*?[^*]+\*?,?\s*(?P<year>\d{4}[a-z]?).*$"
        ),
        "source_sample": "Smith J, Jones K. Title in sentence case[J]. *Journal*, 2024, 12(3): 45-67.",
        "accepts_cjk_punct": True,
    },
}


# --- Preprocessing -----------------------------------------------------------

def strip_zones(text: str) -> str:
    """Replace YAML frontmatter, code fences, inline code, HTML comments, and
    link URLs with newline-preserving equivalents so line numbers in the
    stripped text still match the original. Spec §4.9."""

    def newline_pad(match: "re.Match") -> str:
        return "\n" * match.group(0).count("\n")

    # YAML frontmatter at top of file (between the first two --- markers).
    text = re.sub(r"\A---\n.*?\n---\n?", newline_pad, text, count=1, flags=re.DOTALL)
    # Fenced code blocks.
    text = re.sub(r"```.*?```", newline_pad, text, flags=re.DOTALL)
    # Inline code (no embedded newlines normally, but keep the pad invariant).
    text = re.sub(r"`[^`\n]+`", "", text)
    # HTML comments.
    text = re.sub(r"<!--.*?-->", newline_pad, text, flags=re.DOTALL)
    # Markdown link URLs: keep visible text, drop the URL portion.
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    return text


# --- In-text author-year parsing --------------------------------------------

# Author group: a single lastname, optional "and"/"&" + second lastname,
# optional "et al." trailer. Parenthetical and narrative variants share
# this shape. Multi-author lists with 3+ surface authors are tolerated by
# additional commas inside the group; we capture the lead lastname only
# for pair-match purposes.
_AUTHOR_TOKEN = (
    r"[\wÀ-ɏ一-鿿\-']+"
    r"(?:\s*,\s*[\wÀ-ɏ一-鿿\-']+)*"
    r"(?:\s*,?\s+(?:and|&)\s+[\wÀ-ɏ一-鿿\-']+)?"
    r"(?:\s*,?\s*et\s+al\.?)?"
)

INTEXT_AUTHOR_YEAR_PARENS = re.compile(
    r"\((?P<authors>" + _AUTHOR_TOKEN + r")"
    r"(?P<sep>\s*[,，]?\s+)"
    r"(?P<year>\d{4})(?P<suffix>[a-z]?)\)",
    RE_FLAGS,
)

INTEXT_AUTHOR_YEAR_NARRATIVE = re.compile(
    r"\b(?P<authors>" + _AUTHOR_TOKEN + r")\s+"
    r"\((?P<year>\d{4})(?P<suffix>[a-z]?)\)",
    RE_FLAGS,
)

# Full-width-paren variant (GB/T 7714-2015 with CJK punct enabled).
INTEXT_AUTHOR_YEAR_FULLWIDTH = re.compile(
    r"（(?P<authors>" + _AUTHOR_TOKEN + r")"
    r"(?P<sep>\s*[,，]?\s*)"
    r"(?P<year>\d{4})(?P<suffix>[a-z]?)）",
    RE_FLAGS,
)


def _first_lastname(authors: str) -> str:
    """Pick the first author lastname from the captured `authors` group.
    Strips trailing 'et al.', 'and X', '& X', etc."""
    s = authors.strip()
    # Drop trailing 'et al.' bits.
    s = re.sub(r"\s*,?\s*et\s+al\.?\s*$", "", s, flags=RE_FLAGS)
    # Drop ' and X' / ' & X' second author.
    s = re.sub(r"\s+(?:and|&)\s+.*$", "", s, flags=RE_FLAGS)
    # Comma-list: take the first token.
    s = s.split(",")[0]
    return s.strip()


def parse_intext_author_year(text: str, accepts_cjk: bool = False) -> List[dict]:
    """Return a list of in-text occurrence dicts. Each has lastname,
    year_int, year_suffix, line_num, form ('parens-comma' | 'parens-no-comma'
    | 'narrative'), and raw text. Operates on already-stripped text."""
    occurrences: List[dict] = []

    # Build line-offset table for line-number lookup.
    line_offsets = [0]
    for ch in text:
        if ch == "\n":
            line_offsets.append(line_offsets[-1] + 1)
            line_offsets[-1] = line_offsets[-1]  # placeholder
    # Build properly: cumulative newline count per char position.
    # We'll compute line numbers via text.count up to start of match.

    def line_of(start: int) -> int:
        return text.count("\n", 0, start) + 1

    for m in INTEXT_AUTHOR_YEAR_PARENS.finditer(text):
        sep = m.group("sep") or ""
        # parens-comma if comma in sep (ASCII or full-width); parens-no-comma otherwise.
        form = "parens-comma" if ("," in sep or "，" in sep) else "parens-no-comma"
        occurrences.append({
            "lastname": _first_lastname(m.group("authors")),
            "year_int": int(m.group("year")),
            "year_suffix": m.group("suffix") or "",
            "authors_raw": m.group("authors"),
            "line_num": line_of(m.start()),
            "form": form,
            "raw": m.group(0),
        })

    for m in INTEXT_AUTHOR_YEAR_NARRATIVE.finditer(text):
        # Skip if this match is inside a parens match we already captured —
        # the parens regex consumes the year, so the narrative regex may
        # also fire on the inner author. Simple guard: ensure the char
        # immediately before authors is not inside a parens match.
        # Cheap check: lookbehind for ' (' which would mean we're already
        # inside parens content. Skipping when previous char is '('.
        start = m.start()
        if start > 0 and text[start - 1] == "(":
            continue
        occurrences.append({
            "lastname": _first_lastname(m.group("authors")),
            "year_int": int(m.group("year")),
            "year_suffix": m.group("suffix") or "",
            "authors_raw": m.group("authors"),
            "line_num": line_of(start),
            "form": "narrative",
            "raw": m.group(0),
        })

    if accepts_cjk:
        for m in INTEXT_AUTHOR_YEAR_FULLWIDTH.finditer(text):
            sep = m.group("sep") or ""
            form = "parens-comma" if ("，" in sep or "," in sep) else "parens-no-comma"
            occurrences.append({
                "lastname": _first_lastname(m.group("authors")),
                "year_int": int(m.group("year")),
                "year_suffix": m.group("suffix") or "",
                "authors_raw": m.group("authors"),
                "line_num": line_of(m.start()),
                "form": form,
                "raw": m.group(0),
            })

    return occurrences


def collect_intext_author_year(
    chapter_files: List[Path],
    base_dir: Path,
    accepts_cjk: bool = False,
) -> List[dict]:
    """Walk every chapter file, strip zones, run author-year parser. Each
    returned occurrence dict carries a `location` field (relpath:line)."""
    out: List[dict] = []
    for chap in chapter_files:
        try:
            raw = chap.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        stripped = strip_zones(raw)
        for occ in parse_intext_author_year(stripped, accepts_cjk=accepts_cjk):
            occ["location"] = "{}:{}".format(relpath(chap, base_dir), occ["line_num"])
            out.append(occ)
    return out


# --- Source line author-year parsing ----------------------------------------

# Lead-author regex: capture the first lastname token at the start of a
# Source line. Works for "Smith, J. ..." (Western), "Smith John ..." and
# bare "王 J. ..." (CJK). Uses LASTNAME_CLASS for the unicode-friendly
# character class.
SOURCE_LEAD_AUTHOR_RE = re.compile(
    r"^\*\*Source\*\*:\s+(?:\[\d+\]\s+)?(?P<lastname>[\wÀ-ɏ一-鿿\-']+)",
    RE_FLAGS,
)

# Year-in-parens (Western: "(2024)" or "(2024a)"). Used as the strong
# signal for author-year sources where the year sits in parentheses.
SOURCE_PAREN_YEAR_RE = re.compile(
    r"\((?P<year>\d{4})(?P<suffix>[a-z]?)\)",
    RE_FLAGS,
)

# Bare four-digit year, used as a fallback (Chicago "2024." form, GB/T
# "..., 2024,..." form, MLA "..., 2024." form). Picks the FIRST four-digit
# year on the line — Source lines for thesis sources are dominated by the
# publication year up front.
SOURCE_BARE_YEAR_RE = re.compile(
    r"\b(?P<year>\d{4})(?P<suffix>[a-z]?)\b",
    RE_FLAGS,
)


def parse_source_author_year(notes_files: List[Path]) -> List[dict]:
    """Parse each notes file's **Source**: line and return a list of dicts:
    {lastname, year_int, year_suffix, location}. Tries paren-year first
    (Harvard, APA), falls back to bare year (Chicago, GB/T 7714)."""
    out: List[dict] = []
    for notes_path in notes_files:
        loc = find_source_line(notes_path)
        if loc is None:
            continue
        line_num, line = loc
        author_m = SOURCE_LEAD_AUTHOR_RE.match(line)
        if not author_m:
            continue
        year_m = SOURCE_PAREN_YEAR_RE.search(line) or SOURCE_BARE_YEAR_RE.search(line)
        if not year_m:
            continue
        out.append({
            "lastname": author_m.group("lastname"),
            "year_int": int(year_m.group("year")),
            "year_suffix": year_m.group("suffix") or "",
            "location": "{}:{}".format(notes_path.name, line_num),
            "notes_path": notes_path,
        })
    return out


# --- Source line lastname-only parsing (MLA) --------------------------------

SOURCE_LASTNAME_RE = re.compile(
    r"^\*\*Source\*\*:\s+(?P<lastname>[\wÀ-ɏ一-鿿\-']+)\s*,",
    RE_FLAGS,
)


def parse_source_lastname(notes_files: List[Path]) -> List[dict]:
    """For author-page mode: parse first-author lastname from Source line
    (assumes 'Lastname, Firstname.' opening)."""
    out: List[dict] = []
    for notes_path in notes_files:
        loc = find_source_line(notes_path)
        if loc is None:
            continue
        line_num, line = loc
        m = SOURCE_LASTNAME_RE.match(line)
        if not m:
            continue
        out.append({
            "lastname": m.group("lastname"),
            "location": "{}:{}".format(notes_path.name, line_num),
            "notes_path": notes_path,
        })
    return out


# --- Tier 1: pairing ---------------------------------------------------------

def tier1_author_year_pair(
    in_text: List[dict],
    sources: List[dict],
) -> List[dict]:
    """Pair author-year in-text occurrences against Source lines.
    Suffix rule (spec §4.5):
      - if both sides agree on (lastname, year, suffix): match.
      - if in-text has suffix but no Source has matching (lastname, year, suffix): phantom.
      - if Source has suffix and in-text has none with matching suffix: unused
        for that suffixed source.
      - bare in-text (Smith 2024) matches a bare Source (Smith 2024) OR a
        suffixed source (Smith 2024a) — strip suffix from Source side when
        the in-text has no suffix.
    """
    issues: List[dict] = []

    # Build helper sets.
    src_with_suffix = {(s["lastname"].lower(), s["year_int"], s["year_suffix"]): s for s in sources}
    src_bare_lookup: Dict[Tuple[str, int], List[dict]] = {}
    for s in sources:
        src_bare_lookup.setdefault((s["lastname"].lower(), s["year_int"]), []).append(s)

    intext_keys: Set[Tuple[str, int, str]] = set()
    intext_bare: Set[Tuple[str, int]] = set()
    for occ in in_text:
        intext_keys.add((occ["lastname"].lower(), occ["year_int"], occ["year_suffix"]))
        intext_bare.add((occ["lastname"].lower(), occ["year_int"]))

    # Phantom: in-text occurrences with no compatible source.
    seen_phantom: Set[Tuple[str, int, str]] = set()
    for occ in in_text:
        key = (occ["lastname"].lower(), occ["year_int"], occ["year_suffix"])
        if key in seen_phantom:
            continue
        # Try strict match first.
        if key in src_with_suffix:
            continue
        # If in-text suffix is empty, accept any source with same (last, year).
        if occ["year_suffix"] == "" and src_bare_lookup.get((occ["lastname"].lower(), occ["year_int"])):
            continue
        # Otherwise phantom.
        seen_phantom.add(key)
        issues.append({
            "tier": 1,
            "kind": "phantom",
            "severity": "high",
            "location": occ["location"],
            "message": (
                "in-text citation ({} {}{}) has no matching Source in notes"
            ).format(occ["lastname"], occ["year_int"], occ["year_suffix"]),
            "context": occ["raw"],
        })

    # Unused: source rows with no compatible in-text occurrence.
    for s in sources:
        skey = (s["lastname"].lower(), s["year_int"], s["year_suffix"])
        if skey in intext_keys:
            continue
        # Bare in-text (Smith, 2024) covers any (Smith, 2024, *) source.
        if (s["lastname"].lower(), s["year_int"]) in intext_bare:
            # Only count this as covered when in-text is bare and source is bare,
            # OR in-text has no suffix and source has any suffix.
            bare_intext = any(
                occ["lastname"].lower() == s["lastname"].lower()
                and occ["year_int"] == s["year_int"]
                and occ["year_suffix"] == ""
                for occ in in_text
            )
            if bare_intext:
                continue
        issues.append({
            "tier": 1,
            "kind": "unused",
            "severity": "high",
            "location": "literature/reading_notes/" + Path(s["location"].split(":", 1)[0]).name,
            "message": (
                "Source ({} {}{}) is never cited in chapters"
            ).format(s["lastname"], s["year_int"], s["year_suffix"]),
            "context": "",
        })

    return issues


def tier1_author_page_pair(
    in_text_lastnames: Set[str],
    source_lastnames: Set[str],
    in_text_locations: Dict[str, str],
    source_locations: Dict[str, str],
) -> List[dict]:
    """MLA-style weak pair: lastname only."""
    issues: List[dict] = []
    for ln in sorted(in_text_lastnames - source_lastnames):
        issues.append({
            "tier": 1,
            "kind": "phantom",
            "severity": "high",
            "location": in_text_locations.get(ln, ""),
            "message": "in-text ({}) has no matching Source (lastname-only pair)".format(ln),
            "context": "",
        })
    for ln in sorted(source_lastnames - in_text_lastnames):
        issues.append({
            "tier": 1,
            "kind": "unused",
            "severity": "high",
            "location": source_locations.get(ln, ""),
            "message": "Source ({}) is never cited in chapters".format(ln),
            "context": "",
        })
    return issues


def tier1_numeric_pair(
    chapter_files: List[Path],
    base_dir: Path,
    notes_count: int,
    bracket_pattern: str,
) -> List[dict]:
    """Numeric mode: count balance + gap detection. Returns issues list."""
    issues: List[dict] = []
    bracket_re = re.compile(bracket_pattern, RE_FLAGS)
    seen: Set[int] = set()
    first_loc: Dict[int, str] = {}
    for chap in chapter_files:
        try:
            raw = chap.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        stripped = strip_zones(raw)
        for m in bracket_re.finditer(stripped):
            # Find the named 'num' group if present; otherwise the first
            # non-empty group. Patterns without either provide nothing.
            num: Optional[str] = None
            if "num" in (bracket_re.groupindex or {}):
                num = m.group("num")
            if num is None:
                for g in m.groups():
                    if g:
                        num = g
                        break
            if num is None:
                continue
            n = int(num)
            if n not in seen:
                seen.add(n)
                line = stripped.count("\n", 0, m.start()) + 1
                first_loc[n] = "{}:{}".format(relpath(chap, base_dir), line)

    if not seen:
        # No numeric citations at all; if there are notes, that's an unused signal.
        if notes_count > 0:
            issues.append({
                "tier": 1,
                "kind": "numeric-count-mismatch",
                "severity": "high",
                "location": "",
                "message": (
                    "no [N] citations in chapters but {} numbered Source(s) in notes"
                ).format(notes_count),
                "context": "",
            })
        return issues

    # Count mismatch: unique [N] count vs notes count.
    if len(seen) != notes_count:
        issues.append({
            "tier": 1,
            "kind": "numeric-count-mismatch",
            "severity": "high",
            "location": "",
            "message": (
                "unique [N] count ({}) does not match notes count ({})"
            ).format(len(seen), notes_count),
            "context": "",
        })

    # Gap detection: integers 1..max should all be present.
    expected = set(range(1, max(seen) + 1))
    missing = expected - seen
    if missing:
        for n in sorted(missing):
            issues.append({
                "tier": 1,
                "kind": "numeric-gap",
                "severity": "medium",
                "location": "",
                "message": "[{}] missing from chapter citation sequence".format(n),
                "context": "",
            })
    return issues


# --- Tier 2: mode detection -------------------------------------------------

def tier2_mode_detect(in_text: List[dict]) -> List[dict]:
    """Bucket each in-text occurrence by form; if two non-narrative buckets
    are within 10%, emit ambiguous-mode; otherwise the smaller-bucket
    occurrences are outliers. Total < 10 → return single info issue."""
    issues: List[dict] = []
    if len(in_text) < 10:
        return issues
    buckets: Dict[str, List[dict]] = {}
    for occ in in_text:
        buckets.setdefault(occ["form"], []).append(occ)
    non_narrative = {k: v for k, v in buckets.items() if k != "narrative"}
    if len(non_narrative) < 2:
        return issues
    counts = sorted(non_narrative.items(), key=lambda kv: -len(kv[1]))
    top, runner = counts[0], counts[1]
    top_n, runner_n = len(top[1]), len(runner[1])
    # Ambiguous if runner is within 10% of top.
    if top_n > 0 and (top_n - runner_n) / top_n <= 0.10:
        issues.append({
            "tier": 2,
            "kind": "ambiguous-mode",
            "severity": "medium",
            "location": "",
            "message": (
                "two dominant in-text patterns ({}: {}, {}: {}) within 10%"
            ).format(top[0], top_n, runner[0], runner_n),
            "context": "",
        })
        return issues
    # Otherwise top is the mode; everyone else (excluding narrative) is an outlier.
    mode_form = top[0]
    for form, occs in non_narrative.items():
        if form == mode_form:
            continue
        for occ in occs:
            issues.append({
                "tier": 2,
                "kind": "style-outlier",
                "severity": "medium",
                "location": occ["location"],
                "message": (
                    "in-text form {} differs from manuscript mode {}"
                ).format(form, mode_form),
                "context": occ["raw"],
            })
    return issues


# --- Tier 3: per-style format validation ------------------------------------

def _count_authors(authors_raw: str) -> int:
    """Best-effort author count from a captured authors group. Counts
    comma-separated tokens plus an 'and'/'&' tail; 'et al.' trailers are
    counted as 1 (the surface author before 'et al.')."""
    s = authors_raw.strip()
    s = re.sub(r"\s*,?\s*et\s+al\.?\s*$", "", s, flags=RE_FLAGS)
    # Replace 'and'/'&' with comma to unify split.
    s = re.sub(r"\s+(?:and|&)\s+", ",", s, flags=RE_FLAGS)
    parts = [p.strip() for p in s.split(",") if p.strip()]
    return max(1, len(parts))


def tier3_author_year_format(
    in_text: List[dict],
    style_row: dict,
) -> List[dict]:
    """Validate every parenthetical occurrence's punctuation, connector,
    and et-al threshold against the active style's rules."""
    issues: List[dict] = []
    expected_punct = style_row["intext_paren_punct"]
    connectors = style_row["multi_author_connectors"]
    threshold = style_row["etal_threshold"]
    accepts_cjk = style_row.get("accepts_cjk_punct", False)

    for occ in in_text:
        if occ["form"] == "narrative":
            continue
        # Punctuation check. Styles with `accepts_cjk_punct` (GB/T 7714-2015)
        # accept both comma and no-comma forms, so skip the punct check.
        if not accepts_cjk:
            if expected_punct == "comma" and occ["form"] == "parens-no-comma":
                issues.append({
                    "tier": 3,
                    "kind": "format-comma",
                    "severity": "low",
                    "location": occ["location"],
                    "message": "{} requires a comma between author and year".format(style_row["name"]),
                    "context": occ["raw"],
                })
            elif expected_punct == "no-comma" and occ["form"] == "parens-comma":
                issues.append({
                    "tier": 3,
                    "kind": "format-comma",
                    "severity": "low",
                    "location": occ["location"],
                    "message": "{} forbids a comma between author and year".format(style_row["name"]),
                    "context": occ["raw"],
                })

        # Connector check.
        ar = occ["authors_raw"]
        for tok, allowed_set in [("and", "and" in connectors), ("&", "&" in connectors)]:
            tok_re = re.compile(r"\s+" + re.escape(tok) + r"\s+", RE_FLAGS)
            if tok_re.search(ar) and not allowed_set:
                issues.append({
                    "tier": 3,
                    "kind": "format-connector",
                    "severity": "low",
                    "location": occ["location"],
                    "message": "{} disallows '{}' connector; use one of {}".format(
                        style_row["name"], tok, connectors
                    ),
                    "context": occ["raw"],
                })

        # Et-al threshold check.
        n_authors = _count_authors(ar)
        has_etal = bool(re.search(r"\bet\s+al\.?", ar, RE_FLAGS))
        if not has_etal and n_authors >= threshold:
            issues.append({
                "tier": 3,
                "kind": "format-etal-threshold",
                "severity": "low",
                "location": occ["location"],
                "message": (
                    "{} requires 'et al.' for {}+ authors (saw {})"
                ).format(style_row["name"], threshold, n_authors),
                "context": occ["raw"],
            })

        # CJK punctuation check (when style does NOT accept full-width).
        if not accepts_cjk and re.search(r"[，。：；（）]", occ["raw"], RE_FLAGS):
            issues.append({
                "tier": 3,
                "kind": "format-cjk-punct",
                "severity": "low",
                "location": occ["location"],
                "message": "{} disallows full-width CJK punctuation in citations".format(style_row["name"]),
                "context": occ["raw"],
            })

    return issues


# --- Main --------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audit-citations.py",
        description="Tier 0-3 citation auditor (registry-driven, 7 styles).",
    )
    parser.add_argument(
        "--base-dir",
        required=True,
        help="Project root containing chapters/ and literature/reading_notes/",
    )
    parser.add_argument(
        "--style",
        default=None,
        help="Citation style; one of the registry keys. Omit to skip Tier 3.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="emit_json",
        help="Emit machine-readable JSON (default: human-readable text).",
    )
    parser.add_argument(
        "--chapters-glob",
        default="chapters/*.md",
        help="Override chapter discovery glob (default: chapters/*.md).",
    )
    parser.add_argument(
        "--notes-glob",
        default="literature/reading_notes/*_NOTES.md",
        help="Override notes discovery glob (default: literature/reading_notes/*_NOTES.md).",
    )
    return parser


def discover_files(base_dir: Path, glob: str) -> List[Path]:
    """Return sorted list of files matching glob under base_dir, excluding the
    notes template (`_template_NOTES.md`)."""
    return sorted(
        p for p in base_dir.glob(glob)
        if p.is_file() and p.name != "_template_NOTES.md"
    )


def relpath(path: Path, base_dir: Path) -> str:
    """Best-effort relative path string for issue locations; falls back to
    the absolute path if the file is outside base_dir."""
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


# --- Tier 0: source-line lint -----------------------------------------------

def find_source_line(notes_path: Path) -> Optional[Tuple[int, str]]:
    """Return (line_number, line_text) for the first **Source**: line in
    notes_path, or None if absent. Line numbers are 1-based."""
    try:
        text = notes_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for idx, line in enumerate(text.splitlines(), start=1):
        if line.startswith("**Source**:"):
            return (idx, line)
    return None


def tier0_lint(
    notes_files: List[Path],
    style_row: Optional[dict],
    base_dir: Path,
) -> List[dict]:
    """Per-style **Source**: format lint over notes files. When style_row is
    None, fall back to a permissive single-line + year check; mismatches at
    that level are still flagged as `notes-source-malformed`."""
    issues: List[dict] = []
    if style_row is not None:
        style_re = re.compile(style_row["source_pattern"], RE_FLAGS)
    else:
        style_re = PERMISSIVE_SOURCE_RE
    for notes_path in notes_files:
        loc = find_source_line(notes_path)
        rel = relpath(notes_path, base_dir)
        if loc is None:
            issues.append({
                "tier": 0,
                "kind": "notes-source-missing",
                "severity": "high",
                "location": rel,
                "message": "no **Source**: line in notes file",
                "context": "",
            })
            continue
        line_num, line = loc
        if not style_re.match(line):
            issues.append({
                "tier": 0,
                "kind": "notes-source-malformed",
                "severity": "medium",
                "location": "{}:{}".format(rel, line_num),
                "message": (
                    "**Source**: line does not match style "
                    + (style_row["name"] if style_row else "(permissive)")
                    + " pattern"
                ),
                "context": line.strip(),
            })
    return issues


def emit(issues: List[dict], style_key: Optional[str], mode: Optional[str], emit_json: bool) -> None:
    summary = {
        "tier0_notes_lint": sum(1 for i in issues if i["tier"] == 0),
        "tier1_phantom": sum(1 for i in issues if i.get("kind") == "phantom"),
        "tier1_unused": sum(1 for i in issues if i.get("kind") == "unused"),
        "tier1_count_mismatch": sum(1 for i in issues if i.get("kind") == "numeric-count-mismatch"),
        "tier1_numeric_gap": sum(1 for i in issues if i.get("kind") == "numeric-gap"),
        "tier2_outliers": sum(1 for i in issues if i["tier"] == 2),
        "tier3_format_violations": sum(1 for i in issues if i["tier"] == 3),
    }
    payload = {
        "schema_version": 1,
        "style": style_key,
        "mode": mode,
        "summary": summary,
        "issues": issues,
    }
    if emit_json:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write("Citation audit\n")
        sys.stdout.write("  style: {}\n".format(style_key or "(unspecified)"))
        sys.stdout.write("  mode:  {}\n".format(mode or "(n/a)"))
        for k, v in summary.items():
            sys.stdout.write("  {}: {}\n".format(k, v))
        if issues:
            sys.stdout.write("\nIssues:\n")
            for it in issues:
                sys.stdout.write(
                    "  [tier {tier}] {kind} ({severity}): {message}\n".format(**it)
                )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    base_dir = Path(args.base_dir)
    if not base_dir.is_dir():
        sys.stderr.write("error: --base-dir is not a directory: {}\n".format(base_dir))
        return EXIT_USAGE

    style_key: Optional[str] = args.style
    if style_key is not None:
        style_key = style_key.lower()
        if style_key not in CITATION_STYLES:
            sys.stderr.write(
                "error: unknown --style {!r}; available: {}\n".format(
                    style_key, sorted(CITATION_STYLES.keys()) or "(registry empty)"
                )
            )
            return EXIT_USAGE
    style_row: Optional[dict] = CITATION_STYLES.get(style_key) if style_key else None

    chapters = discover_files(base_dir, args.chapters_glob)
    notes = discover_files(base_dir, args.notes_glob)

    issues: List[dict] = []
    mode = style_row["mode"] if style_row else None

    # Tier 0: source-line lint over notes files.
    issues.extend(tier0_lint(notes, style_row, base_dir))

    # Tier 1/2/3 dispatch by mode. When --style is omitted we still run
    # Tier 1 author-year (the most common case) and Tier 2; Tier 3 is
    # always gated on --style.
    accepts_cjk = bool(style_row.get("accepts_cjk_punct", False)) if style_row else False
    active_mode = mode or "author-year"

    if active_mode == "author-year":
        in_text = collect_intext_author_year(chapters, base_dir, accepts_cjk=accepts_cjk)
        sources_ay = parse_source_author_year(notes)
        issues.extend(tier1_author_year_pair(in_text, sources_ay))
        issues.extend(tier2_mode_detect(in_text))
        if style_row is not None:
            issues.extend(tier3_author_year_format(in_text, style_row))
    elif active_mode == "author-page":
        # MLA: parse `(Lastname N)` or `(Lastname N-M)` from chapters.
        intext_lastnames: Set[str] = set()
        intext_locs: Dict[str, str] = {}
        page_re = re.compile(
            r"\((?P<lastname>[\wÀ-ɏ一-鿿\-']+)\s+\d+(?:-\d+)?\)",
            RE_FLAGS,
        )
        for chap in chapters:
            try:
                raw = chap.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            stripped = strip_zones(raw)
            for m in page_re.finditer(stripped):
                ln = m.group("lastname")
                intext_lastnames.add(ln)
                line = stripped.count("\n", 0, m.start()) + 1
                intext_locs.setdefault(ln, "{}:{}".format(relpath(chap, base_dir), line))
        src_records = parse_source_lastname(notes)
        src_lastnames = {s["lastname"] for s in src_records}
        src_locs = {s["lastname"]: s["location"] for s in src_records}
        issues.extend(tier1_author_page_pair(intext_lastnames, src_lastnames, intext_locs, src_locs))
        # Tier 3 for MLA: source pattern only; rules already validated by Tier 0.
    elif active_mode == "numeric":
        if style_row is None:
            # No bracket pattern available without a style; skip Tier 1 numeric.
            pass
        else:
            issues.extend(tier1_numeric_pair(
                chapters,
                base_dir,
                notes_count=len(notes),
                bracket_pattern=style_row["numeric_bracket_pattern"],
            ))

    emit(issues, style_key, mode, args.emit_json)
    return EXIT_ISSUES if issues else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
