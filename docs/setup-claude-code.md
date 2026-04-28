# Setup: Claude Code

## Prerequisites

- [Claude Code](https://claude.ai/code) installed and authenticated

## Install

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
claude
```

Skills are auto-discovered from `.claude/skills/`. Type `/read` to verify.

## Setup

After cloning, run:

```bash
make setup
```

This sets `git config core.fileMode false` (avoids mode-bit noise commits), regenerates `AGENTS.md` / `GEMINI.md` from `CLAUDE.md`, and runs `make doctor` to verify the environment.

If `make doctor` reports anything red, run `make repair` to fix what it can.

## Verify

Ask Claude: "What skills are available?"

You should see: `/read`, `/note`, `/verify`, `/map`, `/integrate`, `/audit`, `/style`, `/logic-review`, `/verify-refs`, `/progress`, `/export`

## Available Skills

| Command      | Purpose                              |
|--------------|--------------------------------------|
| `/read`      | Guided reading with page-by-page PDF extraction |
| `/note`      | Record structured reading notes      |
| `/verify`    | Fact-check claims against sources    |
| `/map`       | View literature coverage matrix      |
| `/integrate` | Weave reading notes into chapter drafts |
| `/audit`     | Pre-submission consistency check     |
| `/style`     | Check British English consistency    |
| `/logic-review` | Review paragraph flow and transitions |
| `/verify-refs` | Check BibTeX records and metadata |
| `/progress`  | Writing progress dashboard           |
| `/export`    | Export chapters to Word (.docx) + ZIP |

## Customise

Edit `CLAUDE.md` to set your:

- Word count targets per chapter
- Reading pace limits (e.g. max pages per session)
- Directory paths for literature and chapters

## Global Installation (optional)

To use these skills across all projects:

```bash
cp -r .claude/skills/* ~/.claude/skills/
```

## Usage Examples

```
/read literature/my-paper.pdf        # Start reading a paper
/note                                 # Record notes from reading
/verify Smith published the article in 2020  # Fact-check a claim
/map                                  # See literature coverage matrix
/integrate                            # Weave notes into chapters
/audit                                # Pre-submission consistency check
/style                                # Check British English consistency
/logic-review                         # Review paragraph flow
/verify-refs references.bib           # Check BibTeX records
/progress                             # View writing dashboard
/export chapters en-only             # Export chapters to Word
```
