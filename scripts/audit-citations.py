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
            r"^\*\*Source\*\*:\s+(?P<authors>[" + r"\wÀ-ɏ一-鿿\-'" + r"][\wÀ-ɏ一-鿿\-' ,&.]*?)"
            r"\s+\((?P<year>\d{4}[a-z]?)\)\s+.+\*[^*]+\*\.?\s*$"
        ),
        "source_sample": "Smith, J. and Jones, K. (2024) Title in sentence case. *Publisher*.",
        "accepts_cjk_punct": False,
    },
}


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

    # Tier 1/2/3 land in later tasks.
    _ = chapters

    emit(issues, style_key, mode, args.emit_json)
    return EXIT_ISSUES if issues else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
