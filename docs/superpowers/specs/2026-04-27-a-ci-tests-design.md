# A: CI & Tests for Skills

**Status**: draft v1 (awaiting triple-reviewer pass + user sign-off)
**Date**: 2026-04-27
**Sub-project**: A (toolkit roadmap)
**Predecessors**: D — foolproofing & multi-platform robustness (shipped `981d28f`, 2026-04-27); C-emergency — R2 audit bug fixes (shipped `9092294`, 2026-04-27)
**Successors**: C-rest (skill polish, citation format) → B (new skills)

---

## 1. Context

D shipped a regression test harness (`scripts/test-foolproofing.sh`, 7 acceptance tests T2–T10). C-emergency extended it to 18 tests (T1–T18, covering status enum drift, vocab drift, allowed-tools sanity, Python 3.8 import safety, stale doc references). All 18 pass locally on `master @ 9092294`.

The harness has no automated trigger. There is no `tests/` directory, no `.github/` directory, and no `make test` target. Every fix shipped so far has relied on the developer remembering to run `bash scripts/test-foolproofing.sh` before merging — an unreliable safety net.

Sub-project A closes this gap with the **smallest possible** change: wire the existing harness into GitHub Actions and add a `make test` entry point. No new tests are added in this sub-project; the existing 18 already cover every concrete bug surfaced to date by either audit cycle (R1 foolproofing or R2 contract drift). Test-suite expansion (skill contract metatests, multi-platform path resolution stress tests, end-to-end export smoke) is explicitly deferred to subsequent sub-projects where the actual coverage gap will be evidence-driven, not speculative.

This sub-project precedes C-rest (skill polish) and B (new skills) so that both downstream sub-projects ship against an active regression net rather than re-running the same manual harness.

## 2. Scope

**In scope:**

- Rename `scripts/test-foolproofing.sh` → `scripts/test.sh` (the file's coverage long ago outgrew the "foolproofing" label).
- Add `.github/workflows/test.yml` — single ubuntu-latest job, triggers on `push` to `master` and on every `pull_request`.
- Add `make test` target to `Makefile`.
- Update all in-repo references to the old script name (specs, plans, README, CLAUDE.md if applicable).

**Out of scope (deferred with rationale):**

- Adding any new test cases. The 18 existing tests cover the audit-surfaced bug surface; expansion without evidence is YAGNI.
- Skill contract metatests (frontmatter required-fields, `allowed-tools` syntax) — defer to B's first new skill, where the contract enforcement has a concrete consumer.
- pytest / bats / any test framework beyond bash + grep — violates the user's standing simplification preference; the existing harness style works and is uniform.
- macOS / Windows CI runners — the harness exercises file-IO and grep patterns that are platform-agnostic on POSIX systems; macOS-specific divergence has not been observed. If user reports a macOS-only regression later, a matrix entry can be added then.
- `pip install` step in CI — the only Python dependency is `pypandoc` and it is optional (C-emergency Bug #8 made `convert_to_docx.py` import-safe without it). T17 verifies this contract.
- pip cache configuration — N/A without a `requirements.txt`.
- Branch protection rules — these are GitHub repo settings, not files in this repo. Recommended for the user to enable manually after CI lands; out of this spec.
- `make test` chaining `make doctor` internally — orthogonality preserved (Q5); the CI workflow runs them as separate steps.
- Self-hosted runners, custom Docker images, ARC — premature.

## 3. Design Decisions

Settled during brainstorming on 2026-04-27 (Q1–Q5).

| # | Question | Decision | Why |
|---|---|---|---|
| Q1 | Scope shape | A — wire existing 18 tests into CI; no test expansion | R2 audit found bugs because tests *did not run automatically*, not because tests were missing. Highest-ROI fix is the trigger, not more cases. Expansion deferred to B/C-rest where evidence will dictate scope. |
| Q2 | CI trigger model | `pull_request` (any base) + `push` to `master` | User's workflow mixes worktree-merge-then-push with PR flow; PR-only would miss the non-PR merges. Cancel-in-progress concurrency keeps cost low. |
| Q3 | CI environment | ubuntu-latest + `actions/setup-python@v5` with `python-version: '3.8'` | Single OS keeps config minimal. Explicit Python 3.8 makes T17's smoke-import path actually exercise instead of silently no-op-ing. macOS divergence has zero evidence; defer matrix until evidence appears. |
| Q4 | Script name | Rename `test-foolproofing.sh` → `test.sh` | Current name is misleading (T11–T18 are not foolproofing). `test.sh` matches `make test` and the unix convention of a single test entry point. C-rest-style polish but cheap to bundle here. |
| Q5 | `make test` shape | Thin delegate (`make test → bash scripts/test.sh`) | Orthogonality with `make doctor`; CI workflow composes them explicitly. Avoids hidden chains; single failure step in the GHA UI is unambiguous. |

## 4. Architecture & Files

### 4.1 File-level changes

A `grep -rn test-foolproofing .` on `master @ 9092294` confirms references exist only in:
- the script itself (1 file),
- the two **forward-looking spec docs** (D + C-emergency) — 9 hits across 2 files,
- the two **historical implementation plans** — ~40 hits across 2 files.

No matches in README, CLAUDE.md, AGENTS.md, GEMINI.md, .cursor/rules/, docs/setup-\*.md, docs/skills/, or Makefile. This shapes the rename strategy: edit specs (authoritative, patched-as-system-changes), leave plans alone (historical action records).

| Action | Path | Detail |
|---|---|---|
| `git mv` | `scripts/test-foolproofing.sh` → `scripts/test.sh` | Preserves blame history. |
| edit | `scripts/test.sh` | Update header comment line `# scripts/test-foolproofing.sh — runs spec §6 acceptance tests T2-T10.` to `# scripts/test.sh — runs the regression test suite (T1–T18) for academic-writing-toolkit.` |
| edit | `Makefile` | (1) Add `test` to `.PHONY`. (2) Add `test:` target. |
| new | `.github/workflows/test.yml` | See §4.3 below for full content. |
| edit | `docs/superpowers/specs/2026-04-26-foolproofing-design.md` | Replace `test-foolproofing.sh` with `test.sh` (3 hits: lines 62, 397, 429). |
| edit | `docs/superpowers/specs/2026-04-27-c-emergency-design.md` | Replace `test-foolproofing.sh` with `test.sh` (6 hits: lines 52, 293, 314, 341, 351, …). |
| optional postscript | `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md` | Add a one-line preamble at the top: `> Note: scripts/test-foolproofing.sh was renamed to scripts/test.sh in sub-project A (2026-04-27). References below predate that rename.` |
| optional postscript | `docs/superpowers/plans/2026-04-27-c-emergency-implementation.md` | Same preamble. |

**Plans are not edited inline** — they are step-by-step records of `git add`/`git commit` commands and grep-output references that operated on the file *while it was still named `test-foolproofing.sh`*. Rewriting those records would make them dishonest. The one-line preamble redirects future readers to the current name without falsifying the action history.

After all edits the implementing plan must confirm:
- `grep -rn test-foolproofing scripts/ .github/ Makefile docs/superpowers/specs/ README.md CLAUDE.md AGENTS.md GEMINI.md .cursor/ docs/setup-*.md docs/skills/` reports zero hits.
- `grep -rn test-foolproofing docs/superpowers/plans/` still has the historical hits (intentionally), and each plan file's first non-frontmatter line is the rename preamble.

### 4.2 `Makefile` increment

```make
.PHONY: help setup init sync doctor repair test

test:  ## Run the full regression test suite (T1-T18)
	@bash scripts/test.sh
```

`make help` will auto-list `test` because of the `## …` doc-comment convention already used by other targets.

### 4.3 `.github/workflows/test.yml`

```yaml
name: test

on:
  push:
    branches: [master]
  pull_request:

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.8'
      - run: make doctor
      - run: make test
```

Design notes:

- **`permissions: contents: read`** — explicitly minimal token scope; the workflow only reads the repo, no writes needed.
- **`concurrency` with `cancel-in-progress: true`** — rapid pushes to the same ref cancel earlier in-flight runs; saves CI minutes without hiding failures (the latest ref is what matters).
- **`make doctor` then `make test` as separate steps** — unambiguous failure attribution in the GHA UI; matches Q5's orthogonality decision.
- **`actions/setup-python@v5` with `'3.8'`** — explicit string '3.8' (not `3.8` int, which YAML would coerce to float 3.8 and break setup-python's parsing). T17's `command -v python3.8` check finds the binary and the smoke import runs.
- **No `pip install`** — every test path either greps files or imports `convert_to_docx.py` (which is import-safe per C-emergency Bug #8).

### 4.4 What runs in CI on each trigger

| Trigger | What runs |
|---|---|
| `pull_request` opened against any base | full job (checkout → setup-python → doctor → test) |
| `pull_request` synchronized (new commits pushed) | same; previous run cancelled by concurrency rule |
| `push` to `master` | full job |
| `push` to non-master branch | nothing (branch's PR will trigger when opened) |
| Tag push, manual `workflow_dispatch` | nothing (out of scope) |

## 5. Implementation Outline

The detailed step-by-step plan is the deliverable of the next phase (`writing-plans` skill). High-level sequence:

1. Rename script (`git mv`); commit alone for clean blame.
2. Update header comment in renamed script.
3. Add `Makefile` `test` target and update `.PHONY`.
4. Add `.github/workflows/test.yml`.
5. Update specs (D + C-emergency) inline; add rename preamble to plans; verify §4.1 grep contract (zero hits outside `docs/superpowers/plans/`).
6. Verify `make doctor && make test` passes locally.
7. Push to a feature branch; confirm GHA `test` check appears and passes.
8. Merge to master.
9. Confirm CI runs on master push.

## 6. Verification

| Check | Expected |
|---|---|
| `bash scripts/test.sh` (after rename) | 18/18 pass, same as before |
| `make test` | Equivalent to running the bash script directly |
| `make help` | Lists `test` target with the doc-comment description |
| `grep -rn test-foolproofing scripts/ .github/ Makefile docs/superpowers/specs/ README.md CLAUDE.md AGENTS.md GEMINI.md .cursor/ docs/setup-*.md docs/skills/` | Zero hits |
| `grep -rn test-foolproofing docs/superpowers/plans/` | Historical hits remain (intentional); each plan's first content line is the rename preamble |
| Push feature branch + open PR | GHA `test` workflow appears as a check, runs, passes |
| Deliberately corrupt a file watched by T13 (e.g. introduce `revisiting` token) | CI `test` step fails with the T13 message |
| Push to master directly | CI runs again on master push trigger |
| Inspect run summary | Two visible steps: "Run make doctor" and "Run make test" |
| GHA token usage | `permissions:` block honored; no warnings about excess scope |

## 7. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `actions/checkout@v4` does not preserve symlinks → T2 false-positive | Low | v4 documented to preserve symlinks on Linux/macOS runners. Ubuntu-only avoids the Windows symlink trap. |
| Python 3.8 sunset in GHA `setup-python` | Medium (3.8 EOL was 2024-10) | If `setup-python@v5` drops 3.8, bump to 3.10/3.11 and let T17 fall back to grep-only. T17's smoke-import is a belt; the brace (grep) still catches drift. |
| Rename breaks an out-of-tree caller | Low | The script is repo-internal; no documentation outside the repo references it. Foolproofing setup docs (`docs/setup-*.md`) reference `make` targets, not the script. |
| GHA repo billing / minutes for the user's account | Low | Public repo → free GHA minutes; private repo would need account check, but this repo is public per `git remote get-url origin`. |
| `make doctor` failing in CI in a way it does not fail locally | Low | Doctor's checks are environment-agnostic (file IO + grep). Symlink check matters and is preserved. If a CI-only failure surfaces, doctor is the diagnosis. |
| Concurrency cancellation hides a flaky test | Low | Concurrency cancels by ref, not test result. A failing test on the latest commit is what matters; if a flake appears, fix the test, do not disable concurrency. |
| User later wants `workflow_dispatch` for manual reruns | Low | Trivial to add later (`on:` accepts a list); not needed for the audit-bug regression purpose. |

## 8. Reviewer Pass

Per the standing memory rule (`Use codex + superpowers reviewers in parallel for design work`), this spec runs through:

- **codex spec review** (gpt-5.4) — checks the spec against the user's request and surfaces internal contradictions or missing detail.
- **codex project audit** (gpt-5.4) — independent audit of the spec against the current repo state, surfaces drift between what the spec says and what's actually in the tree.
- **superpowers:requesting-code-review** (process review) — checks for premature scope, missing verification, and skill-discipline issues.

Findings will be triaged inline (accept / reject with rationale / defer-to-future-sub-project) before the spec moves to user sign-off.

## 9. References

- Predecessor specs: [docs/superpowers/specs/2026-04-26-foolproofing-design.md](../specs/2026-04-26-foolproofing-design.md), [docs/superpowers/specs/2026-04-27-c-emergency-design.md](../specs/2026-04-27-c-emergency-design.md)
- Predecessor plans: [docs/superpowers/plans/2026-04-26-foolproofing-implementation.md](../plans/2026-04-26-foolproofing-implementation.md), [docs/superpowers/plans/2026-04-27-c-emergency-implementation.md](../plans/2026-04-27-c-emergency-implementation.md)
- Test harness (current): `scripts/test-foolproofing.sh` (will become `scripts/test.sh`)
- GitHub Actions docs: <https://docs.github.com/en/actions> (do not deep-link; spec stays version-agnostic)
- Roadmap memory: `D → C-emergency → A → C-rest → B`
