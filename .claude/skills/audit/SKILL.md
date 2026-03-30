---
name: audit
description: Audit the thesis for data consistency — numbers, percentages, terminology, cross-references between chapters. Use before submission.
allowed-tools: Read, Glob, Grep
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
   - The same concept must use the same term throughout. Flag cases where synonyms are used inconsistently (e.g., "pseudo-understanding" vs "false comprehension" for the same concept).
   - Abbreviations must be defined on first use in each chapter.

   **C. Cross-reference validity**
   - References to other sections (e.g., "as discussed in Section 3.2") must point to sections that exist.
   - References to tables and figures must match actual table/figure numbers.
   - Forward references ("Chapter 6 will show...") must be fulfilled.

   **D. Citation consistency**
   - The same work must be cited with the same author list and year throughout.
   - In-text citations must match the reference list format.

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
| 1 | Critical | Numerical | Ch3 s3.2, Ch5 s5.4 | PUR value differs | 22.5% (Ch3) vs 23.1% (Ch5) | Should be consistent |
| 2 | High | Cross-ref | Ch4 s4.1 | Ref to "Section 3.7" | Section 3.7 | Section does not exist |

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
