# Thesis-Control Schema v3 Adversarial Matrix

## Scope And Boundary

This matrix records structural and human-gate adversarial checks for the
schema-v3 checker, scaffold, and migration helper. It does not test whether a
scholarly claim is true, sufficiently evidenced, or well written. Author
approval remains the authority for edits, escalation decisions, merge, and
release.

Observed results below come from `bash scripts/test.sh` on 2026-07-09. The run
passed all 107 tests. T91-T110 are the dedicated v3 hardening range; earlier
tests are included where they establish a compatibility or approval baseline.

## Matrix

| Surface | Adversarial input | Expected result | Observed result | Regression |
|---|---|---|---|---|
| Checker | Duplicate headers in any control CSV, including conflicting `human_approved` values | Exit 1; `duplicate-column`; no traceback | Pass | T91 |
| Checker | Extra, missing, truncated, invalid-quote, or invalid UTF-8 cells | Exit 1; structured shape/decode issue; no traceback | Pass | T92, T110 |
| Checker | Legacy packet or v2 escalation inspected non-strictly | Non-strict inspection remains available; strict mode requires v3 | Pass | T82, T93 |
| Checker | Approved cycle gate before all three applied contracts have resolved failed audits | Exit 1; `premature-cycle-gate-approval` | Pass | T94 |
| Checker | Approved early diagnosis followed by a completed failure group | Early row never unlocks; distinct cycle gate required | Pass | T95 |
| Checker | Oversized, duplicate, cross-issue, shifted, repeated, or wrong-boundary triggers | Exit 1 with the corresponding structural issue | Pass | T89, T90, T96 |
| Checker | Exact trigger set listed out of attempt order | Exit 1; `misordered-cycle-gate-triggers`; later approved contract remains blocked | Pass | T107 |
| Checker | Multiple resolved failed audits for one applied contract | Count the contract once | Pass | T106 |
| Checker | Passed and failed resolved audits for the same contract | Exit 1; `conflicting-resolved-audits` | Pass | T106 |
| Checker | `status=approved` without human approval, or a non-effective draft gate before a later approved contract | Exit 1; approval/gate issue; no implicit unlock | Pass | T76, T77, T107 |
| Scaffold | Malformed existing header or unsupported extension column | Exit 1 before mutation | Pass | T97, T100 |
| Scaffold | Existing excerpt, spine row, contract row, or review packet collision | Exit 1; project tree byte-identical | Pass | T98 |
| Scaffold | Attempts 1 and 2 without explicit contract IDs | Generate distinct padded IDs and a strict-valid family | Pass | T99 |
| Scaffold | A different existing row makes the full candidate semantically invalid | Exit 1 before mutation with the checker issue | Pass | T108 |
| Scaffold | `thesis_control/` or another owned output component is a symlink | Exit 1; refuse internal symlink; no external write | Pass | T109 |
| Migration | Malformed escalation input while contracts still need migration | Exit 1; legacy contract bytes unchanged | Pass | T101 |
| Migration | One revision column, partial row values, duplicate attempts, or non-sequential attempts | Exit 1 with an author-actionable ambiguity message; no mutation | Pass | T102, T104 |
| Migration | v2 row with one or two triggers | Convert to `early_diagnostic` with empty boundary | Pass | T103 |
| Migration | v2 row with exactly one completed three-failure group | Convert to attempt-ordered `cycle_gate` and derive the final-attempt boundary | Pass | T103 |
| Migration | Oversized, cross-issue, unknown, or incomplete three-trigger v2 row | Exit 1 as ambiguous; no mutation | Pass | T104 |
| Migration | Complete v3 metadata with named extension columns, run twice | Preserve extension values and remain byte-idempotent | Pass | T105 |
| Migration | Owned control directory is a symlink | Exit 1; refuse internal symlink; no external write | Pass | T109 |
| Shared writer | Injected failure after one target replacement | Restore original bytes and remove temporary files | Pass | T110 |

## Acceptance Interpretation

The matrix supports the bounded claim that the current packet state is parsed
unambiguously and that the documented execution gates are internally
consistent. It does not provide a cryptographic event history. In particular,
`approved_after_attempt` is checked against the current ordered failure group;
the author remains responsible for recording approval only after reviewing that
completed group.
