# Release Workflow Templates

These templates are intentionally file-driven. They are for manuscripts, datasets, review packets, artifact bundles, claim registers, rebuttal packages, and camera-ready checks.

## Scope

`release/release_scope.md`

```text
# Release Scope

Scope date: 2026-05-31
Paper/artifact: Generic review packet
Deadline/use: collaborator handoff
Included refs: refs/heads/main at abcdef1234567890
Excluded refs: none
Open question: whether an optional asset should stay local-only
```

## Canonical Refs

`release/canonical_refs.csv`

```text
ref_name,sha,date,status,canonical_for,caveat
main,abcdef1234567890,2026-05-31,clean,manuscript,none
```

## Local Asset Inventory

`release/local_asset_inventory.csv`

```text
path,status,file_count,size,role,release_action
figures/source/tracked.png,tracked,1,42K,figure source,keep tracked
data/private-cache,ignored,120,80M,local review cache,exclude and document boundary
```

Allowed status values can be project-specific, but common values are `tracked`, `ignored`, `untracked`, `external-store`, and `generated`.

## Artifact Anchors

`release/artifact_anchors.csv`

```text
artifact_id,source_ref,source_path,count_or_checksum,evidence_state,verified_by,claim_supported
fig1,main,figures/source/tracked.png,sha256:abc,verified_artifact,manual checksum,figure provenance
```

## Evidence Gates

`release/evidence_gates.csv`

```text
gate_id,artifact_id,evidence_state,human_confirmed,reviewer,review_date,validator,status
gate1,fig1,human_final,true,Reviewer One,2026-05-31,manual packet review,passed
```

Use `draft_advisory` for agent or Gemini reviews. Use `verified_artifact` for deterministic artifact checks. Use `human_final` only for explicit human confirmation.

## Claim Ledger

`release/claim_ledger.csv`

```text
claim_id,claim_text,artifact_ids,evidence_state,denominator,scope_boundary,human_gate_required,status
c1,The figure is anchored to a tracked source artifact,fig1,verified_artifact,one figure,provenance only,false,supported
```

Check every row for:

- stale denominators
- subset-to-universe inflation
- "final", "submitted", "merged", or "human" wording unsupported by the gate
- local-only assets used as if they were release artifacts
- advisory reviews used as final evidence

## Verification Report

`release/verification_report.md`

```text
# Verification Report

Canonical refs:
- main at abcdef1234567890 -> manuscript and tracked artifacts

Advisory reviews:
- Gemini scope review -> risks reviewed; no evidence-state promotion

Verification:
- python .claude/skills/release-governance/scripts/check_release_packet.py . -> clean
- git diff --check -> clean

Residual risk:
- Optional external asset still needs owner decision before submission.
```

## Handoff Packet

End release or rebuttal handoff with:

| Item | Location | Ref/SHA | Owner | Next action |
| --- | --- | --- | --- | --- |
| Manuscript | `chapters/` or final export | exact SHA | author | final venue checklist |
| Artifact manifest | `release/artifact_anchors.csv` | exact SHA | maintainer | checksum review |
| Claim ledger | `release/claim_ledger.csv` | exact SHA | reviewer | approve or revise unsupported claims |
