#!/usr/bin/env bash
# scripts/sync-config.sh [INPUT] [OUTDIR]
#   INPUT   — defaults to CLAUDE.md (the canonical project config)
#   OUTDIR  — defaults to . (repo root); pass a tmpdir for read-only diff checks
#
# Regenerates AGENTS.md and GEMINI.md from CLAUDE.md by combining the
# platform preambles in templates/ with the SHARED block extracted from
# CLAUDE.md (markers must appear as standalone lines).
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

# 1. Validate exactly one marker pair (markers MUST appear alone on their own line)
start_count=$(awk '$0 == "<!-- SHARED:START -->" {n++} END {print n+0}' "$INPUT")
end_count=$(awk '$0 == "<!-- SHARED:END -->" {n++} END {print n+0}' "$INPUT")
if [[ "$start_count" -ne 1 || "$end_count" -ne 1 ]]; then
    die "expected exactly one <!-- SHARED:START --> and one <!-- SHARED:END --> as standalone lines in $INPUT (found start=$start_count end=$end_count)"
fi

# 2. Extract SHARED block (anchored line-equality match excludes markers inside code blocks)
# Note: $(...) strips trailing newlines, so blank lines at the very end of the
# SHARED block are normalised to one. Harmless for markdown.
shared=$(awk '$0 == "<!-- SHARED:START -->" {flag=1; next} $0 == "<!-- SHARED:END -->" {flag=0} flag' "$INPUT")
[[ -n "$shared" ]] || die "SHARED block is empty in $INPUT"

# 3. Generate AGENTS.md and GEMINI.md atomically (write to .new, then mv)
{ cat "$REPO_ROOT/templates/agents-preamble.md"; printf '%s\n' "$shared"; } > "$OUTDIR/AGENTS.md.new"
mv "$OUTDIR/AGENTS.md.new" "$OUTDIR/AGENTS.md"

{ cat "$REPO_ROOT/templates/gemini-preamble.md"; printf '%s\n' "$shared"; } > "$OUTDIR/GEMINI.md.new"
mv "$OUTDIR/GEMINI.md.new" "$OUTDIR/GEMINI.md"

ok "Synced AGENTS.md and GEMINI.md from $INPUT into $OUTDIR"
