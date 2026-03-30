# /integrate — Thesis Integration

Weave arguments, quotes, and concepts from reading notes into thesis chapters. Always requires user approval before modifying any chapter.

---

## What It Does

`/integrate` is the bridge between reading and writing. It takes a completed notes file, identifies where each argument fits in your thesis chapters, presents a plan, and — only after your approval — inserts the material using precise edits.

This is the only skill (besides `/note`) that modifies files, and it **never does so without your explicit go-ahead**.

---

## When To Use

| Scenario | Command |
|----------|---------|
| Integrate a specific source | `/integrate Bennett_Vibrant_Matter_NOTES.md` |
| Integrate all pending sources | `integrate all pending` |
| After completing a reading session | `weave in` or `add to thesis` |

### Trigger Words

The skill activates on: `integrate`, `weave in`, `add to thesis`, `/integrate`.

---

## Internal Workflow

```
User says "/integrate Bennett_Vibrant_Matter_NOTES.md"
│
├─ 1. Read the notes file
│     Extract: Thesis Connections table + Key Arguments
│     Verify status = "completed" (not "reading" or already "integrated")
│
├─ 2. Read target chapter files
│     Grep for: existing citations of Bennett, relevant section headings,
│     thematic paragraphs where new material fits
│
├─ 3. Present integration plan (TABLE — no changes yet)
│     Shows: source concept, target chapter/section, insertion type, preview
│     Shows: estimated word count delta
│     Asks: "Proceed? (yes / edit plan / cancel)"
│
├─ 4. WAIT for user approval
│     "yes"       → execute plan
│     "edit plan"  → user modifies rows, agent re-presents
│     "cancel"     → abort, no files changed
│
├─ 5. Execute approved changes
│     For each row: Read chapter → Edit to insert/expand/cite
│     Preserve surrounding text and paragraph structure
│
├─ 6. Update notes file
│     Status: completed → integrated
│     Last updated: today
│
└─ 7. Report results
       Word count changes per chapter
       Total delta
```

---

## Practical Walkthrough

### Scenario: Integrating Bennett's Vibrant Matter into the thesis

**You type:**
```
/integrate Bennett_Vibrant_Matter_NOTES.md
```

**Step 1 — The agent reads the notes file and presents a plan:**

```
## Integration Plan: Bennett -- Vibrant Matter (2010)

| # | Source Concept | Chapter | Section | Insertion Type | Preview |
|---|---------------|---------|---------|----------------|---------|
| 1 | thing-power as quasi-agency | Ch3 | S3.4.1 | new paragraph | "Bennett's concept of thing-power..." |
| 2 | assemblage theory | Ch5 | S5.2.3 | expand existing | "...extending this through Bennett's..." |
| 3 | vital materialism | Ch3 | S3.5 | add citation | "(Bennett, 2010, p.10)" |
| 4 | Adorno non-identity parallel | Ch3 | S3.4.2 | add footnote | "Cf. Bennett's reading of Adorno..." |

Estimated word count delta: +380 words across 2 chapters.
Proceed? (yes / edit plan / cancel)
```

**Step 2 — You review and approve:**

```
yes
```

Or you might say:
```
edit plan: remove row 4, change row 2 to Ch6 S6.1 instead
```

**Step 3 — The agent executes and reports:**

```
## Integration Complete

| Chapter | Words before | Words after | Delta |
|---------|-------------|------------|-------|
| Ch3 | 11,991 | 12,284 | +293 |
| Ch5 | 11,176 | 11,263 | +87 |

Total: +380 words across 2 chapters.
Notes file status updated to: integrated.
```

---

## Insertion Types

| Type | What it does | When to use |
|------|-------------|-------------|
| `new paragraph` | Inserts a complete new paragraph at the specified location | When the source introduces a concept not yet present in the chapter |
| `expand existing` | Adds sentences to an existing paragraph | When the source strengthens an argument already being made |
| `add citation` | Inserts `(Author, Year)` or `(Author, Year, p.N)` inline | When the chapter makes a claim that the source supports but isn't cited |
| `add footnote` | Adds a footnote with extended discussion | When the connection is important but tangential to the main argument |

---

## The Three-Response Pattern

Integration always follows exactly three exchanges:

```
Exchange 1: Agent presents plan → User reviews
Exchange 2: User approves/edits → Agent executes
Exchange 3: Agent reports results → Done
```

This pattern is rigid by design. No silent edits, no surprises.

---

## Batch Integration

By default, `/integrate` processes **one notes file at a time**. This is deliberate — reviewing integration plans for a single source is manageable; reviewing plans for 10 sources at once is overwhelming. For batch integration when you explicitly want it:

**You type:**
```
integrate all pending
```

**The agent:**
1. Scans all notes files with `Status: completed`
2. Presents a combined plan covering all sources
3. Waits for approval
4. Executes all changes
5. Updates all notes files to `integrated`

Use batch integration cautiously — large plans are harder to review.

---

## Tips

1. **Review the plan carefully.** The integration plan is your last chance to redirect. Check that insertion points make sense and that connection types match your argument structure.

2. **Edit the plan, don't cancel and redo.** If one row is wrong, say "edit plan: change row 3 to Ch4 S4.2." This is faster than cancelling and restarting.

3. **Check word counts after integration.** If a chapter is already over target (visible via `/progress`), you may want to trim elsewhere before integrating more material.

4. **Integration preserves structure.** The agent never reorders sections, deletes existing content, or rewrites paragraphs. It only adds material at specified points.

5. **British English is enforced.** All inserted text uses British English spelling and conventions (colour, analyse, organisation).

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Trying to integrate a file with `Status: reading` | Finish reading first. Say "mark as complete" to change status. |
| Approving without reviewing the plan | Always check insertion points and preview text. |
| Integrating into over-target chapters | Run `/progress` first to check word counts. |
| Expecting the agent to rewrite surrounding text | Integration is additive. It inserts, not rewrites. If restructuring is needed, do it manually. |

---

## Relationship to Other Skills

```
/note (Status: completed)
     │
     ▼
/integrate ──reads──► Thesis Connections + Key Arguments
     │
     ├── reads ──► chapters/ (find insertion points)
     │
     ├── writes ──► chapters/ (insert material)
     │
     └── writes ──► notes file (Status → integrated)
                         │
                         ▼
                    /progress (counts integrated sources)
```

`/integrate` is the most consequential skill. It's the only one that modifies both notes files and chapter files. The approval gate ensures you stay in control.
