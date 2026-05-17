---
name: evidence-review
description: Build evidence-controlled literature reviews and gap maps with source-status labels, claim registers, citation-role plans, traceability tables, and overclaim audits. Use when drafting or auditing review papers, thesis literature reviews, scoping reviews, or evidence syntheses where adjacent-domain evidence, candidate records, unpublished work, and unsupported claims must be kept separate.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
---

# /evidence-review - Evidence-Controlled Review Skill

## Purpose

Create literature-review and review-paper workflows that are traceable from evidence to claim. This skill extends the toolkit's read-note-map-integrate pipeline with stricter evidence-status control, gap mapping, citation-role planning, paragraph-level claim traceability, and overclaim auditing.

## Trigger Words

This skill activates on: `evidence review`, `gap review`, `gap map`, `claim traceability`, `overclaim audit`, `review paper`, `scoping review`, `systematic narrative review`, `/evidence-review`.

## Core Rules

1. Keep the central review scope explicit.
2. Separate direct evidence, background evidence, methodological support, workflow/governance support, candidate-only records, unpublished work, and in-progress work.
3. Do not fabricate references, DOI, PMID, sample size, venue, abstracts, results, or claims.
4. Do not treat candidate-only, metadata-only, abstract-only, generated-stub, or manual-review records as full-text evidence.
5. Do not treat adjacent-domain evidence as direct validation of the target domain.
6. Preserve uncertainty and boundary language.
7. Use the project's citation style or placeholder convention. If the project uses review placeholders, preserve `[CITE: CitationKey]`.
8. Draft section by section. Do not assemble a final chapter or paper until section-level controls are clean.

## Workflow

### 1. Scope And Boundary Setup

Create a short scope statement with:

- central review question
- direct evidence domain
- adjacent background domains
- methodological support domains
- excluded topics
- key overclaim risks

### 2. Evidence Inventory

Inspect existing project files before drafting. Common locations include:

- `literature/reading_notes/`
- `summaries/`
- `evidence/`
- `outputs/references_master.csv`
- `outputs/search_log.md`

Classify each source using `references/evidence_status_schema.md`.

### 3. Gap Map

Create or update:

- `evidence/evidence_matrix.csv`
- `evidence/claim_register.csv`
- `evidence/citation_plan.csv`
- `evidence/remaining_gap_notes.csv`
- `evidence/overclaim_risk_register.csv`

Map each source to what it can legitimately support. If direct evidence is sparse, state that as a gap instead of filling the gap with background literature.

### 4. Section Drafting

For each section:

1. Create an input-check report.
2. Draft first-pass prose.
3. Create paragraph-level claim traceability.
4. Create citation usage audit.
5. Create overclaim audit.
6. Create revision notes.
7. Revise into second-pass prose only after controls are clean.

### 5. Assembly Readiness

Before merging sections:

- check every section has compatible draft maturity
- check traceability and audit files exist
- check CSV files import cleanly
- audit cross-section flow
- audit repetition and boundary-language duplication
- audit integrated citation consistency
- audit integrated overclaim risks

### 6. Export Or Sharing

Use `/export` only after the review has passed assembly and overclaim checks. Export is packaging, not revision.

## Reading Notes Bridge

When the review starts from source reading, use the template in `references/reading_notes_template.md`. Every source note should record:

- citation key or provisional source ID
- source provenance
- evidence status
- relevance
- key arguments
- detailed notes
- review connections
- claim candidates
- limitations and boundary cautions
- follow-up questions

## Output Templates

Use `references/review_workflow_templates.md` for recommended CSV columns and report structures.

Minimum section controls:

- `reports/<section>_input_check.md`
- `docs/<section>_first_pass_draft.md` or `chapters/<section>_first_pass_draft.md`
- `evidence/<section>_claim_traceability.csv`
- `evidence/<section>_citation_usage_audit.csv`
- `reports/<section>_overclaim_audit.md`
- `reports/<section>_revision_notes.md`

## Optional Package Check

If Python is available, run:

```bash
python {skill_dir}/scripts/check_review_package.py <project_root>
```

This checks common directories, common evidence-control files, and CSV readability. It does not judge scientific validity.

## Stop Conditions

Stop and report a blocker if:

- the user prohibits searching but the requested claim requires new evidence
- only candidate or abstract evidence exists for a central claim
- a clinical, causal, deployment, or outcome claim lacks direct evidence
- unpublished or in-progress work cannot be separated from published literature
- citation provenance is missing for a source being used as evidence

