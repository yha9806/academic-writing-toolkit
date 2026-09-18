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
bin/loop lintel <workspace> --once   # write notch cards; refuses unless registered (see below)
```

A workspace is any directory holding `config.json` plus `human/`, `model/`, `index/` and `cache/`. **Keep workspaces outside this repository.** They hold unpublished sentences and the author's own words.

## What it does not do

- It reads committed versions only. Uncommitted edits in the working tree are not seen.
- Trigger inference is a heuristic. A change set whose rows point to more than one trigger, or mix a trigger with "not traceable", is marked *mixed* rather than resolved.
- The ledger check is string matching against saved source text. It shows that a quoted span exists in the source, not that the sentence represents the source faithfully.
- Messages and card text are currently in Chinese.
- There is no Windows launcher yet (`bin/loop` is a POSIX shell script).

## Optional notch display

`bin/loop lintel` writes cards for a separate notch host (lintel) as JSON activity files. It stays off until the producer has been registered with that host. Until then it refuses with a non-zero exit code and creates no directories.

## Tests

```
cd engine/tests && PYTHONPATH="..:." python3 -m unittest    # hermetic: throwaway repos, fake transcripts
python3 engine/tests/redcheck.py                             # every mutation must turn its named test red
```

Both run in the main suite as T139–T141. Regression tests against a real manuscript exist but are kept outside this public repository. They use the same runner through `redcheck.run(mutations=..., extra_paths=...)`.
