# Abstract numbers: measured against the venue, prompted above its range

Status: draft (2026-10-05; the author asked for it; revised the same day against the author's words and an earlier
measurement found on disk; nothing implemented)

## Problem

The author (2026-10-05): an abstract must not carry too many numbers. A revision on one real manuscript had just
rewritten its abstract to carry more than twice as many quantities as the most number-heavy abstract in its venue's
corpus, where the submitted version had sat near the corpus median. No check saw it:
the prose fingerprint measures the whole manuscript, and the number ledger checks whether a number is right, not
whether the abstract should hold it.

Numbers enter abstracts for good reasons (an editor asks for the main result; a reviewer asks for sample size), so
the check must not push towards zero. It should say when an abstract is outside what its venue publishes.

## Earlier evidence on disk

The first draft of this spec missed a measurement made a week earlier for the same manuscript (private evidence
repository, writing-guides round of 2026-09-28):

- 14 abstracts from the target venue, each number read in context and classed as a **result** (the paper's own
  finding) or **setup or noise** (data size, system counts, list markers, dates, the state of the field). 10 of the
  14 report their findings with no result number; the other 4 carry one to three. The classification is a model's
  draft, made by one reader, on papers chosen by title; it is not the author's.
- The writing guide built in that round (ten published guides, quotes checked against archived originals) says the
  same thing in a rule: results after the problem and the method, and the result numbers cut to one group.

Run on those 14 (2026-10-05, read only), the counter below finds every number classed as a result. It also counts
setup numbers, so its total is the construct "quantities in the abstract", not "result numbers"; a regex cannot tell
the two apart. Before list markers and dates were removed, one abstract with no result number counted 8.

## Design

- **Measure.** A quantity is a number not attached to letters (`0.85`, `23%`, `1,859`); names with digits (`BM25`,
  `GPT-4o`) and four-digit years are counted apart. List markers (`(1)`, `(ii)`, `1)`) and calendar dates are
  removed before counting, on both sides. Report count, count per 100 words, and each quantity with a few words of
  context on either side.
- **Baseline.** The target's venue corpus (`target.venue_corpus` in the workspace config, the same corpus the venue
  baseline already uses), abstracts extracted from the PDFs by the same code. Report the abstract's percentile;
  prompt above the 90th, as the prose checks do (global rule 11: percentiles, not min–max). An abstract the
  extractor cannot find (letter-spaced headings such as `A BSTRACT` are one known cause) is listed as missed, never
  counted as zero; fewer than twenty extracted abstracts is no baseline (the venue baseline's floor).
- **Result numbers are the author's call.** The report lists the quantities and asks which carry the main finding.
  When the workspace keeps the author's marks (`abstract-numbers.tsv`: quantity, context, `result` / `setup`), the
  report also gives the result-number count and repeats the guide's rule; it never marks them itself.
- **Prompt, not gate.** It does not choose what to cut. When the abstract is pinned, the report goes to the author
  only.
- **Where it runs.** As a loop check under 摘要, and once per revision round in the overview (abstract quantities:
  submitted version → current).

## Acceptance

- A planted abstract with 5 quantities, 1 year, 3 names with digits, 3 list markers and 1 date is counted
  5 / 1 / 3, with the markers and the date not counted.
- An abstract whose heading the extractor cannot find is reported as missed, and a corpus with fewer than twenty
  abstracts reports no percentile.
- On the hand-classified abstracts above (private tests, read only), every number classed as a result is counted.
- On the real case above (read only), the check reports the revision above the 90th percentile and the submitted
  version below it.
- Synthetic fixtures only in this repository.
