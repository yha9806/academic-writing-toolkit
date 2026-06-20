# /manuscript-reframe

Use this skill when a draft is technically complete but still reads like an engineering report, internal validation packet, or module inventory.

## What It Does

- Identifies the scientific gap and manuscript spine.
- Converts module lists into a contribution chain.
- Rewrites Results around a narrative transition instead of raw metric dumps.
- Keeps LLM/VLM or generative components in supplementary or future-work roles unless they are the locked primary experiment.
- Assigns clear argumentative roles to figures and tables.
- Separates scientific readiness from submission metadata readiness.

## Typical Prompts

```text
Use /manuscript-reframe to make this draft read like a scientific paper.
```

```text
The manuscript still feels like a report. Diagnose the gap, contribution, figure roles, and submission blockers.
```

```text
Reframe this methods paper so the contribution is not just a list of modules.
```

## Expected Outputs

For audit-only tasks:

- paper-spine diagnosis
- gap/contribution issues
- report-like passages
- figure/table issues
- overclaim risks
- submission blockers
- recommended edit plan

For edit tasks:

1. title and abstract thesis
2. Introduction gap and contribution chain
3. Methods hierarchy
4. Results narrative and table captions
5. Discussion/conclusion boundary language
6. figure captions and table placement
7. submission metadata notes

## Key Guardrail

Do not call a draft submission-ready while author metadata, ethics/waiver, funding, competing interests, CRediT, data/code availability, references, or figure provenance remain unresolved.