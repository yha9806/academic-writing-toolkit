# /audit — Consistency Check

Scan all thesis chapters for internal data consistency: contradictory numbers, inconsistent terminology, broken cross-references, citation mismatches.

---

## What It Does

`/audit` reads every chapter file and checks for four categories of internal inconsistency:

1. **Numerical consistency** — the same statistic must have the same value everywhere
2. **Terminological consistency** — the same concept must use the same term everywhere
3. **Cross-reference validity** — section and figure references must point to things that exist
4. **Citation consistency** — the same work must be cited the same way everywhere

It produces a severity-graded report but **never auto-fixes anything**. You decide which issues to address.

---

## When To Use

| Scenario | Command |
|----------|---------|
| Pre-submission quality check | `/audit` |
| After integrating new material | `consistency check` |
| Spot-check numbers | `check numbers` |

### Trigger Words

The skill activates on: `audit`, `consistency check`, `check numbers`, `/audit`.

### When in the pipeline

Run `/audit` after `/integrate` (new material may introduce inconsistencies) and before `/export` (catch problems before generating submission documents).

---

## Internal Workflow

```
User says "/audit"
│
├─ 1. Scan all chapter files (Glob: chapters/*)
│     Read each file completely
│
├─ 2. Extract and cross-reference:
│
│     A. Numbers — find all quantitative claims
│        "42 models" in Ch2 vs "42 models" in Ch5 → OK
│        "22.5% PUR" in Ch3 vs "23.1% PUR" in Ch5 → CRITICAL
│        Percentages in a distribution → must sum to 100% (±1%)
│
│     B. Terminology — find concept definitions and usage
│        "pseudo-understanding" in Ch3 vs "false comprehension" in Ch5
│        → flag inconsistent terminology
│        Abbreviations → must be defined on first use per chapter
│
│     C. Cross-references — find all "Section X.Y" and "Chapter N" refs
│        "as discussed in Section 3.7" → check Section 3.7 exists
│        "see Table 4.2" → check Table 4.2 exists
│        "Chapter 6 will show..." → check Chapter 6 fulfils this
│
│     D. Citations — find all (Author, Year) references
│        "Goodman (1968)" in Ch2 vs "Goodman (1969)" in Ch3 → flag
│        Same author cited with different co-author lists → flag
│
├─ 3. Classify by severity
│     Critical: contradictory data
│     High: broken references, missing definitions
│     Medium: terminology inconsistency, minor rounding
│
└─ 4. Output the audit report
```

---

## Practical Walkthrough

### Scenario: Pre-submission audit of an 8-chapter thesis

**You type:**
```
/audit
```

**The agent produces:**

```
## Audit Report -- 2026-03-30

### Summary

- **Critical**: 2 issues (contradictory data)
- **High**: 3 issues (broken references, missing definitions)
- **Medium**: 4 issues (terminology inconsistency)

### Issues

| # | Severity | Category | Location | Issue | Current | Expected |
|---|----------|----------|----------|-------|---------|----------|
| 1 | Critical | Numerical | Ch3 S3.5.2, Ch8 S8.2 | PUR strict value differs | 0.46% (Ch3) vs 0.48% (Ch8) | Should be consistent |
| 2 | Critical | Numerical | Ch5 Table 5.4 | Percentages sum to 98.7% | 98.7% | 100% (±1%) |
| 3 | High | Cross-ref | Ch4 S4.1 | Ref to "Section 3.7" | Section 3.7 | Section does not exist |
| 4 | High | Cross-ref | Ch6 S6.3 | "see Table 5.5" | Table 5.5 | No Table 5.5 in Ch5 |
| 5 | High | Terminology | Ch2, Ch5 | Abbreviation "VLM" not defined | Used without definition in Ch5 | Define on first use |
| 6 | Medium | Terminology | Ch3, Ch6 | "pseudo-understanding" vs "false understanding" | Both used | Pick one term |
| 7 | Medium | Terminology | Ch4, Ch7 | "evaluation rubric" vs "scoring rubric" | Both used | Pick one term |
| 8 | Medium | Citation | Ch2, Ch5 | "Radford et al. (2021)" vs "Radford and Kim (2021)" | Inconsistent author list | Use consistent format |
| 9 | Medium | Numerical | Ch1, Ch8 | "8 cultural traditions" vs "9 traditions" | Differs by 1 | Verify correct count |

### Recommendations

**Critical — fix immediately:**
1. Verify PUR strict value from source data. Update all chapters to match.
2. Re-check Table 5.4 arithmetic. One percentage may need adjustment.

**High — fix before submission:**
3. Section 3.7 does not exist. Either create it or update the reference to S3.6.
4. Table 5.5 does not exist. Check if Table 5.3 was intended.
5. Add "VLM: Visual Language Model" definition on first use in Ch5.

**Medium — recommended fixes:**
6-7. Choose one term for each concept and search-replace across all chapters.
8. Check the original CLIP paper for the correct author list.
9. Count cultural traditions in the dataset and update all references.
```

---

## Severity Levels

| Level | Meaning | Impact |
|-------|---------|--------|
| **Critical** | Same quantitative claim has different values in different chapters | Directly undermines thesis credibility. Examiners will catch this. |
| **High** | Broken cross-references, undefined abbreviations, missing tables/figures | Reader cannot follow the text. Indicates incomplete editing. |
| **Medium** | Inconsistent terminology, minor rounding within tolerance | Does not cause factual error but suggests lack of polish. |

---

## What It Checks vs. What It Doesn't

| Checks | Does NOT check |
|--------|---------------|
| Numbers matching across chapters | Whether numbers are correct (that's `/verify`) |
| Same concept using same term | Prose quality or style |
| Cross-references pointing to real sections | Grammar or spelling |
| Citations formatted consistently | Whether citations are real (that's `/verify`) |
| Percentage distributions summing to 100% | Whether the research methodology is sound |

---

## Tips

1. **Run after every `/integrate` session.** New material is the primary source of inconsistencies. A quick audit after integration catches problems early.

2. **Fix Critical issues first.** These are the ones examiners will notice. Medium issues can wait.

3. **The audit lists ALL instances, not just the first.** If "42 models" appears in 4 chapters, all 4 locations are shown. This helps you decide which one is correct.

4. **Use with `/progress`.** After fixing issues, run `/progress` to verify word counts haven't drifted.

5. **Re-audit after fixes.** Fixing one issue can introduce another (e.g., updating a number in one chapter but forgetting a related table). Run `/audit` again to confirm.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Expecting auto-fixes | `/audit` only reports. You decide what to fix and how. |
| Ignoring Medium issues | They matter for thesis polish. Fix them before final submission. |
| Running only once at the end | Audit incrementally. Catching issues early is much easier. |
| Confusing `/audit` with `/verify` | `/audit` checks internal consistency. `/verify` checks external facts. |

---

## Relationship to Other Skills

```
/integrate ──► chapters modified
                   │
                   ▼
              /audit ──► consistency report
                   │
                   ├── user fixes issues
                   │
                   ▼
              /progress ──► verify word counts still OK
                   │
                   ▼
              /export ──► submit clean version
```

`/audit` sits between integration and export. It catches the inconsistencies that naturally arise when material from different sources is woven into a thesis over weeks or months.
