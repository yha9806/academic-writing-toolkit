# /evidence-review - Evidence-Controlled Review

Run `/evidence-review` when a project needs a literature-gap review, review-paper plan, thesis literature-review section, or evidence synthesis with explicit claim controls.

This skill adds an evidence-control layer to the normal toolkit workflow:

```text
read -> note -> map -> evidence-review -> integrate -> audit -> style -> logic-review -> export
```

Use it to create:

- evidence matrices
- claim registers
- citation plans
- gap notes
- overclaim risk registers
- paragraph-level claim traceability
- citation usage audits
- overclaim audits
- assembly readiness checks

## Key Distinctions

The skill separates:

- direct domain evidence
- background evidence
- methodological support
- workflow or governance support
- candidate-only records
- metadata-only and abstract-only records
- unpublished work
- in-progress work

Candidate-only and abstract-only sources can guide gap tracking, but they must not support full-text claims. Adjacent-domain evidence can provide context or method rationale, but it cannot validate the target domain.

## Typical Use

```text
/evidence-review Build a gap map for Chapter 2 using local notes only. Do not search.
```

```text
/evidence-review Draft Section 2.3 only, then create claim traceability, citation usage audit, and overclaim audit.
```

```text
/evidence-review Run assembly readiness across Sections 2.1-2.8. Do not merge yet.
```

## Optional Check

The skill includes a lightweight helper:

```bash
python .claude/skills/evidence-review/scripts/check_review_package.py .
```

It checks common evidence-control directories and CSV readability. It does not replace expert review.

