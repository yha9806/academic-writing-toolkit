---
name: edit-contract
description: Create a spine card and edit contract before a substantive chapter edit, and escalate after three failed revision attempts on the same issue.
allowed-tools: Read, Write, Edit, Glob, Grep
---

# /edit-contract — Bounded Chapter Edits

One file per contract at `contracts/{chapter}-{slug}.md`. No other ledgers.

## Running Python helpers

Choose the interpreter before running the examples. For a globally installed
copy, use the private runtime recorded by its installer. In a checkout or linked
workspace, use `AWT_PYTHON` when set, otherwise the toolkit's `.venv` (follow the
skill directory link back to the toolkit): `Scripts/python.exe` on Windows,
`bin/python` on macOS/Linux. Without that environment, check that `python`
(Windows) or `python3` (macOS/Linux) actually runs and has the helper's dependencies.
Replace the example's `python3` with that executable. In PowerShell, prefix a
quoted executable with `&`; keep commands on one line and quote file paths.

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
- May change: {chapters/ch3.md}
- Must not change: {chapters/ch2.md, chapters/ch4.md}

## Attempts
- [ ] Attempt 1: {date} — {outcome: accepted / revise / rejected, one line why}
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

1. One contract file per edit goal; append-only Attempts. Append the next
   attempt line as you make it rather than pre-writing empty ones.

   **Scope lines are paths.** `May change:` and `Must not change:` are read by
   a guard, not by a reader: comma-separated repository paths only, no prose
   around them. Write `chapters/ch3.md`, not "the opening sentence of
   chapters/ch3.md". A line the guard cannot read is refused with
   `CONTRACT_UNPARSABLE` rather than guessed at — reading it as an empty scope
   would silently ignore a contract you wrote, and reading it as a list would
   deny every chapter write including the one it exists to allow. If the real
   constraint is narrower than a file, say so in the spine card, where it is
   guidance for you, and leave the scope line at the file.

   **Retiring a contract.** A contract is active while any `- [ ] Attempt`
   line is unticked, and an active contract scopes every chapter write. Tick an
   attempt only when the **goal is complete** or abandoned — not after a single
   edit. Ticking retires the contract, and a retired contract stops constraining
   anything, including the paths it lists under `Must not change`. Leaving a
   finished contract active instead makes it scope tomorrow's work, and two
   active contracts at once are refused with `CONTRACT_AMBIGUOUS` naming both,
   because the guard cannot know which one an edit belongs to.
2. Never edit outside Scope; never touch quoted spans.
3. In the dsh app this is **enforced**: a write outside Scope is denied with
   `CONTRACT_SCOPE`, and after three typed denials under one contract the next
   in-scope chapter write asks the author (`ESCALATION_REQUIRED`), resolved
   through the harness's own approval events. As a plain Agent Skill it is
   advisory prose you follow. Say which surface you are on rather than
   asserting either; the scope comes from the active contract on disk at the
   moment of the decision.
4. No emoji. British English.

## Project-level intent card (optional, Advisory)

Per-edit spine cards sit under a project-level intent. If the project keeps
one, it is `00_AUTHOR_INTENT.md` from the lightweight author-control profile
in `.claude/skills/edit-contract/references/author-control/` (scaffold with
`python3 .claude/skills/edit-contract/scripts/scaffold-author-control.py "{project_root}"`, check structure
with `python3 .claude/skills/edit-contract/scripts/check-author-control.py "{project_root}" --strict`). A
contract's core claim must not broaden beyond that card. The card's approval
field is a record the author keeps, not an enforcement: nothing on this
surface gates on it, and in the AWT app approvals exist only as harness
events.
