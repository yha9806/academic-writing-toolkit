# /peer-review

Review another author's manuscript as an external reviewer.

Use this skill for formal reviews, desk-reject triage, preprint review, paper critique, proposal review, or thesis-chapter review where the task is to evaluate the submitted work rather than rewrite it.

## Codex-Only Baseline

Codex can complete the review from the supplied manuscript, supplementary files, rubric, and source anchors. Do not require Gemini, gemini-agent, a second model, or a subagent. If `/argument-governance` is unavailable, manually extract the same problem-gap-contribution-claim-evidence spine in the review report.

## Enhanced Advisory Mode

With explicit user approval and an API key stored in an environment variable, Codex may run an external advisory review after its own first-pass review. Treat that result as a second opinion: compare it against source-grounded Codex findings, keep only grounded points, and do not present it as reviewer consensus.

## Scope

The skill reviews only:

- the manuscript
- explicitly supplied supplementary materials
- explicitly requested reference or evidence checks

It does not use private author intent, prior chat context, or unpublished project memory as evidence.

## Review Areas

- novelty
- significance
- gap-contribution fit
- claim-evidence adequacy
- method and evaluation validity
- related-work coverage
- overclaim and generalisation risk
- reproducibility and transparency
- structure and clarity

## Output

Formal reviews use:

```text
## Peer Review

### Summary
### Strengths
### Major Concerns
### Gap-Contribution Fit
### Claim-Evidence Adequacy
### Method / Evaluation Concerns
### Overclaim And Boundary Risks
### Minor Comments
### Required Revisions
### Recommendation
```

Recommendation vocabulary:

- `accept`
- `minor_revision`
- `major_revision`
- `reject_resubmit`
- `reject`
- `no_recommendation`

Use `/argument-governance` first when the review needs a formal intent, contribution, claim, and evidence map.
