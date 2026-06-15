# academic-writing-toolkit

agent-native, local-first workflows for evidence-controlled literature review, thesis writing, citation auditing, reference verification, and release governance.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-Standard-blue.svg)](https://agentskills.io)

Academic Writing Toolkit is a public toolkit for researchers who want their local AI agent to work through academic writing tasks with repeatable files, checks, and evidence controls. Install it into a writing project, open that project in Codex, Claude Code, Gemini CLI, Cursor, or another compatible agent host, and use the skills as a structured research workflow.

This is not a SaaS product and it does not host your thesis. Your chapters, PDFs, reading notes, evidence registers, release packets, and exports stay in your clone. Optional reference metadata checks use external APIs only when you explicitly run them with `--online`.

## Product Surfaces

Local agent skills are the full workflow. Use them when an agent can read and write the project files in your clone: chapters, reading notes, evidence registers, release packets, and export outputs.

The Codex plugin packages those same local skills for Codex plugin installation. It is a distribution surface, not a separate workflow.

The ChatGPT App MCP server is narrower. It provides pasted-text checks and template generation through temporary files only; it does not read or write a local thesis project, run the full skill pipeline, or persist user submissions.

## 10-minute demo

Inspect the runnable demo project:

```bash
python3 scripts/verify-refs.py --bib examples/demo-project/references.bib --json
python3 .claude/skills/evidence-review/scripts/check_review_package.py examples/demo-project --strict
python3 .claude/skills/release-governance/scripts/check_release_packet.py examples/demo-project --json
```

Then open [`examples/demo-project/`](examples/demo-project/) in your agent host and ask it to explain the local workflow.

## Common use cases

- [Write a literature review](docs/use-cases/write-literature-review.md)
- [Audit thesis citations](docs/use-cases/audit-thesis-citations.md)
- [Verify references before submission](docs/use-cases/verify-references-before-submission.md)
- [Prepare a release-governance packet](docs/use-cases/prepare-release-governance-packet.md)
- [Choose the right product surface](docs/use-cases/choose-product-surface.md)

## Workflow

```
/read -> /note -> /map -> /evidence-review -> /integrate -> /audit -> /release-governance -> /style -> /logic-review -> /export
             |                                      |
             v                                      v
        /verify                               /verify-refs
             |
             v
        /progress

/human-eval-handoff-repair supports evaluation-package QC and annotation repair workflows.
```

## Quick Start

Use `git clone`, not GitHub's "Download ZIP". This repository uses symlinks under `.agents/skills/` so Codex, Gemini, and other local agent hosts can discover the same skills as Claude Code.

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-writing-project
cd my-writing-project
make setup
make doctor
```

Then open the folder in a local agent runtime and ask what skills are available. You should see the public academic writing skills listed below.

The intended use is the same as local Superpowers-style skills: install the toolkit into a project folder, let the agent discover the skills from local files, and drive the workflow from natural language or slash commands.

## Agent Runtime Support

| Runtime | Local discovery path |
|---------|----------------------|
| Claude Code | `.claude/skills/` |
| Codex | `.agents/skills/` |
| Gemini CLI | `.agents/skills/` |
| Cursor | `.cursor/rules/` baseline rules |

Setup guides live in [`docs/setup-claude-code.md`](docs/setup-claude-code.md), [`docs/setup-codex-cli.md`](docs/setup-codex-cli.md), [`docs/setup-gemini-cli.md`](docs/setup-gemini-cli.md), and [`docs/setup-cursor.md`](docs/setup-cursor.md).

## Skills

| Skill | Purpose |
|-------|---------|
| `/read` | Read academic PDFs page by page with structured output |
| `/note` | Record reading notes in the shared notes format |
| `/verify` | Fact-check factual claims during reading |
| `/map` | Map sources to chapters and coverage gaps |
| `/evidence-review` | Build evidence-controlled gap maps, claim registers, citation plans, and overclaim audits |
| `/integrate` | Propose and apply approved note-to-chapter integrations |
| `/audit` | Check numbers, terminology, cross-references, and citations |
| `/release-governance` | Prepare release, rebuttal, artifact, and claim packets with ref-artifact-gate controls |
| `/style` | Check and safely fix British English spellings |
| `/logic-review` | Review paragraph flow, transitions, and argument continuity |
| `/verify-refs` | Validate BibTeX records offline or with explicit metadata checks |
| `/human-eval-handoff-repair` | Validate, repair, and map human-evaluation handoff packages and filled annotation CSVs |
| `/progress` | Show reading, writing, and coverage progress |
| `/export` | Convert Markdown outputs to `.docx` and ZIP packages |

Detailed guides live in [`docs/skills/`](docs/skills/).

The local agent skill guides are organized by command name; goal-oriented guides live in [`docs/use-cases/`](docs/use-cases/).

## Quality Checks

Agent-facing skills call deterministic scripts so checks are repeatable in CI and easy to run manually:

```bash
python3 scripts/audit-citations.py --base-dir . --style harvard --json
python3 scripts/audit-citations.py --base-dir . --style harvard --fix-safe --apply

python3 scripts/audit-british-english.py --base-dir . --json
python3 scripts/audit-british-english.py --base-dir . --fix

python3 scripts/audit-logic.py --base-dir . --json

python3 scripts/verify-refs.py --bib references.bib --json
python3 scripts/verify-refs.py --bib references.bib --json --online
python3 scripts/verify-refs.py --bib references.bib --json --online --metadata-dir path/to/metadata-fixtures

python3 .claude/skills/release-governance/scripts/check_release_packet.py .
```

Safe fixers are intentionally narrow. Citation fixes only apply conservative formatting changes such as Harvard comma normalisation; British English fixes only apply whole-word spelling replacements from the built-in map. Paragraph logic and reference metadata checks report findings for agent or user review.
Release packet checks are also narrow: they validate files, columns, evidence-state values, parseability, local path leakage, and unresolved template markers, but they do not judge scientific validity or venue compliance.

## Project Layout

```text
my-writing-project/
├── .claude/skills/          Claude Code skills
├── .agents/skills/          Symlinks for Codex, Gemini, and compatible agents
├── .cursor/rules/           Cursor baseline rules
├── apps/                    ChatGPT App MCP server
├── chapters/                Your chapter drafts
├── literature/
│   └── reading_notes/       One notes file per source
├── plugins/                 Codex plugin package
├── release/                 Optional release governance packets
├── final_output/            Exported documents
├── scripts/                 Deterministic helper checks
├── CLAUDE.md                Canonical project configuration
├── AGENTS.md                Generated local-agent configuration
└── GEMINI.md                Generated Gemini configuration
```

## Configuration

Edit `CLAUDE.md` for project-specific settings, then run:

```bash
make sync
```

`AGENTS.md` and `GEMINI.md` are generated from the shared block in `CLAUDE.md`; do not edit them directly.

Key settings include:

- chapter, literature, notes, and export directories
- reading page limits
- British English writing policy
- citation style (`harvard`, `apa`, `chicago-author-date`, `mla`, `ieee`, `vancouver`, `gb-t-7714-2015`)

## Testing And Maintenance

```bash
make doctor   # read-only environment check
make repair   # repair symlinks and generated configs where possible
make test     # full regression suite
make sync     # regenerate AGENTS.md and GEMINI.md
make plugin-sync   # regenerate the Codex plugin skills from .claude/skills
make plugin-check  # validate plugin metadata, sync state, and bundled helpers
make chatgpt-app-check  # run the ChatGPT App MCP server checks
```

For Codex plugin release preparation, use [`docs/plugin-publishing-checklist.md`](docs/plugin-publishing-checklist.md). For ChatGPT App deployment and submission preparation, use [`docs/chatgpt-app-publishing.md`](docs/chatgpt-app-publishing.md). For `v0.3.0` release preparation, use [`docs/product/v0.3.0-release-readiness.md`](docs/product/v0.3.0-release-readiness.md).

The regression suite covers local skill discovery, config sync, export assumptions, citation auditing, public-content cleanup, British English checks, paragraph-logic checks, human-evaluation handoff repair packaging, and offline plus fixture-backed reference verification.

## Reference Verification

`/verify-refs` uses a deterministic offline core by default:

- parse BibTeX from `.bib` files or Markdown code fences
- check required fields by entry type
- detect duplicate keys
- validate DOI, URL, and arXiv identifier shape

For explicit metadata verification, run with `--online`. The script checks CrossRef for DOI records, Semantic Scholar as a secondary DOI/arXiv source, and arXiv for preprint identifiers. Tests use `--metadata-dir` fixtures so CI stays deterministic; live network calls are only attempted when `--online` is set and no matching fixture is present.

Project-specific self-citation rules are intentionally excluded from this public toolkit.

## License

MIT. See [LICENSE](LICENSE).
