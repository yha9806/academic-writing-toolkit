# Evidence Status Schema

| Status | Meaning | Allowed use |
| --- | --- | --- |
| `verified_full_text_supported` | Full text or structured full-text notes have been reviewed locally. | Can support claims within verified scope. |
| `published_anchor_supported` | Published direct anchor for the central review domain. | Can support central claims with stated cautions. |
| `direct_domain_full_text_supported` | Full-text evidence directly studies the target domain. | Domain-specific claims. |
| `background_supported` | Full-text evidence from an adjacent background domain. | Context only. |
| `methodological_support_only` | Evidence supports method rationale. | Method framing, not target-domain validation. |
| `workflow_support_only` | Evidence supports workflow or decision-support framing. | Design logic, not direct validation. |
| `governance_support_only` | Evidence supports reporting, audit, traceability, or lifecycle governance. | Governance design, not clinical or empirical correctness. |
| `boundary_supported` | Scope or limitation boundary derived from evidence-control logic. | Prevents overclaiming. |
| `metadata_only` | Bibliographic metadata only. | Candidate tracking only. |
| `abstract_only` | Abstract but no verified full text. | Background scouting only unless explicitly allowed. |
| `candidate_placeholder_only` | Candidate record without verified evidence. | Do not use as evidence. |
| `unpublished_work_context_only` | Unpublished thesis, pre-submission, or under-review work. | Context only, not published literature. |
| `in_progress_work_context_only` | In-progress system or experiment. | Context only, not validated evidence. |
| `insufficient_evidence` | Claim lacks adequate support. | Revise, remove, or mark as gap. |

## Rules

1. Direct evidence must match the target domain, task, data type, and claim level.
2. Adjacent-domain evidence cannot validate target-domain performance.
3. Method evidence supports rationale, not completed validation.
4. Outcome claims require outcome evidence.
5. A visible feature is not automatically a diagnosis.
6. Auditability, provenance, or structured reporting is not clinical validation.
7. If sample size or metadata conflicts, preserve the caution.

