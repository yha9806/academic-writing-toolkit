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

OpenClaw reads `AGENTS.md` as its project instruction file. Edit it to set your:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters

## Compatibility Notes

- OpenClaw natively uses `SOUL.md` for agent personality, but is fully
  compatible with the `SKILL.md` format used in `.agents/skills/`.
- Skills are discovered from `.agents/skills/*/SKILL.md` at startup.
- The `AGENTS.md` config file follows the same convention as Codex CLI
  and Gemini CLI, so no extra setup is needed.

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
