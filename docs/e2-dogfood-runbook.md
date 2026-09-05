# E2 Dogfood Runbook — one real chapter cycle in the dsh app

E2 is the v0.1 acceptance gate (design §11): **one real thesis chapter
cycle, executed by the author, in the dsh app, with the session log as the
evidence artifact.** No agent may run it on the author's behalf — an
agent-driven "dogfood" would be the exact self-evaluation the evidence
classes forbid. The empty `chapters/` directory is the falsifier this
product has to answer.

## One-time setup (~5 minutes)

```bash
# from the toolkit checkout
cd guards && npm install && npm run build && cd ..
cd e2e && npm ci && cd ..

node scaffold/awt.mjs init ~/thesis            # or your chosen workspace path
node scaffold/awt.mjs verify ~/thesis          # 5/5 stages, keyless, scratch-only
node scaffold/awt.mjs install-profile          # profile into ~/.dsh
```

Requirements: Node 22+, `pdftotext` (poppler), and one provider key
exported per session — `DEEPSEEK_API_KEY` (cost route, default model) or
`ANTHROPIC_API_KEY` (prose route). Keys live in your shell environment
only; profile files carry `apiKeyEnv` references, never values.

## The cycle (§11: read → note → integrate → edit-contract → review → audit → export)

Run every step from inside the workspace so the guards see it:

```bash
cd ~/thesis
export DEEPSEEK_API_KEY=...
npx --yes @deepseek-ai/dsh@0.1.0-rc.6 --profile awt-headless "<task>"
```

1. **read** — put the chapter's key source PDF under `literature/`; task:
   read a bounded page range with `read_pdf` (≤15 pages per call, ≤90 per
   session — the guards deny beyond that with typed codes).
2. **note** — produce `literature/reading_notes/<source>_NOTES.md`
   following the template. A chapter write that cites a source without a
   lint-conforming notes file will be denied (`NOTES_MISSING`) — that is
   the product working, not a bug.
3. **integrate / edit-contract** — write the edit contract into
   `contracts/` (through the app, so the revision fold sees it), then draft
   the chapter section within its `May change:` scope.
4. **review / audit** — run the review and audit skills over the draft.
   Three typed-denial attempts under one contract put further writes behind
   your explicit approval (the harness records the decision immutably).
5. **export** — produce the chapter output via the export skill.

## What counts as the evidence artifact

The persisted session logs under `~/.dsh/sessions/` for the cycle's
sessions. Keep them; they are the E2 claim. Useful checks afterwards:

- the log contains real `read_pdf` calls and their page ranges;
- every cited source in the drafted text has a conforming notes file;
- any `approval/asked`/`approval/decided` pairs are your actual decisions.

## Honest failure is a result

If you abandon the flow because the enforcement gets in the way (not
because of defects), that is the §12 reframe signal — the enforcement
layer is over-weighted and the design says so out loud. Either outcome of
E2 is evidence; only not running it is not.
