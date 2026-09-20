# Writing control overhaul: author state, reader state, and a thin floor

- **Status:** draft (2026-09-19). Nothing here is approved, implemented or
  verified. It is published as a draft so that the design lives in this
  repository rather than only in a private companion repository.
- **Scope of this document:** design only. The pilot evidence behind it was
  gathered on an unpublished manuscript and stays private; section 12 reports
  it only as method results.
- **Relation to existing designs:** see section 13. In short, this document
  revives parts of the retired project-intent contract, keeps the writing loop
  under `experimental/writing-loop/` as the capture layer, and adds no new
  resident ledgers.

## 1. Problem

Three failures an author meets when an agent helps write or revise a paper:

1. **Statements about cited work say more than the source.** The quoted
   snippet exists in the archived original, so a snippet check passes, but the
   sentence around it still overreaches: a scope is widened, a qualifier is
   dropped, a limitation becomes a finding.
2. **Prose that is locally fluent and globally off.** Sentences are revised
   one at a time; each patch moves the difficulty somewhere else, and nothing
   checks what the whole text now asks the reader to remember.
3. **Punctuation and density.** Semicolons, stacked modifiers and long
   insertions raise the reading load without anyone having decided that the
   load is worth it.

Behind all three sits one pattern. Checks that an agent can close alone
(tests, red checks, hashes, counts, schema validation) are done thoroughly.
Checks that need the author to read real material stay pending. The toolkit's
own history shows it: its end-to-end author trial (#35) has never run, while
its unit suites are green.

## 2. Two states and a one-way gate

| | Author state (the record) | Reader state (the argument) |
|---|---|---|
| Holds | sources read, notes, experiments and failures, superseded findings, every decision | who the reader is, what they should take away, where the advantage lies, what the conclusion should leave behind |
| Rule | complete, chronological, honest | only what serves the stated intent, in the reader's order |
| Written by | the agent may write it | the agent drafts; the author decides |

The gate runs one way: every sentence of the reader text serves an intent the
author stated. Evidence enters only as support for a claim. Process history
does not enter directly.

## 3. Lines at every scale

| Line | What it is | Who provides it |
|---|---|---|
| What you want the reader to take away | the author's intent, in the author's words | author |
| What the reader took | what a simulated reader actually carried away, expected next, re-read | reader panel (section 6) |
| What the draft added | present in the draft but not in the intent: concessions, hedges, process narration, experiments with no argumentative role, undefined terms | derived by comparing the first two lines |
| What the draft dropped | present in the record but not in the draft: qualifiers, scope limits, caveats the record itself states | derived mechanically from the record (section 7, rule 1) |

There are no rules about particular words or sentences. Problems show up as
gaps between the lines, the author sees them and responds, and a revision is
judged by whether the gap narrowed, not by whether a rule was broken.

## 4. Scales and order

| Scale | Question put to the reader |
|---|---|
| Whole text | What will you remember? What is the best reason to accept it? What does it most resemble? |
| Section, paragraph | What do you now believe? What do you expect next? |
| Sentence | Which sentences did you have to re-read? |
| Word | Which words did you have to guess? |

Resolve the highest scale that shows a gap first. Do not polish sentences
while the whole-text gap is open. Readers always read with the preceding text.

## 5. Division of labour

- **Author:** who the reader is, the intent, the advantage, trade-offs, final
  acceptance, and every judgement about meaning.
- **Machine:** play several readers repeatedly; keep the record; propose
  alternative wordings and framings; generate comparison views from artifacts;
  label every judgement as the machine's; say where it is unsure.
- **Interaction:** comments first. The author reacts to gaps; the machine
  revises; the loop records the reaction.

## 6. Simulated readers

- **Channel:** a sub-agent of the host agent. The toolkit does not call a model
  API of its own.
- **Constrained amnesia:** a sub-agent can see project memory. Told to ignore
  it, it reported none, but that is an instruction the reader follows, not
  isolation. Each reading ends with the reader's own report of any outside
  knowledge it used.
- **Panels, not a single reader:** vary model and persona. Leniency differs a
  great deal between models, so compare versions within the same
  model-and-persona cell, never across cells.
- **Calibration against the author, before use:** in the pilot, the
  sentence-level signal (understood on first pass or not) agreed with the
  author on most sentences; the word-level signal ("which words did you
  guess") did not, and is used only as description.
- **Citations must be visible to readers in author-year form.** Stripping
  them to a placeholder removes exactly the signal a real reviewer uses to
  place a paper.

## 7. The thin floor (the only hard rules)

1. **Facts in the reader text do not exceed the record.** Each statement about
   a source maps to a verbatim snippet in an archived original (URL, retrieval
   time, sha256), checked by a script that is red-checked first. A search that
   found nothing supports only "the sources retrieved here do not do X", never
   "nobody has done X". Negative statements need the full text.
2. **The author's intent and reactions are written only by the author.** An
   approval that the agent types into a file it can edit is a record, not a
   gate; this toolkit has already demonstrated that an agent can self-approve a
   full packet that then passes strict validation.
3. **Machine readings are labelled as the machine's.**
4. **A check that examined zero objects is an error**, not a pass.

## 8. Method principles: validate the construct before the machine

1. Every check states what it measures and is compared against the author's
   (or a real reader's) judgement on real material before it is used; until
   then it is a hint.
2. The author's judgement is the primary instrument. Collect it through small,
   frequent questions (first-pass or not, yes or no, read against an exemplar),
   not one large gate that never runs.
3. Statements the agent makes about artifacts (what changed, how many, which
   version) are generated from the artifacts, and shown beside the agent's own
   summary.
4. Reference frames (exemplars, baselines, reader personas, word lists,
   thresholds) are approved by the author, with the reason for each choice.
   Frames the agent picked alone are drafts.
5. Qualitative questions get qualitative methods first: read the originals,
   compare sentence roles, trace where wording comes from. Numbers conclude
   only after they have been validated.
6. While validation is pending, do not build: run the smallest pilot the author
   can judge.

**What the author checks must not be chosen by the agent.** An agent that asks
the author to confirm three points is asking about the points it already
noticed. Comparison views are generated from the artifacts: for each number or
key term in a new text, the record's sentences that contain it, placed side by
side with the new sentence. The view has to fit the author's reading budget
(about one screen per paragraph), and the rule that selects what goes into it
is fixed and published, not chosen per case.

## 9. The reference layer

References are not only a truth check. They decide what a reader takes a
paper to be.

- **Roles:** anchor for positioning, evidence for a fact, origin of a method,
  counter-example, data source.
- **Coordinates:** the few lines of literature the target reader will compare
  the paper against, each with "what they established / where this work
  attaches". They start from the manuscript's own related work and existing
  claim ledger; the agent only proposes additions, and the author approves.
- **Ledger scope:** only sentences that assert something about a cited work's
  content ("X found / did not do / proposed"). Citations that merely credit a
  model, dataset or statistical method are not ledger rows. This keeps the
  author's spot-check small.
- **Reader-side measure:** the reader's "what does this most resemble" answer
  can show whether the positioning landed, but only after the author has said,
  in one sentence, where they want reviewers to place the paper.
- **Machine limits:** retrieving originals (never with personal data in
  request headers or parameters), mechanical snippet checks and bib-to-keyword
  reconciliation belong to the machine. Judging whether a sentence overreaches,
  or whether a neighbour threatens novelty, does not: in the pilot, a
  meaning-drift checker caught one of three planted changes, and missed exactly
  the scope and qualifier changes an agent had made while drafting.

## 10. Targets: journals, conferences, calls

The same record is written differently for different targets: an information
science journal, an NLP conference with a technical or an audit leaning, a
humanities venue, or a funding call. One system can serve them only if it is
clear what is invariant and what is not.

| Invariant (one per manuscript) | Per target |
|---|---|
| the record: facts, numbers, qualifiers, archived sources | official texts: author guidelines, reviewer form, assessment criteria (archived, dated) |
| the thin floor | exemplars from that target, approved by the author |
| the line mechanism and the comparison views | reader personas written from that target's reviewer form |
| | coordinates, intent, advantage sentence, format limits |

Style measures are always relative to the target's own exemplars. Mixing
exemplars from the venue with exemplars from the paper's intellectual lineage
answers neither question. Real reviews previously received are the best
material for calibrating a target's simulated reviewer; they are restricted
and never copied into a public tree.

## 11. Maintenance: no resident tables

This toolkit retired three designs built on resident ledgers: an evidence
packet whose checker validated form but never truth, a many-column argument
ledger that no project maintained, and a seven-table thesis-control set rated
net-negative because its gates were self-serviceable (see
`references/evidence-vocabulary.md`, `references/argument-checklist.md`, and
`docs/specs/2026-08-16-awt-dsh-app-v0.1-design.md`). This design keeps only two
kinds of resident object.

| Resident | Why it does not rot |
|---|---|
| **Snapshots**: archived originals with retrieval time and hash; the manuscript's git history | a snapshot needs no upkeep; it only ages, visibly |
| **The author's words**: captured by the writing loop from session transcripts into a log that agents cannot write | produced by the author, not re-typed by an agent |

- **Everything else is a report:** intent-card drafts, comparison views,
  status, gap lists, reader-panel results. Reports are regenerated when needed,
  carry a timestamp, and are discarded; a report can cite an approval only by
  the log id of the author's words.
- **A target profile** is a list of snapshot paths plus the author's own words
  about that target, not a directory to maintain.
- **Intent** follows the versioned amendment model of
  `docs/product/project-intent-contract-design.md`: moving a paper to a new
  venue is an amendment. The genuinely new case is one record serving two
  targets at once, such as a paper and a grant proposal.
- **Parallel sessions stay consistent by reading the same snapshots and the
  same author log**, not by updating shared state. This bullet first said the
  only shared writes are the log and git commits. Two incidents on 2026-09-19
  and 09-20 showed the list is longer, and that nothing here noticed either:
  a session committing in a manuscript checkout swept in the edits another
  session had left uncommitted in the same working tree (23:50); a session
  merging a toolkit branch to main, pushing and deleting the remote branch
  left the other session, in its own worktree, holding a push plan for a
  branch that no longer existed (17:55). Both were caught by hand. So the
  shared writes are the log, git commits, **the working tree of any shared
  checkout, and the remote's branch list**. The rule that follows: one
  worktree per session; before staging, committing or planning a push, run
  `scripts/session-scan.py`, which reads the remote as `ls-remote` reports it
  rather than as the tracking refs remember it, tells commits made in this
  worktree from commits made elsewhere, flags a staged file older than the
  session, and exits 2 when it cannot see a remote.
- **Registration is per manuscript, not per session:** wherever the author
  discusses a manuscript, their words must reach that manuscript's log. In the
  pilot, a session that made most of the author-facing decisions was not
  registered, and the log captured none of them.
- **Manuscript repositories that mirror a shared editor stay clean.** Process
  material (reader outputs, grill notes) lives with the private workspace, not
  in a branch that will be merged back into what co-authors see.

## 12. Evidence so far (method results only)

All evidence class E0 or E1 in this toolkit's terms; none is an author's own
end-to-end run (E2).

- **Reader panel, reading load:** on one abstract rewrite, the share of words
  in sentences rated "had to re-read or still unclear" fell in every
  model-and-persona cell, under a rule committed before any reader ran. The
  rewrite also said less; the measure does not separate "clearer" from
  "shorter".
- **Memory points:** adding one take-away to an abstract displaced another in
  the readers' three-item recall. The panel makes the trade-off visible; the
  author sets the priority.
- **Meaning-drift checker:** caught 1 of 3 planted changes; the two it missed
  were the kinds an agent actually made (a dropped expectation qualifier, a
  widened scope). Its "no change" verdicts are not evidence.
- **Mechanical comparison view:** a compact version reached about one screen
  but caught 2 of 5 known issues, and was tuned on those known issues; it has
  not been tested on unseen material.
- **Repeated failure of "find before building":** three times in one day the
  pilot designed something the manuscript or this repository already had (a
  sentence-level claim ledger, the manuscript's own positioning, the
  project-intent contract).

## 13. Relation to existing designs

| Existing | Here |
|---|---|
| `docs/product/lost-in-conversation-writing-control-design.md` | same problem statement; this document replaces the resident objects with snapshots, the author log and regenerated reports |
| `docs/product/project-intent-contract-design.md` (retired with thesis-control) | intent and versioned amendments revived as reports plus the author log, not as agent-editable CSV |
| `docs/specs/2026-09-06-gate-a-workspace-contract.md` | unchanged; the Gate A workspace and the writing-loop workspace remain different objects |
| `experimental/writing-loop/` | the capture layer for the author log; needs per-manuscript registration and a `target` reference; the unused `genre` field would be replaced |

## 14. Open questions

- Per-manuscript registration of the author log: mechanism and its tests.
- The comparison view's selection rule, tested on material it was not tuned on.
- Where a one-sentence author statement about each target lives, so that the
  reader-side positioning measure can be calibrated.
- Whether one record serving two simultaneous targets needs anything beyond
  two regenerated intent reports.
