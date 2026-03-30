# /map — Literature-Thesis Mapping

Build a matrix showing which sources support which thesis chapters. Identify coverage gaps.

---

## What It Does

`/map` scans every notes file and every chapter, then builds a cross-reference matrix. Rows are sources, columns are chapters. Each cell shows the connection type (supports, challenges, extends, cite, data, method).

It also flags **under-covered chapters** — chapters with fewer than 3 mapped sources.

---

## When To Use

| Scenario | Command |
|----------|---------|
| See the full mapping | `/map` or `show mapping` |
| Check which chapters need more sources | `coverage` or `which sources cover Ch3?` |
| Save the matrix to file | `/map` then say `save` |

### Trigger Words

The skill activates on: `map`, `show mapping`, `coverage`, `which sources`, `/map`.

---

## Internal Workflow

```
User says "/map"
│
├─ 1. Scan all notes files (Glob: *_NOTES.md)
│     For each file, extract:
│       - Author + title (from heading)
│       - Status field
│       - Relevance field
│       - Thesis Connections table rows
│
├─ 2. Scan chapter files (Glob: chapters/*)
│     Get list of chapters + section headings
│
├─ 3. Build the matrix
│     Rows = sources (alphabetical by author)
│     Columns = chapters (Ch1 through ChN)
│     Cells = connection type or empty
│
├─ 4. Identify coverage gaps
│     Flag chapters with < 3 mapped sources
│
└─ 5. Output the mapping (read-only by default)
       If user says "save" → write to literature/mapping_matrix.md
```

---

## Practical Walkthrough

### Scenario: Checking coverage after reading 10 sources

**You type:**
```
/map
```

**The agent produces:**

```
## Literature-Thesis Mapping -- 2026-03-30

### Matrix

| Source | Status | Ch1 | Ch2 | Ch3 | Ch4 | Ch5 | Ch6 | Ch7 | Ch8 |
|--------|--------|-----|-----|-----|-----|-----|-----|-----|-----|
| Bennett (2010) | integrated | | | argue | | supports | | | |
| Goodman (1968) | integrated | cite | argue | argue | cite | | | | |
| Hui (2017) | completed | | | argue | | | cite | | cite |
| Panofsky (1939) | integrated | cite | argue | argue | | | | | |
| Parsons (1987) | completed | | cite | argue | | | | | |
| Steyerl (2023) | completed | | | | | | argue | cite | |

### Coverage Summary

| Chapter | Mapped Sources | Status |
|---------|---------------|--------|
| Ch1 | 2 | Under-covered |
| Ch2 | 3 | OK |
| Ch3 | 5 | OK |
| Ch4 | 1 | Under-covered |
| Ch5 | 1 | Under-covered |
| Ch6 | 2 | Under-covered |
| Ch7 | 1 | Under-covered |
| Ch8 | 1 | Under-covered |

### Under-covered Chapters

- **Ch1** (2 sources): Consider mapping Hui (2017) — Relevance
  field mentions "introduction to cosmotechnics"
- **Ch4** (1 source): Parsons (1987) Thesis Connections table
  includes methodology notes not yet mapped
- **Ch5** (1 source): Bennett (2010) has additional connections
  in Key Arguments section
```

### Scenario: Saving the matrix

**You type:**
```
save
```

**The agent writes the matrix to `literature/mapping_matrix.md` with a timestamp header.**

---

## Where the Data Comes From

`/map` reads two fields from each notes file:

### 1. The `Relevance` field

```markdown
**Relevance**: Ch3 S3.2 — supports argument about symbolic form
```

This gives a broad chapter-level mapping.

### 2. The `Thesis Connections` table

```markdown
| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| thing-power | Ch3 | S3.4 | supports |
| assemblage | Ch5 | S5.2 | extends |
```

This gives precise section-level mappings with typed connections.

The matrix aggregates both. If a source appears in a chapter via either field, it shows up in the matrix. **Fallback logic**: if a notes file has no `Thesis Connections` table (e.g., an older file), `/map` infers chapter mappings from the `Relevance` field instead.

---

## Gap Threshold

- Default: **3 sources per chapter** is the minimum for adequate coverage.
- You can adjust this: "set minimum to 5 sources per chapter."
- Chapters below the threshold are flagged with suggestions for which completed-but-unmapped notes might fill the gap.

---

## Tips

1. **Run `/map` after every 3-5 reading sessions.** This gives you an evolving picture of coverage and prevents last-minute scrambling for sources.

2. **The matrix is only as good as your Thesis Connections tables.** If you skip filling those during `/note`, `/map` will show sparse results. Go back and fill them in.

3. **Use the "Under-covered Chapters" suggestions.** The agent actively looks for completed notes that could fill gaps — it cross-references the `Relevance` field against the matrix.

4. **Save periodically.** Running `/map` then saying "save" creates a snapshot. You can track how coverage evolves over time.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Empty Thesis Connections tables in notes | Go back to notes files and fill in at least one connection per source |
| Expecting `/map` to modify files | It's read-only by default. Only "save" triggers a write. |
| Only running `/map` at the end | Run it regularly to catch gaps early |

---

## Relationship to Other Skills

```
/note files (Thesis Connections table)
     │
     ▼
  /map ──reads──► chapters/ (section headings)
     │
     ▼
  Matrix output
     │
     ├─ user sees gaps → reads more sources → /read + /note
     │
     └─ user saves → literature/mapping_matrix.md
```

`/map` is a diagnostic tool. It shows you the state of your research coverage and tells you where to focus next.
