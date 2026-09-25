# Generated copies and float reviews: tables and figures the loop never looked at

Status: draft (2026-09-25). The author asked on 2026-09-25 to continue the remaining toolkit items with a grill at
each step; this spec is written before the code and is not author-approved. Items 31.3–31.6 of the same list
(claims strength, statistics review, method sentences, domain reader) are specified in
`2026-09-25-review-gap-closure.md` §4.4 and built in another session; this spec does not touch them.

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
   committed state (never its working tree, never in place) and compare the copy with the output, LaTeX comments
   ignored. A copy that differs, a generator that fails, or a file under the manifest's covered globs that the
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
- Comparison: comments stripped (an escaped `\%` is text), trailing spaces and blank lines ignored. The report
  gives the first differing lines of each copy.
- Staleness: an `outside` entry of the form `git:<repo>` is the repository's HEAD commit, so the check reruns when
  the data repository commits, without hashing the repository's files.
- Float identity: its first `\label`, or `<file>#<n>` when it has none. Floats are found in the draft, the
  `also_checked` files and every file they `\input`, including a float environment that lives inside an input
  file. Fingerprint: sha256 over the caption text and, for each file the float pulls in (`\input`,
  `\includegraphics`, recursively through `.tex` files), its path and bytes.
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
