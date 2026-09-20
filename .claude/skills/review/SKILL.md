---
name: review
description: Review a manuscript or chapter as an external reviewer, or run an own-work self-review in a fresh-context clean room, producing anchored findings and a recommendation.
allowed-tools: Read, Glob, Grep, Agent, Bash
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

Write findings to a TSV the author can check, not prose they must take on
trust. A declaration of what was read, then one row per finding:

```
# reviewed: chapters/ch2_background.md, chapters/ch3_conceptual_framework.md
location	source	problem
chapters/ch2_background.md:142	literature/reading_notes/Foo_NOTES.md	The sentence attributes a claim the note does not contain.
```

- **location** is `file:line`, never a section name or a quoted span. A section
  name cannot be told apart from a plausible one; a line number resolves or it
  does not.
- **source** is the archived original or evidence file the finding rests on, or
  `-` when the finding is about the text itself (structure, clarity, an
  internal contradiction).
- **problem** is one sentence. Type and severity go in that sentence if they
  matter; a separate taxonomy column was never read.

**Run the checker before handing the report over:**

```
python3 .claude/skills/review/scripts/audit-review-findings.py \
  --base-dir <manuscript> --findings <findings.tsv>
```

It resolves every anchor, rejects a finding about a file the review never
declared it read, and exits 2 when the report does not say what it read — a
review with no declaration cannot be told apart from one that examined nothing.
It does **not** judge whether a finding is right. Split the rows three ways in
the accompanying note: defects that block the recommendation, improvements that
would strengthen it, and questions the author must answer. Consult
`references/argument-checklist.md` (repository root) for the interrogation
checklist and examiner-attack pre-mortem when the review targets argument
quality.

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
2. Every finding resolves: run the checker and report its exit code alongside
   the findings. An unresolved anchor is withdrawn, not explained.
3. No emoji. British English.
4. Own-work mode without a subagent available: state plainly that the review
   is NOT clean-room and label the output accordingly.
