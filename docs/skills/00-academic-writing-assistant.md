# Academic Writing Assistant

`/academic-writing-assistant` is the project-level entry point for the toolkit.
Use it when you need to understand what a research project currently contains,
how its argument fits together, and which controlled workflow should happen
next. Its centre is project organisation, not rebuttal writing.

## What it produces

- a canonical project snapshot and explicit unknowns;
- a research-spine summary across gap, data, results, claims, contributions, and
  innovation evidence;
- an objective account of missing, duplicated, orphaned, conflicting, or
  scope-mismatched content;
- one primary specialist route, its expected artifact, and its stop or approval
  gate;
- a contribution-focus decision status with support and counter-signals;
- a short session summary log for later project review when writes are
  authorised.

It does not create a second relationship schema or a scientific-quality score.
Relationship work is delegated to `/argument-governance`, including its strict
checker, object IDs, rule IDs, focus candidates, and author-decision gate.

## Typical request

```text
Use /academic-writing-assistant to organise this project. First confirm the
canonical version, then inspect the relations among the gap, data, results,
claims, contributions, and innovation evidence. Judge objectively what is
missing or redundant, and select only the next workflow. Do not change the
contribution focus without my approval.
```

中文可以直接这样使用：

```text
使用 /academic-writing-assistant 梳理这个项目。先确认作者批准的规范版本，
再检查 gap、数据、结果、claim、贡献与创新证据关系，客观判断哪些缺失、
重复或错配。每轮只选择一个下一步 workflow；未经我确认，不要调整贡献侧重。
```

The assistant normally routes one current need to one specialist:

| Need | Route |
|---|---|
| Literature evidence and gap coverage | `/evidence-review` |
| Argument relations, evidence balance, or contribution focus | `/argument-governance` |
| Approved notes entering a stable chapter | `/integrate` |
| Bounded edits with drift control | `/thesis-control` |
| Paper-wide contribution or narrative change | `/manuscript-reframe` |
| Three failed attempts or version contamination | `/revision-escalation` |
| Final internal consistency | `/audit` |
| Submission and artifact readiness | `/release-governance` |

## Safety gates

- A contribution-focus candidate remains `pending_author_decision` until the
  author approves it. No title, abstract, research-question, contribution-order,
  or paper-spine change happens before that approval.
- A candidate must stay within the same `intent_id`; evidence from a different
  paper or manuscript unit cannot justify swapping the current primary.
- "Too little" means a required argumentative function or reliable relation is
  missing. "Too much" means duplication, padding, orphaning, conflict, scope
  mismatch, or no distinct argumentative function. Raw counts are not proof.
- After three unsuccessful controlled revisions to the same issue, the assistant
  stops a fourth direct edit and routes to `/revision-escalation`.
- If there is no identifiable canonical version, it reports the blocker before
  editing.

## Session logs

When file changes are authorised, the assistant appends a factual Markdown
summary under `codex_outputs/academic-writing-log/`. It records files
inspected, changes made, decisions, deliberately unchanged areas, blockers, and
next controlled actions. It does not store hidden reasoning, credentials, or
sensitive source text. A read-only review produces the same summary in chat
without writing a file.
