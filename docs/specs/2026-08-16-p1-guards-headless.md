# P1 — Guards and Headless Profile

- **Status:** CLOSED 2026-08-16 — all gates green, including the live dsh e2e (author-granted closing session)
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
| `awt-headless` profile package + live e2e (deny observed against a real dsh run with a scripted provider) | 3 | **done** — e2e/ runs the published `@deepseek-ai/dsh@0.1.0-rc.6` launcher with an e2e profile mounting `guards/dist/dsh-plugin.js`; all four required scenarios plus the PAGE_RANGE_EXCEEDED stretch produced their typed outcome in the persisted session store, independently re-run (`node e2e/run-e2e.mjs`, exit 0). User-facing profile naming/packaging ships with P2 `awt init` |
| PDF ingestion decision + page-budget guard | 2 | done — decision: profile bundles a pdftotext-backed `read_pdf` tool (`file_path`, `first_page`, `last_page`); kernel `decidePdfRead`/`foldPdfRead` enforce 15/90 with red-first tests |
| `verify-refs` parser swap to `bibtexparser` | 2 | done — **amended**: replaced by a stdlib balanced-brace parser instead. Rationale: `bibtexparser` failed to build in the pinned environment; a dependency the gate cannot install would make the gate non-deterministic, and the two measured defects (unbraced numeric fields reported missing; nested-brace truncation) are fixed directly with regression tests T125/T126. The amendment keeps the self-contained-tools principle the toolchain already enforces |

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

## Closing status (end of session 2)

Delivered: three chapter-write guards + page budgets in the pure kernel
(24/24 red-first tests), dsh adapter on the monotonic guard seam, verify-refs
parser rebuilt (suite now 123 tests), PDF ingestion decision recorded.

Open: the live `awt-headless` e2e gate. Per parent spec §12's standing rule,
the phase stops at its budget instead of expanding. Until that gate is green,
every surface must keep describing these rules as not yet enforced in any
shipped runtime. Author decision required: (a) grant P1 one closing session
for profile packaging + live e2e, or (b) proceed to P2 and fold the e2e into
P2's self-approval-attack gate.

## P1 close-out (closing session, 2026-08-16)

Live-gate evidence: `e2e/run-e2e.mjs` boots the real published launcher per
scenario; a scripted LLM adapter drives the full loop (assistant tool call →
`tools/pre-execute` → monotonic guards → durable `tool/result`). All five
scenarios green including the negative control (conforming citation written,
zero denials, file on disk). Re-run independently after the build agent's
report — the gate is reproducible, not narrated.

Discoveries that justify the live gate's existence:

1. **The session-1 adapter was a silent no-op against rc.6**: `ToolExecution`
   carries parsed arguments as `arguments`, not the structurally assumed
   `args`; every guard read `{}` and allowed everything. Unit tests could not
   catch this — only the live seam could. This is the drift class the gate
   exists for, caught on its first run.
2. rc.6 loads profile-local plugins from relative path names in
   `cordis.patch.yml` insert rows; bare names resolve via the profile
   node_modules farm. Recorded in `e2e/README.md`.
3. Guard denials materialize as durable `tool/result` `Error: <reason>` with
   `isError: true` — typed codes are greppable verbatim in the session store.
4. The default session store is multi-frame zstd; the e2e profile pins
   `compression: none` for assertability.
5. Auxiliary LLM traffic (session titling) hits the default route; scripted
   adapters must answer non-agent purposes or the run hangs.

Remaining honesty boundary, unchanged until P2: the enforcement exists in the
e2e profile, not yet in a user-installable `awt-headless` profile; skills and
README keep the "not yet enforced in a shipped runtime" wording until `awt
init` ships one.
