# Scan coverage: say what the loop did not read

Status: draft (the author asked on 2026-09-24 to start the fixes and to grill each step; this spec was not shown before work began)

## Problem

A workspace names the sections to track by heading regex (`draft.sections`). `text.sentences_of` skips any heading no rule
matches, silently. When a manuscript's headings are renamed, whole sections leave the sentence index, and the checks that
read the index (the paper-state overreach scan and the claims' required wordings) stop reading them. The per-turn sentence
gate reads the draft files whole and is not affected. Nothing reports it: the index says how many sentences it holds, never how many the draft has. On one real workspace
a restructure left 31% of the body's words (by `prose_words`) outside the index, and the problems an outside reviewer found
sat in that part.

Separately, the overreach scan reads only the index. Files submitted with the draft but not tracked sentence by sentence
(`inputs.also_checked`, e.g. a supplement) and the natural-language text inside figure and table sources are never
scanned for wordings the claims ledger forbids.

## Goals

1. Coverage is measured on every `loop update` and shown in `loop coverage`: words under matched headings, under ignored
   headings, under headings no rule matches (by name), and text before the first heading. The per-turn line shows the row
   only when it fails: an always-on share would become wallpaper.
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

## Review round 1 (2026-09-25, independent reviewer; all ten findings reproduced before fixing)

- A directory in `also_scanned` was read as a tree listing and scanned nothing, silently: directories now expand to their
  text files; an entry that yields nothing is said.
- `tex_plain` missed `~`, `\\[2pt]`, `\%`, `\&` spellings and kept a comment after `\\`: breaks go first, escapes kept.
- Globs used fnmatch (`*` crossed `/`, no `**`); draft files were rescanned: `text.glob_match` and `resolve_listed`,
  draft files excluded.
- False passes: text before the first heading counted nowhere (a markdown draft with only `#` headings read as empty);
  CJK counted zero; an `\input` file listed nowhere passed. Now: a pseudo-heading `(第一个标题之前)`, CJK characters
  count, and an input not in `draft.glob`, `also_checked` or `also_scanned` fails the row.
- A string or an invalid regex in `ignore_headings` either ignored everything or crashed `compute`: validated, and a
  bad entry fails the row.
- The summary fingerprint ignored `draft.sections` / `ignore_headings`: added.
- Extra files were read per turn with one `git show` each: one cat-file process, cached by commit and list
  (on one workspace, 74 ms without extras, 192 ms on a new commit, 80 ms cached).
- The notch landing line said 「检查都过了」 while a check failed (true of any failed check, not only this row): it now
  says 失败 first.
- Labels read like `file:line`: now `file#n` (n-th sentence). A missing extra file is its own blocker
  (额外扫描读不到), not 「清单读不懂」.
- Tests did not pin behaviour: ten mutants (tex_plain collapsed, extras at HEAD, threshold 45, fnmatch, no draft
  exclusion, no directory expansion, no pre-heading text, no input check, no fingerprint entry, comments before breaks)
  each now fail a named test.

## Review round 2 (2026-09-25; eleven findings, all reproduced before fixing)

- `\input` resolution: paths are resolved from the main file's directory (then the including file's), `./` and `..`
  normalised, an existing extension kept, `\input x` without braces, `\subfile` and `\import{dir}{x}` read, and inputs
  inside pulled-in files followed (depth 6). Files listed in `also_checked` / `also_scanned` count as accounted for.
- Regression from round 1: the pseudo-heading made ordinary front matter (title, authors, keywords; 40-65 words in
  common journal templates) fail the row. Text before the first heading is now shown, not failed; the row fails
  instead when the rules keep no word of a draft that has prose.
- `ls-tree` quoted non-ASCII names, so a figure with a Chinese file name was skipped silently: `-z`.
- The notch landing line called stale, never-run or missing-prerequisite checks passed: now 没看全 / 检查算于旧版本.
- `inputs` of the wrong shape crashed `compute` and the fingerprint: validated, reported in the row.
- `tex_plain`: control space, `\\ [2pt]`, `\-`, `\hspace{..}` handled.
- Globs took binary files (a figure folder with PDFs): globs keep text suffixes only (`.tex .md .txt .tikz .pgf`).
- `[...]` character classes in globs work again.
- An ignore pattern that matches the empty string (`""`, `^`, `.*`) is refused; the share counts ignored words.
- The unlisted-input message says the files are in no scan list (they may be listed as number artifacts).
- A malformed cache file is rebuilt instead of raising.
Each fix has a test that fails on the round-1 code and a mutant that the test kills. On live workspaces: one fails
until its figure and table sources are listed in `also_scanned`; one reports two untracked sections (191 and 96
words) that its owner has to name or ignore; a probe workspace whose rules keep no word now says so.

## Acceptance

- Probe (red first): a synthetic two-section LaTeX draft whose config matches one heading must fail the coverage row and
  name the other heading; adding an ignore rule for it, or a matching rule, turns the row current.
- Probe (red first): a forbidden wording present only in a synthetic figure source listed in `inputs.also_scanned` must be
  reported by the paper-state scan with that file's name; removing the file from the list removes the hit.
- A required wording present only in an extra file must still be reported absent.
- Full engine suite passes; fixtures are synthetic (no manuscript text).
