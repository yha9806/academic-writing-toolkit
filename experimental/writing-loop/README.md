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
bin/loop health <workspace>          # what is known to be wrong: failed updates, lag, a tampered index, refused writes
bin/loop bench                       # event -> updated index, through the hook path, on a throwaway workspace
bin/loop lintel <workspace> --once   # write notch cards; refuses unless registered (see below)
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
- The `human/` guard matches the tool call statically. A shell command that builds the path at run time gets through, and so does anything made only of reading commands (`cat`, `grep`, …) with no redirection. It guards the agent's tool channel, not the file system.
- `loop bench` measures a small throwaway workspace. A real manuscript is slower: time `loop update` on it. The first update after the engine code changes is a cold rebuild.

## Optional notch display

`bin/loop lintel` writes cards for a separate notch host (lintel) as JSON activity files. It stays off until the producer has been registered with that host. Until then it refuses with a non-zero exit code and creates no directories.

## Tests

```
cd engine/tests && PYTHONPATH="..:." python3 -m unittest    # hermetic: throwaway repos, fake transcripts
python3 engine/tests/redcheck.py                             # every mutation must turn its named test red
```

Both run in the main suite as T139–T141 (T140 covers 61 mutations, including the hooks). Regression tests against a real manuscript exist but are kept outside this public repository. They use the same runner through `redcheck.run(mutations=..., extra_paths=...)`.
