<p align="center">
  <img src="docs/assets/readme/awt-readme-hero.svg" alt="Academic Writing Toolkit — write with agents, keep the argument yours" width="100%">
</p>

# Academic Writing Toolkit

[![CI](https://github.com/yha9806/academic-writing-toolkit/actions/workflows/test.yml/badge.svg)](https://github.com/yha9806/academic-writing-toolkit/actions/workflows/test.yml)
[![Latest release](https://img.shields.io/github/v/release/yha9806/academic-writing-toolkit?display_name=tag&sort=semver&include_prereleases)](https://github.com/yha9806/academic-writing-toolkit/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-15967D.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-compatible-6F88F7.svg)](https://agentskills.io)

Academic Writing Toolkit (AWT) is an open-source, local-first system for evidence-controlled academic work. It gives AI agents repeatable skills, inspectable files, and deterministic checks for reading, literature review, argument design, bounded revision, citation auditing, clean-room review, and release governance.

The core promise is simple: **agents may help operate the workflow; the author keeps control of claims, boundaries, approvals, and the exact artifact that ships.**

> **Latest: [v0.6.0-rc.1](https://github.com/yha9806/academic-writing-toolkit/releases/tag/v0.6.0-rc.1), a pre-release.**
> It is the first tag of the v0.1 rebuild: AWT as a
> [DeepSeek Harness (dsh)](https://github.com/deepseek-ai/deepseek-harness)
> distribution — a 9-skill catalogue plus deterministic guard plugins with
> typed denials, session-log-derived governance, and harness-event approvals.
> ("v0.1" there is the architecture generation, not the version number;
> `v0.1.0` was taken in May 2026, so the release line continues from v0.5.0.)
>
> It is a release candidate because of what has and has not been verified.
> Every enforcement claim is CI-proven (E0), and the daily loop has been run
> end to end against the acceptance criteria in
> [Gate A §7](docs/specs/2026-09-06-gate-a-workspace-contract.md) — **on macOS
> only**; the Windows repeat is open as
> [#56](https://github.com/yha9806/academic-writing-toolkit/issues/56). A
> [three-source local E1 pilot](e1/published/2026-09-05-local-qwen/README.md)
> is recorded and negative: neither arm produced lint-conforming notes, so it
> does not demonstrate improved writing efficacy. Author-dogfood (E2) and
> external evidence (E3) remain pending. Evidence classes are stated per §11
> of the [v0.1 design](docs/specs/2026-08-16-awt-dsh-app-v0.1-design.md).
>
> **[v0.5.0](https://github.com/yha9806/academic-writing-toolkit/releases/tag/v0.5.0)
> is the last release of the previous product** — the Workbench wheel, Codex
> plugin package and ChatGPT App, all decommissioned since. It is still the
> place to get those, and nothing on `main` replaces them.

AWT is not a hosted writing service and does not operate a manuscript-storage
backend. Its deterministic tools stay local. Provider routes are configured by
`apiKeyEnv` credential references only — no secret ever enters a profile file,
and a missing credential fails typed instead of falling through to ambient
keys. Online reference metadata checks run only when you explicitly add
`--online`.

## Why AWT exists

Long academic projects fail in ways that fluent text alone cannot solve: a citation is remembered but not verified; a claim becomes broader across revisions; a reviewer concern is answered without an evidence anchor; or the released file is not the file that passed review.

AWT turns those risks into visible objects:

| Risk | AWT control |
|---|---|
| Source and citation drift | independent reading notes, source-status labels, BibTeX checks |
| Argument drift | gap → contribution → claim → evidence maps |
| AI revision drift | project-intent contracts, global thesis audits, spine cards, edit contracts, human gates |
| Repeated failed edits | three-attempt escalation with stop-and-diagnose semantics |
| Review contamination | declared source manifests, source-bounded findings, and explicit reviewer-context status |
| Release mismatch | exact ref + artifact + evidence state + gate + owner |

## How the controlled workflow works

<p align="center">
  <img src="docs/assets/readme/awt-control-loop.svg" alt="Five stages from source evidence to exact release" width="100%">
</p>

1. **Ground** — read source material, record notes, and distinguish verified support from leads or unknowns.
2. **Structure** — connect the research gap to contributions, claims, evidence, limitations, and reviewer risks.
3. **Contract** — state what an edit may change, what it must preserve, and how acceptance will be checked.
4. **Adjudicate** — compare the result with the approved boundary; unresolved or repeated failure stops the workflow.
5. **Release** — bind approval to an exact Git ref and artifact rather than to a conversational impression.

Human decisions are first-class data throughout the loop. A draft generated by an agent is never silently promoted to author-confirmed evidence.

## Choose the right product surface

| Surface | Best for | Enforcement |
|---|---|---|
| **AWT dsh app** | the full enforced thesis workflow: `awt init` workspace, guards with typed denials, page budgets, edit contracts, harness-event approvals | Enforced (guards + CI red-first tests) |
| **Agent skills** | the same 9-skill catalogue in Claude Code, Codex, or any Agent-Skills host, without the enforcement layer | Advisory (skill text only) |

The two modes are the design's whole vocabulary — Enforced or Advisory, no
third state. Surfaces retired with v0.5.0 (Workbench wheel, Codex plugin
package, ChatGPT App) are listed under
[Release and distribution](#release-and-distribution).
See [Choose the right product surface](docs/use-cases/choose-product-surface.md) for the boundary.

## Run the AWT dsh app

The dsh app is the enforced surface: profile boot itself truth-tests your
workspace, and every daily-loop constraint is a typed guard denial or an
explicit author approval. It needs Node 22+, `pdftotext` (poppler), a Python
conversion backend for `/export` (see
`.claude/skills/export/scripts/requirements.txt`; `awt verify` asks the
converter rather than guessing), and one
provider key at run time.

```bash
make setup                                   # configs + the /export conversion backend
npm ci --prefix guards && npm run build --prefix guards
npm ci --prefix e2e                          # `awt verify` runs the live denial table from here
node scaffold/awt.mjs init ~/thesis          # clean workspace + skill links
node scaffold/awt.mjs install-profile        # profiles into ~/.dsh + the pinned harness
node scaffold/awt.mjs verify ~/thesis        # six stages, keyless, scratch-only
export DEEPSEEK_API_KEY=...                  # or ANTHROPIC_API_KEY
node scaffold/awt.mjs run ~/thesis "task"    # one headless task

# or the same enforcement behind dsh's web UI, then open the printed URL:
node scaffold/awt.mjs web ~/thesis           # 127.0.0.1:3180 by default
```

`install-profile` fetches the pinned harness into `harness/` once
as well as writing the two profiles. This fetch and the initial npm/Python
dependency installation need the network. `run` and
`web` launch that harness, refuse a target that is not a workspace, and
refuse a launcher whose version is not the one `COMPAT.json` attests.
Anything after `--` is forwarded to the harness untouched, so a launcher
overlay works: `... run ~/thesis "task" -- --patch model.yml`. Your provider
key stays in your environment; no AWT command reads or stores one.

On Windows PowerShell, install native Python and Node.js first, then use the
native entrypoint below. It needs neither Make nor Git Bash, and creates
junctions without Developer Mode or administrator privileges:

```powershell
node scripts/setup.mjs
npm.cmd ci --prefix guards
npm.cmd run build --prefix guards
npm.cmd ci --prefix e2e
$awtWorkspace = Join-Path $HOME "thesis"
node scaffold/awt.mjs init "$awtWorkspace"
node scaffold/awt.mjs install-profile
node scaffold/awt.mjs verify "$awtWorkspace"
$env:DEEPSEEK_API_KEY = "..."
node scaffold/awt.mjs run "$awtWorkspace" "task"
# Or: node scaffold/awt.mjs web "$awtWorkspace"
```

`node scripts/setup.mjs doctor` checks the links, generated configs and actual
export backend; `node scripts/setup.mjs repair` repairs links/configs while
preserving replaced skill folders in `.awt-skill-backups/`. The same commands
work on macOS/Linux, and the existing Make/Bash entrypoints use this implementation.
Setup uses `.venv/Scripts/python.exe` on Windows and `.venv/bin/python` elsewhere.
`AWT_PYTHON`, when set, must point to an already prepared interpreter; unset it
to let setup create the project's private environment. `DSH_HOME` defaults to
the OS user home plus `.dsh` on every platform.

`node scaffold/awt.mjs verify ~/thesis` runs the six-stage verification
ladder (build, notes-lint smoke, composition proof, scripted-denial evidence
table, credential probe, export-backend check) entirely on scratch profiles — no key, no real
thesis data. See [profiles/README.md](profiles/README.md) and
[guards/README.md](guards/README.md) for enforcement semantics and what each
guard deliberately does not do.

## Use the skills in Codex

The canonical skill tree is exposed at `.agents/skills/` (the same files
Claude Code reads from `.claude/skills/` and dsh discovers per workspace) —
clone the repo, run `node scripts/setup.mjs`, and point Codex at it, or let
`awt init` link the skills into your thesis workspace. On Windows, setup keeps
Git's flattened link files intact and adds ignored `awt-local-*` directory
junctions to the same canonical skills.

To use the nine skills across your local Codex projects, install them in
user scope from a source checkout (Python 3.9+, Node.js ^22.12 or >=24):

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git
cd academic-writing-toolkit
npm ci --prefix guards
python scripts/install-codex-skills.py --install-deps
```

Use `python3` if that is your Python command. This copies self-contained
skills to `~/.agents/skills`, builds their audit helpers, creates a private
Python environment, and verifies the installed files. `--install-deps`
downloads the declared Python dependencies on first use; no model key is
needed. Repeat the last two commands after `git pull --ff-only` to update.
Existing skills from another installer, or locally edited skills, require
an explicit `--replace-existing`; their complete folders are backed up
before replacement. Use `--dest` to update an existing legacy Codex skills
directory. See [global installation, verification and recovery](docs/setup-codex-cli.md).

These remain **Advisory** skills. The former packaged Codex plugin (`plugins/`)
was decommissioned with the v0.1 rebuild; it remains installable from the
immutable [v0.5.0 tag](https://github.com/yha9806/academic-writing-toolkit/releases/tag/v0.5.0).

## Use the full repository from source

Use this route when you want the complete skill sources, examples, validators,
and project templates, or when you plan to contribute to AWT. Most authors
should start with the dsh app quickstart above.

Use `git clone`, not GitHub's **Download ZIP**. AWT uses symlinks under `.agents/skills/` so compatible local agents discover the same canonical skills.

The primary surface is an agent-native local agent skill workflow: the agent operates explicit files and validators inside the project you opened.

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-writing-project
cd my-writing-project
make setup
make doctor
```

Open the folder in your agent runtime and ask:

> Show me the available academic-writing skills, explain which files each one reads or writes, and recommend the smallest safe workflow for my task.

Local discovery paths:

| Runtime | Discovery path | Setup guide |
|---|---|---|
| Claude Code | `.claude/skills/` | [Claude Code](docs/setup-claude-code.md) |
| Codex | `.agents/skills/` | [Codex CLI](docs/setup-codex-cli.md) |
| Gemini CLI | `.agents/skills/` | [Gemini CLI](docs/setup-gemini-cli.md) |
| Cursor | `.cursor/rules/` baseline | [Cursor](docs/setup-cursor.md) |

## Run the 10-minute demo

The demo uses fictional public-safe sources and the same validators real
projects use. It needs the network once, to install the guards' dependencies;
everything after that runs against local fixtures.

```bash
python3 .claude/skills/verify-refs/scripts/verify-refs.py \
  --bib examples/demo-project/references.bib --json

npm --prefix guards install
npm --prefix guards run lint:notes -- examples/demo-project/literature/reading_notes/smith2024_NOTES.md
```

A valid run reports no blocking issues. The earlier governance-packet demos
and the lost-in-conversation comparison fixture were retired with their
skills; they remain inspectable under [`archive/skills/`](archive/skills/)
and [`examples/`](examples/) but are no longer presented as evaluations.

## 9 composable skills

The catalogue was triaged from 20 skills to 9 plus 3 reference documents on
2026-08-16 after an adversarial efficacy review (every skill had to beat the
unaided frontier model to stay). See
[`docs/specs/2026-08-16-awt-dsh-app-v0.1-design.md`](docs/specs/2026-08-16-awt-dsh-app-v0.1-design.md)
for the per-skill verdicts; retired skills live under [`archive/skills/`](archive/skills/).

| Lane | Skills | What the lane produces |
|---|---|---|
| **Read and ground** | `/read`, `/note`, `/map` | page-anchored notes with an evidence-status firewall, coverage matrix, progress dashboard |
| **Write without losing control** | `/integrate`, `/edit-contract` | approved integration plans, spine cards, bounded edit scopes, 3-strike escalation |
| **Review and ship** | `/review`, `/audit`, `/verify-refs`, `/export` | anchored review findings, consistency reports, BibTeX checks, Word/ZIP exports |

The [`/review` instructions](.claude/skills/review/SKILL.md) distinguish external
review of another author's submitted work from own-work review of the user's
draft. Own-work clean-room review calls for a fresh-context subagent given only
the manuscript and explicitly listed evidence files. If no subagent is
available, the output must be labelled as not clean-room.

Reference documents (loaded on demand, no standing prompt cost):
[`references/argument-checklist.md`](references/argument-checklist.md),
[`references/evidence-vocabulary.md`](references/evidence-vocabulary.md),
[`references/reframe-method.md`](references/reframe-method.md).

Detailed, goal-oriented documentation lives in:

- [Skill guides](docs/skills/README.md)
- [Use-case guides](docs/use-cases/README.md)
- [Write a literature review](docs/use-cases/write-literature-review.md)
- [Audit thesis citations](docs/use-cases/audit-thesis-citations.md)
- [Verify references before submission](docs/use-cases/verify-references-before-submission.md)
- [Prepare a release-governance packet](docs/use-cases/prepare-release-governance-packet.md)

## What the checks guarantee — and what they do not

AWT's deterministic helpers verify structural facts that software can check reliably:

- required files, columns, identifiers, links, and allowed status values
- source-note citation shape and in-text citation consistency
- malformed or duplicate BibTeX records
- claim/evidence and review-packet structure; packet validation does not establish reviewer-context isolation
- plugin sync, public-content boundaries, local-path leakage, and packaging integrity

They do **not** prove that a scientific claim is true, that evidence is sufficient for a venue, that a paper will be accepted, or that an AI-generated revision expresses the author's intent. Those remain human scholarly judgments.

Safe fixers are deliberately narrow. They may normalise conservative citation punctuation or replace known US spellings with British forms; they do not invent references, rewrite arguments, or mark unresolved evidence as verified.

## Deterministic quality gates

```bash
make setup              # once per clone: configs, export backend, doctor
npm --prefix guards install   # once per clone: guards/node_modules is not committed

make doctor             # read-only environment and project health
make test               # regression suite

npm --prefix guards test  # notes-contract lint + catalogue truth tests

python3 scripts/audit-citations.py --base-dir . --style harvard --json
python3 scripts/audit-british-english.py --base-dir . --json
python3 scripts/audit-logic.py --base-dir . --json
python3 .claude/skills/audit/scripts/audit-prose-fingerprint.py --target chapters --baseline literature --exclude 'ourname*'
python3 .claude/skills/audit/scripts/audit-claim-positioning.py --base-dir . --json
node .claude/skills/audit/scripts/audit-citation-fidelity.mjs --base-dir . --json   # needs guards built once
python3 scripts/audit-public-content.py --base-dir .
```

Reference verification is offline by default:

```bash
python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib references.bib --json
python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib references.bib --json --online
python3 .claude/skills/verify-refs/scripts/verify-refs.py --bib references.bib --json --online --metadata-dir path/to/metadata-fixtures
```

`--exclude` drops baseline files by glob. Point it at the authors' own
papers: a baseline that contains them is partly the thing being measured, and
in practice it is often their own prior work that sets the extreme a target is
then judged against.

Two definitions in that audit are deliberate and worth knowing before the
numbers are read. A sentence may not begin with `(`, because in a PDF-derived
baseline that rule splits every inline author-year citation into a sentence,
and it does so in proportion to how much author-year citation each paper
happens to use. And `sentence_length_lag1` only correlates spans that were
genuinely adjacent: filtering first and correlating afterwards joins the two
sentences on either side of anything dropped, which is enough to move a
manuscript from inside the published range to outside it.

The explicit `--online` mode can query Crossref, Semantic Scholar, and arXiv. CI uses local fixtures so the release gate stays deterministic.

## Project structure

```text
my-writing-project/
├── .claude/skills/          canonical 9-skill catalogue (single source)
├── .agents/skills/          1:1 links — Codex, dsh, and other hosts read here
├── guards/                  dsh guard plugins: typed denials, projections, ask-gate
├── profiles/                canonical awt-headless dsh profile template
├── scaffold/                awt init / verify / install-profile
├── e1/                      paired-session evidence instrument (§11)
├── harness/                 the pinned dsh installation `awt run`/`awt web` launch
├── e2e/                     live headless denial table + credential probe
├── validators/              harness-neutral Python validators
├── references/              on-demand reference documents
├── archive/skills/          retired skill bundles (history; validators still tested)
├── chapters/                manuscript chapters (workspace demo)
├── literature/
│   └── reading_notes/       one structured notes file per source
├── final_output/            generated Word and ZIP outputs
├── scripts/                 deterministic validators and maintenance tools
├── COMPAT.json              dated harness-compatibility baseline
├── CLAUDE.md                canonical project configuration
├── AGENTS.md                generated agent configuration
└── GEMINI.md                generated Gemini configuration
```

Edit `CLAUDE.md` for project-specific directories, page limits, British English policy, and citation style, then run `make sync`. Do not edit the generated `AGENTS.md` or `GEMINI.md` blocks by hand.

## Release and distribution

- [v0.6.0-rc.1](https://github.com/yha9806/academic-writing-toolkit/releases/tag/v0.6.0-rc.1)
  — pre-release, the first tag of the dsh-distribution architecture; verified
  against Gate A §7 on macOS and not yet on Windows (#56)
- [v0.5.0 stable release](https://github.com/yha9806/academic-writing-toolkit/releases/tag/v0.5.0)
  — the last release carrying the ChatGPT App, its privacy/terms documents,
  the Cloud Run/Render deployments, and the local workbench wheel; those
  surfaces are decommissioned on main (v0.1 design §13)
- [README visual source in Figma](https://www.figma.com/design/HhaFm0uorv5oS7MsezWDN5)

Every release should identify one exact Git ref, the packaged artifact and hash, its evidence state, the gate that approved it, and the owner of any remaining human decision.

This repository currently provides open-source, local software. It does not
define a paid subscription, hosted processing service, support SLA, refund
policy, or billing relationship. Those require a separate commercial offer and
customer-facing terms before payment is accepted.

## Development

```bash
make sync          # regenerate AGENTS.md and GEMINI.md from CLAUDE.md
make repair        # apply narrow, idempotent local repairs
make test
```

The canonical skill source is `.claude/skills/`. Read
[CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request: it carries
the evidence classes every claim here is stated in, the rule that installation
and first-run changes are verified on a machine that has never run this
toolkit, and the branch and review conventions. Each of those rules names the
incident that produced it.

## License

MIT. See [LICENSE](LICENSE).
