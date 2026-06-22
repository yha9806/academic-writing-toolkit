---
name: argument-governance
description: Build and audit the manuscript argument system: intent, gap-contribution alignment, hierarchical claims, evidence balance, limitations, and reviewer attack surfaces. Use when a paper, thesis chapter, review article, or rebuttal needs explicit intent registers, contribution chains, claim hierarchy, argument maps, evidence-fit checks, or reviewer-risk matrices before drafting, revision, peer review, or self-review.
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# /argument-governance - Argument System Governance

## Purpose

Make the paper's argument inspectable as a system:

```text
intent -> gap -> contribution -> claim hierarchy -> evidence -> boundary -> reviewer risk
```

Use this before major manuscript revision, before `/peer-review`, before `/self-review`, or after `/manuscript-reframe` when the draft needs stronger gap-contribution and claim-evidence control.

## Codex-Only Baseline

Complete this workflow with Codex, local files, and the bundled checker. External reviewers, subagents, Gemini, or other model calls are optional advisory inputs only; do not require them and do not stop because they are unavailable.

## Enhanced Advisory Mode

When the user explicitly enables an API-key-backed reviewer, Codex may request an external advisory pass after the local argument packet exists. Use this only as a second opinion:

- keep API keys in environment variables, never in CSV, Markdown, logs, or manifests
- send only the source subset the user or manifest permits
- record the provider, model, source subset, prompt purpose, and output path
- place results in advisory notes or reviewer-risk fields
- never treat external output as evidence, source support, or a final gate

## Core Rules

1. Every contribution must answer a named gap.
2. Every main claim must belong to a contribution or the paper-level thesis.
3. Every lower-level claim must support a parent claim.
4. Every claim must have the right type and amount of evidence.
5. Background, methodological, workflow, or governance evidence must not be promoted into empirical, outcome, causal, or deployment validation.
6. Important claims must not be evidence-thin; peripheral claims must not be citation-padded.
7. Reviewer risks must target a specific intent, gap, contribution, claim, evidence cluster, or limitation.
8. Do not fill missing argument links from memory, prior chat, or unstated assumptions. Mark them as gaps.
9. Treat external model reviews as advisory notes, not evidence or required gates.

## Workflow

### 1. Locate The Manuscript And Evidence Base

Inspect the manuscript, references, reading notes, evidence registers, figures, tables, and any existing review or release packets. Record which files are canonical and which are exploratory.

### 2. Build Or Update The Governance Tables

Create or update these files under `evidence/`:

- `intent_register.csv`
- `contribution_chain.csv`
- `claim_hierarchy.csv`
- `argument_system_map.csv`
- `reviewer_attack_matrix.csv`

Read `references/argument_schema.md` before creating or editing these files.

### 3. Check The Argument Hierarchy

For each paper-level intent:

1. State the central problem and target reader.
2. Name the dominant narrative or missing frame the paper corrects.
3. Link each gap to one or more contributions.
4. Link each contribution to primary claims.
5. Link each claim to evidence IDs, citation keys, or declared evidence gaps.
6. Link each high-risk claim to boundary language and reviewer defenses.

### 4. Audit Evidence Balance

Use support-balance labels:

- `unsupported`
- `under_supported`
- `adequately_supported`
- `over_cited`
- `misaligned_evidence`

Treat `over_cited` as a real issue: too many citations on a minor or obvious claim can hide a weak argument spine.

### 5. Run The Deterministic Checker

Resolve the bundled helper at `scripts/check_argument_governance.py` relative to this `SKILL.md`, then run it from the project root:

```bash
python3 {skill_dir}/scripts/check_argument_governance.py . --json
```

The checker validates required files, columns, enums, ID references, tree links, missing evidence links, and weak high-risk reviewer defenses. It does not judge scientific novelty or correctness.

### 6. Report The Argument Health

For audit-only tasks, produce:

- gap-contribution alignment issues
- claim hierarchy breaks
- evidence balance problems
- overclaim and boundary-language risks
- reviewer attacks with weak defenses
- required revision actions

For edit tasks, wait for user approval before modifying manuscript prose.

## Output Pattern

```text
## Argument Governance Report

### Paper Spine
- Intent:
- Core gap:
- Main contributions:
- Paper-level thesis:

### Alignment Issues
| Severity | Location | Issue | Required action |

### Claim-Evidence Balance
| Claim ID | Support balance | Evidence status | Risk | Action |

### Reviewer Risks
| Target | Attack | Defense strength | Revision needed |

### Next Actions
```

## Stop Conditions

Stop and report a blocker if:

- the manuscript's central gap cannot be stated from the available packet
- a contribution lacks any named gap
- a main claim has no evidence anchor or declared evidence gap
- a result, causal, outcome, or deployment claim has only background or method evidence
- requested edits would require inventing evidence, venue expectations, reviewer opinions, or unpublished results
