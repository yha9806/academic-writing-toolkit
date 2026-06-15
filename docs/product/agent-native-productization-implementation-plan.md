# Agent-Native Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the P0 productization pack: clearer agent-native positioning, a runnable demo project, use-case docs, and `v0.3.0` release-readiness guidance.

**Architecture:** Keep the core product local-first and host-agnostic. Do not add runtime dependencies or new skill behaviour; use existing deterministic scripts to validate the demo and keep public docs from drifting into unsupported claims.

**Tech Stack:** Markdown docs, Bash regression harness in `scripts/test.sh`, existing Python validators for references, evidence-review packages, and release-governance packets.

---

## File Structure

- `README.md`: human-facing product entry point, surface chooser, 10-minute demo path, and use-case links.
- `examples/demo-project/`: safe generic project fixture that demonstrates the local workflow.
- `examples/demo-project/README.md`: demo explanation and exact validation commands.
- `examples/demo-project/CLAUDE.md`: demo project configuration for Claude Code.
- `examples/demo-project/AGENTS.md`: demo project instructions for Codex and compatible agents.
- `examples/demo-project/GEMINI.md`: demo project instructions for Gemini CLI.
- `examples/demo-project/chapters/ch01.md`: short chapter draft with generic citations.
- `examples/demo-project/literature/reading_notes/*.md`: two generic reading-note files.
- `examples/demo-project/references.bib`: offline-valid BibTeX for the demo.
- `examples/demo-project/evidence/*.csv`: evidence-review package validated by `check_review_package.py`.
- `examples/demo-project/release/*`: release-governance packet validated by `check_release_packet.py`.
- `docs/use-cases/README.md`: index for goal-oriented product guides.
- `docs/use-cases/write-literature-review.md`: local literature-review workflow guide.
- `docs/use-cases/audit-thesis-citations.md`: citation/style/logic audit workflow guide.
- `docs/use-cases/verify-references-before-submission.md`: reference verification workflow guide.
- `docs/use-cases/prepare-release-governance-packet.md`: release packet workflow guide.
- `docs/use-cases/choose-product-surface.md`: local skills versus Codex plugin versus ChatGPT App guidance.
- `docs/skills/README.md`: add a short cross-link to use-case docs without duplicating skill details.
- `docs/product/v0.3.0-release-readiness.md`: release checklist for the productization pass and PR #14.
- `scripts/test.sh`: add focused productization regression tests T61-T63.

## Execution Boundaries

Do not add new runtime dependencies in this pass. Do not implement Zotero import, RAG, vector search, hosted SaaS surfaces, or ChatGPT App access to local project files. If implementation pressure appears in any of those directions, stop and write a separate design first.

## Task 1: Add Productization Regression Tests

**Files:**
- Modify: `scripts/test.sh`

- [ ] **Step 1: Add failing structure and positioning test**

Insert this function after `test_T60()`:

```bash
test_T61() {
    local demo="$REPO_ROOT/examples/demo-project"
    local use_cases="$REPO_ROOT/docs/use-cases"

    [[ -f "$demo/README.md" ]] || return 1
    [[ -f "$demo/CLAUDE.md" ]] || return 1
    [[ -f "$demo/AGENTS.md" ]] || return 1
    [[ -f "$demo/GEMINI.md" ]] || return 1
    [[ -f "$demo/chapters/ch01.md" ]] || return 1
    [[ -f "$demo/literature/reading_notes/smith2024_NOTES.md" ]] || return 1
    [[ -f "$demo/literature/reading_notes/jones2023_NOTES.md" ]] || return 1
    [[ -f "$demo/references.bib" ]] || return 1

    [[ -f "$use_cases/README.md" ]] || return 1
    [[ -f "$use_cases/write-literature-review.md" ]] || return 1
    [[ -f "$use_cases/audit-thesis-citations.md" ]] || return 1
    [[ -f "$use_cases/verify-references-before-submission.md" ]] || return 1
    [[ -f "$use_cases/prepare-release-governance-packet.md" ]] || return 1
    [[ -f "$use_cases/choose-product-surface.md" ]] || return 1

    grep -q "agent-native" "$REPO_ROOT/README.md" || return 1
    grep -q "local-first" "$REPO_ROOT/README.md" || return 1
    grep -q "10-minute demo" "$REPO_ROOT/README.md" || return 1
    grep -q "docs/use-cases" "$REPO_ROOT/README.md" || return 1
    grep -q "examples/demo-project" "$REPO_ROOT/README.md" || return 1
}
```

- [ ] **Step 2: Add failing demo validation test**

Insert this function after `test_T61()`:

```bash
test_T62() {
    local demo="$REPO_ROOT/examples/demo-project"
    local out

    python3 scripts/verify-refs.py --bib "$demo/references.bib" --json >/dev/null || return 1
    python3 .claude/skills/evidence-review/scripts/check_review_package.py "$demo" --strict >/dev/null || return 1
    out=$(python3 .claude/skills/release-governance/scripts/check_release_packet.py "$demo" --json) || return 1
    echo "$out" | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['issue_count'] == 0"
}
```

- [ ] **Step 3: Add failing local-link and public-path guard**

Insert this function after `test_T62()`:

```bash
test_T63() {
    python3 - "$REPO_ROOT" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
files = [
    root / "README.md",
    root / "docs/use-cases/README.md",
    root / "docs/use-cases/write-literature-review.md",
    root / "docs/use-cases/audit-thesis-citations.md",
    root / "docs/use-cases/verify-references-before-submission.md",
    root / "docs/use-cases/prepare-release-governance-packet.md",
    root / "docs/use-cases/choose-product-surface.md",
    root / "examples/demo-project/README.md",
]
pattern = re.compile(r"!?\[[^\]]+\]\(([^)]+)\)")
missing = []
for path in files:
    if not path.is_file():
        missing.append(str(path.relative_to(root)))
        continue
    text = path.read_text(encoding="utf-8")
    for match in pattern.finditer(text):
        target = match.group(1).strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = target.split("#", 1)[0]
        if not target:
            continue
        candidate = (path.parent / target).resolve()
        if not str(candidate).startswith(str(root.resolve())) or not candidate.exists():
            missing.append(f"{path.relative_to(root)} -> {target}")
if missing:
    raise SystemExit("\n".join(missing))
PY
}
```

- [ ] **Step 4: Register the tests**

Add these run lines after the T60 run line:

```bash
run_test "T61 productization docs and demo structure exist" test_T61
run_test "T62 demo project validates with existing checkers" test_T62
run_test "T63 productization docs keep local links valid" test_T63
```

Update the header comment from:

```bash
# scripts/test.sh — runs the regression test suite (57 automated tests: T2-T18 toolkit + T19-T32 citation/env + T33-T44 public toolkit features + T45-T49 reference metadata + T50-T53 plugin packaging + T54-T58 release governance + T59 docs consistency + T60 Markdown BibTeX) for academic-writing-toolkit.
```

to:

```bash
# scripts/test.sh — runs the regression test suite (60 automated tests: T2-T18 toolkit + T19-T32 citation/env + T33-T44 public toolkit features + T45-T49 reference metadata + T50-T53 plugin packaging + T54-T58 release governance + T59 docs consistency + T60 Markdown BibTeX + T61-T63 productization) for academic-writing-toolkit.
```

- [ ] **Step 5: Verify red**

Run:

```bash
bash scripts/test.sh
```

Expected: the suite fails at T61, T62, and T63 because the productization docs and demo files do not exist yet.

- [ ] **Step 6: Commit failing tests**

Run:

```bash
git add scripts/test.sh
git commit -m "test: add productization regression guards"
```

Expected: commit succeeds with only `scripts/test.sh` staged.

## Task 2: Rewrite README Positioning And Onboarding

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README opening**

Replace the opening description through the current `Product Surfaces` section with:

```markdown
# academic-writing-toolkit

Agent-native, local-first workflows for evidence-controlled literature review, thesis writing, citation auditing, reference verification, and release governance.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-Standard-blue.svg)](https://agentskills.io)

Academic Writing Toolkit is a public toolkit for researchers who want their local AI agent to work through academic writing tasks with repeatable files, checks, and evidence controls. Install it into a writing project, open that project in Codex, Claude Code, Gemini CLI, Cursor, or another compatible agent host, and use the skills as a structured research workflow.

This is not a SaaS product and it does not host your thesis. Your chapters, PDFs, reading notes, evidence registers, release packets, and exports stay in your clone.

## Product Surfaces

Local agent skills are the full workflow. Use them when an agent can read and write the project files in your clone: chapters, reading notes, evidence registers, release packets, and export outputs.

The Codex plugin packages those same local skills for Codex plugin installation. It is a distribution surface, not a separate workflow.

The ChatGPT App MCP server is narrower. It provides pasted-text checks and template generation through temporary files only; it does not read or write a local thesis project, run the full skill pipeline, or persist user submissions.

## 10-minute demo

Inspect the runnable demo project:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```

Then open [`examples/demo-project/`](examples/demo-project/) in your agent host and ask it to explain the local workflow.

## Common use cases

- [Write a literature review](docs/use-cases/write-literature-review.md)
- [Audit thesis citations](docs/use-cases/audit-thesis-citations.md)
- [Verify references before submission](docs/use-cases/verify-references-before-submission.md)
- [Prepare a release-governance packet](docs/use-cases/prepare-release-governance-packet.md)
- [Choose the right product surface](docs/use-cases/choose-product-surface.md)
```

- [ ] **Step 2: Preserve the workflow diagram**

Move the existing pipeline diagram so it remains immediately after the new `Common use cases` section:

```markdown
## Workflow

```text
/read -> /note -> /map -> /evidence-review -> /integrate -> /audit -> /release-governance -> /style -> /logic-review -> /export
             |                                      |
             v                                      v
        /verify                               /verify-refs
             |
             v
        /progress
```
```

- [ ] **Step 3: Verify README content**

Run:

```bash
rg -n "agent-native|local-first|10-minute demo|docs/use-cases|examples/demo-project" README.md
```

Expected: each phrase appears in the README.

- [ ] **Step 4: Run targeted test**

Run:

```bash
bash scripts/test.sh
```

Expected: T61 still fails because demo and use-case files do not exist. README-related assertions in T61 should be satisfied.

- [ ] **Step 5: Commit README positioning**

Run:

```bash
git add README.md
git commit -m "docs: clarify agent native product positioning"
```

Expected: commit succeeds with only `README.md` staged.

## Task 3: Create Runnable Demo Project

**Files:**
- Create: `examples/demo-project/README.md`
- Create: `examples/demo-project/CLAUDE.md`
- Create: `examples/demo-project/AGENTS.md`
- Create: `examples/demo-project/GEMINI.md`
- Create: `examples/demo-project/chapters/ch01.md`
- Create: `examples/demo-project/literature/reading_notes/smith2024_NOTES.md`
- Create: `examples/demo-project/literature/reading_notes/jones2023_NOTES.md`
- Create: `examples/demo-project/references.bib`
- Create: `examples/demo-project/docs/review_protocol.md`
- Create: `examples/demo-project/evidence/evidence_matrix.csv`
- Create: `examples/demo-project/evidence/claim_register.csv`
- Create: `examples/demo-project/evidence/citation_plan.csv`
- Create: `examples/demo-project/evidence/overclaim_risk_register.csv`
- Create: `examples/demo-project/reports/review_summary.md`
- Create: `examples/demo-project/summaries/source_summary.md`
- Create: `examples/demo-project/release/release_scope.md`
- Create: `examples/demo-project/release/canonical_refs.csv`
- Create: `examples/demo-project/release/local_asset_inventory.csv`
- Create: `examples/demo-project/release/artifact_anchors.csv`
- Create: `examples/demo-project/release/evidence_gates.csv`
- Create: `examples/demo-project/release/claim_ledger.csv`
- Create: `examples/demo-project/release/verification_report.md`

- [ ] **Step 1: Create demo README**

Create `examples/demo-project/README.md`:

```markdown
# Demo Project

This demo shows the local Academic Writing Toolkit workflow without private research material.

Run these commands from the repository root:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```

The demo includes:

- a short chapter draft in [`chapters/ch01.md`](chapters/ch01.md)
- two reading notes in [`literature/reading_notes/`](literature/reading_notes/)
- a BibTeX file in [`references.bib`](references.bib)
- an evidence-review packet in [`evidence/`](evidence/)
- a release-governance packet in [`release/`](release/)

Open this folder in Codex, Claude Code, Gemini CLI, Cursor, or another compatible local agent and ask:

```text
Explain how this demo project moves from reading notes to evidence review and release governance.
```
```

- [ ] **Step 2: Create demo agent config files**

Create `examples/demo-project/CLAUDE.md`:

```markdown
# Demo Academic Writing Project

This is a public demo for Academic Writing Toolkit. It uses fictional source records and generic claims.

## Directories

- Chapters: `chapters/`
- Literature notes: `literature/reading_notes/`
- Evidence review packet: `evidence/`
- Release packet: `release/`

## Writing Principles

- Keep claims tied to reading notes.
- Use British English in chapter prose.
- Treat release packet checks as auditability checks, not human academic approval.
```

Create `examples/demo-project/AGENTS.md`:

```markdown
# Demo Academic Writing Project

Follow `CLAUDE.md` for the demo workflow. Use the repository-level Academic Writing Toolkit skills when available.

## Checks

Run these from the repository root when validating the demo:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```
```

Create `examples/demo-project/GEMINI.md`:

```markdown
# Demo Academic Writing Project

This demo mirrors the local agent workflow described in `CLAUDE.md`.

Use it to explain or inspect the workflow. Do not treat the fictional sources as real scholarship.
```

- [ ] **Step 3: Create chapter and reading notes**

Create `examples/demo-project/chapters/ch01.md`:

```markdown
# Chapter 1: Local-first Review Workflow

Local-first academic writing workflows benefit from separating source notes, evidence claims, and release checks (Smith 2024; Jones 2023).

Smith (2024) describes a file-based workflow where notes and claims remain inspectable. Jones (2023) focuses on review audit trails and argues that explicit decision records make later synthesis easier to check.
```

Create `examples/demo-project/literature/reading_notes/smith2024_NOTES.md`:

```markdown
# Smith 2024 Notes

**Status**: complete
**Source**: Smith, Jane (2024). Local-first research workflows. Journal of Research Tooling.

## Relevance

Supports the demo claim that local files can keep notes and claims inspectable.

## Detailed Notes

- The article describes storing source notes beside draft materials.
- The article treats auditability as a workflow property.

## Thesis Connections

- Use in the introduction to explain why local-first workflows matter.
```

Create `examples/demo-project/literature/reading_notes/jones2023_NOTES.md`:

```markdown
# Jones 2023 Notes

**Status**: complete
**Source**: Jones, Alex (2023). Review audit trails for research teams. Proceedings of Demo Methods.

## Relevance

Supports the demo claim that explicit decision records help later review.

## Detailed Notes

- The paper describes lightweight decision records for review teams.
- The paper separates screening decisions from final synthesis prose.

## Thesis Connections

- Use in the evidence-review section to motivate claim registers.
```

- [ ] **Step 4: Create BibTeX file**

Create `examples/demo-project/references.bib`:

```bibtex
@article{smith2024,
  title = {Local-first research workflows},
  author = {Smith, Jane},
  year = {2024},
  journal = {Journal of Research Tooling},
  doi = {10.1000/demo-smith}
}

@inproceedings{jones2023,
  title = {Review audit trails for research teams},
  author = {Jones, Alex},
  year = {2023},
  booktitle = {Proceedings of Demo Methods},
  url = {https://example.org/demo/jones2023}
}
```

- [ ] **Step 5: Create evidence-review packet**

Create `examples/demo-project/docs/review_protocol.md`:

```markdown
# Demo Review Protocol

Question: How can a local academic writing workflow keep source notes, claims, and release checks inspectable?

Scope: This demo uses fictional records to show file structure and validation only.
```

Create `examples/demo-project/evidence/evidence_matrix.csv`:

```csv
source_id,citation_key,evidence_status,claim_supported,source_path,notes
S1,smith2024,verified_artifact,local-first workflows keep notes inspectable,literature/reading_notes/smith2024_NOTES.md,Supports file-based note workflow
S2,jones2023,verified_artifact,decision records support review audit trails,literature/reading_notes/jones2023_NOTES.md,Supports explicit review records
```

Create `examples/demo-project/evidence/claim_register.csv`:

```csv
claim_id,claim_text,evidence_status,sources,scope_boundary,manual_check_needed
C1,Local-first workflows can separate source notes evidence claims and release checks,verified_artifact,smith2024;jones2023,demo project only,false
```

Create `examples/demo-project/evidence/citation_plan.csv`:

```csv
claim_id,citation_key,placement,rationale
C1,smith2024,chapter introduction,Supports inspectable local note workflow
C1,jones2023,chapter introduction,Supports explicit audit trail workflow
```

Create `examples/demo-project/evidence/overclaim_risk_register.csv`:

```csv
risk_id,claim_id,risk,mitigation,status
R1,C1,Claim could sound universal,Limit wording to demo workflow and fictional records,mitigated
```

Create `examples/demo-project/reports/review_summary.md`:

```markdown
# Demo Review Summary

The demo evidence packet links one workflow claim to two fictional sources and marks one overclaim risk as mitigated.
```

Create `examples/demo-project/summaries/source_summary.md`:

```markdown
# Demo Source Summary

Smith 2024 supports local note inspectability. Jones 2023 supports explicit review decision records.
```

- [ ] **Step 6: Create release-governance packet**

Create `examples/demo-project/release/release_scope.md`:

```markdown
# Demo Release Scope

This release packet covers the fictional demo chapter and its evidence-review files. It demonstrates packet structure and validator behaviour only.
```

Create `examples/demo-project/release/canonical_refs.csv`:

```csv
ref_name,sha,date,status,canonical_for,caveat
demo-manuscript,abc1234,2026-06-15,locked,chapter-draft,demo checksum not used for publication
demo-evidence,def5678,2026-06-15,locked,evidence-packet,demo checksum not used for publication
```

Create `examples/demo-project/release/local_asset_inventory.csv`:

```csv
path,status,file_count,size,role,release_action
chapters/ch01.md,present,1,1 KB,manuscript-demo,keep
evidence/evidence_matrix.csv,present,1,1 KB,evidence-demo,keep
```

Create `examples/demo-project/release/artifact_anchors.csv`:

```csv
artifact_id,source_ref,source_path,count_or_checksum,evidence_state,verified_by,claim_supported
art-chapter-claim,demo-manuscript,chapters/ch01.md,abc1234,verified_artifact,automated-demo-check,local-first workflow claim
art-evidence-matrix,demo-evidence,evidence/evidence_matrix.csv,def5678,verified_artifact,automated-demo-check,evidence packet structure
```

Create `examples/demo-project/release/evidence_gates.csv`:

```csv
gate_id,artifact_id,evidence_state,human_confirmed,reviewer,review_date,validator,status
gate-1,art-chapter-claim,verified_artifact,false,,,.claude/skills/release-governance/scripts/check_release_packet.py,passed
gate-2,art-evidence-matrix,verified_artifact,false,,,.claude/skills/release-governance/scripts/check_release_packet.py,passed
```

Create `examples/demo-project/release/claim_ledger.csv`:

```csv
claim_id,claim_text,artifact_ids,evidence_state,denominator,scope_boundary,human_gate_required,status
claim-1,Local-first workflows can separate source notes evidence claims and release checks,art-chapter-claim;art-evidence-matrix,verified_artifact,two fictional demo sources,demo project only,false,ready
```

Create `examples/demo-project/release/verification_report.md`:

```markdown
# Demo Verification Report

The demo packet validates with the release-governance checker. The packet demonstrates structure and evidence-state handling, not scholarly truth.
```

- [ ] **Step 7: Run demo validators**

Run:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```

Expected: all three commands exit 0. The release-governance JSON output has `"issue_count": 0`.

- [ ] **Step 8: Run regression suite**

Run:

```bash
bash scripts/test.sh
```

Expected: T62 passes. T61 and T63 still fail until use-case docs are created.

- [ ] **Step 9: Commit demo project**

Run:

```bash
git add examples/demo-project
git commit -m "docs: add runnable academic workflow demo"
```

Expected: commit succeeds with only `examples/demo-project/` staged.

## Task 4: Add Use-Case Documentation

**Files:**
- Create: `docs/use-cases/README.md`
- Create: `docs/use-cases/write-literature-review.md`
- Create: `docs/use-cases/audit-thesis-citations.md`
- Create: `docs/use-cases/verify-references-before-submission.md`
- Create: `docs/use-cases/prepare-release-governance-packet.md`
- Create: `docs/use-cases/choose-product-surface.md`
- Modify: `docs/skills/README.md`

- [ ] **Step 1: Create use-case index**

Create `docs/use-cases/README.md`:

```markdown
# Use Cases

These guides explain Academic Writing Toolkit by user goal. For the full skill inventory, see the [skills guide](../skills/README.md).

| Goal | Guide |
|------|-------|
| Write a literature review | [write-literature-review.md](write-literature-review.md) |
| Audit thesis citations | [audit-thesis-citations.md](audit-thesis-citations.md) |
| Verify references before submission | [verify-references-before-submission.md](verify-references-before-submission.md) |
| Prepare a release-governance packet | [prepare-release-governance-packet.md](prepare-release-governance-packet.md) |
| Choose the right product surface | [choose-product-surface.md](choose-product-surface.md) |
```

- [ ] **Step 2: Create literature review guide**

Create `docs/use-cases/write-literature-review.md`:

```markdown
# Write A Literature Review

Use the local agent skills when your agent can read and write the project folder.

## Workflow

1. Use [`/read`](../skills/01-read.md) to inspect source PDFs or source text.
2. Use [`/note`](../skills/02-note.md) to create one notes file per source.
3. Use [`/map`](../skills/04-map.md) to see coverage against chapters.
4. Use [`/evidence-review`](../skills/12-evidence-review.md) to build evidence matrices, claim registers, citation plans, and overclaim checks.
5. Use [`/integrate`](../skills/05-integrate.md) to propose chapter edits from completed notes.

## Validate

Run the evidence-review package checker when a review packet exists:

```bash
python3 .claude/skills/evidence-review/scripts/check_review_package.py . --strict
```

The checker validates package structure and parseability. It does not replace human judgement about the literature.
```

- [ ] **Step 3: Create citation audit guide**

Create `docs/use-cases/audit-thesis-citations.md`:

```markdown
# Audit Thesis Citations

Use citation auditing before major drafts, supervisor review, submission, or release.

## Workflow

1. Confirm the citation style in `CLAUDE.md`.
2. Use [`/audit`](../skills/06-audit.md) for citation pairing, style-format checks, terminology, numbers, and cross-references.
3. Use [`/style`](../skills/09-style.md) when British English consistency matters.
4. Use [`/logic-review`](../skills/10-logic-review.md) to inspect paragraph flow and repeated transitions.

## Validate

Run deterministic checks directly when needed:

```bash
python3 scripts/audit-citations.py --base-dir . --style harvard --json
python3 scripts/audit-british-english.py --base-dir . --json
python3 scripts/audit-logic.py --base-dir . --json
```

Safe fixers are intentionally narrow. Review suggested edits before applying them to thesis prose.
```

- [ ] **Step 4: Create reference verification guide**

Create `docs/use-cases/verify-references-before-submission.md`:

```markdown
# Verify References Before Submission

Use [`/verify-refs`](../skills/11-verify-refs.md) before submission, camera-ready packaging, or bibliography cleanup.

## Workflow

1. Export or collect BibTeX records into a `.bib` file.
2. Run offline structure checks first.
3. Add explicit online metadata checks only when network access and external API use are acceptable.

## Validate

```bash
python3 scripts/verify-refs.py --bib references.bib --json
python3 scripts/verify-refs.py --bib references.bib --json --online
```

For deterministic review or CI, use metadata fixtures:

```bash
python3 scripts/verify-refs.py --bib references.bib --json --online --metadata-dir path/to/metadata-fixtures
```

The public toolkit intentionally excludes project-specific self-citation rules and author-name assumptions.
```

- [ ] **Step 5: Create release-governance guide**

Create `docs/use-cases/prepare-release-governance-packet.md`:

```markdown
# Prepare A Release-Governance Packet

Use [`/release-governance`](../skills/13-release-governance.md) when preparing release, rebuttal, artifact, or camera-ready materials that need explicit evidence-state control.

## Workflow

1. Define the release scope.
2. Record canonical references and local assets.
3. Anchor claims to artifacts.
4. Record evidence gates and human-final confirmations when required.
5. Run the release packet validator.

## Validate

```bash
python3 .claude/skills/release-governance/scripts/check_release_packet.py . --json
```

The validator checks required files, columns, evidence states, parseability, local path leakage, and unresolved working markers. It does not judge scientific validity or venue compliance.
```

- [ ] **Step 6: Create surface chooser guide**

Create `docs/use-cases/choose-product-surface.md`:

```markdown
# Choose The Right Product Surface

Academic Writing Toolkit has three public surfaces.

## Local Agent Skills

Use this for the full workflow. The agent can read and write your local project files: chapters, notes, evidence registers, release packets, and exports.

Start here when you use Claude Code, Codex, Gemini CLI, Cursor, or another compatible local agent host.

## Codex Plugin

Use this when you want the same local skills packaged as an installable Codex plugin. The plugin is a distribution wrapper, not a different workflow.

## ChatGPT App MCP Server

Use this for pasted-text checks and reading-note template generation. The ChatGPT App surface processes temporary text inputs only. It does not read or write your local thesis project and does not run the full local workflow.

## Quick Rule

If the task needs project files, use local agent skills. If the task only needs pasted text, the ChatGPT App surface can be enough.
```

- [ ] **Step 7: Add cross-link from skills guide**

Add this paragraph after the canonical-index sentence in `docs/skills/README.md`:

```markdown
If you want to start from a goal rather than a skill name, see the [use-case guides](../use-cases/README.md).
```

- [ ] **Step 8: Run link guard**

Run:

```bash
bash scripts/test.sh
```

Expected: T61 and T63 now pass. All tests should pass unless release-readiness docs are still referenced before creation.

- [ ] **Step 9: Commit use-case docs**

Run:

```bash
git add docs/use-cases docs/skills/README.md
git commit -m "docs: add use case onboarding guides"
```

Expected: commit succeeds with only use-case docs and skills index staged.

## Task 5: Add v0.3.0 Release Readiness Doc

**Files:**
- Create: `docs/product/v0.3.0-release-readiness.md`
- Modify: `README.md`

- [ ] **Step 1: Create release readiness doc**

Create `docs/product/v0.3.0-release-readiness.md`:

```markdown
# v0.3.0 Release Readiness

## Release Theme

`v0.3.0` turns Academic Writing Toolkit into a clearer agent-native product surface for evidence-controlled review and release work.

## Included Work

- release-governance skill
- local agent documentation consistency
- verify-refs public migration guard
- agent-native product positioning
- runnable demo project
- use-case onboarding guides

## Required Checks

Run these before tagging or publishing:

```bash
make test
make plugin-check
make chatgpt-app-check
python3 scripts/audit-public-content.py --base-dir .
git diff --check HEAD
```

Run the demo validators:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```

## Release Notes Draft

Academic Writing Toolkit `v0.3.0` adds release-governance workflows, clearer local-agent product positioning, a runnable demo project, use-case onboarding guides, and stronger public-content guards.

The toolkit remains local-first. The full workflow runs through local agent skills; the Codex plugin packages those skills; the ChatGPT App MCP server remains a narrower pasted-text tool surface.

## Not Included

- Zotero import
- local document RAG
- vector search
- hosted SaaS workflows
- ChatGPT App access to local project files
```

- [ ] **Step 2: Link release readiness from README**

Add this sentence near the `Testing And Maintenance` section in `README.md`:

```markdown
For `v0.3.0` release preparation, use [`docs/product/v0.3.0-release-readiness.md`](docs/product/v0.3.0-release-readiness.md).
```

- [ ] **Step 3: Run link guard**

Run:

```bash
bash scripts/test.sh
```

Expected: all tests pass.

- [ ] **Step 4: Commit release readiness doc**

Run:

```bash
git add docs/product/v0.3.0-release-readiness.md README.md
git commit -m "docs: add v0.3.0 release readiness checklist"
```

Expected: commit succeeds with only README and release-readiness doc staged.

## Task 6: Final Verification And Push

**Files:**
- Verify all modified files

- [ ] **Step 1: Run full local checks**

Run:

```bash
make test
make plugin-check
make chatgpt-app-check
python3 scripts/audit-public-content.py --base-dir .
rg -n 'VU''LCA|EM''NLP|/Users/yhry''zy|TO''DO|TB''D|FIX''ME|PLACE''HOLDER|待''补|待''定' README.md docs examples plugins/academic-writing-toolkit
git diff --check HEAD
```

Expected: `make test`, `make plugin-check`, `make chatgpt-app-check`, public-content audit, and diff check pass. The `rg` leakage scan exits with no matches.

- [ ] **Step 2: Check branch state**

Run:

```bash
git status --short --branch
git log --oneline --decorate --max-count=8
```

Expected: worktree is clean. Recent commits show the productization plan, tests, README positioning, demo project, use-case docs, and release readiness.

- [ ] **Step 3: Push branch**

Run:

```bash
git push
```

Expected: `codex/release-governance-skill` pushes successfully.

- [ ] **Step 4: Verify PR checks**

Run:

```bash
gh pr checks 14 --repo yha9806/academic-writing-toolkit --watch
```

Expected: GitHub checks pass for PR #14.

## Self-Review

Spec coverage:

- README positioning is covered by Task 2.
- Demo project is covered by Task 3.
- Use-case docs are covered by Task 4.
- Product surface separation is covered by Task 2 and Task 4.
- `v0.3.0` readiness is covered by Task 5.
- Public-content and validation guards are covered by Task 1 and Task 6.

Scope check:

- No new runtime dependencies are introduced.
- Zotero import, RAG, vector search, hosted SaaS, and ChatGPT App expansion remain out of scope.
- Demo content is fictional and generic.
- Existing validators are reused instead of adding new validation systems.
