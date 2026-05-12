---
name: integrate
description: Map reading notes to thesis chapters and integrate key arguments into the manuscript. Use after completing a reading session to weave new material into the thesis.
allowed-tools: Read, Edit, Glob, Grep
---

# /integrate — Thesis Integration Skill

## Purpose

After completing a reading session, this skill weaves key arguments, quotes, and concepts from reading notes into the thesis manuscript. It ensures new material is placed in the right chapter and section, with proper attribution and minimal disruption to existing structure.

## Trigger Words

This skill activates on: `integrate`, `weave in`, `add to thesis`, `/integrate`.

## Workflow

1. **Scan the specified notes file(s)** for the `## Thesis Connections` table and `## Key Arguments` section. If the user does not specify which notes file, ask. If the user says "all pending", scan all notes files with `Status: completed` (not yet `integrated`).

2. **Read target chapter files** in `chapters/` to identify insertion points. Use Grep to find relevant sections, existing citations of the same author, and thematic paragraphs where the new material fits.

3. **Present an integration plan** as a table. Do not execute any changes yet.

   ```
   ## Integration Plan: {Author} -- {Title}

   | # | Source Concept | Chapter | Section | Insertion Type | Preview |
   |---|---------------|---------|---------|----------------|---------|
   | 1 | {concept} | Ch{N} | {section ref} | new paragraph / expand existing / add citation / add footnote | {first 10 words of proposed text} |

   Estimated word count delta: +{N} words across {N} chapters.
   Proceed? (yes / edit plan / cancel)
   ```

4. **Wait for user approval.** The user may:
   - Say "yes" or "proceed" to execute the plan as shown.
   - Say "edit plan" and specify changes (remove a row, change a section, etc.).
   - Say "cancel" to abort.

5. **Execute the integration.** For each row in the approved plan:
   - Read the target chapter file.
   - Use Edit to insert, expand, or add citations at the specified location.
   - Preserve existing paragraph structure. Do not rewrite surrounding text.

6. **Update the notes file.** Change `Status` from `completed` to `integrated` using Edit. Update the `Last updated` timestamp.

7. **Report results.**

   ```
   ## Integration Complete

   | Chapter | Words before | Words after | Delta |
   |---------|-------------|------------|-------|
   | {ch} | {N} | {N} | +{N} |

   Total: +{N} words across {N} chapters.
   Notes file status updated to: integrated.
   ```

## Insertion Types

- **new paragraph**: Insert a new paragraph at the specified location. Include a topic sentence, the integrated content, and a transition.
- **expand existing**: Add sentences to an existing paragraph. Maintain the paragraph's flow and argument direction.
- **add citation**: Insert an inline citation (Author, Year) or a parenthetical reference to support an existing claim.
- **add footnote**: Add a footnote with extended discussion or a qualifying remark.

## Constraints

1. **Never integrate without showing the plan first.** The user must approve before any chapter file is modified.
2. **Preserve existing chapter structure.** Do not reorder sections, delete content, or rewrite paragraphs beyond the insertion point.
3. **Track and report word count changes** for every chapter affected.
4. **Attribution**: Every integrated quote must include a page reference. Every integrated argument must cite the source.
5. **No emoji** in output or inserted text.
6. **British English** for all inserted text (e.g., "colour" not "color", "analyse" not "analyze").
7. **One notes file at a time** unless the user explicitly requests batch integration.
