# Skills Guide

This toolkit provides local agent skills for academic writing projects. Skills are discovered from `.claude/skills/` by Claude Code and from `.agents/skills/` by Codex, Gemini, and compatible hosts.

This page is the canonical public index for local agent skills. Runtime setup guides should point here rather than maintaining separate skill inventories.

If you want to start from a goal rather than a skill name, see the [use-case guides](../use-cases/README.md).

## Pipeline

```text
/read -> /note -> /map -> /evidence-review -> /argument-governance -> /integrate -> /thesis-control -> /manuscript-reframe -> /audit -> /release-governance -> /style -> /logic-review -> /export
             |                         |                                           |                                      |
             v                         v                                           v                                      v
        /verify                  /peer-review                                /revision-escalation                    /verify-refs
                                       |
                                       v
                                  /self-review
             |
             v
        /progress

/human-eval-handoff-repair is an evaluation-package QC and annotation repair workflow outside the thesis-writing pipeline.
/revision-escalation is a 3-strike stop-and-diagnose workflow for repeated failed writing, coding, rebuttal, or manuscript revisions.
```

## Guides

| Skill | Guide |
|-------|-------|
| `/read` | [01-read.md](01-read.md) |
| `/note` | [02-note.md](02-note.md) |
| `/verify` | [03-verify.md](03-verify.md) |
| `/map` | [04-map.md](04-map.md) |
| `/evidence-review` | [12-evidence-review.md](12-evidence-review.md) |
| `/argument-governance` | [17-argument-governance.md](17-argument-governance.md) |
| `/integrate` | [05-integrate.md](05-integrate.md) |
| `/thesis-control` | [15-thesis-control.md](15-thesis-control.md) |
| `/manuscript-reframe` | [14-manuscript-reframe.md](14-manuscript-reframe.md) |
| `/revision-escalation` | [16-revision-escalation.md](16-revision-escalation.md) |
| `/audit` | [06-audit.md](06-audit.md) |
| `/release-governance` | [13-release-governance.md](13-release-governance.md) |
| `/progress` | [07-progress.md](07-progress.md) |
| `/export` | [08-export.md](08-export.md) |
| `/style` | [09-style.md](09-style.md) |
| `/logic-review` | [10-logic-review.md](10-logic-review.md) |
| `/verify-refs` | [11-verify-refs.md](11-verify-refs.md) |
| `/human-eval-handoff-repair` | [13-human-eval-handoff-repair.md](13-human-eval-handoff-repair.md) |
| `/peer-review` | [18-peer-review.md](18-peer-review.md) |
| `/self-review` | [19-self-review.md](19-self-review.md) |

The shared data contract is the notes file in `literature/reading_notes/`: status, source citation, relevance, detailed notes, and thesis connections.
