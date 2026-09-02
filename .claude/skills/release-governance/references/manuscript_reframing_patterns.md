# Manuscript Reframing Patterns

Use this reference when a draft reads like an engineering report, module inventory, internal validation packet, or project status report rather than a scientific manuscript.

## Core Reframing Rule

Write around the scientific problem, not the implementation inventory.

Bad center of gravity:

```text
We built module A, module B, module C, reports, figures, and generative-model tests.
```

Better center of gravity:

```text
The field assumes X, but downstream use requires Y. This work defines the missing interface, evaluates the reliability gap, and shows how conservative routing changes what can be safely surfaced.
```

## Problem First, Modules Second

Before rewriting, force the manuscript into one sentence:

```text
This paper solves [specific reliability / evidence / workflow gap] between [upstream technical output] and [downstream scientific or operator-facing use].
```

For action-adjacent or human-facing AI manuscripts, prefer problem statements such as:

- Segmentation outputs are not automatically evidence objects.
- High mask metrics do not guarantee downstream task reliability.
- Uncertain perception should be routed, not silently converted into support.
- Reports and interfaces need explicit claim boundaries.
- Machine-readable records must not imply execution permission unless validated for that role.

## Contribution Shape

Avoid long module lists. Use a small contribution chain that explains why each piece exists.

Recommended structure:

1. Problem formulation: define the reliability or evidence gap.
2. Interface definition: convert raw outputs into structured evidence objects.
3. Bottleneck measurement: quantify where upstream metrics and downstream claims diverge.
4. Conservative routing: expose reliability-coverage trade-offs and review capture.
5. Bounded output: produce traceable reports or records without unsupported claims.

Each contribution should answer: what gap does this close, and what evidence supports it?

## Results Narrative

Do not present results as raw artifact counts or CSV-style metrics. Use result paragraphs that explain the transition:

- Perception metric: what the frozen model achieved.
- Direct conversion: what fails when outputs are treated as task evidence.
- Gate effect: how selective support changes agreement and coverage.
- Failure taxonomy: which bottleneck dominates.
- Bounded output audit: whether generated reports or records stayed within evidence.

Keep exact numbers in tables. In prose, translate audit-zero metrics into natural language when clearer:

```text
The audit detected no unsupported statements, contradictions, or prohibited action claims.
```

instead of

```text
unsupported rate 0.000, contradiction rate 0.000, prohibited rate 0.000
```

## Handling Low Values

Low support or coverage is not automatically a failure. Explain whether it means:

- the model missed evidence,
- geometry conversion failed,
- the gate correctly withheld weak evidence,
- a task is intentionally conservative,
- or the dataset lacks enough evaluable cases.

Use wording such as:

```text
Low supported coverage indicates conservative evidence routing under the frozen gate, not a direct measure of segmentation accuracy.
```

## Generative-Model Positioning

Do not let generative-model experiments steal the manuscript thesis unless they are the locked primary experiment.

Safe hierarchy:

- Primary result: deterministic, evidence-grounded, rule-based, or schema-validated workflow.
- Supplementary extension: frozen text-only or image-conditioned formatting tests.
- Future work: live clinical reporting, open-ended reasoning, or deployment validation.

Boundary phrases:

- format structured evidence only
- no new findings
- no geometry recomputation
- no gate override
- no action command
- no clinical or execution decision

Avoid phrases that imply clinical reasoning, autonomous operation, controller updates, or action recommendations unless explicitly negated as non-goals.

## Figure Design

Figures must carry the argument, not decorate the paper.

Useful figure roles:

1. Gap figure: show traditional pipeline versus proposed evidence-routed pipeline.
2. Dataset/evidence standard figure: show source images, annotation states, and evidence products.
3. Boundary figure: show what may pass through the interface and what is blocked.
4. Real-example figure: show actual cases where visual plausibility and task evidence diverge.

Keep small operational details in captions or supplement. Avoid tiny file names, internal IDs, dense JSON fragments, or floating checklist boxes inside figures.

### Figure Evidence Boundaries

Do not let a figure imply stronger evidence than the artifact supports.

- Use `panel`, `evidence construction panel`, `record-grounded replay panel`, or another function-specific label when the figure explains an evidence interface rather than showing raw empirical imagery.
- Avoid `schematic`, `synthetic`, and `proxy` in submission-facing captions when those words make the figure look like a placeholder or weaken confidence in the data source.
- Do not call a panel `raw microscopy`, `real replay`, or `ground truth` unless it is anchored to the actual locked artifact.
- State what the figure reads from: stored evidence fields, gated records, replay overlays, boundary cards, or raw image data.
- If no locked raw image panel exists, say the limitation in status notes or cover materials; do not smuggle it into a caption as if the figure were final empirical evidence.

## Table Design

Main tables should be compact and interpretation-led.

- Bold key locked values if journal style permits.
- Move wide per-case/per-item logs to supplement.
- Avoid raw CSV-style tables in the main manuscript.
- If a denominator is small, say so next to the value.
- If confidence intervals are descriptive only, label them as such.

### Main-Text Table Hardening

Main-text tables should be rewritten for the paper, not copied from reproducibility artifacts.

- Remove local paths, source columns, representative case IDs, filenames, JSON field names, and internal snake_case headers from main-text tables.
- Convert raw artifact tables into compact reader-facing summaries with title-case headers and interpretation columns.
- Keep only fields needed to answer the research question; move traceability fields to source maps, appendices, or reproducibility packages.
- Prefer p-column wrapping and fewer columns over `\resizebox{\linewidth}{!}`. A table that fits by becoming unreadable has not been fixed.
- Replace slash-heavy or unbreakable tokens when they cause layout issues, e.g. use `oocyte and oolemma geometry` rather than `oocyte/oolemma geometry`.
- Treat tables that render as tiny bands, illegible text, or dense horizontal strips as blockers even if LaTeX reports no overfull warning.

### PDF Artifact Hygiene

Before calling a manuscript PDF ready for review, verify the rendered PDF, not only the source files.

- Compile until the final log has no undefined citations, undefined references, or overfull table warnings.
- Render the PDF pages to images and inspect a contact sheet plus any table/figure-heavy pages at full size.
- Extract PDF text and scan for stale version markers, placeholder terms, local paths, `\textbackslash`, raw snake_case fields, and copied table-number prefixes.
- Use explicit required/forbidden marker checks for known review issues, such as required figure captions and forbidden placeholder wording.
- Keep final generated PDFs outside sync-sensitive paths when requested or when sync/permission problems are likely; use a temp or explicit release directory instead.

## Submission Readiness Gate

A draft can be scientifically improved but still not submission-ready. Check separately:

- author list and affiliations
- ethics approval or waiver statement
- funding
- competing interests
- CRediT roles
- data/code availability
- reference verification
- figure source provenance
- no placeholders in the main manuscript

Classify honestly:

- supervisor-review ready
- submission-prep ready
- submission ready

Do not call a paper submission-ready while metadata, ethics, data availability, or references remain unresolved.
