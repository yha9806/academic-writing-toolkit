# Academic Writing Assistant

`/academic-writing-assistant` is the project-level entry point for the toolkit.
Use it when you need to understand what a research project currently contains,
how its argument fits together, and which controlled workflow should happen
next. Its centre is project organisation, not rebuttal writing.

## What it produces

- a canonical project snapshot and explicit unknowns;
- a research-spine summary across gap, data, results, claims, contributions, and
  innovation evidence;
- an argument-level lock separating the field gap, exact paper contribution,
  scoped empirical claim, and any extrapolative headline;
- a six-line Paper Claim Licence stating the current headline, supported scope, and explicitly
  unsupported stronger claims;
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

## Lock the paper before rewriting it

The assistant first separates four levels that are often accidentally written
as one claim:

1. the broad field-level gap;
2. the exact contribution delivered by this paper;
3. the primary empirical claim supported by the present data and design;
4. any stronger extrapolation, such as necessity, dominance, causality, or
   portability.

It then records six lines:

```text
Broad problem:
Exact paper contribution:
Primary empirical claim:
Headline or extrapolative claim:
Licensed scope:
Explicitly unlicensed claims:
```

`Licensed scope` covers the relevant population or denominator, data, model,
measurement or annotator process, baseline, estimand, conditions, uncertainty,
and transfer limits. Missing information is marked `unknown`; the assistant
does not infer it from how important or interesting the broad problem is.

Every upward inference needs additional direct evidence. A real gap does not
prove that one paper closes it, and a useful scoped finding does not by itself
establish a universal or portable principle.

## Diagnose what kind of repair is possible

| Layer | What it means | Next action |
|---|---|---|
| Wording | Evidence supports a bounded claim, but the title, abstract, contribution wording, result heading, or conclusion overstates it. | Use a controlled edit or approved paper-wide reframe. |
| Argument design | Claim hierarchy, denominator, estimand, evidence mapping, uncertainty, contribution role, or generalisation is unclear. | Run `/argument-governance` before rewriting. |
| Research design | Construct validity, reliability, sampling, baseline, power, comparison, or external validation is insufficient. | Add the decisive evidence, or obtain author approval to narrow the claim. Prose alone cannot repair it. |

If a stronger framing is discovered after the experiments were designed, the
assistant checks whether the original construct, estimand, denominator,
comparison, and validation actually test it. Without matched new evidence, the
framing remains motivation, bounded interpretation, or a future hypothesis.

Boundary is also checked across the whole paper: title, research question,
sampling and denominator, estimand, experiment, abstract, contribution list,
result headings, conclusion, and limitations. A cautious limitations paragraph
does not cancel an overclaim elsewhere. Extra tables, ledgers, guardrails,
qualifiers, or appendices can improve transparency but cannot substitute for
missing evidence.

## Typical request

```text
Use /academic-writing-assistant to organise this project. First confirm the
canonical version, then inspect the relations among the gap, data, results,
claims, contributions, and innovation evidence. Judge objectively what is
missing or redundant. Lock the field gap, exact paper contribution, primary
empirical claim, current headline or extrapolation, licensed scope, and
unlicensed claims, then select only the next workflow. Do not change the
contribution focus without my approval.
```

中文可以直接这样使用：

```text
使用 /academic-writing-assistant 梳理这个项目。先确认作者批准的规范版本，
再检查 gap、数据、结果、claim、贡献与创新证据关系，客观判断哪些缺失、
重复或错配。分别写清领域 gap、本文贡献、主要实证结论、当前 headline 或
外推主张、证据许可范围和当前不能声称的结论；先判断是表述、论证设计还是
研究设计问题。每轮只选择一个下一步 workflow；未经我确认，不要调整贡献侧重。
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
- A late framing upgrade is not treated as validated unless its estimand and
  research design have matching evidence. Otherwise it is narrowed, deferred,
  or recorded as `evidence_needed`.
- Boundaries must constrain the whole paper, not only the limitations section.
- A research-design deficit is never routed to prose polishing. Additional
  defensive tables or guardrails do not upgrade the evidence licence.
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
