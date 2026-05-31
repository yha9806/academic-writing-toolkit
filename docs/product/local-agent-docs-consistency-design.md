# Local Agent Documentation Consistency Design

## Goal

Make the local agent product surface easier to trust and understand by aligning user-facing documentation with the current skill set and by adding a small regression guard against future documentation drift.

This pass targets local agent users first. It does not add new skills, change academic-writing behaviour, or expand the ChatGPT App surface.

## Current Problem

The toolkit has a coherent local workflow, but the documentation is not equally coherent across entry points. The root README and skills index describe the current pipeline, while some setup guides still describe an older skill count and omit newer governance skills. The ChatGPT App is also a narrower pasted-text tool surface, but that difference is not prominent enough for users choosing an entry point.

The result is product friction: a user can run the toolkit, but may not know which surface is complete, which documentation is canonical, or whether newer skills are meant to be part of the main local workflow.

## Users

Primary user: a local agent user working in Claude Code, Codex, Gemini CLI, OpenClaw, or a compatible host with access to the repository files.

Secondary user: a maintainer reviewing whether public docs match the installed skill set.

Non-goal: making the ChatGPT App equivalent to the local agent workflow.

## Design

### Canonical Skill Inventory

Use `docs/skills/README.md` as the canonical public skill index for user-facing setup docs. It should list the current local agent skills and their guide pages.

Setup guides should avoid stale fixed counts when the exact number is not necessary. When a count is useful, it must be derived from the same current inventory and checked by tests.

### Surface Boundary Wording

Add a short root README section that distinguishes:

- Local agent skills: full file-based workflow with project directories, notes, chapters, evidence controls, release packets, and export.
- ChatGPT App MCP server: pasted-text checks and template generation through temporary files only.
- Codex plugin package: distribution wrapper for the local skills.

This prevents an implicit promise that the ChatGPT App can read or write a user's local thesis project.

### Setup Guide Alignment

Update local-agent setup guides so they reflect the same workflow vocabulary:

- `read`, `note`, `verify`, `map`
- `evidence-review`
- `integrate`
- `audit`
- `release-governance`
- `style`, `logic-review`, `verify-refs`
- `progress`, `export`

The guides should keep their runtime-specific setup details but share the same product description.

### Regression Guard

Add a focused test to `scripts/test.sh` that fails when public setup docs drift behind the current local skill set. The guard should check for:

- no stale "11 public academic writing skills" wording
- presence of `evidence-review` and `release-governance` in local-agent setup docs
- root README explicitly distinguishing local skills from the ChatGPT App pasted-text surface

The test should stay lightweight and deterministic. It should not inspect network state, GitHub state, or external package metadata.

## Files In Scope

- `README.md`
- `docs/setup-claude-code.md`
- `docs/setup-codex-cli.md`
- `docs/setup-gemini-cli.md`
- `docs/setup-openclaw.md`
- `docs/skills/README.md`
- `plugins/academic-writing-toolkit/README.md`, only if wording needs alignment
- `scripts/test.sh`

## Files Out Of Scope

- Skill behaviour and skill scripts
- ChatGPT App tools
- Plugin publishing metadata beyond wording consistency
- Example projects and guided tutorials
- Workflow readiness or next-action automation

## Acceptance Criteria

1. Public setup docs no longer mention the stale 11-skill inventory.
2. Local-agent setup docs mention both `evidence-review` and `release-governance`.
3. The root README clearly says the ChatGPT App is a narrower pasted-text tool surface, while local skills are the full file-based workflow.
4. `make test` includes a regression guard for this documentation consistency.
5. `make test`, `make plugin-check`, `python3 scripts/audit-public-content.py --base-dir .`, and the public leakage scan pass.

## Risks

The main risk is over-expanding this pass into onboarding redesign. Keep this change narrowly focused on consistency and product boundary clarity. Sample projects, guided tutorials, and workflow readiness should be separate follow-up work.
