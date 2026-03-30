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

## Verify

Ask Claude: "What skills are available?"

You should see: `/read`, `/note`, `/verify`, `/integrate`, `/audit`, `/export`, `/map`, `/progress`

## Available Skills

| Command      | Purpose                              |
|--------------|--------------------------------------|
| `/read`      | Guided reading with page-by-page PDF extraction |
| `/note`      | Record structured reading notes      |
| `/verify`    | Fact-check claims against sources    |
| `/integrate` | Weave reading notes into chapter drafts |
| `/audit`     | Pre-submission consistency check     |
| `/export`    | Export chapters to Word/PDF          |
| `/map`       | View literature coverage matrix      |
| `/progress`  | Writing progress dashboard           |

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
/verify Panofsky fled in 1933        # Fact-check a claim
/map                                  # See literature coverage matrix
/integrate                            # Weave notes into chapters
/audit                                # Pre-submission consistency check
/progress                             # View writing dashboard
/export chapters en-only             # Export chapters to Word
```
