# Writing loop: paper state ahead of coverage

Status: implemented (branch feat/paper-state; unit tests and red check pass locally; CI not run; the author has not reviewed it)

## Problem

The per-turn line and the overview reported coverage: whether each check has looked at the draft as it is now. On a
real manuscript every check was current while the paper still stated two results more strongly than its evidence
carried, waited on an analysis nobody had run, and had no scope sentence. The author's reading: the loop made it feel
as if nothing was wrong. Iterating is fine; not knowing where the paper stands is not.

Three causes:
1. Coverage answers a question about the checks, not about the paper, and nothing else was said every turn.
2. The checks look at what changed. A claim corrected in the results and left as it was in the abstract, the
   contributions and the conclusion is invisible to them.
3. The queue held only writing. A claim that needed an analysis was "fixed" by rewording, because nothing recorded
   that an analysis was missing.

## Goal

Every turn, before anything about the checks, the loop says: whether the paper's claims stand (a verdict that is
never green), the stage, what stands in the way, and the next items, including analyses and sources, not only
rewriting.

## Non-goals

- Judging a claim's strength automatically. The ledger records it; the loop reports and checks the ledger against the
  whole draft.
- Replacing the risk register or the revision ring. Risks are author decisions; the ring is where a round is. The
  paper state is whether the claims stand.
- A readiness score.

## Decisions

- A claims ledger in Markdown (config key `claims`), like the risk register: 主张 items (evidence, strength, allowed
  wording, optional `越界` / `必须出现` regexes, `缺`) and 待做 items (type 分析 / 出处 / 交付 / 写作 / 决定, the claims
  they change, a status; closing takes a date and evidence or a reason).
- Verdict 未就绪 while any claim is 弱 or 未立, any sentence of the whole draft matches a `越界` pattern, a `必须出现`
  pattern matches nothing, the ledger cannot be read, the sentence index is missing, or any 待做 item is open.
  Otherwise 待作者终审. No green state.
- The line leads with the paper state and is not cut; the coverage line follows. Without a ledger, the line says the
  loop does not know whether the claims stand.
- The overview's first 待办 cell is the paper; the panel rebuilds when the ledger changes.
- `loop state <workspace>` prints every claim, every sentence over the line, every item; exit 0 only at 待作者终审.

## Acceptance

- Unit tests for each rule (test_state.py, one test in test_overview.py); each rule's removal turns its test red
  (redcheck step `state`).
- The full writing-loop suite passes.
- On a real workspace, every sentence flagged `越界` is read by a person before the count is trusted; false
  positives are fixed in the ledger's patterns, and the precision is recorded.

## Known limits

- `越界` patterns catch the wordings someone wrote down. The same claim put another way gets past them.
- The state is only as honest as the ledger. A claim marked 强 that is not strong reads as strong.
- Python 3.8 compatibility was checked statically (syntax at feature level 3.8, no 3.9+ idioms in the new files);
  the tests have not run under 3.8.
