# A — CI & Tests for Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the existing 15-test bash regression harness (`scripts/test-foolproofing.sh`) into GitHub Actions so D + C-emergency fixes cannot silently regress; rename the script to `scripts/test.sh`; add a `make test` entry point; add rename preambles to the four shipped historical docs (D + C-emergency specs + plans); rehearse two CI failure paths to prove the wiring catches regressions before merge.

**Architecture:** Verification-driven. Each task ends with a concrete check (grep contract, `make test` exit code, GHA UI status). No new test cases are added in this sub-project — the existing 15 are the regression net; A turns it on. Commit boundaries follow file-cohesion: rename gets its own commit (clean blame), forward-looking name updates batch together (header + Makefile), the workflow file is its own commit, and the four-file preamble insertion batches together (one logical change). Rehearsals run on the feature branch with revert-after-observation; they do not produce merge-bound commits.

**Tech Stack:** Bash (existing harness, unchanged), GNU make (one new target), GitHub Actions YAML (one new workflow), Markdown edits (preambles into 4 shipped docs). No new test framework, no pytest, no bats. Per spec §3 Q5 simplification preference.

**Spec:** [docs/superpowers/specs/2026-04-27-a-ci-tests-design.md](../specs/2026-04-27-a-ci-tests-design.md) — refer for design rationale.

---

## File Structure

| File | Touched by tasks | Responsibility after A |
|---|---|---|
| `scripts/test-foolproofing.sh` → `scripts/test.sh` | T1 (rename), T2 (header) | Same harness body; new path; updated header comment |
| `Makefile` | T2 (modify) | Adds `test` target; existing `.PHONY` line replaced (not appended) |
| `.github/workflows/test.yml` | T3 (new) | Single ubuntu-latest job; PR-against-master + push-to-master triggers; setup-python 3.8 + pip backend + verify steps + `make doctor` + `make test` |
| `docs/superpowers/specs/2026-04-26-foolproofing-design.md` | T4 (insert preamble) | Body byte-identical to as-shipped; rename preamble after first `---` |
| `docs/superpowers/specs/2026-04-27-c-emergency-design.md` | T4 (insert preamble) | Same |
| `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md` | T4 (insert preamble) | Same |
| `docs/superpowers/plans/2026-04-27-c-emergency-implementation.md` | T4 (insert preamble) | Same |

Total file deltas in A: 1 rename + 6 edits + 1 new = 8 files, ~50 lines net change.

---

## Task ordering rationale

1. **Rename first, alone (T1)**: `git mv` followed by other-file edits in one commit would split blame; isolating preserves history. No tests run between T1 and T2 because the file's path change alone doesn't break anything callers don't reference (Makefile + CI don't yet exist).
2. **Forward-looking name updates next, batched (T2)**: header comment in the renamed script + Makefile both adopt the new name. Logically one change ("update consumers to the new path"); blame is uniform.
3. **CI workflow added before docs (T3)**: gets `make test` exercised end-to-end before any other change muddies the signal.
4. **Preambles to historical docs (T4)**: independent of CI; could go anywhere after T1, but kept after T3 so a later bisect on "did CI regression appear?" lands cleanly between code and doc commits.
5. **Local verification gate (T5)**: spec §6.1 contract before pushing.
6. **Push + observe CI (T6)**: first remote signal.
7. **Rehearsal A and B (T7, T8)**: spec §6.3 — prove the wiring catches regressions in two distinct categories (vocab via T14, symlink via T2). Each rehearsal makes a corruption commit, pushes, observes red, reverts, pushes, observes green. Final branch state before merge is clean.
8. **Merge to master (T9)**: triggers push-to-master CI run; final green check.
9. **Branch protection handoff (T10)**: user-side GitHub settings step; visible net → enforcing net.

---

## Task 1: Rename `test-foolproofing.sh` → `test.sh`

**Files:**
- Rename: `scripts/test-foolproofing.sh` → `scripts/test.sh`

- [ ] **Step 1: Confirm starting state**

```bash
git status
git rev-parse --short HEAD
git log --oneline master..HEAD
```

Expected: working tree clean; HEAD on `claude/optimistic-antonelli-5faff8` at `9dce5d1` (or later) — two A-spec commits (`8963b18 docs(A): add spec...` and `9dce5d1 docs(A): patch spec v1 -> v2 ...`) ahead of master. If the branch differs, sync first.

- [ ] **Step 2: Confirm 15 tests pass on the old name (baseline)**

```bash
bash scripts/test-foolproofing.sh
```

Expected last line: `[✓] all 15 tests passed.` Exit code 0. Save this output mentally — every later step reproduces it on the new path.

- [ ] **Step 3: Rename via git mv**

```bash
git mv scripts/test-foolproofing.sh scripts/test.sh
```

- [ ] **Step 4: Confirm the rename ran on the same content**

```bash
git status
bash scripts/test.sh
```

Expected: `git status` shows `renamed: scripts/test-foolproofing.sh -> scripts/test.sh`. `bash scripts/test.sh` again prints `all 15 tests passed.`

- [ ] **Step 5: Commit the rename alone**

```bash
git commit -m "$(cat <<'EOF'
refactor(A): rename scripts/test-foolproofing.sh to scripts/test.sh

The harness covers far more than foolproofing now (T11–T18 added in
C-emergency cover skill contracts, vocab drift, Python compat, etc).
Rename matches `make test` and the unix convention of a single test
entry point. This commit is the rename only — header comment, Makefile,
CI wiring, and historical-doc preambles follow in subsequent commits
to keep blame clean.

Spec: docs/superpowers/specs/2026-04-27-a-ci-tests-design.md §4.1

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

Confirm: `git log --oneline -1` shows the new rename commit; `git show --stat HEAD` shows one rename, no body diff.

---

## Task 2: Update script header comment + add Makefile `test` target

**Files:**
- Modify: `scripts/test.sh` (line 2 only — header comment)
- Modify: `Makefile` (replace `.PHONY` line + add `test:` target at end)

- [ ] **Step 1: Edit the script header comment**

Replace line 2 of `scripts/test.sh`:

```
# scripts/test-foolproofing.sh — runs spec §6 acceptance tests T2-T10.
```

with:

```
# scripts/test.sh — runs the regression test suite (15 automated tests: T2/T3/T4/T5/T8/T9/T10 + T11-T18) for academic-writing-toolkit.
```

(Lines 3 and onward unchanged.)

- [ ] **Step 2: Verify the comment edit**

```bash
head -3 scripts/test.sh
```

Expected: line 1 still `#!/usr/bin/env bash`, line 2 the new comment, line 3 still `# Self-contained; saves and restores any state it mutates.`

- [ ] **Step 3: Run the harness from the new path**

```bash
bash scripts/test.sh
```

Expected: `all 15 tests passed.` (Header comment is comments only — no behavioural change.)

- [ ] **Step 4: Edit `Makefile` — replace `.PHONY` line**

Find line 5:
```
.PHONY: help setup init sync doctor repair
```

Replace with:
```
.PHONY: help setup init sync doctor repair test
```

(Single edit; the existing line is replaced, NOT appended to. A second `.PHONY` declaration is valid Make but redundant — see spec §4.2.)

- [ ] **Step 5: Append `test:` target to `Makefile`**

Add these three lines at the end of the file (after the `repair:` target's body, line 36):

```make

test:  ## Run the full regression test suite (15 automated tests)
	@bash scripts/test.sh
```

(The blank line above `test:` separates targets per existing Makefile style.)

- [ ] **Step 6: Verify `make help` lists the new target**

```bash
make help
```

Expected: among the existing targets, a new line: `  test       Run the full regression test suite (15 automated tests)`. The cyan-coloured prefix is rendered by `awk` in the existing `help:` body.

- [ ] **Step 7: Verify `make test` runs the harness**

```bash
make test
```

Expected: same `all 15 tests passed.` output as `bash scripts/test.sh`. Exit 0.

- [ ] **Step 8: Commit**

```bash
git add scripts/test.sh Makefile
git commit -m "$(cat <<'EOF'
feat(A): update script header + add make test target

Second commit of sub-project A — forward-looking consumer updates
that adopt the new scripts/test.sh path:
- scripts/test.sh: line-2 header comment now reflects 15-test scope
- Makefile: .PHONY declaration extended with `test`; new `test:`
  target delegates to `bash scripts/test.sh` (thin shell, orthogonal
  to make doctor — see spec §3 Q5).

Spec: docs/superpowers/specs/2026-04-27-a-ci-tests-design.md §4.1, §4.2

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Add GitHub Actions workflow

**Files:**
- Create: `.github/workflows/test.yml`

- [ ] **Step 1: Create the `.github/workflows/` directory**

```bash
mkdir -p .github/workflows
```

(`.github/` does not exist on `master @ 9092294`; this is the first GHA workflow in the repo.)

- [ ] **Step 2: Write `.github/workflows/test.yml`**

Create the file with this exact content:

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

- [ ] **Step 3: Sanity-check the YAML locally**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"
```

Expected: no output, exit 0. (If `yaml` module is not available, `pip install pyyaml` once or skip — GHA's parser is the authoritative check, but a local parse catches typos before pushing.)

- [ ] **Step 4: Run `make doctor && make test` to mirror the CI sequence locally**

```bash
make doctor && make test
```

Expected: both commands exit 0; final line `all 15 tests passed.`

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "$(cat <<'EOF'
feat(A): add GitHub Actions workflow .github/workflows/test.yml

Single ubuntu-latest job. Triggers on PRs against master and on
push to master. Steps: checkout, setup-python 3.8, verify
python3.8 binary, pip install backend (python-docx + markdown so
T17 smoke-import really exercises convert_to_docx.py), make doctor,
make test.

Concurrency: cancel-in-progress on the same ref. Permissions:
contents: read (token scope minimised). Action versions tag-pinned
(@v4, @v5) — single-user thesis-tooling repo, no secrets in
workflow; SHA-pin tradeoff documented in spec §7.

Spec: docs/superpowers/specs/2026-04-27-a-ci-tests-design.md §4.3, §4.4

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Insert rename preambles into 4 historical docs

**Files:**
- Modify: `docs/superpowers/specs/2026-04-26-foolproofing-design.md` — insert after line 9
- Modify: `docs/superpowers/specs/2026-04-27-c-emergency-design.md` — insert after line 9
- Modify: `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md` — insert after line 13
- Modify: `docs/superpowers/plans/2026-04-27-c-emergency-implementation.md` — insert after line 13

**Insertion location**: in each file, immediately after the **first** `---` horizontal-rule line. The line numbers above were verified on `master @ 9092294`; if the line moved due to prior edits, find the first `---` on a line by itself and insert the preamble after it.

**Verbatim preamble block** (exactly the same in all four files):

```markdown

> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.

```

(Note the blank line above and below the blockquote — these go in the file, surrounding the preamble.)

- [ ] **Step 1: Insert preamble into D spec**

In `docs/superpowers/specs/2026-04-26-foolproofing-design.md`, find the first `---` line (line 9). Add the verbatim preamble block immediately after it. The result around lines 9–12 should look like:

```
---

> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.

## §1 Scope & Goals
```

- [ ] **Step 2: Insert preamble into C-emergency spec**

In `docs/superpowers/specs/2026-04-27-c-emergency-design.md`, same pattern. After line 9 (`---`), insert the verbatim preamble block. Result around lines 9–12:

```
---

> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.

## 1. Context
```

- [ ] **Step 3: Insert preamble into D plan**

In `docs/superpowers/plans/2026-04-26-foolproofing-implementation.md`, find the first `---` (line 13). Insert the verbatim preamble block after it. Result around lines 13–16:

```
---

> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.

## File Inventory
```

- [ ] **Step 4: Insert preamble into C-emergency plan**

In `docs/superpowers/plans/2026-04-27-c-emergency-implementation.md`, same pattern. After line 13 (`---`), insert the verbatim preamble block. Result around lines 13–16:

```
---

> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.

## File Structure
```

- [ ] **Step 5: Verify all four preambles inserted**

```bash
grep -rln 'Rename note (2026-04-27, sub-project A)' docs/superpowers/specs/ docs/superpowers/plans/ | wc -l
```

Expected: `4` (one occurrence per file). If the count is anything else, investigate before continuing.

- [ ] **Step 6: Verify body content unchanged in all four**

```bash
grep -rn test-foolproofing docs/superpowers/specs/ docs/superpowers/plans/ | grep -v 'Rename note (2026-04-27, sub-project A)' | wc -l
```

Expected: `73` (= 8 in specs + 65 in plans, byte-identical to `master @ 9092294`). Per spec §6.1 row "Historical refs preserved (body unchanged)".

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/specs/2026-04-26-foolproofing-design.md \
        docs/superpowers/specs/2026-04-27-c-emergency-design.md \
        docs/superpowers/plans/2026-04-26-foolproofing-implementation.md \
        docs/superpowers/plans/2026-04-27-c-emergency-implementation.md
git commit -m "$(cat <<'EOF'
docs(A): add rename preamble to 4 shipped historical docs

D + C-emergency specs and plans contain historical references to
scripts/test-foolproofing.sh (8 spec hits + 65 plan hits = 73
total). Editing them inline would falsify the historical record
of what those sub-projects actually did. Instead, each receives a
one-line preamble immediately after the first --- separator,
redirecting future readers to scripts/test.sh while preserving
the body byte-identical to as-shipped.

Verified: exactly 4 preamble lines added; 73 historical body
references unchanged.

Spec: docs/superpowers/specs/2026-04-27-a-ci-tests-design.md §4.1, §4.1.1, §4.1.2

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Local verification gate (spec §6.1)

No commits in this task — this is a contract check before pushing.

- [ ] **Step 1: Rename succeeded check**

```bash
test -f scripts/test.sh && ! test -f scripts/test-foolproofing.sh && echo OK
```

Expected: `OK`. Exit 0.

- [ ] **Step 2: Harness still runs**

```bash
bash scripts/test.sh
```

Expected: `all 15 tests passed.`

- [ ] **Step 3: `make test` is the same**

```bash
make test
```

Expected: identical pass output to step 2; exit 0.

- [ ] **Step 4: `make help` lists `test`**

```bash
make help | sed 's/\x1b\[[0-9;]*m//g' | grep -E '^\s*test\b'
```

Expected: one matching line containing `test` and the doc-comment description. The `sed` strips ANSI color escape codes — the existing `make help` body uses `\033[36m` cyan codes around target names, which would otherwise prevent the `^\s*test\b` regex from matching.

- [ ] **Step 5: Forward-looking grep is clean**

```bash
grep -rn test-foolproofing scripts/ .github/ Makefile README.md CLAUDE.md AGENTS.md GEMINI.md .cursor/ docs/setup-*.md docs/skills/ 2>/dev/null
echo "exit=$?"
```

Expected: no output; `exit=1` (grep's "no matches found" exit). If any line is printed, find and fix the leftover reference before continuing.

- [ ] **Step 6: Historical refs preserved (body byte-identical) — exclude A's own spec+plan**

```bash
grep -rn test-foolproofing docs/superpowers/specs/ docs/superpowers/plans/ \
  --exclude='*2026-04-27-a-ci-tests-*' \
  | grep -v 'Rename note (2026-04-27, sub-project A)' \
  | wc -l
```

Expected: `73`. The `--exclude='*2026-04-27-a-ci-tests-*'` filters out A's own spec and plan: those files intentionally contain `test-foolproofing` references (they document the rename), and they are NOT what this contract is policing. The body-integrity contract is about the four shipped historical docs (D + C-emergency × spec + plan), which together contributed 73 references on `master @ 9092294`. Sanity baseline: `for f in docs/superpowers/specs/2026-04-2{6,7}-{foolproofing,c-emergency}-{design,*-implementation}.md docs/superpowers/plans/2026-04-2{6,7}-*.md; do git show master:"$f" | grep -c test-foolproofing 2>/dev/null; done | paste -sd + | bc` should sum to 73.

- [ ] **Step 7: YAML permission scope is minimal**

```bash
grep -E '^\s+contents:\s+read' .github/workflows/test.yml
```

Expected: matches once (the line `      contents: read` inside the `permissions:` block).

- [ ] **Step 8: Each historical doc's preamble is in the first 25 lines (the durable check)**

```bash
for f in \
  docs/superpowers/specs/2026-04-26-foolproofing-design.md \
  docs/superpowers/specs/2026-04-27-c-emergency-design.md \
  docs/superpowers/plans/2026-04-26-foolproofing-implementation.md \
  docs/superpowers/plans/2026-04-27-c-emergency-implementation.md; do
  if head -25 "$f" | grep -q 'Rename note (2026-04-27, sub-project A)'; then
    echo "OK $f"
  else
    echo "FAIL $f"
  fi
done
```

Expected: 4 lines, each starting with `OK`.

If any check fails, fix the underlying problem and re-run all of T5 before continuing.

---

## Task 6: Push to origin and observe CI green

**Files:** none.

- [ ] **Step 1: Push the branch**

```bash
git push -u origin claude/optimistic-antonelli-5faff8
```

Expected: GitHub creates the remote branch and prints the PR-creation URL.

- [ ] **Step 2: Open a PR against master**

Either click the URL from step 1, or run:

```bash
gh pr create --base master --head claude/optimistic-antonelli-5faff8 \
  --title "A: CI & tests for skills (wire existing harness)" \
  --body "$(cat <<'EOF'
Implements sub-project A per docs/superpowers/specs/2026-04-27-a-ci-tests-design.md.

- Renames scripts/test-foolproofing.sh -> scripts/test.sh
- Adds make test target
- Adds .github/workflows/test.yml (PR + master push triggers)
- Inserts rename preamble in 4 shipped historical docs

No new tests are added in this sub-project; existing 15 are wired in.

After merge, the user should enable required-status-check on master
in repo settings (see plan T10).
EOF
)"
```

- [ ] **Step 3: Observe the `test` workflow run**

Either via the GitHub web UI or:

```bash
gh pr checks
```

Wait for the `test` job to complete (≤2 min for ubuntu-latest, including pip install). Expected: `test ✓`. The PR's mergeability indicator turns green.

- [ ] **Step 4: Inspect the run summary in the GHA UI**

Open the workflow run; verify the step list:

1. `Set up job` (implicit)
2. `Run actions/checkout@v4`
3. `Run actions/setup-python@v5`
4. `Verify python3.8 binary on PATH` — log shows `Python 3.8.x`
5. `Install conversion backend (T17 smoke-import dependency)` — log shows `Successfully installed markdown-... python-docx-...`
6. `Run make doctor` — log shows the doctor passes
7. `Run make test` — log ends with `all 15 tests passed.`
8. `Complete job` (implicit)

All steps should be green. If any step fails, do not proceed to T7 — diagnose first (likely candidates: missing `python3.8` symlink → bug in `actions/setup-python@v5`'s '3.8' resolution; pip install fails → check action version).

---

## Task 7: Rehearsal A — vocab-drift category (T14)

Spec §6.3 Rehearsal A. Proves CI catches a vocab-drift regression and propagates the failure to the GHA UI.

**Files (rehearsal only — reverted in step 5):**
- Modify: `.claude/skills/note/SKILL.md` (add a forbidden token, then revert)

- [ ] **Step 1: Confirm baseline T14 is green**

```bash
make test 2>&1 | grep T14
```

Expected: `[✓] T14 no deprecated vocab in /map+/note`. If it's already failing, T14 is broken before A landed — investigate.

- [ ] **Step 2: Inject a forbidden vocab token**

Append the token `argue` somewhere in the body of `.claude/skills/note/SKILL.md`. The simplest deterministic injection:

```bash
printf "\n\n<!-- T14 rehearsal: should argue with this -->\n" >> .claude/skills/note/SKILL.md
```

(The HTML comment is a real T14 violation because T14 greps for the literal token `argue` regardless of context. Safer than editing prose.)

- [ ] **Step 3: Confirm T14 fails locally before pushing**

```bash
bash scripts/test.sh 2>&1 | grep -E 'T14|tests'
```

Expected: a `[✗] T14 no deprecated vocab in /map+/note` line and a final summary like `1 of 15 tests failed`. Exit code 1.

- [ ] **Step 4: Push the deliberately-broken commit**

```bash
git add .claude/skills/note/SKILL.md
git commit -m "rehearsal(A): T14 vocab-drift regression check (will revert)"
git push
```

- [ ] **Step 5: Observe CI fails red**

```bash
gh pr checks --watch
```

Or refresh the PR page. Expected: `test ✗` (red X). The `Run make test` step in the workflow run shows the `[✗] T14 no deprecated vocab in /map+/note` line. The job's overall status is **failed**, not "neutral" or "passed-with-warnings".

Confirm exactly: open the failed step's log; the last lines should include something like `1 of 15 tests failed` (the harness's failure summary), and the GHA step's exit code is non-zero. This proves spec §6.3 Rehearsal A's claim "CI catches T14 + non-zero exit propagates".

- [ ] **Step 6: Revert and re-push**

```bash
git revert --no-edit HEAD
git push
```

(Using `git revert` rather than `git reset --hard + force push` keeps PR history honest — it shows the rehearsal explicitly.)

- [ ] **Step 7: Observe CI returns to green**

```bash
gh pr checks --watch
```

Expected: `test ✓`. The PR is again mergeable. Rehearsal A complete.

---

## Task 8: Rehearsal B — symlink category (T2)

Spec §6.3 Rehearsal B. Proves CI catches a symlink-drift regression — a different test category from T14, ruling out test-specific wiring fluke.

**Files (rehearsal only — reverted in step 5):**
- Modify: `.agents/skills/<name>` (replace symlink with directory + copied SKILL.md, then revert via `repair.sh`)

- [ ] **Step 1: Pick a skill name and confirm baseline**

```bash
SKILL=$(find .claude/skills -maxdepth 1 -mindepth 1 -type d | head -1 | xargs basename)
echo "Using skill: $SKILL"
ls -la ".agents/skills/$SKILL"
```

Expected: `$SKILL` is a non-empty name (e.g. `audit`, `export`, `note`); `ls -la` shows a symlink (`l...`) pointing at `../../.claude/skills/$SKILL`.

- [ ] **Step 2: Break the symlink (simulate corruption)**

```bash
rm -rf ".agents/skills/$SKILL"
mkdir -p ".agents/skills/$SKILL"
cp ".claude/skills/$SKILL/SKILL.md" ".agents/skills/$SKILL/SKILL.md"
```

This recreates the corruption pattern that T2 detects: a directory containing a copy instead of a symlink to the canonical source.

- [ ] **Step 3: Confirm T2 fails locally**

```bash
bash scripts/test.sh 2>&1 | grep -E 'T2 |tests'
```

Expected: `[✗] T2  symlink corruption + repair`; final summary indicates a failure. Exit 1.

- [ ] **Step 4: Push the broken state**

```bash
git add ".agents/skills/$SKILL"
git commit -m "rehearsal(A): T2 symlink-drift regression check (will revert)"
git push
```

(`git add` of a former symlink replaces the symlink with the directory + file in the index — this is the corruption committed.)

- [ ] **Step 5: Observe CI fails red**

```bash
gh pr checks --watch
```

Expected: `test ✗`. Open the failing step:

- If `Run make doctor` fails first, that's also valid — T2's drift is also caught by the doctor's symlink check; the spec §6.3 Rehearsal B says "Either failure proves CI catches symlink drift".
- If `Run make doctor` somehow passes, `Run make test` fails on T2.

Either way, the workflow is red and the failure is attributable to symlink drift.

- [ ] **Step 6: Revert via `repair.sh` + commit the fix**

```bash
bash scripts/repair.sh           # restores the symlink locally
git add ".agents/skills/$SKILL"  # stage the restored symlink
git commit -m "rehearsal(A): revert T2 symlink rehearsal (back to symlink)"
git push
```

`scripts/repair.sh` restores the symlink (D's repair pathway, exercised under T2's own design). We commit the fix as a fresh commit rather than `git revert`-ing the corruption commit because the corruption was a tree replacement (symlink → directory + file); the simpler path is "fix the working tree, commit the fix" — `git revert` would have to undo the tree replacement step-by-step.

- [ ] **Step 7: Confirm local + remote green**

```bash
make doctor && make test
gh pr checks --watch
```

Expected: local — both commands exit 0; remote — `test ✓` again. Rehearsal B complete.

- [ ] **Step 8: Rehearsals proven; final branch state is clean**

```bash
git log --oneline master..HEAD | head -10
```

Expected commit graph (newest first):

```
<sha> rehearsal(A): revert T2 symlink rehearsal (back to symlink)
<sha> rehearsal(A): T2 symlink-drift regression check (will revert)
<sha> Revert "rehearsal(A): T14 vocab-drift regression check (will revert)"
<sha> rehearsal(A): T14 vocab-drift regression check (will revert)
<sha> docs(A): add rename preamble to 4 shipped historical docs
<sha> feat(A): add GitHub Actions workflow .github/workflows/test.yml
<sha> feat(A): update script header + add make test target
<sha> refactor(A): rename scripts/test-foolproofing.sh to scripts/test.sh
9dce5d1 docs(A): patch spec v1 -> v2 from triple-reviewer pass
8963b18 docs(A): add spec for CI & tests sub-project
```

The four rehearsal commits document the regression-catch proof. They stay in the branch history; they do not break master because each rehearsal cycle ends in a green state.

---

## Task 9: Merge to master + verify push-trigger CI

**Files:** none (merge commit + post-merge verification).

- [ ] **Step 1: Final pre-merge local verification**

```bash
make doctor && make test
git log --oneline -1
git status
```

Expected: both make commands exit 0; HEAD is the green-state commit from T8 step 6; working tree clean.

- [ ] **Step 2: Merge the PR**

Either via the GitHub UI ("Merge pull request" → "Create a merge commit") or:

```bash
gh pr merge --merge --subject "Merge sub-project A: CI & tests for skills"
```

Use a merge commit (not squash, not rebase) — keeps the rehearsal commits in master's history as proof of the §6.3 verification, matching D and C-emergency's merge style.

- [ ] **Step 3: Pull master locally and verify**

```bash
git checkout master
git pull --ff-only origin master
git log --oneline -5
```

Expected: master tip is now the merge commit; A's 4 production commits + 4 rehearsal commits + the spec commits are all in history.

- [ ] **Step 4: Watch the master-push CI run**

The merge commit triggers the `push: branches: [master]` workflow event.

```bash
gh run list --workflow=test.yml --branch=master --limit=1
gh run watch
```

Expected: a fresh `test` run on `master`, status becomes `completed ✓` within ~2 min.

- [ ] **Step 5: Switch back to the worktree branch (optional)**

If you intend to delete the worktree, do that from the main checkout:

```bash
cd /Users/yhryzy/dev/academic-writing-toolkit
git worktree remove .claude/worktrees/optimistic-antonelli-5faff8
git branch -d claude/optimistic-antonelli-5faff8
```

If you want to keep the worktree for follow-up work, stay in it and switch to master:

```bash
cd /Users/yhryzy/dev/academic-writing-toolkit/.claude/worktrees/optimistic-antonelli-5faff8
git checkout master
git pull --ff-only
```

---

## Task 10: User handoff — branch protection (manual GitHub settings)

This task is **not a code change**. It is the user-side step that converts A's visible regression net into an enforcing one (spec §1, §5.1).

- [ ] **Step 1: Open repo settings → Branches**

Navigate to `https://github.com/yha9806/academic-writing-toolkit/settings/branches` (or Repo → Settings → Branches in the GitHub UI).

- [ ] **Step 2: Add a branch protection rule for `master`**

Click "Add classic branch protection rule" (or the equivalent ruleset path if the repo uses Rulesets). Branch name pattern: `master`.

- [ ] **Step 3: Enable required status checks**

Under "Protect matching branches":
- ☑ Require a pull request before merging
- ☑ Require status checks to pass before merging
  - ☑ Require branches to be up to date before merging (recommended; guards against `make test` passing on a stale base)
  - In the search box, find and select **`test`** (the workflow added in T3)

Leave other options at their defaults unless the user has a reason to change them.

- [ ] **Step 4: Save the rule**

Click "Create" / "Save changes".

- [ ] **Step 5: Verify the gate works**

Open a throwaway PR with a deliberate breakage (e.g. add `argue` to `.claude/skills/note/SKILL.md` again). The PR should now show:

- `test` check is required
- Until `test` passes, the "Merge pull request" button is disabled (greyed out)

Close the throwaway PR without merging. The enforcing net is live.

- [ ] **Step 6 (optional): Confirm GHA billing visibility**

Per spec §7 risk row "GHA repo billing / minutes": confirm the repo's visibility (public vs private) at `https://github.com/yha9806/academic-writing-toolkit/settings`. Public repos get free GHA minutes; private repos consume the user's plan allotment. Workflow uses ~30 s of compute per run — well within typical free-tier allotments either way, but worth being aware of.

- [ ] **Step 7: Roadmap memory update**

Update `~/.claude/projects/-Users-yhryzy-dev-academic-writing-toolkit/memory/project_toolkit_roadmap.md`: mark sub-project A as **SHIPPED** with the date and merge commit SHA. The next sub-project per the roadmap is **C-rest** (skill polish, citation format).

---

## Verification Summary

Every claim from spec §6 is covered:

| Spec §6 row | Plan task |
|---|---|
| §6.1 — Rename succeeded | T5 step 1 |
| §6.1 — Harness still runs | T5 step 2 |
| §6.1 — `make test` is the same | T5 step 3 |
| §6.1 — `make help` lists target | T5 step 4 |
| §6.1 — Forward-looking grep clean | T5 step 5 |
| §6.1 — Historical refs preserved | T5 step 6 |
| §6.1 — All four preambles inserted | T5 step 7 |
| §6.1 — YAML permission scope minimal | T5 step 8 |
| §6.2 — `test` workflow appears as PR check | T6 step 3 |
| §6.2 — GHA UI step list matches | T6 step 4 |
| §6.2 — `python3.8 --version` step succeeds | T6 step 4 |
| §6.2 — pip install step succeeds | T6 step 4 |
| §6.2 — `make test` step prints all 15 passed | T6 step 4 |
| §6.2 — Concurrency cancellation works | (implicit — exercised by T7 step 4 if a second push happens within 30 s; not explicitly tested) |
| §6.3 — Rehearsal A vocab/T14 | T7 (full) |
| §6.3 — Rehearsal B symlink/T2 | T8 (full) |
| §6.3 — Non-zero exit propagates to GHA failure | T7 step 5 + T8 step 5 |
| §5.1 — User handoff: branch protection | T10 (full) |

---

## Commit Boundary Summary

A produces 4 production commits + 4 rehearsal commits + 1 merge commit = **9 commits** on top of the 2 spec commits already on the branch. After merge, master gains all 11 (linear-history merge commit included). The 4 rehearsal commits are kept in history (not squashed) because they document the §6.3 verification.

| # | Commit subject | Task |
|---|---|---|
| 1 | `refactor(A): rename scripts/test-foolproofing.sh to scripts/test.sh` | T1 |
| 2 | `feat(A): update script header + add make test target` | T2 |
| 3 | `feat(A): add GitHub Actions workflow .github/workflows/test.yml` | T3 |
| 4 | `docs(A): add rename preamble to 4 shipped historical docs` | T4 |
| 5 | `rehearsal(A): T14 vocab-drift regression check (will revert)` | T7 |
| 6 | `Revert "rehearsal(A): T14 vocab-drift regression check (will revert)"` | T7 |
| 7 | `rehearsal(A): T2 symlink-drift regression check (will revert)` | T8 |
| 8 | `rehearsal(A): revert T2 symlink rehearsal (back to symlink)` | T8 |
| 9 | `Merge sub-project A: CI & tests for skills` | T9 |
