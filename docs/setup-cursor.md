# Setup: Cursor

## Prerequisites

- [Cursor](https://cursor.com) IDE installed

## Install

1. Clone the repository:
   ```bash
   git clone https://github.com/yhryzy/academic-writing-toolkit.git my-thesis
   ```
2. Open the `my-thesis` folder in Cursor.

Rules are auto-loaded from `.cursor/rules/academic-writing.mdc`.

## What You Get

Cursor applies the academic writing conventions automatically:

- Standardised reading notes file format
- Chapter structure conventions
- Writing principles (read-first workflow, British English)
- Literature directory organisation

## Limitations

Cursor uses its own rules system (`.mdc` files), not the `SKILL.md` agent
skill format. You cannot invoke `/read`, `/note`, etc. as slash commands
inside Cursor's chat.

## Pairing Cursor with a CLI Agent

For full skill functionality, open a terminal inside Cursor and run a CLI agent:

```bash
# Pick one:
claude       # Claude Code
codex        # Codex CLI
gemini       # Gemini CLI
```

This gives you the best of both worlds:

- **Cursor** for editing, navigation, and inline AI assistance
- **CLI agent** for structured skill workflows (`/read`, `/integrate`, `/audit`, etc.)

## Customise

- Cursor rules: `.cursor/rules/academic-writing.mdc`
- Project-wide agent config: `AGENTS.md` (also read by Cursor's agent mode)

Edit these files to adjust word count targets, directory paths, or
writing conventions for your project.
