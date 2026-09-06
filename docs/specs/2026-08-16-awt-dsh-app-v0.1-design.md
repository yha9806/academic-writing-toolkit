# AWT dsh App v0.1 Design

- **Status:** IMPLEMENTED (2026-08-16), not yet E2-verified. Author-approved
  and built through P0–P3 on branch `claude/project-evaluation-review-2ily1b`
  (PR #32): catalogue triage, guards with typed denials, session-log
  projections, harness-event approvals, `awt init`/`verify`/`install-profile`,
  the `awt-headless` and `awt-web` profiles, the E1 instrument, and the §13
  decommission. Per-phase truth lives in each phase spec's own Status header;
  those headers, not this one, are the working state source.
  **Evidence: E0 gates plus a bounded local E1 pilot** (original deterministic gates green in CI —
  guards 84/84, regression 120/120, live headless denial table, credential
  probe, pack-and-install smoke). The [2026-09-05 three-source local E1 pilot](../../e1/published/2026-09-05-local-qwen/README.md)
  collected twelve task observations with Qwen3-VL 4B; neither arm produced
  conforming notes. It does not establish improved writing efficacy.
  E2 (the author's chapter cycle) has not been run; E3 does not
  exist. Two open deviations are recorded in the phase specs: the
  structured-fact writer waits on a published ignorable-append harness
  (tripwire armed), and `archive/skills/` is retained.
- **Date:** 2026-08-16
- **Project:** `academic-writing-toolkit` (AWT)
- **Positioning:** 70% enforcement kernel and evidence, 30% skill-catalogue triage; 0% new writing advice

## 1. Executive decision

Rebuild AWT as a **DeepSeek Harness (dsh) distribution**: one skill catalogue,
two profiles (`awt-web`, `awt-headless`), a small set of guard plugins on
public dsh hooks, and session-log-derived governance. AWT becomes an
independently runnable app that an author opens directly (`awt web`), or that
another agent (Claude Code, Codex, CI) summons as a bounded subprocess
(`dsh --profile awt-headless "task"`, or the dsh Python SDK over stdio).

Three decisions define v0.1:

1. **Enforcement moves from prose to hooks.** The constraints the user relies
   on daily (notes-before-chapters, page budgets, quote integrity, edit-contract
   scope) become deterministic guards at `tools/pre-execute` / `agent/pre-step`,
   with typed denials. Constraints that cannot be enforced are labelled
   *advisory* — never implied to be enforced.
2. **The skill catalogue shrinks from 20 to 9 plus 3 reference documents**,
   per the 2026-08-16 efficacy review (§6). Every retained skill passed the
   test "what does this add over the unaided frontier model?"; everything that
   failed is cut, merged, or demoted to a reference document.
3. **Human gates leave agent-writable files.** An approval recorded in a CSV
   the agent can edit is not a gate (verified: an agent self-approved a full
   thesis-control packet and `--strict` validation passed with placeholders
   intact). v0.1 gates live in harness-owned approval events and the
   append-only session log, which the model cannot rewrite.

The two honest operating modes are **Enforced** (a guard plugin actively
blocks the operation and CI proves it) and **Advisory** (instruction text the
model may follow imperfectly). There is no mode in between, and no advisory
behaviour may be described with enforcement vocabulary.

## 2. Evidence basis

### 2.1 Reviews this spec answers

Three adversarially verified reviews (2026-08-16, multi-agent with independent
verification passes) ground every scope decision:

- **Engineering review** — 36 findings, 8 high-severity all confirmed:
  self-graded benchmark fiction, stale in-repo release packet, quote-corrupting
  spelling fixer, false-phantom citation auditor, broken documented global
  install, dead `render.yaml` branch, enforcement inversion, split
  product/template identity.
- **Efficacy review** — per-skill verdicts against the unaided-model test:
  2 strong/useful keeps, 7 conditional keeps, 11 net-negative or marginal
  (§6 table). Six high-severity findings confirmed, including: thesis-control
  gates self-serviceable; logic-review's lint anti-selects real faults;
  argument-governance's 78-column ledger never once maintained, including by
  its own author.
- **dsh ecosystem review** (of `dsh-subagent-admission` and four upstream fix
  branches) — 0 high findings; source of the design philosophy in §12 and
  proof the author's current toolchain can sustain attested-identity,
  truth-tested releases.

### 2.2 dsh capability baseline (audit baseline, not a floating claim)

Observed 2026-08-16 against `deepseek-ai/deepseek-harness` commit
`47f943859bef60e4160492346772ded9b24f765a`:

| Capability | Anchor |
| --- | --- |
| Skills discovered from `<projectRoot>/.agents/skills` (rank 200), `<name>/SKILL.md`, kebab-case | `docs/subsystems/skills.md` |
| Catalog exposes name+description only; body loads on demand via `skill` tool | `packages/skill/tool-skill` |
| Public hook seams: `agent/pre-step`, `tools/pre-execute`, `tools/post-execute` | `docs/architecture.md` turn flow |
| One-shot runner: `dsh --profile headless "task"`, exit codes, no port | `packages/bundle/headless/README.md` |
| Python SDK drives dsh as subprocess over stdio JSON-RPC | `python/sdk/README.md` |
| Provider-neutral model routing (OpenAI/Anthropic/self-hosted as config) | `packages/llm/llm-pi-ai/README.md` |
| Append-only session log; trajectory inspect/resume/fork/replay | `core/session`, Web UI |
| Profiles/bundles as distribution format (`dsh.profile` / `dsh.bundle`) | `docs/architecture.md` |

**Risk pinned honestly:** dsh is in developer preview and states "THERE WILL BE
COMPATIBILITY-BREAKING CHANGES." Mitigation is architectural (§5): skills and
validators stay harness-neutral files; dsh-specific code is confined to guard
plugins and profile definitions; a pinned-commit compatibility baseline is
re-attested before every release, following the `dsh-subagent-admission`
pattern — in a scheduled workflow, not a blocking push gate.

### 2.3 Demand anchor

Stated against interest: the only demonstrated user is the author (one thesis,
80,000-word target, currently zero chapters written through the toolkit).
There is no external-user evidence and this spec claims none. The acceptance
gate in §11 therefore uses the author's own thesis as the first efficacy
instrument — the product is falsified if its own author cannot sustain it
through one real chapter cycle.

## 3. Goals and non-goals

### 3.1 Goals

1. AWT runs as a standalone app: `awt web` for the author, headless for
   scripted or agent-summoned runs, identical skills and guards in both.
2. Every daily-loop constraint is either Enforced (guard + CI red test) or
   explicitly Advisory. No third state.
3. The skill catalogue contains only skills that beat the unaided model, at
   the token cost recorded in §6.
4. Governance artifacts are projections derived from the session log with a
   versioned fold (`stateVersion` + refold test), never model-authored CSVs.
5. Provider neutrality: the same profiles run DeepSeek, Anthropic, or
   OpenAI-compatible routes via configuration only.
6. Any efficacy claim names its evidence class (§11); unproven claims say so.

### 3.2 Non-goals

v0.1 does not provide:

- an upstream dsh patch, private fork, or monkey patch of any dsh package;
- Strict-style attested-identity machinery (patch hashes, process guards,
  SQLite admission ledgers) — AWT is single-author and race-free; public
  hooks suffice;
- multi-user, hosted, or collaborative operation;
- the ChatGPT App, Cloud Run/Render deployments, or the bespoke
  `awt/mvp.py` workbench (decommissioned, §13);
- new writing-advice content of any kind;
- npm/PyPI publication claims, adoption claims, or efficacy claims beyond the
  evidence classes actually attained;
- automatic migration of existing thesis-control CSV packets (a one-shot
  import script is Phase 3 scope, not a compatibility promise).

## 4. Alternatives considered

1. **Keep the Codex-CLI workbench (`awt/mvp.py`) — rejected.** Locked to one
   vendor CLI, re-implements session/budget/serving that dsh owns, ships an
   undisclosed Chinese-only kernel behind an English README, and duplicates
   five skills without a drift guard.
2. **Expose AWT as an MCP server instead of a dsh app — deferred.** MCP would
   let any host call AWT tools, but reproduces the ChatGPT-App failure: thin
   lints presented as reviews, no session ownership, no enforcement seam. A
   read-only MCP facade over the dsh app may return post-v0.1.
3. **Port the `dsh-subagent-admission` Strict machinery — rejected.** That
   machinery exists because admission must be atomic across concurrent,
   uncooperative callers. AWT has one writer and zero concurrent admission
   races; its budgets are per-conversation, the opposite of a monotonic
   lifetime fuse. Copying it would recreate the thesis-control
   disproportionality at higher cost.
4. **Fork dsh — rejected.** Same grounds as the admission project: drift
   against a fast-moving preview, harder review, and it would obscure whether
   the guard pattern is generally useful.

## 5. Product shape

```
awt/                          repo (product only; no thesis content)
├── skills/                   9 canonical <name>/SKILL.md bundles (§6)
├── references/               3 reference documents (§6)
├── guards/                   dsh guard plugins (TypeScript, §7)
├── profiles/
│   ├── awt-web/              dsh-base + dsh-web-app + guards + skills
│   └── awt-headless/         dsh-base + dsh-headless + guards + skills
├── validators/               harness-neutral Python (notes lint, refs, export)
├── scaffold/                 `awt init` → clean thesis workspace (no dev files)
└── specs/                    this document and per-phase specs
```

Summon paths:

| Caller | Invocation | Session ownership |
| --- | --- | --- |
| Author | `awt web` → dsh Web UI at 127.0.0.1 | dsh session log, trajectory view |
| Claude Code / Codex | subprocess `dsh --profile awt-headless "<task>"` | one persisted session per call, exit-code semantics |
| Scripts / CI | Python SDK (`deepseek-harness-sdk`) | same |

The thesis workspace is created by `awt init` and contains only: `chapters/`,
`literature/reading_notes/`, `CLAUDE.md`-equivalent project config, and
`.agents/skills` links. The product repo is never the workspace (closes the
split-identity finding).

## 6. Skill catalogue decision table

Verdicts from the 2026-08-16 efficacy review. "Delta" answers: what does this
add over the unaided frontier model?

| # | v0.1 skill | Absorbs | Verdict basis | Retained delta |
| --- | --- | --- | --- | --- |
| 1 | `read` (slim) | — | useful | paced page-anchored passes, quotes with page numbers, no-auto-write posture; per-page Key Terms/Connections become on-demand; page budgets move to guards (§7) |
| 2 | `note` | evidence-status firewall from `evidence-review` | strong | the cross-session notes data contract — the toolkit's keystone; gains one `Evidence status: full_text/abstract_only/metadata_only` header field and a deterministic lint |
| 3 | `map` | `progress` | useful | coverage matrix + gap flag; tallying backed by a deterministic script (no LLM counting); no inference fallback — broken notes surface as errors |
| 4 | `integrate` | — | useful | plan-table-then-approve gate; `completed→integrated` status lifecycle (real cross-session memory); contract violations now blocked by the notes lint |
| 5 | `review` | `peer-review` + `self-review` (own-work mode) | marginal→slim | as-submitted evidence boundary, three-way anchored finding split, fixed recommendation vocabulary, stop conditions; ~40 lines; clean-room claims replaced by a fresh-context subagent run, which is the only enforceable clean room |
| 6 | `edit-contract` | `thesis-control` (20% core) + `revision-escalation` | net-negative→salvage | spine card + allowed/forbidden/adjacent edit scope + 3-strike escalation; scope enforced by guard (§7), attempts counted from the session log, not self-reported CSVs |
| 7 | `audit` (slim) | — | marginal | A–D consistency structure, severity taxonomy, never-auto-fix; heuristic citation tiers opt-in until false-positive rates are measured and disclosed |
| 8 | `verify-refs` | — | useful | best functionality-per-byte in the toolkit; parser replaced with `bibtexparser`; offline-first, `--online` explicit |
| 9 | `export` | — | useful | bundled pandoc script behind a slash command; SKILL.md shrinks to invocation + arguments |

Demoted to `references/` (loaded on demand, zero standing description cost):
`argument-checklist.md` (argument-governance's interrogation checklist +
examiner-attack pre-mortem, emitted as a one-shot report, no standing CSVs),
`evidence-vocabulary.md` (release-governance's three-state evidence
vocabulary and the "agent review is never author-confirmed evidence" rule),
`reframe-method.md` (manuscript-reframe's ~8 generic steps, stripped of the
author's perception-paper vocabulary).

Cut outright: `logic-review` (lint anti-selects real faults and scopes the
reviewer to its noise), `style` (net-negative: quote-corrupting fixer, false
passes; superseded by the quote-integrity guard plus a proper spellchecker
wrapper if ever needed), `verify` (default search-enabled model behaviour;
its annotation convention folds into `note`), `human-eval-handoff-repair`
(single-user private runbook; moves to the author's rebuttal repo),
`manuscript-reframe` and `release-governance` and `argument-governance` as
standing skills (their salvageable content is the three references above),
`progress` (folded into `map`), `thesis-control` and `revision-escalation`
and `self-review` and `evidence-review` and `peer-review` as separate skills
(merged per the table).

Result: standing catalogue cost drops from 20 descriptions (~870 tokens per
conversation, plus cross-fire from 9 overlapping governance triggers) to 9
descriptions with disjoint trigger spaces.

## 7. Enforcement plan (guards on public hooks)

All guards are ordinary dsh plugins registered on public seams. No dsh source
is patched. Denials are typed and content-free (operation, rule, observed,
limit, correlation id — never prompt or manuscript text).

Enforced rows, in the ecosystem's enforcement-semantics format (as
implemented; the guards' own README carries the per-guard "what this does
not do" sections):

| Constraint | Seam | What is counted / diffed | Typed outcome |
| --- | --- | --- | --- |
| No chapter write may cite a source without a conforming notes file | `ctx.tools.guard` | author-year citations in the written text vs lint-conforming notes files | deny `NOTES_MISSING` |
| Quoted text in existing chapters is immutable | `ctx.tools.guard` | quotation-delimited spans before vs after the proposed write/edit | deny `QUOTE_SPAN_MODIFIED` |
| Chapter writes stay inside the active contract's scope | `ctx.tools.guard` | target path vs the active contract's `May change:` / `Must not change:` | deny `CONTRACT_SCOPE` |
| ≤15 pages per read invocation | `ctx.tools.guard` | requested `first_page`..`last_page` | deny `PAGE_RANGE_EXCEEDED` |
| ≤90 pages per session | `ctx.tools.guard` | successful reads folded from the session log (projection) | deny `PAGE_BUDGET_EXCEEDED` |
| 3-strike revision escalation | `tools/pre-execute` waterfall | per-contract typed-denial attempts folded from the session log | `ask` `ESCALATION_REQUIRED` via the harness approval seam (fail-closed without an answerer) |
| No inert enforcement mounts | plugin `apply()` at profile boot | config limits, notes root, contracts source | typed `GuardConfigError` boot failure |

Advisory rows (instruction text; never described with enforcement
vocabulary): British English and citation punctuation (optional opt-in
linter with disclosed false-positive rates); read-first writing posture and
review rubrics (skill text). The escalation *diagnosis* — why revisions
keep failing — is likewise advisory; only the count and the author gate are
enforced.

CI proves every Enforced row with a red-first test: the forbidden operation is
attempted against a live headless profile and must be denied with the exact
typed code. An Enforced row without its red test does not ship (docs-are-
executable-claims, applied to enforcement claims).

## 8. Governance re-architecture

- **Projections, not ledgers.** Reading budgets, integration status, revision
  attempts, and audit history are folded from the dsh session log by versioned
  reducers (`stateVersion` + refold test for old checkpoints — the pattern
  from the author's dsh `fix-token-usage-retry-compaction` branch). The model
  never writes a governance counter.
- **Approvals are harness events.** Author decisions (approve integration
  plan, accept/reject reviewed edit, approve escalation) are recorded as
  approval interactions in the dsh session, immutable in the append-only log.
  A file the agent can edit is display, never authority.
- **Ugly truth over clean display.** A guard failure or budget exhaustion is
  surfaced verbatim in the session; nothing rewrites history to make a
  dashboard look consistent.

## 9. Harness leverage (generalisation and elasticity)

What dsh buys beyond the current architecture, exploited deliberately:

1. **Provider elasticity.** `awt-headless` with an Anthropic route for prose
   fidelity, a DeepSeek route for cost, or a self-hosted gateway — pure
   configuration (`llm-pi-ai` routes). The app never hardcodes a vendor.
2. **Trajectory fork = honest revision experiments.** revision attempts fork
   the session at the pre-edit point instead of piling onto one drifting
   context; the 3-strike counter counts forks of the same contract. Replay
   makes "what did the model actually see" a first-class review question.
3. **Bounded subagent fan-out.** Whole-thesis audits fan one bounded reviewer
   per chapter (the fresh-context clean room that `self-review` promised but
   could not enforce), composed under dsh-turn-budget-style limits.
4. **Compaction/spill for long reading sessions.** The 90-page budget guard
   plus dsh compaction replaces "hope the model counts its own history."
5. **Profile-family generalisation.** `awt-thesis` is one profile; the same
   guard + contract + notes-lint kernel parameterises to grant proposals or
   journal papers as sibling profiles without touching the kernel — AWT
   becomes a profile family, not a thesis-only tool.

## 10. Hard invariants

For every reachable v0.1 state:

1. No write to `chapters/**` occurs without a passing notes-lint result for
   the sources the edit cites.
2. No tool run mutates text inside quotation spans of existing chapters.
3. Every Enforced constraint has a CI test that proves the denial fires;
   Advisory constraints never appear in enforcement vocabulary.
4. Governance counters are derived from the session log by versioned reducers;
   no model-writable file is authoritative.
5. Author approvals exist only as harness interaction events.
6. A denied operation changes no authoritative state.
7. Every user-facing claim of skill efficacy cites an evidence class from §11,
   or states that none exists.
8. The product repo contains no thesis content; the workspace contains no
   product internals.

## 11. Evidence classes and the efficacy plan

Evidence classes, never collapsed: (E0) deterministic gate green in CI;
(E1) paired-session comparison on real inputs with machine-graded criteria;
(E2) author dogfood through one real chapter cycle; (E3) external user
evidence. The original individual-skill claims remain at E0 or below. A
three-source E1 pilot now measures the combined AWT profile under one local
model; its negative/inconclusive outcomes do not upgrade individual-skill
efficacy claims. The README links its measured record and boundaries.

Committed E1 instrument (from the efficacy review's ground lane): three real
PDFs; paired sessions (skills vs plain prompting); machine-graded quote
fidelity (string-match quoted spans against `pdftotext`), page-number
accuracy, notes-file parseability, and citations-to-unopened-sources count in
a drafted section. Runs headless, reproducible, published with the producer
script — never a hand-authored comparison table.

**v0.1 acceptance gate (E2):** one real thesis chapter cycle — read → note →
integrate → edit-contract → review → audit → export — completed by the author
in the dsh app, with the session log as the evidence artifact. The empty
`chapters/` directory is the falsifier this product has to answer.

## 12. Kill and reframe gates

Re-run before scaffolding and before each phase ships:

- **Kill:** dsh introduces a breaking change that removes public hook seams or
  `.agents/skills` discovery with no replacement, and the pinned-commit build
  cannot be sustained → stop; the skills and validators remain usable in
  Claude Code/Codex unchanged.
- **Reframe:** the E2 dogfood gate fails because the author abandons the flow
  (not because of defects) → the enforcement layer is over-weighted; reframe
  toward the advisory-only catalogue before adding any further machinery.
- **Standing rule:** thesis progress outranks toolkit progress. Any phase that
  has consumed its budget (§14) without shipping stops rather than expanding.

## 13. Legacy decommission (same release as replacement, not before)

| Legacy surface | Disposition |
| --- | --- |
| `awt/mvp.py` workbench + `mvp_index.html` | removed; `workflow_io.py` SHA-256 binding survives as a validator |
| ChatGPT App (`apps/`), Cloud Run, Render, HF Space | removed with a README pointer to the last supporting tag |
| `plugins/` Codex plugin package + sync scripts | replaced by the single canonical `skills/` tree consumed via `.agents/skills` by Codex, Claude Code, and dsh alike |
| 11 removed/merged SKILL.md bundles | deleted from the catalogue; salvage lands in `references/` per §6 |
| `release/` stale v0.3.1 packet | deleted; release identity moves to tagged, truth-tested release notes |

## 14. Deliverables and phases (spec-driven)

Each phase begins with its own short spec plus truth tests, and ends with the
phase's gates green. No phase starts while the prior phase's gates are red.

| Phase | Scope | Gate |
| --- | --- | --- |
| P0 | Catalogue triage: 9 slim skills + 3 references, notes lint, disjoint descriptions | all skills pass a description-collision test; notes lint red-first tests green |
| P1 | Profiles + guards: `awt-web`/`awt-headless`, the §7 Enforced rows, typed denials | every Enforced row's red-first CI test green against a live headless run |
| P2 | Projections + approvals: session-log reducers, harness approval events, `awt init` scaffold | refold tests green; self-approval attack from the efficacy review re-run and blocked |
| P3 | Evidence: E1 paired-session instrument, E2 dogfood chapter cycle; legacy decommission | E1 results published with producer; E2 session log exists; §13 table executed |

Budget rule: each phase is sized to at most two working sessions; a phase that
exceeds its budget triggers §12's standing rule.

## 15. Open questions for author approval

1. Repository strategy: rebuild in-place on `academic-writing-toolkit` (keep
   history and stars) or a fresh `awt-app` repo with this repo archived as the
   skill source? This spec assumes in-place.
2. Guard implementation language: TypeScript dsh plugins only, or a thin
   TypeScript hook that shells to the Python validators (keeps validators
   harness-neutral but adds a process boundary per check)?
3. Does `awt-web` ship in v0.1, or is headless-first acceptable with the Web
   UI deferred to v0.2? (Headless-first shortens P1 materially.)
4. Citation heuristics: fix `audit-citations.py` to measured-FP quality inside
   v0.1, or ship v0.1 with citation tiers disabled and a disclosed gap?
