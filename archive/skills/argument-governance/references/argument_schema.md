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
