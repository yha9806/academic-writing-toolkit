---
name: logic-review
description: Review chapter drafts for paragraph-level flow, transitions, and argument continuity before editing.
allowed-tools: Read, Glob, Bash, Edit
---

# /logic-review — Paragraph Logic Review

## Purpose

Find paragraphs that may need a topic sentence, a clearer transition, merging, or re-ordering. The deterministic script flags candidates; the agent explains and proposes edits.

## Trigger Words

This skill activates on: `logic review`, `flow check`, `paragraph logic`, `/logic-review`.

## Workflow

1. Run:
   `python3 scripts/audit-logic.py --base-dir . --json`
2. Read the flagged paragraphs and nearby context.
3. Present a numbered review table with location, issue type, why it matters, and a proposed edit.
4. Wait for user approval before editing chapter files.
5. Apply only approved edits, then re-run the audit.

## Constraints

1. Never auto-fix chapter logic without user approval.
2. Preserve the author's argument and section structure.
3. Keep edits local to the flagged paragraph unless the user approves a broader rewrite.
4. No emoji.
