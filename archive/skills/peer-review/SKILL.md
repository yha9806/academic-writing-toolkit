---
name: peer-review
description: Review another author's manuscript, paper, thesis chapter, proposal, or preprint as an external reviewer. Use when asked to evaluate novelty, significance, gap-contribution fit, claim-evidence adequacy, methods, evaluation, overclaim risks, structure, writing, required revisions, or recommendation without rewriting the manuscript or using private author context.
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
---

# /peer-review - External Manuscript Review

## Purpose

Produce a reviewer-style assessment of another author's work. This skill judges the manuscript as submitted, not as the author wishes it to be.

Use `/argument-governance` first when the review needs a formal gap-contribution or claim-evidence map.

## Codex-Only Baseline

Complete the review with Codex using the supplied manuscript, supplements, rubric, and source anchors. Do not require Gemini, gemini-agent, a second model, or a subagent. If another reviewer tool is available, record its output as optional advisory context only.

If `/argument-governance` is unavailable in the user's environment, manually extract the same spine in the review report: problem, gap, contribution, main claims, evidence, boundary language, and reviewer risks.

## Enhanced Advisory Mode

If the user explicitly provides or enables an API-key-backed model review, use it only after Codex has made a first-pass review from the supplied materials.

Rules:

- keep API keys in environment variables, never in review files
- send only user-approved manuscript or supplement excerpts
- label the external result as `advisory_external_review`
- compare it against Codex's local findings
- include only grounded, source-checkable points in the final review
- do not treat the external model as a reviewer consensus, venue decision, or factual verifier

## Core Rules

1. Review only the manuscript and explicitly supplied supplementary materials.
2. Do not use private project memory, prior chats, unstated author intent, or unpublished context as evidence.
3. Separate reviewer judgment from factual verification.
4. Do not rewrite the manuscript unless the user explicitly asks for revision suggestions.
5. Attribute concerns to manuscript locations, sections, figures, tables, claims, or missing evidence.
6. Be fair: identify strengths before high-level weaknesses, but do not soften required revisions.
7. Do not infer venue-specific acceptance thresholds unless the venue or rubric is supplied.
8. Do not treat an unavailable external review tool as a blocker.

## Workflow

### 1. Establish Review Scope

Identify:

- manuscript path or pasted text
- article type or intended venue, if provided
- supplied supplementary materials
- whether the user wants a formal review, desk-reject triage, or improvement-oriented review
- whether reference or evidence checking is in scope

### 2. Extract The Claimed Paper Spine

From the manuscript only, identify:

- central problem
- claimed gap
- stated contributions
- main claims
- evidence offered for each claim
- limitations and boundary language

If this cannot be extracted, report that as a review finding.

### 3. Evaluate With The Reviewer Rubric

Read `references/reviewer_rubric.md` when producing a full review. Cover:

- novelty
- significance
- gap-contribution fit
- method or evaluation validity
- evidence adequacy
- claim-evidence balance
- related-work coverage
- overclaim and generalisation risk
- reproducibility or transparency
- structure and clarity

### 4. Write The Review

Use `references/reviewer_report_template.md` for formal reviews. For shorter triage, preserve the same categories but compress the prose.

Give required revisions as actions that the author could take:

- add or verify evidence
- narrow a claim
- move a claim from result to limitation
- clarify contribution
- separate background from validation
- add missing baseline, ablation, provenance, or reference checks

### 5. Optional Structured Outputs

When requested, create:

- `reviews/peer_review_report.md`
- `reviews/reviewer_attack_matrix.csv`
- `reviews/claim_evidence_findings.csv`

These files are advisory review artifacts. They are not final evidence for the author's claims.

## Recommendation Vocabulary

Use one of:

- `accept`
- `minor_revision`
- `major_revision`
- `reject_resubmit`
- `reject`
- `no_recommendation`

Use `no_recommendation` when the manuscript, venue, or review scope is too incomplete.

## Output Pattern

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

## Stop Conditions

Stop and report a blocker if:

- the manuscript or review target is missing
- the user asks for a review based on memory rather than supplied materials
- the requested factual verification requires sources that are not supplied and web/library access is prohibited
- the user asks you to fabricate reviewer consensus, citation support, or experimental findings
