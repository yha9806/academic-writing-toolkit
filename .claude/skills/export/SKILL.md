---
name: export
description: Convert thesis chapters and reading notes from Markdown to Word (.docx) and package for submission. Use when preparing materials for supervisors or examiners.
disable-model-invocation: true
allowed-tools: Bash(python *), Read, Glob, Write
---

# /export — Document Export Skill

## Purpose

Convert thesis chapters and reading notes from Markdown to Word (.docx) format and package them into a ZIP archive for submission to supervisors or examiners. This skill is user-invoked only and will not be triggered automatically.

## Trigger Words

This skill activates on: `/export`. It is never invoked automatically by the model.

## Parameters

- `$ARGUMENTS[0]` -- **scope**: `chapters` | `notes` | `all` (default: `all`)
- `$ARGUMENTS[1]` -- **language filter**: `en-only` | `all` (default: `all`)

Examples:
- `/export chapters en-only` -- export only chapter files, skip files with significant CJK content
- `/export notes all` -- export only reading notes, include all languages
- `/export` -- export everything, all languages

## Workflow

1. **Check dependencies.** Verify that `pandoc` or `pypandoc` is available. If not, fall back to `python-docx` + `markdown`. Report which conversion method is being used.

2. **Run the conversion script.**
   ```
   python ${CLAUDE_SKILL_DIR}/scripts/convert_to_docx.py \
     --base-dir {project_root} \
     --output-dir {project_root}/export_output \
     --scope {scope} \
     --lang-filter {lang_filter}
   ```

3. **Report results.**
   ```
   ## Export Complete

   | Item | Value |
   |------|-------|
   | Files converted | {N} |
   | Files skipped (language filter) | {N} |
   | Output directory | {path} |
   | ZIP archive | {path} |
   | Total size | {size} |

   Conversion method: {pandoc | python-docx fallback}
   ```

## Constraints

1. **User-invoked only.** This skill has `disable-model-invocation: true` and must not run unless the user explicitly calls `/export`.
2. **No hardcoded paths.** All paths are derived from arguments or project root.
3. **No emoji** in output.
4. **Preserve formatting** as much as possible during conversion -- headings, tables, block quotes, inline code.
