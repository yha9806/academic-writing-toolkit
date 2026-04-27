# academic-writing-toolkit

***Structured skills for reading, writing, and managing academic research with AI agents.***

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Agent Skills](https://img.shields.io/badge/Agent_Skills-Standard-blue.svg)](https://agentskills.io)
[![Works with](https://img.shields.io/badge/Works_with-Claude_Code_|_Codex_CLI_|_Gemini_CLI_|_Cursor-purple.svg)](#platform-compatibility)

```
  /read --> /note --> /map --> /integrate --> /audit --> /export
              ^                                           ^
           /verify                                    /progress
```

| Without toolkit | With toolkit |
|-----------------|--------------|
| Ad-hoc prompts, different every time | Structured pipeline with 8 specialised skills |
| Scattered notes across files and chats | Standardised notes format — one file per source |
| Manual Word conversion | One-command Markdown to Word + ZIP |
| "Did I cite this already?" | Automated cross-chapter consistency audit |
| No idea what you've read | Progress dashboard: sources, words, coverage |

---

## Quick Start

> ⚠️ **Use `git clone`, not GitHub's "Download ZIP".** This repo uses symlinks under `.agents/skills/` for cross-platform skill discovery. ZIP downloads silently replace symlinks with copies, breaking Codex / Gemini / OpenClaw integrations. If you must use ZIP, run `make repair` after extracting.

Clone the repo and start your agent. Skills are discovered automatically.

**Claude Code** (recommended):

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
claude
# Skills auto-discovered. Type /read to start.
```

**Codex CLI**:

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
codex
# Skills loaded from .agents/skills/
```

**Gemini CLI**:

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
gemini
# Skills loaded from .agents/skills/
```

**Cursor**:

```
1. Clone the repo
2. Open in Cursor
3. Rules auto-loaded from .cursor/rules/
Note: Cursor supports rules only. For full skill invocation, pair with a CLI agent.
```

---

## First Run Checklist

After cloning, run these once:

```bash
make setup     # sets git config, syncs configs, runs health check
make init      # opens CLAUDE.md in $EDITOR — fill in your project parameters
```

Then start your AI agent (`claude`, `codex`, or `gemini`) and use `/read` on your first PDF.

Anytime later:

| Command | When to run |
|---------|-------------|
| `make doctor` | Sanity-check the environment (read-only, fast) |
| `make repair` | Fix anything `doctor` flags red |
| `make sync`   | After editing `CLAUDE.md` (regenerates `AGENTS.md` / `GEMINI.md`) |
| `make help`   | List all targets |

---

## Skills Overview

Eight skills covering the full research-to-submission pipeline.

| Skill | Purpose | Phase |
|-------|---------|-------|
| `/read` | Page-by-page PDF reading with structured output | Reading |
| `/note` | Record notes to standardised files | Reading |
| `/verify` | Fact-check claims against online sources | Reading |
| `/map` | Literature-to-chapter mapping matrix | Analysis |
| `/integrate` | Weave reading notes into thesis chapters | Writing |
| `/audit` | Cross-chapter consistency check | Quality |
| `/progress` | Reading + writing progress dashboard | Tracking |
| `/export` | Markdown to Word + ZIP packaging | Delivery |

**New to skills?** Read the [Skills Guide](docs/skills/) for detailed walkthroughs, internal logic, and practical examples for each skill.

---

## The Pipeline

All skills share a standardised notes file format. This is the data contract that connects the pipeline.

When you `/read` a PDF, the agent produces structured output. `/note` writes it into a notes file following the template. Each notes file contains a **Thesis Connections** table:

```markdown
| Note Point | Chapter | Section | Connection Type |
|------------|---------|---------|-----------------|
| thing-power | Ch3 | S3.4 | supports |
| assemblage | Ch5 | S5.2 | extends |
```

This table is what `/map` scans to build a literature-to-chapter matrix, and what `/integrate` consumes when weaving sources into chapter drafts. The `Status` field at the top of each notes file (`reading` / `completed` / `integrated`) is what `/progress` reads to calculate your coverage.

The result: every skill reads from and writes to the same file structure, so nothing falls through the cracks.

---

## Platform Compatibility

| Platform | Config File | Skills Directory | Support Level |
|----------|-------------|------------------|---------------|
| Claude Code | `CLAUDE.md` | `.claude/skills/` | Full |
| Codex CLI | `AGENTS.md` | `.agents/skills/` | Full |
| Gemini CLI | `GEMINI.md` | `.agents/skills/` | Full |
| Cursor | `.cursor/rules/` | — | Rules only |
| OpenClaw | `AGENTS.md` | `.agents/skills/` | Compatible |
| VS Code Copilot | — | `.agents/skills/` | Full |

Skills follow the [Agent Skills](https://agentskills.io) open standard. Write once, run on any supporting agent.

See `docs/` for platform-specific setup guides.

---

## Project Template

Clone the repo and you get a ready-to-use thesis directory:

```
my-thesis/
├── .claude/skills/          8 structured skills (Claude Code)
├── .agents/skills/          Same 8 skills (Codex / Gemini / Copilot)
├── .cursor/rules/           Rules file (Cursor)
├── chapters/                Your thesis chapters (template included)
├── literature/
│   └── reading_notes/       One notes file per source (template included)
├── final_output/            Exported Word / ZIP files
├── docs/                    Platform setup guides
├── CLAUDE.md                Config for Claude Code
├── AGENTS.md                Config for Codex CLI / OpenClaw
└── GEMINI.md                Config for Gemini CLI
```

---

## Configuration

Edit `CLAUDE.md` to set your project parameters. `CLAUDE.md` is the canonical config — `AGENTS.md` and `GEMINI.md` are auto-generated from it. Run `make sync` after editing to propagate changes to all platform files.

Key configurable items:

**Word count targets** — total and per-chapter:

```markdown
## Targets
- Total word count target: 80,000

| Chapter | Title | Target Words |
|---------|-------|-------------|
| Ch1 | Introduction | 5,000 |
| Ch2 | Background | 10,000 |
...
```

**Reading page limits** — prevents the agent from reading too much in one session:

```markdown
## Reading Constraints
- Max pages per read invocation: 15
- Max pages per conversation: 90
```

**Directory paths** — change these if your project structure differs:

```markdown
## Directories
- Chapters: `chapters/`
- Literature PDFs: `literature/`
- Reading notes: `literature/reading_notes/`
- Export output: `final_output/`
```

---

## Notes File Format

All skills share a standardised notes format. This is the data contract that makes the pipeline work.

Key fields in every notes file:

- **Status**: `reading` | `completed` | `integrated` — tracked by `/progress`
- **Relevance**: Which chapter and section this source matters for
- **Thesis Connections table**: Structured mapping consumed by `/map` and `/integrate`

See the full template: [`literature/reading_notes/_template_NOTES.md`](literature/reading_notes/_template_NOTES.md)

---

## Built With

- [Agent Skills](https://agentskills.io) open standard
- Tested on a real 60,000-word PhD thesis with 52 sources across 8 theoretical traditions

---

## Contributing

Contributions welcome. Please open an issue first to discuss what you'd like to change.

---

## License

MIT — see [LICENSE](LICENSE).
