# ChatGPT App Design: Academic Writing Toolkit

## Decision

Build a `tool-only` ChatGPT App for the Academic Writing Toolkit while keeping the existing Codex plugin package intact.

This gives the project two distribution tracks:

- ChatGPT App: public MCP server submitted through OpenAI Platform Apps Manage.
- Codex plugin: local plugin package under `plugins/academic-writing-toolkit`, with official public distribution following OpenAI's app approval and publication flow.

Both surfaces use package version `0.3.0` for this release. The ChatGPT App server reads its version from `apps/chatgpt-academic-writing-toolkit/package.json`, and the test suite checks that it matches the Codex plugin manifest version.

## User Flows

1. A user pastes a thesis paragraph and asks for British English spelling checks.
2. A user pastes a chapter excerpt and reading note source line, then asks for Harvard citation consistency checks.
3. A user asks for paragraph-level logic review before revising a chapter.
4. A user pastes BibTeX and asks for deterministic reference validation.
5. A user asks ChatGPT to create a reading notes template for a source before taking notes.

## Tool Surface

- `audit_citations`: Checks pasted chapter text against pasted reading note source text using the repository citation auditor.
- `check_british_english`: Finds conservative US-to-British spelling replacements in pasted academic text.
- `review_paragraph_logic`: Flags short paragraphs and repeated adjacent transition words.
- `verify_bibtex_references`: Validates pasted BibTeX records offline.
- `create_reading_note_template`: Produces a standard reading notes Markdown template.

All tools are read-only from the user's perspective. They compute results from user-provided text, write only temporary local files during the tool call, do not persist user data, do not call external APIs, and do not mutate local thesis files.

## Surface Alignment

The ChatGPT App intentionally exposes a review-safe subset of the local Codex plugin:

| Capability | Codex plugin | ChatGPT App |
|------------|--------------|-------------|
| Read PDFs and create local notes | `/read`, `/note` | Not exposed; ChatGPT App has no local file access |
| Map and integrate sources into chapters | `/map`, `/integrate` | Not exposed; requires workspace files |
| Evidence-controlled review synthesis | `/evidence-review` | Not exposed; requires local notes and project artefacts |
| Release and human-evaluation packet governance | `/release-governance`, `/human-eval-handoff-repair` | Not exposed; requires local refs, assets, package files, or annotation CSVs |
| Citation audit | `/audit` | `audit_citations` for pasted text and source lines |
| British English check | `/style` | `check_british_english` for pasted text |
| Paragraph logic review | `/logic-review` | `review_paragraph_logic` for pasted text |
| BibTeX/reference validation | `/verify-refs` | `verify_bibtex_references` offline only |
| Reading note scaffold | `/note` template workflow | `create_reading_note_template` |
| Progress and export | `/progress`, `/export` | Not exposed; requires local workspace files |

This is functional alignment by workflow, not one-to-one feature parity. The plugin remains the full local workspace product; the ChatGPT App is the safe hosted review surface for user-provided text.

## Review Constraints

- No ChatGPT widget in v1.
- No authentication in v1.
- No direct local filesystem access from ChatGPT.
- No online metadata verification in v1.
- Every tool must declare explicit `readOnlyHint`, `openWorldHint`, and `destructiveHint` annotations.
- Every tool should declare an `outputSchema`.
- Submission metadata must include at least five positive test cases and three negative test cases.

## Implementation Plan

1. Create an isolated Node MCP server under `apps/chatgpt-academic-writing-toolkit`.
2. Wrap existing deterministic Python scripts through a temporary project directory.
3. Add Node tests for the five user-facing tool helpers.
4. Register the five tools on `/mcp` using the Apps SDK/MCP server pattern.
5. Generate `chatgpt-app-submission.json` from the implemented tool descriptors.
6. Add a Make target for the ChatGPT app checks.

## Deployment Note

OpenAI submission requires a public MCP URL, not a localhost endpoint. This repo prepares the app and submission JSON; a hosting target must provide the final HTTPS `/mcp` URL before dashboard submission.
