# Academic Writing Toolkit Plugin

This Codex plugin packages the academic-writing-toolkit skills for structured research and thesis writing workflows.

## Included Skills

- `read`: read academic PDFs page by page with structured output
- `note`: record source notes in the toolkit notes format
- `verify`: fact-check historical or empirical claims during reading
- `map`: map literature coverage against thesis chapters
- `evidence-review`: build evidence-controlled literature gap maps, claim registers, citation plans, and overclaim audits
- `integrate`: integrate completed reading notes into chapter drafts
- `thesis-control`: keep AI-assisted thesis edits bounded with spine cards, edit contracts, drift audits, human gates, and draft packet scaffolding
- `manuscript-reframe`: turn report-like drafts into paper-form scientific arguments with clear gap, contribution, result narrative, figure/table roles, and submission blockers
- `audit`: audit citation consistency, numbers, terminology, and cross-references
- `release-governance`: prepare release, rebuttal, artifact, and claim packets with ref-artifact-gate controls
- `style`: check and safely fix common US spellings when British English is required
- `logic-review`: review paragraph flow and transition issues
- `verify-refs`: validate BibTeX and reference metadata
- `human-eval-handoff-repair`: validate, repair, and map human-evaluation handoff packages and filled annotation CSVs
- `progress`: show reading, writing, and coverage progress
- `export`: export chapters and notes to Word documents

## Workspace Assumptions

The skills expect a writing project with these directories when relevant:

- `chapters/`
- `literature/`
- `literature/reading_notes/`
- `release/`
- `final_output/`
- `codex_outputs/` for generated handoff-repair reports when no output directory is specified

Script-backed skills use helper scripts bundled inside the individual skill directories, so the plugin can run without copying the repository-level `scripts/` directory into a user's project.

## Publishing Assets

The plugin manifest references local PNG assets under `assets/`:

- `icon.png`
- `logo.png`
- `screenshot-workflow.png`
- `screenshot-progress.png`

Run `make plugin-check` before publishing to validate the manifest, marketplace entry, bundled helpers, and asset paths.
