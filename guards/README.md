# @awt/guards

Deterministic enforcement for the AWT thesis workflow, mounted as an
ordinary dsh plugin on public seams (`ctx.tools.guard`, `tools/pre-execute`,
`ctx.sessionProjections`). Pure policy lives in `src/decisions.ts`, typed
codes and wire shapes in `src/vocabulary.ts`, session-log folds in
`src/projections.ts`; `src/dsh-plugin.ts` only adapts the seams. No dsh
source is patched, and no dsh package is imported by the shipped plugin —
it compiles against structural interfaces and is exercised against the real
pinned harness by the testkit tier and the live e2e.

## Enforcement semantics

| Constraint | Seam | What is counted / diffed | Typed outcome |
| --- | --- | --- | --- |
| No chapter write may cite a source without a conforming notes file | `ctx.tools.guard` | author-year citations extracted from the written/inserted text, matched against lint-conforming `literature/reading_notes/*_NOTES.md` | deny `NOTES_MISSING` |
| Quoted text in existing chapters is immutable | `ctx.tools.guard` | quotation-delimited spans of the target file before vs after the proposed write/edit | deny `QUOTE_SPAN_MODIFIED` |
| Chapter writes stay inside the active edit contract's scope | `ctx.tools.guard` | target path against the on-disk active contract's `May change:` / `Must not change:` lists | deny `CONTRACT_SCOPE` |
| ≤ 15 pages per `read_pdf` invocation | `ctx.tools.guard` | `first_page`..`last_page` of the requested call | deny `PAGE_RANGE_EXCEEDED` |
| ≤ 90 pages per session | `ctx.tools.guard` | successful `read_pdf` results folded from the append-only session log (page-budget projection) | deny `PAGE_BUDGET_EXCEEDED` |
| After 3 typed-denial attempts under a contract, further in-scope chapter writes need the author | `tools/pre-execute` waterfall | per-contract typed-denial attempts folded from the session log (revision-attempts projection) | `ask` with reason `ESCALATION_REQUIRED`, resolved by dsh-user-approval (`allowed-once` / `rejected` / fail-closed `unavailable`) |
| An export runs only when every cited source resolves | `ctx.tools.guard` on `export_docx` | every author-year citation under `chapters/**` against lint-conforming notes files; when a `.bib` exists, entries ↔ citations by first-author surname + year, both directions | deny `EXPORT_SOURCES_UNRESOLVED` |
| A guard that would enforce nothing must not mount | plugin `apply()` (profile boot) | config limits, notes root, contracts source | throw `GuardConfigError` (`PAGE_BUDGET_INERT`, `NOTES_ROOT_MISSING`, `CONTRACTS_SOURCE_UNRESOLVABLE`) |

Denial reasons are content-free: operation, rule, observed value, limit, and
contract identity — never prompt or manuscript text. Governance counters are
projections folded from the session log (`stateVersion` + refold gate);
author approvals exist only as `approval/asked` / `approval/decided` harness
events. No agent-writable file is ever an authority.

## What this does not do

- **Any guard**: operations performed outside dsh tool calls — another
  editor, a shell, a git command — never reach these seams. The guards
  enforce the harness channel; they are not filesystem sandboxing, and tool
  visibility is not a security boundary (upstream's own non-goal).
- **Notes guard**: citation extraction is deliberately conservative — only
  unambiguous author-year forms match, so a missed citation fails open per
  citation. A lint-conforming notes file proves shape, not reading quality.
- **Quote guard**: protects quotation spans in existing chapter files during
  logged writes/edits only; it cannot restore a file rewritten outside dsh,
  and deleting a whole span visibly is allowed by design.
- **Contract-scope guard**: scope comes from the on-disk active contract at
  decision time. Contract lifecycle changes through logged writes are
  legitimate management, not bypass; a contract file placed or edited
  outside dsh still scopes writes but never arms the escalation fold.
- **Page budget**: counts successful logged `read_pdf` results. It cannot
  count reading done outside dsh, and it does not estimate tokens or cost.
- **Escalation ask**: arms only from the session-log fold (contracts that
  entered through logged writes — the derived-channel gap is recorded in the
  P2 spec until the ignorable-append harness pin lifts). Approval requests
  carry the tool name and reason, never call arguments; grants are
  `allowed-once` — nothing persists past the one asked call. A blocked ask
  folds as a `failed` attempt, never as a fourth strike.
- **Export gate**: gates the registered `export_docx` tool only — a manual
  pandoc run is outside dsh and outside every guard. Bibliography matching is
  first-author surname + year (the notes convention): it cannot tell whether
  an entry is the *right* source, and a citation naming only a second author
  will read as unresolved. Presence, never correctness.
- **Projections**: fold this plugin's vocabulary and harness-known events;
  facts from foreign producers are counted as `unrecognizedFacts`, never
  silently folded.

## Tests

`npm test` runs four tiers, all keyless and deterministic: pure kernel and
vocabulary units; testkit integration booting the real rc.6 agent loop
(denial codes, ask-seam scenarios including the self-approval attack, the
crash/remount refold gate); harness-pin seam probes (the ignorable-append
tripwire and the reload-refusal characterization); and scaffold manifest
gates for `awt init`. The live subprocess proof is `e2e/run-e2e.mjs` against
the real published launcher.
