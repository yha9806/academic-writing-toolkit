---
name: verify
description: Fact-check claims encountered during reading — dates, names, events, citations. Use when encountering historical facts or disputed claims.
allowed-tools: WebSearch, WebFetch, Read, Edit
---

# /verify — Fact Verification Skill

## Purpose

Fact-check claims encountered during reading sessions. This covers dates, names, historical events, publication details, and attribution of ideas. Use when the user questions a claim or when a factual assertion seems uncertain.

## Trigger Words

This skill activates on: `verify`, `check this`, `fact-check`, `is this correct`, `/verify`.

## Workflow

1. **Extract the claim** from the user's input or from conversation context. Identify the specific factual assertion to verify (date, name, event, publication, attribution).
2. **Search authoritative sources** using WebSearch. Prioritise:
   - Wikipedia (for dates, biographical facts, historical events)
   - Academic databases (Google Scholar, JSTOR, PhilPapers)
   - Publisher websites (for publication dates, editions, ISBNs)
   - Encyclopedias (Stanford Encyclopedia of Philosophy, Britannica)
3. **Compare** the original claim against verified information.
4. **Output the verdict** using the format below.
5. **Optionally annotate the notes file.** If the user confirms, use Edit to add a `(verified)` or `(corrected: {correct info})` tag next to the relevant entry in the notes file.

## Output Format

```
## Verification

**Claim**: {the original claim as stated in the source}
**Verdict**: Confirmed | Needs correction | Incorrect | Unverifiable

| Item | Original | Verified |
|------|----------|----------|
| {specific fact} | {as claimed} | {as verified} |

**Source**: {single-line citation in the project's declared style — see `literature/reading_notes/_template_NOTES.md` for per-style examples; the active style is `Citation style:` in `CLAUDE.md`. Append the URL after the citation if the source is web-only}
**Confidence**: High | Medium | Low
**Notes**: {any additional context, e.g., "Date varies by edition" or "Multiple conflicting sources"}
```

## Multiple Claims

When verifying several claims at once, produce one verification block per claim, numbered sequentially:

```
### 1. {Brief claim description}
{verification block}

### 2. {Brief claim description}
{verification block}
```

## Annotation

When the user says "annotate" or "mark in notes" after verification:
- Use Edit to find the relevant passage in the notes file.
- Append the tag inline: `(verified 2026-03-30)` or `(corrected: {correct value}, verified 2026-03-30)`.
- Do not alter the original text of the note -- add the tag after it.

## Constraints

1. **Never auto-correct notes** without user confirmation. Present the verdict first, then ask if the user wants to annotate.
2. **Cite sources** with URLs whenever possible. Do not present unverifiable assertions as fact.
3. **Acknowledge uncertainty.** If sources conflict, report all versions and mark confidence as Low.
4. **No emoji** in output.
5. **Scope**: This skill verifies factual claims only. For argument analysis or interpretation, defer to the user's own reading.
