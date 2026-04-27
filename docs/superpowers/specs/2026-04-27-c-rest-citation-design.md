# C-rest: `/audit` Citation Enhancement

**Status**: v2 (reviewer pass integrated; scope expanded to all 7 major styles; ready for plan-writing)
**Date**: 2026-04-27 (v1 morning; v2 evening after triple-reviewer pass + user-confirmed scope expansion)
**Sub-project**: C-rest (toolkit roadmap; narrowed to Cluster 1 only — citation enhancement)
**Predecessors**: D — foolproofing (`981d28f`); C-emergency — R2 audit fixes (`9092294`); A — CI & tests (`71ee2e2`); CI v6 bump (`e3bf461`); A doc fix (`3465ae3`)
**Successors**: B (new skills) — depends on `/audit` having reliable citation logic so new skills can rely on the contract

---

## v1 → v2 changelog (one-line each)

- **Scope expanded** from Harvard+APA only to all 7 major styles via a registry; user-confirmed 2026-04-27 ("需要内容足够宽泛"). Q4 retired, Q-MLA/Q-Num/Q-GB added.
- **Cross-skill Source template propagation** added to scope: `/note` and `/verify` SKILL.md must emit per-style Source format keyed off `CLAUDE.md` `Citation style:` (B5 from project audit).
- **CLAUDE.md `## Citation` block placement pinned** to inside `<!-- SHARED:START --> ... <!-- SHARED:END -->` so `make sync` propagates (B6).
- **Tier 3 style rules promoted to a per-style table**, no more contradictions; et al. threshold integers enumerated per style (B3, B4).
- **Pairing modes**: 3 modes (author-year, author-page, numeric); MLA weak-pairs on lastname; numeric pairs on count + gap detection (Q-MLA, Q-Num).
- **In-text regex Unicode-fixed**: surnames may contain accented Latin and CJK characters; `re.UNICODE` mandatory (M1).
- **Year suffix**: `(YYYY[a]?)` in both Source contract and pairing keys; suffix stripped during pair-match (M2).
- **`--style` CLI flag changed from required to optional**; absence skips Tier 3; exit code 2 reserved for genuine arg errors (M3).
- **Fixture matrix expanded** to 14 fixtures covering all 7 styles, edge cases, and per-skill-template cases (M4).
- **Per-test expected-output table** added in §6.2 (M5).
- **Acceptance criterion** added as §8 (M6).
- **Migration story** added as §9 (M7).
- **Severity vocabulary** enumerated in §4.4 JSON schema (m1).
- **Frontmatter exclusion** clarified: between first and second `---` markers, inclusive (m2).
- **`docs/skills/06-audit.md` filename confirmed**; v1 TODO removed (m4).
- **§4.9 exclusion-zones algorithm** sketched as preprocessing pass (m5).
- **SHARED marker** literal `<!-- SHARED:START -->` / `<!-- SHARED:END -->` quoted (m6).
- **`tests/` directory** explicitly noted as new (no `tests/` exists today; m7).
- **§5 step ordering**: CLI skeleton (argparse + `--help` + exit codes) first, then tier logic (n1).

---

## 1. Context

`/audit` (`.claude/skills/audit/SKILL.md`) is the toolkit's pre-submission consistency checker. It currently has four categories: numerical, terminological, cross-reference, and citation. The first three have concrete logic; **citation (§D) is a 2-line placeholder** with no detection or pairing implementation.

The toolkit has a parallel-running notes infrastructure: each source has its own file in `literature/reading_notes/<slug>_NOTES.md`, with a `**Source**:` line capturing the full citation. There is no central bibliography, no `.bib`, no `references.md`. Reference data is naturally distributed across notes files.

C-rest's roadmap line names citation as the `/audit` enhancement. After scope discussion, C-rest is narrowed to this enhancement only (Cluster 1). v2 broadens the supported style set in response to user direction.

## 2. Scope

**In scope (v2):**

- Replace `/audit` §D placeholder with a real, registry-driven citation-checking implementation supporting **7 styles**: Harvard, APA 7th, Chicago Author-Date, MLA 9, IEEE, Vancouver, GB/T 7714-2015. Each style is one row in a `CITATION_STYLES` registry; adding a new style is a registry-edit, not a code change.
- Three pairing modes:
  - **Author-Year**: Harvard, APA, Chicago Author-Date, GB/T 7714-2015. Pair `(lastname_lower, year_no_suffix)`.
  - **Author-Page**: MLA. Tier 1 weak-pair on lastname only (year/page not enforced at pair stage).
  - **Numeric**: IEEE, Vancouver, GB/T 7714-2005-style citations. Pair on count balance + gap detection (chapters' `[N]` set must equal notes count; no skipped integers).
- Three audit tiers (plus Tier 0 lint):
  - **Tier 0**: per-style `**Source**:` format lint over notes files.
  - **Tier 1**: pairing — phantom (cited but no Source) / unused (Source but uncited) / count-mismatch (numeric).
  - **Tier 2**: style mode detection — flag in-text outliers when manuscript drifts from declared mode.
  - **Tier 3**: per-style format validation — punctuation, et al. threshold, multi-author connector, etc.
- Add `scripts/audit-citations.py` (Python 3.8 stdlib-only), invoked by `/audit` skill, emitting structured JSON.
- Upgrade `**Source**:` field in `_template_NOTES.md` from free-text to **per-style sample blocks** (one block per style; the active one is decided by `CLAUDE.md` `Citation style:`).
- **Cross-skill Source template propagation**: update `.claude/skills/note/SKILL.md` and `.claude/skills/verify/SKILL.md` so they emit Source lines in the project's declared style. Without this, `/note` and `/verify` would write Source lines that fail Tier 0 lint on every fresh note (B5 finding from project audit).
- Add `## Citation` block to `CLAUDE.md` **inside the `<!-- SHARED:START -->` / `<!-- SHARED:END -->` markers** (so D's `make sync` propagates it to AGENTS.md / GEMINI.md). Field: `Citation style: harvard | apa | chicago-author-date | mla | ieee | vancouver | gb-t-7714-2015`.
- Add ~13 regression tests (T19–T31) to `scripts/test.sh` covering all three tiers across the seven styles and the Source contract lint.
- Add fixture corpora under `tests/citation/fixtures/` (NEW directory tree; no `tests/` exists today).
- Update `docs/skills/06-audit.md` to match the new `/audit` §D contract.

**Out of scope (deferred with rationale):**

- Chicago Notes-Bibliography variant (footnote-style). Different model from author-date; defer.
- BibTeX / `.bib` integration. Notes-as-source-of-truth (Q2) is the existing infra.
- Auto-fix. `/audit` already forbids auto-fix (existing constraint).
- Citation graph / network analysis.
- LLM-driven parsing. Non-deterministic; thesis audit must be reproducible.
- Renaming `/audit` or splitting into `/audit-citations`. Single skill, additive tier.
- New `make audit` target. `/audit` is invoked through the agentic platform's command, not Make.
- Strict numeric pairing (`[1] ↔ specific Source`). Numeric Tier 1 is count + gap only; strict map needs an explicit user-declared mapping which contradicts notes-as-source-of-truth. Belongs in a future render-step sub-project.
- Footnote-style citations (`Smith2024[^1]`). Not used in current notes infra.
- Chapter / page suffix in author-year forms (`(Smith, 2024, ch. 3)`). Tolerated and ignored at Tier 1; flagged at Tier 3 only if punctuation violates style.

## 3. Design Decisions

Settled during brainstorming on 2026-04-27. Q1–Q3 were user-confirmed at v1; Q4 was auto-decided at v1 and **explicitly retired in v2** in favour of registry-driven multi-style support per user direction; Q-MLA / Q-Num / Q-GB are the v2 user-confirmed decisions; Q5 v2 supersedes the v1 single-contract decision; Q6–Q10 carry over.

| # | Question | Decision (v2) | Why |
|---|----------|----------|-----|
| Q1 | Scope shape | Cluster 1 only (citation enhancement) | Roadmap memory's intent. User confirmed (v1). |
| Q2 | Reference list source of truth | `literature/reading_notes/*_NOTES.md` `**Source**:` line | Reuse existing infra; no new bibliography file. User confirmed (v1). |
| Q3 | Audit depth | Full = pair + consistency + format | User confirmed (v1). |
| ~~Q4~~ | ~~Style support scope~~ | ~~Harvard + APA only~~ — **superseded in v2** | Replaced by registry-driven 7-style support (Q4-v2 below). |
| Q4-v2 | Style support scope (v2) | All 7: Harvard, APA, Chicago Author-Date, MLA, IEEE, Vancouver, GB/T 7714-2015 | User confirmed 2026-04-27 evening ("需要内容足够宽泛"). Registry-driven so adding the 8th is a data-edit. |
| Q-MLA | MLA pairing strategy | (a) — Tier 1 weak-pair on lastname only; year/page not enforced | Strict pairing requires page-range field in Source which doesn't exist; lastname pairing catches phantom and unused; format validation handled by Tier 3. User confirmed via "三个都按你倾向走". |
| Q-Num | Numeric pairing strategy | (a) — count balance + gap detection; no `references.md` | Preserves Q2 (notes-as-source-of-truth). Strict `[N] ↔ Source` map deferred to a future render-step sub-project. User confirmed. |
| Q-GB | GB/T 7714 variant | 2015 (author-year) default; both ASCII and full-width punctuation accepted | More common in current Chinese thesis writing; mixed punctuation = warning, not fail. User confirmed. |
| Q5 | `**Source**:` contract format | **Per-style** sample (registry-driven); each style has one canonical sample line | v1 single-contract was Harvard/APA-shaped; per-style needed for MLA's page-list, IEEE's bracket-N, GB/T 7714's `[M]/[J]` type marker. Single line still required (`grep`-parseable). |
| Q6 | Output destination | Extend `/audit` §D in existing report | Same skill, same report; new severity rows. |
| Q7 | Auto-fix policy | Never (sustains existing constraint) | `/audit` SKILL.md already forbids; citation findings list issues. |
| Q8 | Implementation path | Python 3.8 stdlib-only script + skill orchestration | Deterministic and testable; T17 already protects 3.8 compat. |
| Q9 | Tier dependency model | Tier 0 always; Tier 1 always; Tier 2 detects mode; Tier 3 needs declared style | Each tier consumes the previous tier's output; `--style` absent skips Tier 3 only. |
| Q10 | Where the chosen style lives | `CLAUDE.md` `## Citation` block, **inside** `<!-- SHARED:START -->` / `<!-- SHARED:END -->` | D's canonical-config principle; `make sync` propagates to AGENTS.md / GEMINI.md. |

## 4. Architecture & Components

### 4.1 Data flow

```
chapters/*.md  ───┐
                  │
literature/       ├──→  audit-citations.py  ──→  JSON  ──→  /audit skill  ──→  §D rows in audit report
  reading_notes/  │      ↑
  *_NOTES.md   ───┘      │
                         │
CLAUDE.md  ── ## Citation: <style> ──┘
                         │
                  CITATION_STYLES registry
                  (in audit-citations.py)
```

### 4.2 Style registry

The registry is a Python `dict` literal at the top of `scripts/audit-citations.py`. One row per style. Adding the 8th style means adding a row, not changing logic.

Each row's fields:

| Field | Type | Purpose |
|---|---|---|
| `name` | str | Human-readable style name. |
| `mode` | `"author-year" | "author-page" | "numeric"` | Drives Tier 1 algorithm choice. |
| `intext_paren_pattern` | regex (str) | Parenthetical in-text citation. Must use `re.UNICODE`. |
| `intext_narrative_pattern` | regex (str) or `None` | Narrative form (`Smith (2024) argued...`). `None` for numeric styles. |
| `intext_paren_punct` | `"comma" | "no-comma" | "n/a"` | Tier 3 expected punctuation between author and year. |
| `etal_threshold` | int | Author count at which `et al.` MUST be used. |
| `etal_first_cite_only` | bool | If True (APA 7th), et al. from first citation; if False (Harvard, Chicago), only when author count ≥ threshold. |
| `multi_author_connectors` | list[str] | Allowed connectors in parens (e.g. `["and", "&"]` Harvard; `["&"]` APA). |
| `source_pattern` | regex (str) | Tier 0 lint regex for `**Source**:` line. |
| `source_sample` | str | The canonical example shown in `_template_NOTES.md` and emitted by `/note` skill. |
| `accepts_cjk_punct` | bool | True for `gb-t-7714-2015`; allows full-width `（），。：；` alongside ASCII. |
| `numeric_bracket_pattern` | regex (str) or `None` | For numeric styles only; matches `[N]` form. |

Sample registry rows (illustrative — exact regex pinned in plan):

```python
CITATION_STYLES = {
    "harvard": {
        "name": "Harvard",
        "mode": "author-year",
        "intext_paren_punct": "no-comma",
        "etal_threshold": 4,
        "etal_first_cite_only": False,
        "multi_author_connectors": ["and", "&"],
        "source_sample": "Smith, J. and Jones, K. (2024) Title in sentence case. *Publisher*.",
        "accepts_cjk_punct": False,
        ...
    },
    "apa": {
        "name": "APA 7th",
        "mode": "author-year",
        "intext_paren_punct": "comma",
        "etal_threshold": 3,
        "etal_first_cite_only": True,
        "multi_author_connectors": ["&"],
        "source_sample": "Smith, J., & Jones, K. (2024). Title in sentence case. *Publisher*. https://doi.org/...",
        "accepts_cjk_punct": False,
        ...
    },
    "chicago-author-date": {
        "name": "Chicago Author-Date (17th)",
        "mode": "author-year",
        "intext_paren_punct": "no-comma",
        "etal_threshold": 4,
        "multi_author_connectors": ["and"],
        "source_sample": "Smith, John, and Kim Jones. 2024. *Title in Title Case*. Publisher.",
        ...
    },
    "mla": {
        "name": "MLA 9",
        "mode": "author-page",
        "intext_paren_punct": "n/a",
        "etal_threshold": 3,
        "multi_author_connectors": ["and"],
        "source_sample": "Smith, John, and Kim Jones. *Title in Title Case*. Publisher, 2024.",
        ...
    },
    "ieee": {
        "name": "IEEE",
        "mode": "numeric",
        "etal_threshold": 7,  # IEEE allows up to 6 authors; 7+ → et al.
        "numeric_bracket_pattern": r"\[(?P<num>\d+)\]",
        "source_sample": "[1] J. Smith and K. Jones, \"Title in title case,\" *Journal*, vol. 12, no. 3, pp. 45-67, 2024.",
        ...
    },
    "vancouver": {
        "name": "Vancouver",
        "mode": "numeric",
        "numeric_bracket_pattern": r"\[(?P<num>\d+)\]|\((?P<num>\d+)\)",
        "source_sample": "1. Smith J, Jones K. Title in sentence case. Journal. 2024;12(3):45-67.",
        ...
    },
    "gb-t-7714-2015": {
        "name": "GB/T 7714-2015 (Author-Year)",
        "mode": "author-year",
        "intext_paren_punct": "comma",  # accepts both ASCII , and full-width ，
        "accepts_cjk_punct": True,
        "etal_threshold": 4,
        "source_sample": "Smith J, Jones K. Title in sentence case[J]. *Journal*, 2024, 12(3): 45-67.",
        ...
    },
}
```

### 4.3 `scripts/audit-citations.py` interface

```
usage: audit-citations.py [-h] --base-dir DIR [--style STYLE] [--json] [--chapters-glob GLOB] [--notes-glob GLOB]

Required:
  --base-dir DIR        Project root containing chapters/ and literature/reading_notes/

Optional:
  --style STYLE         Citation style; one of: harvard | apa | chicago-author-date | mla | ieee | vancouver | gb-t-7714-2015.
                        If omitted, Tier 3 is skipped (Tier 0/1/2 still run).
  --json                Emit machine-readable JSON (default: human-readable text).
  --chapters-glob GLOB  Override chapter discovery glob (default: chapters/*.md).
  --notes-glob GLOB     Override notes discovery glob (default: literature/reading_notes/*_NOTES.md, excluding _template_NOTES.md).

Exit codes:
  0  no issues at any tier
  1  issues found at any tier
  2  invalid arguments (unknown --style value, --base-dir not a directory, etc.)
```

The `/audit` skill always invokes with `--json --style <value-from-CLAUDE.md>` and parses the output. Text mode is for human ad-hoc runs.

### 4.4 JSON output schema

```json
{
  "schema_version": 1,
  "style": "harvard",
  "mode": "author-year",
  "summary": {
    "tier0_notes_lint": 0,
    "tier1_phantom": 2,
    "tier1_unused": 1,
    "tier1_count_mismatch": 0,
    "tier1_numeric_gap": 0,
    "tier2_outliers": 3,
    "tier3_format_violations": 5
  },
  "issues": [
    {
      "tier": 1,
      "kind": "phantom",
      "severity": "high",
      "location": "chapters/ch03.md:142",
      "message": "in-text citation (Smith, 2024) has no matching Source in literature/reading_notes/",
      "context": "...as Smith (2024) argued..."
    }
  ]
}
```

**Severity vocabulary** (full enumeration; m1 fix):
- `critical` — directly undermines thesis credibility (e.g., contradictory data; not used in citation tiers).
- `high` — citation cannot be resolved (phantom, unused, count mismatch).
- `medium` — style outlier in Tier 2; Tier 0 lint failure.
- `low` — Tier 3 stylistic violation that doesn't change meaning (e.g., comma vs. no-comma).
- `info` — informational; not a violation.

**Issue kinds** (enumerated):
- Tier 0: `notes-source-missing`, `notes-source-malformed`
- Tier 1: `phantom`, `unused`, `numeric-count-mismatch`, `numeric-gap`
- Tier 2: `style-outlier`, `ambiguous-mode`
- Tier 3: `format-comma`, `format-etal-threshold`, `format-connector`, `format-year-punct`, `format-cjk-punct`

### 4.5 `**Source**:` per-style contract

The current template has:
```
**Source**: {full citation, e.g. Author, A. (Year). Title. Publisher.}
```

After C-rest, `_template_NOTES.md` shows **all 7 sample formats** under the heading `### Source format examples (use the one matching your CLAUDE.md style)`, and the actual `**Source**:` line in real notes uses the active style. For example:

```
**Source**: Smith, J. (2024) Title in sentence case. *Publisher*.    # harvard
**Source**: Smith, J. (2024). Title in sentence case. *Publisher*.   # apa
**Source**: Smith, John. 2024. *Title in Title Case*. Publisher.     # chicago-author-date
**Source**: Smith, John. *Title in Title Case*. Publisher, 2024.     # mla
**Source**: [1] J. Smith, "Title in title case," *Journal*, vol. 12, no. 3, pp. 45-67, 2024.  # ieee
**Source**: 1. Smith J. Title in sentence case. Journal. 2024;12(3):45-67.                    # vancouver
**Source**: Smith J. Title in sentence case[J]. *Journal*, 2024, 12(3): 45-67.                # gb-t-7714-2015
```

**Common rules across all styles**:
- Single line. No multi-line citation in `**Source**:`.
- The `(YYYY)` or `YYYY` field permits a letter-suffix `(YYYY[a-z]?)` for same-author-same-year disambiguation. Pair-match strips the suffix when comparing against in-text citations that don't carry a suffix; when in-text DOES carry a suffix (e.g., `(Smith, 2024a)`), strict match is required.
- Style-specific punctuation, italics, and field order come from the registry's `source_pattern`.

### 4.6 `CLAUDE.md` `## Citation` block placement

The block is inserted **between the existing `Writing Principles` section and `<!-- SHARED:END -->`**, anchored to the literal markers `<!-- SHARED:START -->` and `<!-- SHARED:END -->` defined by `scripts/sync-config.sh`:

```markdown
<!-- SHARED:START -->
## Project Overview
...
## Writing Principles
...

## Citation

- Citation style: harvard
<!-- SHARED:END -->
```

`scripts/sync-config.sh` requires exactly one of each marker as standalone lines and propagates the SHARED block to AGENTS.md / GEMINI.md. The added section participates in this propagation automatically.

`audit-citations.py` reads this style by parsing `CLAUDE.md` for `^Citation style: (\S+)` (case-insensitive on the value); the parsed value is normalised to lowercase. The CLI flag `--style` overrides the file value.

### 4.7 Tier algorithms

#### Tier 0 — Notes file lint

For each notes file in the discovery glob (excluding `_template_NOTES.md`):
- Find the first line matching `^\*\*Source\*\*:`. If absent → kind `notes-source-missing`, severity `high`.
- Validate against `style.source_pattern` (or, when `--style` absent, against a permissive union pattern). Each violation → kind `notes-source-malformed`, severity `medium`, message names the missing field.
- Lint never fails the whole audit (severity ≤ `high` does not raise critical).

#### Tier 1 — Pairing

Algorithm depends on `style.mode`:

**author-year mode** (Harvard, APA, Chicago, GB-T-7714-2015):
- Parse all `**Source**:` lines → set of `(lastname_lower, year_int, year_suffix_or_empty)` tuples.
- Parse all `chapters/*.md` for in-text citations using a permissive regex covering both parenthetical and narrative forms. `re.UNICODE` flag mandatory; lastname character class is `[\wÀ-ɏ一-鿿\-']` (Latin + Latin Extended + CJK Unified Ideographs + hyphen + apostrophe).
- Build set of `(lastname_lower, year_int, year_suffix)` from in-text matches.
- `phantom` = in-text - notes (severity `high`).
- `unused` = notes - in-text (severity `high`).
- Year-suffix logic: if in-text has `(Smith, 2024a)` and Source has `(2024)` (no suffix), this is `phantom` (mismatch). If both have `2024a`, this is a match. If in-text has `(Smith, 2024)` and Source has `(2024a)`, strip suffix from Source for comparison and match.

**author-page mode** (MLA):
- Parse Source lines for lastname only (ignore page range).
- Parse chapters for `\(([Lastname]+)\s+\d+(?:-\d+)?\)` form.
- Build lastname sets. `phantom` = in-text - notes; `unused` = notes - in-text. Year and page intentionally not used at Tier 1.

**numeric mode** (IEEE, Vancouver):
- Extract every `\[(\d+)\]` (or other bracket pattern per registry) from chapters in document order.
- Record first-appearance order: `[1]`, `[2]`, ..., `[N]` ideally appear in increasing sequence.
- `numeric-count-mismatch` (severity `high`): unique `[N]` count != notes file count.
- `numeric-gap` (severity `medium`): integers `[N]` skip a value (e.g., chapters cite `[1] [2] [4]` with no `[3]`).
- Note: strict `[N] ↔ specific Source` pairing not done (out of scope, Q-Num).

#### Tier 2 — Style mode detection

For author-year and author-page modes (numeric mode skips Tier 2):
- Classify each in-text occurrence into a pattern bucket: `parens-comma` / `parens-no-comma` / `narrative` / `mla-author-page`.
- Mode = max-count bucket. Outliers = all others (excluding `narrative`).
- Total in-text count < 10 → return `info` "insufficient data" instead of mode detection.
- If two dominant buckets have counts within 10% → kind `ambiguous-mode`, severity `medium`.

#### Tier 3 — Per-style format validation

Only runs if `--style` is given. Walks every in-text occurrence and every Source line; for each, applies the registry's per-style rules:

- `intext_paren_punct`: matches `comma` / `no-comma` / `n/a` for the active style.
- `etal_threshold` and `etal_first_cite_only`: counts authors before each `et al.` and validates threshold; logs first-cite-only constraint per APA 7th.
- `multi_author_connectors`: validates the `and`/`&` connector against the active style's allowed list.
- `source_pattern`: matches the Source line against the style's regex; mismatches flagged as `format-*` kinds.
- `accepts_cjk_punct`: when False, full-width `，。：；` in source/in-text → `format-cjk-punct` (severity `low`).

### 4.8 Cross-skill Source template propagation (B5 fix)

These three files emit or display the Source format and must agree on a single source of truth:

- `_template_NOTES.md` (notes template — already in scope)
- `.claude/skills/note/SKILL.md` (currently line 34: `**Source**: {full citation in Harvard style}` — Harvard-only, hardcoded)
- `.claude/skills/verify/SKILL.md` (currently line 41: `**Source**: [{source name}]({URL})` — wrong shape entirely; URL/markdown-link form)

**Fix**:
- Both SKILL.md files reference `_template_NOTES.md` and `CLAUDE.md` `Citation style:` instead of hardcoding a Source format.
- Authoring instructions in each skill: "emit the Source line in the format matching `## Citation` in `CLAUDE.md`. Examples are in `literature/reading_notes/_template_NOTES.md`."
- Tier 0 lint will catch the rare case where a note is created with the wrong style format.

### 4.9 In-text regex limits and exclusion zones

The in-text parser performs a preprocessing pass that strips:
- Code fences (```` ``` ```` blocks; matched as `^```[^\n]*\n.*?\n```` ` `).
- Inline code (`` ` ... ` ``; matched as `` `[^`]+` ``).
- YAML frontmatter (the block delimited by the first `---` on line 1 and the next `---`; m2 fix — between inclusive).
- Markdown link URLs (`\[[^\]]+\]\([^)]+\)` — the `(...)` part is removed; inner text retained).
- HTML comments (`<!--.*?-->` non-greedy).

Pseudocode:

```python
def strip_zones(text: str) -> str:
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.DOTALL)  # YAML frontmatter
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)                  # code fences
    text = re.sub(r"`[^`]+`", "", text)                                     # inline code
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)                 # HTML comments
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)                    # link URLs (keep text)
    return text
```

The stripped text feeds Tier 1/2/3 regex. Line-number reporting: stripped zones are replaced with newlines (not deleted) so line numbers in the output match original-file line numbers.

### 4.10 File-level changes

| Action | Path | Why |
|---|---|---|
| new | `scripts/audit-citations.py` | Tier 0–3 logic + style registry; Python 3.8 stdlib-only |
| edit | `.claude/skills/audit/SKILL.md` | Replace §D placeholder; add invocation step calling `scripts/audit-citations.py --json`; document JSON schema briefly |
| edit | `.claude/skills/note/SKILL.md` | Line 34 `**Source**:` reference unhardcoded; point at `_template_NOTES.md` and `CLAUDE.md` `Citation style:` |
| edit | `.claude/skills/verify/SKILL.md` | Line 41 `**Source**:` shape unhardcoded; same as note |
| edit | `docs/skills/06-audit.md` | User-doc mirror of SKILL.md (filename confirmed; m4) |
| edit | `literature/reading_notes/_template_NOTES.md` | Replace single-line free-text with `### Source format examples` showing all 7 styles |
| edit | `CLAUDE.md` | Add `## Citation` block inside `<!-- SHARED:START -->` / `<!-- SHARED:END -->` |
| run  | `make sync` | Propagate to AGENTS.md / GEMINI.md (no manual edit) |
| edit | `scripts/test.sh` | Append T19–T31 (citation regression tests) |
| new  | `tests/citation/fixtures/` | NEW directory tree (no `tests/` exists today; m7) |

**Fixtures matrix** (under `tests/citation/fixtures/<name>/`; each has its own `chapters/` and `literature/reading_notes/`; sometimes `CLAUDE.md`):

| Fixture | Purpose | Style | Test |
|---|---|---|---|
| `clean_harvard` | Tier 0/1/3 baseline pass | harvard | T19 (Tier 1 phantom), T22 |
| `clean_apa` | Tier 0/1/3 baseline pass | apa | T19 (Tier 1 unused), T23 |
| `clean_chicago_ad` | Chicago Author-Date baseline | chicago-author-date | T26 |
| `clean_mla` | MLA author-page baseline | mla | T27 |
| `clean_ieee` | IEEE numeric baseline | ieee | T28 |
| `clean_vancouver` | Vancouver numeric baseline | vancouver | T29 |
| `clean_gb_2015` | GB/T 7714-2015 baseline (CJK) | gb-t-7714-2015 | T30 |
| `phantom` | unmatched in-text | harvard | T19 |
| `unused` | unreferenced note | harvard | T19 |
| `mixed_style` | Tier 2 outlier | (no style) | T21 |
| `source_lint_fail` | Tier 0 violation | harvard | T24 |
| `format_apa_in_harvard_project` | Tier 3 wrong-comma | harvard | T22 |
| `format_harvard_in_apa_project` | Tier 3 missing-comma | apa | T23 |
| `multi_author_etal` | et al. threshold + connector | per-style | T25, T31 |
| `numeric_gap` | `[1] [2] [4]` skip | ieee | T28 |

Total: ~15 fixtures; 13 tests T19–T31.

## 5. Implementation Outline

The detailed step-by-step plan is the next phase (`writing-plans` skill). High-level sequence (n1 fix: CLI skeleton first):

1. **CLI skeleton + style registry stub** — create `scripts/audit-citations.py` with argparse, exit codes, `--help`, empty `CITATION_STYLES = {}` dict.
2. **Add `tests/citation/fixtures/clean_harvard/`** corpus + helper to invoke the script in tests.
3. **Tier 0 lint** + `harvard` registry row — test against `clean_harvard` and `source_lint_fail`.
4. **Tier 1 author-year pair** + `apa` registry row — test against `phantom`, `unused`, `clean_apa`.
5. **Tier 2 mode detection** — test against `mixed_style`.
6. **Tier 3 author-year format rules** — test against `format_apa_in_harvard_project`, `format_harvard_in_apa_project`, `multi_author_etal`.
7. **Add `chicago-author-date`, `gb-t-7714-2015` rows** — test against their clean fixtures.
8. **Author-page mode + `mla` row** — test against `clean_mla`.
9. **Numeric mode + `ieee`, `vancouver` rows** — test against `clean_ieee`, `clean_vancouver`, `numeric_gap`.
10. **Append T19–T31 to `scripts/test.sh`**.
11. **Edit `_template_NOTES.md`** to per-style sample blocks.
12. **Edit `CLAUDE.md`** `## Citation` block inside SHARED markers; run `make sync` to propagate.
13. **Edit `.claude/skills/audit/SKILL.md` §D** + corresponding `docs/skills/06-audit.md`.
14. **Edit `.claude/skills/note/SKILL.md` line 34** and `.claude/skills/verify/SKILL.md` line 41** to drop hardcoded Source shapes.
15. **Local verification gate**: `make doctor && make test` (all 28 = 15 + 13 new tests pass).
16. **Push feature branch, open PR against `master`, observe CI**.
17. **Regression-catch rehearsal** — introduce a phantom citation in a fixture, observe T19 fail, revert.
18. **Merge**.

## 6. Verification

### 6.1 Local checks (run before push)

| Check | Command | Expected |
|---|---|---|
| Script `--help` works | `python scripts/audit-citations.py --help` | exit 0; usage printed |
| Clean Harvard | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_harvard --style harvard --json` | exit 0 |
| Clean APA | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_apa --style apa --json` | exit 0 |
| Clean Chicago AD | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_chicago_ad --style chicago-author-date --json` | exit 0 |
| Clean MLA | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_mla --style mla --json` | exit 0 |
| Clean IEEE | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_ieee --style ieee --json` | exit 0 |
| Clean Vancouver | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_vancouver --style vancouver --json` | exit 0 |
| Clean GB/T 7714-2015 | `python scripts/audit-citations.py --base-dir tests/citation/fixtures/clean_gb_2015 --style gb-t-7714-2015 --json` | exit 0 |
| Phantom flagged | `--base-dir tests/citation/fixtures/phantom --style harvard --json` | exit 1; tier=1, kind=phantom |
| Unused flagged | `--base-dir tests/citation/fixtures/unused --style harvard --json` | exit 1; tier=1, kind=unused |
| Mixed-style flagged | `--base-dir tests/citation/fixtures/mixed_style --json` (no `--style` → Tier 3 skipped) | exit 1; tier=2, kind=style-outlier |
| Source lint fail | `--base-dir tests/citation/fixtures/source_lint_fail --style harvard --json` | exit 1; tier=0, kind=notes-source-malformed |
| Wrong-comma | `--base-dir tests/citation/fixtures/format_apa_in_harvard_project --style harvard --json` | exit 1; tier=3, kind=format-comma |
| Numeric gap | `--base-dir tests/citation/fixtures/numeric_gap --style ieee --json` | exit 1; tier=1, kind=numeric-gap |
| Test harness 28/28 | `bash scripts/test.sh` | `all 28 tests passed.` |
| Doctor | `make doctor` | exit 0 |
| `make sync` propagates | `make sync && grep -c "## Citation" AGENTS.md GEMINI.md` | both files contain `## Citation` |
| Forward-looking grep clean | `grep -rn 'placeholder\|TBD' .claude/skills/audit/ docs/skills/` | exit 1 (no matches) |

### 6.2 CI tests T19–T31 (per-test expected output; m5 fix)

Each test invokes the script against a fixture and asserts on exit code + JSON kind/severity (parsed via `python -c "import sys, json; ..."`).

| Test | Fixture | `--style` | Expected exit | Expected primary kind | Severity |
|---|---|---|---|---|---|
| T19 | `phantom` | harvard | 1 | `phantom` | high |
| T20 | `unused` | harvard | 1 | `unused` | high |
| T21 | `mixed_style` | (omit) | 1 | `style-outlier` | medium |
| T22 | `format_apa_in_harvard_project` | harvard | 1 | `format-comma` | low |
| T23 | `format_harvard_in_apa_project` | apa | 1 | `format-comma` | low |
| T24 | `source_lint_fail` | harvard | 1 | `notes-source-malformed` | medium |
| T25 | `multi_author_etal` (3-author) | apa | 1 | `format-etal-threshold` (APA et al. from 3rd author first cite) | low |
| T26 | `clean_chicago_ad` | chicago-author-date | 0 | (no issues) | — |
| T27 | `clean_mla` + `unused` MLA variant | mla | 1 | `unused` (lastname-only pair) | high |
| T28 | `numeric_gap` | ieee | 1 | `numeric-gap` | medium |
| T29 | `clean_vancouver` | vancouver | 0 | (no issues) | — |
| T30 | `clean_gb_2015` (mixed full-width and ASCII commas) | gb-t-7714-2015 | 0 | (CJK punct accepted) | — |
| T31 | `multi_author_etal` (Harvard 4-author) | harvard | 1 | `format-etal-threshold` | low |

### 6.3 Regression-catch rehearsal

After CI is green on the PR:
1. Add a phantom citation `(NotInNotes, 2024)` to `tests/citation/fixtures/clean_harvard/chapters/ch01.md`.
2. Push. Confirm CI fails on T19 and `clean_harvard`.
3. Revert. Push. CI returns to green.

## 7. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Strict `**Source**:` contract breaks existing notes | Low (zero real notes today; only template) | Tier 0 reports as `medium` not `critical`; never blocks audit |
| Regex misses real-world citation forms (quotes, accented names) | Medium | `re.UNICODE` + Latin Extended + CJK class; fixtures cover edge cases; misses are bugs, not crashes |
| Tier 2 mis-classifies on small thesis | Low-Medium | Skip Tier 2 when total in-text count < 10 |
| Italics validation unreliable in Markdown | Acknowledged | Validated as text-level `*...*` pattern; no rendering check |
| Style-variant ambiguity (Harvard differs across institutions) | Medium | Most-conservative shared rules; flags only rule-level diffs not stylistic preference |
| Numeric pairing weak by design (Q-Num) | Acknowledged | Documented; strict `[N] ↔ Source` map deferred to render-step sub-project |
| MLA pairing weak by design (Q-MLA) | Acknowledged | Documented; lastname-only Tier 1 catches phantom/unused; format validation in Tier 3 |
| GB/T 7714 CJK punctuation regex complexity | Medium | `accepts_cjk_punct: True` allows both ASCII and full-width; warning not fail on mixed |
| Python 3.8 EOL on GHA | Low | Script uses no 3.8-specific features; runs on 3.10/3.11/3.12 unchanged |
| `/audit` skill output format change breaks user expectations | Low | New rows added to existing report; existing tiers untouched |
| Adding `tests/citation/fixtures/` collides with future `tests/` use | Low | Subdir `tests/citation/`; future uses get sibling subdirs |
| Cross-skill Source template change introduces stale doc | Low (`/note` and `/verify` reference template; no hardcode after change) | Tier 0 lint catches any drift |

## 8. Acceptance Criterion (M6 fix)

**Sub-project ends when ALL of:**
1. `bash scripts/test.sh` reports `all 28 tests passed.` locally and in CI.
2. `make doctor` passes locally and in CI.
3. The §6.3 regression-catch rehearsal demonstrates T19 fails on a phantom and recovers on revert.
4. `make sync` propagates `## Citation` to AGENTS.md and GEMINI.md without errors.
5. `grep -rn 'placeholder\|TBD' .claude/skills/audit/ docs/skills/` returns no matches.
6. PR is approved (single-user repo: self-review explicit) and merged via `gh pr merge --squash`.

## 9. Migration Story (M7 fix)

C-rest tightens an existing soft contract. The migration must be non-breaking:

- **Existing notes today**: 0 real `_NOTES.md` files (only `_template_NOTES.md`). Zero migration cost.
- **Future notes written under old `/note` skill**: not possible — `/note` is updated as part of this sub-project (§4.8).
- **Tier 0 lint policy**: violations emit `medium` severity, never `critical`. They fail Tier 0 (kind `notes-source-malformed`) but the audit overall still completes; user fixes notes incrementally.
- **No auto-migration script**: bringing a notes file into compliance is one-line manual edit; no need for a tool.
- **CLAUDE.md changes**: `make sync` regenerates AGENTS.md and GEMINI.md; existing user customisations to those generated files would be lost on `make sync` — but D's foolproofing flags them as auto-generated (`AGENTS.md` and `GEMINI.md` are output, not input).
- **Rollback**: revert the merge commit. No data structures change; only added files and edited skill text. Fully reversible.

## 10. Reviewer Pass v2 (retrospective)

Per `feedback_review_combo.md`, this spec ran through:

- **codex spec review** (codex CLI; gpt-5.4 fallback effective) — found 2 BLOCKERs, 4 MAJORs, 4 MINORs / NITs. All integrated above.
- **codex project audit** — local Read/Bash audit (codex CLI 1.0.4 incompatible with default model; fell back to direct read). Found 2 integration BLOCKERs (B5 cross-skill Source mismatch; B6 SHARED-marker placement). Both integrated.
- **superpowers process review** — found 1 BLOCKER (reviewer pass not yet executed; resolved by this v2), 1 BLOCKER on Q4/Q5 user-confirm requirement (resolved by user direction 2026-04-27 evening; Q4 retired, Q5 superseded). 4 MAJORs (Tier 3 contradictions, T-spec assertion-shape, acceptance criterion, rollback story). All integrated.

v1 → v2 patch log: see top-of-document changelog.

## 11. References

- Predecessor specs:
  - [docs/superpowers/specs/2026-04-26-foolproofing-design.md](2026-04-26-foolproofing-design.md)
  - [docs/superpowers/specs/2026-04-27-c-emergency-design.md](2026-04-27-c-emergency-design.md)
  - [docs/superpowers/specs/2026-04-27-a-ci-tests-design.md](2026-04-27-a-ci-tests-design.md)
- Predecessor plans: D + C-emergency + A in `docs/superpowers/plans/`
- Test harness (extended in this sub-project): `scripts/test.sh`
- `/audit` skill (modified): `.claude/skills/audit/SKILL.md`
- `/note` skill (Source line emitter, modified): `.claude/skills/note/SKILL.md`
- `/verify` skill (Source line emitter, modified): `.claude/skills/verify/SKILL.md`
- `make sync` mechanism: `scripts/sync-config.sh`
- Roadmap memory: `D → C-emergency → A → C-rest → B`
- Scope expansion memory: `project_c_rest_scope_expansion.md`
