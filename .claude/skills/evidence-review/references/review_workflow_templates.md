# Review Workflow Templates

## Evidence Matrix

`evidence/evidence_matrix.csv`

```text
citation_key,title,year,authors,source_type,evidence_status,scope_role,domain,task,key_findings,limits,source_path,provenance,manual_check_needed
```

## Claim Register

`evidence/claim_register.csv`

```text
section_id,claim_id,claim_text,evidence_status,citation_keys,source_paths,evidence_strength,overclaim_risk,boundary_language,manual_check_needed
```

## Citation Plan

`evidence/citation_plan.csv`

```text
section_id,citation_key,citation_role,evidence_type,source_path,use_case,priority,caution_note
```

Citation roles:

- direct_domain_anchor
- clinical_or_domain_problem_framing
- background_context
- methodological_support
- workflow_support
- governance_support
- boundary_support
- unpublished_context
- in_progress_context
- candidate_only_do_not_use

## Remaining Gap Notes

`evidence/remaining_gap_notes.csv`

```text
gap_id,section_id,gap_description,evidence_needed,current_evidence_status,why_gap_matters,next_action
```

## Claim Traceability

`evidence/<section>_claim_traceability.csv`

```text
section_id,subsection_id,paragraph_id,main_claim,citation_keys_used,evidence_status,source_summary_paths,overclaim_risk,boundary_language_used,manual_check_needed
```

## Citation Usage Audit

`evidence/<section>_citation_usage_audit.csv`

```text
citation_key,subsections_used,citation_role,evidence_type,used_correctly,overused,underused,caution_note
```

## Overclaim Audit

For each risk:

```text
- risk:
- status: absent / present / needs_revision
- affected subsection:
- recommended safer wording:
```

