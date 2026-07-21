---
name: revision-escalation
description: Stop repeated failed writing, coding, manuscript, rebuttal, or restructuring revisions when the same issue has gone through 3+ unsatisfactory edits, vague feedback such as still wrong/weird/unclear/weak/越改越乱, version contamination, or possible gap/claim/evidence/venue-fit drift.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
---

# /revision-escalation - 3-Strike Revision Control

## Purpose

Prevent repeated local patches from making a draft or code path more inconsistent. Use this when the issue may no longer be wording or implementation detail, but specification, structure, evidence, or version-control drift.

## Trigger Words

This skill activates on: `revision escalation`, `3-strike`, `three strikes`, `stop and diagnose`, `still wrong`, `still weird`, `unclear`, `weak`, `越改越乱`, `还是不对`, `还是怪`, `不够清楚`, `逻辑还是混乱`, `/revision-escalation`.

## Core Rule

If the same issue remains unresolved after 3 revision attempts, treat it as a specification or structure problem before treating it as another local editing task.

Do not make a fourth patch immediately.

Count an attempt only when all of the following are true:

- it belongs to the same revision issue;
- its edit contract was actually applied;
- its drift audit is resolved; and
- that resolved audit records a failed acceptance outcome, whether the action was
  `revise` or `rollback`.

Do not count proposed, abandoned, unapplied, pending-review, or unresolved
contracts. List the exact counted contract IDs so the threshold is auditable.

## Revision Escalation Check

Before editing again, classify the problem:

| Category | Meaning | Next action |
| --- | --- | --- |
| Underspecified request | Target, constraint, audience, venue, or expected output is missing. | Ask for a concrete target before editing. |
| Ambiguous feedback | Feedback is evaluative but not operational: "weird", "weak", "unclear", "not good enough". | Ask what should change. |
| Local execution problem | The goal is clear, but the previous patch implemented it incorrectly. | Make one small targeted patch. |
| Structural mismatch | The issue affects the research question, gap, contribution, evidence chain, section structure, module boundary, or venue framing. | Propose a restructure plan before editing. |
| Evidence gap | The desired claim is unsupported by available data, experiments, citations, or files. | Downgrade the claim or request evidence. |
| Version contamination | Repeated patches have mixed old assumptions with new requirements, causing inconsistency, duplication, or bloat. | Recommend a new version, branch, or consolidated brief. |

## Required Response

When triggered, respond in this structure before any patch:

```md
I should pause before making another patch.

This issue has already gone through several revision rounds and may not be a local wording or implementation problem anymore.

Current diagnosis:

* Category:
* Why:
* What is missing or conflicting:
* Recommended next action:

Options:
A. Clarify the concrete target and continue a local patch.
B. Consolidate all current requirements into a single brief, then retry.
C. Create a new version or branch and restructure the section/module.
D. Reframe the paper/project from the research question, gap, and evidence chain.
```

When the user supplies issue IDs, contract IDs, audit outcomes, an approved
version, or an acceptance condition, replace the generic response with this
structured record:

```md
## Revision Escalation Check

- Issue:
- Trigger contracts:
- Counted failed attempts:
- Primary category:
- Secondary risk:
- Revision scope:
- Latest author-approved version:
- Acceptance condition:
- Missing or conflicting evidence:
- Safe next action:
- Author decision required: yes
```

Preserve every supplied identifier and status exactly. If a field was not
provided, write `unknown`; do not infer it. After three counted failures, do not
offer an immediate targeted rewrite as an option. The safe routes are to narrow
the claim, obtain the missing evidence, approve a bounded reframe, or return to
the latest author-approved version and issue a new controlled contract.

## Academic Writing Rule

Classify manuscript work before editing:

- Local patch: wording, grammar, citation format, figure caption, table formatting, or one paragraph.
- Section-level restructure: one section changes, but the research question, contribution, and evidence chain stay stable.
- Full reframing: title, abstract, introduction, research question, gap, contribution, methods-results alignment, discussion, or venue framing changes.

For full reframing, do not directly rewrite the manuscript. First produce a reframing brief with target venue, research question, gap, core claim, available evidence, claims that must not be made, and proposed new structure.

An unsupported universal, causal, clinical, cross-lingual, cross-population, or
cross-benchmark headline is primarily an **Evidence gap** when the requested
scope exceeds the available evidence. If repairing it changes the abstract,
title, main contribution, or paper-wide evidence licence, classify the revision
scope as **Full reframing** even when the user asks for a one-sentence patch.
Record version contamination only as a secondary risk unless mixed versions or
conflicting requirements are actually evidenced.

## Red Flags

Stop and diagnose when thinking:

- "One more patch should fix it."
- "The user is still dissatisfied, but I can just rewrite harder."
- "The wording is awkward" while the evidence chain or contribution boundary is unstable.
- "The current version is messy, but I can keep accumulating edits."

Never continue accumulating edits on a structurally inconsistent manuscript, rebuttal, or code path.
