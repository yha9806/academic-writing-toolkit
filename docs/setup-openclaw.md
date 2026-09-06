# Setup: OpenClaw

## Prerequisites

- [OpenClaw](https://github.com/ArcadeAI/OpenClaw) installed and configured

## Install

```bash
git clone https://github.com/yha9806/academic-writing-toolkit.git my-thesis
cd my-thesis
openclaw
```

Skills are loaded from `.agents/skills/` (symlinked to `.claude/skills/`).

## Verify

Ask OpenClaw: "What skills are available?"

You should see the nine canonical skills listed in [the skills guide](skills/README.md), including `review` and `edit-contract`.

## Available Skills

| Skill | Purpose |
|-------|---------|
| read | Guided reading with page-by-page PDF extraction |
| note | Record structured reading notes |
| map | View literature coverage matrix |
| review | External manuscript review or own-work clean-room review |
| integrate | Weave reading notes into chapter drafts |
| audit | Pre-submission consistency check |
| edit-contract | Define a bounded edit scope and record revision attempts |
| verify-refs | Check BibTeX records and metadata |
| export | Export chapters to Word (.docx) and ZIP |

## Configuration

OpenClaw reads `AGENTS.md` as its project instruction file, but **`AGENTS.md` is auto-generated** from `CLAUDE.md` by this toolkit's sync tooling. To customise:

1. Edit `CLAUDE.md` (the canonical source — the SHARED block is what gets regenerated).
2. Run `make sync` to regenerate `AGENTS.md` (and `GEMINI.md`).
3. Verify with `make doctor`.

Things to set:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters

## Compatibility Notes

- OpenClaw natively uses `SOUL.md` for agent personality, but is fully
  compatible with the `SKILL.md` format used in `.agents/skills/`.
- Skills are discovered from `.agents/skills/*/SKILL.md` at startup.
- The `AGENTS.md` config file (auto-generated from `CLAUDE.md` — see
  Configuration above) follows the same convention as Codex CLI and
  Gemini CLI, so no extra setup is needed.

## Usage Examples

```
read literature/my-paper.pdf         # Start reading a paper
note                                  # Record notes from reading
map                                   # See literature coverage matrix
review                       # Review the submitted manuscript
integrate                             # Weave notes into chapters
audit                                 # Pre-submission consistency check
edit-contract                    # Define the edit scope
verify-refs references.bib            # Check BibTeX records
export chapters en-only              # Export chapters to Word
```
