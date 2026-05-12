---
name: progress
description: Show reading and writing progress dashboard — how many sources read, chapters completed, word counts, and coverage gaps.
allowed-tools: Read, Glob, Grep
---

# /progress — Progress Dashboard Skill

## Purpose

Display a comprehensive dashboard of reading and writing progress: source counts by status, chapter word counts versus targets, and coverage gaps. Use to get a quick overview of the thesis project state.

## Trigger Words

This skill activates on: `progress`, `dashboard`, `status`, `how far`, `/progress`.

## Workflow

1. **Count reading notes by status.** Scan all `*_NOTES.md` files in `literature/reading_notes/` using Glob. For each file, extract the `Status` field and tally counts for `reading`, `completed`, and `integrated`.

2. **Count chapter word counts.** For each file in `chapters/`, count words (split on whitespace, exclude Markdown syntax markers like `#`, `|`, `---`). Compare against target word counts if a configuration file or chapter metadata specifies them. If no target is specified, use 5,000 words per chapter as the default.

3. **Calculate coverage per chapter.** Use the same logic as `/map` -- count how many sources are mapped to each chapter via the `Relevance` and `Thesis Connections` fields in notes files.

4. **Output the dashboard.**

## Output Format

```
## Progress Dashboard -- {YYYY-MM-DD}

### Reading: {completed + integrated}/{total} sources completed

| Status | Count |
|--------|-------|
| Reading | {N} |
| Completed | {N} |
| Integrated | {N} |
| **Total** | **{N}** |

### Writing: {total_words}/{target_words} words ({pct}%)

| Chapter | Title | Words | Target | % | Status |
|---------|-------|-------|--------|---|--------|
| Ch1 | {title} | {N} | {N} | {N}% | Draft / Complete / Over target |
| Ch2 | {title} | {N} | {N} | {N}% | Draft / Complete / Over target |
| ... | | | | | |
| **Total** | | **{N}** | **{N}** | **{N}%** | |

### Coverage Gaps

| Chapter | Mapped Sources | Minimum | Status |
|---------|---------------|---------|--------|
| Ch1 | {N} | 3 | OK / Under-covered |

### Alerts

- {Any chapters over 150% of target word count}
- {Any chapters with 0 mapped sources}
- {Any notes files stuck in "reading" status for more than indicated period}
```

## Chapter Status Logic

- **Draft**: word count is below 50% of target.
- **In progress**: word count is between 50% and 100% of target.
- **Complete**: word count is between 100% and 150% of target.
- **Over target**: word count exceeds 150% of target.

## Constraints

1. **Read-only.** This skill never modifies any files.
2. **No emoji** in output.
3. **No hardcoded chapter list.** Detect chapters dynamically from the `chapters/` directory.
4. **Word counting** should exclude front matter (YAML blocks), Markdown table delimiters (`|---|`), and horizontal rules (`---`).
5. **If no notes files exist**, display the reading section with all zeros and a note that no reading notes have been created yet.
