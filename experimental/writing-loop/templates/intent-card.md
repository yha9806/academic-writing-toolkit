# Intent card

Copy this file into the workspace and name it in `config.json` as `target.intent_card`. Kept under the workspace's
`human/` folder it is the author's own; anywhere else it is a draft, and the loop says so.

The engine reads three things from this file: whether it exists, its approval line, and its hash. It does not read the
sections below. They are for the author and for whoever revises the paper. What keeps a section from being dropped
when the card is revised is the risk register: see "Writing decisions go in the register" in the README.

Mark each part the author has approved with the uuid of that message. Mark each part the author has not approved
with ◌ (a default that anyone may overturn).

## 读者 · Reader

Who reads the paper, what they already know, and what they do not.

## 读者读完要带走的 · What the reader carries away

- **M1** …
- **M2** …

Two to four points. The readers skill measures whether readers carry these away.

## 不属于意图的 · Not part of the intent

Things a reader might take away that the author does not claim. A rewrite that adds one of these is what the scan
below looks for.

## 优势句 · Advantage sentence

The sentence that the abstract and the first paragraph of the introduction open with: what this paper gives its
reader that the nearest work does not. Give the uuid of the message in which the author approved it, or mark it ◌.

## 讲法顺序 · Narrative order

The order that the abstract and the introduction follow, with one line per step saying what goes there. For example:
problem → gap → approach → strongest result → significance. Give the uuid of the author's approval.

## 实验角色 · Experiment roles

Each experiment or section has one role:
- **core**: it holds up a point M;
- **credibility**: it makes a core result believable;
- **scope**: it says how far the results reach;
- **process history**: it tells how the work got here.

Content that serves no point leaves the main text. A pre-registered result is never deleted: it moves to the
supplement or the limitations, and it is reported as it came out.

| # | Experiment or section | Role | Serves | Where it goes | 现状 (checked against the draft on YYYY-MM-DD) |
|---|---|---|---|---|---|
| 1 | … | core | M1 | main text | 未核 |

现状 says where the item stands in the draft, as checked on the date in the header. 未核 means it was not checked
this time.

## 「稿子替你加的」扫描 · What the rewrite added

Done by hand before each round of rewrites goes to the author. It is not an automatic check.

- **What to scan**: every new or rewritten sentence in the sentence-pairs TSV. Once per paper, also scan the
  abstract, introduction and conclusion as they stand; this is the baseline. In the first round this was used on,
  the baseline found more to change than the new sentences did.
- **Types**: a concession; a hedge that carries no information; process narration; the paper arguing against
  itself; content with no role in the argument; framing changed after seeing the results; an undefined term.
- **Output**: `defensive-scan.tsv`, next to the pairs TSV, with one row for every new or rewritten sentence. Columns:
  - `id`, `sentence`, `type` (or `none`), `why`;
  - `fix`: what to do with the sentence, one of keep / cut / move / rewrite;
  - `judged_by`: always "machine draft";
  - `verdict`, `reason`: filled in by the author.
- **What `verdict` means**: whether the author takes the fix (`take` / `leave`), not whether the sentence stays. A
  sentence whose fix is "cut" and whose verdict is `take` is gone. Do not feed this table to
  `audit-sentence-changes.py --pairs`: there, `accepted` means the sentence stays, and for every row whose fix is not
  "keep" the two meanings are opposite.
- **Not counted**:
  - the one concrete statement of a weakness in the limitations section;
  - pre-registered results reported as they came out;
  - negations with a stated search scope ("the sources searched this time do not …").
- **Tally, once the author has given verdicts**: for each type, the rows flagged and how many fixes the author took.
  Keep the tally round by round. Whether this scan is worth automating can then be decided on more than one round.

## 验收 · Acceptance

Before a round of rewrites goes to the author, run each check and write the result on the page the author reviews,
including whether it found something that was then changed.

| # | What | How | Judged by |
|---|---|---|---|
| V1 | The paper follows the advantage sentence and the narrative order | Label each paragraph of the abstract and the introduction with its step. For each results subsection and for the conclusion, write which point M it serves. List what fits nowhere | Draft by the model, the author judges |
| V2 | The experiment roles have landed | "Where it goes" in the roles table matches the draft, and a search for the process-history passages finds nothing in the main text. Write the search command under the roles table | Mechanical |
| V3 | The conclusion does not argue against itself | Run the conclusion through the scan: no concession, and nowhere does the paper argue against itself | Draft by the model, the author judges |
