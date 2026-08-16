# Skills Guide

This toolkit provides local agent skills for academic writing projects. Skills are discovered from `.claude/skills/` by Claude Code and from `.agents/skills/` by Codex, Gemini, and compatible hosts.

This page is the canonical public index for local agent skills. Runtime setup guides should point here rather than maintaining separate skill inventories.

If you want to start from a goal rather than a skill name, see the [use-case guides](../use-cases/README.md).

## Pipeline

```text
/read -> /note -> /map -> /integrate -> /edit-contract -> /review -> /audit -> /verify-refs -> /export
```

The catalogue was triaged from 20 skills to 9 on 2026-08-16
(see `docs/specs/2026-08-16-awt-dsh-app-v0.1-design.md` for per-skill
verdicts). Retired skills and their guides live under `archive/`.
On-demand reference documents: `references/argument-checklist.md`,
`references/evidence-vocabulary.md`, `references/reframe-method.md`.

## Guides

| Skill | Guide |
|-------|-------|
| `/review` | (guide pending; see the SKILL.md) |
| `/edit-contract` | (guide pending; see the SKILL.md) |
| `/read` | [01-read.md](01-read.md) |
| `/note` | [02-note.md](02-note.md) |
| `/map` | [04-map.md](04-map.md) |
| `/integrate` | [05-integrate.md](05-integrate.md) |
| `/audit` | [06-audit.md](06-audit.md) |
| `/export` | [08-export.md](08-export.md) |
| `/verify-refs` | [11-verify-refs.md](11-verify-refs.md) |

The shared data contract is the notes file in `literature/reading_notes/`: status, source citation, relevance, detailed notes, and thesis connections.
