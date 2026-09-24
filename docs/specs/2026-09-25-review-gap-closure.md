# Writing loop: what one co-author reading found that three weeks of checks did not

- **Status: draft.** Written 2026-09-25. Not author-approved, not implemented, not verified. The author asked for all
  the remaining toolkit work to be done while a co-author reads the manuscript; §4 is carried out on the recommended
  defaults, each of which can be overturned.

## 1. Problem

A journal manuscript went through three weeks of the writing loop: claims ledger, over-reach scan, number ledger,
sentence gate, reader panels, independent grills. Every check was current and the paper state had no sentence over
the line. A co-author then read it once and found two sentences that overstated their evidence, a universal negation,
a statistical test that treated dependent observations as independent, and a question about
the benchmark's construct that no reviewer in the loop had raised.

The evidence and the per-item analysis are in the private workspace repository, not here. What they show about the
toolkit falls into six failures:

1. **The scan shrank silently.** `draft.sections` selects sentences by heading. Two restructurings renamed headings,
   the old names stopped matching, and about a third of the body text dropped out of every sentence-level check. The
   word-count check, reading the whole file, reported the full length the whole time. Figure and table sources and the
   supplement were never in `draft.glob`.
2. **Deleting was free.** The sentence gate and the rate-based checks penalise what is written, never what is removed.
   Under every check the cheapest move was to delete, and a research question, three qualifiers and a denominator were
   deleted that way. A `必须出现` pattern now turns red when its sentence goes, but only across the whole draft, so it
   cannot say "the problem must come first".
3. **The ledger was checked, not questioned.** The over-reach scan asks whether a sentence says more than the ledger
   allows. It never asks whether the ledger's allowed wording is stronger than the test behind it. Method sentences
   ("only X differs", "no cue is left") are not claims, so nothing compared them with the results and limitations.
4. **The reader panel measured its own noise.** Rerunning one packet with one prompt moved a recall count by the same
   margin the rule calls a clear drop. Free recall is zero-sum across memory points. The judge checks whether a point
   was mentioned, not whether it was attributed to the right thing. The person revising the text was the only coder of
   a derived metric. The prompted questions are answerable by copying the abstract, and they sit at ceiling. The
   packet builder rendered every cross-reference as `§x`, and most readers spent their "what got in the way" answer on
   it.
5. **No check was ever shown a real failure.** A draft with its research question deleted passed every check. None
   of the checks was written from a known bad draft, so a fully green run says nothing.
6. **Nobody looked at the figures.** Rendered figures, table cells beyond the ones the text quotes, and the supplement
   were outside every check. Two figure-versus-data contradictions were found by opening the rendered images, outside any check.

Two further items were handed over with these: whether the revision ring needs an analysis stage, and how the claims
ledger's to-do items and the conversation list stay in step.

## 2. Goal

Each failure above gets a check that turns red on the draft or configuration that actually failed, and stays green
on the corrected one. A check that cannot be shown to go red is not counted as added.

## 3. Non-goals

- Judging whether a figure misleads, or whether a domain construct is right. The toolkit can put the rendered figure
  and the construct in front of a reviewer and record that the reviewer saw them; the judgement stays with a person.
- A readiness score, or any state that reads as green (the paper-state spec keeps no green state; this does not add
  one).
- Changing the manuscript. The workspace repository is read for probes; nothing is written back to the draft.
- Statistical review of preregistered analyses as code. It becomes a recorded gate with a named reviewer who is not
  the drafter; the review itself is a person's.
- Real manuscript text, author names or result numbers in fixtures. Every probe in this repository is synthetic. Before
  each commit the diff goes through the private workspace's verbatim-overlap scan and is read by a person for
  manuscript names and findings, which the scan cannot see.

## 4. Decisions

Ownership. Failures 1 and 6 (scan coverage; the supplement and figure/table text in the over-reach scan) are on
`feat/scan-coverage` in another session, with their own spec (`2026-09-24-scan-coverage.md`). This spec covers the
rest. It touches `state.py` only after that branch lands, because both change `scan`.

Order: 4.1 first, because every later rule is accepted by a probe in it.

### 4.1 A probe set that must go red (failure 5)

- `experimental/writing-loop/engine/tests/probes/`: synthetic drafts, each a small LaTeX file with a README line
  naming the failure it reproduces, the check that must flag it, and its corrected twin.
- `tests/test_probes.py` runs each named check on both files: red on the bad one, green on the twin. A probe whose
  bad file passes fails the suite. A check with no probe is listed by the test as unprobed (listed, not failed, so
  the list is honest about what has none yet).
- Every rule in 4.2–4.5 lands with its probe. The first probe is the one that started this: a draft whose research
  question was deleted, which today passes every check.

### 4.2 Deleting is not free (failure 2)

- **Sentence gate.** `audit-sentence-changes.py` judges removed sentences, not only counts them. A removed sentence
  is flagged when it carries something: it matches a pattern passed with `--carriers <file>` (the loop passes the
  claims ledger's `必须出现` patterns and each claim's `承载` patterns, below), or it holds a number, or a limiting
  qualifier from a short fixed list (only, at most, in this benchmark, of N, may, estimated, exploratory, ...). A
  flagged removal needs a reason in the TSV exactly as a new sentence does. The report prints removed and flagged
  counts separately, so "0 flagged" can be told from "nothing was compared".
- **Where a wording must appear.** A `必须出现` pattern may name where: `- 必须出现：<regex> @ A, I1` means the
  abstract and the first paragraph of the introduction, by sentence-label prefix. Each place is checked on its own;
  a pattern that matches elsewhere but not in a named place is absent from that place. Unscoped patterns keep today's
  meaning. This is the "problem first" invariant: the research question must appear in `@ A, I1`, not just anywhere.
- **What a grill must read.** A claim may list `- 承载：<regex>` for the sentences that state it. `loop state` prints,
  per claim, every sentence that carries it, changed or not, so a grill reads the unchanged abstract sentence that
  states the result as well as the rewritten one.

### 4.3 The reader panel measures the text, not itself (failure 4)

- **Cross-references.** `build-reader-packet.py` resolves `\ref` from the compiled `.aux` when one is given
  (`--aux`); without it, references become `§(number omitted)` and the instructions tell readers the packet omits
  section numbers. Probe: a packet built from a draft with references has no `§x` in it.
- **Noise floor.** `tally-readers.py` reports, per memory point, the spread between repeat runs of the same packet
  (file names already carry a run number). With `--compare`, a change no larger than that spread is reported as
  inside the noise, whatever its p value; without repeat runs on both sides the comparison says it has no noise
  floor.
- **Recall is zero-sum.** Free recall is reported with the rank at which each point was recalled. A drop in free
  recall alone is not an alarm; the alarm needs the prompted question to drop too.
- **Attribution.** The judging criteria carry a fact sheet per point (who or what did it, the number). A point
  mentioned but attributed to the wrong thing is its own grade and does not count as carried. Before judging, the
  judge grades a fixed injected set (correct, misattributed, reversed, bare number); more than two misses on it stops
  the panel.
- **Blind derived metrics.** A derived metric (a misreading count, "the introduction repeats the abstract") is
  reported only when its coding file comes from a coder other than the session that revised the text; otherwise the
  report says it is uncoded.
- **Repetition, measured.** Shared word n-grams and the longest verbatim run between the abstract and the first
  paragraph of the introduction are computed, not asked; readers' complaints stay as supporting evidence.
- **Questions that can be copied, and a blank reader.** A directed question whose key phrases appear verbatim in the
  abstract is flagged. A blank reader, who answers only by copying the abstract, is scored like the others; a point
  the blank reader carries is reported as not evidence that readers carried it. Results are grouped by model family.
- **Registration.** `check-reader-output.py` reports a `remember` field given as a string as "a string, not a list"
  instead of "missing or empty", and a panel that is not registered by `tally-readers.py` is not counted as run.

### 4.4 The ledger is questioned (failure 3, the parts outside scan coverage)

- A claim's `允许的说法` may cite the test that supports it (`- 依据：<artifact or test id>`). A claim stated as a
  universal negation (none, no, never, not) with no `依据` or no power note is flagged by `loop state`.
- An evidence note of the form "A significant, B not significant" used to say A differs from B is flagged.
- Method sentences that close off an alternative ("only X differs", "no cue left", "all identical") are listed by
  `loop state` beside every sentence in the results and limitations that names a remaining cue, for a person to read.
- The statistical review before a preregistration freezes, and the non-Claude domain reader before upload, become
  gates in the risk register with a named reviewer; the loop reports them open until a person closes them. It does
  not do either review.

### 4.5 The ring gets an analysis stage (handed-over question)

- Recommended default, can be overturned: yes. Stage `analysis` (分析) sits between 设计 and 改稿. It is seen through
  the claims ledger: an open 待做 of type 分析 hangs on it; one closed within the round marks it done.
- Blocked on the notch: the ring is drawn by the lintel host at a fixed width per stage. The engine change lands
  behind a flag until the host is checked at eight stages on the real notch.

### 4.6 Design only in this round

Not implemented here, written down so the next round starts from it: how the conversation list and the next step
divide the work (every item says what it blocks; the next step names the first item and why); a bridge from the
claims ledger's 待做 to the conversation list; a status for work deferred past submission that is shown but does not
hold the paper at 未就绪; a way for 落稿 to be seen (a commit to the draft after the last review gate closed); and
labels that tell "how far the round got" from "where it waits".

## 5. Acceptance

- Each rule in 4.2–4.5 has a probe in 4.1 that is red on the bad draft and green on its twin, and a mutation of the
  rule's code turns its probe red (`redcheck.py`).
- The full writing-loop suite and `scripts/test.sh` pass locally under Python 3.8 as well as the default Python; CI on
  the pull request passes.
- Each flagged sentence the new rules raise on the real manuscript is read by a person before a count is reported;
  the precision is recorded in the private workspace, not here.
- The installed copy the hooks run is checked after landing, not only the branch.

## 6. Known limits

- The qualifier list and the carrier patterns catch what someone wrote down. A qualifier phrased another way is
  removed without a flag. Measured on the change that started this (in the private workspace): of five introduction
  sentences removed without a successor, the removal check flags two, both only because they held a digit; the
  sentence that stated the problem held no number, no qualifier and no required wording, and is not flagged. The
  removal check protects what the ledger names; the problem sentence is protected only once `必须出现 @ A, I1` (4.2,
  second bullet) names it.
- The blank reader and the noise floor make the panel more honest about what it cannot see; they do not make a
  sixteen-reader panel precise.
- The injected set checks the judge on known cases; a judge can pass it and still misgrade a new kind of answer.
- Every reviewer in the loop is still the same model family. 4.4 records a human domain reader as a gate; it cannot
  supply one.
