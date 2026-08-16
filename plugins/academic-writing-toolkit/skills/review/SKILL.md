---
name: review
description: Review a manuscript or chapter as an external reviewer, or run an own-work self-review in a fresh-context clean room, producing anchored findings and a recommendation.
allowed-tools: Read, Glob, Grep, Agent
---

# /review — Manuscript Review

## Modes

- **external** (default): review another author's work as submitted.
- **own-work**: review the user's own draft. The clean room is real, not
  declared: spawn ONE fresh-context subagent whose prompt contains only the
  manuscript text (and explicitly listed evidence files), and relay its
  findings. Never present a same-session read-through as a clean-room review —
  the drafting conversation is context contamination by definition.

## Evidence boundary

Judge the manuscript **as submitted**. Do not use prior chat memory, unstated
author intentions, or model background knowledge as evidence for or against a
claim. If a claim cannot be assessed from the manuscript and its cited
sources, say so — that is itself a finding.

## Findings format

Every finding is anchored (section/paragraph or quoted span) and typed:

| # | Type | Anchor | Finding | Severity |
|---|------|--------|---------|----------|

Types: `claim-exceeds-evidence` | `gap-contribution-mismatch` | `method` |
`structure` | `clarity` | `citation`. Split findings three ways: defects that
block the recommendation, improvements that would strengthen it, and
questions the author must answer. Consult `references/argument-checklist.md`
for the interrogation checklist and examiner-attack pre-mortem when the
review targets argument quality.

## Recommendation vocabulary

Exactly one of: `accept` | `minor_revision` | `major_revision` |
`reject_resubmit` | `reject` | `no_recommendation`.

## Stop conditions

Stop and report a blocker instead of continuing if asked to: fabricate
reviewer consensus, citation support, or experimental findings; review text
that is not available as submitted; or convert this review into a rewrite —
/review never edits the manuscript.

## Constraints

1. Never rewrite or patch the manuscript; output findings only.
2. No emoji. British English.
3. Own-work mode without a subagent available: state plainly that the review
   is NOT clean-room and label the output accordingly.
