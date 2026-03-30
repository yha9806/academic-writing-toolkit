# /note — Structured Reading Notes

Record reading notes to standardised files. One file per source, append-only, shared format across all skills.

---

## What It Does

`/note` writes structured reading notes into a standardised Markdown file. Each source (book, article, paper) gets exactly one notes file at `literature/reading_notes/{Author}_{ShortTitle}_NOTES.md`.

The notes file is the **data contract** of the entire toolkit. Every downstream skill — `/map`, `/integrate`, `/progress` — reads from it. The format is fixed so that the pipeline works end to end.

---

## When To Use

| Scenario | Command |
|----------|---------|
| Record what you just read | `take notes` or `/note` |
| Record a specific observation | `note: Bennett's thing-power connects to L3 assemblage theory` |
| Mark a source as finished | `mark as complete` |

### Trigger Words

The skill activates on: `take notes`, `record this`, `/note`.

---

## Internal Workflow

```
User says "take notes"
│
├─ 1. Identify current literature from conversation context
│     Author, title, year, pages just discussed
│
├─ 2. Locate or create notes file
│     Glob search: literature/reading_notes/*_{Author}*_NOTES.md
│     If exists → open for appending
│     If not   → create from template
│
├─ 3. Determine what to record
│     User specifies content → use that
│     User says "take notes" only → extract core analysis from last message
│       (summary + key terms + thesis connections)
│
├─ 4. Append to correct section (never overwrite)
│     Page notes    → ## Detailed Notes
│     Key terms     → ## Key Terms table
│     Connections   → ## Thesis Connections table
│     Arguments     → ## Key Arguments bullets
│     Questions     → ## Questions & Follow-ups
│
├─ 5. Update "Last updated" timestamp
│
└─ 6. Confirm: "Recorded: {description} → {filename}"
```

---

## The Notes File Format

This is the template that every notes file follows:

```markdown
# Reading Notes: {Author} -- {Title} ({Year})

**Source**: {full citation in Harvard style}
**Date read**: {YYYY-MM-DD}
**Status**: reading
**Relevance**: {which chapter/section this maps to}

---

## Key Arguments

- {Main argument 1}
- {Main argument 2}

## Detailed Notes

### p.{N}--{M}: {Section Title}

> "{direct quote}" (p.{N})

{Your analysis and commentary}

## Key Terms

| Term | Translation | Definition in context |
|------|-------------|----------------------|

## Thesis Connections

| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|

## Questions & Follow-ups

- {Open questions for future reading}

---
*Last updated: {YYYY-MM-DD}*
```

### Critical Fields

| Field | Format | Consumed by |
|-------|--------|-------------|
| `Status` | `reading` → `completed` → `integrated` | `/progress`, `/integrate` |
| `Relevance` | e.g. `Ch3 S3.2 — supports argument about X` | `/map` |
| `Thesis Connections` table | 4-column table with connection types | `/map`, `/integrate` |

---

## Practical Walkthrough

### Scenario: Recording notes after reading 5 pages of Bennett

**Context:** You've just used `/read` to read pages 10-14 of *Vibrant Matter*. The agent displayed structured output for each page.

**You type:**
```
take notes
```

**The agent:**
1. Identifies the current text: Bennett, *Vibrant Matter* (2010), pages 10-14
2. Finds existing file: `literature/reading_notes/Bennett_Vibrant_Matter_NOTES.md`
3. Extracts core analysis from its last output (summary, key terms, connections)
4. Appends to the appropriate sections:

```markdown
### p.10--14: Thing-Power and the Force of Things

> "the capacity of things — edibles, commodities, storms, metals —
>  to act as quasi agents or forces with trajectories, propensities,
>  or tendencies of their own" (p.10)

Bennett defines thing-power as the active capacity of non-human
entities. This directly challenges the subject-object divide that
underpins traditional aesthetics evaluation...
```

5. Updates the Key Terms table:

```markdown
| thing-power | -- | Active capacity of non-human entities to exert force |
| actant | -- | Latour's term adopted by Bennett for any entity that modifies action |
```

6. Updates Thesis Connections:

```markdown
| thing-power | Ch3 | S3.4 | supports |
| assemblage | Ch5 | S5.2 | extends |
```

7. Confirms:
```
Recorded: Bennett pp.10-14 (thing-power, actant, assemblage)
  → Bennett_Vibrant_Matter_NOTES.md
```

---

## File Naming Convention

| Author type | File name | Example |
|-------------|-----------|---------|
| Single author (Western) | `{LastName}_{ShortTitle}_NOTES.md` | `Bennett_Vibrant_Matter_NOTES.md` |
| Single author (Chinese) | `{Pinyin}_{ShortTitle}_NOTES.md` | `Hui_Cosmotechnics_NOTES.md` |
| Multiple authors | `{FirstAuthor}_et_al_{ShortTitle}_NOTES.md` | `Radford_et_al_CLIP_NOTES.md` |
| Organisation author | `{OrgName}_{ShortTitle}_NOTES.md` | `WHO_Guidelines_NOTES.md` |

`{ShortTitle}` uses underscores, title case, and omits articles (a, an, the).

---

## Status Transitions

```
reading ──────► completed ──────► integrated
  │                │                   │
  │ (created by    │ (user says       │ (/integrate
  │  /note)        │  "mark complete") │  processes it)
```

| Status | Meaning | Who changes it |
|--------|---------|---------------|
| `reading` | Currently being read | Set on file creation |
| `completed` | Finished reading, notes complete | User explicitly requests |
| `integrated` | Material woven into thesis chapters | `/integrate` sets this automatically |

---

## Tips

1. **Parallel routing with /read.** If you say "read next page and take notes," the agent handles them as two steps: `/read` processes the page first, then `/note` records the output. You don't need to invoke them separately in this case.

2. **Missing sections are auto-created.** If an older notes file is missing a `## Thesis Connections` table, `/note` creates the section automatically. You never need to manually fix file structure.

3. **Don't note everything.** Read 5-10 pages, then note the 2-3 most important points. Over-noting produces noise that makes `/map` and `/integrate` less effective.

4. **Fill the Thesis Connections table early.** This table is what makes `/map` and `/integrate` work. Even rough connections (e.g., `supports | Ch3 | S3.2`) are valuable.

5. **Use connection types consistently.** The standard types are:
   - `supports` — source provides evidence for your argument
   - `challenges` — source contradicts or complicates your argument
   - `extends` — source adds a new dimension to your argument
   - `cite` — source is referenced but not deeply engaged
   - `data` — source provides data or examples
   - `method` — source informs methodology

6. **One file per source, always.** Even if you read a source across 10 sessions, all notes go in the same file. The file accumulates over time.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Creating multiple notes files for the same source | Search with Glob first. `/note` does this automatically. |
| Leaving Thesis Connections empty | Always fill at least one row. Downstream skills need it. |
| Forgetting to mark sources as `completed` | Say "mark as complete" when you finish reading. `/progress` depends on this. |
| Trying to use `/note` without reading first | `/note` needs conversation context. Use `/read` first, then `/note`. |

---

## Relationship to Other Skills

```
/read output
     │
     ▼
  /note ──writes──► {Author}_{Title}_NOTES.md
                         │
           ┌─────────────┼─────────────┐
           ▼             ▼             ▼
        /map         /integrate    /progress
   (reads Thesis   (reads notes,  (counts by
    Connections)    inserts into    Status field)
                    chapters)
```

The notes file is the hub. `/note` writes it; three other skills read it.
