# Writing loop: the story before the sentences

Status: draft. S1 and S2 are implemented (T268, the engine's unit tests, the red check and the full test.sh run locally; brought onto main 2026-09-30 in one commit; the author has not reviewed them). S3 is implemented (StoryPageTest, the red check; 2026-09-30, extended 2026-10-07; its two decisions taken as recommended and open to reversal). S5 is next: on the manuscript this spec comes from, the author approved a five-step story page and asked that the toolkit be designed from it. S4, S6, S7 and S8 are proposals only.

## Problem

A journal manuscript (kept private) went through about a month of revision with this loop. Every check the loop runs
reads sentences or tokens: numbers against their artifacts, citations against sources, overreach patterns, prose rates
against a venue corpus, each changed sentence against the one it replaced, and a panel of model readers. Several
times the author, or an outside revision document, found a problem that the checks had passed. Nearly all of them
concerned how the paper is told rather than what any sentence says: what the first sentence does, whether the problem
comes before the method, how much a reader must hold in mind at once.

Three causes, from the retrospective:
1. **The checks measure sentences; the author judges the story.** No check read the order of the argument or the
   opening of a paragraph. A version with the research question deleted passed every check; the version that put the
   question back had many sentences flagged.
2. **Each critique added material where it arose, and nothing was consolidated.** The body grew by more than half
   in a few weeks, was cut back after the author said the reader was carrying too much, and grew again.
3. **The same agent translated the author's comments, wrote the rubric and scored against it.** A comment asking to
   open with the phenomenon became a design line asking for a phenomenon "with figures" in the first two sentences, and
   a rubric that counted a reader only if they could name a finding that had already happened, so a problem stated in
   plain words scored as a miss. The reader panel gave the figure-first version a full score, and the author
   rejected it on reading. The rubric had been validated against the agent's reading of the comment, not against the
   author.

The published writing guides read for this spec say the same things from the other side: settle an outline with one
informal sentence per planned paragraph before working on prose; in the abstract, do not give results before the reader
is ready for them; open each paragraph on its topic (sources in the intent-card template, "Story page").

## Goals

- G1: the story is written in plain words and agreed with the author before sentence work, and stays visible.
- G2: paragraphs whose first sentence leads with figures are pointed out across the whole text, not only the abstract.
- G3: body growth between versions the author approved is visible.
- G4: a reader-panel rubric the author has not approved is reported as the model's own reading.

## Non-goals

- No check says whether the story is good. The author does.
- Nothing rewrites prose.
- No readability score.

## Changes

### S1: the paragraph-openers check (implemented)

`scripts/audit-openers.py`, catalogued as `paragraph-openers` (段首), reads the prose view like the paragraph-logic
check. It lists paragraphs whose first sentence carries a number or a formula (inline math shows as MATH in the view)
or opens on a table, a figure or an equation. A year, a metric's name (Recall@10), a pointer (Section 3), a list
marker and a model's version (BLIP 2) are not figures. It reports findings, never a failure: a paragraph whose
content is data rightly opens with data, so the output is a list to read, with each chapter's first paragraph named
first. Exit 1 with findings, 0 without, 2 when there is nothing to read; registered in `check-fails-closed.py`.

### S2: the intent-card template (implemented)

- 讲法顺序 becomes 讲法页, the story page: per step, the plain words, the evidence (figures go here), what the reader
  can say, and where it lands in the paper; four questions to read a draft against it; how to build same-genre
  exemplars from the target venue with a fragment ledger that is checked against archived originals.
- The advantage sentence is no longer fixed as the abstract's first sentence; where it goes follows the story page.
- Acceptance gains V4: each flagged paragraph opener is marked keep or rewrite, and the author judges.

### S3 (implemented 2026-09-30): the loop reads the story page

Parse the story page's steps and their approval marks. The per-turn line says how many steps the author has approved.
Whether an unapproved page should also block 待作者终审 is the author's decision, so this change reports it and does not
change the verdict until that decision is made.

As built (`loop/state.py`, `story_page`): the page is the intent card's section headed 讲法页, 讲法顺序 or Story page;
its steps are the first run of numbered items (a numbered history kept below the page is not the page). A step is
approved when an author's message it names by uuid is in the workspace's transcripts, or, naming none, when the page's
own approval (a uuid above the first step) is; a step marked ◌ is not approved. The per-turn line says "讲法页 k/n 步认可";
a card without the section, or a section with no numbered steps, is a blocker (second decision below).

Decision, taken as recommended on 2026-09-30 and open to reversal: a step with no approval on record is a blocker, so
the verdict stays 未就绪 until the author approves it. Reversing it is one line in `judge`. On the manuscript this spec
comes from, the page has five steps, all approved; its verdict did not change.

Second decision, taken as recommended on 2026-10-07 and open to reversal: a card without a story page, or a page
with no numbered steps, is a blocker too ("意图卡里没有讲法页" / "讲法页没列出编号的步骤"). Said in the per-turn line
and not blocking, the missing page was never shown, because the loop repeats only blockers and verdict changes; an
abstract whose order no page could check reached its author with every reader point carried, and the author could not
follow it. A missing page is at least as open as an unapproved step. Reversing it is two branches in `judge`. A
workspace without an intent card is unaffected; one whose card has no page stays 未就绪 until a page is written.

### S4 (proposed): growth between approved versions

A config key names the commit the author last approved. Coverage shows words per section against it; growth above a
set share without a note in the register is a finding, with the question "main text or supplement?".

### S5 (proposed): rubric approval per point

`tally-readers.py` reads per-point marks (uuid or ◌) from the intent card and heads each point's result with who
approved it. Points without the author's approval are reported as the model's rubric; they cannot move a per-turn line
or a verdict. Rubric changes are shown to the author before a panel runs on them.

### S6 (proposed): exemplar kit and figures in the abstract

A generic version of the fragment verifier used for the exemplars, and a count of result figures in the abstract
against the venue corpus. Result figures versus set-up figures needs a person's reading, so the count would be labelled
as a pointer.

### S7 (proposed): pair splits and merges within one file

The changed-sentence check paired one sentence of the introduction, changed by a single word, with a new sentence of
the abstract, and reported the two as one split sentence that had grown longer. Each sentence had been checked on its
own. Splits and merges should be paired within one file and one section; similar sentences across files are one
removal and one addition, each checked on its own.

### S8 (proposed, 2026-10-07; Status: draft): sentence order against the story page

Problem. On one private abstract, most readers guessed at the same turn between two sentences. A connector added at
that turn did not make it followable; putting the sentences in the order of the approved story page's steps did. No
check compares the order of a front-matter text's sentences with the order of the page's steps.

Goal. For the abstract and the introduction, say where the order of sentences departs from the order of the story
page's steps: which sentence, which step it serves, and which earlier step it comes before.

Non-goals. No rewriting, no verdict, no blocker: the result is a pointer for the author, as the reader report is.
Not for sections other than the abstract and the introduction until the two are tried.

Decision still open. Which step a sentence serves needs a reading, not a keyword match: on the candidate pair below,
the order in which each step's words first appear does not separate the two versions. The proposal is to let the
reader panel label it: each reader writes, per sentence, the step number it serves (or none), and the tally takes
the label most readers give. A sentence whose label readers split on is reported as unplaced, not guessed.

Acceptance (to be written when the author picks it). On the candidate pair, two versions of that abstract, the one
the author could not follow and the one they could, the check names the turn in the first and none in the second.
One pair is a case, not a validation: the labels' agreement between readers is reported beside the result, and the
pair stays in the private workspace, not in this repository.

### Order after the author's approval

The author approved the story page on the manuscript that motivated this spec and asked for the toolkit to be built
from it. S3 comes first because nothing else can refer to an approved step until the loop can read one; S5 follows
because the reader panel's rubric should be the approved "the reader can say" lines rather than a rubric the model
writes for itself.

## Acceptance

- S1: T268 passes, and fails against five mutants of the script (no MATH, no Recall@ exclusion, no model-version
  exclusion, no "As shown in", no year exclusion); the empty-target case exits 2 (registry and T268); the engine's
  LaTeX coverage test runs the check through the prose view. On the private manuscript it names, among chapter-first
  paragraphs, exactly the ones the author rejected, and none in the version before them (evidence kept in the private
  workspace, not in this repository).
- S2: documentation only. What the template says the engine reads stays true.
- S3–S6: to be written when the author picks which to do.

## Evidence

In the private workspace, not in this repository: the retrospective (commit counts, words per section by day, the
title history), the check run on two versions of the manuscript, the archived writing guides with their fragment ledger
(every fragment re-extracted from the raw files and checked; an injected fake fragment and a tampered copy both fail).
