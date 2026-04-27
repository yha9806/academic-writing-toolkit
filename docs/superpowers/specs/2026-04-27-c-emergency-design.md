# C-emergency: Fix R2 Audit Bugs

**Status**: draft v2 (post triple-reviewer pass; awaiting user sign-off)
**Date**: 2026-04-27
**Sub-project**: C-emergency (toolkit roadmap)
**Predecessors**: D — foolproofing & multi-platform robustness (shipped `981d28f`, 2026-04-27)
**Successors**: A (CI & tests for skills) → C-rest (skill polish, citation format) → B (new skills)

---

## 1. Context

The 2026-04-26 R2 codex audit of `academic-writing-toolkit` flagged seven bugs — two BLOCKERs, three MAJORs, two MINORs — affecting skill contracts and user-facing documentation. Verification on 2026-04-27 confirmed all seven remained unfixed.

The two BLOCKERs (`${CLAUDE_SKILL_DIR}` hardcode and missing pandoc preflight) make `/export` unreachable on Codex / Gemini / OpenClaw despite the toolkit's documented multi-platform claim. The three MAJORs cause silent contract drift between user-facing docs (CLAUDE.md, README.md, .cursor) and skill implementations, breaking `/progress` and `/integrate` for users who follow the documented status enum or output-directory names. The two MINORs are stale references (`compile_pdf.py`) and split vocabulary (`/map` vs `/note`).

Sub-project D shipped foolproofing safeguards but did **not** address pre-existing skill bugs; those were deferred to this sub-project per the roadmap chosen on 2026-04-26. C-emergency precedes A (test infrastructure) because BLOCKERs in `/export` block users *now*, while CI is a long-term safety net.

The triple-reviewer pass on 2026-04-27 (codex spec review at gpt-5.4, codex project audit at gpt-5.4, superpowers process review) surfaced **three additional bugs** (#8 Python 3.8 compat, #9 `/map` `allowed-tools`, #10 `/verify` `allowed-tools`) and an **adjacent doc fix** (OpenClaw setup) that all qualify under the user's "B + adjacent cleanup" scope decision. Several substantive enhancements to the existing fixes were also accepted (Bug #2 stronger probe + adjacent docs unification; Bug #7 `docs/skills/02-note.md` expansion; T14 vocab tightening; T13 narrowing to `revisiting`-only). Reviewer-flagged items deferred to subsequent sub-projects are listed in §2.

## 2. Scope

**In scope:**
- Fix R2 Bugs #1–#7.
- Fix three new bugs surfaced during reviewer pass (#8 Python 3.8 compat, #9 `/map` `allowed-tools`, #10 `/verify` `allowed-tools`).
- Fix one adjacent doc bug surfaced during reviewer pass (`docs/setup-openclaw.md:38` instructs editing `AGENTS.md` directly, but D made `AGENTS.md` a generated artefact).
- Strengthen Bug #2 fix per codex spec review (smoke probe + try/except fallback + adjacent docs unification).
- Expand Bug #7 fix to include `docs/skills/02-note.md:204-211` (which currently teaches the 6-element vocab as "the standard types").
- Tighten regression tests T13 (narrow to `revisiting` + manual review), T14 (ban whole deprecated vocab in all affected files), and add T17 (Python 3.8 import sanity), T18 (allowed-tools / Write+Edit / Read+Edit consistency).

**Out of scope (deferred with rationale):**
- New skills (defer to B).
- Citation format checking — Harvard/APA detection, in-text ↔ reference list pairing (defer to C-rest, becomes a `/audit` enhancement).
- pytest / unit-test framework for Python scripts (defer to A).
- Re-architecting `/map` and `/note` data contracts beyond vocabulary alignment.
- **Export symlink / path-traversal validation** in `convert_to_docx.py` — codex audit recommended C-emergency, but the threat model (single-user thesis tool, not a public service) makes this over-engineering for current usage. Defer to C-rest as a security-pass item.
- **D-script cwd contract** (`sync-config.sh`, `doctor.sh`, `repair.sh` assume `cwd == repo root`) — does not break `make ...` flow; defer to C-rest.
- **`sync-config.sh` `.new` race** (concurrent `make sync`/`make repair` could stomp) — track for C-rest.
- **`docs/setup-cursor.md:51`** treating `AGENTS.md` as user-editable — defer to C-rest (Cursor docs are lower priority than OpenClaw, which is in the toolkit's headline platform list).
- **README VS Code Copilot row claim** (`README.md:138` says "Full" but no `docs/setup-vscode-copilot.md` exists) — defer to C-rest doc-pass.

## 3. Design decisions

The following design decisions were settled during brainstorming on 2026-04-27 (Q1–Q5) and refined after the triple-reviewer pass.

| # | Question | Decision | Why |
|---|---|---|---|
| Q1 | Scope shape | "B" — 7 R2 bugs + adjacent cleanup; reviewer pass triggered at spec stage | Cheap to bundle; reviewer combo is the project's standing rule for non-trivial specs. Reviewer pass added 3 more bugs that fit the same scope. |
| Q2 | Bug #1 fix path | Cwd-relative path: `python .claude/skills/export/scripts/convert_to_docx.py` | Matches D's `$REPO_ROOT/...` pattern; minimal change; works on every platform without env vars or wrappers |
| Q3 | Bug #4 canonical name | `final_output/` | User-facing CLAUDE.md / AGENTS.md / GEMINI.md / README.md already say it; only 2 skill-internal files need editing; "final" semantically fits submission-ready output |
| Q4 | Bug #7 vocabulary | Stance-only set: `supports / challenges / extends`; `/map` AND `docs/skills/02-note.md` adopt `/note` template's vocab | `_template_NOTES.md` is declared the data contract; no real notes files exist yet (zero migration cost); stance is what `/integrate` actually consumes |
| Q5 | Verification | Extend `scripts/test-foolproofing.sh` with cheap grep-based regression cases; no new framework | D's harness is already in place; pandoc-preflight unit test deferred to A |
| R1 | Bug #2 probe strength | Use `pypandoc.get_pandoc_version()` smoke (calls `pandoc --version` internally) instead of bare `shutil.which("pandoc")`; wrap first `pypandoc.convert_file()` call in try/except with python-docx fallback on any pandoc runtime failure | Codex spec review showed `which` proves only the binary name is on PATH; broken Snap-isolation, missing libs, or wrappers still crash. Smoke probe + runtime fallback is defence in depth at low cost (one stdlib call + one try/except). |
| R2 | Bug #2 adjacent docs | Unify "pandoc" and "pypandoc" in `.claude/skills/export/SKILL.md:30` and `docs/skills/08-export.md:56-58,123-129` — they describe the same code path | Codex spec review found the docs still treat pandoc and pypandoc as alternatives; after the preflight fix, that's misleading. Adjacent drift, fits "B" scope. |
| R3 | Bug #8 (NEW) — Python 3.8 compat | Add `from __future__ import annotations` at top of `convert_to_docx.py`; do not refactor type hints | Codex audit BLOCKER: `tuple[int, int]` (PEP 585) at lines 205, 214, 223 fails on Python 3.8 import. `from __future__ import annotations` is a one-line fix that postpones all annotation evaluation. Same multi-platform-regression class as R2 Bugs #1, #2. |
| R4 | Bug #9 (NEW) — `/map` Write missing | Add `Write` to `.claude/skills/map/SKILL.md:4` `allowed-tools` line | Codex audit + substitute audit both flagged: line 62 says "use Write (if creating new)" but allowed-tools is `Read, Glob, Grep, Edit`. First-time save fails. One-line fix. |
| R5 | Bug #10 (NEW) — `/verify` Read missing | Add `Read` to `.claude/skills/verify/SKILL.md:4` `allowed-tools` line | Substitute audit flagged: lines 27 + 61 use `Edit` to annotate notes file, but Edit requires a prior Read per harness contract. allowed-tools is `WebSearch, WebFetch, Edit`. Annotation always fails. One-line fix. |
| R6 | OpenClaw doc adjacent | Rewrite `docs/setup-openclaw.md:38` Configuration paragraph to say users edit `CLAUDE.md` (canonical) and run `make sync`, not edit `AGENTS.md` directly | Codex audit found this contradicts D's canonical-config model. Same drift class as Bug #5 (PDF claim). 3-line edit. |
| R7 | T13 narrowing | Drop the brittle `\bcomplete\b[^d]` half; T13 asserts only "no `\brevisiting\b` anywhere"; add a manual-review note in §6 for `complete` vs `completed` | Reviewers concur the `complete` regex would have false positives in prose ("complete reading", "must complete"). Narrowing trades automation breadth for reliability. |
| R8 | T14 strengthening | Ban whole deprecated vocab `\b(argue|cite|data|method)\b` in `.claude/skills/map/`, `docs/skills/04-map.md`, and `docs/skills/02-note.md`; with explicit allowed-context exemptions for `cite/data/method` as ordinary English (e.g., `data consistency`, `must cite the source`, `handle_data`) | Codex spec review showed bare `\bargue\b` passes if `cite/data/method` strays remain. The strengthened test scopes to **table-cell context** (cells delimited by `|`) to avoid prose false positives. |

## 4. Bug-fix specification

### 4.1 Bug #1 — `${CLAUDE_SKILL_DIR}` hardcode (BLOCKER)

**Problem.** `.claude/skills/export/SKILL.md:34` and `docs/skills/08-export.md:61` instruct the model to invoke the converter via `python ${CLAUDE_SKILL_DIR}/scripts/convert_to_docx.py`. `$CLAUDE_SKILL_DIR` is a Claude Code-only environment variable; on Codex / Gemini / OpenClaw it is undefined, so the command becomes `python /scripts/convert_to_docx.py` and fails.

**Fix.** Use a cwd-relative path that resolves identically on every platform.

- `.claude/skills/export/SKILL.md:34` — change to `python .claude/skills/export/scripts/convert_to_docx.py \`.
- `docs/skills/08-export.md:61` — same change in the workflow code block.
- `.claude/skills/export/SKILL.md` — add one prose line in the Workflow section: "Run from the project root." Insert immediately above step 1.

**Rationale.** Sub-project D established the convention `bash scripts/<name>.sh` and `python scripts/...` from project root; this fix extends the same convention to `/export`. No new wrapper needed because the python script already accepts `--base-dir` for everything path-related.

**Acceptance.** Regression test T11 (no `CLAUDE_SKILL_DIR` in skill files); manual smoke test in Codex CLI confirms `/export chapters` no longer fails.

### 4.2 Bug #2 — pypandoc preflight (BLOCKER) — strengthened per R1+R2

**Problem.** `scripts/convert_to_docx.py:25-32` sets `USE_PANDOC = True` whenever `import pypandoc` succeeds, regardless of whether the system `pandoc` binary exists. If pypandoc is installed but pandoc is not (or pandoc is on PATH but broken — Snap-isolated, missing shared libs, wrapper that fails to exec), the conversion fails at `pypandoc.convert_file()` time with an opaque traceback rather than falling through to the python-docx fallback. The current docs at `.claude/skills/export/SKILL.md:30` and `docs/skills/08-export.md:56-58,123-129` further confuse this by listing "pandoc" and "pypandoc" as separate methods, when in fact they are the same code path (pypandoc shells out to pandoc).

**Fix (strengthened per R1).**

```python
import shutil

USE_PANDOC = False
try:
    import pypandoc
    # Smoke probe: get_pandoc_version() shells out to `pandoc --version` internally
    # and raises if the binary is missing or broken (Snap isolation, missing libs).
    pypandoc.get_pandoc_version()
    USE_PANDOC = True
except (ImportError, OSError, RuntimeError):
    pass
```

Additionally, wrap the first `pypandoc.convert_file()` call site in `convert_file()` (around `convert_to_docx.py:83-89`) and `create_cover()` (around `:247-258`) in try/except. On any pandoc-side `RuntimeError`, log a one-line warning and fall through to `_convert_with_docx()` for that file. This is defence in depth: even if the smoke probe passes, a single broken file shouldn't crash the batch.

If neither pypandoc-with-working-pandoc nor python-docx is available, the existing `sys.exit(...)` path runs with the current message, extended:

```
Error: No conversion backend available.
  - pypandoc is installed but `pandoc` binary is missing/broken on PATH.
  - python-docx + markdown fallback is also missing.
Install one of:
  pip install pypandoc      (also requires `pandoc` binary)
  pip install python-docx markdown
```

**Adjacent docs unification (per R2).** After the smoke-probe fix, the docs listing pandoc and pypandoc as separate methods becomes misleading. Unify:

- `.claude/skills/export/SKILL.md:30` — change "Verify that `pandoc` or `pypandoc` is available." to "Verify that `pypandoc` is installed AND a working `pandoc` binary is on PATH (the script smoke-probes via `pypandoc.get_pandoc_version()`)."
- `docs/skills/08-export.md:56-58` — same change in the workflow code block.
- `docs/skills/08-export.md:123-129` — collapse the "pandoc / pypandoc / python-docx" three-row table to two rows: (1) "pypandoc + pandoc binary" Preferred, (2) "python-docx + markdown" Fallback.

**Acceptance.** Manual regression: in a clean venv with `pip install pypandoc python-docx markdown` but no `pandoc` binary on PATH, the script reports "Conversion method: python-docx + markdown (fallback)" rather than crashing. Today the script crashes mid-conversion. **No automated regression test in T11–T18** — pandoc-preflight unit testing is deferred to sub-project A; flag explicitly that if A slips, Bug #2 has no automated guard, and this manual procedure should be A's first test.

### 4.3 Bug #3 — Status enum drift (MAJOR) + adjacent README fixes

**Problem.** Three documented status enums conflict:
- `README.md:212` — `reading` or `complete`
- `README.md:123` — `reading / completed` (missing `integrated`)
- `.cursor/rules/academic-writing.mdc:9` — `reading | complete | revisiting`
- Skills (`note`, `progress`, `integrate`) — `reading | completed | integrated`

Users who follow README or `.cursor` write status values that `/progress` and `/integrate` cannot parse, silently dropping the source from coverage counts.

**Fix.** Standardise on `reading | completed | integrated`. Drop `revisiting` (no skill consumes it; conceptually it's just a return to `reading`).

- `README.md:123` — `(reading / completed)` → `(reading / completed / integrated)`
- `README.md:212` — `reading or complete` → `reading | completed | integrated`
- `.cursor/rules/academic-writing.mdc:9` — `reading | complete | revisiting` → `reading | completed | integrated`

Skill files already match the target — no change.

**Rationale.** The skill implementations are what actually parse the field, so they win. `revisiting` was added in the cursor rule alone and never made it into any skill; removing it costs nothing and reduces vocabulary surface area.

**Acceptance.** Regression test T13 (narrowed per R7 — `! grep -rqE '\brevisiting\b' README.md .cursor/rules/ docs/ .claude/skills/`). Manual spot-check that `complete` only appears as a verb (e.g., "complete reading notes"), never as a status value. **Expected manual-review false positives** that should NOT be flagged: `docs/skills/02-note.md:223` ("mark as complete"), `docs/skills/07-progress.md:113,163` ("mark as complete" / "complete or decide"), `.claude/skills/integrate/SKILL.md:46` ("from `completed` to `integrated`").

### 4.4 Bug #4 — Output path drift (MAJOR)

**Problem.** Two output directory names appear in parallel:
- User-facing docs (`CLAUDE.md:15`, `AGENTS.md:17`, `GEMINI.md:17`, `README.md:158,201`) — `final_output/`
- Skill implementation (`.claude/skills/export/SKILL.md:36`, `docs/skills/08-export.md:63,99,100`) — `export_output/`

The repo physically contains `final_output/` (with `.gitkeep`); running `/export` today creates a second directory `export_output/`, leaving users confused about where their .docx files went.

**Fix.** Standardise on `final_output/`.

- `.claude/skills/export/SKILL.md:36` — `{project_root}/export_output` → `{project_root}/final_output`
- `docs/skills/08-export.md:63` — same
- `docs/skills/08-export.md:99` — table cell `export_output/` → `final_output/`
- `docs/skills/08-export.md:100` — same in zip path

User-facing docs and the existing directory already match — no further changes.

**Rationale.** Smaller blast radius (2 files vs 4); semantic fit ("final" = submission-ready, not just an intermediate export); no orphaned directory for users who already have `final_output/` populated; AGENTS.md / GEMINI.md auto-derive from CLAUDE.md SHARED block via D's `make sync`.

**Acceptance.** Regression test T12 (no `export_output` in `.claude/skills/` or `docs/skills/`). Manual smoke: `/export chapters` writes to `final_output/`.

### 4.5 Bug #5 — PDF export claim (MAJOR)

**Problem.** All four `docs/setup-*.md:44` (or :32 in `setup-openclaw.md`) claim `/export` produces "Word/PDF". The toolkit has no PDF export path — `convert_to_docx.py` produces only `.docx` + `.zip`.

**Fix.** Replace each claim with the truthful capability.

- `docs/setup-claude-code.md:44` — `Export chapters to Word/PDF` → `Export chapters to Word (.docx) + ZIP`
- `docs/setup-codex-cli.md:44` — same
- `docs/setup-gemini-cli.md:44` — same
- `docs/setup-openclaw.md:32` — same

Other PDF mentions in the same files refer to `/read` consuming PDFs as **input** — that capability is real, leave it alone.

**Acceptance.** Regression test T16 (no `Word/PDF` or `to Word and PDF` in `docs/setup-*.md`).

### 4.6 Bug #6 — `compile_pdf.py` reference (MINOR)

**Problem.** `docs/skills/08-export.md:184` references a script `compile_pdf.py` that does not exist in the repo and was never implemented.

**Fix.** Rewrite the row to acknowledge the absence of a built-in PDF path.

> | Expecting PDF output | `/export` produces .docx + ZIP. There is no PDF export path; convert the .docx to PDF in Word or LibreOffice if you need PDF. |

**Acceptance.** Regression test T15 (no `compile_pdf.py` in `docs/` or `README.md`).

### 4.7 Bug #7 — Vocabulary drift (MINOR) — expanded per codex review

**Problem.** Two vocabulary sets compete for the same column (`Connection Type` in notes files):
- `_template_NOTES.md:33`, `/note` SKILL.md, `/integrate` — `supports / challenges / extends` (stance)
- `/map` SKILL.md:28, examples in `docs/skills/04-map.md` — `cite / argue / data / method` (citation purpose)
- `docs/skills/04-map.md:9` mixes both lists
- **`docs/skills/02-note.md:204-211` (added per codex review) explicitly teaches the 6-element merged set as "the standard types"** — this contradicts `_template_NOTES.md:33` and would re-introduce the bug if left in place.

Per `/map` SKILL.md:75, `/map` reads the `Connection Type` column populated by users following the `/note` template. So `/map` example matrices show vocabulary that no user would actually write — making the documentation deceptive about what `/map` will display.

**Fix.** Standardise on stance-only (`supports / challenges / extends`). `/map` and `docs/skills/02-note.md` both adopt `/note` template's vocabulary.

- `.claude/skills/map/SKILL.md:28` — `e.g., cite, argue, data, method` → `e.g., supports, challenges, extends`
- `.claude/skills/map/SKILL.md:44–46` — rebuild example matrix with stance values only
- `docs/skills/04-map.md:9` — `(supports, challenges, extends, cite, data, method)` → `(supports, challenges, extends)`
- `docs/skills/04-map.md:76–81` — rebuild example matrix with stance values
- `docs/skills/02-note.md:204-211` — collapse the 6-element list to the 3-element stance set, with the descriptive prose:
  > Use connection types consistently. The standard types are:
  > - `supports` — source provides evidence for your argument
  > - `challenges` — source contradicts or complicates your argument
  > - `extends` — source adds a new dimension to your argument
- `docs/skills/04-map.md:124,134-135` — Glossary table examples already use stance vocabulary (verified in pre-spec sweep), no change needed.

`/note` template (`_template_NOTES.md:33`), `/note` SKILL.md, `/integrate`, `/audit` already use stance-only — no changes.

**Rationale.** `/note` template is the contract; consumers (`/map`, `/integrate`, `docs/skills/02-note.md` user guide) must speak the producer's vocabulary, not the other way around. No real notes files exist yet (per memory `project_toolkit_roadmap.md`), so zero data migration. Stance is the dimension `/integrate` actually uses; "citation purpose" was never wired into any data flow.

**Acceptance.** Regression test T14 (strengthened per R8 — bans `\b(argue|cite|data|method)\b` in matrix-cell context within `.claude/skills/map/`, `docs/skills/04-map.md`, `docs/skills/02-note.md` Connection Types section).

### 4.8 Bug #8 — Python 3.8 compat (NEW BLOCKER, per codex audit) — per R3

**Problem.** `convert_to_docx.py:205,214,223` use `tuple[int, int]` (PEP 585 generic syntax) without `from __future__ import annotations`. On Python 3.8 (Debian 11, Ubuntu 20.04 default, RHEL 8) the script fails at *import* with `TypeError: 'type' object is not subscriptable` — **before** the friendly dependency-error path can run. `scripts/doctor.sh:83` accepts any `python3` and only verifies `import docx` succeeds, so `make doctor` reports green on a broken `/export` setup.

**Fix.** Add `from __future__ import annotations` as the first non-docstring import in `convert_to_docx.py`.

```python
"""Convert thesis chapters and reading notes from Markdown to Word (.docx).
...
"""
from __future__ import annotations  # NEW: postpone annotation evaluation for Python 3.8

import argparse
import os
...
```

Do not refactor the existing `tuple[int, int]` annotations — `from __future__ import annotations` makes all annotations strings at runtime, so PEP 585 syntax becomes safe on 3.8.

**Rationale.** One-line fix; no behavioral change on 3.9+; unblocks 3.8.

**Acceptance.** Regression test T17 (per §5): `python3.8 -c "import .claude.skills.export.scripts.convert_to_docx"` (or equivalent file-import smoke) succeeds without `TypeError`. If Python 3.8 is not available locally, T17 falls back to `grep -q 'from __future__ import annotations' .claude/skills/export/scripts/convert_to_docx.py` (asserts the safeguard is in place; doesn't actually run 3.8).

### 4.9 Bug #9 — `/map` `allowed-tools` missing `Write` (NEW MAJOR, per codex + substitute audit) — per R4

**Problem.** `.claude/skills/map/SKILL.md:4` declares `allowed-tools: Read, Glob, Grep, Edit`. Line 62 explicitly says: "use Edit (if the file exists) or **Write** (if creating new)" for `literature/mapping_matrix.md`. The repo currently has no `mapping_matrix.md`, so the first time a user invokes `/map save`, Write is denied by the harness and the save fails.

**Fix.** Add `Write` to the `allowed-tools` line.

```yaml
---
allowed-tools: Read, Glob, Grep, Edit, Write
---
```

**Acceptance.** Regression test T18 (per §5): allowed-tools sanity check — `/map` lists `Write`, `/verify` lists `Read`. Manual smoke: on a fresh checkout, `/map` then "save" creates `literature/mapping_matrix.md`.

### 4.10 Bug #10 — `/verify` `allowed-tools` missing `Read` (NEW MAJOR, per substitute audit) — per R5

**Problem.** `.claude/skills/verify/SKILL.md:4` declares `allowed-tools: WebSearch, WebFetch, Edit`. Steps 5 (line 27) and the Annotation section (line 61) instruct the agent to use `Edit` to annotate the relevant notes file. `Edit` requires a previous `Read` on the same file per the harness contract ("You must use your Read tool at least once… before editing"). Without `Read` in the allow-list, annotation always fails.

**Fix.** Add `Read` to the `allowed-tools` line.

```yaml
---
allowed-tools: WebSearch, WebFetch, Read, Edit
---
```

**Acceptance.** Regression test T18 (per §5). Manual smoke: invoke `/verify` on a claim that requires annotating a notes file; confirm Edit succeeds.

### 4.11 OpenClaw setup doc — adjacent fix (per R6)

**Problem.** `docs/setup-openclaw.md:38` Configuration paragraph instructs users to "Edit `AGENTS.md`" to set chapter targets, reading constraints, etc. After D, `AGENTS.md` is generated from `CLAUDE.md` SHARED block by `make sync`. Users who follow this doc edit a generated file; their changes vanish on the next `make sync`.

**Fix.** Rewrite the Configuration section to point at the canonical source.

```markdown
## Configuration

OpenClaw reads `AGENTS.md` as its project instruction file, but **`AGENTS.md` is auto-generated** from `CLAUDE.md` by sub-project D's tooling. To customise:

1. Edit `CLAUDE.md` (the canonical source — the SHARED block is what gets regenerated).
2. Run `make sync` to regenerate `AGENTS.md` (and `GEMINI.md`).
3. Verify with `make doctor`.

Things to set:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters
```

**Acceptance.** Manual review of rendered Markdown; no regression test (this is one paragraph in one file).

## 5. Regression tests

Append the following to `scripts/test-foolproofing.sh` using the existing `pass` / `fail` / `die` helpers from `scripts/lib.sh`. Implementation translates each row into a one-liner; the spec specifies the FORBIDDEN states and the ASSERTIONS, not the regex literals.

| Test | Assertion | Bug | Notes |
|---|---|---|---|
| T11 | No `CLAUDE_SKILL_DIR` in `.claude/skills/` or `docs/skills/` | #1 | grep -F |
| T12 | No `export_output` in `.claude/skills/` or `docs/skills/` | #4 | grep -F |
| T13 | No `\brevisiting\b` anywhere in repo | #3 | Narrowed per R7 — `complete` half dropped, manual review covers it |
| T14 | No deprecated vocab `\b(argue\|cite\|data\|method)\b` in matrix-cell context (lines containing `\|`) within `.claude/skills/map/`, `docs/skills/04-map.md`, `docs/skills/02-note.md` | #7 | Strengthened per R8 — scopes to table cells to skip prose false positives like "data consistency" or "must cite the source" |
| T15 | No `compile_pdf.py` references in `docs/` or `README.md` | #6 | grep -F |
| T16 | No `Word/PDF` or `to Word and PDF` in `docs/setup-*.md` | #5 | grep -E |
| T17 | `from __future__ import annotations` present in `convert_to_docx.py`; if `python3.8` is on PATH, `python3.8 -c "import importlib.util; ..."` smoke succeeds | #8 | Two-tier: cheap grep guard + optional 3.8 smoke |
| T18 | `/map` SKILL.md `allowed-tools` includes `Write`; `/verify` SKILL.md `allowed-tools` includes `Read` | #9, #10 | Two grep -E lines |

T13 implementation note (per R7): we drop the brittle `\bcomplete\b[^d]` half. The expected manual-review false positives that should NOT be flagged are listed in §4.3 acceptance.

T14 implementation note (per R8): the regex must scope to lines containing `|` (matrix-cell delimiter) to skip ordinary English prose. Files outside the named three are not checked because `cite`, `data`, and `method` legitimately appear there as ordinary words.

The pandoc-preflight regression for Bug #2 is **not** a grep test — it requires either a Python unit test or a manual venv setup. This is deferred to sub-project A (CI/tests). For C-emergency, the spec records the manual procedure under §4.2 acceptance. **If A slips, Bug #2 has no automated guard** — the manual procedure should be promoted to A's first test.

## 6. Verification (end-to-end)

1. **Self-test:** `bash scripts/test-foolproofing.sh` reports 15/15 ✓ (7 existing T2–T10 + 8 new T11–T18, with T17 as two-tier and T18 as two grep lines counted as one test).
2. **`/export` works on Claude Code:** running `/export chapters` from the repo root creates `final_output/chapters/*.docx` + a ZIP archive.
3. **Cross-platform smoke:** opening the same repo in Codex CLI (or Gemini) and running `export chapters` does **not** error on `${CLAUDE_SKILL_DIR}`.
4. **Pandoc preflight:** in a clean venv with `pip install pypandoc python-docx markdown` but no `pandoc` binary on PATH, `python .claude/skills/export/scripts/convert_to_docx.py --base-dir . --output-dir final_output --scope chapters` reports "Conversion method: python-docx + markdown (fallback)" rather than crashing.
5. **Python 3.8 import:** if 3.8 is available, `python3.8 -c "import importlib.util, pathlib; importlib.util.spec_from_file_location('m', '.claude/skills/export/scripts/convert_to_docx.py').loader.exec_module(importlib.util.module_from_spec(importlib.util.spec_from_file_location('m', '.claude/skills/export/scripts/convert_to_docx.py')))"` succeeds.
6. **D safeguards still green:** `make doctor` reports 5/5 ✓; `make sync` is a no-op (CLAUDE.md SHARED block unchanged).
7. **`/map` save smoke:** on a fresh checkout, `/map save` creates `literature/mapping_matrix.md` without harness denial.
8. **`/verify` annotate smoke:** `/verify` on a claim that requires annotating a notes file completes without harness denial.
9. **Migration note for orphan `export_output/`:** users who ran the buggy `/export` may have a populated `export_output/` directory; this fix does NOT migrate contents automatically. Mention in the PR description that affected users should `mv export_output/* final_output/` after upgrade. No code action.

## 7. Critical files

| File | Bug | Edit type |
|---|---|---|
| `.claude/skills/export/SKILL.md` | #1, #2-docs, #4 | 3 line edits + 1 prose line + 1 paragraph rewrite |
| `.claude/skills/export/scripts/convert_to_docx.py` | #2, #8 | ~10 line block edit (preflight + try/except) + 1 line `from __future__` |
| `.claude/skills/map/SKILL.md` | #7, #9 | example matrix rebuild + 1 instruction line + 1 frontmatter line |
| `.claude/skills/verify/SKILL.md` | #10 | 1 frontmatter line |
| `docs/skills/08-export.md` | #1, #2-docs, #4, #6 | 4 line edits + 1 row rewrite + 1 table collapse |
| `docs/skills/04-map.md` | #7 | intro line + matrix rebuild |
| `docs/skills/02-note.md` | #7 | 6-line list collapse to 3-line stance set |
| `docs/setup-claude-code.md` | #5 | 1 line |
| `docs/setup-codex-cli.md` | #5 | 1 line |
| `docs/setup-gemini-cli.md` | #5 | 1 line |
| `docs/setup-openclaw.md` | #5, R6 | 1 line + Configuration paragraph rewrite |
| `README.md` | #3 | 2 line edits |
| `.cursor/rules/academic-writing.mdc` | #3 | 1 line |
| `scripts/test-foolproofing.sh` | verification | append T11–T18 (~50 lines) |

14 existing files; ~70–90 lines of total edit volume.

## 8. References

- R2 audit findings (memory): `project_audit_known_bugs.md`
- Toolkit roadmap (memory): `project_toolkit_roadmap.md`
- Sub-project D spec: `docs/superpowers/specs/2026-04-26-foolproofing-design.md`
- Sub-project D plan: `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md`
- D-shipped harness: `scripts/test-foolproofing.sh`
- D-shipped helpers: `scripts/lib.sh`
- v2 reviewer logs (this spec):
  - Codex spec review (gpt-5.4): `/Users/yhryzy/.claude/plugins/data/codex-inline/state/stoic-ritchie-ed61ac-b78a6d5ea0a1b9f2/jobs/task-moh94y2q-yz0hd6.log`
  - Codex project audit (gpt-5.4): `/Users/yhryzy/.claude/plugins/data/codex-inline/state/stoic-ritchie-ed61ac-b78a6d5ea0a1b9f2/jobs/task-moh94y9w-e3cwa7.log`

## 9. Reviewer-feedback integration log

For traceability — what was integrated and what was deferred from the triple-reviewer pass on 2026-04-27.

**Integrated (added to spec):**
- R1: Bug #2 stronger probe (`pypandoc.get_pandoc_version()` + try/except fallback) — codex spec MAJOR
- R2: Bug #2 adjacent docs unification (SKILL.md:30 + 08-export.md docs) — codex spec MAJOR
- R3: Bug #8 Python 3.8 compat — codex audit NEW-BLOCKER + substitute audit BLOCKER
- R4: Bug #9 `/map` Write — codex audit NEW-MAJOR + substitute audit MAJOR
- R5: Bug #10 `/verify` Read — substitute audit MAJOR (unique to substitute; verified independently)
- R6: OpenClaw setup doc — codex audit NEW-MAJOR
- R7: T13 narrowing — codex spec MINOR + superpowers IMPROVE 1
- R8: T14 strengthening — codex spec MAJOR + substitute spec M2
- Bug #7 expansion to `docs/skills/02-note.md:204-211` — codex spec MAJOR + substitute spec M1
- §6 migration note for orphan `export_output/` — codex spec MINOR + substitute spec m3
- §5 Bug #2 deferred-test acknowledgment — superpowers IMPROVE 2

**Deferred to subsequent sub-projects:**
- Export symlink / path-traversal validation — codex audit NEW-MAJOR → C-rest (security pass; out of "B" scope per simplest-design rule)
- D-script cwd contract — codex audit NEW-MAJOR → C-rest
- `sync-config.sh` `.new` race — codex audit NEW-MINOR → C-rest
- `docs/setup-cursor.md:51` AGENTS.md edit issue — codex audit NEW-MAJOR → C-rest
- README VS Code Copilot row — substitute audit MAJOR → C-rest doc-pass

**Accepted as observation (no spec change):**
- superpowers IMPROVE 3: §4.1 prose location — addressed by spec text "Insert immediately above step 1"
- superpowers IMPROVE 4: scope-creep risk — observation; mitigated by §2 explicit out-of-scope list
- substitute spec m1 (cite `_template_NOTES.md:33` as already-correct) — addressed in §4.7 closing paragraph
- substitute spec m4 (`.gitattributes` covers `.mdc`) — verified, no action
- substitute spec m5 (zip UTF-8 already correct) — verified, no action
- substitute spec m6 (§4.6 wording) — verified fine
