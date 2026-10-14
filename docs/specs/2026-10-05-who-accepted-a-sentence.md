# Who accepted a flagged sentence: the author, or the model that wrote it

Status: implemented locally (2026-10-05). The author approved borrowing A ("the judge and the judged are not changed
in the same edit; prompt, do not block"). Measured before building, that rule as written fires on most commits and
caught nothing. This spec is the narrower form the measurement points to, and the author has not read it. It is
reversible: dropping it is one revert.

What was run:
- The new test failed on the old code.
- The four red-check mutants (`whoaccepted`) each turned their test red.
- `make test-all` passed: 251 shell tests and 40 node tests.
- A read-only run on the measured manuscript's ledger counted 0 of 19 live acceptances as read by the author. A real
  author uuid was found in 0.8 s, and a made-up one was not.

Python 3.8 was checked by grammar only. CI has not run.

## Problem

The changed-sentence gate flags a rewritten sentence; a row in the acceptance ledger (key, reason, who decided, the
sentence) releases it. The loop then reports the run as clean, "已接受 N 句", whoever wrote the row.

On one real manuscript, measured read-only:

- Changing the draft and a judge file in the same commit is the norm, not a signal: 102 of 137 draft commits. On the
  toolkit itself, 181 of 204 commits that change check code also change its tests. Narrowed to the judging columns of
  the same ledger row, the hits were repairs (a number re-pointed to the artifact that holds it, a verdict handed back
  to the author); narrowed to tests removed alongside code, the 4 hits were whole features retired. None was a check
  being weakened.
- The place where the same hand writes a sentence and judges it is the acceptance ledger. Of 1,365 rows, about one in
  five rests on the author having read the wording (a read of the final PDF, a blind read, a review page accepted line
  by line). The rest were written by the model in the commit that wrote the sentence, under an earlier general
  approval ("go with the defaults"); most say so in their own words.
- The latest run on that manuscript: 53 changed, 19 flagged, 19 accepted, clean. All 19 rows say the sentences were
  written by the model and not read one by one by the author. The loop showed the same clean as a run the author had
  read.

Free text cannot settle it: a regex over the "who decided" column put about 80 rows under the author that cite an
approval given before the wording existed.

## Goal

A clean run that rests on acceptances says how many of them the author read.

## Non-goals

- Blocking. An acceptance releases a sentence exactly as before; the verdict and the base move as before.
- Prompting on co-changed files or co-changed ledger rows. Measured above: noise on both histories.
- Reading free text to guess who read what.
- Rewriting any workspace's ledger. Old rows count as the model's until someone marks them; a workspace that wants its
  history counted marks it itself.
- Checking that the author's message came after the wording existed. A later version may compare the message's time
  with the commit that introduced the sentence; this one only requires the message to be on record.

## Decisions

**D1 The mark.** In the "who decided" column, `作者读过：uuid <id>` (or `author-read: uuid <id>`), with the author's
message uuid, at least its first 8 hex digits, as the stale-check acceptance and the intent card already take it.

**D2 The test.** A row counts as the author's only if the mark is there and that message is a user message in this
workspace's transcripts (`targets._approval_in_transcripts`, the test the intent card and the stale acceptance use).
No transcripts configured, no mark, a uuid not on record: the model's. Unsure goes to the model.

**D3 What is shown.** The run summary becomes "已接受 N 句（作者读过 a 句）"; the run record keeps the keys the author
read under `accepted_by_author`. Nothing else in the loop reads the summary, so nothing else changes.

## Acceptance

- A fixture run with one accepted sentence: no mark → "作者读过 0 句"; the mark with a uuid on record → "作者读过 1 句";
  the mark with a uuid not on record → 0.
- The existing acceptance tests pass unchanged (verdict, base, `accepted`).
- A red-check mutant that skips the transcript lookup turns a test red; one that ignores the mark does too.

## Open for the author

- Q1 Should a run where the model accepted every flagged sentence still show as clean? Default: yes, as now; only the
  count is added.
- Q2 Mark the old rows that do rest on the author's reading (about 270 on the measured manuscript)? Default: no; they
  count only when their sentences are flagged again, which a clean base makes rare.
