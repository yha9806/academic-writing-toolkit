---
name: map
description: Show or update the mapping between literature and thesis chapters — which sources support which arguments. Use for tracking coverage.
allowed-tools: Read, Glob, Grep, Edit, Write
---

# /map — Literature-Thesis Mapping Skill

## Purpose

Build and display a mapping matrix showing which literature sources support which thesis chapters. Identify coverage gaps where chapters lack sufficient source support.

## Trigger Words

This skill activates on: `map`, `show mapping`, `coverage`, `which sources`, `/map`.

## Workflow

1. **Scan all notes files** in `literature/reading_notes/` using Glob (`*_NOTES.md`). For each file, extract:
   - Author and title (from the `# Reading Notes:` heading)
   - `Status` field value
   - `Relevance` field value
   - All rows from the `## Thesis Connections` table

2. **Scan chapter files** in `chapters/` to get the list of chapters and their section headings.

3. **Build the mapping matrix.** Rows are sources (sorted alphabetically by author), columns are chapters (Ch1 through Ch8 or however many exist).
   - Mark each cell with the connection type if a mapping exists (e.g., `supports`, `challenges`, `extends`).
   - Leave cells empty if no connection.

4. **Identify coverage gaps.** Flag any chapter that has fewer than 3 mapped sources as "under-covered".

5. **Output the mapping.**

## Output Format

```
## Literature-Thesis Mapping -- {YYYY-MM-DD}

### Matrix

| Source | Status | Ch1 | Ch2 | Ch3 | Ch4 | Ch5 | Ch6 | Ch7 | Ch8 |
|--------|--------|-----|-----|-----|-----|-----|-----|-----|-----|
| Smith (2024) | integrated | | supports | supports | | | | | |
| Jones (2021) | integrated | extends | supports | supports | extends | | | | |
| Lee (2019) | completed | | | supports | | | challenges | | challenges |

### Coverage Summary

| Chapter | Mapped Sources | Status |
|---------|---------------|--------|
| Ch1 | {N} | OK / Under-covered |
| Ch2 | {N} | OK / Under-covered |

### Under-covered Chapters

{List chapters with < 3 sources, with suggestions for which completed-but-not-yet-mapped notes might fill the gap.}
```

## Saving the Matrix

If the user says "save" or "export mapping", write the matrix to `literature/mapping_matrix.md` using Edit (if the file exists) or Write (if creating new). Include a timestamp header.

## Gap Threshold

- **Under-covered**: fewer than 3 mapped sources per chapter.
- This threshold can be adjusted if the user specifies a different minimum.

## Constraints

1. **Read-only by default.** Only modify files if the user explicitly asks to save the matrix.
2. **No emoji** in output.
3. **No hardcoded chapter count.** Detect chapters dynamically from the `chapters/` directory.
4. **Source names** use the format `{Author} ({Year})` for readability.
5. **Connection types** are derived from the `Connection Type` column in notes files. If that column is missing, infer from the `Relevance` field.
