# Human Eval Handoff Repair

Use `/human-eval-handoff-repair` when reviewing human-evaluation handoff packages, filled annotation CSVs, annotation UI exports, or reviewer returns across package versions.

## What It Checks

- Row counts against target task CSVs.
- Required editable label columns.
- Legal enum values for each audit task.
- Exact stable-key alignment with the target public package.
- Cross-snapshot contamination and old package leakage.
- Simple label-logic warnings.
- Public package safety before annotator release.

## Stable-Key Rule

Never rely on row number, filename, or visible ID alone. A filled CSV is safe for formal aggregation only when it aligns to the target package by the task's stable key and its labels pass schema checks.

If a row cannot be matched exactly, leave the target annotation fields blank and produce refill/import files for manual completion.

## Output Pattern

The skill should produce:

- QC JSON and Markdown summaries.
- Clean or mapped CSVs.
- Lightweight UI import CSVs when useful.
- Unmatched-row reference CSVs.
- Text-only fuzzy mapping candidates marked manual review only.
- A final verdict: `PASS`, `PASS_WITH_MINOR_QC`, `PARTIAL_PASS`, `REFERENCE_ONLY`, or `FAIL_REDO`.

## Typical Prompt

```text
Use /human-eval-handoff-repair to check this filled annotation CSV against the current public handoff package. Tell me which rows can be formally aggregated and generate refill templates for anything unsafe.
```
