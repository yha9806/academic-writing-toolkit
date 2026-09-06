# Gate A — The workspace contract

- **Status:** item 1 IMPLEMENTED (2026-09-06), not yet verified against §7.
  Author-approved the same day: the ⚑ decision in §5 is **Option D**. Items
  2–5 are not started. Approval is not implementation and implementation is
  not verification; §7 states what verification means here, and no run of it
  has been recorded.
- **Amendment to §5, item 1 (2026-09-06).** As approved, Option D split the
  work five-and-one: five standalone scripts move into the skill that calls
  them, and `audit-citation-fidelity.mjs` becomes a registered profile tool
  because its dependence on `guards/dist` and `e1/graders.mjs` was thought to
  prevent it travelling. That premise is wrong, and was tested rather than
  assumed: Node resolves modules through the real path, so a workspace
  reaching that file through `.agents/skills` still finds the toolkit's own
  trees beneath it. All six moved; the tool was unnecessary surface and was
  not built. The mechanism that makes one path resolve on both surfaces is
  `awt init` mounting the catalogue under both names — `.agents/skills` and
  `.claude/skills`, one directory, the same dual-naming this scaffold already
  applies to AGENTS.md and CLAUDE.md.
- **Parent spec:** `2026-08-16-awt-dsh-app-v0.1-design.md` §6 (catalogue),
  §7 (Enforced vs Advisory), §11 (evidence classes)
- **Inputs:** the doc-vs-reality audit of `main` at `b48d0f6` (2026-09-06, ten
  product surfaces, seventy findings each independently re-run before it was
  kept), the audience decision below, a fresh-clone walk of the documented
  quickstart on 2026-09-06, and a survey of the published harness the same day.
- **Harness survey (2026-09-06):** npm now carries up to
  `@deepseek-ai/dsh@0.1.2-rc.1`. Nothing in it bears on this decision. The
  additions since our pinned `0.1.0-rc.6` are the `sdk`, `sdk-minimal` and
  `acp` profiles; `dsh plugin --profile <name> <pnpm args>`, the supported way
  to install out-of-tree plugins into a profile, was already present in rc.6.
  **The pin does not need to move for Gate A**, and moving it would re-open
  every attestation in `COMPAT.json` for no gain here.

## 1. Audience decision this spec serves

The author has decided what this repository is: **an open-source tool other
PhD students can use.** Not a personal tool that happens to be public, and not
yet a citable research artefact. Everything below follows from that and would
be disproportionate for the other two readings.

A reader of that kind is not a developer of this toolkit. They clone it once,
run the documented commands, and expect the daily loop to work on their own
machine — commonly Windows, commonly without a Python toolchain they control.

## 2. Problem

A workspace created by `awt init` cannot run most of what its own skills tell
the agent to do. The skills shell out to paths that exist only in the toolkit
checkout:

| Skill | Command it issues | Resolves in a workspace? |
| --- | --- | --- |
| `/verify-refs` | `python3 scripts/verify-refs.py` | no — its only command |
| `/audit` | `python3 scripts/audit-claim-positioning.py` | no |
| `/audit` | `python3 scripts/audit-prose-fingerprint.py` | no |
| `/audit` | `node scripts/audit-citation-fidelity.mjs` | no; also needs `guards/dist` |
| `/edit-contract` | `python3 scripts/{check,scaffold}-author-control.py` | no |
| `/export` | `python .claude/skills/export/scripts/convert_to_docx.py` | wrong path *and* wrong interpreter |
| `/review`, `/audit` | reference documents under `references/` | no (addressed in PR #40) |

The root cause is not a set of broken paths. It is that **the nine skills have
one text and two execution contexts.** Written for the Advisory surface, where
the agent's working directory is the toolkit checkout and `scripts/…` resolves,
they are also mounted in the Enforced surface, where the working directory is
the author's workspace and it does not. Nothing in the catalogue distinguishes
the two, so the same instruction is correct in one and unrunnable in the other.

Two consequences follow that a path fix alone would not remove. First, several
skills describe a world that no longer exists — `/read` and `/edit-contract`
tell the agent the guards have not shipped, while the shipped guards deny page
ranges and out-of-scope writes with typed codes; `/note` names a retired
`/progress`; `/export` prescribes `/style` and `/logic-review`, neither of
which is in the catalogue. Second, `/export` fails on a machine that has
`pandoc`, because the converter needs a Python backend that no manifest in this
repository declares and that CI installs only for itself.

## 3. Goals

1. Every command a skill issues resolves and runs in a workspace created by
   `awt init`, on macOS, Linux and Windows.
2. The daily loop of the parent spec §11 — read, note, integrate,
   edit-contract, review, audit, export — completes end to end from a fresh
   clone, including a real `.docx` at the end.
3. Skill text describes the surface it is running on. Where the two surfaces
   genuinely differ, the skill says so rather than asserting one of them.
4. A first-time reader's failures are typed and actionable: a missing
   dependency names itself and the command that installs it in a way that
   works on a PEP 668 system.

## 4. Non-goals

- **Efficacy.** This gate makes the tool run, not work better. The E1 pilot
  remains a negative result under one small local model and nothing here
  upgrades it. No claim about writing quality may cite this work.
- **E2.** The author's own chapter cycle (issue #35) is a separate gate and
  comes after this one. This spec does not satisfy it and must not be
  described as doing so.
- **The Advisory surface's convenience.** Skills used as plain Agent Skills in
  a toolkit checkout already work; nothing here is required to improve them.
- **Restoring any retired surface.** The Workbench, the packaged plugin and
  the App stay decommissioned; issue #39 owns that question.
- **A release.** Tagging, `CONTRIBUTING.md` and branch hygiene are Gate C.
  `CONTRIBUTING.md` ships alongside this spec only because the rules it records
  govern how this work itself is done.
- **New skills.** The catalogue stays at nine.

## 5. ⚑ Decision the author must take: how a workspace reaches the toolkit

An existing invariant makes this a real choice rather than a detail.
`guards/tests/scaffold.test.ts` asserts the scaffolded workspace contains
*exactly* the thesis-workspace manifest, and its comment records why: it was
written so that a toolkit-dev file leaking into the scaffold is a red test
rather than a review comment. The first option below deliberately relaxes that
invariant; the others preserve it at a higher cost. The author picks one.

### Option A — link the toolkit's script surface into the workspace

`awt init` adds `scripts/` and `guards/dist` links beside the `references/`
link PR #40 already introduces.

- *For:* smallest change; one shape already accepted for `references/`; skills
  need no rewriting; works on Windows through the junctions #40 adds.
- *Against:* directly relaxes the manifest invariant, and relaxes it in the
  direction it was written to prevent. The workspace acquires a development
  surface the author never asked for and may commit to their own thesis
  repository. Two of the three linked trees are executable code, so the blast
  radius of a bad link is larger than for reference prose.

### Option B — one workspace-safe entry point

Skills stop naming toolkit paths and call a single stable command
(`awt check <kind>`, resolved from the workspace back to the installed
toolkit). The entry point owns interpreter selection and dependency checks.

- *For:* preserves the manifest invariant; the workspace gains one command
  rather than three trees; interpreter and dependency problems get a single
  typed home instead of being restated in six skills; the same command works
  on both surfaces, which removes the two-context split at its source.
- *Against:* a new product surface to design, document and test; all six
  invocations must be rewritten; the workspace must be able to find the
  toolkit, which is a new piece of state.

### Option C — promote the deterministic checks to dsh tools

The checks become registered profile tools, as `read_pdf` and `export_docx`
already are, and the agent calls a tool rather than a shell command.

- *For:* consistent with the product's own architecture; path resolution stops
  existing as a problem; the guards can gate the checks; identical behaviour on
  Windows without junctions.
- *Against:* the largest change; the Advisory surface loses the checks unless
  the skills keep a shell fallback, which reintroduces the two-context split
  this spec exists to close; it also moves Advisory analysis into the Enforced
  layer, which the parent spec's vocabulary keeps deliberately separate.

### Option D — co-locate each script with the skill that calls it, and make a
tool of the one that cannot be moved

The first draft of this spec framed the choice as one mechanism for all six
commands. Measuring their dependencies shows that is the wrong unit.

| Script | Depends on the toolkit tree |
| --- | --- |
| `audit-claim-positioning.py` | nothing |
| `audit-prose-fingerprint.py` | nothing |
| `verify-refs.py` | nothing |
| `check-author-control.py` | nothing |
| `scaffold-author-control.py` | the `references/author-control` templates only |
| `audit-citation-fidelity.mjs` | `guards/dist` (three modules) and `e1/graders.mjs` |

Five of the six are standalone. They move into the `scripts/` directory of the
skill that calls them, and the skill names a path relative to itself. Both
surfaces then resolve, because both mount the same skill directory — one at
`.claude/skills/<skill>/`, the other at `.agents/skills/<skill>/`.

This is not a new idea to invent. `/export` already ships its converter at
`.claude/skills/export/scripts/convert_to_docx.py`, and
`profiles/awt-headless/awt-export.plugin.mjs:16` already resolves it by trying
both prefixes against the workspace root. The pattern is shipping and proven.

The sixth is different in kind: it reuses the guards' own citation extractor
and notes parser on purpose, so that the audit and the enforcement cannot drift
apart. It becomes a registered profile tool alongside `export_docx`, resolving
the guards from `awt-guards`, which `install-profile` already places in the
profile. On the Advisory surface it keeps working from the checkout as it does
today, because that is where its dependencies are.

- *For:* preserves the manifest invariant with no new links; introduces no new
  CLI surface, no new documentation, and no new "where is the toolkit" state;
  reuses two patterns already in the product; and the one script that becomes a
  tool is precisely the one whose dependencies the Enforced surface already
  installs. Five skills stop naming paths that only exist in a checkout without
  anything being wrapped.
- *Against:* moves files, so anyone with a bookmark to `scripts/…` follows a
  redirect; `scaffold-author-control.py` must take its templates with it; and
  the split has to be justified per script rather than stated once, which is a
  little more to explain in `CONTRIBUTING.md`.

**Recommendation: Option D.** It addresses the cause named in §2 — a skill that
names a path only one of its two contexts has — by giving each skill a path
both contexts have. It keeps the manifest invariant, adds no surface, and reuses
two mechanisms that already ship. Option B was the first draft's recommendation
and remains the best answer *if* the six commands must share one mechanism; the
dependency table above is the evidence that they need not. Option A is cheaper
today and more expensive every time a skill grows a command. Option C is right
for exactly one of the six and wrong for the other five, which is what Option D
says.

A caveat this spec should not hide: Option D leaves `/export`'s Python backend
problem untouched. That is work item 2, and it needs a home for a typed
dependency error whichever option is chosen.

## 6. Work items, once the decision is taken

1. **The chosen mechanism** from §5, with red-first tests.
2. **Export dependencies.** Declare them; make `awt verify` fail when the
   converter cannot run rather than reporting green; replace the converter's
   printed remedy with one that works under PEP 668. `make doctor` must stop
   reporting a healthy environment on a machine where `/export` cannot run.
3. **Skill text revision.** Remove statements that describe the pre-guard
   world, the retired `/progress`, and the absent `/style` and
   `/logic-review`; state the real `read_pdf` tool shape in `/read`; correct
   `/export`'s converter path and interpreter.
4. **The README ten-minute demo.** Its `npm --prefix guards run …` line
   resolves relative paths against `guards/`, so the demo dies on a correct
   checkout with an uncaught `ENOENT`.
5. **Edit-contract lifecycle.** Yesterday's contract silently scopes today's
   writes and nothing documents how to retire one; the loop works on day one
   and denies on day two against a scope the author is not working under.

Items 2–5 do not depend on the §5 decision and may proceed in parallel.

## 7. Acceptance

Not "the tests pass". This gate is accepted when, on a machine that has never
run this toolkit:

```
git clone … && cd academic-writing-toolkit
npm ci --prefix guards && npm run build --prefix guards
node scaffold/awt.mjs install-profile
node scaffold/awt.mjs init <workspace>
```

then, inside that workspace and with only a provider key exported, one pass of
read → note → integrate → edit-contract → review → audit → export completes,
every skill's own commands run, and the export produces a `.docx`. The run is
recorded with the platform it ran on, and it is repeated on Windows.

Evidence class: **E0** for the deterministic gates, and nothing more. A green
run of this acceptance is not E2; E2 requires the author's real chapter, not a
scripted pass.

## 8. Risks

- **PR #40 overlaps item 1.** It introduces the `references/` link, which is
  Option A's shape for one of the three trees. If the author picks B or C, that
  link becomes a special case; if A, it is the precedent. Sequencing #40 before
  implementation avoids resolving the same conflict twice.
- **Windows is on the critical path for this audience and is the least
  exercised platform here.** #40 carries the junction and hard-link work; the
  acceptance run must include it, not assume it.
- **Scope creep from the audit.** The audit produced seventy findings. This
  gate takes only what blocks the daily loop. The rest stay recorded and
  unclaimed rather than being folded in silently.
