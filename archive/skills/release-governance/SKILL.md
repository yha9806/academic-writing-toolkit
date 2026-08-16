---
name: release-governance
description: Use when preparing, auditing, releasing, or rebuttal-hardening academic manuscripts, datasets, artifacts, reviewer packets, or claim registers involving multiple refs, local assets, human labels, or agent-assisted drafts.
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# /release-governance - Release Evidence Governance

## Purpose

Prepare release-facing academic artifacts with explicit evidence control. The core rule is:

```text
release truth = ref + artifact + gate
```

Do not infer release truth from memory, a branch name, a pull request title, a local file cache, or an agent draft.

## Trigger Words

This skill activates on: `release governance`, `release evidence`, `camera-ready`, `rebuttal packet`, `artifact packet`, `claim ledger`, `human evidence gate`, `release packet`, `/release-governance`.

## Core Rules

1. Name the exact ref, artifact, and gate behind every release-facing claim.
2. Keep draft advisory evidence, verified artifacts, and final human evidence separate.
3. Do not promote agent or Gemini review output into final evidence.
4. Do not treat ignored, untracked, cached, or local-only assets as submitted artifacts.
5. Do not treat a repository check as venue, submission-system, or scientific compliance.
6. If two refs diverge, name both and scope which one is canonical for each artifact.
7. If a worktree is dirty, list the dirty paths and mark the packet as draft until changes are committed or explicitly scoped.

## Evidence States

Use `references/evidence_state_schema.md` for the shared states:

- `draft_advisory`
- `verified_artifact`
- `human_final`

`human_final` requires an explicit human confirmation gate when the project schema provides one. Agent drafts, reviewer suggestions, generated summaries, simulations, and prefilled labels stay `draft_advisory`.

## Workflow

### 1. Declare Scope

Create `release/release_scope.md` with scope date, artifact name, intended use, included refs, excluded refs, and the highest-risk open question.

### 2. Map Repository Truth

Run narrow ref checks before reading a checkout as final state:

```bash
git fetch --all --prune
git status --short --branch
git worktree list --porcelain
git branch --all --verbose --no-abbrev
```

Create `release/canonical_refs.csv`. Detached HEADs are acceptable only when the exact SHA is recorded.

### 3. Inventory Assets

Create `release/local_asset_inventory.csv` to separate tracked, ignored, untracked, external-store, and generated assets. Local assets may support review, but release claims require an artifact anchor or explicit exclusion.

### 4. Anchor Artifacts And Claims

Create:

- `release/artifact_anchors.csv`
- `release/claim_ledger.csv`
- `release/evidence_gates.csv`

Every paper-facing number, qualitative conclusion, table value, figure, dataset count, and human-label claim should point to the artifact and gate that support it.

### 5. Review Advisory Evidence

Gemini or another agent may review the scope, packet, or diff, but its result is advisory. Record advisory review in the verification report without changing any evidence state to `human_final`.

### 6. Verify Packet

Use `references/release_workflow_templates.md` for columns and report structure. If Python is available, run:

```bash
python {skill_dir}/scripts/check_release_packet.py <project_root>
```

The helper checks required packet files, CSV/JSON/YAML readability, evidence-state values, required columns, local absolute paths, and obvious template markers. YAML files use PyYAML when installed; otherwise the helper applies a basic local syntax check for simple mappings and lists. It does not run experiments, access networks, push branches, or judge scientific validity.

## Stop Conditions

Stop and report a blocker if:

- a final claim depends on a dirty or ambiguous ref
- a human-label claim lacks a human confirmation gate
- a release artifact exists only as an ignored, untracked, cache, or local-only file
- a count comes from a pointer, stub, generated preview, or non-canonical ref
- a draft pull request, closed-unmerged pull request, or advisory review is being treated as final release state
- the packet validator reports issues that affect release-facing claims
