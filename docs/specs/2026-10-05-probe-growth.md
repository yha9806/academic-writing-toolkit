# Growing the probe set from defects the checks missed, one confirmed batch at a time

Status: batch 1 implemented and pushed to its branch, no pull request (2026-10-05). Batch 2 implemented and pushed
to the same branch, no pull request (2026-10-05). The ledger cap of batch 2's held-back part implemented locally
(2026-10-05), not pushed. The author approved the idea ("grow the red-check set by target band, with the author
confirming each defect") and confirmed all three defects of batch 1 and all three of batch 2 (gate 1, "三条都算"
both times). The spec itself has not been read by the author.

What was run for batch 1:
- Each probe's bad draft failed on the old code; each new unit test that asserts a flag failed there too.
- 20 red-check mutants (`probegrowth`) each turned their test red.
- A new cross-check: no probe's corrected twin raises any probe's flag. Loosening the near-repeat threshold to 0.5
  turns it red.
- Read-only runs on one real draft, below.

Python 3.8 was checked by grammar only. CI has not run.

## Problem

The probe set (`experimental/writing-loop/engine/tests/probes/`, spec 2026-09-25 §4.1) holds six synthetic drafts. All
six are for the changed-sentence gate, and each was added after an incident. Meanwhile the private gap notes from one
manuscript record about sixty defects in the text that the checks of the time let through. Nothing decides which of
them should become probes, so the set grows only when someone remembers to add one.

Two things found while picking the first batch:

- A note's "no check catches this" goes stale. One candidate, a rewrite that copies another section's sentence word
  for word, is caught today by `duplicates_elsewhere`. Gate 2 has to be measured, not read from the note.
- About 25 of the 58 candidates need reading to see: the meaning, the code, a figure, or a cited source. No string
  rule will catch those, and they belong with the reader panels and the grill.

## Goal

A defect becomes a probe only after three gates (EnvHarness's write–verify loop, with the author as the benchmark's
own verdict):

1. **Real**: the author confirms it was a defect.
2. **Challenging**: today's checks miss it, measured on its synthetic bad draft.
3. **Solvable**: a rule can be written that flags the bad draft and not its corrected twin.

## Non-goals

- Defects a model makes up with no incident behind them (R-Zero-style self-play). Version 1 draws only on recorded
  incidents.
- Defects that need reading. They are closed as "needs reading" and stay in the gap notes.
- Adding a probe automatically. Every probe lands with its rule in a reviewed change.
- Loosening an existing check so that a probe passes.

## Decisions

**D1 Where things live.** The candidate list names a real manuscript, so it stays in the private workspace
repository. A probe in this tree is synthetic, with no manuscript wording, names or results, as now.

**D2 Gate 1.** The author confirms a batch of at most three. The confirmation (message uuid) goes in the private
candidate list. Unconfirmed candidates are not built.

**D3 Gate 2.**
- The synthetic bad draft is run through the checks that read that kind of text.
- If one of them already flags the defect by name, the candidate is closed as covered, with the flag recorded.
- A style flag on the same sentence (`longer`, `adverb`) does not count as catching it.

**D4 Gate 3.**
- The new rule flags the bad draft.
- It flags neither the twin nor the twins of the existing probes.
- A read-only run on one real draft counts its other hits. The count is reported with the rule; no threshold is fixed
  in advance.
- At most two revisions. After that the candidate is closed as "needs reading", with a gap note saying why.

**D5 The test.**
- `test_probes.py` gains a `CHECKS` entry when a probe names a check other than the sentence gate.
- `expect_flag` names the new rule's flag, so a probe caught by a different rule does not count.

## Batch 1 (measured 2026-10-05, gate 2 run on synthetic drafts)

| Defect | Today | Gate 2 |
|---|---|---|
| A sentence rewritten to copy another section's sentence word for word | `duplicates_elsewhere` | covered |
| An introduction sentence that repeats the abstract except for one word | nothing | missed |
| "N times more often than chance" with no hit count or denominator beside it | `longer`, `adverb` only | missed |
| `\label` after a run-in `\paragraph`, so `\ref` prints the enclosing section's number | no script reads it | missed (by search, not by running every check) |

The three missed ones went to the author, who confirmed all three (gate 1).

## Batch 1 results (gate 3)

| Defect | Rule | Bad / twin | Other hits on one real draft |
|---|---|---|---|
| A sentence that repeats another but for a word | sentence gate, `repeats_elsewhere`: a changed sentence of 8 words or more whose word sequence matches another sentence of the draft at difflib ratio 0.8 or more, and is not the same (that stays `duplicates_elsewhere`) | flagged / not | All pairs in the draft: 3 at 0.8 or more, 12 at 0.7. Each of the 3 restates an abstract or conclusion sentence in the body; most of the 12 are paraphrases, which is why the threshold is 0.8. The latest real round flags 2 more sentences, one such pair |
| A multiple of chance with no count beside it | sentence gate, `multiple_without_count`: "N times … chance/random" or a math multiple followed by "chance" ("the MATH chance level" excluded), with no "K of N", "K hits in N" or "K/N" in the sentence or the one either side | flagged / not | The draft states a multiple of chance in 14 sentences: 5 with a count in the sentence, 3 with one in a neighbour, 6 with none. The latest real round flags 1 more sentence |
| A `\label` on a heading with no number | new check `audit-cross-refs.py` (loop id `cross-refs`), LaTeX, follows `\input`: a label inside or right after a starred heading or one deeper than secnumdepth (last `\setcounter`, else the class default), reported only when a `\ref`, `\cref` or `\autoref` prints it | flagged / not | 7 labels, each on a run-in paragraph. The compiled draft's `.aux` gives all 7 the number of the section around them, so 7 of 7 are true; two pairs of them share a number |

Three remarks:
- The real draft's counts for the two sentence-gate rules are not an out-of-sample test: the 0.8 threshold and the
  two exclusions of the second rule (a random draw of sub-pools, "the MATH chance level") were set after reading that
  draft's hits. The third check was not changed after the run, and the `.aux` comparison is independent of it.
- The sentence-gate rules flag only changed sentences, so the counts above are what a round could raise, not what
  the next round will. The cross-reference check reads the whole draft, so a workspace that turns it on sees all of
  its hits in the first run.
- The cross-reference check does not see a label placed further down the paragraph, or references made from another
  document (an `xr` prefix). Both stay with the reader.

## Batch 2 (gate 2 run on the whole loop, 2026-10-05)

The 16 remaining candidates the triage agent had marked "a script could catch it" were run as synthetic drafts
through every check the loop runs, the state computation, and the claim ledger with an empty ledger. Three positive
self-tests (a duplicate sentence, an uncited "prior work" claim, a universal negation) went red first, so a silent
harness would have shown. Five candidates were already caught, one partly (a coined name: caught only when its
definition is cut in the same round), seven missed. Three of the missed needed no new registration and went to the
author, who confirmed all three (gate 1). The other four need a terms table or a ledger field and wait.

| Defect | Today | Gate 2 |
|---|---|---|
| The abstract keeps none of the words of the title's main clause | nothing | missed |
| In an author-year style, "Smith et al. report ... \\citep{smith}" prints the name twice | nothing | missed |
| The abstract's first use of a name the paper coins does not say what it is (definition never in the abstract) | nothing | missed |

## Batch 2 results (gate 3)

| Defect | Rule | Bad / twin | On one real draft (read-only, several commits) |
|---|---|---|---|
| Title words lost from the abstract | new check `audit-front-matter.py` (loop id `front-matter`), LaTeX, follows `\\input`: `title-word-missing-from-abstract` for each content word of the full title that no abstract word shares (plural, or the first max(6, n-3) letters; synonyms do not count) | flagged / not | The commit before the fix lists 3 words; the author's fix lists 2 (it restored one; a later commit added the other two); the current head lists 0. A two-word term whose words both occur apart in the abstract is not seen, and the defect's own example was such a term |
| A coined name the abstract uses before saying what it is | same check, `coined-name-undefined-in-abstract`: a name with an inner capital that the draft says we made or calls ours, whose first abstract sentence neither says we made it, nor describes it (indefinite noun phrase, or "our" with two or more words), nor opens a relative clause on it, nor follows a sentence that says we made something | flagged / not | 1 of 5 commits flagged, the bad one. The first version also flagged two later abstracts that do say what the name is ("NAME is our <adjective> <noun>", "our <noun> of <description>, NAME, whose ..."); "our" with two or more words and the relative clause were added after reading them, so this count is not out of sample |
| An author named in the sentence and printed again by an author-year citation | `reconcile-cites.py` (loop id `cite-bib`), new kind `author-named-twice`, checked only when the style prints names: read from the class, packages and `\\setcitestyle` (last wins), else the bibliography style, or set by the workspace's `target.citation_style` (`--style`) | flagged / not | The draft's source is a numeric class; a venue build rewrites it to an author-year style, so the source alone reads as numeric and nothing is checked. With the style set: the incident's sentence is flagged at the bad commit and not at the fix; the fix left a second sentence of the same form in the same paragraph. The current head has 2 hits, and the venue's built PDF prints both names twice (read from its text), so 2 of 2 are true. The first version also flagged two tests named after their authors ("X's test" beside its source), which is the usual form; methods named by a surname were left out after reading them, not out of sample |

Three remarks:
- A build that changes the class or the bibliography style for a venue leaves the source saying one style and the
  submission printing another. The check reads the source, so such a workspace has to name the printed style.
- The venue build on the measured draft already rewrites "X et~al.~\\cite" into a textual citation; both current
  hits were written with an ordinary space and slipped past it.
- The two current hits sit in a manuscript the author has frozen. They are reported to the author, not changed.

## Batch 2, held back: a cap on how often, and a terms table

Four of the seven missed candidates needed something registered first. Gate 2 was rerun for two of them with a
claims ledger, which the first run had left empty:

- **A new term in the abstract that the body never uses, and a retired term left in a figure caption.** The ledger
  already expresses both: `必须出现：<term> @ <places>` for the first; `越界：<old term>` for the second, which also
  reads figure files when `inputs.also_scanned` lists them. On synthetic drafts with one claim registered, the bad
  drafts are flagged and the twins are not. These are not defects the checks miss but terms nobody registered: no step
  prompts registering them when the abstract is settled. **The author's call (gate 1, 2026-10-05): real defects,
  filed as "the existing fields catch them; not registered". No probe, no new check.**
- **One weakness restated in many sentences, each worded differently.** No field expressed "at most N". **The
  author's call (gate 1, 2026-10-05): real, build it.**

The new field, on a claim: `至多：<regex> ‖ <regex> @ N`, or `@ N A, I1` to count only in those places, together.
It counts sentences of the sentence index that match any listed wording; a sentence matching two counts once.
Supplement and figure sources are not counted. Over the cap, the verdict is 未就绪 with the blocker 说太多遍
<claim>; the table shows every capped claim with its count and sentences, over the cap or not. A cap without a
number is a ledger problem.

| Defect | Rule | Bad / twin | On one real draft (read-only, every indexed version) |
|---|---|---|---|
| One weakness said in more sentences than the author allows | claims ledger, new field `至多` | flagged / not | Five wordings of one limitation, collected by reading the version before the fix, capped at two as the author's card asked. That version: 4 sentences counted, flagged; the source has 5, and the fifth sat under a heading the section rules no longer matched, which the scan-coverage row reported at the time. From the author's fix to the current head: 2 in the source at every version, never flagged. The note on the incident counts a sixth wording that was never found again |

Three remarks:
- Only the listed wordings are counted. The cap is worth having because counting by hand went wrong twice in the
  incident, not because it finds a new paraphrase. A rewrite that rewords a mention drops it from the count silently.
- The count is only as complete as the sentence index. A heading the section rules miss lowers it; the scan-coverage
  row already says so.
- A cap penalises saying it too often and nothing else, so deleting the one place a weakness is stated passes it.
  The sentence gate's `removed_carrier` flag covers deleted carrying sentences, not this field.

Deviation from D5: the bad draft and its twin are unit tests of the paper state (`test_state.py`), not a probe
directory, because `test_probes.py` runs scripts and this rule needs a ledger and a sentence index. A probe's twin
has no ledger, so the rule cannot flag it. The rule is not added to the landed-parts agreement in `parts.py`: which
of the surplus sentences should go is the author's call, and listing all of them there would mark every part.

What was run: the three new tests failed on the previous commit (on the bad draft it said 待作者终审 with no
blocker); 8 new red-check mutants each turned their test red.

## Open for the author

- Q1 Should a covered candidate still get a probe, to pin the rule that catches it? Default: no, following
  EnvHarness's rule against non-challenging tasks. The test already lists checks with no probe.
- Q2 Batch size. Default: three, because the author's attention is the scarce part.
- Q3 The cross-reference check is on for every LaTeX workspace, needing no configuration. On the measured manuscript it
  would show its 7 hits in the first run after the toolkit is updated. Default: on, because all 7 are true and the
  check is cheap. Making it opt-in is one line in the catalogue. **Decided 2026-10-05 by the author: on by default.**
- Q4 The title-and-abstract check is on for every LaTeX workspace, like the cross-reference check. On the measured
  draft's current head it reports nothing. Default: on.
- Q5 The measured workspace builds its submission in an author-year style, so `target.citation_style: author-year`
  belongs in its configuration; the loop would then show the 2 hits above. Default: set it.
