# Retire the dsh distribution; keep the skills, the audits and the workspace scaffold

- **Status:** implemented (merged as #71, `f7e7cc9`, 2026-09-21, with every
  acceptance criterion below green at merge). The direction (retire, do not
  freeze) was decided by the author on 2026-09-20 after the evidence below was
  put to him; this text itself has not been reviewed by him. Not `verified`:
  nobody has yet used the toolkit from `main` without the retired line.
- **Scope:** the product's shape. No skill text changes meaning; no audit
  changes behaviour (criterion 1 below is byte equality on a real manuscript).

## Problem

Since 2026-08-16 the repository has described itself as a DeepSeek Harness
(dsh) distribution: an enforced surface (`guards/` plugin with typed denials,
`profiles/`, `scaffold/awt.mjs verify|install-profile|run|web`, the pinned
`harness/`, the `e2e/` denial table, the `e1/` evidence instrument,
`COMPAT.json`, a weekly re-attestation workflow) beside an advisory surface
(the eight skills in any Agent-Skills host).

What the enforced surface has been used for, on the author's machine, as of
2026-09-20: two dsh sessions on 2026-09-06 between 00:16 and 00:18, which were
the Gate A macOS acceptance run. Nothing since. The daily executor runs a
different profile. The README's own evidence ledger says the same in other
words: author dogfood (E2) never run, the E1 pilot negative, the Windows
repeat (#56) open since the first rc.

Meanwhile the need the enforced surface existed for, stopping an agent from
crossing a line rather than advising it not to, is served since 2026-09-19 by
a guard hook in the host the author actually writes in. It is exercised every
day. The dsh guards are a second implementation of the same need in a host he
does not use, and they cost three CI steps, a weekly cron, 160 tests and about
120 files of maintenance.

## Goals

1. `main` describes what the toolkit is: eight skills, the audits under
   `scripts/` and `.claude/skills/audit/`, the workspace scaffold, the writing
   loop (on its branch). Nothing on `main` claims an enforcement layer.
2. The last state of the dsh distribution stays reachable: tag
   `v0.6.0-rc.2` (`ce7b9ba`) carries all of it, with its evidence records.
3. No live behaviour changes. The three pieces of code the live skills borrowed
   from the retired line move into the skills that use them, unchanged.

## Non-goals

- Deciding whether an enforcement layer should exist in Claude Code. It does
  (`~/.agent-rules/hooks/guard/`, outside this repository) and this spec does
  not touch it.
- Rewriting any skill. `/note`'s lint command changes path, not behaviour.
- Removing `archive/skills/` or the retired-bundle tests; #70 made those
  opt-in and that is where they stay.
- The Codex packaged plugin and ChatGPT App: retired with v0.5.0 already.

## Dependency map (read from disk on 2026-09-20, the reason this is a spec)

The retired line was not a set of directories. Live code reached into it:

| Live consumer | Borrowed from the retired line | Moves to |
|---|---|---|
| `.claude/skills/audit/scripts/audit-citation-fidelity.mjs` | `guards/dist/decisions.js` (`extractCitations`), `guards/dist/projections.js` (`parseNotesSource`) | `.claude/skills/audit/scripts/citations.mjs` |
| same | `guards/dist/notes-lint.js` (`lintNotes`, `hasErrors`) | `.claude/skills/note/scripts/notes-lint.mjs` |
| same | `e1/graders.mjs` (`normalizeForMatch`, `extractQuotedSpans`, `gradeQuoteFidelity`, `pagesFromLabeledText`) | `.claude/skills/audit/scripts/quote-fidelity.mjs` |
| same | `profiles/awt-headless/pdf-pages.mjs` (`labelPdfPages`) | `.claude/skills/audit/scripts/pdf-pages.mjs` |
| `/note` SKILL.md step 7 | `npm --prefix guards run lint:notes` | `node .claude/skills/note/scripts/notes-lint.mjs` |
| `scripts/install-codex-skills.py` | built `guards/dist` and bundled it beside the installed audit | nothing to build; the modules ship inside the skills |
| `docs/setup-codex-cli.md`, README | `scaffold/awt.mjs init` to create a thesis workspace | stays; `init` is host-neutral and is the only subcommand kept |
| four `guards/tests/*.test.ts` about the catalogue itself (descriptions, skill-text, skill-commands, the `init` half of scaffold) | ran under the guards package | `scripts/test-catalogue.mjs`, `scripts/test-scaffold.mjs` (plain `node --test`, no build) |
| `guards/tests/{notes-lint,notes-lint-cli,citation-fidelity}.test.ts` and the extractor case in `decisions.test.ts` | same | `scripts/test-notes-lint.mjs`, `scripts/test-citation-fidelity.mjs` |
| CI `test` job, T169 | built guards before `make test` | no build step |

Everything else under `guards/`, `e2e/`, `e1/`, `profiles/`, `harness/`,
`validators/`, `COMPAT.json`, `.github/workflows/reattest.yml`,
`docs/e2-dogfood-runbook.md` and `docs/use-cases/choose-product-surface.md`
has no live consumer and is removed from `main`.

## Decision

Retire, with the tag as the record. Not freeze: a frozen layer that CI does
not run is a layer whose README claims rot silently, and the README's first
paragraph is about that layer.

## Acceptance criteria

1. `audit-citation-fidelity.mjs --json` on the author's thesis workspace
   (14 chapters, 53 notes files) produces the same JSON before and after,
   byte for byte apart from nothing. Same for `notes-lint` over all 53 files.
2. Every ported test passes, and the count of ported tests equals the count of
   the tests they replace (40: 4 + 5 + 5 + 4 catalogue and scaffold, 6 + 3 lint, 11 fidelity, 2 extractor and parser).
3. `scripts/check-fails-closed.py` is green with the notes lint registered as
   a check and the three library modules registered as not-checks.
4. `make test-all`, the native-setup test on three platforms, the Codex
   installer tests and `make doctor` are green with no `npm` step anywhere in
   CI.
5. A test (T190) reads the README's project-structure block and asserts every
   path it names exists on disk; run before the README is edited it is red on
   the seven removed paths.
6. No file outside `docs/specs/`, `docs/research/` and `docs/product/` names
   `guards/`, `e2e/`, `e1/`, `profiles/`, `harness/`, `validators/`,
   `COMPAT.json`, or an `awt.mjs` subcommand other than `init`, except the
   incident narratives in `CONTRIBUTING.md`, which are dated history of why
   a rule exists and keep their original wording, and the dated provenance
   line at the top of each moved module, which says where its code came from.

## What the README says afterwards

That the toolkit is the eight skills plus the audits, run in the author's own
agent host; that enforcement is the host's business; that the dsh distribution
ran from v0.6.0-rc.1 to v0.6.0-rc.2 and is retired with its evidence state
(E0 green, E1 negative, E2 never run) stated as it was, at the tag.
