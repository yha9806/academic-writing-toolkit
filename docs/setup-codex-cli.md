# Setup: Codex CLI

## Prerequisites

- [Codex CLI](https://github.com/openai/codex) installed and authenticated

## Install

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
codex
```

Skills are loaded from `.agents/skills/` (symlinked to `.claude/skills/`).

## Setup

After cloning, run:

```bash
make setup
```

This sets `git config core.fileMode false` (avoids mode-bit noise commits), regenerates `AGENTS.md` / `GEMINI.md` from `CLAUDE.md`, and runs `make doctor` to verify the environment.

If `make doctor` reports anything red, run `make repair` to fix what it can.

## Verify

Ask Codex: "What skills are available?"

You should see the 8 academic writing skills: read, note, verify, integrate, audit, export, map, progress.

## Available Skills

| Skill     | Purpose                              |
|-----------|--------------------------------------|
| read      | Guided reading with page-by-page PDF extraction |
| note      | Record structured reading notes      |
| verify    | Fact-check claims against sources    |
| integrate | Weave reading notes into chapter drafts |
| audit     | Pre-submission consistency check     |
| export    | Export chapters to Word (.docx) + ZIP |
| map       | View literature coverage matrix      |
| progress  | Writing progress dashboard           |

## Configuration

Codex reads `AGENTS.md` as its project instruction file, but `AGENTS.md` is auto-generated from `CLAUDE.md` (the canonical config). Edit `CLAUDE.md` to set your:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters

Then run `make sync` to regenerate `AGENTS.md` from your changes.

## Skill Invocation

Codex CLI may use different syntax for invoking skills. Check the
[Codex documentation](https://github.com/openai/codex) for whether skills
are invoked as `/skill-name`, `$skill-name`, or by natural language reference.

The skill definitions in `.agents/skills/*/SKILL.md` are plain Markdown
and compatible with any agent that reads instruction files.

## Usage Examples

```
read literature/my-paper.pdf         # Start reading a paper
note                                  # Record notes from reading
verify Panofsky fled in 1933         # Fact-check a claim
map                                   # See literature coverage matrix
integrate                             # Weave notes into chapters
audit                                 # Pre-submission consistency check
progress                              # View writing dashboard
export chapters en-only              # Export chapters to Word
```
