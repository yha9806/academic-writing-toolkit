# P1 — Guards and Headless Profile

- **Status:** In progress (session 1 of the 2-session budget)
- **Parent spec:** `2026-08-16-awt-dsh-app-v0.1-design.md` §7, §14
- **Approved constraints:** pure-TypeScript guards; headless-first.

## dsh seam facts (recon 2026-08-16, upstream `47f9438`)

- `ctx.tools.guard(g)` registers a **monotonic** synchronous guard evaluated
  after every `tools/pre-execute` listener: returning a string denies the
  call; `undefined` leaves it unchanged; no guard can force-allow. This is
  the fail-closed seam AWT uses — a denial cannot be reordered away.
- Built-in fs tools and their arguments: `write` (`file_path`, `content`),
  `edit` (`file_path`, `old_string`, `new_string`, `replace_all`), `read`
  (`file_path`, `offset`, `limit`).
- **Discovery that amends parent §7:** dsh core `read` is UTF-8 text only —
  there is no PDF page reading in core. The 15-page/90-page budgets can only
  be enforced once the awt profile decides its PDF ingestion tool. Those two
  rows move to P1 session 2 alongside that decision; until then they remain
  Advisory everywhere and are documented as such.

## P1 deliverables

| Item | Session | State |
| --- | --- | --- |
| Decision kernel (`guards/src/decisions.ts`): pure, dependency-injected, unit-tested red-first | 1 | this change |
| dsh plugin adapter (`guards/src/dsh-plugin.ts`) wiring the kernel into `ctx.tools.guard` | 1 | this change (structural types; not yet mounted) |
| `awt-headless` profile package + live e2e (deny observed against a real dsh run with a scripted provider) | 2 | pending |
| PDF ingestion decision + page-budget guard | 2 | pending |
| `verify-refs` parser swap to `bibtexparser` | 2 | pending |

## Enforced rows implemented in session 1

Typed denials are content-free: code, rule, offending path, and remedy only.

1. **`NOTES_MISSING`** — a `write`/`edit` whose target is under `chapters/`
   and whose *inserted text* contains author–year citations must have each
   cited source matched by a lint-conforming notes file (matched on first
   author surname + year from the `**Source**:` line). Bias note: the
   citation extractor is deliberately conservative (capitalised-name
   parenthetical and narrative forms only) — for a blocking guard, a missed
   citation fails open per citation; a false positive would block real
   writing. The opposite bias from an audit report, chosen on purpose.
2. **`QUOTE_SPAN_MODIFIED`** — an `edit`/`write` on an existing chapter file
   must leave every quotation span (`"…"` / `“…”`, up to 500 chars) that
   existed in the previous content byte-identical in the resulting content.
   Deleting an entire span together with its citation sentence is allowed
   (removal is visible); silently altering text inside a span is not.
3. **`CONTRACT_SCOPE`** — while a contract in `contracts/*.md` is active
   (its `## Attempts` has an unchecked box), chapter writes must fall under
   its `May change:` path prefixes and never under `Must not change:`
   prefixes. Scope entries are path prefixes relative to the project root,
   comma-separated — deliberately not globs.

## Session-1 gates

- Every denial code has a red-first unit test (violating call denied with
  that exact code; conforming call passes) — in `guards/tests/`.
- Kernel has zero dsh imports; the adapter compiles against structural
  interfaces only, so upstream preview churn cannot break the test suite.
- CI runs the suite via the existing guards step.

## Session-2 gates (P1 close)

- `dsh --profile awt-headless` boots with the plugin mounted; an e2e run
  attempts each forbidden operation against a scripted provider and the
  typed denial is observed in the session log. Until this gate is green,
  README and skills must keep describing these rules as *not yet enforced
  in any shipped runtime* (Claude Code surface remains advisory).
