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
