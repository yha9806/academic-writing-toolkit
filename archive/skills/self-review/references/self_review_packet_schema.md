# Self-Review Packet Schema

Create `review_packet/review_manifest.yaml` with this shape:

```yaml
review_mode: self_review_clean_room
allowed_sources:
  - manuscript.md
  - references.bib
  - evidence/claim_register.csv
  - evidence/evidence_matrix.csv
  - evidence/claim_hierarchy.csv
  - evidence/contribution_chain.csv
forbidden_sources:
  - prior_chat_memory
  - unstated_project_assumptions
  - model_background_knowledge_as_evidence
  - unpublished_notes_not_listed_in_manifest
review_outputs:
  - self_review_report.md
advisory_review:
  enabled: false
  provider: ""
  model: ""
  api_key_env_var: ""
  allowed_to_send_sources: false
  allowed_source_subset:
    - manuscript.md
  output_path: advisory/advisory_review.md
```

## Required Keys

- `review_mode`
- `allowed_sources`
- `forbidden_sources`

## Required Forbidden Sources

The manifest should explicitly forbid:

- `prior_chat_memory`
- `unstated_project_assumptions`
- `model_background_knowledge_as_evidence`
- `unpublished_notes_not_listed_in_manifest`

## Source Rules

- Allowed sources must be relative paths inside the packet.
- Absolute local paths should not appear in the manifest.
- Directories may be listed with a trailing slash.
- If a file is needed but missing from `allowed_sources`, add it to the manifest before using it or mark the related finding as unsupported.

## Advisory Review Rules

- `advisory_review` is optional and defaults to disabled.
- Store API key names only, such as `OPENAI_API_KEY` or `GEMINI_API_KEY`.
- Never store API key values in the manifest.
- `allowed_to_send_sources` must be true before any listed source is sent to an external model.
- `allowed_source_subset` must be a subset of `allowed_sources`.
- Advisory output is not evidence; it must be re-grounded against allowed sources.
