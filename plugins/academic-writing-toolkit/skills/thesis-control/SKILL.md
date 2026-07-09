---
name: thesis-control
description: Use when AI-assisted thesis edits risk claim drift, scope creep, loss of author control, or repeated revisions that fail to converge; provides spine cards, edit contracts, drift audits, revision escalation, and human gates.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
---

# /thesis-control - Thesis Drift Control

## Purpose

Prevent AI-assisted writing from becoming fluent but distorted. Use this before and after substantive thesis edits when the risk is not spelling or style, but loss of author control: widened claims, blurred section purpose, missing caveats, unsynchronised adjacent paragraphs, or local edits that weaken the chapter spine.

## Trigger Words

This skill activates on: `thesis control`, `drift audit`, `edit contract`, `spine card`, `claim drift`, `author control`, `loss of control`, `scope creep`, `rewrite risk`, `/thesis-control`.

## Core Rule

Do not edit thesis prose until the intended change has an explicit contract.

The contract must answer:

```text
This edit is allowed to change [specific local issue] in [specific unit], while preserving [spine sentence], [scope boundary], [core claims], and [do-not-change items].
```

If this sentence cannot be written, stop and diagnose the section instead of rewriting it.

## Control Files

Use a `thesis_control/` directory when the project needs durable tracking:

- `spine_cards.csv`
- `edit_contracts.csv`
- `drift_audits.csv`
- `revision_escalations.csv`

Run the optional validator when Python is available:

```bash
python {skill_dir}/scripts/check_thesis_control.py <project_root> --strict
```

The validator checks packet structure and gate consistency. It does not judge scholarly truth.

Strict validation requires revision-tracking schema v3. Upgrade a complete
legacy packet without guessing historical revision families:

```bash
python {skill_dir}/scripts/upgrade_thesis_control_revision_tracking.py <project_root>
```

To create a draft packet from a real Markdown unit before editing prose:

```bash
python {skill_dir}/scripts/scaffold_thesis_control.py <project_root> \
  --source chapters/ch1_introduction.md \
  --start-line 71 \
  --end-line 104 \
  --revision-issue-id ri-ch1-gap-clarity \
  --attempt-no 1 \
  --copy-source
```

The scaffold writes `human_approved=false`, `status=draft`, and
`AUTHOR_REVIEW_REQUIRED` fields. Replace those fields with concrete author
judgement before applying a substantive edit. Its default contract id includes
the attempt number, so attempts 1 and 2 become `ec-<unit>-001` and
`ec-<unit>-002`. Reuse an explicit `revision_issue_id` for retries.

The migration helper stops without writing when revision metadata is partial or
when a legacy escalation cannot be classified from current contracts and
resolved audits. It preserves named extension columns and converts one- or
two-trigger legacy rows to `early_diagnostic`; a three-trigger row becomes a
`cycle_gate` only when it already matches one completed failure group.

## Workflow

### 1. Establish Or Read The Spine Card

Before editing a chapter, section, or paragraph cluster, identify:

- unit id
- source path
- section title
- spine sentence
- scope boundary
- core claims
- do-not-change items

The spine sentence should be narrow:

```text
This unit argues that [specific claim] by showing [specific basis], so the chapter can [specific function].
```

If the current text does not support a clear spine sentence, produce a diagnosis and ask for author direction before changing prose.

### 2. Create The Edit Contract

For every substantive edit, state:

- target unit and file range
- change scope
- allowed changes
- forbidden changes
- adjacent context that must be checked
- acceptance checks
- whether human approval is required before editing

When using the scaffold helper, treat its output as a draft control packet, not
as approval. A generated contract becomes actionable only after the author has
replaced the `AUTHOR_REVIEW_REQUIRED` fields and explicitly approved the scope.

Always require human approval for:

- changing the section spine
- adding or broadening claims
- deleting caveats or limitations
- moving evidence between sections
- rewriting more than one paragraph
- merging or splitting sections

### 3. Apply Only Approved Changes

After approval, edit only the approved scope.

Keep mechanical fixes separate from argument changes. Do not bundle style, structure, evidence, and claim changes into one patch unless the contract explicitly allows it.

### 4. Run The Drift Audit

After editing, compare the new prose against the contract and report:

- changed claims
- changed boundaries or caveats
- new unsupported claims
- deleted evidence anchors
- missed adjacent updates
- section-spine change
- decision: accept, partial accept, revise, or rollback

If any claim, boundary, or caveat changed, the result needs human review even if the prose is smoother.

Use audit `status=needs_review` only while the author's post-edit decision is
pending. Strict validation blocks an applied contract in that state. After the
author decides, record `status=passed` for `accept` or `partial_accept`, and
`status=failed` for `revise` or `rollback`. Do not treat a pending audit as a
completed unsuccessful attempt.

### 5. Record Human Gate Outcome

The author decides whether to accept, partially accept, revise, or rollback. Do not mark a high-risk edit as accepted without explicit human approval.

## Revision Escalation Rule

Treat three unsuccessful attempts on the same revision issue as an operational escalation threshold, not as evidence that every task fails after three turns. Use `revision_issue_id` to keep successive contract versions attached to that issue. Only count an attempt when its drift decision is `revise` or `rollback` and its audit status is `failed`. Only applied contracts count as unsuccessful attempts. Record author rejection as one of those decisions. Multiple failed audits of one contract still count as one attempt; contradictory passed and failed resolved audits are invalid. Clarifying discussion, pending human reviews, and unexecuted proposals do not count.

After three unsuccessful attempts, stop. Do not apply a fourth prose patch. Record a row in `revision_escalations.csv`; a later contract may become `approved` or `applied` only after the matching escalation has `human_approved=true` and `status=approved`.

An approved escalation closes only that group of three unsuccessful contracts. If three later contracts also receive `revise` or `rollback`, require a new escalation before another contract can proceed.

Only a `cycle_gate` whose three triggers exactly match one completed group of
unsuccessful contracts, in attempt order, may close that group. Set
`approved_after_attempt` to the final attempt number in that group. The gate is
effective only with `human_approved=true` and `status=approved`. One gate cannot
close more than one group. Do not repeat a trigger contract within a row or
create multiple rows for the same issue and trigger set.

Only an escalation whose trigger set exactly matches one completed group of three unsuccessful contracts may close that group. One escalation cannot close more than one group.

Record an earlier warning as `early_diagnostic` with one or two unique triggers
and an empty `approved_after_attempt`. It may be author-approved as a diagnosis,
but it never closes or pre-authorises a later completed group.

An earlier escalation with fewer than three trigger contracts does not close or pre-authorise a later completed group.

Escalate earlier than three attempts when any of these signals is already visible:

- the section spine cannot be stated consistently
- the requested claim lacks supporting evidence
- a revision changes a claim, caveat, or scope boundary outside the contract
- the latest author-approved version cannot be identified
- old assumptions, duplicated explanations, or conflicting requirements indicate version contamination

### Required Escalation Check

Before editing again:

1. Consolidate the currently valid requirements into one brief.
2. Compare that brief with the spine card, evidence boundaries, current contract, and latest author-approved version.
3. Classify the failure as one primary category:
   - **underspecified or conflicting intent** — the target, audience, venue, constraint, or acceptance condition is missing or inconsistent, or the feedback is evaluative but not operational, such as “weak”, “unclear”, or “still not right” without a concrete change target
   - **local execution failure** — the contract is clear, but the edit did not implement it correctly
   - **structural mismatch** — the problem affects the section purpose, research question, gap, contribution, evidence chain, or manuscript structure
   - **evidence gap** — the requested claim is not supported by the available sources, data, experiments, or files
   - **version contamination** — accumulated patches mix incompatible assumptions, duplicate reasoning, or obscure which prose the author approved
4. Classify the writing scope:
   - **local patch** — wording or presentation changes that preserve the spine, claims, evidence, and adjacent-section relationships
   - **section-level restructure** — changes confined to one section without changing the research question, contribution, or evidence chain
   - **full reframing** — changes to the title, abstract, research question, gap, contribution, methods-results alignment, evidence chain, or discussion framing
5. Recommend the smallest valid next action and wait for author approval.

Use these default actions:

- For a local execution failure, create a corrected local contract.
- For underspecified or conflicting intent, ask for the missing decision before editing.
- For a structural mismatch, propose a section-level restructure or full reframing plan before editing.
- For an evidence gap, narrow, qualify, or remove the unsupported claim unless the author supplies more evidence.
- For version contamination, restore or copy the latest author-approved version, then apply a consolidated contract. Create a separate branch or manuscript version only when the approved scope requires structural work.

For full reframing, hand off a brief that states the target venue, research question, gap, core claim, available evidence, claims that must not be made, and proposed new structure. Do not rewrite the manuscript until the author approves that brief.

Return the escalation check in this form:

```text
## Revision Escalation Check

Revision issue:
Contract:
Unsuccessful attempts:
Trigger contracts:
Primary category:
Writing scope:
Why the revisions did not converge:
Valid requirements:
Missing or conflicting information:
Latest author-approved version:
Recommended next action:
Author decision required:
```

## Output Patterns

### Audit Only

Return:

- current spine diagnosis
- likely drift risks
- control gaps
- recommended edit contracts
- blocked items needing author decision

### Pre-Edit Contract

Return:

```text
## Edit Contract

Unit:
Spine sentence:
Allowed changes:
Forbidden changes:
Adjacent context to check:
Acceptance checks:
Human approval required:
Proceed only after approval:
```

### Post-Edit Drift Audit

Return:

```text
## Drift Audit

Contract:
Changed claims:
Changed boundaries:
New unsupported claims:
Missed adjacent updates:
Decision:
Human review required:
Recommended next action:
```

## Stop Conditions

Stop and ask for author direction if:

- the section spine cannot be stated clearly
- the requested edit would broaden a claim without evidence
- a local edit requires adjacent updates outside the approved scope
- the user asks for a full-chapter rewrite without a spine map
- previous AI edits cannot be distinguished from author-approved text
- the edit would remove caveats, limitations, or uncertainty language without explicit approval
