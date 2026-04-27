# C-rest: `/audit` Citation Enhancement

**Status**: draft v1 (awaiting triple-reviewer pass + user sign-off)
**Date**: 2026-04-27
**Sub-project**: C-rest (toolkit roadmap; narrowed to Cluster 1 only — citation enhancement)
**Predecessors**: D — foolproofing (`981d28f`); C-emergency — R2 audit fixes (`9092294`); A — CI & tests (`71ee2e2`)
**Successors**: B (new skills) — depends on `/audit` having reliable citation logic so new skills can rely on the contract

---

## 1. Context

`/audit` (`.claude/skills/audit/SKILL.md`) is the toolkit's pre-submission consistency checker. It currently has four categories: numerical, terminological, cross-reference, and citation. The first three have concrete logic; **citation (§D) is a 2-line placeholder** ("the same work must be cited with the same author list and year throughout; in-text citations must match the reference list format") with no detection or pairing implementation.

The toolkit has a parallel-running notes infrastructure: each source has its own file in `literature/reading_notes/<slug>_NOTES.md`, with a free-text `**Source**:` line capturing the full citation. There is no central bibliography, no `.bib`, no `references.md`. Reference data is naturally distributed across notes files.

C-rest's roadmap line names citation as the `/audit` enhancement. After scope discussion, **C-rest is narrowed to this enhancement only** (Cluster 1 of a wider backlog); other deferred items (skill safety, CI maintenance, doc cleanup) ship as separate sub-projects or chips.

This sub-project depends on A having shipped because the new test suite (T19-T25) for citation logic uses A's CI workflow as the gate. It precedes B (new skills) so future skills can build on `/audit` having reliable citation enforcement instead of a placeholder.

## 2. Scope

**In scope:**

- Replace `/audit` §D placeholder with a real citation-checking implementation that does:
  - **Tier 1 — Pairing**: every in-text citation in `chapters/*.md` must have a matching `**Source**:` entry in `literature/reading_notes/*_NOTES.md` (and vice versa flagged as "unused").
  - **Tier 2 — Style consistency**: in-text citations across the manuscript should follow a single pattern. Outliers (e.g. mixed `(Smith, 2024)` and `(Smith 2024)`) are flagged.
  - **Tier 3 — Style format validation**: a chosen citation style (Harvard or APA) is declared in `CLAUDE.md`; in-text citations and `**Source**:` lines are validated against that style's text-level rules (parentheses, commas, et al. threshold, multi-author punctuation).
- Add a Python 3.8 stdlib-only script (`scripts/audit-citations.py`) that does the parsing and emits structured JSON. The `/audit` skill orchestrates and renders.
- Upgrade `**Source**:` field in `_template_NOTES.md` from a free-text comment to a strict single-line contract.
- Add a `## Citation` block to `CLAUDE.md` with a `Citation style: harvard | apa` field (D's existing `make sync` propagates this to AGENTS.md / GEMINI.md).
- Add 7 regression tests (T19-T25) to `scripts/test.sh` covering the three tiers and the Source contract lint.
- Add test fixture directory `tests/citation/fixtures/` with small chapter + notes mini-corpora so the regression tests run deterministically.
- Update `docs/skills/06-audit.md` (or whatever the user-doc filename is) to match the new `/audit` §D contract.

**Out of scope (deferred with rationale):**

- Chicago author-date, MLA, IEEE, Vancouver, GB/T 7714, and other styles. Out-of-scope because (a) Harvard / APA are the user's declared environment (British English in `CLAUDE.md`; roadmap memory only mentioned these two); (b) numeric styles (IEEE, Vancouver) need a different algorithm; (c) extending later is straightforward — Tier 3 is data-driven via a style-rules dict.
- BibTeX / `.bib` integration. Notes-as-source-of-truth is the existing infra (Q2 decision); `.bib` would be a parallel store with sync overhead.
- Auto-fix. `/audit` already has a "Never auto-fix" constraint (existing SKILL.md line 74); citation issues are reported, not patched.
- Citation graph visualisation, citation network analysis, anything beyond pair + format checks.
- Cross-language citation (Chinese theses commonly use GB/T 7714; out-of-scope per Harvard/APA-only decision).
- Multi-volume / chapter / page suffix in the in-text token (e.g. `Smith, 2024, ch. 3`). The match is on `(Lastname, Year)` only; trailing `, p. 42` or `, ch. 3` is tolerated and ignored. Page-precision pairing belongs in a future sub-project.
- Footnote-style citations (`Smith2024[^1]` with `[^1]: footnote`). Not used in the project's current notes infra; defer.
- LLM-driven citation parsing. Non-deterministic; thesis audit must be reproducible.
- Renaming `/audit` to `/audit-data` or splitting into `/audit-citations`. Single skill is fine; new tier is additive.
- New `make audit` target. The `/audit` skill is invoked through the agentic platform's command, not Make.

## 3. Design Decisions

Settled during brainstorming on 2026-04-27 (Q1-Q3 user-confirmed; Q4-Q10 auto-decided in auto mode with rationale). All ten captured here so reviewers can challenge each.

| # | Question | Decision | Why |
|---|----------|----------|-----|
| Q1 | Scope shape | Cluster 1 only (citation enhancement) | Roadmap memory's original intent; cluster 2/3/4 ship separately to keep one clear scope per cycle. User confirmed. |
| Q2 | Reference list source of truth | `literature/reading_notes/*_NOTES.md` `**Source**:` line | Reuse existing infra; no new bibliography file; `/note` and `/integrate` skills already operate on these files. User confirmed. |
| Q3 | Audit depth | Full = pair + consistency + format | User confirmed (chose option c). The first two tiers cover 80%+ of real errors; tier 3 adds value when the style is declared. |
| Q4 | Style support scope | Harvard + APA only | UK British English context (CLAUDE.md); roadmap memory listed these two; Chicago author-date is near-identical to Harvard (skip until evidence); MLA / IEEE / Vancouver use different algorithms (separate sub-project). |
| Q5 | `**Source**:` contract format | Strict single-line `Lastname, F. (YYYY). Title. *Publisher*, vol(issue), pages. https://doi.org/...` | Single line so `grep` parses; sentence-case title and italicised publisher per APA/Harvard convention; structured enough to extract `(lastname, year)` deterministically. |
| Q6 | Output destination | Extend `/audit` §D in existing report | Same skill, same report; new severity rows for citation-specific findings. No new skill, no new file. |
| Q7 | Auto-fix policy | Never (sustains existing constraint) | `/audit` SKILL.md line 74 already forbids auto-fix; citation findings list issues for user review. |
| Q8 | Implementation path | Python 3.8 stdlib-only script + skill orchestration | Deterministic and testable (unlike LLM parsing); regex+structured logic (unlike pure bash); matches `/export`'s `convert_to_docx.py` pattern; T17 already protects 3.8 compat in CI. |
| Q9 | Tier dependency model | Tier 1 always runs; Tier 2 detects style mode; Tier 3 needs declared style | Tier 1 is style-agnostic (pure pairing); Tier 2 is style-detection; Tier 3 is style-validation. Each tier consumes the previous tier's output. |
| Q10 | Where the chosen style lives | `CLAUDE.md` `## Citation` block | D's canonical-config principle; `make sync` propagates to AGENTS.md / GEMINI.md automatically. No CLI flag, no per-invocation override. |

## 4. Architecture & Components

### 4.1 Data flow

```
chapters/*.md  ───┐
                  ├──→  audit-citations.py  ──→  JSON  ──→  /audit skill  ──→  §D rows in audit report
literature/       │
  reading_notes/  │
  *_NOTES.md   ───┘

CLAUDE.md ── ## Citation: harvard ──→ audit-citations.py --style harvard
```

### 4.2 `scripts/audit-citations.py` interface

```
usage: audit-citations.py [-h] --base-dir DIR --style {harvard,apa} [--json] [--chapters-glob GLOB] [--notes-glob GLOB]

Required:
  --base-dir DIR        Project root containing chapters/ and literature/reading_notes/
  --style {harvard,apa} Citation style declared in CLAUDE.md

Optional:
  --json                Emit machine-readable JSON (default: human-readable text)
  --chapters-glob GLOB  Override chapter discovery glob (default: chapters/*.md)
  --notes-glob GLOB     Override notes discovery glob (default: literature/reading_notes/*_NOTES.md, excluding _template_NOTES.md)

Exit codes:
  0  no issues
  1  issues found (any tier)
  2  invalid arguments / missing CLAUDE.md style
```

The `/audit` skill always invokes with `--json` and parses the output. The text mode is for human ad-hoc runs.

### 4.3 JSON output schema

```json
{
  "schema_version": 1,
  "style": "harvard",
  "summary": {
    "tier1_phantom": 2,
    "tier1_unused": 1,
    "tier2_outliers": 3,
    "tier3_format_violations": 5,
    "tier0_notes_lint": 0
  },
  "issues": [
    {
      "tier": 1,
      "kind": "phantom",
      "severity": "critical",
      "location": "chapters/ch03.md:142",
      "message": "in-text citation (Smith, 2024) has no matching reading_notes/*_NOTES.md Source",
      "context": "...as Smith (2024) argued..."
    },
    {
      "tier": 3,
      "kind": "format-comma",
      "severity": "high",
      "location": "chapters/ch04.md:88",
      "message": "Harvard style: in-text should be `(Smith 2024)` without comma; found `(Smith, 2024)`",
      "context": "...(Smith, 2024)..."
    }
  ]
}
```

The `/audit` skill renders these into its existing table rows (§Output Format), adding citation as the new entries in the `Issues` table.

### 4.4 `**Source**:` contract (in `_template_NOTES.md`)

The current template has:
```
**Source**: {full citation, e.g. Author, A. (Year). Title. Publisher.}
```

After C-rest:
```
**Source**: Lastname, F. (YYYY). Title in sentence case. *Publisher or Journal*, vol(issue), pages. https://doi.org/...
```

Rules (enforced by `audit-citations.py` Tier 0 lint):
- Single line. No multi-line citation in `**Source**:`. (Multi-line splits the parser.)
- First field: `Lastname, F.` (one or more authors, separated by `,` or `, &` per APA/Harvard).
- Year: `(YYYY)` exactly four digits in parentheses, immediately after authors.
- Title: sentence case (first word capitalised; proper nouns retained); ends with `.`.
- Publisher / journal: italicised with `*...*` Markdown.
- Optional fields after publisher: volume, issue, pages, DOI URL. All separated by `,` or per style rules.
- For et al. (≥3 authors): full author list goes in the `**Source**:` field; the audit's pairing logic handles abbreviation in-text per style.

### 4.5 `CLAUDE.md` addition

After the existing "Writing Principles" section:

```markdown
## Citation

- Citation style: harvard
```

The single field `Citation style:` accepts values `harvard` or `apa`. Parser is **case-insensitive on input** (`Harvard`, `APA`, `harvard`, `apa` all valid) but the script normalises to lowercase internally and the `--style` argument accepts only lowercase to keep the CLI surface narrow. Unknown values exit 2 with a message listing accepted styles. Future styles add a row to the accepted-values set.

D's `scripts/sync-config.sh` already extracts the SHARED block; adding this section inside the SHARED markers propagates it to AGENTS.md / GEMINI.md on next `make sync`.

### 4.6 Tier algorithms

**Tier 0 — Notes file lint (Source format contract)**:

For each `_NOTES.md` (excluding `_template_NOTES.md`):
- Find the line starting with `**Source**:`. If absent, severity high.
- Validate single-line, single year `(YYYY)`, italicised publisher. Each violation is one issue.

**Tier 1 — Pair check**:

- Parse all `**Source**:` lines into `(lastname, year, title)` tuples. Build a set of `(lastname_lower, year)` keys.
- Parse all `chapters/*.md` for in-text citations using a permissive regex covering both Harvard and APA shapes:
  - `\(([A-Z][\w\-']+)(?:,\s+|\s+)(\d{4}[a-z]?)\)` (parenthetical: `(Smith 2024)` or `(Smith, 2024)`, with optional letter suffix)
  - `\b([A-Z][\w\-']+)\s+\((\d{4}[a-z]?)\)` (narrative: `Smith (2024)`)
  - Optional 2nd author: `& Lastname` or `and Lastname`
  - Et al. variants: `(Smith et al., 2024)`, `Smith et al. (2024)`
- Build set of `(lastname_lower, year)` from in-text matches.
- `phantom` = in-text - notes; `unused` = notes - in-text.

**Tier 2 — Style mode detection**:

- Classify each in-text occurrence into a pattern bucket:
  - `parens-comma`: `(Author, Year)` (APA / loose Harvard)
  - `parens-no-comma`: `(Author Year)` (strict Harvard)
  - `narrative`: `Author (Year)` (style-agnostic)
- Count occurrences per bucket. Mode = max count. Outliers = all that don't match the mode (excluding `narrative` which is allowed in both styles).
- If parens-comma and parens-no-comma counts are within 10% of each other, report "ambiguous mode" instead of picking one.

**Tier 3 — Style-specific format validation** (only if `--style` given):

- For each in-text occurrence:
  - **Harvard**: `(Author Year)` — no comma. Multi-author: `(Smith and Jones 2024)` or `(Smith & Jones 2024)`. Et al. threshold: ≥3 authors.
  - **APA**: `(Author, Year)` — comma required. Multi-author: `(Smith & Jones, 2024)`. Et al. threshold: ≥3 authors (APA 7th).
  - Narrative (`Author (Year)`) is valid in both.
- For each `**Source**:` line:
  - **Harvard**: `Smith, J. (2024) Title. Publisher.` — note: NO period after author initial group; year comma optional. (See note below.)
  - **APA**: `Smith, J. (2024). Title. *Publisher*.` — period after year-paren; sentence case title; italicised publisher.

(Note: Harvard variants differ across institutions. The implementation uses the most-conservative shared rules — both styles accept `Smith, J. (2024)` as the author/year prefix; the divergence is mainly in the post-title punctuation. Tier 3 flags only differences that are rule-level, not stylistic preference.)

### 4.7 In-text regex limits and exclusion zones

The in-text parser intentionally skips:
- Code fences (```` ``` ```` blocks)
- Inline code (`` ` ... ` ``)
- Frontmatter (lines before the second `---`)
- Markdown link URLs (`[...](https://example.com/2024)` — `2024` could match year regex)
- HTML comments (`<!-- ... -->`)

This is implemented as a preprocessing pass that strips these zones before regex matching.

### 4.8 File-level changes

| Action | Path | Why |
|---|---|---|
| new | `scripts/audit-citations.py` | Tier 0-3 logic; Python 3.8 stdlib-only |
| edit | `.claude/skills/audit/SKILL.md` | Replace §D placeholder; add invocation step calling `scripts/audit-citations.py --json`; document JSON schema briefly |
| edit | `docs/skills/06-audit.md` (verify filename) | User-doc mirror of SKILL.md |
| edit | `literature/reading_notes/_template_NOTES.md` | Upgrade `**Source**:` from free-text e.g. to strict format example |
| edit | `CLAUDE.md` | Add `## Citation` block inside SHARED markers |
| edit | `scripts/test.sh` | Append T19–T25 (citation regression tests) |
| new | `tests/citation/fixtures/` | Test data: small chapter + notes corpora for harvard, apa, mixed-style cases |
| new | `tests/citation/fixtures/clean_harvard/chapters/ch01.md` | Minimum clean Harvard corpus |
| new | `tests/citation/fixtures/clean_harvard/literature/reading_notes/example1_NOTES.md` | matching note |
| new | `tests/citation/fixtures/clean_apa/chapters/ch01.md` | Minimum clean APA corpus |
| new | `tests/citation/fixtures/clean_apa/literature/reading_notes/example1_NOTES.md` | matching note |
| new | `tests/citation/fixtures/phantom/chapters/ch01.md` | Has unmatched in-text citation |
| new | `tests/citation/fixtures/phantom/literature/reading_notes/.gitkeep` | empty notes dir |
| new | `tests/citation/fixtures/unused/chapters/ch01.md` | empty chapter |
| new | `tests/citation/fixtures/unused/literature/reading_notes/example1_NOTES.md` | unreferenced note |
| new | `tests/citation/fixtures/mixed_style/chapters/ch01.md` | Mixes Harvard/APA — Tier 2 should detect |
| new | `tests/citation/fixtures/source_lint_fail/literature/reading_notes/bad_NOTES.md` | Notes file with malformed `**Source**:` (multi-line, missing year, missing italics) — Tier 0 should flag |
| new | `tests/citation/fixtures/source_lint_fail/chapters/.gitkeep` | empty chapters dir |
| new | `tests/citation/fixtures/format_apa_in_harvard_project/CLAUDE.md` | declares `Citation style: harvard` |
| new | `tests/citation/fixtures/format_apa_in_harvard_project/chapters/ch01.md` | uses APA-style `(Smith, 2024)` (comma) — Tier 3 Harvard should flag the comma |
| new | `tests/citation/fixtures/format_apa_in_harvard_project/literature/reading_notes/example_NOTES.md` | matching note |
| new | `tests/citation/fixtures/format_harvard_in_apa_project/CLAUDE.md` | declares `Citation style: apa` |
| new | `tests/citation/fixtures/format_harvard_in_apa_project/chapters/ch01.md` | uses Harvard-style `(Smith 2024)` (no comma) — Tier 3 APA should flag the missing comma |
| new | `tests/citation/fixtures/format_harvard_in_apa_project/literature/reading_notes/example_NOTES.md` | matching note |
| new | `tests/citation/fixtures/multi_author_etal/chapters/ch01.md` | uses `(Smith et al., 2024)` (3+ authors) — Tier 3 verifies threshold and punctuation per style |
| new | `tests/citation/fixtures/multi_author_etal/literature/reading_notes/multi_NOTES.md` | matching note with 3-author full list |

Every fixture is < 30 lines so the test suite remains fast. Each fixture is its own self-contained mini-project (with its own `chapters/` and `literature/reading_notes/`); the audit script's `--base-dir` flag points at the fixture root, not the toolkit root.

## 5. Implementation Outline

The detailed step-by-step plan is the next phase (`writing-plans` skill). High-level sequence:

1. Add `tests/citation/fixtures/` corpora (drives TDD for the script).
2. Write `scripts/audit-citations.py` skeleton + Tier 0 lint, test against `clean_harvard` and Source-contract violation fixture.
3. Add Tier 1 pair check, test against `phantom` and `unused` fixtures.
4. Add Tier 2 style mode detection, test against `mixed_style` fixture.
5. Add Tier 3 Harvard rules, test against `clean_harvard`.
6. Add Tier 3 APA rules, test against `clean_apa`.
7. Add JSON output schema + argparse CLI surface.
8. Append T19–T25 to `scripts/test.sh`.
9. Edit `_template_NOTES.md` `**Source**:` contract.
10. Edit `CLAUDE.md` `## Citation` block; run `make sync` to propagate to AGENTS.md / GEMINI.md.
11. Edit `.claude/skills/audit/SKILL.md` §D + corresponding `docs/skills/06-audit.md`.
12. Local verification gate: `make doctor && make test` (all 22 = 15 + 7 new tests pass).
13. Push feature branch, open PR against `master`, observe CI.
14. Run regression-catch rehearsal: deliberately introduce a phantom citation in a fixture, observe T19 fail, revert.
15. Merge.

## 6. Verification

### 6.1 Local checks (run before push)

| Check | Command | Expected |
|---|---|---|
| Script runs cleanly on a clean Harvard fixture | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_harvard --style harvard` | exit 0; no issues |
| Script runs cleanly on a clean APA fixture | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_apa --style apa` | exit 0; no issues |
| Phantom citation flagged | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/phantom --style harvard --json` | exit 1; JSON issues array contains tier=1, kind="phantom" |
| Unused note flagged | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/unused --style harvard --json` | exit 1; tier=1, kind="unused" |
| Mixed-style flagged | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/mixed_style --style harvard --json` | exit 1; tier=2 outliers reported |
| Source contract violation flagged | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/source_lint_fail --style harvard --json` | exit 1; tier=0 notes-lint reported |
| Harvard format violation flagged | (use `tests/citation/fixtures/format_apa_in_harvard_project`) | exit 1; tier=3 format-comma issues |
| Test harness 22/22 green | `bash scripts/test.sh` | `all 22 tests passed.` |
| Doctor still green | `make doctor` | exit 0 |
| `make sync` doesn't break anything | `make sync && git diff --stat AGENTS.md GEMINI.md` | shows the new `## Citation` block propagated |
| Forward-looking grep clean | `grep -rn 'placeholder\|TBD' .claude/skills/audit/ docs/skills/` | exits 1 (no matches) |

### 6.2 CI pipeline checks

Same workflow as A. T19–T25 run as part of `make test`. Specifically:

| Test | Asserts |
|---|---|
| T19 | phantom citation detection (chapter cites unknown source) |
| T20 | unused source detection (notes file with no chapter mention) |
| T21 | style mode detection (mixed Harvard/APA → outlier reported) |
| T22 | harvard format strict (validates `(Smith 2024)` no comma; flags `(Smith, 2024)`) |
| T23 | apa format strict (validates `(Smith, 2024)` with comma; flags `(Smith 2024)`) |
| T24 | notes Source format contract lint (multi-line / missing year / missing italics) |
| T25 | et al. threshold + multi-author punctuation (≥3 authors per style) |

### 6.3 Regression-catch rehearsal (proves CI catches citation regressions)

After CI is green on the PR:
1. Add a phantom citation `(NotInNotes, 2024)` to `tests/citation/fixtures/clean_harvard/chapters/ch01.md`.
2. Push. Confirm CI fails on T19. Note: if A's branch protection is enabled (post-T10), merge is blocked.
3. Revert the change. Push. CI returns to green.

## 7. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Strict `**Source**:` contract breaks existing notes | Low (only `_template_NOTES.md` exists today; no real notes yet) | Tier 0 lint reports violations as "high" not "critical"; doesn't fail audit overall; user fixes notes incrementally |
| Regex miss real-world citation forms (e.g. quoted citations, hyphenated names with apostrophes) | Medium | Test fixtures cover edge cases; users can report misses as bugs; future sub-project widens the regex |
| Tier 2 mode detection mis-classifies on small thesis (e.g. only 5 in-text citations) | Low-Medium | Skip Tier 2 (return "insufficient data") if total in-text count < 10 |
| Italics validation is unreliable in plain Markdown (asterisks vs literal text) | Acknowledged | Spec §4.6 notes: italics are validated as text-level only (`*...*` pattern); no rendering check |
| Harvard variant ambiguity (different institutions have different rules) | Medium | Spec §4.6 notes: implementation uses most-conservative shared rules; flags only rule-level diffs |
| Python 3.8 sunset on GHA (~2024-10 EOL; might drop) | Low (A's spec already covered this risk) | If `setup-python@v5` drops 3.8, Python script still works on 3.10/3.11; no language-feature-3.8-specific code |
| `/audit` skill output format change breaks user expectations | Low | New rows added to existing table; no schema break for tiers 1-3; existing tiers (numerical, terminological, cross-ref) untouched |
| Adding `tests/citation/fixtures/` makes T2 (symlink check) discover them as "skills" | Low | T2 globs `.claude/skills/`, not `tests/`; no overlap |
| User has citations in formats this spec doesn't recognise (e.g. footnote-style) | Acknowledged | Out of scope per §2; user can add fixtures + extend regex in future sub-project |

## 8. Reviewer Pass

Per the standing memory rule (`Use codex + superpowers reviewers in parallel for design work`), this spec runs through:

- **codex spec review** (`gpt-5.4` — required per `feedback_review_combo.md`; default `gpt-5.5` requires newer Codex CLI; ChatGPT-account credential blocks `gpt-4o` / `gpt-5.3-codex-spark`).
- **codex project audit** (`gpt-5.4`) — independent audit of spec against current repo state.
- **superpowers:code-reviewer** (process review) — checks scope discipline, verification rigor, skill-discipline.

Findings will be triaged inline (accept / reject with rationale / defer-to-future-sub-project) before user sign-off.

## 9. References

- Predecessor specs:
  - [docs/superpowers/specs/2026-04-26-foolproofing-design.md](2026-04-26-foolproofing-design.md)
  - [docs/superpowers/specs/2026-04-27-c-emergency-design.md](2026-04-27-c-emergency-design.md)
  - [docs/superpowers/specs/2026-04-27-a-ci-tests-design.md](2026-04-27-a-ci-tests-design.md)
- Predecessor plans: D + C-emergency + A in `docs/superpowers/plans/`
- Test harness (extended in this sub-project): `scripts/test.sh`
- `/audit` skill (modified): `.claude/skills/audit/SKILL.md`
- `/note` skill (Source contract reader, NOT modified): `.claude/skills/note/SKILL.md`
- Roadmap memory: `D → C-emergency → A → C-rest → B`
- Codex model selection memory: `feedback_review_combo.md` (use `gpt-5.4` explicitly)
