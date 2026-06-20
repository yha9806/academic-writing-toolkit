---
name: manuscript-reframe
description: Reframe academic manuscript drafts that read like engineering reports, module inventories, internal validation packets, or system notes into paper-form scientific arguments with clear gap, contribution chain, results narrative, figure/table roles, AI-assisted component boundaries, and submission-readiness blockers.
allowed-tools: Read, Glob, Grep, Edit, Write, Bash
---

# /manuscript-reframe - Scientific Manuscript Reframing

## Purpose

Turn a technically valid but report-like manuscript into a scientific paper argument. Use this when a draft contains many modules, raw tables, internal artifact language, scattered figures, or exploratory AI/report-generation material but the scientific gap and contribution are not yet crisp.

## Trigger Words

This skill activates on: `manuscript reframe`, `paper form`, `too much like a report`, `gap and contribution`, `scientific framing`, `journal framing`, `submission clean`, `methods paper`, `/manuscript-reframe`.

## Core Rule

Write around the scientific problem, not the implementation inventory.

Before editing, force the draft into one sentence:

```text
This paper solves [specific reliability / evidence / workflow gap] between [upstream technical output] and [downstream scientific or operator-facing use].
```

If the sentence cannot be written, do not rewrite sections yet. First produce a gap-and-contribution diagnosis.

## Workflow

### 1. Locate The Current Draft And Evidence Anchors

Inspect manuscript sources, figures, tables, supplementary files, result summaries, reference files, and revision reports. Identify which artifacts are canonical and which are exploratory.

Create a short working note with:

- manuscript source path
- intended venue or article type
- canonical result artifacts
- exploratory-only artifacts
- forbidden or overclaim risks
- unresolved submission metadata

### 2. Diagnose The Paper Spine

Check whether the Introduction answers:

1. What do existing approaches output?
2. Why is that output insufficient for downstream use?
3. What gap does this paper evaluate or close?
4. What is the proposed interface, workflow, or method?
5. What evidence shows the gap and the method effect?

Prefer gap forms such as:

- Perception outputs are not automatically evidence objects.
- Segmentation metrics do not guarantee downstream task reliability.
- Uncertain perception should be routed rather than silently converted into support.
- Reports and interfaces need explicit claim boundaries.
- Machine-readable records must not imply execution permission unless validated for that role.

### 3. Rebuild Contributions As A Chain

Avoid module lists. Use a small contribution chain:

1. Problem formulation: define the reliability, evidence, or workflow gap.
2. Interface definition: convert raw outputs into structured evidence objects.
3. Bottleneck measurement: quantify where upstream metrics and downstream claims diverge.
4. Conservative routing: expose reliability-coverage trade-offs and review capture.
5. Bounded output: produce traceable reports or records without unsupported claims.

Every contribution should answer: what gap does this close, and what evidence supports it?

### 4. Rewrite Results As A Narrative Transition

Do not present Results as raw artifact counts. Use paragraphs that explain the transition:

- perception metric: what the frozen model or upstream system achieved
- direct conversion: what fails when outputs are treated as downstream evidence
- gate/routing effect: how selective support changes agreement and coverage
- failure taxonomy: which bottleneck dominates
- bounded output audit: whether reports or records stayed within evidence boundaries

Keep exact values in tables. In prose, translate audit-zero metrics into natural language when clearer:

```text
The audit detected no unsupported statements, contradictions, or prohibited action claims.
```

Do not write prose that sounds like a metric dump:

```text
unsupported rate 0.000, contradiction rate 0.000, prohibited rate 0.000
```

### 5. Explain Low Values Honestly

Low support, low coverage, or small denominators are not automatically failures. Identify what they mean:

- model evidence was missing
- geometry conversion failed
- the gate correctly withheld weak evidence
- the task is intentionally conservative
- the dataset has few evaluable cases

Use language such as:

```text
Low supported coverage indicates conservative evidence routing under the frozen gate, not a direct measure of segmentation accuracy.
```

### 6. Keep Generative Components In Their Proper Role

Do not let language-model or multimodal generative experiments steal the manuscript thesis unless they are the locked primary experiment.

Safe hierarchy:

- Primary result: deterministic, evidence-grounded, rule-based, or schema-validated workflow.
- Supplementary extension: frozen text-only or image-conditioned formatting tests.
- Future work: live domain reporting, open-ended reasoning, or deployment validation.

Boundary phrases:

- format structured evidence only
- no new findings
- no geometry recomputation
- no gate override
- no action command
- no domain or execution decision

Flag or remove wording that implies domain reasoning, autonomous operation, controller updates, or action recommendations unless explicitly negated as non-goals.

### 7. Make Figures And Tables Carry The Argument

Assign each main figure a job:

1. Gap figure: traditional pipeline versus proposed evidence-routed pipeline.
2. Dataset/evidence standard figure: source images, annotation states, and evidence products.
3. Boundary figure: what may pass through the interface and what is blocked.
4. Real-example figure: actual cases where visual plausibility and task evidence diverge.

Move tiny operational details, raw IDs, file names, JSON fragments, and long checklists to captions or supplement.

Main tables should be compact and interpretation-led:

- move per-case/per-item logs to supplement
- avoid raw CSV-style tables in the main manuscript
- label small denominators explicitly
- mark descriptive intervals as descriptive
- bold key locked values only if journal style permits

### 8. Check Submission Readiness Separately

Do not call a draft submission-ready while metadata or governance fields are unresolved. Check:

- author list and affiliations
- corresponding author details
- ethics approval or waiver
- funding
- competing interests
- CRediT roles
- data/code availability
- reference verification
- figure provenance
- no placeholders in the main manuscript

Classify the draft honestly:

- supervisor-review ready
- submission-prep ready
- submission ready

## Output Pattern

For an audit-only task, produce:

- paper-spine diagnosis
- unclear gap/contribution points
- report-like passages
- figure/table issues
- overclaim risks
- submission blockers
- recommended edit plan

For an edit task, apply local edits in this order:

1. title and abstract thesis
2. Introduction gap and contribution chain
3. Methods section hierarchy
4. Results narrative and table captions
5. Discussion/conclusion boundary language
6. figure captions and table placement
7. submission metadata notes

## Stop Conditions

Stop and report a blocker if:

- locked numbers or evidence sources are missing
- raw data are unavailable for requested analyses
- references cannot be verified but are needed for central claims
- user asks to claim domain, causal, deployment, or outcome validity without direct evidence
- author-, ethics-, funding-, or data-availability fields are required for submission but unavailable
