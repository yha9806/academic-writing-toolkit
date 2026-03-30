# /progress — Progress Dashboard

Display reading progress, writing word counts, and coverage gaps in a single dashboard.

---

## What It Does

`/progress` scans your notes files and chapter files to produce a three-part dashboard:

1. **Reading progress** — how many sources are in each status (reading, completed, integrated)
2. **Writing progress** — word counts per chapter vs. targets, with completion percentages
3. **Coverage analysis** — which chapters have enough mapped sources and which don't

It is strictly **read-only** and never modifies any files.

---

## When To Use

| Scenario | Command |
|----------|---------|
| Quick project status | `/progress` or `dashboard` |
| Check before a supervisor meeting | `how far am I?` |
| Decide what to work on next | `status` |

### Trigger Words

The skill activates on: `progress`, `dashboard`, `status`, `how far`, `/progress`.

---

## Internal Workflow

```
User says "/progress"
│
├─ 1. Count reading notes by status
│     Glob: literature/reading_notes/*_NOTES.md
│     For each file → extract Status field
│     Tally: reading | completed | integrated
│
├─ 2. Count chapter word counts
│     Glob: chapters/*
│     For each file → count words
│       (exclude Markdown syntax: #, |, ---, YAML frontmatter)
│     Compare against targets from config
│
├─ 3. Calculate coverage per chapter
│     Same logic as /map — count sources mapped to each chapter
│     via Relevance and Thesis Connections fields
│
└─ 4. Output the dashboard
```

---

## Practical Walkthrough

### Scenario: Mid-project status check

**You type:**
```
/progress
```

**The agent produces:**

```
## Progress Dashboard -- 2026-03-30

### Reading: 38/52 sources completed

| Status | Count |
|--------|-------|
| Reading | 3 |
| Completed | 11 |
| Integrated | 38 |
| **Total** | **52** |

### Writing: 62,736/80,000 words (78%)

| Chapter | Title | Words | Target | % | Status |
|---------|-------|-------|--------|---|--------|
| Ch1 | Introduction | 3,292 | 5,000 | 66% | In progress |
| Ch2 | Background | 9,783 | 10,000 | 98% | In progress |
| Ch3 | Framework | 11,991 | 12,000 | 100% | Complete |
| Ch4 | Methodology | 5,186 | 8,000 | 65% | In progress |
| Ch5 | Judge++ | 11,176 | 15,000 | 75% | In progress |
| Ch6 | Anchored | 10,678 | 12,000 | 89% | In progress |
| Ch7 | Practice | 5,099 | 8,000 | 64% | In progress |
| Ch8 | Conclusion | 5,531 | 5,000 | 111% | Over target |
| **Total** | | **62,736** | **80,000** | **78%** | |

### Coverage Gaps

| Chapter | Mapped Sources | Minimum | Status |
|---------|---------------|---------|--------|
| Ch1 | 5 | 3 | OK |
| Ch2 | 8 | 3 | OK |
| Ch3 | 15 | 3 | OK |
| Ch4 | 4 | 3 | OK |
| Ch5 | 3 | 3 | OK |
| Ch6 | 6 | 3 | OK |
| Ch7 | 2 | 3 | Under-covered |
| Ch8 | 3 | 3 | OK |

### Alerts

- Ch8 is over target (111%). Consider trimming ~500 words.
- Ch7 has only 2 mapped sources. Consider integrating Steyerl (2023)
  or Grba (2022) notes.
- 3 sources still in "reading" status. Finish or mark as complete.
```

---

## Chapter Status Logic

| Status | Condition | Meaning |
|--------|-----------|---------|
| Draft | < 50% of target | Early stage, needs significant writing |
| In progress | 50-99% of target | Actively being written |
| Complete | 100-150% of target | Reached target, may need editing |
| Over target | > 150% of target | Needs trimming |

---

## Word Counting Method

The agent counts words by:

1. Reading the file content
2. **Excluding**: YAML frontmatter blocks, Markdown heading markers (`#`), table delimiters (`|---|`), horizontal rules (`---`), and empty lines
3. **Counting**: remaining text split on whitespace

This gives a count close to what a word processor reports, minus formatting overhead.

**Default targets**: If your config file does not specify per-chapter word count targets, `/progress` uses 5,000 words per chapter as the default.

**Empty state**: If no notes files exist yet (e.g., on a fresh project), the reading section displays all zeros and a note that no reading notes have been created. The skill handles this gracefully — you can run `/progress` at any time, even before your first reading session.

---

## Tips

1. **Run at the start of each session.** It takes seconds and tells you exactly where to focus. If Ch4 is at 65% and Ch8 is over target, you know where to write and where to trim.

2. **Use Alerts as a to-do list.** The Alerts section highlights actionable items: over-target chapters, under-covered chapters, stale reading notes.

3. **Track trends across sessions.** Run `/progress` at the start and end of a writing session. The word count delta tells you how productive the session was.

4. **Coverage gaps inform your reading list.** If Ch7 is under-covered, that's a signal to read more sources relevant to Ch7 before writing.

5. **The "reading" count should decrease over time.** If sources stay in "reading" status for too long, either finish them or decide they're not relevant and remove them.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Forgetting to mark sources as "completed" | `/progress` undercounts your reading. Say "mark as complete" after finishing a source. |
| Ignoring "Over target" warnings | Examiners notice bloated chapters. Trim early. |
| Not filling Thesis Connections in notes | Coverage analysis depends on these mappings. Empty tables = invisible sources. |

---

## Relationship to Other Skills

```
/note files (Status field) ──► Reading progress
chapters/ (word counts)    ──► Writing progress
/note files (Thesis Connections) ──► Coverage analysis
                                       │
                                       ▼
                                  /progress dashboard
```

`/progress` reads from the same files as `/map` but produces a different view. `/map` shows the full matrix; `/progress` shows summary counts and actionable alerts.
