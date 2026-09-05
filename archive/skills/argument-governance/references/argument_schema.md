# Argument Governance Schema

Use these CSV files under `evidence/` to model a paper as a layered argument system.

## `intent_register.csv`

```text
intent_id,paper_title,central_problem,target_venue,target_readers,field_positioning,core_gap,current_dominant_narrative,narrative_to_correct,why_now,main_contribution_ids,boundary_statement,success_criterion,reviewer_risk_level,notes
```

Required semantic links:

- `intent_id` is the root for one paper or manuscript unit.
- `main_contribution_ids` references `contribution_chain.contribution_id`; use semicolon-separated IDs for multiple contributions.
- `core_gap` must be specific enough to distinguish absent evidence, weak framing, weak evaluation, weak governance, or weak translation.
- `boundary_statement` states what the paper does not claim.

## `contribution_chain.csv`

```text
contribution_id,intent_id,gap_id,gap_statement,gap_type,why_gap_matters,insight,contribution_statement,contribution_type,method_or_artifact_id,primary_claim_ids,required_evidence_type,current_evidence_ids,evidence_coverage,limitation,boundary_language,reviewer_defense_note
```

Allowed `gap_type`:

```text
empirical_gap
methodological_gap
conceptual_gap
evaluation_gap
governance_gap
translation_gap
reproducibility_gap
```

Allowed `contribution_type`:

```text
conceptual_reframing
method_or_tool
dataset_or_benchmark
empirical_finding
evaluation_protocol
governance_framework
case_study
```

Allowed `evidence_coverage`:

```text
missing
thin
adequate
strong
over_supported
misaligned
```

Required semantic links:

- Every `contribution_id` must reference an existing `intent_id`.
- Every contribution must have a `gap_id`, `gap_statement`, and `contribution_statement`.
- `primary_claim_ids` references `claim_hierarchy.claim_id`.
- `required_evidence_type` should name the evidence needed, not merely the evidence available.

## `claim_hierarchy.csv`

```text
claim_id,parent_claim_id,root_intent_id,contribution_id,section_id,claim_level,claim_role,claim_text,depends_on_claim_ids,evidence_requirement,evidence_ids,citation_keys,evidence_status,evidence_strength,support_balance,system_role,overclaim_risk,boundary_language,revision_action
```

Allowed `claim_level`:

```text
paper_thesis
contribution_claim
section_claim
subsection_claim
paragraph_claim
```

Allowed `claim_role`:

```text
gap_claim
background_claim
method_claim
artifact_claim
result_claim
interpretive_claim
limitation_claim
implication_claim
```

Allowed `support_balance`:

```text
unsupported
under_supported
adequately_supported
over_cited
misaligned_evidence
```

Allowed `system_role`:

```text
motivates_gap
defines_gap
answers_gap
justifies_method
supports_result
interprets_result
states_boundary
states_implication
```

Required semantic links:

- `paper_thesis` claims should be few, normally 1-3 per manuscript.
- `contribution_claim` claims must reference `contribution_id`.
- `section_claim`, `subsection_claim`, and `paragraph_claim` should have `parent_claim_id`.
- `depends_on_claim_ids` references other claim IDs when a claim logically depends on another claim.
- `evidence_ids` references evidence records, artifacts, or evidence clusters used by the project.
- `citation_keys` references bibliography or reading-note citation keys.

## `argument_system_map.csv`

```text
node_id,parent_node_id,node_type,node_label,linked_gap_id,linked_contribution_id,linked_claim_id,linked_evidence_ids,section_id,status,risk_level,notes
```

Allowed `node_type`:

```text
intent
gap
contribution
main_claim
subclaim
evidence_cluster
limitation
reviewer_risk
```

Use this as the compact argument map. The map should be a tree or a small forest rooted in `intent` nodes. A node may link to a contribution, claim, evidence cluster, or reviewer risk.

## `reviewer_attack_matrix.csv`

```text
attack_id,target_type,target_id,reviewer_question,attack_category,severity,likely_reviewer_profile,current_defense,evidence_needed,current_evidence_ids,defense_strength,revision_needed,response_strategy,owner,status
```

Allowed `target_type`:

```text
intent
gap
contribution
claim
evidence
limitation
```

Allowed `attack_category`:

```text
novelty
significance
gap_validity
claim_evidence_mismatch
method_validity
evaluation_strength
generalization
causal_overclaim
related_work_coverage
positioning
reproducibility
scope_boundary
```

Allowed `defense_strength`:

```text
none
weak
partial
adequate
strong
```

High-severity attacks with `none`, `weak`, or `partial` defense should trigger revision before submission-facing use.

## Explicit Research Relation Profile

Use this additive profile when the project must distinguish gaps, claims, data, results, contributions, and innovation evidence. Run the checker with `--strict-relations`. The five base tables above remain unchanged for backward compatibility.

Use stable prefixes:

```text
GAP-  gap
CLM-  claim
DAT-  data
RES-  result
CON-  contribution
NOV-  innovation
SRC-  source or prior work
EVD-  other evidence
ART-  artifact
ANL-  analysis
LIM-  limitation
REL-  typed relation
```

Do not collapse these distinctions:

- Data are analysis inputs; results are derived outputs.
- Contributions state what the project delivers; innovations state how a contribution differs from an explicit comparison set.
- A gap is a scoped and evidenced absence, limitation, or mismatch; it is not merely an interesting topic.

### `gap_register.csv`

```text
gap_id,intent_id,gap_statement,gap_type,gap_priority,gap_status,scope,search_or_problem_evidence_ids,boundary_language,notes
```

Allowed `gap_priority`:

```text
core
supporting
exploratory
out_of_scope
```

Allowed `gap_status`:

```text
candidate
scoped
evidence_supported
contested
partially_closed
closed
superseded
```

Every `core` gap should have scope-matched source or problem evidence and at least one contribution that addresses it. A closed or superseded gap must not silently remain the basis of a current primary contribution.

### `evidence_objects.csv`

```text
object_id,object_type,statement_or_description,artifact_or_source,version,scope,method_or_measure,provenance_status,quality_status,uncertainty,status,notes
```

Allowed `object_type`:

```text
data
result
source
prior_work
evidence
artifact
analysis
limitation
```

Allowed `provenance_status`:

```text
verified
traceable
partial
unverified
unavailable
restricted
```

Allowed `quality_status`:

```text
unknown
raw
checked
validated
frozen
unstable
contradicted
not_applicable
```

Allowed object `status`:

```text
planned
available
verified
contested
deprecated
superseded
```

Use `DAT-` IDs for data rows and `RES-` IDs for result rows. A result record must state the analysis, measure, or method that produced it and must link back to data through `argument_relations.csv`.

### `innovation_register.csv`

```text
innovation_id,contribution_id,innovation_type,innovation_dimension,comparison_set,difference_statement,materiality_statement,novelty_scope,comparison_evidence_ids,comparison_status,boundary_language,notes
```

Allowed `innovation_type`:

```text
new_problem
new_method
new_evidence
new_data
new_evaluation
new_workflow
transfer
integration
```

Allowed `comparison_status`:

```text
unverified
pending
partial
supported
contradicted
```

Innovation is relational. `comparison_set` must name the baselines, prior work, practices, or assumptions against which the difference is claimed. Absence from a local search is not sufficient novelty evidence.

### `argument_relations.csv`

```text
relation_id,source_type,source_id,relation_type,target_type,target_id,evidence_ids,directness,scope_match,status,rationale,notes
```

Allowed entity types:

```text
intent
gap
contribution
claim
data
result
innovation
source
prior_work
evidence
artifact
analysis
limitation
```

Allowed `relation_type`:

```text
supports
contradicts
limits
addresses
produces
bounds
substantiates
characterises
differentiates
compares_with
qualifies
refutes
depends_on
duplicates
supersedes
```

Allowed `directness`:

```text
direct
partial
indirect
conflicting
unverified
absent
```

Allowed `scope_match`:

```text
exact
partial
mismatch
unknown
```

Allowed relation `status`:

```text
candidate
verified
contested
rejected
superseded
```

For chain completeness and focus review, a reliable relation must have:

```text
status = verified
directness = direct | partial
scope_match = exact | partial
```

Object endpoints must be `available` or `verified`, have `verified` or `traceable` provenance, and have `checked`, `validated`, `frozen`, or `not_applicable` quality. Other valid enum values preserve work-in-progress and counter-evidence state but do not complete a chain.

Use only these typed relation families:

| Source | Relation | Target |
|---|---|---|
| `source`, `prior_work`, `evidence` | `supports`, `contradicts`, `limits` | `gap`, `innovation` |
| `source`, `prior_work`, `evidence` | `supports`, `contradicts`, `limits`, `refutes` | `claim` |
| `contribution` | `addresses` | `gap` |
| `data` | `produces`, `bounds` | `result` |
| `data` | `supports`, `bounds` | `claim` |
| `data` | `bounds` | `contribution` |
| `result` | `supports`, `contradicts`, `limits`, `qualifies`, `refutes` | `claim` |
| `result`, `claim` | `substantiates` | `contribution` |
| `claim` | `depends_on`, `supersedes` | `claim` |
| `artifact`, `analysis` | `supports` | `claim` |
| `innovation` | `characterises` | `contribution` |
| `innovation` | `compares_with` | `source`, `prior_work` |
| `limitation` | `bounds` | `claim`, `contribution`, `result` |
| same-type `gap`, `contribution`, `claim`, `result`, or `innovation` | `supersedes` | same type |
| `contribution` | `duplicates` | `contribution` |

The core empirical path is:

```text
data --produces--> result --supports/qualifies--> claim --substantiates--> contribution --addresses--> gap
```

Innovation uses a separate path:

```text
source/prior_work/evidence --supports/contradicts/limits--> innovation --characterises--> contribution
```

Do not force the empirical path on every contribution type:

- `empirical_finding` and `case_study` need a data-result-claim-contribution path.
- `method_or_tool` and `evaluation_protocol` need tested results or a bounded artifact/analysis-to-claim path.
- `dataset_or_benchmark` needs traceable data or artifact evidence and quality claims.
- `conceptual_reframing` and `governance_framework` may use direct source/evidence-to-claim support instead of empirical data.

### `contribution_focus.csv`

```text
contribution_id,current_role,core_gap_fit,target_reader_fit,narrative_emphasis,author_locked,section_ids,decision_status,notes
```

Allowed `current_role`:

```text
primary
secondary
enabling
boundary
exploratory
deprioritised
```

Allowed `core_gap_fit`:

```text
direct
partial
weak
unknown
```

Allowed `target_reader_fit`:

```text
high
medium
low
unknown
```

Allowed `narrative_emphasis`:

```text
dominant
balanced
light
absent
unknown
```

Allowed `decision_status`:

```text
current
under_review
approved
superseded
```

`author_locked` is `true` or `false`. This file records current emphasis; it does not authorise a focus change.

### Conditionally Required `contribution_focus_snapshot.json`

This file is not required when strict checking emits no focus candidate. Once `focus_review_candidates` is non-empty, create and validate it before making a focus decision or any focus-related prose edit:

```text
schema_version
intent_ids
current_primary_ids
author_approved_manuscript_path
author_approved_manuscript_sha256
relation_packet_sha256
captured_from_files
status = pending_author_review
```

`schema_version` must be `1`; the ID and file fields are JSON lists; `status` must be `pending_author_review`; hashes are 64-character SHA-256 hex strings or `unavailable`. `intent_ids` must exactly match the affected candidate intent(s), and `current_primary_ids` must exactly match every current primary contribution in those intents. The author-approved manuscript path must be a non-glob path to an existing file inside the project; when its SHA-256 is supplied, the digest must match that file. Each captured-file entry must be an in-project relative path or glob that matches existing files, and the combined patterns must cover every required argument-packet CSV. If a hash cannot be computed, record `unavailable` and the reason as `hash unavailable: <reason>`; do not silently omit the field. The checker reports a blocking snapshot issue whenever a focus candidate exists without a semantically matching snapshot. This snapshot is the frozen before-state used by `/manuscript-reframe`, `/thesis-control`, and the three-attempt revision gate.

### Optional `contribution_focus_decisions.jsonl`

Append one object only after the author decides:

```text
decision_id
before_primary_ids
after_primary_ids
trigger_rule_ids
graph_snapshot_sha256
affected_claim_ids
affected_section_ids
reason
expected_effect
user_approved
created_at
```

Keep the old contribution ID when only emphasis changes. Create a new contribution and link it with `supersedes` when the contribution's meaning or scope changes.
