---
name: audit
description: Check thesis chapters for consistency before submission — contradictory numbers, terminology drift, and broken cross-references.
allowed-tools: Read, Glob, Grep, Bash
---

# /audit — Thesis Consistency Audit Skill

## Purpose

Scan all thesis chapters for internal data consistency issues: contradictory numbers, inconsistent terminology, broken cross-references, and arithmetic errors. This is a pre-submission quality check.

## Trigger Words

This skill activates on: `audit`, `consistency check`, `check numbers`, `/audit`.

## Workflow

1. **Scan all chapter files** in the `chapters/` directory using Glob. Read each file to extract quantitative claims, terminology, and cross-references.

2. **Check the following categories:**

   **A. Numerical consistency**
   - The same statistic (e.g., accuracy, sample size, p-value) cited in multiple chapters must have the same value.
   - Percentages in a distribution must sum to 100% (with tolerance of +/-1% for rounding).
   - Counts (e.g., "42 models") must match between chapters.

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

   **E. Claim positioning (deterministic, runs before F — positioning is
   not repairable after review; style is)**

   ```
   python3 scripts/audit-claim-positioning.py --base-dir chapters --bib references.bib --json
   ```

   (omit `--bib` when the project has no bibliography file). Report every
   issue it returns: `unsourced-keyword` and `bare-novelty` as **High** — a
   field's vocabulary in use without its literature, or a novelty claim in a
   paragraph that shows no search — `uncited-method` and `dangling-entry` as
   **Medium**. The tool checks that a source is *present* near a claim, never
   that it is the right one, and it cannot tell whether a citing sentence
   says what its source says; do not present its silence as either.

   **F. Prose fingerprint (measurement only; skip when no baseline exists)**

   Only when the project holds a baseline corpus of its *own* reference
   PDFs (`literature/`, twenty or more, the author's own papers excluded):

   ```
   python3 scripts/audit-prose-fingerprint.py --target chapters --baseline literature --exclude '<author-surname>*'
   ```

   Report the distributions under **Measurements**, never as issues: this is
   Advisory by nature. Out-of-range is the hard signal, a percentile is a
   soft one, and clustering matters more than count. Method and stop rules:
   `references/prose-polish-method.md`.

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

### Measurements (category F, when a baseline exists)

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
