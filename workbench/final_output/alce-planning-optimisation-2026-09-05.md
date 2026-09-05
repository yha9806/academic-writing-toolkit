# ALCE real-PDF planning optimisation

Status: technical optimisation in draft PR #41. The Workbench remains retired
under the parent specification's section 13. This does not satisfy the real
author cycle or establish review quality.

## Same-source comparison

The input is the same complete 24-page ALCE PDF as the
[original attempt](alce-real-document-attempt-2026-09-05.json), SHA-256
`ae9868f07f0f7ffaae5346778f79b7827d9ec6b13b1e6aae4dff6b2ffc37a2e1`.
The review request, dependency-free token estimator, local model and per-call
8,000-input / 1,600-output estimated budget are unchanged.

| Measure | Original | Optimised |
|---|---:|---:|
| Detected sections | 482 | 24 |
| Detected chapters | 441 | 13 |
| Extracted blocks | 5,822 | 5,787 |
| Original PDF text regions retained | 6,670 | 6,670 |
| Text-stage requests at estimated 8,000 input tokens | 486 | 44 |

The text-stage request count decreases by **90.9%**. The original heuristic
mistook short prose containing `results`, `methods` or `references`, numeric
table rows and some reference years for headings. The planner also opened
a new request at every section boundary. Whole-title checks and consecutive
packing within each file remove these sources of underfilled requests.
Every material still carries its section, source locator and unchanged text.
Repeated section names no longer reorder the source.

All 6,670 original region texts and coordinates match the earlier extraction,
including 95,150 source characters. Splitting/joining produces different
block counts and 35 additional separator newlines; no original region text
is removed. The canonical region-text-and-geometry SHA-256 matches on both
sides: `b45b252f803ee30b5220ab705840e1baddba736ef4ec91214d5a55e1976fd7da`.
Every new block appears exactly once and in source order in the text plan.

| Estimated input ceiling per call | Text-stage requests |
|---|---:|
| 2,400 | 216 |
| 4,000 | 101 |
| 8,000 | 44 |
| 16,000 | 21 |

These are text-stage counts, **not totals for a complete review**. The default
economy profile remains 4,000. Larger inputs require a suitable model context
window and can affect model reliability. Token estimates depend on the
installed tokenizer and are not the provider's actual usage or a hard context
guarantee. Chapter and cross-section requests depend on earlier results;
unknown chapter roles still require author inspection.

## Retained live attempt

The [machine-readable record](alce-planning-optimisation-2026-09-05.json)
includes implementation hashes and all observed provider usage. A new local
Ollama/Qwen attempt reserved **12 calls**, completed 11 text batches, and then
stopped because a model quote or locator failed exact source validation.
Its completed batches cover 1,401 of 5,787 new blocks. Ten completed responses
were entirely empty reports; none supplied a grounded claim or finding.
Schema-valid completion therefore does not establish substantive review.
Chapter and cross-section stages were not reached. No automatic retry,
quote repair, model switch or failure deletion was performed.

The attempt used a declared ceiling of 80 calls / 800,000 estimated total
tokens, increased from the earlier pilot's 24 / 250,000 so a full attempt
was possible. It stopped on validation failure before those ceilings. The
planning comparison uses identical per-call budgets; this is not a controlled
comparison of runtime, cost or review quality. DeepSeek was not called.

## Verification and reproduction

Local runtime tests: 77 discovered; 76 passed / 1 Windows-only skip with PDF
dependencies, and 67 passed / 10 optional-dependency/platform skips both
without extras and with the optional tokenizer but without PDF extras.
The new checks cover false headings, numeric tables with font changes,
source order, file boundaries, per-call limits under two estimators, and
resuming a version-2 checkpoint without repeating completed requests.
Existing quote validation, full coverage, revision invalidation and budget
pause tests also pass. Gemini advisory review was unavailable because its
API request failed; no independent Gemini approval is claimed.

From `workbench/`, with `documents` extras installed, planning alone makes
no model calls:

```sh
python scripts/check-real-document-planning.py /path/to/gao2023-alce.pdf --output planning.json
```

To compare every original region, add `--baseline-job-dir` pointing to the
original local job directory. To explicitly run the configured local Qwen
model, add `--live-root` pointing to a new checkpoint directory. Existing
directories are rejected so earlier attempts remain intact. The exported
report contains hashes and aggregate results, with no machine paths, PDF
text or model-response bodies. Historical records remain unchanged.

New jobs, explicitly revised documents and new review requirements use
planning version 3. Restoring an old job retains its stored plan and usage;
it does not silently rebatch or rerun prior observations.
