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

You should see the nine canonical skills listed in [the skills guide](skills/README.md), including `/review` and `/edit-contract`.

## Available Skills

| Command | Purpose |
|---------|---------|
| `/read` | Guided reading with page-by-page PDF extraction |
| `/note` | Record structured reading notes |
| `/map` | View literature coverage matrix |
| `/review` | External manuscript review or own-work clean-room review |
| `/integrate` | Weave reading notes into chapter drafts |
| `/audit` | Pre-submission consistency check |
| `/edit-contract` | Define a bounded edit scope and record revision attempts |
| `/verify-refs` | Check BibTeX records and metadata |
| `/export` | Export chapters to Word (.docx) and ZIP |

## Customise

Edit `CLAUDE.md` to set your:

- Word count targets per chapter
- Reading pace limits (e.g. max pages per session)
- Directory paths for literature and chapters

## Helper resources

Use the source checkout for this project-local route. Several skills call
repository helpers or load templates outside their own directory; copying
only `.claude/skills/` produces an incomplete standalone installation.
The [global installer](setup-codex-cli.md) packages those resources for Codex.

## Usage Examples

```
/read literature/my-paper.pdf        # Start reading a paper
/note                                 # Record notes from reading
/map                                  # See literature coverage matrix
/review                      # Review the submitted manuscript
/integrate                            # Weave notes into chapters
/audit                                # Pre-submission consistency check
/edit-contract                   # Define the edit scope
/verify-refs references.bib           # Check BibTeX records
/export chapters en-only             # Export chapters to Word
```
