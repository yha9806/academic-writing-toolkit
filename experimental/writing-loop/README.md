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
bin/loop doctor <workspace>          # every configured path resolves (not: the content is right)
bin/loop index <workspace>           # build index/ from git and transcripts
bin/loop rebuild <workspace> --check # byte-for-byte comparison with a fresh rebuild
bin/loop update <workspace>          # rebuild index/ and record the outcome in health.json (what the hooks call)
bin/loop health <workspace>          # what is known to be wrong: failed updates, lag, a tampered index, hook errors
bin/loop ack <workspace>             # the author has seen the refused writes and hook errors so far (records are kept)
bin/loop bench                       # event -> updated index, through the hook path, on a throwaway workspace
bin/loop lintel <workspace>          # resident notch producer: reads index/, syncs cards, keeps the heartbeat
```

Rebuilds reuse two caches under `cache/`: per-transition alignments (keyed by the sentences and the engine code) and a per-file record of which session files hold the branch. `rebuild --check` gives the same bytes with or without them, and an unreadable cache file is recomputed rather than trusted.

A workspace is any directory holding `config.json` plus `human/`, `model/`, `index/` and `cache/`. **Keep workspaces outside this repository.** They hold unpublished sentences and the author's own words.

## Hooks (Claude Code)

`hooks/loop_hook.py` is one script for four events; `hooks/settings.example.json` shows how to wire it. Workspaces it should act on are listed one per line in `~/.awt/loop-workspaces` (or `$AWT_LOOP_REGISTRY`).

- **UserPromptSubmit**: in a session on a registered manuscript (cwd under the configured prefix, on the configured branch), the prompt is appended verbatim to `human/comments.jsonl`, and Claude is asked to end manuscript replies with a short explanation block (`〔循环〕` … `〔/循环〕`: what it read the message as, which sentences it changed, on what basis). The block is parsed from the transcript into `index/explanations.json`, next to the verbatim message. It is what Claude says, not a record of what happened.
- **PreToolUse**: a model write into any registered workspace's `human/` is refused and recorded (the author's words are written by hooks or an interface, never by the model).
- **PostToolUse**, **Stop**: a write to the draft or the ledger, a git command, or the end of a turn starts `loop update` detached. Overlapping requests are merged.

Field names are the ones the runtime sends (read from the Claude Code binary, 2.1.252), not the documentation's. A payload that lacks the field its event needs is recorded in `health.json` as a hook error, so a renamed field shows up instead of silently doing nothing.

## What it does not do

- It reads committed versions only. Uncommitted edits in the working tree are not seen.
- Trigger inference is a heuristic. A change set whose rows point to more than one trigger, or mix a trigger with "not traceable", is marked *mixed* rather than resolved.
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

Both run in the main suite as T139–T141 (T140 covers 61 mutations, including the hooks). Regression tests against a real manuscript exist but are kept outside this public repository. They use the same runner through `redcheck.run(mutations=..., extra_paths=...)`.
