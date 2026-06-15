# Skills Guide

This toolkit provides local agent skills for academic writing projects. Skills are discovered from `.claude/skills/` by Claude Code and from `.agents/skills/` by Codex, Gemini, and compatible hosts.

This page is the canonical public index for local agent skills. Runtime setup guides should point here rather than maintaining separate skill inventories.

If you want to start from a goal rather than a skill name, see the [use-case guides](../use-cases/README.md).

## Pipeline

```text
/read -> /note -> /map -> /evidence-review -> /integrate -> /audit -> /release-governance -> /style -> /logic-review -> /export
             |                                      |
             v                                      v
        /verify                               /verify-refs
             |
             v
        /progress
```

## Guides

| Skill | Guide |
|-------|-------|
| `/read` | [01-read.md](01-read.md) |
| `/note` | [02-note.md](02-note.md) |
| `/verify` | [03-verify.md](03-verify.md) |
| `/map` | [04-map.md](04-map.md) |
| `/evidence-review` | [12-evidence-review.md](12-evidence-review.md) |
| `/integrate` | [05-integrate.md](05-integrate.md) |
| `/audit` | [06-audit.md](06-audit.md) |
| `/release-governance` | [13-release-governance.md](13-release-governance.md) |
| `/progress` | [07-progress.md](07-progress.md) |
| `/export` | [08-export.md](08-export.md) |
| `/style` | [09-style.md](09-style.md) |
| `/logic-review` | [10-logic-review.md](10-logic-review.md) |
| `/verify-refs` | [11-verify-refs.md](11-verify-refs.md) |

The shared data contract is the notes file in `literature/reading_notes/`: status, source citation, relevance, detailed notes, and thesis connections.
