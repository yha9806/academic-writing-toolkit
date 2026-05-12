# academic-writing-toolkit

Structured local agent skills for academic reading, writing, reference checking, and export.

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-Standard-blue.svg)](https://agentskills.io)

This repository is a public toolkit. It contains reusable local agent skills, scripts, templates, and tests only. Put your own chapters, PDFs, notes, and private project material in your clone.

```
/read -> /note -> /map -> /integrate -> /audit -> /style -> /logic-review -> /export
             |                         |
             v                         v
        /verify                  /verify-refs
             |
             v
        /progress
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
| `/integrate` | Propose and apply approved note-to-chapter integrations |
| `/audit` | Check numbers, terminology, cross-references, and citations |
| `/style` | Check and safely fix British English spellings |
| `/logic-review` | Review paragraph flow, transitions, and argument continuity |
| `/verify-refs` | Validate BibTeX records offline or with explicit metadata checks |
| `/progress` | Show reading, writing, and coverage progress |
| `/export` | Convert Markdown outputs to `.docx` and ZIP packages |

Detailed guides live in [`docs/skills/`](docs/skills/).

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
```

Safe fixers are intentionally narrow. Citation fixes only apply conservative formatting changes such as Harvard comma normalisation; British English fixes only apply whole-word spelling replacements from the built-in map. Paragraph logic and reference metadata checks report findings for agent or user review.

## Project Layout

```text
my-writing-project/
├── .claude/skills/          Claude Code skills
├── .agents/skills/          Symlinks for Codex, Gemini, and compatible agents
├── .cursor/rules/           Cursor baseline rules
├── chapters/                Your chapter drafts
├── literature/
│   └── reading_notes/       One notes file per source
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
```

For Codex plugin release preparation, use [`docs/plugin-publishing-checklist.md`](docs/plugin-publishing-checklist.md).

The regression suite covers local skill discovery, config sync, export assumptions, citation auditing, public-content cleanup, British English checks, paragraph-logic checks, and offline plus fixture-backed reference verification.

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
