# Abstract numbers: measured against the venue, prompted above its range

Status: draft (2026-10-05; the author asked for it; nothing implemented)

## Problem

The author (2026-10-05): an abstract must not carry too many numbers. A revision on one real manuscript had just
rewritten its abstract to carry more than twice as many quantities as the most number-heavy abstract in its venue's
corpus, where the submitted version had sat near the corpus median. No check saw it:
the prose fingerprint measures the whole manuscript, and the number ledger checks whether a number is right, not
whether the abstract should hold it.

Numbers enter abstracts for good reasons (an editor asks for the main result; a reviewer asks for sample size), so
the check must not push towards zero. It should say when an abstract is outside what its venue publishes.

## Design

- **Measure.** A quantity is a number not attached to letters (`0.85`, `23%`, `1,859`); names with digits (`BM25`,
  `GPT-4o`) and four-digit years are counted apart. Report count, count per 100 words, and the list of quantities.
- **Baseline.** The target's venue corpus (`target.venue_corpus` in the workspace config, the same corpus the venue
  baseline already uses), abstracts extracted from the PDFs. Report the abstract's percentile; prompt above the
  90th, as the prose checks do (global rule 11: percentiles, not min–max).
- **Known bias, stated in the report.** PDF extraction counts list markers ("(1)", "(2)") and running-header dates
  as quantities, so the corpus side is overestimated and the prompt fires late, not early.
- **Prompt, not gate.** The report lists the quantities and asks which carry the main finding; it does not choose.
  When the abstract is pinned, the report goes to the author only.
- **Where it runs.** As a loop check under 摘要, and once per revision round in the overview (abstract quantities:
  submitted version → current).

## Acceptance

- A planted abstract with 5 quantities, 1 year and 3 names with digits is counted 5 / 1 / 3.
- On the real case above (read only), the check reports the revision above the 90th percentile and the submitted
  version below it.
- Synthetic fixtures only in this repository.
