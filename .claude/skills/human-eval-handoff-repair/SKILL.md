---
name: human-eval-handoff-repair
description: Use when validating, repairing, or mapping human-evaluation handoff packages, filled annotation CSVs, rebuttal annotation UIs, or reviewer annotation returns across package versions. Applies to checking row alignment, detecting cross-snapshot contamination, converting old labels to current schemas, generating refill/import CSVs, and deciding whether filled annotations are safe for formal aggregation.
allowed-tools: Read, Glob, Grep, Bash, Write
---

# Human Eval Handoff Repair

Use this skill when the user asks to inspect, repair, migrate, or validate human-evaluation packages or filled annotation CSVs, especially when multiple package versions exist.

## First Principle

Never trust row number, filename, or visible ID alone. Treat a filled CSV as usable only after it is aligned to the target public package by stable task-specific keys and its editable labels pass schema checks.

Do not fix labels by guessing. If a row cannot be matched safely, leave its annotation fields blank and produce a refill/import template plus an unmatched reference file.

## Inputs To Locate

- Target public handoff package folder or ZIP.
- Filled CSVs from annotators.
- Any older package claimed as the source version.
- Current task schemas from the target UI data or target task CSVs.
- If relevant, QC reports from the target package.

Prefer a user-specified output directory. If none is specified, write generated reports and repaired files under `codex_outputs/` in the current workspace. Avoid synced personal document folders unless the user explicitly asks for them.

## Task Types And Stable Keys

Use these stable keys before copying any labels:

- Claim Warrant Audit: `item_id`, `tradition`, `medium`, `period`, `layer`, `dimension_id`, `claim_text`.
- Release Suitability Audit: `item_id`, `source_bucket`, `pipeline_mode`, `option_a_source`, `option_b_source`, `governed_option`, `option_a_text`, `option_b_text`.
- Card Faithfulness Spot Audit: `audit_field_id`, `tradition`, `card_type`, `dimension_id`, `field_name`, `field_value`, `source_reference_excerpt`.

If the exact stable key does not match, do not formally aggregate the row. Text-only fuzzy candidates may be generated for manual review, but must not be treated as validated mappings.

## Editable Label Columns

Claim Warrant Audit editable columns:

- `support_source`
- `overreach`
- `certainty_calibration`
- `recommended_action`
- `annotator_confidence`
- `notes`

Release Suitability Audit editable columns:

- `suitability_decision`
- `reason_primary`
- `risk_in_worse_option`
- `annotator_confidence`
- `notes`

Card Faithfulness Spot Audit editable columns:

- `field_status`
- `field_provenance`
- `notes`

Only copy editable label columns. Never copy old evidence text, image paths, metadata fields, or UI-only columns into a new package.

## Label Schema Checks

Claim legal values:

- `support_source`: `visual_observation`, `metadata_context`, `card_or_expert_context`, `b0_excerpt`, `mixed`, `none`
- `overreach`: `no_overreach`, `minor_overreach`, `major_overreach`, `unsupported`
- `certainty_calibration`: `well_calibrated`, `slightly_overstated`, `clearly_overstated`, `uncertain_or_not_checkable`
- `recommended_action`: `accept`, `revise`, `reject`, `filter_or_abstain`
- `annotator_confidence`: usually `1` to `5`

Release legal values:

- `suitability_decision`: `A_better`, `B_better`, `tie_both_ok`, `tie_both_bad`, `abstain_required`
- `reason_primary`: target package enum only; validate from the target CSV or UI schema.
- `risk_in_worse_option`: target package enum only; validate from the target CSV or UI schema.
- `annotator_confidence`: usually `1` to `5`

Card legal values:

- `field_status`: `faithful`, `over_specific`, `unsupported`, `wrong`, `unclear`
- `field_provenance`: `expert_critique`, `metadata`, `visual_observation`, `accepted_domain_context`, `none`, `unclear`

Normalize harmless spelling and casing only when the mapping is deterministic. Otherwise flag the value and leave it blank.

## Required QC Procedure

For every filled CSV:

1. Count rows against the target task row count.
2. Check required label columns are present.
3. Check all non-empty labels are legal enum values.
4. Compare non-label/source columns with the target blank CSV.
5. Compute exact stable-key overlap with the target package.
6. Identify whether the filled CSV matches the current package, an older package, or neither.
7. Run simple logic checks.
8. Produce a QC JSON and Markdown summary.

Important logic flags:

- Claim: `support_source=none` with `recommended_action=accept`.
- Claim: `overreach=unsupported` with `recommended_action=accept`.
- Claim: `recommended_action=filter_or_abstain` with `overreach=no_overreach`.
- Claim: `recommended_action=reject` while `support_source` is not `none` and `overreach=no_overreach`.
- Release: `abstain_required` with a confident preference reason.
- Release: `A_better` or `B_better` with notes saying both options are unusable.
- Card: `field_status=faithful` with `field_provenance=none`.
- Card: `field_status=wrong` with strong provenance unless notes justify it.

Logic flags are review warnings, not automatic invalidation.

## Decision Categories

- `PASS`: exact target alignment, legal labels, no serious logic issues.
- `PASS_WITH_MINOR_QC`: exact alignment and legal labels, but has small note or logic warnings requiring spot check.
- `PARTIAL_PASS`: some rows safely map by stable key; use only mapped rows, refill unmatched rows.
- `REFERENCE_ONLY`: old package or fuzzy/text-only mapping; useful for guidance but not formal aggregation.
- `FAIL_REDO`: no safe stable alignment, major contamination, missing required labels, or wrong task schema.

## Mapping And Repair Rules

When migrating old filled data to a current package:

1. Start from the current target blank task CSV.
2. Build exact stable-key lookup for current rows.
3. For each old filled row, copy only editable label columns if exactly one current row matches the stable key.
4. Leave unmatched current rows blank.
5. Save unmatched old rows separately for manual review.
6. Save a lightweight import CSV with only ID/key columns plus editable label columns when the UI import is sensitive to long evidence text.
7. Never overwrite current evidence fields with old package evidence.

If stable overlap is low, explain that the old annotations may reflect a different snapshot and should not be imported as formal evidence.

## Package-Level Public Handoff Checks

Before saying a package is safe for annotators, scan public UI/data/CSV files for forbidden internal or old-version markers.

Forbidden public markers commonly include:

- `claim_master`
- `release_master`
- `Claim Warrant Master QC`
- `Release Suitability Master QC`
- `claim_warrant_audit_master.csv`
- `release_suitability_master.csv`
- `card_context_snapshot`
- `source_result_item_id`
- `metadata_item_id`
- `mapping_status`
- `snapshot_row_hash`
- old package names such as `mapped_v5_current_20260531`, `handoff_with_images_20260529`, `filled3_normalized`, `fallback_card_faithfulness`

Expected public tasks for this rebuttal package pattern:

- Claim Warrant Annotator A
- Claim Warrant Annotator B
- Release Suitability Annotator A
- Release Suitability Annotator B
- Card Faithfulness Spot Audit

Master/coordinator files must be absent from public UI loading. If retained, place them in `coordinator_only/` or a separate coordinator-only archive.

## Evidence Text And Image Checks

Check that evidence text is not legacy-short truncated. Watch for old uniform limits:

- `visual_observations` around 900 characters ending in `...`
- `b0_excerpt` around 700 characters ending in `...`
- `source_reference_excerpt` around 900 characters ending in `...`
- `field_value` around 1000 characters ending in `...`

A few long fields may still end in `...` only if they hit a new high limit such as 8000 to 12000 characters. English source text is authoritative; translated text is auxiliary reading support unless the package states otherwise.

Verify images exist and that the UI can load representative rows from all task types.

## Card Faithfulness Caveat

For Card Faithfulness, a field/source mismatch can be the thing being audited, not necessarily a package bug. Example: if `field_value` discusses one iconographic context but `source_reference_excerpt` is about a different work, the correct human action may be `field_status=wrong` or `unsupported` and `field_provenance=none`.

Do not confuse this with Claim/Release cross-snapshot contamination. Claim/Release rows evaluate model outputs for a specific image; if claim/release text comes from another snapshot, the metric is invalid.

## Outputs To Produce

For validation or repair tasks, return:

- Clean or mapped CSVs.
- Lightweight UI import CSVs when useful.
- Unmatched rows reference CSV.
- Text-only candidate mapping CSV, clearly marked manual review only.
- QC JSON and QC Markdown.
- ZIP path and SHA256 if packaging outputs.
- Short final verdict stating exactly what can be formally used and what must be refilled.

## User-Facing Summary Pattern

Keep the final answer direct:

- Current verdict: usable, partial, or redo.
- Exact counts, e.g. `164/200 safe mapped, 36 need refill`.
- Paths to outputs.
- Any row IDs needing spot check.
- Clear warning if a file is reference only, not formal human evidence.
