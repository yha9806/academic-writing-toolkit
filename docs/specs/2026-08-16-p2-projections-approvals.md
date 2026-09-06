# P2 — Projections, Approvals, Scaffold

- **Status:** Session 1 complete (items 1, 3, 5 landed; 65/65 guard tests, e2e smoke green, independently re-verified). Session 2: harness pin DECIDED (below), `awt init`/`awt verify` LANDED (scaffold/awt.mjs; manifest + refusal gates), ask-seam approvals LANDED (item 2: escalation `ask` via dsh-user-approval, self-approval attack re-run and blocked; 74/74, live e2e green). Item 6 docs reshape LANDED (guards/README.md enforcement-semantics + "what this does not do"; parent §7 table reshaped as-implemented). **Session 2 complete**; the sole open item is the structured-fact writer, BLOCKED on a published ignorable-append harness (tripwire armed).
- **Arming condition (recorded honestly):** the escalation gate arms from the
  revision fold, so it covers contracts that entered through logged writes —
  the real lifecycle. A contract file placed on disk outside dsh never arms
  the gate (the §"projections" derived-channel gap; closes with the fact
  writer when the pin lifts). Scope checks still enforce from disk either way.
- **Parent spec:** `2026-08-16-awt-dsh-app-v0.1-design.md` §8, §14
- **Inputs:** P1 close-out discoveries; `docs/research/2026-08-16-ecosystem-practices.md`
  adoptions #1-#4, #6, #7 (this spec instantiates them; #5/#8 land in P3).

## Scope

1. **Session-log projections replace plugin state** (eco #3, background-agents
   discipline): page-budget counter, per-contract revision-attempt counter,
   and notes integration-status lifecycle each become a ProjectionDefinition
   folding the append-only session log — `stateVersion`, zod wire schema,
   custom guard-fact events stamped `ignorable: true`, provenance-tagged rows.
   One `guards/src/vocabulary.ts` owns denial codes and fact shapes for guard,
   reducer, and tests alike.
2. **Approvals become harness events** (eco #2): the 3-strike escalation and
   integration-plan gates return `ask` on the `tools/pre-execute` waterfall
   instead of `deny`, so dsh's approval seam records the immutable human
   interaction. No agent-writable file is ever the authority (§10.5).
3. **Guards refuse to mount inert** (eco #4): missing limits, absent notes
   root, or an unresolvable contracts source is a profile-boot FAILURE with a
   typed load error, unit-tested. Boot itself becomes a truth test.
4. **`awt init` + `awt verify`** (eco #6): `init` scaffolds a clean thesis
   workspace (chapters/, literature/reading_notes/ with template, contracts/,
   project config, `.agents/skills` links — zero toolkit-dev files, closing
   the split-identity finding); `verify` runs the ladder: typecheck → build →
   offline lint smoke → `--dump-config` contains every guard row → one
   scripted-adapter denial. All verification on scratch DSH_HOME profiles,
   never a real thesis profile.
5. **Testing uplift** (eco #1): port the P1 denial scenarios onto
   `@deepseek-ai/dsh-agent-loop-testkit` as the on-every-push deterministic
   tier; keep `e2e/run-e2e.mjs` as the subprocess smoke tier.
6. **Docs reshape** (eco #7): §7's table and each guard's README section move
   to the four-column enforcement-semantics format plus a mandatory "what
   this does not do" paragraph per guard.

## Gates

- Refold test copied from the background-agents shape: flush log → dispose
  context (simulated crash) → remount on the same persistence root → every
  projection value reconstructs from the durable log alone.
- **Self-approval attack re-run and blocked**: the efficacy review's scripted
  attack (agent edits its own approval records) is re-executed against the
  P2 surfaces; file edits must have zero effect on any gate decision because
  the authority lives in approval interactions and log folds.
- Inert-mount rejection unit tests green (one per guard).
- `awt init` produces a workspace where `awt verify` passes end-to-end; the
  workspace contains no toolkit-dev files (asserted by a manifest test).
- Testkit tier green for every denial code on a clean install.

## Non-goals (unchanged from parent)

No web UI (v0.2), no npm publication claims, no legacy deletion (P3), no
multi-user. Budget: two working sessions; §12 standing rule applies.

## Session-1 close-out discoveries (rc.6, file evidence in guards/src/vocabulary.ts)

1. `ctx.sessionProjections.register()` is externally usable on rc.6 — the
   three AWT folds register on the REAL registry; the page budget now reads a
   per-SESSION snapshot (P1's plugin counter was silently per-process — a
   discriminating two-session test now locks this in).
2. **Missing upstream seam**: rc.6 `Session.append` cannot stamp
   `ignorable: true`, and the persistence read path rejects unknown
   non-ignorable event types — switching on the structured-fact WRITER on
   rc.6 would poison session resume. The folds already consume the fact
   channel, so session 2 only needs a harness pin at or beyond upstream's
   ignorable-append commit (8c690c7) — or the model-visible user-message
   notice channel — before enabling the writer. No fold changes required.
3. `ESCALATION_REQUIRED` is deliberately absent from the vocabulary until the
   ask-seam ships — no denial code exists before its enforcement does.

## Session 2 — harness pin decision (2026-08-16, local)

**Decision: stay on published npm at exact `0.1.0-rc.6` everywhere; the
structured-fact writer remains OFF, gated on the first PUBLISHED harness
version whose `Session.append` honors `{ ignorable: true }`.**

Evidence (verified 2026-08-16 via GitHub compare API + npm registry API):

- The ignorable-append surface exists upstream only as three commits
  referenced by **no branch** (repo's sole branch is master, frozen at the
  2026-08-13 launch push): master + `9a20e17a` (feat: expose the ignorable
  envelope marker on Session.append) → `f5be34d7` (docs) → `8c690c7` (test),
  authored 2026-08-14. The PR surface of the repo is disabled; the commits
  are reachable by SHA only.
- npm has published nothing since 2026-08-13; `dist-tags.latest` still points
  at `0.0.1-rc.1` (the known latest/next trap) and `next` at `0.1.0-rc.6`.

Alternatives rejected:

1. *Pin/vendor a from-source build at `8c690c7`* — pins an unreferenced,
   rebase-vulnerable commit of a ~50-package monorepo and abandons the
   npm-exact discipline; the payoff is only an earlier writer.
2. *Model-visible user-message notice channel* — puts governance facts into
   model context, violating §7 content-free separation. Off the table, not
   deferred.

Mechanism (a seam-probe/tripwire discipline: characterize what the pinned
harness actually does, so behavior changes force re-review instead of
rotting silently), in `guards/tests/harness-pin-probe.test.ts`:

- **Tripwire**: asserts the pinned harness still *drops* the ignorable
  marker on append. The first pin bump where the marker is honored turns
  this red, forcing: enable the writer + re-run the refold gate.
- **Characterization**: asserts an unmarked unknown event type still
  *refuses* to reload (the resume-poison this decision avoids). Expected to
  keep passing after the bump — unknown-and-unmarked refusal is upstream's
  deliberate fail-closed default.

Consequences: session 2 proceeds with `awt init`/`awt verify` and the
ask-seam approvals (neither depends on the writer); projections keep folding
the derived channel with their documented gaps until the gate lifts.

## Published-package recheck — 2026-09-05

Newer launcher and session packages now exist on npm, so the historical
"nothing newer is published" observation above is no longer current.
The required append behaviour is still absent: a detached-session runtime
probe against both `@deepseek-ai/dsh-session@0.1.0-rc.6` and the published
`0.1.2-rc.1` appended a content-free `awt-guards/fact` with
`{ ignorable: true }`; the returned event omitted the marker in both cases.
The rc.7 and rc.8 published source was also inspected and still omitted it.

Use `node scripts/probe-session-append.mjs` for the installed pin, or pass
`--package <installed-dsh-session-directory> --out <report.json>` for an
isolated candidate installation. The report records the package version
and entry-file SHA-256. It never downloads packages or changes the pin.
The tested latest entry SHA-256 was
`be25b05ffd1403908796935ef11a61d4c002f7ff3d12f83ef82a8c9976984342`.

Issue #37 therefore remains blocked. Do not enable the writer or equate a
new version number with compatibility. A future marker-preserving result
is a candidate for the writer implementation and refold/live gates, not
automatic permission to ship. No dependency was upgraded by this recheck.
