# A: CI & Tests for Skills

**Status**: draft v2 (post triple-reviewer pass; awaiting user sign-off)
**Date**: 2026-04-27
**Sub-project**: A (toolkit roadmap)
**Predecessors**: D — foolproofing & multi-platform robustness (shipped `981d28f`, 2026-04-27); C-emergency — R2 audit bug fixes (shipped `9092294`, 2026-04-27)
**Successors**: C-rest (skill polish, citation format) → B (new skills)

---

## 1. Context

D shipped a regression test harness (`scripts/test-foolproofing.sh`, 7 automated acceptance tests T2/T3/T4/T5/T8/T9/T10; T1/T6/T7 documented as manual-only because they require separate clones or PATH mutation that conflicts with parallel runs). C-emergency extended it with 8 more tests (T11–T18, covering status enum drift, vocab drift, allowed-tools sanity, Python 3.8 import safety, stale doc references). The harness now runs **15 automated tests on every invocation** and prints `all 15 tests passed` on `master @ 9092294`.

The harness has no automated trigger. There is no `tests/` directory, no `.github/` directory, and no `make test` target. Every fix shipped so far has relied on the developer remembering to run `bash scripts/test-foolproofing.sh` before merging — an unreliable safety net.

Sub-project A closes this gap with the **smallest possible** change: wire the existing harness into GitHub Actions and add a `make test` entry point. No new tests are added in this sub-project; the existing 15 already cover every concrete bug surfaced to date by either audit cycle (R1 foolproofing or R2 contract drift). Test-suite expansion (skill contract metatests, multi-platform path resolution stress tests, end-to-end export smoke) is explicitly deferred to subsequent sub-projects where the actual coverage gap will be evidence-driven, not speculative.

This sub-project precedes C-rest (skill polish) and B (new skills) so that both downstream sub-projects ship against a **visible regression net** — CI surfaces failures publicly on every PR/master push. **Enforcement** of the net (preventing red-CI merges) is a separate, repo-settings-level user action: enabling GitHub branch protection's "required status checks" on `master` after this spec lands. This spec delivers the net itself; §5 calls out the user handoff item.

## 2. Scope

**In scope:**

- Rename `scripts/test-foolproofing.sh` → `scripts/test.sh` (the file's coverage long ago outgrew the "foolproofing" label).
- Add `.github/workflows/test.yml` — single ubuntu-latest job, triggers on `push` to `master` and on `pull_request` against `master`.
- Add `make test` target to `Makefile`.
- Update **forward-looking references** to the old script name (README/CLAUDE.md/etc.; on `master @ 9092294` there are zero such references). **Historical references in shipped predecessor specs and plans are preserved**; rename preambles redirect future readers to the new name without rewriting history (see §4.1).
- Document the user handoff item: enabling branch protection on `master` to convert the visible CI net into an enforcing one (see §5).

**Out of scope (deferred with rationale):**

- Adding any new test cases. The 15 existing automated tests cover the audit-surfaced bug surface; expansion without evidence is YAGNI.
- Skill contract metatests (frontmatter required-fields, `allowed-tools` syntax) — defer to B's first new skill, where the contract enforcement has a concrete consumer.
- pytest / bats / any test framework beyond bash + grep — violates the user's standing simplification preference; the existing harness style works and is uniform.
- macOS / Windows CI runners — the harness exercises file-IO and grep patterns that are platform-agnostic on POSIX systems; macOS-specific divergence has not been observed. If user reports a macOS-only regression later, a matrix entry can be added then.
- pip cache configuration — `requirements.txt` would be premature; pip install runs once per job, ~5 s, no caching needed.
- Branch protection rules — these are GitHub repo settings, not files in this repo. §5 includes the user handoff; configuring protections is out of this spec's file changes.
- `make test` chaining `make doctor` internally — orthogonality preserved (Q5); the CI workflow runs them as separate steps.
- Self-hosted runners, custom Docker images, ARC — premature.
- T1/T6/T7 automation — the C-emergency / D harnesses left these manual-only by design (parallel-test conflicts, PATH mutation). Re-engineering them is C-rest territory.

## 3. Design Decisions

Settled during brainstorming on 2026-04-27 (Q1–Q5).

| # | Question | Decision | Why |
|---|---|---|---|
| Q1 | Scope shape | A — wire existing 15 automated tests into CI; no test expansion | R2 audit found bugs because tests *did not run automatically*, not because tests were missing. Highest-ROI fix is the trigger, not more cases. Expansion deferred to B/C-rest where evidence will dictate scope. |
| Q2 | CI trigger model | `pull_request` against `master` + `push` to `master` | User's workflow mixes worktree-merge-then-push with PR flow; PR-only would miss the non-PR merges. Restricting `pull_request` to base `master` avoids noisy CI on ephemeral inter-worktree PRs. Cancel-in-progress concurrency keeps cost low. |
| Q3 | CI environment | ubuntu-latest + `actions/setup-python@v5` with `python-version: '3.8'` + `pip install python-docx markdown` | Single OS keeps config minimal. Explicit Python 3.8 + at least one conversion backend makes T17's smoke-import path actually exercise — without a backend, `convert_to_docx.py:50-58` exits at module-load with `sys.exit(...)` and T17 fails. `python-docx + markdown` is the cheapest backend pair (no system pandoc binary needed); the `pypandoc + pandoc` path is exercised by users in production, not in CI. C-emergency Bug #8 (`from __future__ import annotations` for 3.8 syntax safety) is what T17 protects against; that protection is the reason for choosing 3.8 specifically. macOS divergence has zero evidence; defer matrix until evidence appears. |
| Q4 | Script name | Rename `test-foolproofing.sh` → `test.sh` | Current name is misleading (T11–T18 are not foolproofing). `test.sh` matches `make test` and the unix convention of a single test entry point. C-rest-style polish but cheap to bundle here. (Self-acknowledged scope-bend; included because locality-coherent with adding `make test`.) |
| Q5 | `make test` shape | Thin delegate (`make test → bash scripts/test.sh`) | Orthogonality with `make doctor`; CI workflow composes them explicitly. Avoids hidden chains; single failure step in the GHA UI is unambiguous. |

## 4. Architecture & Files

### 4.1 File-level changes

A `grep -rn test-foolproofing .` on `master @ 9092294` (excluding this A spec, which intentionally documents the rename) finds references only in:

| Location | Hits | Status after A |
|---|---|---|
| `scripts/test-foolproofing.sh` (self) | 1 (header comment) | renamed → `scripts/test.sh`; comment edited |
| `docs/superpowers/specs/2026-04-26-foolproofing-design.md` | 3 | unchanged inline; rename preamble added |
| `docs/superpowers/specs/2026-04-27-c-emergency-design.md` | 5 | unchanged inline; rename preamble added |
| `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md` | 12 | unchanged inline; rename preamble added |
| `docs/superpowers/plans/2026-04-27-c-emergency-implementation.md` | 53 | unchanged inline; rename preamble added |

No matches in README, CLAUDE.md, AGENTS.md, GEMINI.md, .cursor/rules/, docs/setup-\*.md, docs/skills/, or Makefile (verified by `grep -rl`).

**Rename strategy — uniform across specs and plans**: shipped predecessor docs (D and C-emergency, both specs *and* implementation plans) contain historical statements like "Append the following to `scripts/test-foolproofing.sh`" or "git add scripts/test-foolproofing.sh && git commit ...". These describe actions taken on the file *while it was named `test-foolproofing.sh`*. Rewriting the names would produce a dishonest record of what was done. Instead, every shipped historical doc receives a one-line preamble redirecting future readers to the new name, while bodies stay byte-identical to their as-shipped state. Forward-looking docs (the renamed script's header comment, the new Makefile, the new workflow) use the new name directly.

| Action | Path | Detail |
|---|---|---|
| `git mv` | `scripts/test-foolproofing.sh` → `scripts/test.sh` | Preserves blame history. |
| edit (header only) | `scripts/test.sh` | Replace header comment line `# scripts/test-foolproofing.sh — runs spec §6 acceptance tests T2-T10.` with `# scripts/test.sh — runs the regression test suite (15 automated tests: T2/T3/T4/T5/T8/T9/T10 + T11-T18) for academic-writing-toolkit.` |
| edit | `Makefile` | (1) **Replace** the existing `.PHONY: help setup init sync doctor repair` line with `.PHONY: help setup init sync doctor repair test` (do NOT append a second `.PHONY` line). (2) Add `test:` target body (§4.2). |
| new | `.github/workflows/test.yml` | See §4.3. |
| insert preamble | `docs/superpowers/specs/2026-04-26-foolproofing-design.md` | Insert preamble (§4.1.1) immediately after the front-matter block / first-heading. |
| insert preamble | `docs/superpowers/specs/2026-04-27-c-emergency-design.md` | Same preamble. |
| insert preamble | `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md` | Same preamble. |
| insert preamble | `docs/superpowers/plans/2026-04-27-c-emergency-implementation.md` | Same preamble. |

#### 4.1.1 Rename preamble (verbatim)

Insert this exact block (Markdown blockquote) after the document's title heading and any front-matter, before the first body section:

```markdown
> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.
```

#### 4.1.2 Post-edit grep contract

The implementing plan must confirm all four checks (verbatim commands recorded in the implementation log):

- `grep -rn test-foolproofing scripts/ .github/ Makefile README.md CLAUDE.md AGENTS.md GEMINI.md .cursor/ docs/setup-*.md docs/skills/` → exits with no matches (i.e. `grep` returns 1).
- `grep -rn test-foolproofing docs/superpowers/specs/ docs/superpowers/plans/` → returns the historical hits (8 spec + 65 plan = 73 total on `master @ 9092294`; the count must not decrease, and only the count of `Rename note` lines may increase — exactly +4, one per historical doc).
- For each of the four historical docs: `head -25 <file> | grep -q "Rename note (2026-04-27, sub-project A)"` returns 0.
- This A spec's own `test-foolproofing` mentions are intentional (the spec documents the rename) and are excluded from the zero-hit contract by the explicit path enumeration.

### 4.2 `Makefile` increment

```make
.PHONY: help setup init sync doctor repair test

test:  ## Run the full regression test suite (15 automated tests)
	@bash scripts/test.sh
```

The `.PHONY` line **replaces** the existing one (do not append a second `.PHONY` declaration). `make help` will auto-list `test` because of the `## …` doc-comment convention already used by other targets.

### 4.3 `.github/workflows/test.yml`

```yaml
name: test

on:
  push:
    branches: [master]
  pull_request:
    branches: [master]

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
      - name: Verify python3.8 binary on PATH
        run: python3.8 --version
      - name: Install conversion backend (T17 smoke-import dependency)
        run: pip install python-docx markdown
      - run: make doctor
      - run: make test
```

Design notes:

- **`pull_request: branches: [master]`** — restricts CI to PRs targeting `master`. Avoids triggering on inter-worktree feature-to-feature PRs the user does not promote (matches Q2's stated reasoning).
- **`permissions: contents: read`** — explicitly minimal token scope; the workflow only reads the repo, no writes needed. (Verification of the permission is **static** in the YAML, not a GHA runtime signal — see §6.)
- **`concurrency` with `cancel-in-progress: true`** — rapid pushes to the same ref cancel earlier in-flight runs; saves CI minutes without hiding failures (the latest ref is what matters).
- **`make doctor` then `make test` as separate steps** — unambiguous failure attribution in the GHA UI; matches Q5's orthogonality decision.
- **`actions/setup-python@v5` with `'3.8'`** — quoted string `'3.8'` (an unquoted `3.8` would parse as YAML float, which `setup-python` may interpret as `python-version: 3.80` or otherwise mis-resolve depending on the action version). The `setup-python@v5` action installs CPython 3.8 with both `python` and `python3.8` symlinks on `ubuntu-latest`; the explicit `python3.8 --version` step fails fast if that binary name is missing (T17 internally guards on `command -v python3.8`, so a missing symlink would silently no-op the smoke tier).
- **`pip install python-docx markdown`** — required for T17's smoke import. `convert_to_docx.py:50-58` calls `sys.exit(...)` at module-load time if neither `pypandoc` (with `pandoc` binary) nor `python-docx + markdown` is importable. The CI runner installs only the latter pair; the former path is exercised by users in production. C-emergency Bug #8 is the regression T17 protects against (Python 3.8 SyntaxError on annotations); installing a backend is what makes the smoke tier actually exercise the file.
- **`actions/checkout@v4` and `setup-python@v5` are tag-pinned, not SHA-pinned** — single-user thesis-tooling repo; supply-chain attack surface is low and the user explicitly trades action SHA pinning for readability. If this assumption changes (e.g. the toolkit gains contributors, or starts handling secrets), revisit.

### 4.4 What runs in CI on each trigger

| Trigger | What runs |
|---|---|
| `pull_request` against `master` (opened, ready_for_review) | full job (4 setup steps + 2 shell steps; see §6) |
| `pull_request` against `master` (synchronized — new commits pushed to PR head) | same; previous run cancelled by concurrency rule |
| `pull_request` against any base **other than `master`** | nothing |
| `push` to `master` | full job |
| `push` to any non-master branch | nothing (branch's PR will trigger if/when opened against `master`) |
| Tag push, manual `workflow_dispatch` | nothing (out of scope; trivial to add later if needed) |

## 5. Implementation Outline

The detailed step-by-step plan (commit boundaries, exact diff per file, regression-catch rehearsal) is the deliverable of the next phase (`writing-plans` skill). The implementation plan must determine where commits split.

High-level changes (order is not a commit-boundary specification):

- Rename script (`git mv`).
- Edit script header comment.
- Edit `Makefile` (`.PHONY` replacement + `test` target).
- Add `.github/workflows/test.yml`.
- Insert rename preamble into the four shipped historical docs (D spec, C-emergency spec, D plan, C-emergency plan).
- Run §6 verifications locally — must all pass before pushing.
- Push to a feature branch; open PR to `master`; confirm `test` workflow appears as a check.
- Run the §6 regression-catch rehearsal on the PR (deliberately corrupt a file, confirm CI fails, revert).
- Merge to `master`; confirm CI runs again on master push.

### 5.1 User handoff items (post-merge, repo-settings level)

These are **not** code changes and **not** part of the spec's file changes; they convert the visible regression net into an enforcing one. The implementing plan must surface them to the user at completion:

1. **Enable required status check on `master`** — GitHub repo settings → Branches → branch protection rule for `master` → Require status checks → select `test`. Without this, a developer can still merge a red PR.
2. **(Optional) Enable "Require branches to be up-to-date before merging"** — guards against the `make test` passing on stale base.
3. **(Optional) Confirm GitHub repo visibility (public vs private)** — affects GHA billing minute allotment; the §7 risk row treats this as unverified-by-this-spec.

## 6. Verification

### 6.1 Local checks (run before push)

| Check | Command | Expected |
|---|---|---|
| Rename succeeded | `test -f scripts/test.sh && ! test -f scripts/test-foolproofing.sh` | exits 0 |
| Harness still runs | `bash scripts/test.sh` | prints `all 15 tests passed`; exit 0 |
| `make test` is the same | `make test` | identical pass output, exit 0 |
| `make help` lists target | `make help \| grep -E '^\s*test\b'` | one line, doc-comment visible |
| Forward-looking grep is clean | `grep -rn test-foolproofing scripts/ .github/ Makefile README.md CLAUDE.md AGENTS.md GEMINI.md .cursor/ docs/setup-*.md docs/skills/` | exits 1 (no matches) |
| Historical refs preserved (body unchanged) | `grep -rn test-foolproofing docs/superpowers/specs/ docs/superpowers/plans/ \| grep -v 'Rename note (2026-04-27, sub-project A)'` | exactly 73 lines (8 spec + 65 plan, byte-identical to `master @ 9092294`) |
| Preamble inserted exactly once per historical doc | `grep -rln 'Rename note (2026-04-27, sub-project A)' docs/superpowers/specs/ docs/superpowers/plans/ \| wc -l` | exactly 4 |
| All four historical docs have preamble | for each of D-spec, C-emergency-spec, D-plan, C-emergency-plan: `head -25 <file> \| grep -q 'Rename note (2026-04-27, sub-project A)'` | all 4 exit 0 |
| YAML permission scope is minimal | `grep -E '^\s+contents:\s+read' .github/workflows/test.yml` | matches once |

### 6.2 CI pipeline checks (after PR open)

| Check | Expected |
|---|---|
| `test` workflow appears as a status check on the PR | yes |
| GHA UI shows the expected step list | 6 steps: `Set up job` (implicit), `Run actions/checkout@v4`, `Run actions/setup-python@v5`, `Verify python3.8 binary on PATH`, `Install conversion backend`, `Run make doctor`, `Run make test`, `Complete job` (implicit). Specifically the two custom shell steps `Run make doctor` and `Run make test` are both green. |
| `python3.8 --version` step | prints `Python 3.8.x`; exit 0 |
| `pip install python-docx markdown` step | prints `Successfully installed ...`; exit 0 |
| `make test` step prints | `all 15 tests passed`; exit 0 (T17 smoke import path actually runs because both `python3.8` and a backend are present) |
| Concurrency cancellation works | push a second commit to the PR within ~30 s; the first run gets `Cancelled` status, second runs to completion |

### 6.3 Regression-catch rehearsal (proves the wiring does its job, not just that it exists)

The spec's safety claim is "CI catches regressions before merge". The rehearsal verifies this for two distinct test categories. Run on a throwaway branch (do **not** merge):

**Rehearsal A — vocab-drift category (T14)**:

1. On the PR's branch, edit `.claude/skills/note/SKILL.md` to add the deprecated token `argue` somewhere in the body (T14 forbids it).
2. Push.
3. Wait for CI; assert the `test` workflow status is **failed** (red X), not "passed with warnings" or "neutral". The failed step is `Run make test`. Reading the step's log shows the `[✗] T14 no deprecated vocab in /map+/note` line and `1 of 15 tests failed`. The job's overall exit is non-zero.
4. Revert the change; push; assert CI returns to green within one cycle.

**Rehearsal B — symlink category (T2)**:

1. On the PR's branch, break a skill's symlink: `rm .agents/skills/note && mkdir .agents/skills/note && cp .claude/skills/note/SKILL.md .agents/skills/note/SKILL.md`.
2. Push.
3. Assert the `test` workflow fails. The failed step is `Run make doctor` (T2's drift is also caught by `doctor`); if `doctor` is green for some reason, the failure surfaces in `Run make test`. Either failure proves CI catches symlink drift.
4. Revert via `bash scripts/repair.sh`; push; assert CI returns to green.

**Why two rehearsals**: a single rehearsal would only prove the wiring catches *one* test category. The two together prove (a) `make test`'s non-zero exit propagates to GHA step failure, (b) the failure is attributable in the GHA UI (specific test name visible in the step log), and (c) the wiring is not accidentally specific to one subset of the suite (e.g. a YAML typo that only runs grep-tier tests).

## 7. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| `actions/checkout@v4` does not preserve symlinks → T2 false-positive | Low | v4 documented to preserve symlinks on Linux/macOS runners. Ubuntu-only avoids the Windows symlink trap. |
| Python 3.8 sunset in GHA `setup-python` (3.8 EOL was 2024-10) | Medium | If `setup-python@v5` drops 3.8, bump to 3.10/3.11; T17 falls back to grep-only on whichever Python is available (the smoke-import is a belt; grep is the brace). The CI workflow is the only place affected; one-line edit. |
| `python3.8` symlink missing on `setup-python@v5` runners (silent T17 no-op) | Low | Mitigated explicitly: the `Verify python3.8 binary on PATH` step (`python3.8 --version`) fails the job if the symlink is missing, before T17 silently passes. |
| `pip install python-docx markdown` adds CI dependency surface | Low | Both packages are pure-Python and ABI-compatible across Python versions; no native build. If either becomes a supply-chain concern (compromise, name-typo squat), the install line is a one-line edit. T17's smoke remains useful even if a backend changes hands. |
| Rename breaks an out-of-tree caller | Low | The script is repo-internal; no documentation outside the repo references it. Foolproofing setup docs (`docs/setup-*.md`) reference `make` targets, not the script. |
| GHA repo billing / minutes | Low | GitHub repo visibility was not verified by this spec (a remote URL alone does not establish public/private status). User should confirm the repo is public if they want unlimited GHA minutes; if private, the user's plan dictates billing. Workflow is a single ubuntu-latest job, ~1 min, ~30 s of which is `make doctor` + `make test` — well within typical free-tier allotments either way. |
| `make doctor` failing in CI in a way it does not fail locally | Low | Doctor's checks are environment-agnostic (file IO + grep). Symlink check matters and is preserved. If a CI-only failure surfaces, doctor is the diagnosis. |
| Concurrency cancellation hides a flaky test | Low | Concurrency cancels by ref, not test result. A failing test on the latest commit is what matters; if a flake appears, fix the test, do not disable concurrency. |
| User later wants `workflow_dispatch` for manual reruns | Low | Trivial to add later (`on:` accepts a list); not needed for the audit-bug regression purpose. |
| Tag-pinned (vs SHA-pinned) actions allow upstream owner takeover | Low | Single-user thesis-tooling repo; no secrets in the workflow; `permissions: contents: read` further limits blast radius. If contributors join or secrets enter the workflow, switch to SHA pins as a follow-up sub-project (out of A's scope). |

## 8. Reviewer Pass (executed 2026-04-27)

Per the standing memory rule (`Use codex + superpowers reviewers in parallel for design work`), this spec went through three parallel reviewers. Findings drove the v1 → v2 changes.

**Runtime note**: the local Codex CLI 1.0.4 with a ChatGPT-account credential cannot reach `gpt-5.5` (default; needs newer CLI), `gpt-4o`, or `gpt-5.3-codex-spark` (credential disallowed). The first codex-rescue dispatch fell through silently (audit returned a runtime error; spec review fell back to direct file reading). The reviewers were re-dispatched with explicit `--model gpt-5.4`, which resolved the runtime issue. The corresponding memory file (`feedback_review_combo.md`) was updated to require explicit `gpt-5.4` until the toolchain situation changes.

Reviewers (in the order they returned):

- **superpowers:code-reviewer** (process review) — clean process, two MAJORs in §6 (verification did not prove the wiring catches regressions; non-zero exit propagation not asserted), several MINORs/NITs.
- **codex spec review** (`gpt-5.4`) — flagged 1 BLOCKER (self-referential grep contract — the A spec mentions `test-foolproofing` but its own grep contract said specs/ must be zero-hits) and 3 MAJORs around the rename strategy's asymmetry between specs and plans.
- **codex project audit** (`gpt-5.4`) — confirmed several spec claims (15-test count, predecessor SHAs, no .github/, T17 binary-name dependency, pypandoc try/except guard) but caught 1 MAJOR factual error: spec said "only Python dep is pypandoc" — `convert_to_docx.py:42-58` also imports `markdown` and `python-docx`, and `:50-58` calls `sys.exit(...)` at module-load if **neither** backend is available. This collapsed the previous "no pip install" claim and motivated the new Q3 + §4.3 `pip install` step. Audit also corrected line/count mismatches in §4.1.

Triage outcomes encoded into v2:

- BLOCKER #1 (self-reference) — fixed by §4.1.2 explicit-path enumeration.
- MAJOR #1 (asymmetric rename strategy) — fixed by uniform preamble approach in §4.1.
- MAJOR (T17 silent no-op without backend) — fixed by §4.3 `pip install` + `python3.8 --version` precheck.
- MAJOR (§6 wiring not really verified) — fixed by §6.3 two-rehearsal recipe.
- MAJOR (no exit-code propagation assertion) — fixed by §6.3 explicit "failed (red X)" expectations.
- MINORs (counts, line numbers, branches filter, .PHONY replace, billing-risk evidence, plan-preamble brittleness) — all addressed inline.
- NITs (calibration, scope-bend ack, format consistency, action SHA pinning) — accepted as-is or added §7 row noting the tradeoff.

User sign-off required before transitioning to `superpowers:writing-plans`.

## 9. References

- Predecessor specs: [docs/superpowers/specs/2026-04-26-foolproofing-design.md](../specs/2026-04-26-foolproofing-design.md), [docs/superpowers/specs/2026-04-27-c-emergency-design.md](../specs/2026-04-27-c-emergency-design.md)
- Predecessor plans: [docs/superpowers/plans/2026-04-26-foolproofing-implementation.md](../plans/2026-04-26-foolproofing-implementation.md), [docs/superpowers/plans/2026-04-27-c-emergency-implementation.md](../plans/2026-04-27-c-emergency-implementation.md)
- Test harness (current): `scripts/test-foolproofing.sh` (will become `scripts/test.sh`)
- GitHub Actions docs: <https://docs.github.com/en/actions> (do not deep-link; spec stays version-agnostic)
- Roadmap memory: `D → C-emergency → A → C-rest → B`
