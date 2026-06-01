# /release-governance - Release Evidence Governance

Run `/release-governance` before manuscript submission, rebuttal, camera-ready work, dataset release, artifact handoff, or claim-register freeze when claims depend on multiple refs, local assets, human labels, or agent-assisted drafts.

The core rule is:

```text
release truth = ref + artifact + gate
```

Use it after `/evidence-review` and `/audit` when the work moves from drafting into release or rebuttal hardening.

## What It Produces

- `release/release_scope.md`
- `release/canonical_refs.csv`
- `release/local_asset_inventory.csv`
- `release/artifact_anchors.csv`
- `release/evidence_gates.csv`
- `release/claim_ledger.csv`
- `release/verification_report.md`

## Evidence States

The release packet uses:

- `draft_advisory` for agent reviews, Gemini reviews, prefills, simulations, and provisional notes
- `verified_artifact` for checked files, manifests, counts, checksums, tables, figures, and exports
- `human_final` for explicit human confirmation with reviewer identity or role, review date, and matching scope

Agent or Gemini review is useful as advisory risk review, but it cannot promote evidence to `human_final`.

## Typical Use

```text
/release-governance Build a release packet for this camera-ready artifact using local refs only.
```

```text
/release-governance Audit whether these human label claims are supported by explicit confirmation gates.
```

```text
/release-governance Prepare a rebuttal handoff with canonical refs, artifact anchors, and residual risks.
```

## Optional Check

The skill includes a lightweight helper:

```bash
python .claude/skills/release-governance/scripts/check_release_packet.py .
```

It checks required packet files, CSV/JSON/YAML readability, legal evidence-state values, required columns, local absolute paths, and unresolved template markers. YAML files use PyYAML when installed; otherwise the helper applies a basic local syntax check for simple mappings and lists. It does not replace expert review, venue checks, ethics checks, licensing checks, or scientific validation.
