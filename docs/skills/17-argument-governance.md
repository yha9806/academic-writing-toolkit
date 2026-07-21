# /argument-governance

Build and audit a manuscript's argument system:

```text
intent -> gap -> contribution
data -> result -> claim -> contribution
prior-work evidence -> innovation -> contribution
claim/contribution -> boundary -> reviewer risk
```

Use this skill when a paper, thesis chapter, or research project needs explicit control over whether the contribution answers a real gap, whether results support the claims made from them, whether innovation has comparison evidence, and whether any argumentative function is missing, duplicated, orphaned, or over-emphasised.

## Codex-Only Baseline

Codex can complete this workflow using local files, the CSV schemas, and the bundled checker. Gemini, gemini-agent, external reviewers, subagents, or other model calls are optional advisory inputs only.

## Enhanced Advisory Mode

With explicit user approval and an API key stored in an environment variable, Codex may request an external second opinion after the local argument packet exists. This is the high-assurance mode, not the baseline. External output remains advisory and must not become evidence.

## Creates Or Updates

Under `evidence/`:

- `intent_register.csv`
- `contribution_chain.csv`
- `claim_hierarchy.csv`
- `argument_system_map.csv`
- `reviewer_attack_matrix.csv`

For the explicit research-relation profile, also create:

- `gap_register.csv`
- `evidence_objects.csv`
- `innovation_register.csv`
- `argument_relations.csv`
- `contribution_focus.csv`

The original five-table packet remains supported. The additional files are required only when the strict relation profile is requested.

If any project-intent control file exists under `thesis_control/`, first run
the strict `/thesis-control` validator. The argument packet must reuse the
unique active author-approved project `intent_id`. A partial, draft,
multiply-active, or conflicting project-intent layer is a stop condition, not
permission to create a second root.

## Main Checks

- Every contribution answers a named gap.
- Every main claim belongs to a contribution or the paper-level thesis.
- Every lower-level claim supports a parent claim.
- Every claim has the right type and amount of evidence.
- Field-level gap, paper-level contribution, data-level finding, and
  extrapolative claim remain separate; every upward inference needs its own
  evidence anchor.
- Data are recorded as inputs and results as derived outputs; the two are not interchangeable.
- Every result used in the paper reaches a claim through an explicit relation.
- Every innovation statement names a comparison set and comparison evidence.
- Too little means a required argumentative function or relation is absent; too much means content is duplicated, orphaned, citation-padded, or doing no distinct argumentative work.
- Background, method, workflow, or governance evidence is not promoted into empirical, causal, outcome, or deployment validation.
- Licensed scope is checked across the title, research question, denominator,
  estimand, abstract, contribution list, result headings, conclusion, and
  limitations. A limitation-only disclaimer does not close an oversized chain.
- Tables, ledgers, guardrails, qualifiers, and appendices do not substitute for
  missing construct, reliability, sampling, baseline, power, or transfer
  evidence; the action is `evidence_needed` or a narrower claim.
- High-risk reviewer attacks have adequate defenses or revision actions.

## Deterministic Helper

```bash
python3 .claude/skills/argument-governance/scripts/check_argument_governance.py . --json
```

For gap-claim-data-result-contribution-innovation relations:

```bash
python3 .claude/skills/argument-governance/scripts/check_argument_governance.py . --strict-relations --json
```

The helper checks files and required values, enums, typed ID links, cross-table target consistency, tree and relation cycles, required evidence paths, orphaned results, redundancy candidates, and weak reviewer defenses. Only verified, direct-or-partial, scope-matched relations backed by traceable checked objects complete a chain; candidate or disputed links remain visible but cannot justify a focus shift. It emits explainable rule IDs, severities, and confidence rather than a single quality score. It does not establish scientific novelty, correctness, importance, or venue acceptance.

## Contribution Focus Changes

If the current primary contribution has at least two independent structural weaknesses while another contribution in the same `intent_id` has stronger verified core-gap fit and a complete evidence chain, the checker emits a `focus_review_candidates` handoff. Contributions from another paper or manuscript unit are never focus candidates. Each candidate includes supporting signals, counter-signals, bounded actions, and `requires_author_approval: true`. A single missing link produces `evidence_needed`, not an automatic promote/demote proposal.

When a focus candidate is emitted, freeze the affected intent IDs, all current primary IDs in those intents, author-approved manuscript hash, and relation-packet hash in `evidence/contribution_focus_snapshot.json`. The checker blocks missing, stale, unrelated, out-of-project, or incomplete snapshots: IDs must match the current packet, the manuscript path must exist inside the project, and captured patterns must cover all required packet CSVs. Weaknesses are deduplicated by dimension, and innovation limits remain traceable through relation IDs in structured counter-signals. The skill does not silently change the paper's main contribution. Before approval the route remains `pending_author_decision`; after the author chooses `keep`, `narrow`, `promote`, `demote`, `merge`, `remove`, or `evidence_needed`, use `/manuscript-reframe` for paper-wide narrative changes or `/thesis-control` for bounded prose edits. Three failed focus-revision attempts trigger `/revision-escalation` before a fourth edit.

## Typical Output

```text
## Argument Governance Report

### Paper Spine
### Argument Licence And Headline Scope
### Alignment Issues
### Claim-Evidence Balance
### Functional Balance
### Contribution Focus Review
### Reviewer Risks
### Next Actions
```

Use `/evidence-review` for detailed evidence status and citation-role planning. Use `/peer-review` or `/self-review` after the argument skeleton is explicit.
