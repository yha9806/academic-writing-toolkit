# Unfamiliar-Reader Comprehension Gate

Use this gate for an important manuscript version after its research spine is
author-approved. It tests whether the paper's purpose and evidence boundary
are recoverable without exposing the reader to the full manuscript.

## Reader Packet

Provide only:

- title
- abstract
- Figure 1 with its caption
- the main Results summary table with its caption

All items must be listed in the self-review manifest. Do not add explanatory
notes, the author-intent card, prior chat, or a verbal briefing.

## Reader Questions

Ask an unfamiliar human reader to answer, preferably within three minutes:

1. What concrete problem does the paper address?
2. Who could use or benefit from the result?
3. What did the authors actually do?
4. What is the main result?
5. What has not yet been validated?

Record answers verbatim, elapsed time when available, and whether the reader
had prior project knowledge.

## Decision

Compare the answers with the author-approved intent and argument baseline.
Use:

- `passed`: the unfamiliar reader recovers all five functions without author
  explanation and without material contradiction;
- `failed`: one or more functions are missing, materially wrong, or require
  author explanation;
- `not_run`: no eligible human response is available;
- `advisory_only`: a model, collaborator with prior knowledge, or other
  non-independent reader supplied the response.

A model simulation can identify likely ambiguity but cannot pass this human
gate. Numerical, citation, reference, or PDF checks do not substitute for it.

If the result is `failed`, classify the failure as missing application purpose,
unclear research object or method task, hidden main result, missing evidence
boundary, or cross-section identity drift. Route structural failures to
`/thesis-control` or `/manuscript-reframe`; do not repeatedly paraphrase the
same abstract without an approved edit contract.

## Record Template

```text
Version:
Argument baseline:
Reader independence:
Elapsed time:
Q1 answer:
Q2 answer:
Q3 answer:
Q4 answer:
Q5 answer:
Decision: passed / failed / not_run / advisory_only
Mismatch summary:
Required next action:
```
