# /self-review

Review the user's own manuscript with clean-room anti-contamination controls.

The governing rule is:

```text
self-review truth = explicit review packet + source anchor
```

Use this skill for internal pre-submission checks, self-review, reviewer simulation on your own work, or claim-evidence self-audit where prior chat memory and unstated project knowledge must not become evidence.

## Codex-Only Baseline

Codex can complete self-review with the review manifest, allowed sources, source anchors, and the bundled checker. Gemini, gemini-agent, a second model, or a subagent may be used only as optional advisory context and never as evidence. If `/argument-governance` is unavailable, manually extract the argument spine from manifest-listed sources only.

## Enhanced Advisory Mode

With explicit user approval, a manifest-enabled advisory section, and an API key stored in an environment variable, Codex may request an external second-model pass. Only manifest-approved source subsets may be sent. External comments stay under `Reviewer-risk inference` or advisory notes until Codex re-grounds them against allowed sources.

## Required Packet

Preferred layout:

```text
review_packet/
  review_manifest.yaml
  manuscript.md or manuscript.pdf
  references.bib
  evidence/
  figures/
  tables/
  claims/
```

The manifest should include:

```yaml
review_mode: self_review_clean_room
allowed_sources:
  - manuscript.md
  - references.bib
  - evidence/claim_register.csv
forbidden_sources:
  - prior_chat_memory
  - unstated_project_assumptions
  - model_background_knowledge_as_evidence
  - unpublished_notes_not_listed_in_manifest
advisory_review:
  enabled: false
  provider: ""
  model: ""
  api_key_env_var: ""
  allowed_to_send_sources: false
  allowed_source_subset:
    - manuscript.md
```

## Deterministic Helper

```bash
python3 .claude/skills/self-review/scripts/check_self_review_packet.py review_packet --json
```

The helper checks the manifest, required forbidden-source controls, relative allowed paths, and report section separation.

## Output

The report must keep findings separated:

```text
## Clean-Room Self-Review

### Packet Boundary
### Supported By Packet
### Not Supported By Packet
### Reviewer-Risk Inference
### Revision Actions
```

Supported findings require source anchors. Missing support must be marked as a gap rather than filled from memory.
