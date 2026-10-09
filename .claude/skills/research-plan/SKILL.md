---
name: research-plan
description: Explore research directions, assess value and feasibility, plan thesis or paper contributions, and revisit plans after new evidence. Use for 选题、研究方向、论文规划; not manuscript editing or citation checking.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebSearch, WebFetch
---

# /research-plan — Research Direction and Paper Planning

Help the researcher decide what is worth investigating next, what is feasible,
and what a thesis or paper might contribute. A vague idea is a valid starting
point. This is an experimental advisory workflow; producing a plan does not
establish scientific value, degree sufficiency, or publication prospects.

## Choose the scope from the request

- **Explore:** clarify an idea, its possible value and the next useful question.
  Discuss with the user; a complete form, manuscript or experiment is not needed.
- **Plan:** organise a research direction into a concise discussion summary,
  separating thesis planning from individual paper planning.
- **Revisit:** read the existing plan and the new information, compare the old
  and current judgement, and explain what could justify continuing, narrowing,
  redirecting, pausing or stopping. Effort already spent is not by itself a
  reason to continue. The researcher chooses the direction.

Use the user's language and retain their framing. Recover known information
from the supplied material before asking questions. Ask only about unknowns
that could change the next action; do not administer all six areas as a fixed
questionnaire. If useful progress is possible, leave unknowns visible and proceed.

## Judgements to support

| Area | Establish when relevant |
|---|---|
| Goals and requirements | Exploration, degree completion, publication or a combination; degree type, stage, time and actual requirements with their source. Scaffold word counts and chapter targets are defaults, not verified degree requirements. |
| Research value | What is unknown, what indicates the question exists, the nearest inspected prior work or current explanation, and what an answer could add to knowledge or practice. Ask whether an existing method, tool or simpler study already answers it well enough; if so, that is the comparator to beat. |
| Research scope | How subquestions answer a central question; distinguish the main answer, explanation, validation and development exploration. One sufficiently deep study is also valid. |
| Feasibility | Available data or materials, access conditions, equipment, skills, time, feedback, key unknowns and a smaller path if an essential condition fails. |
| Contribution and evidence | Prospective contribution, an informative comparator or competing explanation, appropriate evidence and what is still missing. Keep plans distinct from observations and results. |
| Publication planning | Optional candidate paper units, independent questions and contributions, required evidence, readers, possible venues and evidence-dependent timing. |

Keep these judgements separate. Do not infer merit from workload, counts, venue
prestige or one overall score. Contributions may be theoretical, explanatory,
conceptual, qualitative, measurement, replication, synthesis, negative findings
or resources; do not require a new model, a solution or an immediate application.
Lack of supplied evidence calls for bounded investigation, not automatic rejection.

For thesis planning, explain the central question and the relationship between
studies or the route to depth in one study. For each candidate paper, explain its
own question, contribution, comparator and evidence needs. Never assume one
chapter equals one paper. Shared evidence and dependencies should be visible;
overlapping units may belong in one paper. Publication planning may be deferred.

## Find a decision-changing next step

Choose the smallest useful investigation of the most consequential uncertainty.
It may be a literature check, access check, proof attempt, observation, interview
or experiment. Name the question, comparator or competing explanation, needed
materials, resource limit and revisit point, and the events that should
prompt an earlier revisit: closer prior work found, a change of scope or goal,
or the resource limit reached. Explain what supporting,
non-supporting and ambiguous outcomes would change, and the fallback if the
necessary conditions cannot be obtained. Do not invent thresholds or results.

Identify the basis of consequential statements locally: researcher report,
hypothesis, inspected source, obtained result or tool suggestion. Give a source
location and actual reading scope when available. A title, abstract, sparse
search or remembered paper cannot establish novelty or absence of prior work.
Do not invent literature, data access, degree rules or venue requirements.
Verify current official rules when concrete degree or venue decisions need them;
if sources or browsing are unavailable, retain the specific verification task.

## Produce and preserve the discussion summary

Read the [discussion template](references/discussion-record.md) when producing
or updating a summary. Adapt its labels to the user's language, retain the seven
discussion areas and separate thesis and paper fields, and allow unknown or
not-applicable entries. Aim for a one-page summary; link detailed evidence and
designs rather than compressing away uncertainty. Do not require new CSV ledgers.

For a request to create, organise, save or update a research plan or discussion
record, save the result in the user's research workspace. Reuse a supplied path
or the existing plan; otherwise use `planning/research-discussion.md`. A purely
exploratory question can be answered in chat. Existing authorisation to save or
update is sufficient; do not ask again just because the plan contains unknowns.

Before replacing an existing record, preserve its exact bytes in that project's
version history or a new file under `planning/history/` with a unique dated name.
Check that the previous content is recoverable before writing the new version;
an uncommitted working copy alone is not version history. Never overwrite a prior
snapshot. If preservation fails, leave the existing file intact and return the
proposed update in chat. Follow existing project naming conventions when present.

Each update names its predecessor and records the old judgement, new judgement,
basis, effect on the next action, and whether the researcher has decided. Keep
unchanged uncertainty and contrary evidence. A deliberate goal change is a
researcher decision, not a new scientific finding. Repetition, a polished plan
or an agent's judgement must not promote a guess to fact or imply human approval.

Finish with the current next step, pending decisions and the saved file link
when applicable. Do not change a manuscript, contact collaborators or transmit
project materials to another service as a side effect of planning.

## Use alongside other work

When entered after `/review`, use the completed findings as advisory input and
name the manuscript or evidence anchors behind them. Keep the assessment of
the current manuscript distinct from prospective contributions and researcher
decisions. Additional goals or constraints supplied for planning do not become
evidence read by a prior independent reviewer. An agent's review is not itself
proof of the underlying scientific claim. Reuse an existing discussion record
when asked to save or update the plan.

This skill works directly without ProblemBridge or ClaimHarness. A user-supplied
ProblemBridge brief can be an input. So can a user-supplied ClaimHarness evidence
brief (`evidence_brief.md` or `.json`): read its program statuses apart from the
user's notes and handling records, and treat neither as a confirmed human review.
Its coverage stays unknown, since claims the checker did not extract are absent
from the brief. Concrete results and text may later support
a limited ClaimHarness check within its available capabilities; this skill does
not implement that connection. Use AWT's existing reading, notes and manuscript
workflows when the user needs those tasks, without making them prerequisites
for an initial research discussion.
