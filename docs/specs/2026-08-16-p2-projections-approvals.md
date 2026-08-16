# P2 — Projections, Approvals, Scaffold

- **Status:** Approved to start (author: "开工 P2" after ecosystem report); session 1 pending
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
