# C-emergency Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 10 bugs (2 R2 BLOCKERs + 1 NEW BLOCKER + 3 R2 MAJORs + 2 NEW MAJORs + 2 R2 MINORs) and 1 adjacent doc bug in academic-writing-toolkit, plus extend `scripts/test-foolproofing.sh` with 8 grep-based regression tests (T11–T18) so the same drift cannot silently re-appear.

**Architecture:** TDD per bug. Each task: add the regression test (or apply the fix where automated test isn't possible per spec §5), run it to confirm it fails on current state, apply the fix, run it to confirm it passes, commit. Tasks ordered to keep commits small and self-contained — multi-file fixes that share a regression test commit together; bugs that share a file are sequenced (not batched) for cleaner blame.

**Tech Stack:** Bash (test harness using D's `lib.sh` helpers `pass` / `fail` / `die`), Python 3.8+ (compat fix), Markdown edits.

**Spec:** `docs/superpowers/specs/2026-04-27-c-emergency-design.md` — refer for design rationale.

---

## File Structure

| File | Touched by tasks | Responsibility after fix |
|---|---|---|
| `.claude/skills/export/SKILL.md` | T1 (Bug #1), T4 (Bug #2-docs), T5 (Bug #4) | Skill instructions for `/export`; cwd-relative path; honest backend description; correct output dir |
| `.claude/skills/export/scripts/convert_to_docx.py` | T2 (Bug #8), T3 (Bug #2) | Python 3.8-compatible; pandoc preflight via `get_pandoc_version()`; try/except runtime fallback |
| `.claude/skills/map/SKILL.md` | T8 (Bug #7), T10 (Bug #9) | Stance-only example matrix; `Write` in allowed-tools |
| `.claude/skills/verify/SKILL.md` | T10 (Bug #10) | `Read` in allowed-tools |
| `docs/skills/08-export.md` | T1 (Bug #1), T4 (Bug #2-docs), T5 (Bug #4), T6 (Bug #6) | Same skill prose as SKILL.md but at user-doc layer |
| `docs/skills/04-map.md` | T8 (Bug #7) | Stance-only matrix and intro |
| `docs/skills/02-note.md` | T8 (Bug #7) | Stance-only "standard types" list |
| `docs/setup-claude-code.md`, `docs/setup-codex-cli.md`, `docs/setup-gemini-cli.md`, `docs/setup-openclaw.md` | T9 (Bug #5), T11 (R6 OpenClaw only) | Truthful `/export` capability description; OpenClaw points at CLAUDE.md not AGENTS.md |
| `README.md` | T7 (Bug #3) | 3-state status enum |
| `.cursor/rules/academic-writing.mdc` | T7 (Bug #3) | 3-state status enum, no `revisiting` |
| `scripts/test-foolproofing.sh` | T1, T2, T5, T6, T7, T8, T9, T10 | Append T11–T18 |

Spec §7 lists 14 files / ~70-90 lines of edit volume; this plan implements that exactly.

---

## Task 1: Bug #1 — `${CLAUDE_SKILL_DIR}` hardcode + T11 regression

**Files:**
- Modify: `.claude/skills/export/SKILL.md:34` (workflow code block) + add prose line above step 1
- Modify: `docs/skills/08-export.md:61` (workflow code block)
- Modify: `scripts/test-foolproofing.sh` (append T11)

- [ ] **Step 1: Append T11 to `scripts/test-foolproofing.sh`**

Find the line near the bottom (around line 184) that reads:
```bash
run_test "T2  symlink corruption + repair"        test_T2
```

Add the T11 test function above the runners section (around line 158, after `test_T10`):

```bash
# Match T2-T10 harness style: function returns 0/1; run_test handles printing.
test_T11() {
    # No CLAUDE_SKILL_DIR references in skill prose or user docs
    ! grep -rq 'CLAUDE_SKILL_DIR' "$REPO_ROOT/.claude/skills/" "$REPO_ROOT/docs/skills/"
}
```

Add the runner line at the bottom (after `run_test "T10 ...`):

```bash
run_test "T11 no CLAUDE_SKILL_DIR in skill files" test_T11
```

- [ ] **Step 2: Run T11; expect FAIL**

```bash
bash scripts/test-foolproofing.sh
```

Expected: `T11 no CLAUDE_SKILL_DIR in skill files` reports FAIL with message about Bug #1. Other tests still pass.

- [ ] **Step 3: Fix `.claude/skills/export/SKILL.md`**

Replace:
```
2. **Run the conversion script.**
   ```
   python ${CLAUDE_SKILL_DIR}/scripts/convert_to_docx.py \
     --base-dir {project_root} \
     --output-dir {project_root}/export_output \
     --scope {scope} \
     --lang-filter {lang_filter}
   ```
```

with:
```
   **Run from the project root.**

2. **Run the conversion script.**
   ```
   python .claude/skills/export/scripts/convert_to_docx.py \
     --base-dir {project_root} \
     --output-dir {project_root}/export_output \
     --scope {scope} \
     --lang-filter {lang_filter}
   ```
```

(The `export_output` → `final_output` change happens in Task 5; leave it alone for now.)

- [ ] **Step 4: Fix `docs/skills/08-export.md`**

Find the workflow code block around line 61:
```
├─ 2. Run conversion script
│     python ${CLAUDE_SKILL_DIR}/scripts/convert_to_docx.py \
│       --base-dir {project_root} \
│       --output-dir {project_root}/export_output \
```

Change `${CLAUDE_SKILL_DIR}/scripts/convert_to_docx.py` to `.claude/skills/export/scripts/convert_to_docx.py`.

- [ ] **Step 5: Run T11; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T11 passes. All other tests (T2–T10) still pass.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/export/SKILL.md docs/skills/08-export.md scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): replace ${CLAUDE_SKILL_DIR} hardcode with cwd-relative path

Bug #1 (R2 BLOCKER). On non-Claude platforms (Codex, Gemini, OpenClaw)
${CLAUDE_SKILL_DIR} is undefined, so /export crashes. Use the cwd-relative
path matching sub-project D's convention. Skill prose now says "Run from
the project root."

Adds T11 regression test (no CLAUDE_SKILL_DIR in skill files).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Bug #8 — Python 3.8 compat + T17 regression

**Files:**
- Modify: `.claude/skills/export/scripts/convert_to_docx.py` (top of file)
- Modify: `scripts/test-foolproofing.sh` (append T17)

- [ ] **Step 1: Append T17 to `scripts/test-foolproofing.sh`**

Add the T17 test function (after `test_T11`):

```bash
# Match T2-T10 harness style: function returns 0/1; run_test handles printing.
test_T17() {
    local script="$REPO_ROOT/.claude/skills/export/scripts/convert_to_docx.py"
    grep -q '^from __future__ import annotations$' "$script" || return 1
    if command -v python3.8 >/dev/null 2>&1; then
        python3.8 -c "import importlib.util as u; s=u.spec_from_file_location('m','$script'); m=u.module_from_spec(s); s.loader.exec_module(m)" 2>/dev/null || return 1
    fi
    return 0
}
```

Add runner line:

```bash
run_test "T17 Python 3.8 import safety"           test_T17
```

- [ ] **Step 2: Run T17; expect FAIL**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T17 reports FAIL with "missing 'from __future__ import annotations'".

- [ ] **Step 3: Fix `convert_to_docx.py`**

The current top of file (after the docstring) is:
```python
"""Convert thesis chapters and reading notes from Markdown to Word (.docx).
...
"""

import argparse
import os
```

Insert `from __future__ import annotations` as the first import:

```python
"""Convert thesis chapters and reading notes from Markdown to Word (.docx).
...
"""
from __future__ import annotations

import argparse
import os
```

Use Edit tool: find `\n\nimport argparse\n` in the file and replace with `\nfrom __future__ import annotations\n\nimport argparse\n`. Or anchor on the docstring closing `"""`.

- [ ] **Step 4: Run T17; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T17 passes (grep tier). If `python3.8` is on PATH, the smoke import also succeeds.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/export/scripts/convert_to_docx.py scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): make convert_to_docx.py import-safe on Python 3.8

Bug #8 (NEW BLOCKER, surfaced by codex audit). PEP 585 generic syntax
(tuple[int, int]) at lines 205, 214, 223 fails at import on Python 3.8
with TypeError: 'type' object is not subscriptable. Add
`from __future__ import annotations` to postpone evaluation; no
behavioral change on 3.9+.

Adds T17 regression test (grep + optional 3.8 smoke import).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Bug #2 — pypandoc preflight + runtime fallback

**Files:**
- Modify: `.claude/skills/export/scripts/convert_to_docx.py:25-45` (preflight block) + `:79-89` (convert_file try/except) + `:243-258` (create_cover try/except)

No regression test — Bug #2 acceptance is manual smoke per spec §4.2 (deferred to sub-project A).

- [ ] **Step 1: Replace the entire backend-detection block (lines 23-45)**

Current `convert_to_docx.py:23-45` (the section between the comment headers `# Conversion backends` and `# Language detection`):
```python
# ---------------------------------------------------------------------------
# Conversion backends
# ---------------------------------------------------------------------------

USE_PANDOC = False

try:
    import pypandoc

    USE_PANDOC = True
except ImportError:
    pass

if not USE_PANDOC:
    try:
        import markdown
        from docx import Document
        from docx.shared import Inches, Pt
    except ImportError:
        sys.exit(
            "Error: Neither pypandoc nor (python-docx + markdown) are installed.\n"
            "Install one of:\n"
            "  pip install pypandoc\n"
            "  pip install python-docx markdown"
        )
```

Replace the entire block with:
```python
# ---------------------------------------------------------------------------
# Conversion backends
# ---------------------------------------------------------------------------

USE_PANDOC = False

try:
    import pypandoc
    # Smoke probe: get_pandoc_version() shells out to `pandoc --version`
    # internally and raises if the binary is missing or broken
    # (Snap isolation, missing libs, broken wrapper).
    pypandoc.get_pandoc_version()
    USE_PANDOC = True
except (ImportError, OSError, RuntimeError):
    pass

# Always try to import python-docx — needed both as primary path when
# USE_PANDOC=False, and as runtime fallback when pypandoc fails on a
# specific file (see convert_file / create_cover try/except below).
HAS_DOCX = False
try:
    import markdown
    from docx import Document
    from docx.shared import Inches, Pt
    HAS_DOCX = True
except ImportError:
    pass

if not USE_PANDOC and not HAS_DOCX:
    sys.exit(
        "Error: No conversion backend available.\n"
        "  - pypandoc is installed but `pandoc` binary is missing/broken on PATH.\n"
        "  - python-docx + markdown fallback is also missing.\n"
        "Install one of:\n"
        "  pip install pypandoc       (also requires `pandoc` binary on PATH)\n"
        "  pip install python-docx markdown"
    )
```

Key changes from the original:
- New `pypandoc.get_pandoc_version()` smoke probe.
- Catch `OSError` and `RuntimeError` (raised when binary is missing/broken) in addition to `ImportError`.
- python-docx imports moved out of the `if not USE_PANDOC` branch — always attempted, gated by `HAS_DOCX` flag.
- Hard exit only when BOTH backends are missing.

- [ ] **Step 2: Add runtime fallback in `convert_file()`**

Current `convert_to_docx.py:79-89`:
```python
def convert_file(src: Path, dst: Path) -> None:
    """Convert a single Markdown file to .docx."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    if USE_PANDOC:
        pypandoc.convert_file(
            str(src),
            "docx",
            outputfile=str(dst),
            extra_args=["--wrap=none"],
        )
    else:
        _convert_with_docx(src, dst)
```

Replace with:
```python
def convert_file(src: Path, dst: Path) -> None:
    """Convert a single Markdown file to .docx."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    if USE_PANDOC:
        try:
            pypandoc.convert_file(
                str(src),
                "docx",
                outputfile=str(dst),
                extra_args=["--wrap=none"],
            )
            return
        except (OSError, RuntimeError) as exc:
            print(f"  Warning: pandoc failed on {src.name}: {exc}; falling back to python-docx")
    _convert_with_docx(src, dst)
```

(The python-docx imports were already hoisted in Step 1 so `_convert_with_docx` works whether or not pandoc was the primary backend.)

Also update `_convert_with_docx()` to assert `HAS_DOCX` (in case pandoc-only setups end up here via the fallback path with `HAS_DOCX=False`). Find the function definition and add a guard at the top:

```python
def _convert_with_docx(src: Path, dst: Path) -> None:
    """Fallback converter using python-docx + markdown."""
    if not HAS_DOCX:
        raise RuntimeError(
            "python-docx fallback not available; install python-docx + markdown"
        )
    md_text = src.read_text(encoding="utf-8")
    ...  # rest of function unchanged
```

- [ ] **Step 3: Add runtime fallback in `create_cover()`**

Current `convert_to_docx.py:243-258` is inside `create_cover()` and uses the same `if USE_PANDOC: ... else: ...` pattern. Wrap the pypandoc call in try/except identically:

```python
def create_cover(metadata: dict, out: Path) -> Path:
    """Create a simple cover page .docx with thesis metadata."""
    dst = out / "00_cover.docx"
    dst.parent.mkdir(parents=True, exist_ok=True)

    if USE_PANDOC:
        try:
            cover_md = f"# {metadata.get('title', 'Thesis')}\n\n"
            cover_md += f"**Author**: {metadata.get('author', 'Unknown')}\n\n"
            cover_md += f"**Date**: {metadata.get('date', datetime.now().strftime('%Y-%m-%d'))}\n\n"
            cover_md += f"**Institution**: {metadata.get('institution', '')}\n\n"
            if metadata.get("abstract"):
                cover_md += f"## Abstract\n\n{metadata['abstract']}\n"
            tmp = out / "_cover_tmp.md"
            tmp.write_text(cover_md, encoding="utf-8")
            pypandoc.convert_file(str(tmp), "docx", outputfile=str(dst))
            tmp.unlink()
            return dst
        except (OSError, RuntimeError) as exc:
            print(f"  Warning: pandoc failed on cover: {exc}; falling back to python-docx")
            tmp_path = out / "_cover_tmp.md"
            if tmp_path.exists():
                tmp_path.unlink()

    # Fallback path
    if not HAS_DOCX:
        raise RuntimeError("python-docx fallback not available")
    doc = Document()
    doc.add_heading(metadata.get("title", "Thesis"), level=0)
    doc.add_paragraph(f"Author: {metadata.get('author', 'Unknown')}")
    doc.add_paragraph(
        f"Date: {metadata.get('date', datetime.now().strftime('%Y-%m-%d'))}"
    )
    doc.add_paragraph(f"Institution: {metadata.get('institution', '')}")
    if metadata.get("abstract"):
        doc.add_heading("Abstract", level=1)
        doc.add_paragraph(metadata["abstract"])
    doc.save(str(dst))

    return dst
```

- [ ] **Step 4: Re-run T17 and the full suite; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

Expected: All tests still pass (T11, T17 + T2–T10).

- [ ] **Step 5: Manual smoke test — pypandoc-installed-but-pandoc-missing**

If you have a clean venv handy:
```bash
python3 -m venv /tmp/c-emergency-venv
source /tmp/c-emergency-venv/bin/activate
pip install pypandoc python-docx markdown
# Critically: do NOT install pandoc binary
python .claude/skills/export/scripts/convert_to_docx.py --base-dir . --output-dir /tmp/test-output --scope chapters
```

Expected output line: `Conversion method: python-docx + markdown (fallback)` rather than a pypandoc traceback. If pandoc IS installed, you'll see `Conversion method: pypandoc (pandoc)` — that's fine too.

If you can't easily make a 3.8 venv, log this manual procedure as deferred-verification in the PR description.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/export/scripts/convert_to_docx.py
git commit -m "$(cat <<'EOF'
fix(C-emergency): strengthen pandoc preflight + add runtime fallback

Bug #2 (R2 BLOCKER, strengthened per codex spec review). The previous
preflight (`USE_PANDOC = True if import pypandoc succeeds`) didn't prove
the system pandoc binary works. Replace with `pypandoc.get_pandoc_version()`
smoke probe (which shells out to `pandoc --version` internally), and wrap
`pypandoc.convert_file()` and `create_cover()` calls in try/except so a
broken pandoc on a single file falls back to python-docx instead of
crashing the batch.

Manual-smoke acceptance per spec §4.2; automated unit test deferred to
sub-project A.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Bug #2 — adjacent docs unification

**Files:**
- Modify: `.claude/skills/export/SKILL.md:30` (Workflow step 1)
- Modify: `docs/skills/08-export.md:56-58` (Workflow code block)
- Modify: `docs/skills/08-export.md:123-129` (Conversion Methods table)

No regression test — text-level docs unification.

- [ ] **Step 1: Fix `.claude/skills/export/SKILL.md:30`**

Current line:
```
1. **Check dependencies.** Verify that `pandoc` or `pypandoc` is available. If not, fall back to `python-docx` + `markdown`. Report which conversion method is being used.
```

Replace with:
```
1. **Check dependencies.** Verify that `pypandoc` is installed AND a working `pandoc` binary is on PATH (the script smoke-probes via `pypandoc.get_pandoc_version()`). If pypandoc/pandoc are unavailable, fall back to `python-docx` + `markdown`. Report which conversion method is being used.
```

- [ ] **Step 2: Fix `docs/skills/08-export.md:56-58`**

Current block:
```
├─ 1. Check dependencies
│     Preferred: pandoc / pypandoc
│     Fallback: python-docx + markdown library
│     Report which method is being used
```

Replace with:
```
├─ 1. Check dependencies
│     Preferred: pypandoc + working `pandoc` binary on PATH
│                (smoke-probed via pypandoc.get_pandoc_version())
│     Fallback: python-docx + markdown library
│     Report which method is being used
```

- [ ] **Step 3: Fix `docs/skills/08-export.md:123-129`**

Current table:
```
| Method | Priority | Requirements | Quality |
|--------|----------|-------------|---------|
| pandoc | Preferred | `pandoc` installed on system | Best — handles tables, footnotes, cross-references |
| pypandoc | Fallback 1 | `pip install pypandoc` | Same as pandoc (Python wrapper) |
| python-docx + markdown | Fallback 2 | `pip install python-docx markdown` | Adequate — may lose complex table formatting |
```

Replace with:
```
| Method | Priority | Requirements | Quality |
|--------|----------|-------------|---------|
| pypandoc + pandoc | Preferred | `pip install pypandoc` AND `pandoc` binary on PATH | Best — handles tables, footnotes, cross-references |
| python-docx + markdown | Fallback | `pip install python-docx markdown` | Adequate — may lose complex table formatting |
```

(Update the surrounding paragraph from "checks for each method in order" to reflect the two-tier model.)

- [ ] **Step 4: Verify nothing broke**

```bash
bash scripts/test-foolproofing.sh
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/export/SKILL.md docs/skills/08-export.md
git commit -m "$(cat <<'EOF'
docs(C-emergency): unify pandoc/pypandoc description in /export skill docs

Bug #2 adjacent docs (R2 reviewer-flagged). After Task 3's preflight
strengthening, "pandoc OR pypandoc as separate methods" is misleading —
they're the same code path (pypandoc shells out to pandoc). Unify into
one "pypandoc + pandoc binary" preferred path with python-docx as
fallback. Affects SKILL.md workflow step 1 and 08-export.md workflow
diagram + Conversion Methods table.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Bug #4 — output path drift + T12 regression

**Files:**
- Modify: `.claude/skills/export/SKILL.md:36`
- Modify: `docs/skills/08-export.md:63,99,100`
- Modify: `scripts/test-foolproofing.sh` (append T12)

- [ ] **Step 1: Append T12 to `scripts/test-foolproofing.sh`**

```bash
test_T12() {
    # No export_output references in skill prose or user docs
    ! grep -rq 'export_output' "$REPO_ROOT/.claude/skills/" "$REPO_ROOT/docs/skills/"
}
```

Add runner:

```bash
run_test "T12 no export_output in skill files"   test_T12
```

- [ ] **Step 2: Run T12; expect FAIL**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T12 reports FAIL.

- [ ] **Step 3: Fix `.claude/skills/export/SKILL.md:36`**

In the workflow code block (modified in Task 1), change `{project_root}/export_output` → `{project_root}/final_output`.

- [ ] **Step 4: Fix `docs/skills/08-export.md:63,99,100`**

- Line 63 (workflow code block): `{project_root}/export_output` → `{project_root}/final_output`
- Line 99 (Output directory table cell): `export_output/` → `final_output/`
- Line 100 (ZIP archive table cell): `export_output/thesis_2026-03-30.zip` → `final_output/thesis_2026-03-30.zip`

- [ ] **Step 5: Run T12; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T12 passes; everything else still passes.

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/export/SKILL.md docs/skills/08-export.md scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): unify output path to final_output/

Bug #4 (R2 MAJOR). User-facing docs (CLAUDE.md, AGENTS.md, GEMINI.md,
README.md) say final_output/; skill internals said export_output/. The
mismatch creates a second directory at runtime, confusing users about
where their .docx files are. Skill now writes to final_output/ matching
user-facing docs.

Adds T12 regression test (no export_output in skill files).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Bug #6 — `compile_pdf.py` reference + T15 regression

**Files:**
- Modify: `docs/skills/08-export.md:184` (Common Mistakes row)
- Modify: `scripts/test-foolproofing.sh` (append T15)

- [ ] **Step 1: Append T15 to `scripts/test-foolproofing.sh`**

```bash
test_T15() {
    # No compile_pdf.py references — that script does not exist.
    # Scoped to user-facing skill docs; docs/superpowers/{specs,plans}/
    # legitimately mention compile_pdf.py while documenting Bug #6.
    ! grep -rq 'compile_pdf.py' "$REPO_ROOT/docs/skills/" "$REPO_ROOT/README.md"
}
```

Add runner:

```bash
run_test "T15 no compile_pdf.py references"      test_T15
```

- [ ] **Step 2: Run T15; expect FAIL**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T15 FAIL.

- [ ] **Step 3: Fix `docs/skills/08-export.md:184`**

Current row:
```
| Expecting PDF output | `/export` produces .docx + ZIP. For PDF, use your own Markdown-to-PDF pipeline (e.g., `compile_pdf.py`). |
```

Replace with:
```
| Expecting PDF output | `/export` produces .docx + ZIP. There is no PDF export path; convert the .docx to PDF in Word or LibreOffice if you need PDF. |
```

- [ ] **Step 4: Run T15; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

- [ ] **Step 5: Commit**

```bash
git add docs/skills/08-export.md scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): drop stale compile_pdf.py reference

Bug #6 (R2 MINOR). 08-export.md:184 referenced compile_pdf.py which
does not exist in the repo and was never implemented. Rewrite the row
to acknowledge there is no built-in PDF path; users convert .docx via
Word or LibreOffice.

Adds T15 regression test (no compile_pdf.py references).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Bug #3 — status enum drift + T13 regression

**Files:**
- Modify: `README.md:123` and `:212`
- Modify: `.cursor/rules/academic-writing.mdc:9`
- Modify: `scripts/test-foolproofing.sh` (append T13)

- [ ] **Step 1: Append T13 to `scripts/test-foolproofing.sh`**

```bash
test_T13() {
    # No `revisiting` status anywhere — only `reading | completed | integrated`
    ! grep -rqE '\brevisiting\b' "$REPO_ROOT/README.md" "$REPO_ROOT/.cursor/" "$REPO_ROOT/docs/" "$REPO_ROOT/.claude/skills/" 2>/dev/null
}
```

Add runner:

```bash
run_test "T13 no revisiting status enum"         test_T13
```

- [ ] **Step 2: Run T13; expect FAIL**

Expected: T13 FAIL because of `.cursor/rules/academic-writing.mdc:9`.

- [ ] **Step 3: Fix `.cursor/rules/academic-writing.mdc:9`**

Current line:
```
- **Status**: `reading` | `complete` | `revisiting`
```

Replace with:
```
- **Status**: `reading` | `completed` | `integrated`
```

- [ ] **Step 4: Fix `README.md:212`**

Current line (around line 212):
```
- **Status**: `reading` or `complete` — tracked by `/progress`
```

Replace with:
```
- **Status**: `reading` | `completed` | `integrated` — tracked by `/progress`
```

- [ ] **Step 5: Fix `README.md:123`**

Current line (around line 123):
```
This table is what `/map` scans to build a literature-to-chapter matrix, and what `/integrate` consumes when weaving sources into chapter drafts. The `Status` field at the top of each notes file (`reading` / `completed`) is what `/progress` reads to calculate your coverage.
```

Replace `(`reading` / `completed`)` with `(`reading` / `completed` / `integrated`)`.

- [ ] **Step 6: Run T13; expect PASS. Manual review of `complete` vs `completed`**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T13 passes.

Manual: review `grep -nE '\bcomplete\b' README.md .cursor/rules/academic-writing.mdc | grep -v completed`. Allowed false positives: `complete reading notes` (verb), `complete the` (verb). Reject any usage as a status value.

- [ ] **Step 7: Commit**

```bash
git add README.md .cursor/rules/academic-writing.mdc scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): standardise status enum to reading|completed|integrated

Bug #3 (R2 MAJOR). README.md and .cursor/rules used outdated/partial
enums (reading | complete | revisiting in cursor; reading or complete
in README:212; reading / completed without integrated in README:123).
Skill implementations parse only reading|completed|integrated, so users
following these docs silently dropped from /progress and /integrate
counts.

Drops `revisiting` (no skill consumes it; conceptually equivalent to
returning to `reading`).

Adds T13 regression test (no revisiting). Manual review covers the
`complete` vs `completed` distinction (regex would have prose false
positives).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Bug #7 — vocab drift + T14 regression

**Files:**
- Modify: `.claude/skills/map/SKILL.md:28,44-46`
- Modify: `docs/skills/04-map.md:9,76-81`
- Modify: `docs/skills/02-note.md:204-211`
- Modify: `scripts/test-foolproofing.sh` (append T14)

- [ ] **Step 1: Append T14 to `scripts/test-foolproofing.sh`**

```bash
test_T14() {
    # No deprecated vocab (argue|cite|data|method) in matrix-cell context
    # within /map skill files and the /note user doc's standard-types section.
    local files=(
        "$REPO_ROOT/.claude/skills/map/SKILL.md"
        "$REPO_ROOT/docs/skills/04-map.md"
    )
    # Scope to lines containing | (table-cell delimiter) to skip prose like
    # "data consistency" or "must cite the source"; exclude header rows.
    if grep -nE '\|.*\b(argue|cite|data|method)\b' "${files[@]}" 2>/dev/null \
        | grep -vE '^[^:]+:[0-9]+:\s*\|\s*Term\s*\|' | grep -q .; then
        return 1
    fi
    # Also check the /note user doc for the 6-element list as "standard types"
    ! grep -qE '`(argue|cite|data|method)`' "$REPO_ROOT/docs/skills/02-note.md"
}
```

Add runner:

```bash
run_test "T14 no deprecated vocab in /map+/note" test_T14
```

- [ ] **Step 2: Run T14; expect FAIL**

Expected: T14 FAIL — finds `argue` and `cite` in `/map` example matrices and the 6-word list in `02-note.md`.

- [ ] **Step 3: Fix `.claude/skills/map/SKILL.md:28`**

Current:
```
   - Mark each cell with the connection type if a mapping exists (e.g., `cite`, `argue`, `data`, `method`).
```

Replace with:
```
   - Mark each cell with the connection type if a mapping exists (e.g., `supports`, `challenges`, `extends`).
```

- [ ] **Step 4: Fix `.claude/skills/map/SKILL.md:44-46`**

Current example matrix rows:
```
| Bennett (2010) | integrated | | argue | argue | | | | | |
| Goodman (1968) | integrated | cite | argue | argue | cite | | | | |
| Hui (2017) | completed | | | argue | | | cite | | cite |
```

Replace with stance-only values:
```
| Bennett (2010) | integrated | | supports | supports | | | | | |
| Goodman (1968) | integrated | extends | supports | supports | extends | | | | |
| Hui (2017) | completed | | | supports | | | challenges | | challenges |
```

- [ ] **Step 5: Fix `docs/skills/04-map.md:9`**

Current:
```
`/map` scans every notes file and every chapter, then builds a cross-reference matrix. Rows are sources, columns are chapters. Each cell shows the connection type (supports, challenges, extends, cite, data, method).
```

Replace with:
```
`/map` scans every notes file and every chapter, then builds a cross-reference matrix. Rows are sources, columns are chapters. Each cell shows the connection type (supports, challenges, extends).
```

- [ ] **Step 6: Fix `docs/skills/04-map.md:76-81`**

Current example matrix:
```
| Bennett (2010) | integrated | | | argue | | supports | | | |
| Goodman (1968) | integrated | cite | argue | argue | cite | | | | |
| Hui (2017) | completed | | | argue | | | cite | | cite |
| Panofsky (1939) | integrated | cite | argue | argue | | | | | |
| Parsons (1987) | completed | | cite | argue | | | | | |
| Steyerl (2023) | completed | | | | | | argue | cite | |
```

Replace with stance-only:
```
| Bennett (2010) | integrated | | | supports | | supports | | | |
| Goodman (1968) | integrated | extends | supports | supports | extends | | | | |
| Hui (2017) | completed | | | supports | | | challenges | | challenges |
| Panofsky (1939) | integrated | extends | supports | supports | | | | | |
| Parsons (1987) | completed | | extends | supports | | | | | |
| Steyerl (2023) | completed | | | | | | supports | extends | |
```

- [ ] **Step 7: Fix `docs/skills/02-note.md:204-211`**

Current:
```
5. **Use connection types consistently.** The standard types are:
   - `supports` — source provides evidence for your argument
   - `challenges` — source contradicts or complicates your argument
   - `extends` — source adds a new dimension to your argument
   - `cite` — source is referenced but not deeply engaged
   - `data` — source provides data or examples
   - `method` — source informs methodology
```

Replace with:
```
5. **Use connection types consistently.** The standard types are:
   - `supports` — source provides evidence for your argument
   - `challenges` — source contradicts or complicates your argument
   - `extends` — source adds a new dimension to your argument
```

- [ ] **Step 8: Run T14; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

Expected: T14 passes; full suite green.

- [ ] **Step 9: Commit**

```bash
git add .claude/skills/map/SKILL.md docs/skills/04-map.md docs/skills/02-note.md scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): standardise connection-type vocab to stance-only

Bug #7 (R2 MINOR, expanded per codex spec review). Two vocabularies
competed for the Connection Type column:
- /note template + /integrate use stance: supports/challenges/extends
- /map example matrices used citation purpose: cite/argue/data/method
- docs/skills/02-note.md taught the 6-element merged set as "standard"

Per /map SKILL.md:75 /map reads the column /note populates, so /map's
example matrices showed vocabulary users would never write. Standardise
on /note's stance vocabulary (the contract owner). Update /map skill +
04-map.md example matrices and the /note user doc's standard-types list.

No real notes files exist yet (per project memory), so zero migration
cost.

Adds T14 regression test (deprecated vocab in matrix-cell context).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Bug #5 — PDF claim + T16 regression

**Files:**
- Modify: `docs/setup-claude-code.md:44`
- Modify: `docs/setup-codex-cli.md:44`
- Modify: `docs/setup-gemini-cli.md:44`
- Modify: `docs/setup-openclaw.md:32`
- Modify: `scripts/test-foolproofing.sh` (append T16)

- [ ] **Step 1: Append T16 to `scripts/test-foolproofing.sh`**

```bash
test_T16() {
    # No "Word/PDF" or "to Word and PDF" in setup docs — /export only produces .docx + .zip
    ! grep -lE '(Word/PDF|to Word and PDF)' "$REPO_ROOT"/docs/setup-*.md 2>/dev/null | grep -q .
}
```

Add runner:

```bash
run_test "T16 no PDF export claim in setup docs" test_T16
```

- [ ] **Step 2: Run T16; expect FAIL**

Expected: T16 FAIL — all 4 setup docs.

- [ ] **Step 3: Fix all four setup files**

In `docs/setup-claude-code.md:44`, `docs/setup-codex-cli.md:44`, `docs/setup-gemini-cli.md:44`, `docs/setup-openclaw.md:32` — find the row:
```
| `/export` (or export) | Export chapters to Word/PDF |
```
(actual table row format may vary slightly per file)

Replace `Word/PDF` with `Word (.docx) + ZIP` in each file.

- [ ] **Step 4: Run T16; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

- [ ] **Step 5: Commit**

```bash
git add docs/setup-*.md scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): correct PDF export claim in setup docs

Bug #5 (R2 MAJOR). All 4 setup-*.md files claimed /export produces
"Word/PDF". Reality: convert_to_docx.py only writes .docx + .zip.
Replace with "Word (.docx) + ZIP" everywhere. Other PDF mentions in
the same files refer to /read consuming PDFs as input — leave alone.

Adds T16 regression test.

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Bug #9 + #10 — allowed-tools repairs + T18 regression

**Files:**
- Modify: `.claude/skills/map/SKILL.md:4` (frontmatter `allowed-tools`)
- Modify: `.claude/skills/verify/SKILL.md:4` (frontmatter `allowed-tools`)
- Modify: `scripts/test-foolproofing.sh` (append T18)

- [ ] **Step 1: Append T18 to `scripts/test-foolproofing.sh`**

```bash
test_T18() {
    # /map needs Write (line 62 says "use Write if creating new")
    grep -qE '^allowed-tools:.*\bWrite\b' "$REPO_ROOT/.claude/skills/map/SKILL.md" || return 1
    # /verify needs Read (Edit requires prior Read per harness contract)
    grep -qE '^allowed-tools:.*\bRead\b' "$REPO_ROOT/.claude/skills/verify/SKILL.md" || return 1
    return 0
}
```

Add runner:

```bash
run_test "T18 allowed-tools sanity (/map+/verify)" test_T18
```

- [ ] **Step 2: Run T18; expect FAIL**

Expected: T18 FAIL — `/map` missing `Write` (or `/verify` missing `Read`, depending which check fails first).

- [ ] **Step 3: Fix `.claude/skills/map/SKILL.md:4`**

Current:
```yaml
allowed-tools: Read, Glob, Grep, Edit
```

Replace with:
```yaml
allowed-tools: Read, Glob, Grep, Edit, Write
```

- [ ] **Step 4: Fix `.claude/skills/verify/SKILL.md:4`**

Current:
```yaml
allowed-tools: WebSearch, WebFetch, Edit
```

Replace with:
```yaml
allowed-tools: WebSearch, WebFetch, Read, Edit
```

- [ ] **Step 5: Run T18; expect PASS**

```bash
bash scripts/test-foolproofing.sh
```

- [ ] **Step 6: Commit**

```bash
git add .claude/skills/map/SKILL.md .claude/skills/verify/SKILL.md scripts/test-foolproofing.sh
git commit -m "$(cat <<'EOF'
fix(C-emergency): repair allowed-tools for /map and /verify

Bug #9 (NEW MAJOR, codex audit + substitute audit). /map SKILL.md:62
says "use Write (if creating new)" for literature/mapping_matrix.md
but allowed-tools omitted Write. First-time save was denied. Add Write.

Bug #10 (NEW MAJOR, substitute audit). /verify SKILL.md uses Edit to
annotate notes files (lines 27, 61) but allowed-tools omitted Read.
The harness requires Read before Edit. Annotation always failed. Add
Read.

Adds T18 regression test (allowed-tools sanity).

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: R6 — OpenClaw setup doc

**Files:**
- Modify: `docs/setup-openclaw.md` (Configuration section, around line 38)

No regression test — text-level doc fix.

- [ ] **Step 1: Rewrite Configuration section**

Find the Configuration section (around line 36-44). Current:
```markdown
## Configuration

OpenClaw reads `AGENTS.md` as its project instruction file. Edit it to set your:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters
```

Replace with:
```markdown
## Configuration

OpenClaw reads `AGENTS.md` as its project instruction file, but **`AGENTS.md` is auto-generated** from `CLAUDE.md` by sub-project D's tooling. To customise:

1. Edit `CLAUDE.md` (the canonical source — the SHARED block is what gets regenerated).
2. Run `make sync` to regenerate `AGENTS.md` (and `GEMINI.md`).
3. Verify with `make doctor`.

Things to set:

- Word count targets per chapter
- Reading pace limits
- Directory paths for literature and chapters
```

- [ ] **Step 2: Verify nothing broke**

```bash
bash scripts/test-foolproofing.sh
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add docs/setup-openclaw.md
git commit -m "$(cat <<'EOF'
docs(C-emergency): point OpenClaw setup at CLAUDE.md, not generated AGENTS.md

R6 adjacent doc fix (codex audit). docs/setup-openclaw.md:38 told users
to edit AGENTS.md directly, but sub-project D made AGENTS.md a generated
artefact synced from CLAUDE.md. Users following the old doc would lose
edits on next `make sync`. Rewrite Configuration section to point at the
canonical CLAUDE.md + `make sync` workflow.

(Cursor doc has the same issue at setup-cursor.md:51 — defer to C-rest
per spec §2 since OpenClaw is the headline cross-platform target.)

Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Final verification + ship

**Files:**
- Read: all (no edits — this is verification)

- [ ] **Step 1: Run full self-test**

```bash
bash scripts/test-foolproofing.sh
```

Expected output: 15 tests run, 15 pass.
- T2 symlink corruption + repair ✓
- T3 sync drift detection + restore ✓
- T4 CLAUDE.md edit propagates to both ✓
- T5 missing marker aborts sync ✓
- T8 sync is idempotent ✓
- T9 make init aborts without tty ✓
- T10 core.fileMode auto-fix ✓
- T11 no CLAUDE_SKILL_DIR in skill files ✓
- T12 no export_output in skill files ✓
- T13 no revisiting status enum ✓
- T14 no deprecated vocab in /map+/note ✓
- T15 no compile_pdf.py references ✓
- T16 no PDF export claim in setup docs ✓
- T17 Python 3.8 import safety ✓
- T18 allowed-tools sanity (/map+/verify) ✓

- [ ] **Step 2: Run doctor**

```bash
make doctor
```

Expected: 5/5 ✓.

- [ ] **Step 3: Run sync (idempotency check)**

```bash
make sync
```

Expected: no-op (CLAUDE.md SHARED block unchanged by C-emergency fixes).

- [ ] **Step 4: Manual smoke test for `/export`**

In Claude Code:
```
/export chapters
```

Expected: creates `final_output/chapters/*.docx` (none if `chapters/` is empty, which is the current state) + ZIP. No `${CLAUDE_SKILL_DIR}` errors.

If running in Codex CLI or Gemini, the same command should also succeed.

- [ ] **Step 5: Manual smoke test for `/map save`**

In Claude Code on a fresh checkout (or after `rm literature/mapping_matrix.md` if it exists):
```
/map
save
```

Expected: `literature/mapping_matrix.md` is created without harness denial.

- [ ] **Step 6: Manual smoke test for `/verify` annotate (optional)**

If you have a notes file to verify a claim against, invoke `/verify` with a request to annotate. Expected: Edit succeeds (no "Read tool required" denial).

- [ ] **Step 7: Review PR description draft**

Use this template for the PR (the implementer adapts):

```markdown
## Summary

Sub-project C-emergency — fix 10 bugs (2 R2 BLOCKERs + 1 NEW BLOCKER + 3 R2 MAJORs + 2 NEW MAJORs + 2 R2 MINORs) and 1 adjacent doc bug. Also extends scripts/test-foolproofing.sh with 8 grep-based regression tests (T11–T18).

See spec at docs/superpowers/specs/2026-04-27-c-emergency-design.md for design rationale and reviewer-feedback log.

## What's in here

- **R2 BLOCKERs:** ${CLAUDE_SKILL_DIR} hardcode, pypandoc preflight (with try/except runtime fallback)
- **NEW BLOCKER:** Python 3.8 compat (from __future__ import annotations)
- **R2 MAJORs:** status enum standardisation, output path unification, false PDF export claim
- **NEW MAJORs:** /map allowed-tools missing Write, /verify allowed-tools missing Read
- **R2 MINORs:** stale compile_pdf.py reference, /map vs /note vocab drift
- **Adjacent:** OpenClaw setup doc points at CLAUDE.md (not generated AGENTS.md)
- **Tests:** T11–T18 added to scripts/test-foolproofing.sh

## Migration note

Users who ran the buggy /export may have a populated `export_output/` directory. This patch does NOT migrate contents automatically. Affected users should `mv export_output/* final_output/` after upgrade.

## Test plan

- [x] `bash scripts/test-foolproofing.sh` — 15/15 ✓
- [x] `make doctor` — 5/5 ✓
- [x] `make sync` — no-op
- [ ] Manual smoke: `/export chapters` on Claude Code
- [ ] Manual smoke: same on Codex CLI
- [ ] Manual smoke: `/map save` creates literature/mapping_matrix.md
- [ ] Manual smoke: pypandoc-without-pandoc-binary falls back to python-docx (if a clean venv is available)

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

- [ ] **Step 8: No commit needed for Task 12** — all changes already committed in Tasks 1-11.

---

## Implementation summary

| Task | Bug | Files touched | Commit count |
|---|---|---|---|
| 1 | #1 + T11 | SKILL.md, 08-export.md, test-foolproofing.sh | 1 |
| 2 | #8 + T17 | convert_to_docx.py, test-foolproofing.sh | 1 |
| 3 | #2 | convert_to_docx.py | 1 |
| 4 | #2-docs | SKILL.md, 08-export.md | 1 |
| 5 | #4 + T12 | SKILL.md, 08-export.md, test-foolproofing.sh | 1 |
| 6 | #6 + T15 | 08-export.md, test-foolproofing.sh | 1 |
| 7 | #3 + T13 | README.md, .cursor/rules/, test-foolproofing.sh | 1 |
| 8 | #7 + T14 | map/SKILL.md, 04-map.md, 02-note.md, test-foolproofing.sh | 1 |
| 9 | #5 + T16 | 4× setup-*.md, test-foolproofing.sh | 1 |
| 10 | #9 + #10 + T18 | map/SKILL.md, verify/SKILL.md, test-foolproofing.sh | 1 |
| 11 | R6 | docs/setup-openclaw.md | 1 |
| 12 | (verification) | — | 0 |

**Total: 11 commits, 14 files modified, ~70-90 lines edit volume.**
