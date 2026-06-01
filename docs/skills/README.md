# Skills Guide

This toolkit provides local agent skills for academic writing projects. Skills are discovered from `.claude/skills/` by Claude Code and from `.agents/skills/` by Codex, Gemini, and compatible hosts.

## Pipeline

```text
/read -> /note -> /map -> /evidence-review -> /integrate -> /audit -> /style -> /logic-review -> /export
             |                                      |
             v                                      v
        /verify                               /verify-refs
             |
             v
        /progress

/human-eval-handoff-repair is an evaluation-package QC and annotation repair workflow outside the thesis-writing pipeline.
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
| `/progress` | [07-progress.md](07-progress.md) |
| `/export` | [08-export.md](08-export.md) |
| `/style` | [09-style.md](09-style.md) |
| `/logic-review` | [10-logic-review.md](10-logic-review.md) |
| `/verify-refs` | [11-verify-refs.md](11-verify-refs.md) |
| `/human-eval-handoff-repair` | [13-human-eval-handoff-repair.md](13-human-eval-handoff-repair.md) |

The shared data contract is the notes file in `literature/reading_notes/`: status, source citation, relevance, detailed notes, and thesis connections.
