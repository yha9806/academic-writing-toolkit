# Related work: placed early, each closest work told apart, novelty laid out in a table

Status: draft (2026-10-05; the author asked for it; recommended answers to Q1–Q4 below are defaults the author can
overturn; nothing implemented)

## Problem

The author's request (2026-10-05): related work goes near the front; it says in detail how this paper differs from
each earlier one; and a table lays out the paper's novelty point by point, with columns for the earlier paper, this
paper, and the difference (what is new and why it matters).

What AWT has today reads positioning one sentence at a time:

- `audit-claim-positioning.py`: a field's keyword with no source, a bare novelty claim, a method with no citation, a
  dangling entry.
- `audit-claim-ledger.py`: a sentence about a cited work bound to a verbatim snippet of the archived original; a
  negative claim ("X did not do Y") recorded against an abstract only is a finding
  (`negative-claim-without-fulltext`), and so is a negative, scope or numeric claim no author has read.
- The method ledger (`2026-09-29-method-ledger.md`): a sentence about what this paper did, bound to code, a result
  file or a preregistered section.
- The reader panel asks each reader what existing work the paper most resembles (`closest_prior_work`).

Nothing reads positioning as a whole:

1. Where related work sits. No check reports it, and the per-target layer of the overhaul spec (§10) does not list it.
2. Whether each closest work gets an explicit difference. The overhaul spec's reference layer (§9, "coordinates": the
   few lines of literature the target reader will compare the paper against, each with what they established and
   where this work attaches) was designed and never built.
3. Whether the novelty is stated point by point, in one place a reviewer can check against the literature.

A reviewer reads positioning first, and a positioning failure is the one that cannot be repaired in a rebuttal
(global rule 10: positioning before style).

## Goals

- G1 The loop reports where related work sits, against the target's default, and says nothing when it matches.
- G2 Every closest work the author names (the coordinates) has, in the related-work prose, a sentence citing it that
  says how this paper differs.
- G3 The manuscript carries a novelty table: one row per novelty point, columns earlier work / this paper /
  difference / value. Every cell is bound to evidence by a ledger that already exists.
- G4 The reader panel's `closest_prior_work` answers are compared with the table's earlier-work column, so the author
  sees whether the positioning landed.

## Non-goals

- The agent does not decide whether a neighbour threatens the novelty (overhaul spec §9: a person judges that).
- The agent does not write the table's content on its own. It drafts from the author's approved story page and the
  ledgers; the author approves rows as with any candidate sentence.
- No pinned block of any manuscript is touched. A manuscript whose related work is pinned gets the report only.
- No new judgement of prose style. The table may lower contrast-construction density (the "Unlike X, we…" sentences
  move into the table), but that is measured by the existing prose checks, not targeted.

## Design

### P1 The positioning file

One file per workspace, `positioning.tsv`, next to the claims ledger. Two kinds of rows:

- `coord`: a closest work: bib key, one-line "what they established", one-line "where this paper attaches".
- `row`: a novelty point: id, earlier-work bib keys (one to three), this-paper pointer (a section label, a result key,
  or a method-ledger row), difference, value.

The file is the source; the table in the manuscript is generated from it (or checked against it when the author
writes the table by hand). The story page comes first: rows are drafted in plain language, approved, then turned
into English cells (feedback: story page before sentences).

### P2 The check (`audit-related-work.py`, deterministic)

- `rw-position`: the related-work section's ordinal against the target's default (Q1). Reported once, as a
  prompt, not a failure.
- `coord-without-difference`: a `coord` key that no related-work paragraph cites, or whose citing paragraphs contain
  no sentence that also refers to this paper ("we", "our", "this paper", "this work"). A proxy; the report says so.
- `table-row-unbound`, per cell:
  - earlier-work cell: the sentence must have a claim-ledger row; a negative cell ("does not", "no", "only") needs a
    full-text source (the ledger's existing `negative-claim-without-fulltext`);
  - this-paper cell: must resolve to a section label, a result key, or a method-ledger row;
  - value cell: must name a claim in the claims ledger, or the report lists it as unbound.
- `table-drift`: the manuscript's table differs from `positioning.tsv`.
- `novelty-outside-table`: a novelty claim (the positioning audit's existing detector) in the abstract, introduction
  or conclusion whose point has no table row.

Before it is trusted, the check is run on a planted bad manuscript and must go red on each kind (global rule 10:
a red check first).

### P3 The loop

`positioning.tsv` registered in the workspace config (`positioning`). The coverage view lists the four findings
under 定位, and an open `row` with an unbound cell is a 待做 item, so it reaches the conversation list through the
hookup of `2026-10-04` when that is switched on.

### P4 The reader panel

The tally puts each reader's `closest_prior_work` beside the table's earlier-work keys: named / not named / named
something the table does not have. The last is the useful one: a work the reader thinks of that the author did not.

## Questions for the author (recommended answer first)

- Q1 Where related work goes. **Per target, default right after the introduction for journals and for IR/IS and
  humanities venues; the report only prompts.** Some ML conferences put it before the conclusion; forcing one place
  would fight the target layer.
- Q2 Table rows. **One row per novelty point, earlier-work column lists one to three closest works.** One row per
  earlier paper repeats our side and hides which point each work threatens.
- Q3 Where the table goes. **At the end of related work, referenced from the introduction's contribution list.**
  At the start it reads as a claim before the evidence; in the introduction it costs the opening page.
- Q4 Prose and table together. **The table carries the point-by-point difference; the prose groups the lines of
  work and keeps one difference sentence per closest work.** Writing every difference twice is the accretion the
  author flagged on 2026-09-27.

## Acceptance

- P2: each finding kind goes red on a planted manuscript and green on its fixed version; synthetic fixtures only
  (public repository).
- P1–P3: one real workspace runs it read-only and the author reads the report; that is the first time it counts as
  verified.
- P4: the comparison is shown for one existing panel run, without rerunning readers.

## Risks

- A table cell is a claim. Without the ledgers it would be the least checked text in the paper; with them it is the
  most checked. P2 refuses unbound cells for that reason.
- "Difference" sentences found by pronoun matching are a proxy (P2 says so); a paragraph can say "we" and still not
  tell the works apart. The author's reading stays the judge.
- Space: a table of four to six rows is about a third of a page.
- Whether `audit-claim-ledger.py` reads sentences inside LaTeX table cells is not yet checked; the plan's first step
  is to find out.
