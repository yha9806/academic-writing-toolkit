# C-rest — `/audit` Citation Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement registry-driven 7-style citation auditing for `/audit` per spec v2: a Python 3.8 stdlib-only `scripts/audit-citations.py` with three pairing modes (author-year / author-page / numeric) and four tiers (0 lint / 1 pair / 2 mode / 3 format), backed by ~15 fixtures and 13 regression tests T19–T31, plus cross-skill Source-template propagation and a `## Citation` block in `CLAUDE.md` propagated by `make sync`.

**Architecture:** Test-driven. Each tier+style combination ships behind one or more fixtures and tests; tests land in `scripts/test.sh` to run under A's CI. The registry is a Python `dict` literal — adding the 8th style is data-only. Source-line emission across `_template_NOTES.md`, `/note`, `/verify` is unhardcoded so the active style flows from `CLAUDE.md`.

**Tech Stack:** Python 3.8 stdlib only (`re`, `argparse`, `pathlib`, `json`, `sys`); GNU make (existing `make sync`, `make test`, `make doctor`); bash test harness (extended by T19–T31); markdown edits in skill files. No pytest, no third-party deps. Per spec §3 Q8.

**Spec:** [docs/superpowers/specs/2026-04-27-c-rest-citation-design.md](../specs/2026-04-27-c-rest-citation-design.md) v2 — refer for design rationale.

---

## File Structure

| File | Touched by tasks | Responsibility after C-rest |
|---|---|---|
| `scripts/audit-citations.py` | T1, T3, T4, T5, T6, T7, T8, T9 | Tier 0–3 logic + `CITATION_STYLES` registry; argparse CLI; Python 3.8 stdlib only |
| `tests/citation/fixtures/<name>/` | T2, T3, T4, T5, T6, T7, T8, T9 | New directory tree (`tests/` did not exist pre-C-rest) |
| `scripts/test.sh` | T10 | Append T19–T31 |
| `literature/reading_notes/_template_NOTES.md` | T11 | Replace single-line free-text with per-style sample blocks |
| `CLAUDE.md` | T11 | Add `## Citation` block inside `<!-- SHARED:START -->` / `<!-- SHARED:END -->` markers |
| `AGENTS.md`, `GEMINI.md` | T11 (via `make sync`) | Auto-regenerated; not hand-edited |
| `.claude/skills/audit/SKILL.md` | T11 | Replace §D placeholder; add invocation step |
| `docs/skills/06-audit.md` | T11 | User-doc mirror |
| `.claude/skills/note/SKILL.md` | T12 | Line 34 unhardcoded; references `_template_NOTES.md` and `CLAUDE.md` |
| `.claude/skills/verify/SKILL.md` | T12 | Line 41 unhardcoded; same |

Total file deltas: 1 new script + 1 new fixture tree (~30 small files) + 7 edits + auto-regenerated `AGENTS.md`/`GEMINI.md`.

---

## Task ordering rationale

1. **CLI skeleton first (T1)**: argparse + exit codes + `--help` + an empty registry. Establishes the contract; lets every later task verify against `--help` output and exit codes.
2. **Fixture infrastructure (T2)**: directory layout + the first clean fixture (`clean_harvard`). Establishes the corpus pattern.
3. **Tier 0 + Harvard (T3)**: Tier 0 is style-agnostic in shape but needs one registry row to validate against; Harvard is the simplest. Test against `clean_harvard` and `source_lint_fail` fixtures.
4. **Tier 1 author-year + APA (T4)**: completes the most-used pairing path. Test against `phantom`, `unused`, `clean_apa`.
5. **Tier 2 mode detection (T5)**: independent of style choice; tests against `mixed_style`.
6. **Tier 3 author-year format rules (T6)**: Harvard + APA divergence (comma vs no-comma; `&` vs `and`; et al. threshold).
7. **Add Chicago + GB/T 7714-2015 (T7)**: same author-year mode; both ship together with their clean fixtures.
8. **Add MLA — author-page mode (T8)**: new pairing-mode branch; weak-pair Tier 1.
9. **Add IEEE + Vancouver — numeric mode (T9)**: numeric branch; count + gap detection; ships with `clean_ieee`, `clean_vancouver`, `numeric_gap`.
10. **Wire all tests into `scripts/test.sh` T19–T31 (T10)**: tests rely on the script being feature-complete.
11. **Update notes template + CLAUDE.md + audit skill (T11)**: user-facing surfaces. `make sync` propagates CLAUDE.md changes.
12. **Update `/note` and `/verify` skills (T12)**: cross-skill Source unification (B5 fix).
13. **Local verification gate (T13)**: `make doctor && make test` reports `all 28 tests passed.`
14. **Push + observe CI (T14)**: first remote signal.
15. **Regression-catch rehearsal (T15)**: spec §6.3 — phantom in `clean_harvard`, observe red, revert, observe green.
16. **Merge to master (T16)**: post-CI green; squash merge.

Commit boundaries follow file-cohesion: each tier+style addition is one commit; the user-surface batch (T11) is one commit; cross-skill batch (T12) is one commit; rehearsal commits revert before merge. Estimated ~12-16 commits total.

---

## Task 1: CLI skeleton + empty style registry

**Files:**
- New: `scripts/audit-citations.py`

- [ ] **Step 1: Create the file with shebang, header, argparse CLI, exit codes, and an empty `CITATION_STYLES = {}` dict.**

The file must:
- Use Python 3.8 syntax only (no `match`/`case`, no walrus in stdlib calls beyond 3.8 acceptance, no `dict | dict` union — use `{**a, **b}`).
- Import only `re`, `argparse`, `pathlib`, `json`, `sys` from stdlib.
- Define exit codes as a small dict at top: `EXIT_OK=0, EXIT_ISSUES=1, EXIT_USAGE=2`.
- argparse: `--base-dir` (required, must be a directory), `--style` (optional, choices = list of registry keys; when registry is empty, `choices=None` so all values rejected gracefully), `--json` (flag), `--chapters-glob` (default `chapters/*.md`), `--notes-glob` (default `literature/reading_notes/*_NOTES.md`).
- `main()` returns one of the exit codes.
- A `main()`-as-`__main__` guard at the bottom.

- [ ] **Step 2: Verify the skeleton runs**

```bash
python3 scripts/audit-citations.py --help
echo "exit: $?"
```

Expected: usage text printed; exit 0.

```bash
python3 scripts/audit-citations.py --base-dir /tmp
echo "exit: $?"
```

Expected: exit 1 (no chapters/notes found in `/tmp` — but the script reaches its main loop). When the registry is empty and Tier 0 finds no notes, the script should still exit cleanly with exit 0 (no issues to report) — adjust if needed.

- [ ] **Step 3: Commit**

```bash
git add scripts/audit-citations.py
git commit -m "feat(C-rest): add audit-citations.py CLI skeleton + empty registry"
```

---

## Task 2: First fixture corpus + helper

**Files:**
- New: `tests/citation/fixtures/clean_harvard/CLAUDE.md`
- New: `tests/citation/fixtures/clean_harvard/chapters/ch01.md`
- New: `tests/citation/fixtures/clean_harvard/literature/reading_notes/smith2024_NOTES.md`

- [ ] **Step 1: Create the fixture directory tree.** Each fixture is a self-contained mini-project:

```
tests/citation/fixtures/clean_harvard/
├── CLAUDE.md                                       # declares Citation style: harvard
├── chapters/
│   └── ch01.md                                     # ~10 lines; ≥ 1 in-text citation (Smith 2024)
└── literature/reading_notes/
    └── smith2024_NOTES.md                          # has matching **Source**: line in Harvard format
```

Content templates:

`tests/citation/fixtures/clean_harvard/CLAUDE.md`:
```markdown
## Citation

- Citation style: harvard
```

`tests/citation/fixtures/clean_harvard/chapters/ch01.md`:
```markdown
# Chapter 1

Recent work (Smith 2024) shows that thesis writing benefits from automation.
As Smith (2024) argues, the toolkit should enforce consistency.
```

`tests/citation/fixtures/clean_harvard/literature/reading_notes/smith2024_NOTES.md`:
```markdown
# Smith 2024

**Source**: Smith, J. (2024) Title in sentence case. *Publisher*.

## Notes
Some notes here.
```

- [ ] **Step 2: Verify the fixture is parseable by file count**

```bash
find tests/citation/fixtures/clean_harvard -type f | wc -l
```

Expected: 3.

- [ ] **Step 3: Commit**

```bash
git add tests/citation/fixtures/clean_harvard/
git commit -m "test(C-rest): add clean_harvard fixture corpus"
```

---

## Task 3: Tier 0 lint + Harvard registry row

**Files:**
- Edit: `scripts/audit-citations.py` (add Harvard row + Tier 0 logic)
- New: `tests/citation/fixtures/source_lint_fail/literature/reading_notes/bad_NOTES.md`
- New: `tests/citation/fixtures/source_lint_fail/literature/reading_notes/missing_NOTES.md`
- New: `tests/citation/fixtures/source_lint_fail/chapters/.gitkeep`
- New: `tests/citation/fixtures/source_lint_fail/CLAUDE.md`

- [ ] **Step 1: Add the Harvard registry row**

In `CITATION_STYLES`, populate the `harvard` key per spec §4.2 (mode, intext_paren_punct, etal_threshold, etal_first_cite_only, multi_author_connectors, source_pattern, source_sample, accepts_cjk_punct).

The `source_pattern` regex for Harvard:
```
^\*\*Source\*\*:\s+(?P<authors>[\wÀ-ɏ一-鿿\-' ,&.]+?)\s+\((?P<year>\d{4}[a-z]?)\)\s+.+\s+\*[^*]+\*\.?\s*$
```
(Built incrementally; capture authors, year, and require italicised publisher.)

- [ ] **Step 2: Add Tier 0 logic**

Function `tier0_lint(notes_files, style_row, accept_any=False)` returns a list of issue dicts. For each notes file:
- Find first line matching `^\*\*Source\*\*:`. If absent → kind `notes-source-missing`, severity `high`.
- Try matching against `style_row.source_pattern`. On no-match → kind `notes-source-malformed`, severity `medium`, with the file path and line number.
- Skip `_template_NOTES.md` (excluded by glob).

When `--style` is not given, run Tier 0 with a permissive union pattern (just check single-line, contains `**Source**:`, has a 4-digit year) — no malformed-flag for stylistic mismatches.

- [ ] **Step 3: Add fixture `source_lint_fail`** with two failing cases:

`bad_NOTES.md` (multi-line — should fail):
```markdown
**Source**: Smith, J. (2024)
Title in sentence case. *Publisher*.
```

`missing_NOTES.md` (no Source line — should fail):
```markdown
# Some notes
No source here.
```

`CLAUDE.md`:
```markdown
## Citation

- Citation style: harvard
```

- [ ] **Step 4: Verify Tier 0 against fixtures**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_harvard --style harvard --json
echo "exit: $?"
# Expected: exit 0; JSON shows tier0_notes_lint: 0
```

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/source_lint_fail --style harvard --json
echo "exit: $?"
# Expected: exit 1; JSON shows 2 tier-0 issues (one missing, one malformed)
```

- [ ] **Step 5: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/source_lint_fail/
git commit -m "feat(C-rest): tier 0 source-line lint + harvard registry row"
```

---

## Task 4: Tier 1 author-year pair check + APA row

**Files:**
- Edit: `scripts/audit-citations.py`
- New: `tests/citation/fixtures/clean_apa/` (mirror `clean_harvard` shape; APA-formatted)
- New: `tests/citation/fixtures/phantom/` (Harvard chapter cites unmatched author)
- New: `tests/citation/fixtures/unused/` (Harvard notes file with no citing chapter)

- [ ] **Step 1: Add APA registry row** (mode `author-year`, `intext_paren_punct: comma`, `etal_threshold: 3`, `etal_first_cite_only: True`, `multi_author_connectors: ["&"]`).

- [ ] **Step 2: Add `strip_zones(text)` preprocessor** per spec §4.9.

- [ ] **Step 3: Add `parse_intext_author_year(text)`** that returns a list of `(lastname, year_int, year_suffix, line_num, is_narrative, raw_match)` tuples. Handle:
- Parenthetical with comma: `(Smith, 2024)`
- Parenthetical without comma: `(Smith 2024)`
- Narrative: `Smith (2024)`
- Multi-author: `(Smith and Jones 2024)`, `(Smith & Jones, 2024)`, `(Smith et al., 2024)`
- Year suffix: `(Smith, 2024a)` → year_int=2024, year_suffix='a'

The combined regex (with `re.UNICODE`):
```python
INTEXT_AUTHOR_YEAR_PARENS = re.compile(
    r"\((?P<authors>[\wÀ-ɏ一-鿿\-']+(?:\s+(?:and|&)\s+[\wÀ-ɏ一-鿿\-']+)?(?:\s+et\s+al\.?)?)"
    r"(?P<sep>,?\s+)"
    r"(?P<year>\d{4})(?P<suffix>[a-z]?)\)",
    re.UNICODE,
)

INTEXT_AUTHOR_YEAR_NARRATIVE = re.compile(
    r"\b(?P<authors>[\wÀ-ɏ一-鿿\-']+(?:\s+(?:and|&)\s+[\wÀ-ɏ一-鿿\-']+)?(?:\s+et\s+al\.?)?)\s+"
    r"\((?P<year>\d{4})(?P<suffix>[a-z]?)\)",
    re.UNICODE,
)
```

(Tune as fixtures expose edge cases — keep readable; don't over-anchor.)

- [ ] **Step 4: Add `parse_source_author_year(notes_files, style_row)`** that returns a set of `(lastname_lower, year_int, year_suffix)` from each Source line's first author + year.

- [ ] **Step 5: Add `tier1_pair(in_text_set, source_set)`** that returns:
- `phantom` issues for every `(lastname, year)` in in_text_set not in source_set
- `unused` issues for every `(lastname, year)` in source_set not referenced in chapters

Year-suffix rule (spec §4.5): when in-text has suffix and Source doesn't (or vice versa), strict mismatch — flag as phantom/unused.

- [ ] **Step 6: Add fixtures**

`tests/citation/fixtures/phantom/`:
- `CLAUDE.md`: `Citation style: harvard`
- `chapters/ch01.md`: cites `(NotInNotes 2024)` and `(Smith 2024)`
- `literature/reading_notes/smith2024_NOTES.md`: matches Smith 2024 only
- Expected: `phantom` issue for `(NotInNotes, 2024)`

`tests/citation/fixtures/unused/`:
- `CLAUDE.md`: `Citation style: harvard`
- `chapters/ch01.md`: cites `(Smith 2024)` only
- `literature/reading_notes/smith2024_NOTES.md`: Smith 2024
- `literature/reading_notes/lonely2023_NOTES.md`: Lonely 2023, never cited
- Expected: `unused` issue for `(Lonely, 2023)`

`tests/citation/fixtures/clean_apa/`:
- `CLAUDE.md`: `Citation style: apa`
- `chapters/ch01.md`: cites `(Smith, 2024)` (with comma) and `Smith (2024)`
- `literature/reading_notes/smith2024_NOTES.md`: APA format Source

- [ ] **Step 7: Verify**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/phantom --style harvard --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='phantom' for i in d['issues']), d"
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/unused --style harvard --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='unused' for i in d['issues']), d"
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_apa --style apa --json
echo "clean_apa exit: $?"   # Expected: 0
```

- [ ] **Step 8: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/{clean_apa,phantom,unused}/
git commit -m "feat(C-rest): tier 1 author-year pairing + apa registry row"
```

---

## Task 5: Tier 2 mode detection

**Files:**
- Edit: `scripts/audit-citations.py`
- New: `tests/citation/fixtures/mixed_style/`

- [ ] **Step 1: Implement `tier2_mode_detect(in_text_occurrences)`** per spec §4.7:
- Bucket each occurrence into `parens-comma` / `parens-no-comma` / `narrative` / `mla-author-page`.
- Total < 10 → return `info` "insufficient data"; no outliers.
- Mode = bucket with max count, excluding `narrative` (which is style-agnostic).
- Outliers = all non-mode, non-narrative occurrences.
- If two non-narrative buckets within 10% of each other → kind `ambiguous-mode` instead.

- [ ] **Step 2: Add fixture `mixed_style`**

```
tests/citation/fixtures/mixed_style/
├── CLAUDE.md                      # no style declared (or omitted entirely)
├── chapters/ch01.md               # mixes (Smith, 2024) and (Jones 2024) — 5+ of each
└── literature/reading_notes/{smith,jones}_NOTES.md
```

- [ ] **Step 3: Verify**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/mixed_style --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['tier']==2 for i in d['issues']), d"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/mixed_style/
git commit -m "feat(C-rest): tier 2 style mode detection"
```

---

## Task 6: Tier 3 author-year format rules + multi-author fixtures

**Files:**
- Edit: `scripts/audit-citations.py`
- New: `tests/citation/fixtures/format_apa_in_harvard_project/`
- New: `tests/citation/fixtures/format_harvard_in_apa_project/`
- New: `tests/citation/fixtures/multi_author_etal/`

- [ ] **Step 1: Implement `tier3_format(in_text_occurrences, source_lines, style_row)`**:

For each in-text occurrence in the active style's mode:
- Validate `intext_paren_punct` (comma vs no-comma): if mismatch, emit `format-comma` (severity `low`).
- Validate `multi_author_connectors`: if connector not in allowed list, emit `format-connector`.
- Count authors before `et al.`; validate against `etal_threshold` and `etal_first_cite_only`. Mismatch → `format-etal-threshold`.
- For Source lines: validate against `style_row.source_pattern`. (Tier 0 already does this; Tier 3 adds `format-year-punct` for year-paren punctuation specifics.)

- [ ] **Step 2: Add three fixtures**

`format_apa_in_harvard_project`: declared style `harvard`, but chapters use APA-style `(Smith, 2024)` (with comma). Tier 3 should flag every comma occurrence.

`format_harvard_in_apa_project`: declared style `apa`, but chapters use Harvard-style `(Smith 2024)` (no comma). Tier 3 should flag every missing-comma occurrence.

`multi_author_etal`:
- `CLAUDE.md`: declared `apa`
- chapters cite `(Smith, Jones, & Brown, 2024)` (3 authors → APA requires `et al.` from first cite)
- expected: Tier 3 emits `format-etal-threshold`

- [ ] **Step 3: Verify**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/format_apa_in_harvard_project --style harvard --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='format-comma' for i in d['issues']), d"
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/format_harvard_in_apa_project --style apa --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='format-comma' for i in d['issues']), d"
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/multi_author_etal --style apa --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='format-etal-threshold' for i in d['issues']), d"
```

- [ ] **Step 4: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/{format_apa_in_harvard_project,format_harvard_in_apa_project,multi_author_etal}/
git commit -m "feat(C-rest): tier 3 author-year format validation (Harvard + APA)"
```

---

## Task 7: Add Chicago Author-Date + GB/T 7714-2015 (author-year mode)

**Files:**
- Edit: `scripts/audit-citations.py` (two registry rows)
- New: `tests/citation/fixtures/clean_chicago_ad/`
- New: `tests/citation/fixtures/clean_gb_2015/`

- [ ] **Step 1: Add `chicago-author-date` row**

`mode: author-year`, `intext_paren_punct: no-comma`, `etal_threshold: 4`, `multi_author_connectors: ["and"]`. Title case in titles. Source pattern accepts Title Case publication titles (no italic-required for unpublished sources, but italics for journals).

- [ ] **Step 2: Add `gb-t-7714-2015` row**

`mode: author-year`, `intext_paren_punct: comma`, `accepts_cjk_punct: True`, `etal_threshold: 4`. Both `(王 2024)` (no comma) and `(王，2024)` (full-width comma) accepted. Source pattern includes `[J]/[M]/[D]` document-type marker after title.

- [ ] **Step 3: Add fixtures**

`clean_chicago_ad`:
- chapters cite `(Smith and Jones 2024)` and `Smith (2024)`
- notes: Chicago-format Source line

`clean_gb_2015`:
- `CLAUDE.md`: `Citation style: gb-t-7714-2015`
- chapters cite mixed `(王, 2024)` (ASCII), `（李，2024）` (full-width), and `Wang and Li (2024)` (narrative)
- notes: `**Source**: Wang J. Title in sentence case[J]. *Journal*, 2024, 12(3): 45-67.`
- Tier 1 should pair lastnames; Tier 3 should accept both punct styles

- [ ] **Step 4: Verify**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_chicago_ad --style chicago-author-date --json
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_gb_2015 --style gb-t-7714-2015 --json
# Both expect exit 0
```

- [ ] **Step 5: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/{clean_chicago_ad,clean_gb_2015}/
git commit -m "feat(C-rest): add chicago-author-date and gb-t-7714-2015 styles"
```

---

## Task 8: Author-page mode + MLA

**Files:**
- Edit: `scripts/audit-citations.py`
- New: `tests/citation/fixtures/clean_mla/`

- [ ] **Step 1: Implement author-page mode branch in Tier 1**

For `mode == "author-page"`:
- Parse chapters for `\(([\w\-']+)\s+\d+(?:-\d+)?\)` (lastname + page).
- Build set of lastnames cited.
- Parse notes Source lines for first-author lastname.
- `phantom` = chapter lastnames - notes lastnames (severity `high`).
- `unused` = notes lastnames - chapter lastnames (severity `high`).
- Year and page intentionally not used.

Tier 3 for MLA validates Source format (`Smith, John. *Title*. Publisher, 2024.`); page form in chapters is style-correct (`(Smith 47)`, not `(Smith, 47)`).

- [ ] **Step 2: Add `mla` registry row**

`mode: author-page`, `intext_paren_punct: n/a`, `etal_threshold: 3`, `multi_author_connectors: ["and"]`, source_sample per spec §4.2.

- [ ] **Step 3: Add fixture**

`clean_mla`:
- `CLAUDE.md`: `Citation style: mla`
- chapters cite `(Smith 47)`, `(Smith and Jones 92)`, `Smith argues that...`
- notes: `**Source**: Smith, John. *Title in Title Case*. Publisher, 2024.`

- [ ] **Step 4: Verify**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_mla --style mla --json
# Expected: exit 0
```

Add a deliberate phantom (cite `(NotInNotes 5)`) to a temp variant and verify phantom is detected (then revert).

- [ ] **Step 5: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/clean_mla/
git commit -m "feat(C-rest): author-page mode + mla style"
```

---

## Task 9: Numeric mode + IEEE + Vancouver

**Files:**
- Edit: `scripts/audit-citations.py`
- New: `tests/citation/fixtures/clean_ieee/`
- New: `tests/citation/fixtures/clean_vancouver/`
- New: `tests/citation/fixtures/numeric_gap/`

- [ ] **Step 1: Implement numeric mode branch**

For `mode == "numeric"`:
- Use `style_row.numeric_bracket_pattern` to extract every `[N]` (or per-style variant) from chapters in document order across `chapters/*.md` (alphabetical filename order).
- Record first-appearance integer set; check for gaps in 1..max.
- Count notes files (excluding template).
- `numeric-count-mismatch` (severity `high`): unique `[N]` count != notes count.
- `numeric-gap` (severity `medium`): integers skip a value (e.g., `[1] [2] [4]` with no `[3]`).

Tier 2 skipped for numeric (no parens-comma vs parens-no-comma to detect).

Tier 3 for numeric: validate Source line format only (e.g., IEEE requires `[N]` prefix, Vancouver requires `N.` prefix or numbered list).

- [ ] **Step 2: Add `ieee` and `vancouver` registry rows**

`ieee`: `mode: numeric`, `numeric_bracket_pattern: r"\[(\d+)\]"`, source_sample per spec.
`vancouver`: `mode: numeric`, `numeric_bracket_pattern: r"\[(\d+)\]|\((\d+)\)"`, source_sample per spec.

- [ ] **Step 3: Add fixtures**

`clean_ieee`:
- `CLAUDE.md`: `Citation style: ieee`
- chapters cite `[1]`, `[2]` in order
- notes: 2 files with `**Source**: [1] J. Smith, ...` and `**Source**: [2] K. Jones, ...`

`clean_vancouver`:
- `CLAUDE.md`: `Citation style: vancouver`
- chapters cite `[1]`, `[2]` in order
- notes: 2 files with `**Source**: 1. Smith J. ...` and `**Source**: 2. Jones K. ...`

`numeric_gap`:
- `CLAUDE.md`: `Citation style: ieee`
- chapters cite `[1]`, `[2]`, `[4]` (skipping `[3]`)
- notes: 3 files
- expected: Tier 1 emits `numeric-gap`

- [ ] **Step 4: Verify**

```bash
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_ieee --style ieee --json
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_vancouver --style vancouver --json
python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/numeric_gap --style ieee --json | python3 -c "import json,sys; d=json.load(sys.stdin); assert any(i['kind']=='numeric-gap' for i in d['issues']), d"
```

- [ ] **Step 5: Commit**

```bash
git add scripts/audit-citations.py tests/citation/fixtures/{clean_ieee,clean_vancouver,numeric_gap}/
git commit -m "feat(C-rest): numeric mode + ieee + vancouver styles"
```

---

## Task 10: Append T19–T31 to `scripts/test.sh`

**Files:**
- Edit: `scripts/test.sh`

- [ ] **Step 1: Add 13 `test_T*` functions** following the existing pattern (functions defined at top, registered with `run_test "label" test_TN` near the bottom).

Each test function:
- Invokes `python3 scripts/audit-citations.py --base-dir tests/citation/fixtures/<fixture> [--style <style>] --json`.
- Captures stdout + exit code.
- Asserts on the expected `tier`, `kind`, and `severity` per spec §6.2 table.
- Uses `python3 -c '...'` for JSON parsing (stdlib only; `python3.8` already verified by CI).

Pattern example (T19):

```bash
test_T19() {
    local out
    out=$(python3 scripts/audit-citations.py \
        --base-dir tests/citation/fixtures/phantom \
        --style harvard --json) || true
    echo "$out" | python3 -c '
import json, sys
d = json.load(sys.stdin)
issues = [i for i in d["issues"] if i["kind"] == "phantom"]
assert issues, "expected phantom issue"
print("T19 ok:", len(issues), "phantom issues")
'
}
```

- [ ] **Step 2: Update the test count display in the harness footer**

The footer line currently reads `all 15 tests passed.`; update the totals constant (or whatever drives it) to 28 (15 + 13).

- [ ] **Step 3: Verify**

```bash
bash scripts/test.sh
# Expected last line: all 28 tests passed.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/test.sh
git commit -m "test(C-rest): wire T19-T31 citation tests into harness"
```

---

## Task 11: Update template, CLAUDE.md, audit skill + docs

**Files:**
- Edit: `literature/reading_notes/_template_NOTES.md`
- Edit: `CLAUDE.md`
- Edit: `.claude/skills/audit/SKILL.md`
- Edit: `docs/skills/06-audit.md`
- Auto-regen: `AGENTS.md`, `GEMINI.md` (via `make sync`)

- [ ] **Step 1: Update `_template_NOTES.md`**

Replace the single-line placeholder with a `### Source format examples` section showing all 7 sample blocks (per spec §4.5). The actual `**Source**:` line in real notes uses the active style's sample.

- [ ] **Step 2: Add `## Citation` block to `CLAUDE.md` inside SHARED markers**

Place between `## Writing Principles` and `<!-- SHARED:END -->`:

```markdown
## Citation

- Citation style: harvard
```

(Default to `harvard` for the toolkit project itself; users override per-project.)

- [ ] **Step 3: Run `make sync`**

```bash
make sync
git diff --stat AGENTS.md GEMINI.md
# Expected: both files show the new ## Citation section propagated
```

- [ ] **Step 4: Update `.claude/skills/audit/SKILL.md` §D**

Replace the 2-line placeholder with the new contract: invoke `scripts/audit-citations.py --json --style $(style)`, parse JSON, render into the existing `Issues` table per the documented kinds and severities. Reference spec §4.4 for the JSON schema.

- [ ] **Step 5: Update `docs/skills/06-audit.md`** to mirror the SKILL.md change (user-facing doc).

- [ ] **Step 6: Verify**

```bash
make sync                                 # already done; re-running is idempotent
bash scripts/test.sh                      # all 28 tests still pass
make doctor                               # exit 0
grep -rn 'placeholder\|TBD' .claude/skills/audit/ docs/skills/   # exit 1 (no matches)
```

- [ ] **Step 7: Commit**

```bash
git add literature/reading_notes/_template_NOTES.md CLAUDE.md AGENTS.md GEMINI.md \
        .claude/skills/audit/SKILL.md docs/skills/06-audit.md
git commit -m "feat(C-rest): per-style Source samples + CLAUDE.md ## Citation + audit §D"
```

---

## Task 12: Cross-skill Source template propagation (`/note` and `/verify`)

**Files:**
- Edit: `.claude/skills/note/SKILL.md` (line 34 area)
- Edit: `.claude/skills/verify/SKILL.md` (line 41 area)

- [ ] **Step 1: Update `/note` SKILL.md**

Replace the hardcoded line:
```
**Source**: {full citation in Harvard style}
```

with:
```
**Source**: {citation in the project's declared style — see `_template_NOTES.md` for per-style samples; the active style is `Citation style:` in `CLAUDE.md`}
```

- [ ] **Step 2: Update `/verify` SKILL.md**

Replace the hardcoded line:
```
**Source**: [{source name}]({URL})
```

with:
```
**Source**: {citation in the project's declared style — see `_template_NOTES.md` for per-style samples; the active style is `Citation style:` in `CLAUDE.md`}
```

The previous URL/markdown-link form was inconsistent with the rest of the toolkit; verify and note now agree.

- [ ] **Step 3: Verify**

```bash
grep -n "Source" .claude/skills/note/SKILL.md .claude/skills/verify/SKILL.md
# Expected: both reference _template_NOTES.md and CLAUDE.md, no hardcoded format
bash scripts/test.sh   # still 28/28
```

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/note/SKILL.md .claude/skills/verify/SKILL.md
git commit -m "feat(C-rest): unhardcode Source line format in /note and /verify"
```

---

## Task 13: Local verification gate

- [ ] **Step 1: Full local check matrix per spec §6.1**

```bash
make doctor                                                      # exit 0
bash scripts/test.sh                                             # all 28 tests passed.
python3 scripts/audit-citations.py --help                        # exit 0
grep -rn 'placeholder\|TBD' .claude/skills/audit/ docs/skills/   # exit 1 (no matches)
git status                                                       # clean
git log --oneline master..HEAD                                   # ~12-14 C-rest commits
```

If all pass, proceed to T14.

---

## Task 14: Push + observe CI

- [ ] **Step 1: Push the branch**

```bash
git push -u origin feature/c-rest-citation
```

- [ ] **Step 2: Open PR**

```bash
gh pr create --base master --head feature/c-rest-citation \
    --title "C-rest: /audit citation enhancement (7 styles, 3 modes)" \
    --body "$(cat <<EOF
## Summary
- Implements registry-driven 7-style citation auditing per spec v2:
  Harvard, APA 7th, Chicago Author-Date, MLA 9, IEEE, Vancouver, GB/T 7714-2015.
- Three pairing modes (author-year / author-page / numeric); four tiers (0-3).
- 13 regression tests T19-T31; ~15 fixture corpora.
- Cross-skill Source-line propagation: /note and /verify keyed off CLAUDE.md.

## Spec
docs/superpowers/specs/2026-04-27-c-rest-citation-design.md (v2 with reviewer pass integrated)

## Test plan
- [ ] CI test workflow goes green (28 tests pass)
- [ ] make sync propagates ## Citation to AGENTS.md and GEMINI.md
- [ ] Regression rehearsal: phantom citation in clean_harvard fails T19, revert recovers

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Watch CI**

```bash
gh pr checks --watch --interval 15
```

Expected: `test` workflow goes green within ~1 minute.

---

## Task 15: Regression-catch rehearsal

- [ ] **Step 1: Add a phantom in `clean_harvard`**

```bash
echo "" >> tests/citation/fixtures/clean_harvard/chapters/ch01.md
echo "Per (NotInNotes 2024), this should fail T19." >> tests/citation/fixtures/clean_harvard/chapters/ch01.md
git add tests/citation/fixtures/clean_harvard/chapters/ch01.md
git commit -m "rehearsal(C-rest): T19 regression check (will revert)"
git push
```

- [ ] **Step 2: Observe CI red**

```bash
gh pr checks --watch --interval 15
```

Expected: `test` workflow fails; the failing assertion is in `test_T19` (or whatever test exercises `clean_harvard`).

- [ ] **Step 3: Revert**

```bash
git revert --no-edit HEAD
git push
```

- [ ] **Step 4: Observe CI green again**

```bash
gh pr checks --watch --interval 15
```

Expected: `test` workflow back to pass.

This pair of commits stays in the PR history as evidence the safety net catches phantoms; both are real commits (not amended).

---

## Task 16: Merge to master

- [ ] **Step 1: Final PR review**

Self-review on GitHub: scan the diff, confirm no debug `print()` left in `audit-citations.py`, no stray `TODO` markers, fixture files all small.

- [ ] **Step 2: Merge**

```bash
gh pr merge --squash --delete-branch
```

- [ ] **Step 3: Update local master**

```bash
git checkout master
git pull --ff-only
git log --oneline -3
```

Expected: most-recent commit is the squash of C-rest.

- [ ] **Step 4: Post-merge cleanup**

```bash
git fetch --prune origin
git branch
# Expected: only master remaining
```

- [ ] **Step 5: Save completion memory**

Update memory file (or add a chip) noting C-rest shipped on YYYY-MM-DD with the merge commit SHA, and that roadmap moves on to **B (new skills)**.

---

## Verification Summary (mirrors spec §8 acceptance criteria)

After T16 completes, ALL of the following must be true:

- [ ] `bash scripts/test.sh` reports `all 28 tests passed.` locally and in master CI.
- [ ] `make doctor` passes locally and in CI.
- [ ] §6.3 regression-catch rehearsal demonstrated T19 failure and recovery (T15).
- [ ] `make sync` propagates `## Citation` to AGENTS.md and GEMINI.md.
- [ ] `grep -rn 'placeholder\|TBD' .claude/skills/audit/ docs/skills/` returns no matches.
- [ ] PR squash-merged; remote branch deleted; local repo clean.

---

## Risks during implementation

| Risk | Mitigation |
|---|---|
| Regex over-anchoring rejects valid citations | Tune incrementally against fixtures; prefer permissive over strict at Tier 1 |
| `re.UNICODE` flag forgotten | Add a top-level constant `RE_FLAGS = re.UNICODE` and use everywhere |
| Tier 2 mis-classifies on small thesis | Already handled (`< 10` → insufficient data) |
| Long-running fixture creation blocks progress | Each fixture is < 30 lines; use heredoc shell creation if helpful |
| Python 3.8 compat slip (e.g., `dict | dict`) | T17 already validates; run `make test` between every commit |
| `make sync` errors on the new `## Citation` block | Verify SHARED markers in CLAUDE.md before running; sync-config.sh requires exactly one of each |
| Cross-skill template change introduces stale reference | Tier 0 lint over a fresh fixture covers regression |

---

## References

- Spec: [docs/superpowers/specs/2026-04-27-c-rest-citation-design.md](../specs/2026-04-27-c-rest-citation-design.md)
- Predecessor plans (style references):
  - [docs/superpowers/plans/2026-04-26-foolproofing-implementation.md](2026-04-26-foolproofing-implementation.md)
  - [docs/superpowers/plans/2026-04-27-c-emergency-implementation.md](2026-04-27-c-emergency-implementation.md)
  - [docs/superpowers/plans/2026-04-27-a-ci-tests-implementation.md](2026-04-27-a-ci-tests-implementation.md)
- Test harness: `scripts/test.sh`
- Memory: `project_c_rest_scope_expansion.md`
