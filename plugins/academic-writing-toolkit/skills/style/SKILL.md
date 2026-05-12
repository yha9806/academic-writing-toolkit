---
name: style
description: Check thesis text for British English consistency and safe mechanical spelling fixes.
allowed-tools: Read, Glob, Bash, Edit
---

# /style — British English Check

## Purpose

Audit chapter drafts and reading notes for common US spellings when the project requires British English.

## Trigger Words

This skill activates on: `style`, `British English`, `spelling check`, `/style`.

## Workflow

1. Resolve the bundled helper at `scripts/audit-british-english.py` relative to this `SKILL.md`, then run it from the project root:
   `python3 {skill_dir}/scripts/audit-british-english.py --base-dir . --json`
2. Report every issue by file, line, current spelling, and recommended replacement.
3. If the user asks for safe fixes, run:
   `python3 {skill_dir}/scripts/audit-british-english.py --base-dir . --fix`
4. Re-run the audit and report the remaining issue count.

## Constraints

1. Only apply mechanical spelling replacements produced by the script.
2. Do not rewrite style, tone, argument, or citations as part of this skill.
3. Use British English in any inserted prose.
4. No emoji.
