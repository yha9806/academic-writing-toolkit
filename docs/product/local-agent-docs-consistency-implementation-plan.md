# Local Agent Documentation Consistency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align local-agent setup documentation with the current skill set and add an automated drift guard.

**Architecture:** Treat `docs/skills/README.md` as the canonical public local skill index, then align README and runtime setup docs around that inventory. Add a lightweight shell test in `scripts/test.sh` so stale setup wording and missing governance skills fail the normal regression suite.

**Tech Stack:** Markdown docs, Bash test harness in `scripts/test.sh`, existing `make test`, `make plugin-check`, and public-content audit scripts.

---

### Task 1: Add Documentation Drift Guard Test

**Files:**
- Modify: `scripts/test.sh`

- [ ] **Step 1: Add failing test function**

Insert this function after `test_T58()` in `scripts/test.sh`:

```bash
test_T59() {
    local setup_docs=(
        "$REPO_ROOT/docs/setup-claude-code.md"
        "$REPO_ROOT/docs/setup-codex-cli.md"
        "$REPO_ROOT/docs/setup-gemini-cli.md"
        "$REPO_ROOT/docs/setup-openclaw.md"
    )

    ! grep -R -q "11 public academic writing skills" "${setup_docs[@]}" || return 1

    local doc
    for doc in "${setup_docs[@]}"; do
        grep -q "evidence-review" "$doc" || return 1
        grep -q "release-governance" "$doc" || return 1
    done

    grep -q "Local agent skills" "$REPO_ROOT/README.md" || return 1
    grep -q "ChatGPT App MCP server" "$REPO_ROOT/README.md" || return 1
    grep -q "pasted-text" "$REPO_ROOT/README.md" || return 1
}
```

- [ ] **Step 2: Register the test**

Add this run line after T58:

```bash
run_test "T59 local-agent docs avoid skill drift" test_T59
```

Update the header comment from `T54-T58 release governance` to `T54-T58 release governance + T59 docs consistency`, and from `55 automated tests` to `56 automated tests`.

- [ ] **Step 3: Verify red**

Run:

```bash
bash scripts/test.sh
```

Expected: test suite fails at `T59 local-agent docs avoid skill drift`, because setup docs still contain stale 11-skill wording and README does not yet have the surface boundary section.

### Task 2: Add Root README Surface Boundary

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add product surfaces section**

Insert this section after the paragraph ending `tool-only ChatGPT App MCP server.`:

```markdown
## Product Surfaces

The full workflow is the local agent skill set. Use it when an agent can read and write the project files in your clone: chapters, reading notes, evidence registers, release packets, and export outputs.

The Codex plugin packages those same local skills for Codex plugin installation. It is a distribution surface, not a separate workflow.

The ChatGPT App MCP server is narrower. It provides pasted-text checks and template generation through temporary files only; it does not read or write a local thesis project, run the full skill pipeline, or persist user submissions.
```

- [ ] **Step 2: Verify boundary wording**

Run:

```bash
grep -n "Product Surfaces" README.md
grep -n "Local agent skill" README.md
grep -n "ChatGPT App MCP server" README.md
grep -n "pasted-text" README.md
```

Expected: each command prints a matching README line.

### Task 3: Align Local-Agent Setup Guides

**Files:**
- Modify: `docs/setup-claude-code.md`
- Modify: `docs/setup-codex-cli.md`
- Modify: `docs/setup-gemini-cli.md`
- Modify: `docs/setup-openclaw.md`
- Modify: `docs/skills/README.md`

- [ ] **Step 1: Update setup verify wording**

In each setup guide, replace the current “You should see...” sentence with the runtime-appropriate version:

```markdown
You should see the public local agent skills listed in [the skills guide](skills/README.md), including `evidence-review` and `release-governance`.
```

For `docs/setup-claude-code.md`, use the same sentence with slash-command examples:

```markdown
You should see the public local agent skills listed in [the skills guide](skills/README.md), including `/evidence-review` and `/release-governance`.
```

- [ ] **Step 2: Update available skill tables**

Ensure each setup guide’s `Available Skills` table includes these rows in workflow order:

```markdown
| read | Guided reading with page-by-page PDF extraction |
| note | Record structured reading notes |
| verify | Fact-check claims against sources |
| map | View literature coverage matrix |
| evidence-review | Build evidence-controlled gap maps and claim registers |
| integrate | Weave reading notes into chapter drafts |
| audit | Pre-submission consistency check |
| release-governance | Prepare release, rebuttal, artifact, and claim packets |
| style | Check British English consistency |
| logic-review | Review paragraph flow and transitions |
| verify-refs | Check BibTeX records and metadata |
| progress | Writing progress dashboard |
| export | Export chapters to Word (.docx) and ZIP |
```

For `docs/setup-claude-code.md`, keep slash-command labels in the first column.

- [ ] **Step 3: Update usage examples**

Add these examples to each setup guide after `audit`:

```text
evidence-review                       # Build evidence-controlled review maps
release-governance                    # Prepare release evidence packet
```

For `docs/setup-claude-code.md`, use slash-command forms:

```text
/evidence-review                      # Build evidence-controlled review maps
/release-governance                   # Prepare release evidence packet
```

- [ ] **Step 4: Fix OpenClaw configuration wording**

In `docs/setup-openclaw.md`, replace:

```markdown
OpenClaw reads `AGENTS.md` as its project instruction file, but **`AGENTS.md` is auto-generated** from `CLAUDE.md` by sub-project D's tooling.
```

with:

```markdown
OpenClaw reads `AGENTS.md` as its project instruction file, but **`AGENTS.md` is auto-generated** from `CLAUDE.md` by this toolkit's sync tooling.
```

- [ ] **Step 5: Mark the skills guide as canonical**

In `docs/skills/README.md`, after the opening paragraph, add:

```markdown
This page is the canonical public index for local agent skills. Runtime setup guides should point here rather than maintaining separate skill inventories.
```

### Task 4: Verify And Commit Documentation Pass

**Files:**
- Verify all modified docs and tests

- [ ] **Step 1: Run targeted drift checks**

Run:

```bash
rg -n "11 public academic writing skills" docs README.md
rg -n "evidence-review|release-governance" docs/setup-claude-code.md docs/setup-codex-cli.md docs/setup-gemini-cli.md docs/setup-openclaw.md
```

Expected: first command exits with no matches; second command prints matches in all four setup docs.

- [ ] **Step 2: Run full verification**

Run:

```bash
make test
make plugin-check
python3 scripts/audit-public-content.py --base-dir .
rg -n 'VU''LCA|/Users/yhry''zy|TO''DO|TB''D|FIX''ME|PLACE''HOLDER|待''补|待''定' plugins/academic-writing-toolkit docs README.md
git diff --check HEAD
```

Expected: `make test`, `make plugin-check`, public-content audit, and diff check pass. The `rg` leakage scan exits with no matches.

- [ ] **Step 3: Commit**

Run:

```bash
git add README.md docs/setup-claude-code.md docs/setup-codex-cli.md docs/setup-gemini-cli.md docs/setup-openclaw.md docs/skills/README.md scripts/test.sh docs/product/local-agent-docs-consistency-implementation-plan.md
git commit -m "docs: align local agent setup guides"
```

Expected: commit succeeds with only documentation and test-harness changes.
