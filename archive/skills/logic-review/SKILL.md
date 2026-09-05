---
name: logic-review
description: Review stable chapter or manuscript drafts for paragraph flow, transitions, argument continuity, and repeated rhetorical functions before editing. Use after the author-approved spine is stable; route structural drift back to thesis-control.
allowed-tools: Read, Glob, Bash, Edit
---

# /logic-review — Paragraph Logic Review

## Purpose

Find paragraphs that may need a topic sentence, a clearer transition, merging,
re-ordering, or removal of duplicated argumentative work. The deterministic
script flags mechanical candidates; the agent separately reviews rhetorical
functions without redefining the manuscript spine.

## Trigger Words

This skill activates on: `logic review`, `flow check`, `paragraph logic`, `/logic-review`.

## Workflow

1. Run:
   `python3 scripts/audit-logic.py --base-dir . --json`
2. Confirm that the research object, core question, intended use, primary
   experiment, headline claim, and evidence boundary are stable under the
   active `/thesis-control` contract. If they are not, stop the language pass
   and route the issue to drift control or revision escalation.
3. Read the flagged paragraphs and nearby context.
4. Label each relevant sentence or paragraph by its main function: `problem`,
   `gap`, `method`, `evidence`, `interpretation`, `boundary`, or `transition`.
5. Flag duplicated functions and monotonous sequences, especially repeated
   `evidence -> disclaimer` endings. Prefer deleting or consolidating repeated
   argumentative work over generating synonymous wording.
6. Check boundary placement. Scope must remain aligned across the paper, but
   full limitation prose need not be repeated after every result. Preserve
   essential local qualifiers and concentrate fuller study-boundary language
   in the abstract ending, Methods boundary, Discussion/Limitations, and
   conclusion when appropriate.
7. Present a numbered review table with location, function, issue type, why it
   matters, and a proposed edit.
8. Wait for user approval before editing chapter files.
9. Apply only approved edits, then re-run the audit.

## Constraints

1. Never auto-fix chapter logic without user approval.
2. Preserve the author's argument and section structure.
3. Keep edits local to the flagged paragraph unless the user approves a broader rewrite.
4. Do not use a logic or style pass to repair an unstable research question,
   evidence chain, application purpose, or contribution order.
5. No emoji.
