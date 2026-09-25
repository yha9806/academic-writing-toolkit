# Generated copies and float reviews: tables and figures the loop never looked at

Status: implemented (2026-09-25): four independent review rounds (round 1 on the generator check, rounds 2 to 4 on both;
every finding reproduced, fixed, each with a test that fails on the reviewed code); every rule has a test and a mutant that the test kills; run
read-only on one real manuscript. Not author-approved before work began: the author asked on 2026-09-25 to continue the
remaining toolkit items with a grill at each step. Items 31.3–31.6 of the same list (claims strength, statistics
review, method sentences, domain reader) are specified in `2026-09-25-review-gap-closure.md` §4.4 and built in another
session; this spec does not touch them.

## Problem

Two parts of a manuscript sit outside every check the loop runs.

1. **Table and figure sources are copies of a generator's output.** A data repository holds the analysis artifacts
   and the scripts that turn them into LaTeX tables and TikZ figures; the manuscript holds copies. The number
   ledger binds numbers in the prose to those copies, so it treats the copies as the truth. Nothing checks that a
   copy is still what its generator emits from the committed artifacts: a cell edited by hand, a copy left behind
   when an artifact was rerun, or a generator that was never updated after a fix in the copy all pass. On one real
   manuscript, one of eighteen copies differed from its generator: a figure label corrected by hand in the copy,
   which the next regeneration would have silently undone. A presence test ("is this cell's number somewhere in
   the artifact") was considered and rejected: a two-decimal value in [0, 1] is found by chance in any artifact
   holding a few hundred floats, so it would pass almost everything.
2. **Nobody is recorded as having looked at a rendered figure or table.** Overflowing labels, a caption that no
   longer matches its figure, or a figure that contradicts its own data are found only when someone opens the
   PDF. The loop cannot judge a figure, but it can say which figures and tables no one has looked at since they
   last changed.

## Goals

1. `audit-generated-copies.py`: for every copy listed in a manifest, rerun its generator on the data repository's
   committed state (never its working tree, never in place) and compare the copy with the output, whole-line
   comments ignored. A copy that differs, a generator that fails, or a file under the manifest's covered globs that the
   manifest does not list fails the check. A file the manifest lists as hand-made is reported as such, not checked.
2. `audit-float-reviews.py`: list every figure and table the draft includes, with a version fingerprint (its caption
   and the bytes of every file it pulls in), and compare with a review record. A float with no review of its
   current fingerprint fails the check, by name. `--render` writes one PNG per float from a compiled PDF and its
   `.aux`, and a review sheet, so a reviewer (a person or a multimodal model) has the pages to look at.
3. Both run as catalogued checks, so their state is shown per turn, goes stale when their inputs change, and the
   generator check goes stale when the data repository's HEAD moves.

## Non-goals

- Judging a figure. The review record says who looked at which version and what they said; the verdict is theirs.
- Checking numbers by presence in an artifact (see Problem 1).
- Reading the data repository's working tree. Uncommitted generator changes are reported, not used.
- Cropping floats out of a page. A float is reviewed on the page it prints on, with its caption.
- The reviewer's model family. The record names the reviewer; the domain-reader gate is 31.6's.

## Decisions

- Manifest: JSON in the manuscript repository, `inputs.generated`. `covers` is a list of globs; `hand` maps a copy
  to a reason; `generators` is a list of `{name, repo, export, run, copies}`: `export` is the pathspecs archived
  from the repository's HEAD into a temporary tree, `run` is the argv run there (`{repo}`, `{tree}`, `{out}` are
  substituted; `{out}` is an empty directory), `copies` maps each manuscript path to the produced file.
- Comparison: whole-line comments, trailing spaces and blank lines ignored; everything else compared as written,
  bytes kept (changed in review round 1: stripping every comment folded a trailing `%` and a `%` in a URL away).
  The report gives the first differing lines of each copy.
- Staleness: an `outside` entry of the form `git:<repo>` is the repository's HEAD commit, so the check reruns when
  the data repository commits, without hashing the repository's files.
- Float identity: its first `\label`, or `<file>#<n>` when it has none. Floats are found in the draft, the
  `also_checked` files and every file they `\input`, including a float environment that lives inside an input
  file. Fingerprint: sha256 over the float's environment text (comments dropped, spaces collapsed: the caption and
  the layout commands around it) and, for each file the float pulls in (`\input`, `\includegraphics`, recursively
  through `.tex` files), its path and bytes. A change inside a comment does not reopen a review.
- Review record: TSV `label, fingerprint, reviewer, date, verdict, note`. Only a row whose fingerprint is the
  current one counts. Rows for labels that no longer exist are reported as stale rows.
- Render: pages come from the `.aux` (`\newlabel{<label>}{{n}{page}…}`); `pdftoppm` renders each page once. The
  sheet lists each float's label, page, caption, fingerprint and PNG path, and a record row to fill in.

## Acceptance

- Probe (red first): a synthetic data repository whose generator emits a table; the manuscript copy with one cell
  changed fails and names the copy and the line; the unchanged copy passes; a copy produced by an uncommitted
  generator change is not used.
- Probe: a table under a covered glob that the manifest does not list fails; listing it as hand-made passes and is
  reported.
- Probe (red first): a synthetic draft with two floats and a record for one: fails and names the other; changing
  a pulled-in image's bytes makes the reviewed one fail too.
- Empty inputs exit 2 (the fails-closed registry lists both scripts).
- On the real manuscript: the generator check reproduces the one known differing copy before any fix, and a person
  reads each float at its rendered page before a review row is written.

## Review round 1 (2026-09-25, independent reviewer on the generator check; every finding reproduced first)

- The working tree still reached a run through the interpreter: PYTHONPATH, an editable install whose `.pth` points
  into the repository, `{repo}` in the arguments. The report said the uncommitted change was "not used". Now
  PYTHONPATH and user site-packages are removed, the interpreter's `.pth` and editable-finder files are searched for
  paths inside the repository (compared resolved: the first fix compared strings and missed a path written through
  a link, which its own test caught), and `{repo}` is allowed only as the interpreter.
- Copies were read after the generators ran, so a generator that syncs into the manuscript made its own copy match:
  copies are read first, and a copy that changed during the run fails.
- A produced path with `..`, or through a link committed in the data repository, removed a file outside the run:
  paths are resolved before anything is removed, and links are not extracted from the archive.
- Comparisons folded different files together: empty output against a comment-only copy, a trailing `%` (LaTeX
  joins the lines), `%` in a URL, invalid UTF-8 bytes. Only whole-line comments are dropped now, bytes are kept, and
  output with no content line fails.
- A `covers` pattern with a typo silently turned the unlisted check off; a name differing only in case escaped it;
  `./` in a key and a copy listed under two generators were counted twice; a timeout left grandchildren running.
- Not changed, written down: any commit to the data repository reruns every generator (one real manuscript: about a
  second); the generator is not sandboxed and can write anything it names by absolute path; Python 3.8 was checked by
  parsing only (no 3.8 interpreter on the machine).

## Review round 2 (2026-09-25, independent reviewer on both scripts; fourteen findings, all reproduced first)

Float reviews, a float that printed differently kept its review: a blank line (a paragraph break) was collapsed into a
space; a trailing `%` between images was dropped; `\includegraphics[...]` followed by a line break or a space before
its argument was not followed; `\import` resolved from the root, not its directory; a bare file beside `plot.png` was
hashed instead of the image; preamble macros and data files (`\addplot table`, `\includestandalone`,
`\lstinputlisting`, `\csv...`) were never followed. Floats were missed: `\begin {figure}`, an environment defined
around `figure*`, `longtable`, `\captionof`, a label inside an input file; floats in `\iffalse` and comment
environments and a `\newenvironment` definition were counted; an `\input` naming a macro was dropped silently. A
pulled `.tex` was hashed by bytes, so a regenerated table's timestamp comment reopened it. Render took the printed
page number as the PDF page, let two PDFs with one name overwrite each other's PNGs, rendered a label present in two
`.aux` files from the first without saying so, did not follow `\@input` in an `.aux`, compared `--built-from` files
from the repository root when run in a subdirectory, and crashed on a missing `--aux`. Now: the fingerprint is taken
over the text as it bears on the page (whole-line comments and inline comment text dropped, the `%` kept, a paragraph
break kept), every pulled `.tex` by that text, data files and the main file's preamble with what it pulls in included;
floats are found in the document body only, with the other spellings above; a macro `\input` fails the check; the
page is the physical one from the PDF's named destination for the label's anchor.

Generator check, round-1 fixes that did not hold: a script in the repository as the first word, and an absolute or
`~` path to it in the arguments, still ran uncommitted code; a relative `.pth` line and an interpreter reached through
`/usr/bin/env` escaped the editable-install search; `{out}/sub/../x` was reported missing. Now only a python in a
`bin/` directory may live in the repository, any other word pointing into its working tree is refused, `.pth` lines
are resolved as site.py resolves them, the interpreters a command runs are found on its PATH, and produced paths are
normalised. Three mutants survived the first set of tests (a relative `.pth` line whose fixture also carried an
absolute tail, a comment-only change in a table that sat in its own float, a macro `\input` in a draft whose floats
were all unreviewed anyway); each test was sharpened until its mutant died.

Not changed, written down: macros defined outside the preamble, `\graphicspath`, packages and classes are not
followed; the float search is textual, so an environment built by a macro that is not a `\newenvironment` is not seen.

## Review round 3 (2026-09-25; sixteen findings, five of them regressions round 2 introduced; all reproduced first)

- Regressions. The `\iffalse` strip ran from a `\let\ifanon\iffalse` in the preamble to the first `\fi` in the body
  and dropped a live float (a false pass): only an `\iffalse` that starts a line opens a dead block now, it ends at
  its matching `\fi` with TeX's and `\newif`'s conditionals counted, and with no match nothing is dropped. Every line
  break had become part of the fingerprint, so re-wrapping a caption reopened it: the text is now read as TeX reads it
  (a line break a space, a `%` at the end of a line joins, a blank line a paragraph break). Inline `\addplot table`
  data was reported as a missing file. A caption on the sheet lost its `\%`. A `filecontents` block holding
  `\begin{document}` moved the preamble.
- Design: every edit to the preamble or a file it pulls in reopened every float at once, and a new `\etal` looked the
  same as a font change; the reviewer judged that people would re-stamp without looking. The preamble is now one item
  of its own (`preamble:<main>`), reviewed once; floats no longer carry it. A macro-named or missing `\input` in the
  preamble fails the check, as the docstring already claimed.
- Still false reviewed after round 2, now followed: a table `\pgfplotstableread` fills in the body and `\addplot
  table {\macro}` uses; a `\captionof` inside `center` with its image above a blank line; `\includesvg`. Noise:
  `\graphicspath` made every figure a missing file; its directories are tried now.
- Generator check: a script started through bash that calls the python on PATH, and `env -u NAME python3`, reached an
  editable install; the python3 and python on the run's PATH are now always searched, and env's options are skipped.
  Refused although legitimate: `env NAME=value {repo}/.venv/bin/python` (a python in a `bin/` directory is allowed in
  any position), a TMPDIR inside the repository (the run's own directories are exempt), a relative `.pth` line to a
  directory that does not exist (site.py ignores it, so does the search).
- Not changed, written down: an image named inside a `\newcommand` is not followed (macro expansion is out of scope);
  the reader is textual, so a conditional built another way than `\iffalse` at the start of a line is typeset text to
  it.

## Review round 4 (2026-09-25, narrow: regressions of round 3 only; ten findings, all reproduced first)

- Reading as TeX reads had been applied to text TeX does not read as prose. A re-wrapped listing, a joined verbatim
  line and re-flowed inline plot rows kept their review; a `filecontents` block edited in the preamble counted for
  nothing until the next build. Verbatim-like environments, inline plot data and filecontents blocks are now sealed
  first: each becomes a token carrying the hash of its raw text.
- A `\captionof` in a minipage beside the image's minipage left the image out: the outermost wrapper is taken.
- An `\iffalse ... \else FIGURE \fi` dropped the live figure, and a `\newif` inside a dead block opened a conditional
  that closed on a later `\fi`: an `\else` at the block's level keeps the whole block, and `\newif\ifname` opens
  nothing.
- The preamble item failed on a macro's `#2`, on `\input{tables/#1}` and on a TeX-distribution file such as
  `glyphtounicode`, with no way to clear it; inline data read into a table macro was a missing file. Parameters are
  skipped, a file `kpsewhich` finds is the distribution's, whitespace in a table source means inline data.
- Generator check: a script named `bin/python_gen.sh` passed as an interpreter; a command naming its own venv python
  was refused because another python on PATH had an editable install; `env -S` hid its program; a `.pth` line naming
  a zip in the repository was skipped. Interpreters are matched by name (`python`, `python3`, `python3.11`); PATH
  pythons are searched only when the command runs a shell or a script; `env -S` is read; any path site.py would add
  counts.
- Also from this round: `\graphicspath` in a file the preamble inputs is read, and without `--built-from` a preamble
  newer than the PDF marks every float stale.

## Where the reviews stopped, and what is left

Rounds 2, 3 and 4 reported 14, 16 and 10 defects (round 1's report grouped its findings and was not counted item by
item); each was reproduced, fixed, and given a test that fails on the reviewed code and a mutant the test kills. The kind of finding moved from ordinary layouts (a copy read after its generator
ran, a blank line that did not count) to rare ones (an `\else` inside `\iffalse`, a listing inside a figure), and two
rounds found regressions the previous round's fixes introduced. A textual reader of TeX will keep having such cases,
so the review loop was stopped here on this rule: when uncertain, the float check reopens a review and the generator
check refuses a run, rather than the reverse. Known and left:

- what a macro expands to (an image or a file named inside a `\newcommand`);
- conditionals other than a line-start `\iffalse` (`\ifdraft ... \fi`, `\iftoggle`): their text counts as typeset;
- an image name present in two directories: the first found here, which can differ from LaTeX's choice;
- a python the generator starts from PATH when the command names its own interpreter: not searched;
- the generator is not sandboxed and runs with the user's rights.

## After the reviews: a table in the running text (2026-09-25, found on the real manuscript)

Fixing the figures on the real manuscript showed a table set in the running text (a `center` with a `tabular`, no
float, no caption) that the check never listed, though it prints like any other. Such a tabular is now its own item,
`<file>#tabular<k>` by order in the file: its `center` or `minipage` when there is one, else the tabular alone (not the
paragraph before it). A tabular inside a float, beside a `\captionof`, or in a file a float pulls in belongs to that
float and is not listed twice. Test T253; four mutants killed after one test was extended.

## On one real manuscript

- Generator check: 18 copies, 17 matched and one figure differed; the figure had been corrected by hand in the copy
  and not in its generator. After the generator was fixed in the data repository, 18 of 18 match.
- Float reviews: 20 floats found (4 figures, 16 tables, including tables that exist only in the supplement; the same 20
  after round 2, and the round-2 render of the same build is byte-identical page for page). The
  rendered pages were read by the drafting session (same model family as the drafter), and the record holds 11 ok and
  9 fix with notes: overlapping markers that hide cells a caption says are drawn, legends whose markers sit nearer the
  previous label, a CJK font falling back to a second typeface inside a table about character forms, note rows that
  widen tables, a hyphen for a minus sign, and narrow tables scaled up by `\resizebox{\columnwidth}`. The render
  step's older-version marking was probed with a build commit from before the last figure changes: the four changed
  figures and one changed table were marked, the rest were not.

