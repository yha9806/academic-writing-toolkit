# Argument Governance Checks

Use these checks when writing reports or interpreting `check_argument_governance.py` output.

## Structural Checks

- Every required CSV exists under `evidence/`.
- Every CSV has the required columns.
- Every enum value is from the schema unless the cell is intentionally blank.
- Every referenced ID exists.
- Claim parent links do not form cycles.
- Argument-system map parent links do not form cycles.

## Alignment Checks

- Every contribution answers a named gap.
- Every paper intent links to at least one contribution.
- Every contribution links to at least one primary claim.
- Every main claim links to an intent and, when applicable, a contribution.
- Lower-level claims support a parent claim rather than floating as isolated observations.

## Evidence-Balance Checks

- `unsupported` means the claim should be removed, revised into a gap, or held for evidence gathering.
- `under_supported` means the claim may remain only with boundary language or lower force.
- `adequately_supported` means the evidence type and claim type match.
- `over_cited` means the claim has more support than its argumentative role justifies.
- `misaligned_evidence` means the evidence exists but supports a different claim level, domain, or result type.

## Reviewer-Risk Checks

- Every high-risk contribution should have novelty, significance, and evidence-strength attacks considered.
- High or critical attacks require a response strategy.
- Weak defenses should become revision actions, not just rebuttal wording.
- Reviewer defenses must not cite unavailable evidence, memory, or private context.

## Functional Balance Checks

Treat "too little" and "too much" as missing or duplicated argument functions, not raw counts.

| Rule | Deterministic trigger | Interpretation |
|---|---|---|
| `GAP-01` | A core gap has no scope-matched source or problem-evidence relation | Gap evidence is too thin |
| `GAP-02` | A core gap has no current contribution that addresses it | The project promises more than it delivers |
| `CLM-01` | A paper-thesis or contribution claim has no direct result, source, or evidence support relation | Main claim support is too thin |
| `CLM-02` | A supporting relation has `scope_match=mismatch` | Claim scope exceeds evidence scope |
| `CLM-03` | Two claims have the same normalised text | Claim hierarchy may contain duplicated argumentative work |
| `DATA-01` | Available data produce no result | Data are currently orphaned; this is not automatically a contribution |
| `DATA-02` | A result has no traceable data input | Result provenance is incomplete |
| `RES-01` | A result supports, limits, refutes, or substantiates nothing | Result is orphaned or a candidate unclaimed finding |
| `RES-03` | A verified result refutes a main claim without a recorded qualification or boundary | Mixed or conflicting evidence is being hidden |
| `CON-01` | A current primary contribution lacks the evidence path required for its contribution type | Contribution support is too thin |
| `CON-02` | Contributions of the same type address the same gap with at least the configured support-set overlap | Contribution list may be artificially split |
| `CON-03` | A verified result is not represented by any current claim or contribution | A defensible result may be under-emphasised |
| `NOV-01` | An innovation has no explicit comparison set or comparison evidence | Innovation evidence is too thin |
| `NOV-02` | A primary contribution relies on contradicted innovation evidence | Innovation emphasis may be unsafe |
| `FIT-01` | A primary contribution has weak gap fit, low target-reader fit, absent narrative emphasis, or an incomplete required chain | Current contribution emphasis is misaligned |
| `FIT-02` | A current primary has multiple independent weaknesses while a secondary contribution has a complete, scope-matched chain and stronger declared fit | Contribution-focus review is warranted |

Count-based warnings such as more than three primary contributions are advisory only. Citation count, word count, number of datasets, number of metrics, and statistical significance never determine contribution importance by themselves.

A relation counts toward chain completeness only when `status=verified`, `directness` is `direct` or `partial`, and `scope_match` is `exact` or `partial`. Any evidence object used by that relation must be `available` or `verified`, have `provenance_status` of `verified` or `traceable`, and have checked, validated, frozen, or not-applicable quality. Candidate, contested, indirect, unverified, unknown-scope, raw, unstable, or contradicted inputs can be reported, but cannot make a chain complete or trigger `FIT-02`.

## Severity And Confidence

Keep severity and confidence separate:

- `critical`: a central claim or contribution chain is invalid for its declared scope
- `high`: contribution focus, evidence fit, or innovation framing is likely misleading
- `medium`: redundancy, orphaning, or narrative imbalance needs review
- `low` or `info`: a navigation or clean-up signal

Confidence labels:

- `confirmed`: the required relation is explicitly missing or contradictory
- `likely`: at least two independent signals agree
- `possible`: only one signal exists or context is incomplete
- `cannot_assess`: project intent, target readers, venue, or scope is missing

Do not calculate a single novelty, contribution, balance, or manuscript-quality score.

## Contribution Focus Review

Before suggesting a focus change, compare current and candidate contributions on:

- core-gap fit
- required evidence-chain completeness
- result consistency
- innovation-comparison evidence
- target-reader and venue fit when declared
- scope mismatch and overclaim risk
- narrative emphasis
- affected sections and revision cost

The checker may emit a `focus_review_candidates` array with:

```text
intent_id
current_primary_id
candidate_id
trigger_rule_ids
current_signals
current_signal_dimensions
candidate_signals
counter_signals
candidate_actions
requires_author_approval
recommended_next_skill
approval_status
affected_section_ids
revision_scope
snapshot_required
post_approval_routes
```

This is an advisory handoff contract, not automatic routing. A candidate must have the same `intent_id` as the current primary contribution; contributions from another paper or manuscript unit cannot become focus candidates. `counter_signals` is a list of traceable objects with `dimension`, `message`, and `relation_ids`; a verified `limits` relation must remain visible even when positive innovation evidence also exists. Before approval, `recommended_next_skill` must be `pending_author_decision`. Use only `keep`, `narrow`, `promote`, `demote`, `merge`, `remove`, or `evidence_needed` as candidate actions. Never rewrite the title, abstract, introduction, contribution list, or conclusion until the author approves a focus decision.

After approval:

- use `/manuscript-reframe` if the research question, core gap, title, abstract thesis, or paper-wide narrative changes
- otherwise use `/thesis-control` to create a bounded edit contract and drift audit
- after three failed focus-revision attempts, use `/revision-escalation` before any fourth edit

## Forbidden Inferences

Never infer that:

- more citations, datasets, metrics, or words mean stronger evidence or contribution
- a local search that found no match establishes novelty
- statistical significance establishes practical importance, causality, or generalisation
- the contribution with the most evidence must become primary
- a negative or mixed result means the project failed
- an orphan result automatically deserves a new contribution
- a checker result replaces author or domain-expert judgement
