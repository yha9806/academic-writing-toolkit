---
name: verify-refs
description: Use when checking BibTeX reference records for missing fields, malformed identifiers, duplicate keys, or metadata mismatches before submission.
allowed-tools: Read, Glob, Bash, WebFetch
---

# /verify-refs — Reference Authenticity Check

## Purpose

Check reference records for missing required fields, duplicate keys, malformed DOI values, malformed arXiv identifiers, and invalid URLs. The default mode is offline and deterministic.

## Trigger Words

This skill activates on: `verify refs`, `verify references`, `reference check`, `/verify-refs`.

## Workflow

1. Identify the target Markdown or `.bib` file. If the user does not specify one, ask.
2. Resolve the bundled helper at `scripts/verify-refs.py` relative to this `SKILL.md`, then run it from the project root:
   `python3 {skill_dir}/scripts/verify-refs.py --bib {path} --json`
3. Report issues by entry key and severity.
4. For explicit metadata verification, run:
   `python3 {skill_dir}/scripts/verify-refs.py --bib {path} --json --online`
5. Use CrossRef for DOI metadata, Semantic Scholar as a secondary metadata source, and arXiv for preprint identifiers. Online checks must be explicit because they depend on network availability.
6. In tests or offline review, use `--metadata-dir {dir}` to read CrossRef JSON, Semantic Scholar JSON, and arXiv Atom fixtures instead of live network calls.

## Constraints

1. Do not import project-specific reference rules from other repositories.
2. Do not auto-fix reference records without user approval.
3. Keep output plain Markdown with no emoji.
4. Treat CrossRef, Semantic Scholar, and arXiv as verification sources, not as citation style authorities.
