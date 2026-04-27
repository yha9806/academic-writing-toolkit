#!/usr/bin/env bash
# scripts/repair.sh — apply idempotent fixes for issues flagged by doctor.sh.
# Re-runs doctor at the end to confirm the result.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/lib.sh"

header "Repairing academic-writing-toolkit environment..."
header ""

if [[ ! -d .claude/skills ]]; then
    die ".claude/skills/ directory missing — are you in the toolkit root?"
fi

# Derive skill names (matches doctor.sh)
SKILL_NAMES=()
while IFS= read -r -d '' name; do
    SKILL_NAMES+=("$(basename "$name")")
done < <(find .claude/skills -maxdepth 1 -mindepth 1 -type d -print0 | sort -z)

# --- Fix (i+ii): rebuild any broken symlinks ---------------------------------
mkdir -p .agents/skills
if [[ ${#SKILL_NAMES[@]} -eq 0 ]]; then
    warn ".claude/skills/ has no skill subdirectories — nothing to symlink"
    hint "reinstall the toolkit"
else
    rebuilt=0
    for n in "${SKILL_NAMES[@]}"; do
        if ! { test -L ".agents/skills/$n" && \
               [[ "$(readlink ".agents/skills/$n")" == "../../.claude/skills/$n" ]]; }; then
            if [[ -e ".agents/skills/$n" && ! -L ".agents/skills/$n" ]]; then
                warn ".agents/skills/$n exists but is not a symlink; replacing"
            fi
            rm -rf ".agents/skills/$n"
            ln -s "../../.claude/skills/$n" ".agents/skills/$n"
            rebuilt=$((rebuilt+1))
        fi
    done
    if [[ $rebuilt -gt 0 ]]; then
        ok "rebuilt $rebuilt skill symlink(s)"
    else
        ok "symlinks already intact (no action)"
    fi
fi

# --- Fix (iii): set git core.fileMode false ----------------------------------
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    fileMode=$(git config --get core.fileMode || true)
    if [[ "$fileMode" != "false" ]]; then
        git config core.fileMode false
        ok "set git core.fileMode = false (local repo only)"
    else
        ok "git core.fileMode already false"
    fi
else
    warn "not in a git repo; skipping core.fileMode fix"
fi

# --- Fix (iv): re-sync AGENTS.md and GEMINI.md -------------------------------
header ""
header "Re-syncing AGENTS.md / GEMINI.md..."
if ! bash "$SCRIPT_DIR/sync-config.sh"; then
    die "sync-config.sh failed — fix CLAUDE.md markers before re-running repair"
fi

# --- Fix (v): system deps — print hints only, never auto-install -------------
if ! command -v pandoc >/dev/null 2>&1 || \
   ! command -v python3 >/dev/null 2>&1 || \
   ! python3 -c "import docx" >/dev/null 2>&1; then
    header ""
    warn "system dependencies missing — install manually:"
    hint "macOS:        brew install pandoc && pip install python-docx"
    hint "Debian/Ubuntu: apt install pandoc python3 python3-pip && pip install python-docx"
fi

# --- Re-run doctor to confirm -------------------------------------------------
header ""
header "Re-running doctor:"
exec bash "$SCRIPT_DIR/doctor.sh"
