# /export — Document Export

Convert thesis chapters and reading notes from Markdown to Word (.docx) and package into a ZIP archive.

---

## What It Does

`/export` takes your Markdown files and converts them to Word documents (.docx) suitable for submission to supervisors or examiners. It can export chapters only, notes only, or everything. The output is packaged into a ZIP archive.

This is the **only user-invoked-only skill** in the toolkit. It never runs automatically — you must explicitly call `/export`.

---

## When To Use

| Scenario | Command |
|----------|---------|
| Export everything | `/export` |
| Export chapters only | `/export chapters` |
| Export only English content | `/export chapters en-only` |
| Export reading notes | `/export notes` |

### Trigger Words

This skill activates **only** on: `/export`. It has `disable-model-invocation: true`, meaning the agent will never trigger it on its own.

---

## Parameters

| Parameter | Values | Default | Purpose |
|-----------|--------|---------|---------|
| Scope | `chapters` / `notes` / `all` | `all` | Which files to convert |
| Language filter | `en-only` / `all` | `all` | Skip files with significant CJK content |

### Parameter Combinations

```
/export                    → all files, all languages
/export chapters           → chapters only, all languages
/export chapters en-only   → chapters only, English only
/export notes              → reading notes only, all languages
/export notes en-only      → reading notes only, English only
/export all en-only        → all files, English only
```

---

## Internal Workflow

```
User says "/export chapters en-only"
│
├─ 1. Check dependencies
│     Preferred: pypandoc + working `pandoc` binary on PATH
│                (smoke-probed via pypandoc.get_pandoc_version())
│     Fallback: python-docx + markdown library
│     Report which method is being used
│
├─ 2. Run conversion script
│     python .claude/skills/export/scripts/convert_to_docx.py \
│       --base-dir {project_root} \
│       --output-dir {project_root}/export_output \
│       --scope chapters \
│       --lang-filter en-only
│
│     For each Markdown file:
│       - Parse Markdown → HTML (or AST)
│       - Convert to .docx preserving:
│         headings, tables, block quotes, inline code
│       - Apply language filter (skip if CJK ratio > threshold)
│
├─ 3. Package into ZIP
│     {project_name}_{date}.zip
│
└─ 4. Report results
```

---

## Practical Walkthrough

### Scenario: Exporting chapters for supervisor review

**You type:**
```
/export chapters en-only
```

**The agent produces:**

```
## Export Complete

| Item | Value |
|------|-------|
| Files converted | 8 |
| Files skipped (language filter) | 0 |
| Output directory | export_output/ |
| ZIP archive | export_output/thesis_2026-03-30.zip |
| Total size | 2.4 MB |

Conversion method: pandoc

### Files Included

| File | Source | Size |
|------|--------|------|
| ch1_introduction.docx | chapters/ch1_introduction.md | 45 KB |
| ch2_background.docx | chapters/ch2_background.md | 128 KB |
| ch3_conceptual_framework.docx | chapters/ch3_conceptual_framework.md | 156 KB |
| ch4_methodology.docx | chapters/ch4_methodology.md | 72 KB |
| ch5_judge_plus.docx | chapters/ch5_judge_plus.md | 142 KB |
| ch6_anchored.docx | chapters/ch6_anchored.md | 138 KB |
| ch7_practice.docx | chapters/ch7_practice.md | 68 KB |
| ch8_conclusion.docx | chapters/ch8_conclusion.md | 74 KB |
```

---

## Conversion Methods

| Method | Priority | Requirements | Quality |
|--------|----------|-------------|---------|
| pypandoc + pandoc | Preferred | `pip install pypandoc` AND `pandoc` binary on PATH | Best — handles tables, footnotes, cross-references |
| python-docx + markdown | Fallback | `pip install python-docx markdown` | Adequate — may lose complex table formatting |

The agent checks for the preferred method first (pypandoc calling the pandoc binary) and falls back to python-docx if either is unavailable. It reports which method was used so you know what to expect.

---

## The Language Filter

The `en-only` filter is designed for multilingual projects where some reading notes contain significant non-English content (Chinese, Japanese, etc.) that supervisors may not need.

**How it works:**
- Scans each file for CJK character ratio
- If the ratio exceeds the threshold, the file is skipped
- Skipped files are reported in the output

**When to use it:**
- Submitting to an English-language supervisor or examiner
- Generating a "chapters only" package where notes in other languages are irrelevant

**When NOT to use it:**
- Your thesis itself contains non-English content that should be preserved
- You want a complete backup of all project files

---

## The Conversion Script

The conversion script lives at `.claude/skills/export/scripts/convert_to_docx.py`. It handles:

- Markdown parsing (headings, bold, italic, code, tables, block quotes)
- Table conversion (Markdown pipe tables → Word tables)
- Heading hierarchy preservation (# → Heading 1, ## → Heading 2, etc.)
- Block quote formatting
- Output directory creation
- ZIP packaging

---

## Tips

1. **Run `/audit` before `/export`.** Export produces the files you submit. Make sure they're consistent first.

2. **Check the conversion method.** Pandoc produces the best results. If you see "python-docx fallback," consider installing pandoc for better table formatting.

3. **Use `chapters` scope for submissions.** Supervisors and examiners typically want chapters, not your reading notes.

4. **Use `en-only` selectively.** Only filter by language if your recipient specifically needs English-only content.

5. **The ZIP includes a timestamp.** Each export creates a dated archive, so you can maintain a history of submissions without overwriting.

---

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Exporting without auditing first | Run `/audit` before `/export`. Inconsistencies in the Word docs are harder to spot. |
| Expecting PDF output | `/export` produces .docx + ZIP. For PDF, use your own Markdown-to-PDF pipeline (e.g., `compile_pdf.py`). |
| Running `/export` expecting it to auto-trigger | This skill is user-invoked only. You must type `/export` explicitly. |
| Not checking which conversion method was used | If pandoc isn't installed, tables may look different in the fallback method. |

---

## Relationship to Other Skills

```
/audit ──► confirm consistency
   │
   ▼
/export ──► .docx files + ZIP archive
   │
   ▼
Submit to supervisor/examiner
```

`/export` is the final step in the pipeline. Everything before it — reading, noting, mapping, integrating, auditing — feeds into producing clean, consistent documents ready for submission.
