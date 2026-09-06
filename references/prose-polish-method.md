# Prose Polish Method — measure, then edit, then re-measure everything

Distilled from ten polishing rounds on a real manuscript; every rule below
stands on a mistake that actually happened. Tool-neutral: the measurements
come from `.claude/skills/audit/scripts/audit-prose-fingerprint.py` (punctuation and distribution)
and, when available, a sentence-structure measure of the project's own; the
rules do not depend on either.

**One line:** measure, never judge by feel; read distributions, not counts;
change sentences, never numbers; stop at the boundary; after every round,
re-measure everything.

## 0. Preconditions — do not start without them

| Condition | Check |
| --- | --- |
| The baseline corpus is the manuscript's **own** reference PDFs, twenty or more | count them |
| The baseline contains **none of the author's own papers** | name pattern → `--exclude` |
| The working tree is clean and the pre-polish commit is written down | `git status` empty; note the hash |
| A compile/health baseline was recorded once before touching anything | run the project's checks, keep the numbers |
| No other session is editing the same tree | check file mtimes; never treat an early copy as the current state |

Why the author's own papers must be excluded: a baseline that includes them
uses the author as the ruler that measures the author. In one real case the
extreme values on two metrics both came from the author's own earlier paper.

## 1. Positioning before style — the order is not negotiable

Style problems can be repaired at any stage; positioning problems cannot be
repaired after submission, and a late citation reads as remedial. Do these
in order and do not proceed while one fails:

1. **Claim positioning** — every term the manuscript advertises (keywords,
   title, contribution statements) must trace to a source in its own
   bibliography. Keywords naming a concept the bibliography never sources is
   a contradiction visible from inside the manuscript.
2. **Method attribution** — for every self-coined term ask: does this
   phenomenon already have a standard name? is this analysis a variant of a
   known diagnostic? Reproducing a standard diagnostic independently is a
   credit; failing to say so is a debit.
3. **Counter-evidence search** — especially for negative findings ("the
   model cannot X"): look for published results on the other side, cite
   them, and state the difference. The conclusion gets stronger, not weaker.
4. **Method citations** — every statistical procedure used in the body has a
   citation.
5. Only then, style.

`.claude/skills/audit/scripts/audit-claim-positioning.py` covers step 1 and the method-citation
part of step 4 deterministically. It checks that a source is present, never
that it is the right one.

**Bibliography discipline:** never write a BibTeX entry from memory — resolve
the DOI through content negotiation and replace only the citation key. Clean
what registries return (all-caps author names, HTML tags in titles, bare month
strings). After edits, the full audit must show bibliography entries equal to
body citations, zero dangling, zero missing.

## 2. Establish the measurements before changing a word

Run the fingerprint audit on a directory that holds only the manuscript's
prose files (no logs, no notes) against the baseline corpus. Record the full
pre-polish table. Also record which files are in scope: whatever you edit
later must be inside the measured set — abstract, appendix, and captions
included. Scope that leaks is the most common way a manuscript reads
"in range per section, out of range as a whole".

## 3. How to read the numbers

- **Out of range is the hard signal; a percentile is a soft one; clustering
  and the longest gap matter more than the total.** The same construction
  used often but in clusters reads as human; used at the right rate but
  spread evenly reads as machine.
- **Dispersion baselines are computed per document and never pooled.**
  Pooling gaps across documents of different rates inflates the coefficient
  of variation and once turned a clear overshoot into an apparent pass.
- **Short sentences are not the same as readable sentences.** A manuscript
  can sit at a low sentence-length percentile while its clause density per
  comma exceeds every baseline paper: dense, not long. The remedy is more
  commas and fewer clauses, not shorter sentences.
- **Diagnose causes from history, not from a story.** Run the same metrics
  on the pre-polish version before attributing a shift to the polishing.
- **A proxy metric is not evidence until it has been hand-sampled.** "37% of
  paragraphs end in an aphorism" turned out to be one real aphorism and many
  short factual sentences.
- **When two tools disagree, ablate one factor at a time** and report which
  document produces each extreme value. Do not pick the tool you prefer.

## 4. Edit operations, ordered by value and risk

Before every change ask: is the sentence better to read after this? If not,
do not make it — even when a metric wants it. Changing a construction's
surface form is not removing it (`rather than` → `, not` is the same family).
Vary the replacements deliberately; replacing everything with full stops
swaps one uniform pattern for another.

1. **Pure punctuation first** (zero semantic risk). Add every legitimate
   comma, then stop: manufacturing commas the prose does not want is a new
   artefact.
2. **Tics**: corrective diptychs (`X rather than Y`), explanatory colons,
   semicolon chains, paragraph-final aphorisms. Test for the diptych: does
   the negated half exclude something the reader would otherwise believe?
   Keep it if yes; otherwise drop the negation or split the sentence.
   Splitting semicolons drives lag-1 sentence-length autocorrelation
   negative; the repair is to merge the too-short sentence into the next one
   (long–medium–medium), not to restore the semicolon.
3. **Structure**: subordinate to coordinate without splitting; move the
   relative clause that sits between subject and verb to the end; split a
   30-word three-clause sentence into two of fifteen words each. Leave
   deliberate parallel triplets alone.
4. **Local**: sections already inside the baseline range are not touched.

## 5. After every round, without exception

- **Content invariance**: numeric tokens and citation keys must be identical
  before and after — zero difference.
- **Self-injury scan**: comma followed by a capitalised pronoun, doubled
  words, `. .`, `; ;`. Compilers do not read English and numeric diffs do
  not read prose; only this scan catches a comma splice.
- **Compile and health checks**: the same set as the baseline, compared.
- **Re-measure every metric, not only the one you changed.** Suppressing
  one device raises another: halving semicolons pushed sentence-length
  autocorrelation below the baseline floor.
- Commit.

## 6. Stop conditions

- **Stop at the boundary; do not worship the metric.** Eleven of twelve in
  range and the twelfth ten percent out is a more honest stopping point
  than a forced all-green.
- **An instrumental target is not the goal.** A comma-rate threshold was
  only one of two routes to the clause-per-comma target; once clauses fell,
  chasing the threshold would have manufactured commas the prose did not
  need.
- **When legitimate edits are exhausted, stop and report the remaining gap**
  for the author to decide whether to change approach.
- **Scope covers the whole manuscript**: whichever files were edited must be
  in the measured set.

## 7. Discipline for the tools themselves

- A new test must first fail on the old code. Two of four "new" tests once
  passed on the old implementation — one fixture was confounded, one targeted
  the wrong tool.
- A sentence-splitting rule must be equally harmless on both sides of the
  comparison; a rule that adds noise to PDF baselines by citation style must
  go.
- Filtering before computing autocorrelation joins the two sides of a gap;
  keep placeholders and use only truly adjacent pairs.
- A configuration whose conclusion flips when one parameter changes is
  itself evidence that it should not be trusted.
- Alignment between two tools is accepted on agreeing verdicts, not equal
  numbers; differences of scope are written down, not smoothed away.

## Traps that have each happened at least once

| Trap | Symptom | Countermeasure |
| --- | --- | --- |
| Checking the proxy, not the object | pooled CV; `[12]` read as a citation; `that` inflating clause counts | sample the object before trusting any proxy |
| Scope missing files | in range per section, out of range as a whole | write the scope down in step 2 |
| Fixing one metric breaks another | semicolons pass, autocorrelation fails | full re-measurement in step 5 |
| Changing the skin, not the construction | `rather than` → `, not` | ask whether the negated half is working |
