# Release Evidence State Schema

Release governance uses three states so agent-assisted drafts, verified files, and final human evidence stay visibly separate.

| State | Meaning | Allowed use | Promotion gate |
| --- | --- | --- | --- |
| `draft_advisory` | Agent review, Gemini review, prefill output, simulation, draft label, reviewer note, or provisional working file. | Planning, triage, risk review, candidate wording, and follow-up tracking. | Cannot support final claims. Requires artifact verification or human confirmation before promotion. |
| `verified_artifact` | A concrete file, count, checksum, manifest, figure, table, dataset slice, or export has been checked against an exact ref or named external artifact. | Artifact existence, provenance, counts, checksums, and bounded claims within the verified scope. | Requires a command, checksum, manifest, or manual artifact check recorded in the packet. |
| `human_final` | A human reviewer, adjudicator, coordinator, or author has explicitly confirmed the evidence according to the project gate. | Human-label claims, adjudication conclusions, reviewer decisions, final wording approvals, and release sign-off. | Requires explicit human confirmation fields, reviewer identity or role, review date, and matching denominator or scope. |

## Minimal Packet Schema

Required files:

- `release/release_scope.md`
- `release/canonical_refs.csv`
- `release/local_asset_inventory.csv`
- `release/artifact_anchors.csv`
- `release/evidence_gates.csv`
- `release/claim_ledger.csv`
- `release/verification_report.md`

Required CSV columns:

| File | Columns |
| --- | --- |
| `canonical_refs.csv` | `ref_name`, `sha`, `date`, `status`, `canonical_for`, `caveat` |
| `local_asset_inventory.csv` | `path`, `status`, `file_count`, `size`, `role`, `release_action` |
| `artifact_anchors.csv` | `artifact_id`, `source_ref`, `source_path`, `count_or_checksum`, `evidence_state`, `verified_by`, `claim_supported` |
| `evidence_gates.csv` | `gate_id`, `artifact_id`, `evidence_state`, `human_confirmed`, `reviewer`, `review_date`, `validator`, `status` |
| `claim_ledger.csv` | `claim_id`, `claim_text`, `artifact_ids`, `evidence_state`, `denominator`, `scope_boundary`, `human_gate_required`, `status` |

## Gate Rules

1. `draft_advisory` rows must not be described as final evidence.
2. `verified_artifact` rows need an exact ref, artifact path, manifest, count, checksum, or recorded manual check.
3. `human_final` rows need explicit confirmation, reviewer or coordinator identity, review date, and a denominator or scope boundary.
4. Agent or Gemini review can flag risks, but it cannot promote any row to `human_final`.
5. Repository checks prove repository state only; they do not prove venue, ethics, licensing, or scientific compliance.
