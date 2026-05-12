---
name: read
description: Read PDF page by page with structured output — key arguments, terms glossary, thesis connections. Use when reading academic papers, books, or articles.
allowed-tools: Read, Glob, Grep
---

# /read — Academic PDF Reading Skill

## Core Principle

**Display first, restrain expansion.** Show the page content, provide a terms glossary, give a brief summary and thesis connections. Do not auto-expand, auto-search, or auto-record unless the user explicitly asks. The reader controls the pace and direction.

## Trigger Words

This skill activates on: `read`, `next page`, `continue`, `skip to p.N`, `read p.N`, `/read`.

## PDF Limits

- **Maximum 15 pages per invocation.**
- **Maximum 90 pages per conversation.**
- Track cumulative pages read in the conversation. When the count reaches 75, display:
  `[Limit reminder: {N}/90 pages read this conversation. 15 remaining.]`
- If a request would exceed the limit, warn the user and suggest starting a new conversation.

## Workflow

1. **Identify the PDF.** If the user provides a path, use it directly. If the user names an author or title, search the project's `literature/` directory using Glob to locate the file.
2. **Read the specified page(s)** using the Read tool with the `pages` parameter. Default to the next unread page if the user says "next page" or "continue".
3. **Display structured output** following the format below.
4. **Wait for user instruction.** Do not proceed to the next page, take notes, or search for related material unless explicitly asked.

## Output Format

For each page read, produce the following:

```
## p.{N} -- {Topic Summary}

### Content

**{Paragraph topic}**

> "{direct quote}" (p.{N})

- {key point}
- {key point}

**{Next paragraph topic}**

> "{direct quote}" (p.{N})

- {key point}

### Key Terms

| Term | Translation | Context |
|------|-------------|---------|
| {term} | {if non-English, provide translation} | {how it is used on this page} |

### Summary

{3-5 sentence summary of the page content. Focus on the argument structure and evidence presented.}

### Connections

- **Thesis link**: {one sentence connecting to the user's research}
- **Previous page**: {one sentence on continuity with previous page, or "First page" if N=1}
- **Open question**: {if any unresolved point or tension is raised}

---
Next page? Take notes? Expand a connection?
```

## Handling Multiple Pages

When reading a range (e.g., "read p.10-15"):
- Produce the structured output for each page individually.
- At the end, add a range summary section:
  ```
  ## Pages {start}--{end} Summary
  {5-8 sentence summary of the range as a whole}
  ```

## Constraints

1. **Never auto-record notes.** The user must explicitly say "take notes", "record this", or invoke `/note`.
2. **Never auto-search** for related literature, web sources, or definitions unless the user asks.
3. **Never launch agents** or parallel tasks.
4. **All extensions require explicit user request** -- expanding a connection, comparing with another source, verifying a claim.
5. **Literature directory** is determined from project configuration. Do not hardcode paths.
6. **Keep connections to 1-2 sentences max.** Do not elaborate. The user will ask if they want more.
7. **Preserve original language** for key terms. If the source is in a non-English language, show the original term alongside the translation.
8. **Quote accurately.** Use the exact text from the PDF. If a quote spans pages, note both page numbers.
