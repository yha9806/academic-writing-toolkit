---
name: edit-contract
description: Create a spine card and edit contract before a substantive chapter edit, and escalate after three failed revision attempts on the same issue.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /edit-contract — Bounded Chapter Edits

One file per contract at `contracts/{chapter}-{slug}.md`. No other ledgers.

## When to use

Before a substantive edit (rewriting more than one paragraph, changing what a
section claims, restructuring). Not for typo fixes or single-sentence edits.

## Contract file format

```markdown
# Edit Contract: {chapter} — {short goal}

## Spine card
- Section role: {what this section must keep doing in the argument}
- Core claim (must not broaden): {one sentence}
- Sources in scope: {list; their roles — support / background / challenge}
- Forbidden: {claims that must NOT appear; scope that must NOT leak in}

## Scope
- May change: {files/sections}
- Must not change: {adjacent sections, quoted spans, other chapters}

## Attempts
- [ ] Attempt 1: {date} — {outcome: accepted / revise / rejected, one line why}
- [ ] Attempt 2: …
- [ ] Attempt 3: …
```

## Workflow

1. Draft the contract from the user's request and the current section; show
   it; the user approves or amends it **in conversation** before any edit.
2. Make the edit within Scope. After the edit, restate in one short table:
   what changed, whether the core claim broadened (quote before/after if it
   did), and whether anything Forbidden appeared.
3. Record the attempt line. The user's accept/revise/reject decision in
   conversation is the gate — the file records it, it does not grant it.

## Three-strike escalation

After **three recorded failed attempts on the same contract** (not before —
a single "this is unclear" is feedback, not an escalation trigger): stop
patching. Diagnose which it is — underspecified request, wrong scope (needs
section-level restructure, not a patch), evidence gap (the claim wants
support the sources cannot give), or drifted spine — and offer: (a) rewrite
the contract, (b) escalate scope deliberately, (c) drop the change. Do not
produce a fourth patch under the old contract.

## Constraints

1. One contract file per edit goal; append-only Attempts.
2. Never edit outside Scope; never touch quoted spans.
3. In P0 this discipline is advisory prose; the P1 guard enforces Scope and
   the attempt count from the session log. Do not describe it as enforced.
4. No emoji. British English.

## Project-level intent card (optional, Advisory)

Per-edit spine cards sit under a project-level intent. If the project keeps
one, it is `00_AUTHOR_INTENT.md` from the lightweight author-control profile
in `references/author-control/` (scaffold with
`python3 scripts/scaffold-author-control.py <project_root>`, check structure
with `python3 scripts/check-author-control.py <project_root> --strict`). A
contract's core claim must not broaden beyond that card. The card's approval
field is a record the author keeps, not an enforcement: nothing on this
surface gates on it, and in the AWT app approvals exist only as harness
events.
