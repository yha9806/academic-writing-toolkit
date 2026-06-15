# Agent-Native Productization Design

## Goal

Turn Academic Writing Toolkit from a capable repository of agent skills into a product that a new researcher can understand, install, and validate in one short session.

The first productization pass should make the project feel like an agent-native academic workflow product, not a loose collection of scripts, and should prepare the current release-governance work for a coherent `v0.3.0` release.

## Product Positioning

Academic Writing Toolkit is an agent-native, local-first skill pack for evidence-controlled academic writing workflows.

It is not a standalone SaaS application. Codex, Claude Code, Gemini CLI, Cursor, and compatible local agents are execution hosts. The toolkit provides the domain workflow, deterministic checks, schemas, templates, and repeatable project structure those agents use.

The product should be described as:

> A local-first agent skill pack for evidence-controlled literature review, thesis writing, citation auditing, reference verification, and release governance.

## Current Problem

The repository has a strong technical core:

- local agent skills for reading, note-taking, mapping, evidence review, integration, audit, release governance, style review, logic review, reference verification, progress, and export
- deterministic scripts and tests for several high-risk checks
- distribution surfaces for local skills, Codex plugin packaging, and a narrow ChatGPT App MCP server

The product gap is first-use clarity. A user can see that many capabilities exist, but they do not yet get a compact, guided path from clone to successful academic workflow output. This creates three risks:

- Interested users star the repository but do not become active users.
- Users confuse the local skill workflow, Codex plugin, and ChatGPT App MCP server.
- Release-governance looks like another skill rather than the closing step of an evidence-controlled workflow.

## Reference Products

The product should borrow patterns from adjacent tools without copying their product model.

| Reference | Useful Pattern | Toolkit Adaptation |
|-----------|----------------|--------------------|
| PaperQA2 | Local document search, grounded answers, source-aware workflow | Later: optional library Q&A. Now: emphasise local-first evidence control and source-backed outputs. |
| Elicit systematic reviews | Protocol, screening, extraction, synthesis, PRISMA-style audit trail | Later: screening packet. Now: make evidence-review outputs understandable as auditable review materials. |
| Rayyan | Clear systematic-review screening workflow and collaboration vocabulary | Later: include/exclude decision register. Now: use workflow-oriented docs instead of skill-only docs. |
| ASReview | Open-source, user-controlled, transparent AI-aided review process | Reinforce local-first, transparent files, deterministic checks, and no hidden data persistence. |
| Zotero | Researchers already start from a library and citation workflow | Later: Zotero import bridge. Now: document where reference verification fits beside existing reference managers. |
| Semantic Scholar | Research feeds and paper discovery | Later: candidate-paper queue. Now: avoid making discovery promises before the local workflow is strong. |
| GPT Researcher | One-command research report and citation-oriented output | Later: guided report generation. Now: provide a demo project and concrete output examples. |

## Product Surfaces

The public product should keep three surfaces distinct:

1. **Local agent skills** are the full product. They work when an agent can read and write the project folder.
2. **Codex plugin** is an installable distribution wrapper for the same local skills.
3. **ChatGPT App MCP server** is a narrower pasted-text tool surface. It should not be marketed as the full local thesis workflow.

This boundary should remain prominent in README and onboarding docs.

## P0 Productization Pack

The first implementation should be documentation- and example-focused.

### 1. README Positioning Rewrite

The README should lead with the product promise, then show the workflow and quickest path to a first result.

The top of the README should answer:

- What is this?
- Who is it for?
- Where does it run?
- What can I complete in 10 minutes?
- Which surface should I use: local skills, Codex plugin, or ChatGPT App?

### 2. Guided Demo Project

Add a small `examples/demo-project/` that a user can inspect and run without private data.

The demo should include:

- `CLAUDE.md`, `AGENTS.md`, and `GEMINI.md` style project config where appropriate
- one short sample chapter
- two or three generic reading notes
- a small BibTeX file
- an evidence-review packet sample
- a release-governance packet sample
- expected outputs documented in a README

The demo should avoid real private thesis material and avoid project-specific research claims. It should use generic fictional or public-domain-style examples.

### 3. Use-Case Guides

Add a small docs layer organized by user goals, not by skill internals:

- `docs/use-cases/write-literature-review.md`
- `docs/use-cases/audit-thesis-citations.md`
- `docs/use-cases/verify-references-before-submission.md`
- `docs/use-cases/prepare-release-governance-packet.md`
- `docs/use-cases/choose-product-surface.md`

These guides should link back to the canonical skill docs rather than duplicating all skill details.

### 4. Release Readiness For v0.3.0

PR #14 should be treated as the release candidate for `v0.3.0` after this productization pass lands.

The release should highlight:

- release-governance skill
- evidence-review positioning
- local agent documentation consistency
- verify-refs public migration guard
- demo project and use-case docs

The release checklist should verify:

- `make test`
- `make plugin-check`
- `make chatgpt-app-check`
- public-content audit
- plugin packaging state
- README and demo links

## Future Product Tracks

These are deliberately out of scope for P0, but they should guide the roadmap.

### Zotero Bridge

Support importing a Zotero-exported BibTeX or RIS file into toolkit scaffolds:

- reference verification input
- reading note templates
- source map starter
- evidence-review candidate source list

Avoid reading Zotero SQLite directly in the first version. Export-file import is safer and easier to document.

### Systematic Review Screening Packet

Add a local file-based workflow for screening:

- protocol criteria
- candidate records
- include/exclude decisions
- exclusion reasons
- conflict status
- PRISMA-lite counts

This should borrow from Elicit, Rayyan, and ASReview while staying local and auditable.

### Library Q&A

Optionally integrate with a local document index for source-backed Q&A. This should come after the demo and use-case docs because RAG adds dependency and expectation risk.

## Files In Scope For P0

- `README.md`
- `docs/use-cases/`
- `examples/demo-project/`
- `docs/skills/README.md`, only for cross-links
- `docs/plugin-publishing-checklist.md`, only if release notes need a pointer
- `docs/chatgpt-app-publishing.md`, only if surface boundaries need clarification
- `scripts/test.sh`, only for lightweight guards around demo/public docs

## Files Out Of Scope For P0

- new runtime dependencies
- Zotero API or SQLite integration
- PDF parsing engine changes
- RAG or vector search
- hosted SaaS surfaces
- ChatGPT App expansion to local project access
- major skill behaviour changes

## Acceptance Criteria

1. A new user can read the README and understand that the product is an agent-native local workflow, not a SaaS.
2. A new user can inspect `examples/demo-project/` and understand what a successful workflow output looks like.
3. Use-case docs explain common goals without duplicating all skill implementation details.
4. The local skills, Codex plugin, and ChatGPT App surfaces remain clearly separated.
5. The release-governance PR has a clear path to `v0.3.0`.
6. Public-content and test checks prevent private or project-specific material from entering the demo or docs.

## Risks

The main risk is over-expanding productization into feature development. Keep P0 focused on positioning, onboarding, examples, and release readiness. Zotero, systematic-review screening, and library Q&A are valuable, but they should be separate design and implementation cycles.

Another risk is over-promising evidence control. Documentation should state that deterministic scripts and release packet checks improve auditability, but they do not replace human academic judgement.
