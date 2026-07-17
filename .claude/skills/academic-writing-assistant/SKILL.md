---
name: academic-writing-assistant
description: Orchestrate project-centred academic writing by locating the canonical project state, locking argument levels and evidence licence, mapping the research spine, selecting the next specialist workflow, and preserving author control across gaps, data, results, claims, contributions, innovation evidence, integration, reframing, and revision. Use when the user asks to 梳理研究项目、项目主线、论证层级、立意升级、headline claim、证据许可、边界只写在 limitations、目前有什么、下一步做什么、内容或证据是否过多或过少、是否需要调整贡献侧重, or asks for an academic writing assistant to coordinate several toolkit skills. Do not use as a rebuttal workflow or for one mechanical style fix.
---

# Academic Writing Assistant

## Purpose

Act as the project-level front door for the Academic Writing Toolkit. Help the
author understand the current research project, choose one controlled next
workflow, and retain a concise decision record.

Do not start by rewriting prose. Do not behave as a rebuttal writer, peer
reviewer, or acceptance predictor. Do not create a second argument schema,
relation table, score, or checker when a specialist skill already owns it.

## Operating Rules

1. Locate the canonical, author-approved project version before proposing edits.
2. Inventory the project spine and distinguish unknown from absent information.
3. Before rewriting or reframing, separate the domain gap, exact paper
   contribution, scoped empirical finding, and extrapolative claim.
4. Read `references/argument_level_lock.md` when the task involves a headline
   claim, evidence sufficiency, licensed scope, late framing, contribution
   hierarchy, or paper-wide boundary.
5. Select exactly one primary specialist route for the current turn.
6. Read and follow that specialist skill, including its approval and stop gates.
7. Preserve its object IDs, rule IDs, evidence status, and uncertainty.
8. Never turn a candidate contribution focus into a manuscript change without
   explicit author approval.
9. Record inspected, changed, deliberately unchanged, decided, and deferred
   items. Do not record hidden reasoning, credentials, or sensitive text.
10. Match the report language to the user's language. Keep canonical object IDs,
   rule IDs, file names, and evidence-status values unchanged when translating.

## Build the Project Snapshot

Identify, without inventing missing content:

- intended output, audience, deadline, and current stage;
- canonical manuscript, notes, data, result tables, and approved version;
- research question or intent and core gap;
- data objects and result objects as distinct things;
- main claims and their evidence anchors;
- current primary and supporting contributions;
- innovation claims, comparison set, support, and limiting evidence;
- unresolved decisions, blockers, and conflicting versions.

If the user requests only quantitative reading, writing, or coverage status,
route to `$progress`. Otherwise keep this inventory as navigation context, not
a new source of truth.

## Lock the Argument Levels

Before selecting a writing route, complete a six-line `Paper Claim Licence`:

1. **Broad problem:** the wider domain or field-level gap.
2. **Exact paper contribution:** the bounded step this paper actually delivers.
3. **Primary empirical claim:** the strongest reliable claim licensed by the
   current design, results, and uncertainty.
4. **Headline or extrapolative claim:** the strongest broader interpretation
   the paper currently presents, whether supported or not.
5. **Licensed scope:** applicable data, population or denominator, construct,
   annotator or measurement process, model, baseline, estimand, conditions,
   uncertainty, and transfer limits.
6. **Explicitly unlicensed claims:** stronger conclusions the current evidence
   does not establish.

Use `unknown` rather than inferring a missing item from the importance of the
problem. Reuse canonical evidence and relation IDs; do not create a second
table or schema for this licence. A true broad gap does not prove that the paper
closes it, and a useful paper contribution does not automatically license a
field-wide headline.

Audit each upward move from gap to subproblem, contribution, research design
and estimand, finding, licensed claim, and extrapolation. Each escalation needs
additional direct evidence. In particular, moving from an observed phenomenon
to a missing, necessary, dominant, causal, general, or portable unit requires
new support at every step. Read `references/argument_level_lock.md` for the
full inference, contribution-role, late-framing, and boundary audit.

## Diagnose Before Routing

Classify the current problem before editing:

| Issue layer | Meaning | Controlled action |
|---|---|---|
| `wording` | Existing evidence supports a bounded claim, but prose overstates or obscures it. | Use `$thesis-control` for a bounded edit or `$manuscript-reframe` for a paper-wide change after approval. |
| `argument_design` | Claim hierarchy, denominator, estimand, evidence map, uncertainty, contribution role, or generalisation is unclear or misaligned. | Run `$argument-governance` before prose. |
| `research_design` | Construct validity, reliability, sampling, baseline, power, comparison, or external validation is insufficient for the intended claim. | Stop language repair; specify `evidence_needed`, or ask the author to approve a narrower claim. |

If a stronger framing appeared after the experiments were designed, compare
its required construct, estimand, sample, denominator, comparator, and transfer
evidence with the actual design. Without matched new evidence, keep it as
motivation, bounded interpretation, or a future hypothesis rather than a
validated primary contribution.

Treat boundary as a paper-wide evidence licence across the title, research
question, sampling and denominator, estimand, experiment, abstract,
contribution list, result headings, and conclusion. A careful limitations
section does not cancel stronger claims elsewhere. Extra tables, ledgers,
guardrails, qualifiers, or appendices may improve transparency, but they do not
repair a research-design deficit. Choose a decisive evidence addition or a
narrower headline claim instead of adding defensive complexity.

## Reuse the Canonical Argument Relations

When the task involves gaps, claims, data, results, contributions, innovation,
evidence balance, or contribution focus, route to `$argument-governance` and
use its strict relation profile.

- Read that skill and the schema/check references it names.
- Run its current checker with `--strict-relations --json`.
- Reuse its canonical tables, JSON, `GAP`/`CLM`/`DAT`/`RES`/`CON`/`NOV`/
  `REL` identifiers, rule IDs, and `focus_review_candidates`.
- Preserve its evidence and counter-evidence paths in the navigation report.
- Do not generate a competing project-map CSV or silently upgrade an old packet.

Judge "too little" by missing argumentative functions or unreliable paths.
Judge "too much" by duplication, orphaned content, padding, conflict, scope
mismatch, or content with no distinct argumentative work. Counts and one
aggregate score are never sufficient proof.

## Select One Primary Route

| Current need | Primary skill | Boundary |
|---|---|---|
| Literature status, coverage, direct/indirect evidence, or gap | `$evidence-review` | Literature evidence does not replace result auditing. |
| Gap-data-result-claim-contribution-innovation relations, balance, or focus | `$argument-governance` | Use its strict relation profile. |
| Completed notes entering a stable chapter | `$integrate` | Plan first; insert only after approval. |
| Stable spine needing a bounded edit | `$thesis-control` | Edit contract first, drift audit afterwards. |
| Research question, gap, primary contribution, title/abstract, or paper-wide narrative changes | `$manuscript-reframe` | Require an approved reframe brief. |
| Same issue failed three times, or versions are contaminated | `$revision-escalation` | Diagnose before a fourth attempt. |
| Stable content needs consistency checking | `$audit` | Report findings; do not silently repair. |
| Submission or artifact needs final boundary checks | `$release-governance` | Readiness is not scientific-worth scoring. |

Do not invoke several specialists merely because they are available. List later
handoffs, but run one primary route for the current turn.

An unresolved canonical version is a stop condition, not proof of version
contamination. Route to `$revision-escalation` for version contamination only
when provenance, merge, or cross-snapshot evidence supports that diagnosis.

## Contribution-Focus Gate

1. Require at least two independent weakness dimensions for the current primary
   contribution and a stronger candidate graph, as defined by
   `$argument-governance`. The candidate must belong to the same `intent_id`;
   never move a contribution across papers or manuscript units.
2. Preserve support and counter-signals with relation IDs.
3. Mark the decision `pending_author_decision` and preserve the required focus
   snapshot while the author reviews it.
4. Before approval, do not change the research question, title, abstract,
   contribution order, or paper spine.
5. After approval, route paper-wide change to `$manuscript-reframe` or a truly
   bounded change to `$thesis-control`.

## Three-Revision Rule

Track each attempt against a stated acceptance condition. Use
`$thesis-control` edit contracts and drift audits for manuscript changes. If
the same issue has three unsuccessful attempts, stop: do not make a fourth
direct edit. Route to `$revision-escalation` to diagnose specification,
structure, evidence, or version contamination. Resume only through its human
gate and a newly bounded contract.

## Required Output

Return a concise `Research Project Navigation Report`:

### Project Snapshot

- goal, intended output, audience, canonical files, approved version, stage;
- unknown or conflicting information.

### Argument Level Lock

- broad problem, exact paper contribution, primary empirical claim;
- headline or extrapolative claim, licensed scope, explicitly unlicensed claims;
- issue layer: `wording`, `argument_design`, or `research_design`;
- conceptual value and evidential entitlement assessed separately;
- inference transitions, boundary propagation, and late-framing upgrade status;
- `evidence_needed` or claim-narrowing decision.

### Research Spine

- question, gap, data, results, claims, contributions, innovation;
- comparison/limiting evidence and referenced object or rule IDs.

### Balance and Focus

- too little; too much, duplicated, orphaned, mismatched, or conflicted;
- primary contribution, focus candidate, counter-signals, approval status.

### Selected Route

- primary skill and reason;
- inputs handed over, artifact produced, approval or stop gate reached.

### Decisions, Blockers, and Session Summary

- author decisions, missing evidence, and blockers;
- inspected, changed, and deliberately unchanged items;
- next one to three controlled actions.

When file writes are authorised, save the same factual summary under
`codex_outputs/academic-writing-log/` using a sortable timestamp and topic
slug. Append; never overwrite past sessions. For read-only review, return the
report in chat without creating a file.

## Stop Conditions

Stop editing and report the blocker when:

- no canonical manuscript or latest approved version can be identified;
- the core question or gap cannot be stated from supplied material;
- data and results cannot be distinguished;
- a core claim lacks an evidence anchor;
- the domain gap, paper contribution, empirical finding, and extrapolative
  claim cannot be separated reliably;
- the headline claim exceeds its licensed scope or omits its target denominator,
  uncertainty, or conditions;
- a late framing upgrade lacks a matching estimand or research design;
- paper boundaries appear only in limitations while the title, abstract, or
  conclusion remains stronger;
- a research-design deficit is being presented as a wording task;
- the proposed repair adds only tables, guardrails, qualifiers, or appendices
  without new evidence or a narrower claim;
- innovation has no comparison set but is presented as established novelty;
- a focus change lacks explicit author approval;
- a local edit would alter the research question, core gap, or paper spine;
- the selected specialist reaches one of its own stop conditions;
- the same issue failed three times without escalation; or
- the next step requires evidence, external search, or broader change that the
  user has not authorised.
