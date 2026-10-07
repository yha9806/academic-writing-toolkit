# Writing loop (experimental)

**Status: experimental.** Not part of any release, not linked from the main README, and it may be removed if real use does not justify it. Nothing here changes the behaviour of the nine skills, `guards/`, or the `make` targets.

## What it is

A read-only engine that reconstructs, sentence by sentence, how a manuscript changed and why. It is meant to sit beside a conversation with a coding agent.

- **Stable sentence ids across versions.** Ids are inherited by alignment, not by position, so moved, split and merged sentences keep their history.
- **Change sets.** Each commit is compared sentence by sentence (edited, split, merged, added, removed).
- **Triggers.** For each changed sentence, the author message that caused it is recorded. There are three possible sources:
  - a `Loop-Trigger:` line in the commit message;
  - an inference from the words that changed, stored together with its evidence;
  - "not traceable", which is shown as such.
- **The author's messages, verbatim, from Claude Code session transcripts.** This includes messages typed while the agent was still working, which are stored as a different record type.
- **Per-sentence mechanical checks.** Every claim in an evidence ledger is matched against the saved source text.
- **A rebuildable index.** `rebuild --check` rebuilds `index/` from git and the transcripts and compares it byte for byte with what is on disk.
- **An optional notch display, off by default** (see below).

It is stdlib-only Python (3.9+). It never writes to the manuscript repository or to the transcripts.

## Commands

```
bin/loop init <workspace> --repo <manuscript repo> --ref <branch> --draft-glob <glob>
bin/loop doctor <workspace>          # every configured path resolves, and the hook registry lists the workspace (not: the content is right)
bin/loop index <workspace>           # build index/ from git and transcripts
bin/loop rebuild <workspace> --check # byte-for-byte comparison with a fresh rebuild
bin/loop update <workspace>          # rebuild index/ and record the outcome in health.json (what the hooks call)
bin/loop health <workspace>          # what is known to be wrong: failed updates, lag, a tampered index, hook errors
bin/loop ack <workspace>             # the author has seen the refused writes and hook errors so far (records are kept)
bin/loop bench                       # event -> updated index, through the hook path, on a throwaway workspace
bin/loop lintel <workspace>          # resident notch producer: reads index/, syncs cards, keeps the heartbeat
bin/loop state <workspace>           # whether the paper's claims stand (exit 0 only at 待作者终审)
bin/loop precheck <workspace>        # every script check on the uncommitted working tree, recording nothing (exit 1 if one would turn red)
```

Rebuilds reuse two caches under `cache/`: per-transition alignments (keyed by the sentences and the engine code) and a per-file record of which session files hold the branch. `rebuild --check` gives the same bytes with or without them, and an unreadable cache file is recomputed rather than trusted.

A workspace is any directory holding `config.json` plus `human/`, `model/`, `index/` and `cache/`. **Keep workspaces outside this repository.** They hold unpublished sentences and the author's own words.

## Hooks (Claude Code)

`hooks/loop_hook.py` is one script for five events; `hooks/settings.example.json` shows how to wire it. Workspaces it should act on are listed one per line in `~/.awt/loop-workspaces` (or `$AWT_LOOP_REGISTRY`).

A workspace that is not listed there gets nothing from the hooks: the author's words are not recorded, no update runs after an edit, and no session is told the paper's state. Nothing else would say so, since every configured path still resolves. So `loop doctor` fails on it and names the registry, and `loop state` and `loop coverage` say it in their first line (`hook_registry` in their JSON).

- **UserPromptSubmit**: in a session on a registered manuscript (cwd under the configured prefix, on the configured branch), the prompt is appended verbatim to `human/comments.jsonl`, and Claude is asked to end manuscript replies with a short explanation block (`〔循环〕` … `〔/循环〕`: what it read the message as, which sentences it changed, on what basis). The block is parsed from the transcript into `index/explanations.json`, next to the verbatim message. It is what Claude says, not a record of what happened.
- **A session named by id** (`"transcripts": {"sessions": [{"id": "<session id>", "note": "<why it is this paper's>"}]}`) is a manuscript session wherever it runs, for example one that edits the draft by absolute path from another checkout and branch. Its prompts are recorded and get the block, its draft writes (counted against the manuscript's checkout, not the one it runs in) and its stops start an update, and transcript reading, `loop doctor` (which fails on an id with no transcript file), approvals and the to-do ring count it too: one list, read through `config.session_ids`. A neighbour in the same directory is not taken in. `history_sessions` stays read-only history that only the hook reads.
- **PreToolUse**: a model write into any registered workspace's `human/` is refused and recorded (the author's words are written by hooks or an interface, never by the model).
- **PostToolUse**, **Stop**: a write to the draft or the ledger, a git command, or the end of a turn starts `loop update` detached. Overlapping requests are merged.
- **StopFailure**: fired instead of Stop when an API error ended the turn (its output is ignored). The update it starts records the turn as ended but unfinished, so the notch stops showing it as running and does not show a landing card. A Stop the rewrite gate blocks is recorded as `stop:blocked`, which does not end the turn.

Field names are the ones the runtime sends (read from the Claude Code binary, 2.1.252), not the documentation's. A payload that lacks the field its event needs is recorded in `health.json` as a hook error, so a renamed field shows up instead of silently doing nothing.

## Open gates and strategic risks

Every check above reads the text. None of them can tell whether the evidence is enough for the venue, or whether a
decision the whole paper depends on has been taken. Those live in a register that the workspace's `config.json`
names as `risks` (a path to a Markdown file). Each item is a level-two heading with four fields:

```
## 门 G0 First venue: go, reframe or kill
来源：planning document, section 3
消除它的证据：the three judgments and the author's decision
由哪个门决定：G0
状态：未决

## 风险 R1 Evidence smaller than its comparators
来源：mock review, strike 3
消除它的证据：the same audit on a second, independent source
由哪个门决定：G0
规模：我们 12 · 同类 40、95 · 单位 queries
状态：未决
```

- Every open item leads the per-turn line (`未决 N：…`), before any check result, and `coverage.pending(summary)`
  returns them as rows for the notch. They are not check statuses and are not counted as checks to run.
- An item is decided only by `状态：已决 <YYYY-MM-DD> <decision> — 作者 uuid <uuid>`, where the uuid is the author's
  message in this workspace's transcripts. A uuid that is not on record, or a message that is not the author's,
  decides nothing. A register kept under the workspace's `human/` folder is the author's own and needs no uuid.
- A `规模` line whose own number is below its comparators is said on every turn, decided or not: a decision does
  not change the numbers. With two or more comparators "below" means below their median, and the line says where
  ours stands (`我们 12：第 0 百分位 / 中位数 67.5（n=2）`, a mid-rank percentile); with one comparator it means below
  that one and the line says `我们 12 < 同类 40`, since a single paper has no percentile.
- The comparators can come from a venue ledger instead of being typed in:
  `规模：我们 3 · 台账 refs/venue.tsv · 列 models · 单位 models`. The ledger is a TSV, a CSV (`.csv`) or a JSON list
  of objects (`.json`), one row per paper; a relative path is read from the register's folder. Cells that are not a
  number (`未报告`, `n/a`) are skipped and counted on the terminal view. A ledger that cannot be read, has no such
  column or no number in it is shown as a problem, never taken for "no scale", and editing the ledger marks the
  coverage summary stale just as editing the register does.
- A missing field, an unreadable status, a register that cannot be read or holds no item: each is shown, never
  taken for "no risks". Editing the register marks the coverage summary stale.
- The parser reads only the five fields shown above. Any other line in an item (a `进展：` note, say) stays in the
  file for people to read, but it is not parsed and does not appear on the per-turn line.

### Writing decisions go in the register

The intent card (template: [`templates/intent-card.md`](templates/intent-card.md)) holds decisions about the writing:
the advantage sentence, the narrative order, the role of each experiment. The engine does not read those sections.
So a decision that lives only in the card can be dropped when the card is revised, and nothing will say so. Put each
one in the register as well:

- A writing decision gets an item whether the author has approved it or it is still pending, for example
  `## 风险 W1 Advantage sentence not settled`. Its 消除它的证据 names the section of the card and the check that shows
  the decision has landed (V1–V3 in the template). Its 由哪个门决定 names the page on which the author reviews the
  rewrite.
- Like any other item, it is decided only by the author's message uuid.
- Revising the card never removes a section the author approved. If one has to change, the reply to the author says
  which one and why.

## Paper state: whether the claims stand, not whether the checks ran

Coverage says whether every check has looked at the draft as it is now. That is not the same as the paper being in
order: a draft can be current everywhere and still say a result more strongly than its evidence carries, or wait on an
analysis nobody has run. When the per-turn line reported coverage alone, a paper in that condition read as "nothing
is wrong". So the line now starts with the paper's state, read from a claims ledger the workspace config names as
`claims` (template: [`templates/claims.md`](templates/claims.md)):

- **主张** items: each claim, where the evidence is, its strength (强 / 中 / 弱 / 未立 / 推论 / 范围), the strongest
  wording the evidence allows, optional regexes for wordings that go beyond it (`越界`) or must be present
  (`必须出现`; when the draft no longer has one that an earlier indexed version said, `loop state` names the last
  commit that said it, since the draft may have been reworded and the ledger not), the sentences that state it (`承载`) and qualifiers each of those sentences must keep (`限定词`),
  how many sentences at most may say something, such as a limitation restated across the paper (`至多：<regex> ‖
  <regex> @ 2`, optionally in named places; only the listed wordings are counted), and the work items it waits on
  (`缺`).
- **集合** items: the set a universal quantifier ranges over (the systems compared, say): its noun, the sentence that
  defines it, its size, and names outside it that the same noun might be read to cover. In the abstract (or the
  places `全称量词查：` names), every / all / each / none of / no + noun must either say its size where it stands
  ("all five systems") or range over a set whose defining sentence comes first. A sentence using the set's noun with
  a name outside the set is listed for a person to read. Phrases read and let stand go in `全称量词不查：`.
- **待做** items: work that changes a claim, typed 分析 / 出处 / 交付 / 写作 / 决定, so an analysis or a source to find
  sits in the same queue as rewriting. Closing one takes a date and the evidence (`已做 YYYY-MM-DD …`) or the reason
  (`不做 YYYY-MM-DD …`).
- `阶段：…` at the top names where the paper is (for example 主轴 → 分析 → 正文 → 讨论 → 引言摘要 → 终检), and only
  names it. A stage written as a paragraph (what was done, what is left) is cut in the per-turn line at its first full
  stop and said: the account belongs in the revision log, the open work in the conversation's list.

The verdict is 未就绪 while any claim is weak or unestablished, any sentence **of the whole draft** (not just what
changed) matches a `越界` pattern, a required wording is missing, a sentence carrying a claim drops one of its
qualifiers, a universal quantifier is not held to a set, the ledger cannot be read, or a work item is open.
Otherwise it is 待作者终审. There is no green: whether the paper can be submitted is the author's decision. The line
names the next open items in the ledger's order, and the overview's first 待办 cell shows the same verdict. Without
a ledger the line says the loop does not know whether the claims stand.

The line reads the same every turn, and a blocker that appears in it is easy to miss: on a real manuscript one stood
there from one commit on and was not acted on until the author asked why the verdict had changed. So a change is also
said once, on its own, at the next prompt of the manuscript's session: `写作循环 · <name>：上一条消息以来，论文状态有变化——`
followed by the verdict's move (`未就绪 → 待作者终审`), the new blockers (`新：…`) and the cleared ones (`已解：…`). The
hook says it itself rather than through wishing-willow's note, because its own output always reaches the model. What
was last said is kept in `cache/state-told.json`; a prompt of a session that reads the manuscript only as history
does not use the change up.

## Known failure: passing the checks instead of improving the paper

An agent revising a draft inside this loop sees which checks fail, and it can make them pass without making the paper
better. This is a known pattern and not peculiar to this tool. Pan et al. (2024, arXiv:2407.04549) had a language
model revise essays against a language-model evaluator and found the evaluator's ratings rising while quality as judged
by human preference stayed flat or fell. ImpossibleBench (Zhong et al., 2025, arXiv:2510.20270) gives the example of a coding agent
that deletes a failing test instead of fixing the bug.

The writing version of deleting the test is deleting the sentence. Removing a sentence lowers every per-thousand-words
rate, shortens the text under a word limit, and gives a reader panel less to complain about. Moves of this kind seen
while using the loop on a real manuscript:

- A reader-panel target ("the opening paragraph does not repeat the abstract") was met by deleting the paragraph's
  research question.
- A word limit was met by dropping a qualifier and the denominator of a reported count.
- A sentence was kept because readers recalled it, although it said more than the evidence supports.
- A check script was changed until it reported green, while the output it checks still had the fault.
- A panel round was reported as passing because its pre-set main question passed, while another measure had fallen
  two rounds in a row.

What the loop does about it:

- The paper state reads the whole draft, not only the sentences that changed, and it has no green state
  ([Paper state](#paper-state-whether-the-claims-stand-not-whether-the-checks-ran)).
- A removed sentence that carried a required wording, a number or a qualifier is flagged like a rewrite, so
  deleting is no longer the one move no check sees (#78). Reader panels get a blank reader that only copies the first
  paragraph, as the baseline a result has to beat (#78). The claims ledger can require a wording in named places and
  name the sentences that carry each claim (#80).
- Not built: keeping the evaluator out of the writer's context. Pan et al. report that the effect was weaker with
  GPT-3.5 when the author and the judge did not see the same context. Also not built: hiding thresholds from the writer
  and giving it only the question each check stands for.

None of this makes a paraphrase that weakens a claim visible to a regex. Whether the paper is better is still the
author's call.

## What it does not do

- It reads committed versions only. Uncommitted edits in the working tree are not seen.
- Trigger inference is a heuristic. A change set whose rows point to more than one trigger, or mix a trigger with "not traceable", is marked *mixed* rather than resolved.
- The paper state is only as good as the ledger. `越界` patterns are regexes the author or agent writes; a claim put
  another way gets past them. The state says what the ledger records; it does not judge a claim itself.
- Qualifiers are checked within the sentence 承载 finds; a qualifier stated in the sentence before does not count.
  Universal quantifiers are found by their words only (every / all / each / none of / no, 所有 / 全部 / 任何 / 每);
  "the encoders outperform" with no quantifier ranges over a set just as widely and is not seen.
- The ledger check is string matching against saved source text. It shows that a quoted span exists in the source, not that the sentence represents the source faithfully.
- Messages and card text are currently in Chinese.
- There is no Windows support yet: `bin/loop` is a POSIX shell script and health.json locking uses `fcntl`.
- The `human/` guard matches the tool call statically. A shell command that builds the path at run time gets through. Only the parts of a shell command that name a `human/` path are judged: such a part passes if it starts with a reading command (`cat`, `grep`, …) and redirects nothing into `human/`. It guards the agent's tool channel, not the file system.
- `loop bench` measures a small throwaway workspace. A real manuscript is slower: time `loop update` on it. The first update after the engine code changes is a cold rebuild.

## Optional notch display

`bin/loop lintel` writes cards for a separate notch host (lintel) as JSON activity files. It stays off until the producer has been registered with that host; until then it refuses with a non-zero exit code and creates no directories.

Once registered, the hooks start one resident `loop lintel` per workspace (a pid file prevents a second one). It reads the index that the hooks keep up to date and never rebuilds it, so it costs almost nothing while idle, and it rewrites unchanged cards often enough to keep lintel's heartbeat alive.

**One manuscript, one activity** (design research 2026-09-18, balance rule P1, decided by the author on 09-18). The activity's id is `loop`; the wings, the capsule, the popup and the expanded card say the one thing that matters now, in this order:

| state | right wing | how it reaches you |
|---|---|---|
| the engine failed | 跑挂了 | anomaly, red; `tool-broken` event |
| the latest change set has no traceable author message | 改动无出处 | Time Sensitive: `drift` event (registered with `attention`), the short card pops for six seconds |
| the latest change set traces to your message | the ≤6-character reason Claude wrote in its explanation block (`标签：`), else `改了 N 句`; the small number is the sentence count | Active: `changed` event, no popup |
| no change set yet | 还没有改动 | idle |

The popup is three lines (你说 / 改了 / 读成); the expanded card is your words, Claude's reading, and the rows two lines each; the panel lists every change set newest first, with the badge `△` on the ones that trace to nothing. Missing-evidence ledger entries and refused writes into `human/` are Passive: they never reach the wings, only the panel's note and its stats, and their events carry no `attention`. Seen means gone (`labelUntilSeen`, `pillUntilSeen`).

## Tests

```
cd engine/tests && PYTHONPATH="..:." python3 -m unittest    # hermetic: throwaway repos, fake transcripts
python3 engine/tests/redcheck.py                             # every mutation must turn its named test red
```

Both run in the main suite as T191–T193 (T192 runs every mutation listed in `redcheck.py`, including the hooks). Regression tests against a real manuscript exist but are kept outside this public repository. They use the same runner through `redcheck.run(mutations=..., extra_paths=...)`.
