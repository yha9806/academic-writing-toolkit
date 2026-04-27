#!/usr/bin/env bash
# scripts/doctor.sh — read-only health check for academic-writing-toolkit.
# Exits 0 if all checks pass, 1 if any check fails. CI-suitable.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

header "Checking academic-writing-toolkit environment..."
header ""

# Derive expected skill names from .claude/skills/ to avoid hard-coding
# (spec §7 implementation note 3).
if [[ ! -d .claude/skills ]]; then
    fail ".claude/skills/ directory missing"
    hint "are you in the toolkit root?"
    exit 1
fi
SKILL_NAMES=()
while IFS= read -r -d '' name; do
    SKILL_NAMES+=("$(basename "$name")")
done < <(find .claude/skills -maxdepth 1 -mindepth 1 -type d -print0 | sort -z)

# --- Check (i+ii): symlinks intact -------------------------------------------
if [[ ${#SKILL_NAMES[@]} -eq 0 ]]; then
    fail ".claude/skills/ has no skill subdirectories"
    hint "reinstall the toolkit"
else
    local_fails=0
    for n in "${SKILL_NAMES[@]}"; do
        if ! { test -L ".agents/skills/$n" && \
               [[ "$(readlink ".agents/skills/$n")" == "../../.claude/skills/$n" ]]; }; then
            fail "skill symlink broken: .agents/skills/$n"
            local_fails=$((local_fails+1))
        fi
    done
    if [[ $local_fails -eq 0 ]]; then
        pass "symlinks intact (.agents/skills/* -> ../../.claude/skills/*)"
    else
        hint "make repair"
    fi
fi

# --- Check (iii): git core.fileMode is false ---------------------------------
# Spec §7 implementation note 2 — guard with rev-parse.
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fileMode=$(git config --get core.fileMode || true)
    if [[ "$fileMode" == "false" ]]; then
        pass "git core.fileMode disabled (no mode-bit noise commits)"
    else
        fail "git core.fileMode is '$fileMode' (expected: false)"
        hint "make repair  (or: git config core.fileMode false)"
    fi
else
    warn "not in a git repo; skipping core.fileMode check"
fi

# --- Check (iv): CLAUDE.md / AGENTS.md / GEMINI.md in sync -------------------
sync_tmp=$(mktemp -d)
trap 'rm -rf "$sync_tmp"' EXIT
if bash "$SCRIPT_DIR/sync-config.sh" CLAUDE.md "$sync_tmp" >/dev/null 2>&1; then
    if diff -q AGENTS.md "$sync_tmp/AGENTS.md" >/dev/null 2>&1 && \
       diff -q GEMINI.md "$sync_tmp/GEMINI.md" >/dev/null 2>&1; then
        pass "config sync (CLAUDE.md, AGENTS.md, GEMINI.md aligned)"
    else
        fail "config sync — AGENTS.md or GEMINI.md drifted from CLAUDE.md"
        hint "make sync"
    fi
else
    fail "config sync — sync-config.sh refused to run; check CLAUDE.md markers"
    hint "see scripts/sync-config.sh stderr for details"
fi

# --- Check (v): system dependencies ------------------------------------------
deps_ok=true
if command -v pandoc >/dev/null 2>&1; then
    pandoc_v=$(pandoc --version | head -1)
    pass "pandoc available ($pandoc_v)"
else
    fail "pandoc not found"
    hint "macOS: brew install pandoc  |  Debian/Ubuntu: apt install pandoc"
    deps_ok=false
fi
if command -v python3 >/dev/null 2>&1; then
    py_v=$(python3 --version 2>&1)
    pass "python3 available ($py_v)"
    if python3 -c "import docx" >/dev/null 2>&1; then
        pass "python-docx importable"
    else
        fail "python-docx not importable"
        hint "pip install python-docx  (or: pip3 install python-docx)"
        deps_ok=false
    fi
else
    fail "python3 not found"
    hint "macOS: brew install python3  |  Debian/Ubuntu: apt install python3 python3-pip"
    deps_ok=false
fi

# --- Summary ------------------------------------------------------------------
header ""
if [[ $FAILS -eq 0 ]]; then
    pass "all checks pass."
    exit 0
else
    printf "\n%d issue(s). Run \`make repair\` to fix what can be fixed automatically.\n" "$FAILS"
    exit 1
fi
