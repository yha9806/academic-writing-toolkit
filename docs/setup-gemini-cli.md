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

You should see the 11 public academic writing skills: read, note, verify, map, integrate, audit, style, logic-review, verify-refs, progress, export.

## Available Skills

| Skill     | Purpose                              |
|-----------|--------------------------------------|
| read      | Guided reading with page-by-page PDF extraction |
| note      | Record structured reading notes      |
| verify    | Fact-check claims against sources    |
| map       | View literature coverage matrix      |
| integrate | Weave reading notes into chapter drafts |
| audit     | Pre-submission consistency check     |
| style     | Check British English consistency    |
| logic-review | Review paragraph flow and transitions |
| verify-refs | Check BibTeX records and metadata |
| progress  | Writing progress dashboard           |
| export    | Export chapters to Word (.docx) + ZIP |

## Configuration

Gemini CLI reads `GEMINI.md` as its project instruction file, but `GEMINI.md` is auto-generated from `CLAUDE.md` (the canonical config). Edit `CLAUDE.md` to set your:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters

Then run `make sync` to regenerate `GEMINI.md` from your changes.

## Skill Discovery

Gemini CLI discovers skills from `.agents/skills/*/SKILL.md`. Each skill
file is plain Markdown with trigger conditions, input/output specs, and
step-by-step procedures.

## Usage Examples

```
read literature/my-paper.pdf         # Start reading a paper
note                                  # Record notes from reading
verify Smith published the article in 2020  # Fact-check a claim
map                                   # See literature coverage matrix
integrate                             # Weave notes into chapters
audit                                 # Pre-submission consistency check
style                                 # Check British English consistency
logic-review                          # Review paragraph flow
verify-refs references.bib            # Check BibTeX records
progress                              # View writing dashboard
export chapters en-only              # Export chapters to Word
```
