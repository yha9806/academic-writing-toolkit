# Scan coverage: say what the loop did not read

Status: draft (the author asked on 2026-09-24 to start the fixes and to grill each step; this spec was not shown before work began)

## Problem

A workspace names the sections to track by heading regex (`draft.sections`). `text.sentences_of` skips any heading no rule
matches, silently. When a manuscript's headings are renamed, whole sections leave the sentence index, and every check that
reads the index (the paper-state overreach scan, the per-turn sentence gate, the claims' required wordings) stops reading
them. Nothing reports it: the index says how many sentences it holds, never how many the draft has. On one real workspace
a restructure left 31% of the body's words (by `prose_words`) outside the index, and the problems an outside reviewer found
sat in that part.

Separately, the overreach scan reads only the index. Files submitted with the draft but not tracked sentence by sentence
(`inputs.also_checked`, e.g. a supplement) and the natural-language text inside figure and table sources are never
scanned for wordings the claims ledger forbids.

## Goals

1. Coverage is measured and shown every turn: words under matched headings, words under headings no rule matches, and the
   unmatched headings by name.
2. A heading that carries prose and is neither matched nor explicitly ignored fails the coverage row. Ignoring a heading is
   a decision written in the config (`draft.ignore_headings`), not a silence.
3. The overreach scan also reads `inputs.also_checked` and a new `inputs.also_scanned` list (paths or globs, e.g. figure
   and table sources), at the same commit as the index, with LaTeX markup stripped. Hits there are reported with the file
   they came from.

## Non-goals

- No change to sentence identity, versions or the index format. Extra files are scanned, not indexed.
- Required wordings (`必须出现`) keep reading the index only: a figure label must not satisfy a required claim.
- No visual review of rendered figures, no table-cell checks, no statistical-method review (later items).

## Decisions

- Word count for coverage: letters-led tokens after dropping LaTeX comments and `\cite/\ref/\label`-style arguments; a
  heading's words are the words of its body up to the next heading. Headings are the ones `latex_sections` /
  `markdown_sections` already cut.
- Failure rule: any unmatched, unignored heading with at least 20 words fails; the detail lists up to five by name with
  word counts. The share (matched / (matched + unmatched)) is shown beside it.
- Extra-text extraction for `.tex`: drop comments, turn `\\` and `&` into spaces, drop command names and brace/bracket
  delimiters, keep their text; split into sentences with the existing splitter.

## Acceptance

- Probe (red first): a synthetic two-section LaTeX draft whose config matches one heading must fail the coverage row and
  name the other heading; adding an ignore rule for it, or a matching rule, turns the row current.
- Probe (red first): a forbidden wording present only in a synthetic figure source listed in `inputs.also_scanned` must be
  reported by the paper-state scan with that file's name; removing the file from the list removes the hit.
- A required wording present only in an extra file must still be reported absent.
- Full engine suite passes; fixtures are synthetic (no manuscript text).
