# /revision-escalation

Use `/revision-escalation` when the same writing, code, rebuttal, or manuscript issue has gone through repeated unsatisfactory edits and may no longer be a local patch problem.

## What It Does

- Stops the fourth patch after three failed revision attempts.
- Counts only applied contracts for the same issue whose resolved drift audits
  failed; proposed, unapplied, pending, and unresolved work does not consume an
  attempt.
- Classifies the failure as underspecified request, ambiguous feedback, local execution problem, structural mismatch, evidence gap, or version contamination.
- Separates local wording fixes from section restructuring and full reframing.
- Forces unsupported claims to be downgraded or backed with evidence before revision continues.
- Recommends a consolidated brief, new version, or branch when repeated patches have polluted the draft.

## Typical Prompts

```text
Use /revision-escalation. This gap paragraph has been revised three times and still feels wrong.
```

```text
Stop editing and diagnose whether this is a local patch, section restructure, or full reframing problem.
```

```text
The rebuttal keeps getting longer but not clearer. Run the 3-strike revision check before another rewrite.
```

## Expected Output

- category
- exact issue and counted contract IDs when supplied
- counted failed-attempt total
- revision scope and latest author-approved version
- acceptance condition
- reason for the diagnosis
- missing or conflicting information
- safe next action and an explicit author-decision gate
- options for clarifying, consolidating, branching, restructuring, or reframing

When structured revision metadata is available, the output is a
`Revision Escalation Check`. Unsupported universal, causal, clinical,
cross-lingual, cross-population, or cross-benchmark headlines are classified as
an evidence gap; changing an abstract, title, main contribution, or paper-wide
evidence licence is full reframing even if the requested patch is short.

## Key Guardrail

Do not continue accumulating edits on a structurally inconsistent manuscript, rebuttal, or code path. If a claim cannot be supported by the available evidence, downgrade it or request evidence before rewriting.
