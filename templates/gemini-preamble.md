# Academic Writing Project

<!-- GENERATED FROM CLAUDE.md — do not edit. Run `make sync` after editing CLAUDE.md. -->

Configuration for Gemini CLI.

## Skill Discovery
Project skills are directories under `.agents/skills/`, each with `SKILL.md`,
linked to canonical sources in `.claude/skills/`. A text file containing a link
target is not a usable skill. Run `node scripts/setup.mjs` after cloning; on
Windows it creates ignored `awt-local-*` junction aliases when Git flattens
symlinks. `node scripts/setup.mjs doctor` checks actual link targets. Resolve a
selected skill's directory link before following relative resource paths.

