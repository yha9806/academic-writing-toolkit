# /read — Page-by-Page PDF Reading

Read academic PDFs with structured output: content extraction, key terms glossary, thesis connections.

---

## What It Does

`/read` turns a raw PDF into structured, page-by-page output. For each page, it produces:

- **Content** — direct quotes and key points, organised by paragraph topic
- **Key Terms** — a glossary table with translations (for non-English terms) and context
- **Summary** — 3-5 sentences on argument structure
- **Connections** — one-line thesis link, continuity with previous page, open questions

It does **not** take notes, search for related literature, or launch sub-agents. The reader controls pace and direction.

---

## When To Use

| Scenario | Command |
|----------|---------|
| Start reading a new PDF | `/read literature/Bennett_Vibrant_Matter.pdf` |
| Continue to next page | `next page` or `continue` |
| Jump to a specific page | `read p.42` or `skip to p.42` |
| Read a page range | `read p.10-15` |
| Find a PDF by author name | `/read Bennett` (searches `literature/` directory) |

### Trigger Words

The skill activates on: `read`, `next page`, `continue`, `skip to p.N`, `read p.N`, `/read`.

---

## Internal Workflow

```
User says "/read literature/Hui_Cosmotechnics.pdf p.1-5"
│
├─ 1. Identify the PDF
│     If path given → use directly
│     If author/title given → Glob search literature/ directory
│
├─ 2. Read pages using Read tool (pages parameter)
│     Track cumulative page count for this conversation
│     Enforce: max 15 pages per invocation, max 90 per conversation
│
├─ 3. For each page, produce structured output
│     Content → Key Terms → Summary → Connections
│
├─ 4. If multiple pages, add a range summary at the end
│
└─ 5. Wait for user instruction
      "Next page? Take notes? Expand a connection?"
      Do NOT auto-proceed
```

### Page Limits

| Limit | Value | What happens |
|-------|-------|-------------|
| Per invocation | 15 pages | Agent refuses and suggests splitting |
| Per conversation | 90 pages | Agent warns at 75 pages, refuses at 90 |
| At 75 pages | Warning displayed | `[Limit reminder: 75/90 pages read. 15 remaining.]` |
| At 90 pages | Hard stop | Agent suggests starting a new conversation |

These limits exist because AI context windows degrade with excessive content. 15 pages per invocation keeps output quality high. 90 pages per conversation prevents context overflow.

---

## Practical Walkthrough

### Scenario: Reading the first 3 pages of a book

**You type:**
```
/read literature/Goodman_Languages_of_Art.pdf p.1-3
```

**The agent produces (for each page):**

```
## p.1 -- Preface and Scope

### Content

**The problem of representation**

> "The arts must be taken no less seriously than the sciences
>  as modes of discovery, creation, and enlargement of
>  knowledge" (p.1)

- Goodman positions art as epistemically equivalent to science
- This is a rejection of the emotivist view of aesthetics

### Key Terms

| Term | Translation | Context |
|------|-------------|---------|
| denotation | -- | Used here as the basic semantic relation between symbol and referent |
| exemplification | -- | Introduced as a distinct mode of reference, contrasted with denotation |

### Summary

Goodman opens by arguing that the arts are genuine modes of knowledge,
not mere emotional expression. He introduces his central project:
a general theory of symbols that encompasses both artistic and
scientific representation. The key move is treating art works as
symbol systems subject to the same analytical tools as language.

### Connections

- **Thesis link**: Directly supports L1-L5 framework — if art is a symbol
  system, then understanding it requires hierarchical decoding
- **Previous page**: First page
- **Open question**: How will Goodman distinguish "good" from "bad"
  symbol systems?

---
Next page? Take notes? Expand a connection?
```

After all pages, a range summary appears:

```
## Pages 1--3 Summary

Goodman establishes the epistemological foundation for treating art as a
symbol system. He introduces denotation and exemplification as the two
basic modes of reference, argues against the emotivist reduction of
aesthetics, and previews the book's structure...
```

---

## What It Does NOT Do

These constraints are central to the skill's design:

| Forbidden action | Why |
|-----------------|-----|
| Auto-take notes | Reading and recording are separate activities. You decide what matters. |
| Auto-search related literature | Tangential searches break reading flow. Ask explicitly if needed. |
| Launch sub-agents | Reading is a single-threaded, focused activity. |
| Proceed to next page automatically | The reader controls pace. You may want to re-read, verify, or reflect. |
| Expand connections beyond 1-2 sentences | Brief connections prompt thinking. Long analysis overwhelms. |

---

## Tips

1. **Quotes must be exact.** The agent uses the precise text from the PDF. If a quote spans two pages, both page numbers are noted (e.g., `(p.14-15)`). Never paraphrase inside quote marks.

2. **Read in batches of 5-10 pages.** This balances depth with progress. A 300-page book takes ~30 sessions at 10 pages each.

3. **Use "continue" for flow.** Once you've started a PDF, saying "continue" or "next page" automatically reads the next unread page.

4. **Combine with /note selectively.** Don't note every page. Read 5 pages, then note the 2-3 most important points. This produces better notes than page-by-page recording.

5. **Non-English texts get bilingual terms.** If reading a Chinese, French, or German source, the Key Terms table shows both the original term and translation.

6. **Watch the page counter.** At 75 pages, you'll see a reminder. Plan your reading sessions around the 90-page conversation limit.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Trying to read an entire book in one conversation | Respect the 90-page limit. Plan sessions across multiple conversations. |
| Saying "read and take notes" expecting a single action | `/read` and `/note` are separate skills. Read first, then decide what to note. |
| Giving a vague file name | Be specific: `literature/Hui_Cosmotechnics.pdf` not just "the Hui paper" |
| Reading without checking page count | Ask "how many pages have I read?" if you lose track |

---

## Relationship to Other Skills

```
/read ──produces──► structured output (displayed to user)
                          │
                    user decides
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
           /note       /verify     (reflect)
        (record it)  (check a claim)  (re-read)
```

`/read` is the entry point. It feeds `/note` (when you want to record) and `/verify` (when you want to fact-check). But the decision to invoke those skills is always yours.
