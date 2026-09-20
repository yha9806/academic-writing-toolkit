# The venue baseline

- **Status: draft.** Written 2026-09-20. Not author-approved, not implemented,
  not verified. The decisions in §4 are the ones an approval would be
  approving; the measured numbers in §2 are already checked and are not
  awaiting anything.

## 1. Problem

The prose fingerprint reports where a manuscript sits relative to a baseline
corpus, and the baseline is an input the toolkit assumes already exists. There
is no code here that builds one — eight scripts across five skills, none of
them a corpus builder — so the corpus is assembled by hand, and what it
represents has never been checked by anything.

It has now gone wrong three times, in three different ways:

- **A thesis, 2026-09-06.** `literature/` held Markdown files that were the
  author's own reading notes. A run reported the corpus as "none by the
  author" and two metrics were four percentile points high, discourse markers
  twelve.
- **A journal manuscript, found 2026-09-20.** Its baseline directory held two
  earlier drafts of the manuscript being measured. Every polishing round had
  been measured against it. Now checked by the tool itself.
- **The same manuscript, found the same day.** The directory was named for the
  target journal and holds the manuscript's **own bibliography**. Measured:
  of its PDFs, **none** is an article that journal had published. Every
  "inside the published range" the project had recorded meant *inside the
  range of the papers we cite* and had never meant *reads like what this
  journal publishes*.

The first two are contamination and are fixed. The third is not contamination:
the corpus is exactly what the method asks for. It is that a second question
was never asked, and the directory's name made it look as though it had been.

## 2. What is already measured

- arXiv API, `search_query=jr:"ACM Computing Surveys"`: **139** preprints.
- By submission year: 2026 × 2, 2025 × 6, 2024 × 22, 2023 × 13, 2022 × 16,
  2021 × 18 — **77** in a 2021-and-later window.
- **131 of 139 (94%)** carry an `arxiv:doi`, and **all 131 are `10.1145`**.
  Requiring a DOI costs two papers in the window: 77 → **75**.
- DOI content negotiation returns `container-title` verbatim: `10.1145/3560815`
  and `10.1145/3648354` both answer `ACM Computing Surveys`.
- A PDF fetch from `arxiv.org/pdf/…` returns in about a second.
- Primary categories spread across cs.LG 17, cs.CR 16, cs.CV 12, cs.CL 11,
  cs.HC 10, cs.SE 10, cs.DC 9, cs.AI 8.

## 3. Goals

1. A native capability in this toolkit that **builds** a venue baseline, with
   its sampling frame recorded rather than remembered.
2. A workflow position **before writing**, not at polish time: knowing what the
   venue's prose looks like is useful while drafting and nearly useless as a
   last check.
3. Every claim about "the published range" names which baseline produced it.

## 4. Decisions

- **D1. Two baselines, never merged.** The bibliography baseline answers "am I
  inside the literature I am in conversation with". The venue baseline answers
  "am I inside what this journal prints". A report that does not say which one
  a percentile came from is not a report.
- **D2. Acquisition is the arXiv API, not the publisher.** Free, scriptable,
  within terms, and it sidesteps acm.org returning 403 to a non-browser client.
- **D3. Membership is verified against the registrar, never the author.**
  `journal_ref` is free text — one entry in the measured set reads "Just
  accpeted by ACM Computing Surveys 2026", typo included. A record is admitted
  only if it has a DOI **and** the DOI resolves to a `container-title` equal to
  the venue. This is the method the writing rules already require for
  bibliography entries, applied to corpus construction.
- **D4. The window is part of the frame and is always recorded.** House genre
  drifts; a corpus reaching back to 2001 is a different object from one
  starting in 2021. Default 2021, always printed.
- **D5. Stage-matched, and the limit stated.** These are authors' accepted
  manuscripts, at the same stage as the manuscript being measured, and they
  have not been through ACM copyediting. The comparison is "does this read like
  other people's submissions to the venue", not "like the venue's printed page".
- **D6. Read both sides as PDF.** The measured pipeline asymmetry — 40% in word
  count, a sign change in sentence-length lag-1 — cannot be removed against a
  bibliography baseline, because a published PDF has no source. Against a venue
  baseline it can: point `--target` at the manuscript's own built PDF. This is
  the first baseline for which an apples-to-apples reading exists.
- **D7. Diagnostic, not a target.** Percentiles against the venue baseline are
  read once to answer whether the manuscript reads like the venue's genre. The
  stop rule in the prose method applies unchanged; nothing is edited to move a
  venue percentile.
- **D8. Corpus outside the repository, manifest inside.** PDFs land in a
  directory the operator names, as the existing corpora do. The manifest — the
  verbatim query, the window, and every candidate with its disposition — is
  version-controlled evidence.

## 5. Non-goals

- Predicting acceptance, or estimating any acceptance threshold. The toolkit
  already refuses this: *do not infer venue-specific acceptance thresholds
  unless the venue or rubric is supplied*. A prose distribution is not a rubric.
- Judging whether the topic fits the venue. That is the positioning audit.
- Replacing the bibliography baseline, or letting one stand in for the other.
- Any editing action. This builds a corpus and reports; it does not rewrite.

## 6. Acceptance criteria

1. `build-venue-baseline.py --venue "ACM Computing Surveys" --from-year 2021`
   writes a manifest in which `admitted + rejected_* = candidates`, with a
   reason on every rejection, and admits ≥ 20 documents.
2. The manifest records the query string verbatim, the window, the API
   endpoint, and the retrieval date.
3. A record whose DOI resolves to a different `container-title` is rejected and
   named. Probed with a real DOI from another ACM journal.
4. A record with no DOI is rejected as unverified, and the count is reported —
   not silently dropped.
5. `--dry-run` produces the manifest and downloads nothing.
6. The fingerprint run against the built corpus reports
   `preconditions_checked: true`, `pipeline_mismatch: false` when the target is
   the built PDF, and a full baseline accounting.
7. The prose method's step 0 lists building this corpus as a precondition, and
   the audit skill states that a percentile must name its baseline.
8. Each new test is probed red against the code before the change.
