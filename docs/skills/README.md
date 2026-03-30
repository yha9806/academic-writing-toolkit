# Skills Guide

A deep-dive into each of the eight skills — what it does, how it works internally, and how to use it in practice.

---

## Architecture

The toolkit is a pipeline, not a bag of independent tools. Every skill reads from or writes to the same file structure, connected by a shared **data contract**: the standardised notes file.

```
PDF file
  │
  ▼
/read ──► Structured page output (displayed, not saved)
  │
  ▼
/note ──► literature/reading_notes/{Author}_{Title}_NOTES.md
  │            │
  │         /verify ──► Fact-check annotations added to notes
  │            │
  ▼            ▼
/map  ◄── Reads Thesis Connections table from every notes file
  │        Reads chapter files from chapters/
  │
  ▼
/integrate ──► Inserts material from notes into chapters/
  │              Updates notes Status: completed → integrated
  ▼
/audit ──► Scans all chapters for cross-chapter consistency
  │
  ▼
/progress ──► Dashboard: reading status + word counts + coverage
  │
  ▼
/export ──► Markdown → Word (.docx) + ZIP
```

### The Data Contract

The notes file template (`literature/reading_notes/_template_NOTES.md`) is the glue. Three fields matter most:

| Field | Used by | Purpose |
|-------|---------|---------|
| `Status` (reading / completed / integrated) | `/progress`, `/integrate` | Tracks lifecycle stage |
| `Relevance` (e.g. "Ch3 S3.2") | `/map`, `/integrate` | Links source to chapter |
| `Thesis Connections` table | `/map`, `/integrate` | Structured mapping with connection types |

When `/read` produces output and `/note` writes it into a notes file, these fields are populated. Every downstream skill consumes them. Nothing falls through the cracks because every skill reads the same files.

### Skill Properties

| Skill | Reads files | Writes files | Needs internet | User approval required |
|-------|-------------|-------------|----------------|----------------------|
| `/read` | PDF | -- | No | No |
| `/note` | Notes file | Notes file | No | No |
| `/verify` | -- | Notes file (optional) | Yes | Yes (for annotations) |
| `/map` | Notes files + chapters | Mapping file (optional) | No | Yes (for save) |
| `/integrate` | Notes files + chapters | Chapters + notes file | No | Yes (always) |
| `/audit` | Chapters | -- | No | No |
| `/progress` | Notes files + chapters | -- | No | No |
| `/export` | Chapters + notes | .docx + .zip | No | N/A (user-invoked only) |

---

## Skill Lifecycle

A typical thesis writing session follows this order:

```
Session 1: Reading
  /read literature/Bennett_Vibrant_Matter.pdf
  (read 15 pages, take notes along the way)
  /note
  /verify "Bennett claims thing-power originates from Spinoza"

Session 2: Analysis
  /map
  /progress

Session 3: Writing
  /integrate Bennett_Vibrant_Matter_NOTES.md
  (approve integration plan, agent inserts material)

Session 4: Quality
  /audit
  /progress

Session 5: Submission
  /export chapters en-only
```

Not every session uses every skill. The pipeline is flexible — you can jump to any stage as long as the prerequisite data exists.

---

## Individual Skill Guides

| # | Skill | Guide | One-line summary |
|---|-------|-------|------------------|
| 1 | `/read` | [01-read.md](01-read.md) | Page-by-page PDF reading with structured output |
| 2 | `/note` | [02-note.md](02-note.md) | Record notes to standardised files |
| 3 | `/verify` | [03-verify.md](03-verify.md) | Fact-check claims against online sources |
| 4 | `/map` | [04-map.md](04-map.md) | Literature-to-chapter mapping matrix |
| 5 | `/integrate` | [05-integrate.md](05-integrate.md) | Weave reading notes into thesis chapters |
| 6 | `/audit` | [06-audit.md](06-audit.md) | Cross-chapter consistency check |
| 7 | `/progress` | [07-progress.md](07-progress.md) | Reading + writing progress dashboard |
| 8 | `/export` | [08-export.md](08-export.md) | Markdown to Word + ZIP packaging |

---

## Key Design Decisions

### Why restrain auto-expansion?

The `/read` skill explicitly forbids the agent from auto-searching, auto-noting, or auto-expanding. This is deliberate. Academic reading requires the reader to control pace and direction. The agent presents structured content; the human decides what matters.

### Why append-only notes?

`/note` never overwrites existing content. Notes accumulate across sessions. This prevents accidental loss and creates a chronological reading log that reflects evolving understanding.

### Why require approval for /integrate?

Integration modifies thesis chapters — the most important files in the project. The skill always presents a plan first, waits for approval, and reports word count changes. No silent edits.

### Why no emoji?

Every SKILL.md includes the constraint "No emoji in output." Academic writing tools should produce clean, professional text. Emoji in notes files or chapter insertions would look unprofessional and can cause encoding issues in some Word conversion pipelines. All 8 skills produce plain text output only.

### Why separate /read and /note?

Reading and recording are distinct cognitive activities. You may read 10 pages and only note 2 points. Separating the skills respects this natural workflow and prevents noise in notes files.
