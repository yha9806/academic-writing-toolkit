# D — Foolproofing & Multi-Platform Robustness

**Status**: Design (awaiting review)
**Date**: 2026-04-26
**Owner**: yha9806
**Brainstormed via**: superpowers:brainstorming
**Sub-project of**: A-D toolkit-development roadmap (D first, then A → C → B)

---

> **Rename note (2026-04-27, sub-project A)**: The script referenced below as `scripts/test-foolproofing.sh` was renamed to `scripts/test.sh` in sub-project A. The body of this document is preserved as-shipped to keep the historical record honest; readers acting on the instructions today should substitute the new name.

## §1 Scope & Goals

### Goal

Make any user who clones / downloads `academic-writing-toolkit` on macOS, Linux, or WSL able to complete first-time setup, dependency verification, and cross-platform config sync with minimum friction and zero silent breakage.

### In-scope (the 7 candidate problems)

1. Symlink corruption defence and repair (`.agents/skills/*` → `.claude/skills/*`)
2. File mode drift defence (`core.fileMode`)
3. CRLF defence (`.gitattributes`)
4. System dependency declaration and runtime check (pandoc / python3 / python-docx)
5. First-run onboarding (`make init` + README "First Run Checklist")
6. `.gitignore` semantic review (minimal change)
7. `Makefile` single entry point

### Out-of-scope

- Native Windows PowerShell path (users on Windows go via WSL)
- YAML-based config (YAGNI; CLAUDE.md remains the human-edited source)
- Any skill internal logic changes (those belong to sub-projects A / B / C)
- `.cursor/rules/` sync (its content is complementary to CLAUDE.md, not duplicative)
- CI workflow files (sub-project A)
- Citation format checking (sub-project C, as `/audit` enhancement)

### Constraint (CLAUDE.md content discipline)

CLAUDE.md must only carry **project-level metadata**: `targets`, `directories`, `principles`, `reading constraints`. Any skill-internal algorithm, template, or check logic must live in the corresponding `.claude/skills/<name>/SKILL.md` or its `references/` subfile — following the SKILL-level modularisation pattern used by superpowers itself. This constraint prevents CLAUDE.md from drifting into a "global junk drawer" as sub-projects B / C add features.

### Success criteria

1. New user on mac / linux / WSL can run `git clone && make setup && make doctor` and confirm environment is ready in three commands.
2. After editing `CLAUDE.md`, a single `make sync` realigns `AGENTS.md` and `GEMINI.md`.
3. When symlinks corrupt or file mode drifts, `make doctor` reports red, `make repair` fixes idempotently.
4. `git status` after a clean clone + `make setup` is empty (no mode-bit noise).

---

## §2 Components & Layout

### New files (7)

```
academic-writing-toolkit/
├── Makefile                          # Single entry point; orchestration only, no logic
├── .gitattributes                    # `* text=auto eol=lf` to defend against CRLF
├── scripts/
│   ├── sync-config.sh                # Regenerate AGENTS.md / GEMINI.md from CLAUDE.md
│   ├── doctor.sh                     # Read-only checks (i, ii, iii, iv, v)
│   ├── repair.sh                     # Idempotent fixes for whatever doctor flags
│   ├── lib.sh                        # Shared: colour output, check helpers, exit codes
│   └── test-foolproofing.sh          # Self-test script callable by sub-project A's CI later
├── templates/
│   ├── agents-preamble.md            # Codex / OpenClaw header before SHARED block
│   └── gemini-preamble.md            # Gemini header before SHARED block
└── docs/superpowers/specs/
    └── 2026-04-26-foolproofing-design.md   # This spec
```

### Modified files (4)

| File | Change |
|------|--------|
| `CLAUDE.md` | Neutralise wording (drop Claude-Code-specific phrases); insert `<!-- SHARED:START -->` / `<!-- SHARED:END -->` markers around the syncable section; add a top-of-file note explaining canonicality |
| `AGENTS.md` | Becomes a generated artefact; keep Codex preamble (moved into `templates/agents-preamble.md`); add `<!-- GENERATED FROM CLAUDE.md — do not edit, run \`make sync\` -->` |
| `GEMINI.md` | Same as AGENTS.md but with Gemini preamble |
| `README.md` | Add "First Run Checklist" section + warning "do not use GitHub Web 'Download ZIP' (breaks symlinks)" |
| `docs/setup-claude-code.md`, `setup-codex-cli.md`, `setup-gemini-cli.md` | Mention `make setup` and `make doctor` in the install flow |

### Untouched

- `.gitignore` — current rules cover the academic use case (PDFs, DOCXs, ZIPs, DS_Store, pycache, .env). YAGNI on whitelist subdirs until someone actually needs to commit a sample artefact.
- `.cursor/rules/academic-writing.mdc` — content is complementary (writing conventions), not duplicative.
- Any `.claude/skills/*/SKILL.md` — out of scope for D.

### Data flow (CLAUDE.md is canonical)

```
   ┌──────────────┐
   │  CLAUDE.md   │  ← single human-edited source
   └──────┬───────┘
          │  scripts/sync-config.sh
          │   1. extract content between SHARED:START / SHARED:END
          │   2. + templates/agents-preamble.md → AGENTS.md
          │   3. + templates/gemini-preamble.md → GEMINI.md
          ▼
   ┌──────────────┐  ┌──────────────┐
   │  AGENTS.md   │  │  GEMINI.md   │  ← generated, but committed to git
   └──────────────┘  └──────────────┘
```

> AGENTS.md and GEMINI.md remain committed (not in `.gitignore`) so cloners can use Codex / Gemini immediately without running `make sync` first. `make doctor` check (iv) ensures the three files stay aligned.

### Makefile targets

| Target | Action | When |
|--------|--------|------|
| `make help` | List targets parsed from comments | Default target |
| `make setup` | `git config core.fileMode false` + `make sync` + `make doctor` (propagates doctor's exit code; non-zero if any check fails) | Once after clone |
| `make init` | `$(EDITOR) CLAUDE.md && make sync` | First-time customisation |
| `make sync` | Invoke `scripts/sync-config.sh` | After any CLAUDE.md edit |
| `make doctor` | Invoke `scripts/doctor.sh`, read-only | Anytime |
| `make repair` | Invoke `scripts/repair.sh`, write actions | After `make doctor` flags red |

### Component boundaries (single-responsibility)

- **Makefile** — pure orchestration, no business logic
- **sync-config.sh** — parse + template fill
- **doctor.sh** — five independent check functions, all read-only, exit codes aggregated
- **repair.sh** — five matched fix functions, idempotent and safe to re-run
- **lib.sh** — colour, `pass` / `fail` / `warn` / `hint` / `header`

---

## §3 Sync Mechanism

### CLAUDE.md structure (post-migration)

```markdown
# Academic Writing Project

<!-- This is the canonical project config. Do not edit AGENTS.md or GEMINI.md
     directly — they are generated from this file. After editing here, run:
       make sync -->

## Project Overview
<!-- SHARED:START -->
This project uses the academic-writing-toolkit skills for structured research...

## Directories
- Chapters: `chapters/`
...

## Targets
...

## Reading Constraints
...

## Writing Principles
...
<!-- SHARED:END -->
```

The two markers delimit the syncable block. Anything outside the markers (the H1 title, the explanatory comment) is local to CLAUDE.md and not propagated.

### Platform preambles (new files)

```
templates/
├── agents-preamble.md    # Codex / OpenClaw preamble
└── gemini-preamble.md    # Gemini preamble
```

`templates/agents-preamble.md`:

```markdown
# Academic Writing Project

<!-- GENERATED FROM CLAUDE.md — do not edit. Run `make sync` after editing CLAUDE.md. -->

This file provides instructions for AI coding agents working in this repository.

## Skill Discovery
Skills are located in `.agents/skills/`. Each `.md` file in that directory defines a slash-command skill for academic writing workflows.
```

`templates/gemini-preamble.md`: same structure with Gemini-flavoured introduction.

### sync-config.sh algorithm

```bash
#!/usr/bin/env bash
# scripts/sync-config.sh [INPUT_FILE] [OUTPUT_DIR]
#   INPUT_FILE  — defaults to CLAUDE.md
#   OUTPUT_DIR  — defaults to . (repo root); pass a tmpdir for read-only diff use
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

INPUT="${1:-CLAUDE.md}"
OUTDIR="${2:-.}"

# 0. Validate prerequisites
[[ -f "$INPUT" ]] || die "input not found: $INPUT"
[[ -d "$OUTDIR" ]] || die "output dir not found: $OUTDIR"
[[ -f "$REPO_ROOT/templates/agents-preamble.md" ]] || die "$REPO_ROOT/templates/agents-preamble.md missing — reinstall toolkit"
[[ -f "$REPO_ROOT/templates/gemini-preamble.md" ]] || die "$REPO_ROOT/templates/gemini-preamble.md missing — reinstall toolkit"

# 1. Validate exactly one marker pair (markers MUST appear alone on their own line — no leading/trailing whitespace, not inside code fences)
start_count=$(awk '$0 == "<!-- SHARED:START -->" {n++} END {print n+0}' "$INPUT")
end_count=$(awk '$0 == "<!-- SHARED:END -->" {n++} END {print n+0}' "$INPUT")
[[ "$start_count" -eq 1 && "$end_count" -eq 1 ]] || \
  die "expected exactly one <!-- SHARED:START --> and one <!-- SHARED:END --> as standalone lines in $INPUT (found start=$start_count end=$end_count)"

# 2. Extract SHARED block (anchored line-equality match excludes markers inside code blocks)
shared=$(awk '$0 == "<!-- SHARED:START -->" {flag=1; next} $0 == "<!-- SHARED:END -->" {flag=0} flag' "$INPUT")
[[ -n "$shared" ]] || die "SHARED block is empty in $INPUT"

# 3. Generate AGENTS.md atomically
{ cat "$REPO_ROOT/templates/agents-preamble.md"; printf '%s\n' "$shared"; } > "$OUTDIR/AGENTS.md.new"
mv "$OUTDIR/AGENTS.md.new" "$OUTDIR/AGENTS.md"

# 4. Generate GEMINI.md atomically
{ cat "$REPO_ROOT/templates/gemini-preamble.md"; printf '%s\n' "$shared"; } > "$OUTDIR/GEMINI.md.new"
mv "$OUTDIR/GEMINI.md.new" "$OUTDIR/GEMINI.md"

ok "Synced AGENTS.md and GEMINI.md from $INPUT into $OUTDIR"
```

`SCRIPT_DIR` and `REPO_ROOT` are derived from `BASH_SOURCE`, so the script resolves `templates/` against its own location rather than the caller's cwd. This lets `make doctor` invoke it from any directory (it writes to a `mktemp -d` for read-only diffs) and guarantees correct behaviour even when the script is symlinked or invoked with absolute paths.

**Marker constraint** — both `<!-- SHARED:START -->` and `<!-- SHARED:END -->` MUST appear on their own line, with no leading or trailing whitespace, and never inside a markdown code fence. The anchored `$0 == "..."` check enforces this; markers appearing inside fenced code blocks (e.g. examples in this spec) are correctly ignored.

**Path parameters** — `sync-config.sh` accepts optional positional args so the same script powers both `make sync` (in-place, default args) and `make doctor`'s check (iv) (which writes to a `mktemp -d` for non-mutating diff). No separate dry-run mode needed.

### Properties

- **Deterministic** — same input always produces same output (no timestamps, no randomness)
- **Idempotent** — N consecutive runs leave the working tree identical
- **Atomic** — `.new` temp file + `mv` avoids half-written states
- **Loud failure** — missing markers abort immediately, no silent empty output

### Sync ↔ Doctor coupling

- `make sync` invokes `scripts/sync-config.sh` with default args (in-place write)
- `make doctor` check (iv): `tmp=$(mktemp -d) && scripts/sync-config.sh CLAUDE.md "$tmp" && diff -q AGENTS.md "$tmp/AGENTS.md" && diff -q GEMINI.md "$tmp/GEMINI.md"`; either diff returning non-zero → red, hint `make sync`; trap removes tmpdir on exit
- `make repair` for (iv): invoke `make sync` directly

### Explicitly rejected (kept simple)

- ❌ `pandoc` / `mustache` template engine — unnecessary dependency
- ❌ YAML frontmatter config — would force users to learn YAML
- ❌ Bidirectional sync (regenerate CLAUDE.md from generated files) — complexity explosion, YAGNI
- ❌ git smudge / clean filters — opaque magic, undebuggable for new contributors

---

## §4 Doctor & Repair Check Matrix

Each check is a small bash function paired with a same-named fix function. `lib.sh` provides `pass` / `fail` / `warn` / `hint` / `header`. No external dependencies beyond git and standard system tools.

### Five checks

| ID | Check | Implementation | Fix | Exit |
|----|-------|----------------|-----|------|
| **i+ii** | `.agents/skills/<8 names>` are symlinks pointing to `../../.claude/skills/<name>` | Loop accumulates failures so a broken early symlink is not masked by good later ones: `local_fails=0; for n in audit export integrate map note progress read verify; do if ! { test -L ".agents/skills/$n" && [[ "$(readlink ".agents/skills/$n")" == "../../.claude/skills/$n" ]]; }; then fail "skill symlink broken: $n"; local_fails=$((local_fails+1)); fi; done; [[ $local_fails -eq 0 ]] && pass "symlinks intact"` | `for n in <8 names>; do rm -rf ".agents/skills/$n"; ln -s "../../.claude/skills/$n" ".agents/skills/$n"; done` | 0 / 1 |
| **iii** | `git config core.fileMode == false` | `[[ "$(git config --get core.fileMode)" == "false" ]]` (empty value treated as failure) | `git config core.fileMode false` (local repo only, never `--global`) | 0 / 1 |
| **iv** | CLAUDE.md ↔ AGENTS.md / GEMINI.md in sync | sync to `$(mktemp -d)`, `diff -q` against on-disk files | invoke `scripts/sync-config.sh` | 0 / 1 |
| **v** | `pandoc`, `python3`, `python3 -c "import docx"` available | `command -v` plus one import test | **No auto-install**; print OS-specific install hints (macOS: `brew install pandoc && pip install python-docx`; Debian: `apt install pandoc && pip install python-docx`) | 0 / 1 |

### `make doctor` output

```
$ make doctor
Checking academic-writing-toolkit environment...

[✓] symlinks intact (.agents/skills/* → .claude/skills/*)
[✓] git core.fileMode disabled
[✗] config sync — AGENTS.md drifted from CLAUDE.md
       fix: make sync
[✓] system deps — pandoc 3.1.9, python3 3.12.2, python-docx 1.1.0

1 issue. Run `make repair` to fix.
```

Exit code: 0 if all pass, 1 if any fail (CI-friendly).

### `make repair` semantics

```
$ make repair
[i+ii] Rebuilding 8 symlinks... ok
[iv]   Re-syncing AGENTS.md / GEMINI.md... ok
[v]    System deps OK, nothing to do.

Re-running doctor:
[✓] all checks pass.
```

- Acts directly, no `--dry-run` flag (run doctor first if you want preview)
- Idempotent — re-runs leave system in same state
- (v) never auto-installs system packages (avoids sudo / cross-distro landmines)
- Re-runs doctor at the end to confirm

### `lib.sh` helpers

```bash
# Initialise the failure counter so `set -u` does not trip
FAILS=${FAILS:-0}

pass()   { printf "  \033[32m[✓]\033[0m %s\n" "$*"; }
fail()   { printf "  \033[31m[✗]\033[0m %s\n" "$*"; FAILS=$((FAILS+1)); }   # soft fail — accumulates, does not exit
warn()   { printf "  \033[33m[!]\033[0m %s\n" "$*"; }
hint()   { printf "       fix: %s\n" "$*"; }
header() { printf "\n%s\n" "$*"; }
die()    { printf "\033[31merror:\033[0m %s\n" "$*" >&2; exit 2; }            # hard fail — exits immediately
```

**Two failure helpers, two distinct uses**:
- `fail` — used by `doctor.sh`'s individual checks; accumulates into `FAILS`, doctor sums them at the end and exits 1 if any.
- `die` — used by `sync-config.sh` and similar one-shot scripts where a structural error means there is no point continuing; exits 2 immediately.

Non-TTY environments (CI) ignore colour codes naturally; no detection logic added.

---

## §5 Error Handling & Edge Cases

### sync-config.sh failure modes

| Scenario | Behaviour | Exit |
|----------|-----------|------|
| `CLAUDE.md` missing | abort: `error: CLAUDE.md not found in repo root` | 2 |
| SHARED markers missing or unpaired | abort: `error: missing <!-- SHARED:START --> or <!-- SHARED:END --> in CLAUDE.md` | 2 |
| Markers present but empty content | abort: `error: SHARED block is empty in CLAUDE.md` | 2 |
| Multiple SHARED:START or SHARED:END markers | abort: `error: expected exactly one SHARED:START and one SHARED:END` | 2 |
| `templates/agents-preamble.md` or `gemini-preamble.md` missing | abort: `error: templates/<file> missing — reinstall toolkit` | 2 |
| Write fails (permission / disk) | bash strict mode aborts; `.new` temp file left for inspection | 1 |

**Principle**: sync failures are loud. Never silently emit a degraded file, never "best-effort" fall back.

### Doctor edge cases

| Scenario | Behaviour |
|----------|-----------|
| Not inside a git repo | (iii) skipped with note "not a git repo, skipping core.fileMode check"; other 4 checks proceed |
| `git config core.fileMode` unset (empty) | git default is true, treated as failure; repair will set false |
| `python3` missing | (v) fails with hint to install python3; does not chain to python-docx test |
| `python3` present but `import docx` fails | (v) fails with hint `pip install python-docx`; no venv vs system distinction |
| `mktemp -d` fails | (iv) fails with hint disk full / permission |

### Repair edge cases

| Scenario | Behaviour |
|----------|-----------|
| Partial symlink success (e.g. 7/8 fixed, 8th fails) | continue fixing the rest; report aggregate at end; overall exit 1 |
| `git config` write fails | report fail, continue; aggregate at end |
| sync fails | repair aborts entirely (sync failure means structural issue, no point continuing) |
| Already healthy | each fix function is idempotent: detects correct state and skips; ends with "all checks pass" |

### Makefile edge cases

| Scenario | Behaviour |
|----------|-----------|
| `$(EDITOR)` unset (`make init`) | fall back to `vi`; if missing, abort with "please set $EDITOR" |
| `make` not in PATH | shell error, no special handling |
| `make init` in CI | detect `[[ -t 0 ]]`, non-interactive aborts: "make init requires a tty" |
| `make` with no args | defaults to `help`, no side effects |

### Migration of the existing repo (one-shot, performed during implementation)

Current `AGENTS.md` and `GEMINI.md` carry platform preamble content (header + Skill Discovery section) that is not in `CLAUDE.md`. Exact line counts vary, so the migration extracts by **structural marker**, not by line number:

1. From `AGENTS.md`, copy **everything from the start of file up to (but not including) the line `## Project Overview`** into `templates/agents-preamble.md`. Add the `<!-- GENERATED FROM CLAUDE.md ... -->` notice as shown in §3.
2. From `GEMINI.md`, do the same: copy up to the `## Project Overview` line into `templates/gemini-preamble.md`.
3. In `CLAUDE.md`: insert `<!-- SHARED:START -->` on its own line immediately **above** `## Project Overview`; insert `<!-- SHARED:END -->` on its own line immediately **after** the last line of `## Writing Principles`. (Both markers must be standalone-line per §3 marker constraint.)
4. Run `scripts/sync-config.sh` — `AGENTS.md` and `GEMINI.md` are overwritten.
5. `git diff` to verify the only changes are: CLAUDE.md gains markers, AGENTS.md/GEMINI.md preambles unchanged + body now matches CLAUDE.md SHARED block, two new template files added → commit.

This migration is performed by the implementer once, not by an end-user `make` command.

### CI / automation usage

- doctor exit codes are CI-suitable (0 / 1)
- sync can serve as a CI gate: `make sync && git diff --exit-code AGENTS.md GEMINI.md`
- repair is not for CI (write actions)
- init is not for CI (requires tty)

### YAGNI — NOT handled

- Concurrent writes (two sessions running sync simultaneously) — filesystem-level, no lock added
- Partial download / corrupted repo — doctor reports `templates/` missing, no self-heal attempt
- User-customised SHARED marker names — hard-coded `SHARED:START` / `SHARED:END`
- `make uninstall` — user runs `rm -rf` themselves

---

## §6 Testing & Acceptance

### Testing scope

D does not add CI infrastructure (that belongs to A). D provides:

1. **Manual acceptance checklist** — implementer / reviewer runs through it
2. **Callable test hooks** — `scripts/test-foolproofing.sh` invokes the check functions; sub-project A's GitHub Actions can call it later

### Manual acceptance tests

| # | Test | Expected |
|---|------|----------|
| **T1** | Fresh-clone simulation in `$(mktemp -d)` | `make setup` exits 0; `make doctor` all green; `git status` empty |
| **T2** | Symlink corruption: `rm -rf .agents/skills/note && mkdir .agents/skills/note && cp .claude/skills/note/SKILL.md .agents/skills/note/` | `make doctor` (i+ii) red; `make repair` fixes; `make doctor` green |
| **T3** | Sync drift: edit `AGENTS.md` to add a stray line | `make doctor` (iv) red; `make repair` restores; `git diff` empty |
| **T4** | CLAUDE.md edit propagation: change Ch1 target 5,000 → 6,000 | `make sync` updates AGENTS.md and GEMINI.md; all three files contain `Ch1 \| Introduction \| 6,000` |
| **T5** | Marker missing: delete `<!-- SHARED:START -->` from CLAUDE.md | `make sync` exits 2 with "missing SHARED:START" |
| **T6** | Dependency missing: `PATH=$(echo $PATH | sed 's|/opt/homebrew/bin:||')` to hide pandoc | `make doctor` (v) red, hint includes `brew install pandoc` |
| **T7** | `make init` editor: `EDITOR=true make init` (`true` substitutes for vi, exits immediately) | exits 0; CLAUDE.md unchanged; `make sync` runs automatically |
| **T8** | Idempotency: run `make sync` twice in a row | second run leaves `git diff` empty |
| **T9** | CI mode: `< /dev/null make init` | aborts with "make init requires a tty" |
| **T10** | core.fileMode: `git config --unset core.fileMode` | `make doctor` (iii) red; `make repair` sets false; `make doctor` green |

### Acceptance criteria (testable form of §1 success criteria)

| Criterion | Test |
|-----------|------|
| Fresh clone + setup + doctor in three commands | T1 |
| One `make sync` aligns three files after CLAUDE.md edit | T4 |
| Symlink / mode drift detected and repaired | T2, T10 |
| `git status` empty after setup | T1 |
| **CLAUDE.md content discipline** (§1 constraint) | One-time human review during D's PR: confirm CLAUDE.md contains only project-level metadata. Not enforced as an automated CI gate (would belong to A if ever needed) |

### Deliverables checklist

**New**:
- `Makefile`
- `.gitattributes`
- `scripts/sync-config.sh`, `doctor.sh`, `repair.sh`, `lib.sh`, `test-foolproofing.sh`
- `templates/agents-preamble.md`, `gemini-preamble.md`
- `docs/superpowers/specs/2026-04-26-foolproofing-design.md` (this spec)

**Modified**:
- `CLAUDE.md` (insert SHARED markers, neutralise wording, add canonicality note)
- `AGENTS.md`, `GEMINI.md` (become generated artefacts with GENERATED comment)
- `README.md` (First Run Checklist + ZIP-download warning)
- `docs/setup-claude-code.md`, `setup-codex-cli.md`, `setup-gemini-cli.md` (mention `make setup` / `make doctor`)

**Untouched**:
- `.gitignore`
- `.cursor/rules/`
- Any `.claude/skills/*/SKILL.md`

### Explicitly out of D scope (avoid scope creep)

- ❌ GitHub Actions / CI workflow files (→ A)
- ❌ Skill-internal logic tests (→ A)
- ❌ Citation format checking (→ C, as `/audit` enhancement)
- ❌ Pre-commit hook to auto-sync (→ future backlog; users running `make sync` manually is acceptable for now)
- ❌ Multi-language templates (→ future)

---

## §7 Implementation notes (from external review)

These do not change the design but should be applied during implementation:

1. **Per-target `mktemp` for atomicity** — instead of `> AGENTS.md.new` literal name (which can collide with stale files from a crashed prior run), use `mktemp` per target file inside `$OUTDIR` and `mv` to the final name. Already partially folded into §3 algorithm; implementer should verify the trap-cleanup semantics on early exit.
2. **Explicit git-repo guard for check (iii)** — §5 says "not in a git repo → skip (iii)" but §4 algorithm does not encode the guard. Implement check (iii) as: first `git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { warn "not a git repo, skipping core.fileMode check"; return 0; }`, then proceed with the `git config` test.
3. **Derive 8 skill names from `.claude/skills/` instead of hard-coding** — the loop in check (i+ii) and in repair currently lists `audit export integrate map note progress read verify` literally. When sub-project B adds a new skill, this list must be hand-edited or coverage silently drops. Replace with: `mapfile -t SKILL_NAMES < <(cd .claude/skills && find . -maxdepth 1 -mindepth 1 -type d -printf '%f\n' | sort)` (or `ls -1 .claude/skills/` with safe parsing). This makes foolproofing self-extending.

## Roadmap context

D is the first of four planned sub-projects:

| Order | Sub-project | Why this order |
|-------|-------------|----------------|
| **D** (now) | Foolproofing & multi-platform robustness | Cheapest, eliminates real distribution risk (today's symlink incident is the trigger) |
| **A** (next) | CI & tests | Safety net before adding new skills (B) or modifying existing ones (C) |
| **C** (then) | Skill polish — including `/audit` citation enhancement | Sharpen the eight skills already shipped before expanding surface area |
| **B** (last) | New skills | New surface benefits from A's CI |

After D's spec is reviewed and implemented, an external project audit (Codex + superpowers review) will run before starting A.
