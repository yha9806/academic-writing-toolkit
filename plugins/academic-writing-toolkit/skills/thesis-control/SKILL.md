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

Run the optional validator when Python is available:

```bash
python {skill_dir}/scripts/check_thesis_control.py <project_root> --strict
```

The validator checks packet structure and gate consistency. It does not judge scholarly truth.

To create a draft packet from a real Markdown unit before editing prose:

```bash
python {skill_dir}/scripts/scaffold_thesis_control.py <project_root> \
  --source chapters/ch1_introduction.md \
  --start-line 71 \
  --end-line 104 \
  --copy-source
```

The scaffold writes `human_approved=false`, `status=draft`, and
`AUTHOR_REVIEW_REQUIRED` fields. Replace those fields with concrete author
judgement before applying a substantive edit.

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

### 5. Record Human Gate Outcome

The author decides whether to accept, partially accept, revise, or rollback. Do not mark a high-risk edit as accepted without explicit human approval.

## Revision Escalation Rule

Treat three unsuccessful attempts on the same edit contract as an operational escalation threshold, not as evidence that every task fails after three turns. Count an attempt when its drift decision is `revise` or `rollback`, or when the author rejects the result against the same contract. Clarifying discussion and unexecuted proposals do not count.

After three unsuccessful attempts, stop. Do not apply a fourth prose patch.

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
   - **underspecified or conflicting intent** — the target, audience, venue, constraint, or acceptance condition is missing or inconsistent
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

Return the escalation check in this form:

```text
## Revision Escalation Check

Contract:
Unsuccessful attempts:
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
