---
name: argument-governance
description: Build and audit the manuscript or research-project argument system across intent, gaps, claims, data, results, contributions, innovation evidence, limitations, and contribution focus. Use when a paper, thesis chapter, review article, or research project needs an explicit argument map, evidence-fit or over/under-balance checks, contribution prioritisation, innovation-evidence checks, or a decision about whether the current contribution emphasis should change; also use for Chinese requests such as 梳理研究项目、研究主线、贡献侧重、创新证据、结果是否支撑论点、内容或证据是否过多或过少.
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# /argument-governance - Argument System Governance

## Purpose

Make the paper's argument inspectable as a system:

```text
intent -> gap -> contribution
data -> result -> claim -> contribution
prior-work evidence -> innovation -> contribution
claim/contribution -> boundary -> reviewer risk
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
10. Keep data and results separate: data are analysis inputs; results are derived outputs with a method, scope, and provenance.
11. Keep contribution and innovation separate: contribution states what the project delivers; innovation states how it differs from an explicit comparison set.
12. Judge over- or under-balance by missing, duplicated, orphaned, conflicting, or scope-mismatched functions. Do not infer quality from raw counts, word count, citation count, dataset count, or one composite score.
13. Treat contribution-focus changes as advisory candidates. Require an explicit author decision before changing the title, abstract, research question, contribution order, or manuscript spine.
14. Keep the field-level gap, paper-level contribution, data-level finding, and extrapolative claim separate. A true field gap does not prove that this paper closes it; require evidence for every upward inference.
15. Treat boundary as a paper-wide evidence licence across intent, population or denominator, estimand, evidence scope, title, abstract, contribution list, result headings, and conclusion, not as a limitation-only disclaimer.
16. Do not treat tables, ledgers, guardrails, qualifiers, or appendices as substitutes for missing construct validity, reliability, sampling, baseline, power, or transfer evidence. Record `evidence_needed` or narrow the claim.
17. When a `thesis_control/` project-intent layer exists, reuse its unique active
    author-approved `intent_id`. A draft, unapproved, partial, multiply active,
    or conflicting layer is a stop condition, not permission to create another
    intent root.

## Workflow

### 1. Locate The Manuscript And Evidence Base

Inspect the manuscript, references, reading notes, evidence registers, figures, tables, and any existing review or release packets. Record which files are canonical and which are exploratory.

If any of `thesis_control/project_intent.csv`,
`thesis_control/manuscript_contracts.csv`, or
`thesis_control/global_thesis_audits.csv` exists, read `$thesis-control` and run
its checker with `--strict --json` before changing the argument packet. Use the
unique active author-approved project `intent_id` in `intent_register.csv`,
`contribution_chain.csv`, `claim_hierarchy.csv`, and `gap_register.csv`. Stop
when the layer is partial or unresolved, or when an existing argument intent
conflicts with it. Do not treat a scaffolded draft as author approval.

### 2. Build Or Update The Governance Tables

Create or update these files under `evidence/`:

- `intent_register.csv`
- `contribution_chain.csv`
- `claim_hierarchy.csv`
- `argument_system_map.csv`
- `reviewer_attack_matrix.csv`

Read `references/argument_schema.md` before creating or editing these files.

For full research-project relation auditing, also create:

- `gap_register.csv`
- `evidence_objects.csv`
- `innovation_register.csv`
- `argument_relations.csv`
- `contribution_focus.csv`

These files form the explicit relation profile. Legacy five-table packets remain valid without them. Never infer missing data, result, or innovation records while upgrading an older packet.

### 3. Check The Argument Hierarchy

For each paper-level intent:

1. State the central problem and target reader.
2. Separate the broad problem, exact paper contribution, primary empirical
   claim, headline or extrapolative claim, licensed scope, and explicitly
   unlicensed claims. Reuse existing object IDs and boundary fields; do not
   create a second schema.
3. Name the dominant narrative or missing frame the paper corrects.
4. Link each gap to one or more contributions.
5. Link each contribution to primary claims.
6. Link each claim to evidence IDs, citation keys, or declared evidence gaps.
7. Audit every upward inference from finding to headline or generalisation and
   require a new evidence anchor for each escalation.
8. Compare the licence with the title, abstract thesis, contribution list,
   result headings, and conclusion.
9. If framing exceeds the research design, record `narrow` or
   `evidence_needed`; boundary prose alone does not complete the chain.
10. Link each high-risk claim to boundary language and reviewer defenses.

### 4. Audit Evidence Balance

Use support-balance labels:

- `unsupported`
- `under_supported`
- `adequately_supported`
- `over_cited`
- `misaligned_evidence`

Treat `over_cited` as a real issue: too many citations on a minor or obvious claim can hide a weak argument spine.

Also distinguish functional balance:

- `under_connected`: a required gap, data, result, claim, contribution, or innovation relation is missing
- `orphaned`: a valid object is not used by the argument
- `duplicated`: two contributions or claims perform the same function with substantially the same support
- `scope_mismatched`: evidence exists but its population, task, metric, or comparison scope does not match the claim
- `conflicted`: reliable results point in different directions and the claim does not preserve that uncertainty

Use these labels as explainable diagnostics, not as proof of scientific quality.

### 5. Run The Deterministic Checker

Resolve the bundled helper at `scripts/check_argument_governance.py` relative to this `SKILL.md`, then run it from the project root:

For a legacy packet:

```bash
python3 {skill_dir}/scripts/check_argument_governance.py . --json
```

For the explicit gap-claim-data-result-contribution-innovation profile:

```bash
python3 {skill_dir}/scripts/check_argument_governance.py . --strict-relations --json
```

The checker validates required files and values, columns, enums, typed ID references, cross-table target consistency, relation cycles, required evidence paths, orphaned results, contribution redundancy candidates, and focus-review candidates. A relation completes an evidence path only when it is verified, direct or partial, scope-matched, and backed by an available or verified object with traceable provenance and checked quality. Candidate, contested, indirect, unverified, or unknown-scope links remain diagnostics; they do not complete a chain. The checker does not judge scientific novelty, importance, correctness, or venue acceptance.

### 6. Review Contribution Focus

When the current main contribution may no longer be the most defensible emphasis:

1. Once the checker or a manual audit identifies a focus candidate, freeze the current intent, primary contribution IDs, manuscript spine, and author-approved version in `evidence/contribution_focus_snapshot.json`; include the packet hash and manuscript hash or explicitly mark either as unavailable.
2. Compare current primary and candidate contributions on core-gap fit, required evidence-chain completeness, result consistency, innovation-comparison evidence, target-reader fit, scope risk, and narrative emphasis.
   A candidate must share the current primary contribution's `intent_id`; never move a contribution across paper or manuscript-unit boundaries through a focus recommendation.
3. Report supporting and counter-signals. Do not select a winner from a total score.
4. Offer only bounded candidate actions: `keep`, `narrow`, `promote`, `demote`, `merge`, `remove`, or `evidence_needed`.
5. Require an author decision before updating contribution focus.
6. If the decision changes the research question, core gap, title, abstract thesis, or paper-wide narrative, hand off an approved brief to `/manuscript-reframe`. Otherwise create a bounded `/thesis-control` edit contract before changing prose.

The checker may emit `focus_review_candidates`; this is a diagnostic handoff, not automatic routing or author approval. It requires a valid `contribution_focus_snapshot.json` whenever a candidate is emitted. The snapshot IDs must match the affected intent and its current primary contributions, the author-approved manuscript must exist inside the project, and captured file patterns must resolve inside the project and cover the required packet CSVs. `recommended_next_skill=pending_author_decision` remains unchanged until the author chooses a before/after focus state. Weaknesses are counted by independent dimensions (evidence chain, gap fit, reader fit, result consistency, innovation, and narrative), so two symptoms of the same gap problem do not satisfy the two-signal gate.

After approval, keep the change under the existing three-attempt revision gate. If three focus revisions fail their acceptance checks, stop and use `/revision-escalation` before a fourth edit; do not keep patching the title, abstract, introduction, or contribution list.

### 7. Report The Argument Health

For audit-only tasks, produce:

- gap-contribution alignment issues
- claim hierarchy breaks
- data-result-claim chain breaks
- innovation claims without explicit comparison evidence
- evidence balance problems
- content-function excess or shortage candidates
- contribution-focus review candidates with counter-signals
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

### Argument Licence And Headline Scope
- Broad problem:
- Exact paper contribution:
- Primary empirical claim:
- Headline or extrapolative claim:
- Licensed scope:
- Explicitly unlicensed claims:
- Repair layer: wording / argument design / research design
- Boundary propagation status:

### Alignment Issues
| Severity | Location | Issue | Required action |

### Claim-Evidence Balance
| Claim ID | Support balance | Evidence status | Risk | Action |

### Functional Balance
| Rule | Relationship path | Too little / too much / mismatch | Severity | Confidence | Action |

### Contribution Focus Review
| Current role | Contribution | Gap fit | Evidence chain | Result consistency | Innovation evidence | Supporting signals | Counter-signals | Candidate action | Approval status | Affected sections / cost | Route if approved |

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
- a requested focus shift lacks an explicit author decision
- the current primary contribution or latest author-approved manuscript spine cannot be identified
- an existing project-intent layer is partial, unapproved, multiply active, or
  inconsistent with the argument packet's `intent_id`
- data and results cannot be distinguished from the available project artifacts
- an innovation claim has no declared comparison set but the user asks to present it as established novelty
- the field gap, paper contribution, data-level finding, and extrapolative claim cannot be separated
- a headline claim exceeds the licensed scope and no new evidence or narrowing decision is available
- a late higher-level framing has no matching estimand or research design
- the user asks prose editing to repair a construct, reliability, sampling, baseline, power, or transfer-evidence deficit
- boundary language appears only in limitations while stronger claims remain in the title, abstract, contribution list, result headings, or conclusion
