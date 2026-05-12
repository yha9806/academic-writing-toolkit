---
name: note
description: Record reading notes to a structured notes file. Use when the user says "take notes" or "record this" during reading sessions.
allowed-tools: Read, Write, Edit, Glob
---

# /note — Reading Notes Skill

## Parallel Routing

This skill is triggered by: `take notes`, `record this`, `/note`.

This skill does **not** handle page reading -- that is `/read`. If the user says "read next page and take notes", the `/read` skill handles the reading, and `/note` handles the recording as a second step.

## Workflow

1. **Identify the current literature** from conversation context -- author, title, year, and the page(s) just discussed.
2. **Locate or create the notes file** at `literature/reading_notes/{Author}_{ShortTitle}_NOTES.md`. Use Glob to check if the file already exists. The `{Author}` is the last name of the first author. `{ShortTitle}` uses underscores, title case, and omits articles (e.g., `Smith_Methods_NOTES.md`).
3. **Append content** to the correct section of the notes file. Never overwrite existing content.
4. **Update the `Last updated` timestamp** at the bottom of the file to today's date.
5. **Confirm** with a one-line summary: `Recorded: {brief description} -> {filename}`

## Default Behavior

If the user says "take notes" without specifying what to record, default to recording the core analysis from the **last assistant message** -- summary, key terms, and thesis connections.

## Notes File Template

This is the data contract shared across all skills (`/read`, `/note`, `/integrate`, `/map`, `/progress`). When creating a new notes file, use this exact structure:

```markdown
# Reading Notes: {Author} -- {Title} ({Year})

**Source**: {single-line citation in the project's declared style — see `literature/reading_notes/_template_NOTES.md` for per-style examples; the active style is `Citation style:` in `CLAUDE.md`}
**Date read**: {YYYY-MM-DD}
**Status**: reading
**Relevance**: {which chapter/section this maps to}

---

## Key Arguments

- {bullet points summarising the main arguments}

## Detailed Notes

### p.{N}--{M}: {Section Title}

> "{direct quote}" (p.{N})

{analysis and commentary}

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|----------------------|

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|

## Questions & Follow-ups

- {open questions for future reading}

---
*Last updated: {YYYY-MM-DD}*
```

## Appending Rules

When appending to an existing file:

- **New page notes** go under `## Detailed Notes`, as a new subsection `### p.{N}--{M}: {Title}`.
- **New key terms** are appended to the `## Key Terms` table.
- **New thesis connections** are appended to the `## Thesis Connections` table.
- **New key arguments** are appended to `## Key Arguments` as bullet points.
- **New questions** are appended to `## Questions & Follow-ups`.

If the section does not exist in the file (e.g., an older file missing `## Thesis Connections`), create it.

## Status Field

- Starts as `reading` when the file is first created.
- Changes to `completed` when the user explicitly says they are done with this text (e.g., "done reading", "mark as complete").
- Changes to `integrated` after `/integrate` has processed the notes into thesis chapters.

## Constraints

1. **Append only.** Never overwrite or delete existing content in a notes file.
2. **No emoji** in any output or file content.
3. **Always update** the `Last updated` timestamp when modifying a file.
4. **Status transitions** are explicit: only change status when the user requests it or after `/integrate` completes.
5. **No hardcoded paths.** Use the project's `literature/reading_notes/` directory relative to the project root.
6. **One file per text.** Each book, article, or paper gets exactly one notes file.
