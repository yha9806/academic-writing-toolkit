---
name: audit
description: Check thesis chapters for consistency before submission — contradictory numbers, terminology drift, and broken cross-references.
allowed-tools: Read, Glob, Grep, Bash
---

# /audit — Thesis Consistency Audit Skill

## Running Python helpers

Choose the interpreter before running the examples. For a globally installed
copy, use the private runtime recorded by its installer. In a checkout or linked
workspace, use `AWT_PYTHON` when set, otherwise the toolkit's `.venv` (follow the
skill directory link back to the toolkit): `Scripts/python.exe` on Windows,
`bin/python` on macOS/Linux. Without that environment, check that `python`
(Windows) or `python3` (macOS/Linux) actually runs and has the helper's dependencies.
Replace the example's `python3` with that executable. In PowerShell, prefix a
quoted executable with `&`; keep commands on one line and quote file paths.

## Purpose

Scan all thesis chapters for internal data consistency issues: contradictory numbers, inconsistent terminology, broken cross-references, and arithmetic errors. This is a pre-submission quality check.

## Trigger Words

This skill activates on: `audit`, `consistency check`, `check numbers`, `/audit`.

## Workflow

1. **Scan all chapter files** in the `chapters/` directory using Glob. Read each file to extract quantitative claims, terminology, and cross-references.

2. **Check the following categories:**

   **A. Numerical consistency** — read by the model, not checked by a script,
   except for what audit H binds. The three bullets below are what to look for;
   nothing verifies that you looked.
   - The same statistic (e.g., accuracy, sample size, p-value) cited in multiple chapters must have the same value.
   - Percentages in a distribution must sum to 100% (with tolerance of +/-1% for rounding).
   - Counts (e.g., "42 models") must match between chapters.

   For numbers that matter, use audit H instead: it binds the printed value to
   the artifact it came from, so the check survives the next edit.

   **B. Terminological consistency**
   - The same concept must use the same term throughout. Flag cases where synonyms are used inconsistently (e.g., "structured review" vs "systematic review" for the same concept).
   - Abbreviations must be defined on first use in each chapter.

   **C. Cross-reference validity**
   - References to other sections (e.g., "as discussed in Section 3.2") must point to sections that exist.
   - References to tables and figures must match actual table/figure numbers.
   - Forward references ("Chapter 6 will show...") must be fulfilled.

   **D. Citation checks — disabled in this release (disclosed gap)**

   The deterministic citation tiers previously run here are disabled: measured
   against realistic thesis text they produced false high-severity "phantom
   citation" findings on ordinary parentheticals, missed multi-word
   institutional authors, and flagged the comma form that Cite Them Right
   Harvard mandates. Until the checker meets a measured, disclosed
   false-positive rate, do not run it and do not present citation
   consistency as audited. Reference integrity is still covered by
   `/verify-refs` (BibTeX records) and by the notes-file contract lint.

   **E. Claim positioning (deterministic, runs before F and G — positioning
   is not repairable after review; style is)**

   ```
   python3 .claude/skills/audit/scripts/audit-claim-positioning.py --base-dir chapters --bib references.bib --json
   ```

   (omit `--bib` when the project has no bibliography file). Report every
   issue it returns: `unsourced-keyword` and `bare-novelty` as **High** — a
   field's vocabulary in use without its literature, or a novelty claim in a
   paragraph that shows no search — `uncited-method` and `dangling-entry` as
   **Medium**.

   Measured precision, one manuscript, 2026-09-20: the checker returned 11
   issues and 9 were false, all from three mechanisms now fixed — a
   `\keywords{}` block wrapped across source lines so a term matched only its
   own declaration; the bare word "novelty" inside the manuscript's own method
   name, and inside two sentences that *refuse* the claim; and a natbib
   optional argument (`\citep[p.~12]{key}`) that made the citation invisible,
   so a method cited in its own sentence was reported as uncited. After the
   fixes it returns the 2 that reading had already confirmed. That is n=1 and
   not a rate — but it is the reason to read every issue against the source
   before writing it into a report at High, exactly as category D's disabled
   tiers required.

   For a requested claim-scope or contribution review, consult
   `references/argument-licence/argument-level-lock.md`. Separate the field
   gap, delivered contribution, observed finding and extrapolation; report
   the six-line claim licence and any unsupported transition with a text or
   evidence anchor. This is an Advisory reading task. Do not create standing
   CSV ledgers or infer scientific validity from a checker result. Existing
   legacy packets can be interpreted with the schema and checks linked in
   `references/argument-licence/README.md`.

   **H. Number ledger — is this the artifact's number, and is it scoped?**

```
python3 .claude/skills/audit/scripts/audit-number-ledger.py --base-dir . --ledger numbers.tsv --json
```

A row binds one printed value to the file it came from:
`printed`, `in_artifact`, `scope`, `artifact`, `locator`. Two value columns
because they differ in practice — a figure writing `0.635` against prose
printing `63.5\%` — and the relation is recorded, never inferred. Report
`locator-not-in-artifact`, `value-not-in-locator`, `printed-artifact-mismatch`,
`number-not-in-manuscript` and `scope-missing` as **Critical**;
`unledgered-number` is a coverage list, not a finding. An empty ledger exits 2.

`scope` is matched literally: pick a token the correct sentences contain, or
`-`. On a real manuscript the first token tried flagged two sentences that carry
the scope in other words; `technique` passed both.

**G. Claim ledger — does a LaTeX manuscript's claim match its archived source?**

   ```
   python3 .claude/skills/audit/scripts/audit-claim-ledger.py --base-dir . --ledger ledger.tsv --json
   ```

   For manuscripts kept as `.tex` (which audit F does not read). The ledger is a
   TSV with the columns `claim, cite_key, snippet, source_file, level`: one row
   binds one manuscript sentence to one verbatim snippet in one archived source.
   Report `snippet-not-in-source`, `claim-not-in-manuscript`,
   `key-not-in-claim-sentence`, `source-file-missing` and
   `negative-claim-without-fulltext` as **High**; `unledgered-assertion` as
   **Medium**; `qualifier-dropped` and `unledgered-credit` are prompts, not
   findings. Exit 2 means no ledger row was checked at all — report that as
   **not audited**, never as clean. `--pairs` prints the claim/snippet pairs so
   a reader can judge what the audit does not: whether a claim says more than
   its snippet.

   **F. Citation fidelity — does the citing sentence match its source?**

   ```
   node .claude/skills/audit/scripts/audit-citation-fidelity.mjs --base-dir . --json
   ```

   (needs the guards built once: `npm --prefix guards install && npm --prefix guards run build`.)
   Exit 2 with `nothing_checked: true` means the audit found no citation under
   `chapters/**/*.md` — report it as **not audited**, never as clean. For a LaTeX
   manuscript, `not_covered` counts the `\cite` commands, distinct keys and
   files this audit does not read — under the whole `--base-dir`, so point it
   at the manuscript directory rather than at a repository that also holds
   archived copies, or the count will be a multiple of the truth.
   `--allow-empty` accepts an empty workspace on purpose. An empty `findings`
   list is only a result when `corpus_files` and `sentences_checked` say
   something was read.
   Report `quote-not-in-source` and `page-mismatch` as **High** — a quoted
   span that is not verbatim in the source's notes or PDF, or a page that the
   source contradicts — and `notes-missing` as **Medium**. `low-overlap` is
   **experimental**: list it under Measurements as a prompt to re-read, never
   as an issue; no false-positive rate has been measured for it yet. State
   the tool's own limit in the report verbatim: it does **not** detect a
   sentence that inverts its source in the source's own words — the failure
   that mattered most on a real manuscript — and that still requires
   reading. Every finding here is a proxy; a finding is a reason to open the
   source, not a verdict.

   **G. Prose fingerprint (measurement only; skip when no baseline exists)**

   Only when the project holds a baseline corpus of its *own* reference
   PDFs (`literature/`, twenty or more, the author's own papers excluded):

   ```
   python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target chapters --baseline literature --exclude '<author-surname>*'
   ```

   The tool now checks that precondition itself rather than trusting the
   flag: it measures how much of the target's 4-gram vocabulary each baseline
   document contains, and a document that looks like a draft or a copy of the
   target is named in `baseline_suspect`. When one is found it **withholds
   every percentile and exits 2** — not 1, which means "measured, something is
   out of range". Exclude the file, or pass `--allow-overlap` if the overlap
   is intended; the waiver restores the percentiles but still reports
   `preconditions_checked: false`, because a waiver is not a met precondition.

   Two further fields have to be read before the percentiles mean anything.
   `baseline_too_short` names every document that loaded but fell under the
   1500-word floor, so `baseline_documents` plus the skipped, too-short and
   excluded lists account for every candidate in the directory; a count that
   does not close means the corpus is not what you think it is.
   `pipeline_mismatch` is true when the target is read as stripped markup and
   the baseline as printed PDF, which is what the documented invocation above
   does: a percentile then compares two readings, not two documents. When the
   target's own build sits beside it the tool measures both readings and puts
   them in `pipeline_cross_check`. On one real manuscript the word count --
   the denominator of every per-1k rate -- differed by 40% between them and
   sentence-length lag-1 changed sign, so quote the cross-check rather than
   treating the percentiles as exact.

   **Two baselines, and a percentile that does not name its own is not a
   result.** The corpus above is the project's bibliography: it answers whether
   the prose sits inside the literature the manuscript argues with. Build the
   other one before drafting, not at polish time:

   ```
   python3 .claude/skills/audit/scripts/build-venue-baseline.py --venue "<journal>" --from-year 2021 --out <corpus-dir> --manifest <repo>/venue_manifest.json
   ```

   It admits a record only when its DOI resolves to the venue's registered
   `container-title`, writes every candidate's disposition so the manifest's
   arithmetic closes, and exits 2 with `VENUE_CORPUS_TOO_SMALL` rather than
   returning a short corpus that reads like a complete one. Run the fingerprint
   a second time against it, with `--target` pointing at the manuscript's built
   **PDF** — against a venue corpus both sides go through the same extraction,
   which is the one case where `pipeline_mismatch` can be false. Read it once,
   to answer whether the manuscript reads like the venue's genre. Do not edit
   to move a venue percentile; the stop rule is unchanged.

   Report the distributions under **Measurements**, never as issues: this is
   Advisory by nature. Out-of-range is the hard signal, a percentile is a
   soft one, and clustering matters more than count. Always report
   `preconditions_checked` beside them: `outliers: []` on an unverified
   baseline says nothing, and reading it as a pass is the failure this scan
   was added for. Method and stop rules: `references/prose-polish-method.md`.

3. **Output the audit report** using the format below.

## Output Format

```
## Audit Report -- {YYYY-MM-DD}

### Summary

- **Critical**: {N} issues (contradictory data)
- **High**: {N} issues (broken references, missing definitions)
- **Medium**: {N} issues (terminology inconsistency, minor arithmetic)

### Issues

| # | Severity | Category | Location | Issue | Current | Expected |
|---|----------|----------|----------|-------|---------|----------|
| 1 | Critical | Numerical | Ch3 s3.2, Ch5 s5.4 | Sample size differs | 120 (Ch3) vs 125 (Ch5) | Should be consistent |
| 2 | High | Cross-ref | Ch4 s4.1 | Ref to "Section 3.7" | Section 3.7 | Section does not exist |

### Measurements (category G when a baseline exists; category F's experimental low-overlap prompts)

{Per metric: rate, clustering (gap CV), longest gap — with the baseline's
range and where the manuscript sits. Numbers, not verdicts.}

### Recommendations

{Grouped by severity, brief notes on how to resolve each issue.}
```

## Severity Levels

- **Critical**: The same quantitative claim has different values in different chapters. This directly undermines thesis credibility.
- **High**: Broken cross-references, undefined abbreviations on first use, missing table/figure numbers.
- **Medium**: Inconsistent terminology that does not cause factual error, minor rounding discrepancies within tolerance.

## Constraints

1. **Never auto-fix.** List all issues for the user to review and decide. The user may choose to fix selectively.
2. **No emoji** in output.
3. **Report all instances**, not just the first occurrence. If a statistic appears in 4 chapters with 2 different values, list all 4 locations.
4. **Be specific** about locations. Provide chapter number, section number, and surrounding context so the user can find the issue quickly.
5. **Do not flag stylistic issues.** This skill checks data consistency, not prose quality.
