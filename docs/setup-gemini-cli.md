# Setup: Gemini CLI

## Prerequisites

- [Gemini CLI](https://github.com/google-gemini/gemini-cli) installed and authenticated

## Install

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
gemini
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

Ask Gemini: "What skills are available?"

You should see the 8 academic writing skills: read, note, verify, integrate, audit, export, map, progress.

## Available Skills

| Skill     | Purpose                              |
|-----------|--------------------------------------|
| read      | Guided reading with page-by-page PDF extraction |
| note      | Record structured reading notes      |
| verify    | Fact-check claims against sources    |
| integrate | Weave reading notes into chapter drafts |
| audit     | Pre-submission consistency check     |
| export    | Export chapters to Word/PDF          |
| map       | View literature coverage matrix      |
| progress  | Writing progress dashboard           |

## Configuration

Gemini CLI reads `GEMINI.md` as its project instruction file. Edit it to set your:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters

## Skill Discovery

Gemini CLI discovers skills from `.agents/skills/*/SKILL.md`. Each skill
file is plain Markdown with trigger conditions, input/output specs, and
step-by-step procedures.

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
