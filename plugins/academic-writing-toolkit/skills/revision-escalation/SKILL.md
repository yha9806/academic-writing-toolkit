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

Repeated feedback that the manuscript is becoming more abstract, no longer
states who it helps, or contains individually correct sentences without a
recognisable paper spine is a structural signal even when fewer than three
formal edit contracts have failed. Pause and compare the current draft with
the author-intent and argument baselines.

## Revision Escalation Check

Before editing again, classify the problem:

| Category | Meaning | Next action |
| --- | --- | --- |
| Underspecified request | Target, constraint, audience, venue, or expected output is missing. | Ask for a concrete target before editing. |
| Ambiguous feedback | Feedback is evaluative but not operational: "weird", "weak", "unclear", "not good enough". | Ask what should change. |
| Local execution problem | The goal is clear, but the previous patch implemented it incorrectly. | Make one small targeted patch. |
| Structural mismatch | The issue affects the real-world problem, intended use, research object, research question, primary experiment, gap, contribution, evidence chain, section structure, module boundary, or venue framing. | Propose a restructure plan before editing. |
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

## Academic Writing Rule

Classify manuscript work before editing:

- Local patch: wording, grammar, citation format, figure caption, table formatting, or one paragraph.
- Section-level restructure: one section changes, but the research question, contribution, and evidence chain stay stable.
- Full reframing: title, abstract, introduction, research question, gap, contribution, methods-results alignment, discussion, or venue framing changes.

For full reframing, do not directly rewrite the manuscript. First produce an
old-versus-proposed reframing brief with target venue, real-world problem,
intended use, research object, research question, primary experiment,
supporting analyses, gap, contribution order, headline claim, evidence
boundary, evidence baseline, argument baseline, available evidence, claims
that must not be made, and proposed new structure. The author must approve the
new spine before editing resumes.

## Red Flags

Stop and diagnose when thinking:

- "One more patch should fix it."
- "The user is still dissatisfied, but I can just rewrite harder."
- "The wording is awkward" while the evidence chain or contribution boundary is unstable.
- "The current version is messy, but I can keep accumulating edits."

Never continue accumulating edits on a structurally inconsistent manuscript, rebuttal, or code path.
