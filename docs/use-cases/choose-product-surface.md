# Choose The Right Product Surface

Academic Writing Toolkit has two enforcement modes since the v0.1 rebuild.
The vocabulary is deliberate: a constraint is either **Enforced** (a guard
actively blocks the operation and CI proves the denial) or **Advisory**
(instruction text the model may follow imperfectly). There is no third
state.

## AWT dsh App (Enforced)

Use this for the full thesis workflow with enforcement. `awt init` creates
the workspace, `awt install-profile` installs the `awt-headless` profile,
and every daily-loop constraint — notes-before-chapters, quote integrity,
page budgets, edit-contract scope, 3-strike escalation — is a typed guard
denial or an explicit author approval recorded as immutable harness events.
Profile boot itself refuses a directory that is not an AWT workspace.

Start here for real thesis work. See the README quickstart and
`guards/README.md` for exact enforcement semantics, including what each
guard deliberately does not do.

## Agent Skills (Advisory)

Use this when you want the same 9-skill catalogue inside Claude Code,
Codex, Gemini CLI, or any Agent-Skills-compatible host, without the
enforcement layer. The skills are the identical files (`.claude/skills/`,
linked at `.agents/skills/`); the constraints they describe are advisory
because no guard is mounted.

## Quick Rule

If a constraint being violated should stop the operation, use the dsh app.
If you only want the workflow guidance, the skills alone are enough — and
nothing in them pretends to be enforcement.

## Long-document Workbench (Advisory review)

The optional [`workbench/` component](../../workbench/README.md) integrates
the thesis-scale workflow: PDF/DOCX import, bounded provider requests,
chapter coverage, revision reuse, resumable page comparison and local
submission checks. Its schema, quotation, hash and workload-budget checks
are local controls. Its review suggestions are advisory and it does not
mount dsh's manuscript guards or harness approval events.

Use it for inspecting long documents and candidate revisions. Use dsh when
the workflow requires its notes, page-budget and edit-contract enforcement.
The same source files can be selected explicitly; there is no automatic
conversion of Workbench review results or page checks into dsh approvals.

## Retired surfaces

The original Workbench wheel, packaged Codex plugin, and ChatGPT App were
decommissioned with the v0.1 rebuild; the last release carrying them is
[v0.5.0](https://github.com/yha9806/academic-writing-toolkit/releases/tag/v0.5.0).
The [2026-09-05 integration](../specs/2026-09-05-long-document-integration.md)
restores the long-document Workbench as an optional development package;
the plugin package and ChatGPT App remain retired.
