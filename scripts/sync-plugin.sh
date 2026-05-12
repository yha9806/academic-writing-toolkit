#!/usr/bin/env bash
# scripts/sync-plugin.sh [--check]
#
# Regenerates the Codex plugin's skills from .claude/skills, then applies the
# small path adaptations needed for a self-contained plugin package.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

MODE="${1:-sync}"
if [[ "$MODE" != "sync" && "$MODE" != "--check" ]]; then
    die "usage: scripts/sync-plugin.sh [--check]"
fi

PLUGIN_ROOT="$REPO_ROOT/plugins/academic-writing-toolkit"
PLUGIN_SKILLS="$PLUGIN_ROOT/skills"
SOURCE_SKILLS="$REPO_ROOT/.claude/skills"

[[ -d "$SOURCE_SKILLS" ]] || die "missing canonical skills directory: $SOURCE_SKILLS"
[[ -f "$PLUGIN_ROOT/.codex-plugin/plugin.json" ]] || die "missing plugin manifest: $PLUGIN_ROOT/.codex-plugin/plugin.json"

copy_helper() {
    local source="$1"
    local dest="$2"
    [[ -f "$source" ]] || die "missing helper script: $source"
    mkdir -p "$(dirname "$dest")"
    cp "$source" "$dest"
}

remove_python_caches() {
    local root="$1"
    find "$root" -type d -name "__pycache__" -prune -exec rm -rf {} +
    find "$root" -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete
}

generate_skills() {
    local dest="$1"
    rm -rf "$dest"
    mkdir -p "$dest"
    cp -R "$SOURCE_SKILLS/." "$dest/"
    remove_python_caches "$dest"

    copy_helper "$REPO_ROOT/scripts/audit-citations.py" "$dest/audit/scripts/audit-citations.py"
    copy_helper "$REPO_ROOT/scripts/audit-british-english.py" "$dest/style/scripts/audit-british-english.py"
    copy_helper "$REPO_ROOT/scripts/audit-logic.py" "$dest/logic-review/scripts/audit-logic.py"
    copy_helper "$REPO_ROOT/scripts/verify-refs.py" "$dest/verify-refs/scripts/verify-refs.py"

    python3 - "$dest" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])

def replace(relative_path: str, old: str, new: str) -> None:
    path = root / relative_path
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new), encoding="utf-8")

replace(
    "audit/SKILL.md",
    "   Run `python3 scripts/audit-citations.py --base-dir . --style $(grep -oP '(?<=Citation style: )\\S+' CLAUDE.md) --json` and parse the JSON output. The script implements four tiers:",
    "   Resolve the bundled helper at `scripts/audit-citations.py` relative to this `SKILL.md`, then run it from the project root:\n\n"
    "   `python3 {skill_dir}/scripts/audit-citations.py --base-dir . --style $(grep -oP '(?<=Citation style: )\\S+' CLAUDE.md) --json`\n\n"
    "   Parse the JSON output. The script implements four tiers:",
)
replace(
    "audit/SKILL.md",
    "   See `docs/skills/06-audit.md` and `python3 scripts/audit-citations.py --help` for the public citation-audit interface and supported styles.",
    "   Use `python3 {skill_dir}/scripts/audit-citations.py --help` for the public citation-audit interface and supported styles.",
)
replace(
    "style/SKILL.md",
    "1. Run:\n   `python3 scripts/audit-british-english.py --base-dir . --json`",
    "1. Resolve the bundled helper at `scripts/audit-british-english.py` relative to this `SKILL.md`, then run it from the project root:\n"
    "   `python3 {skill_dir}/scripts/audit-british-english.py --base-dir . --json`",
)
replace(
    "style/SKILL.md",
    "   `python3 scripts/audit-british-english.py --base-dir . --fix`",
    "   `python3 {skill_dir}/scripts/audit-british-english.py --base-dir . --fix`",
)
replace(
    "logic-review/SKILL.md",
    "1. Run:\n   `python3 scripts/audit-logic.py --base-dir . --json`",
    "1. Resolve the bundled helper at `scripts/audit-logic.py` relative to this `SKILL.md`, then run it from the project root:\n"
    "   `python3 {skill_dir}/scripts/audit-logic.py --base-dir . --json`",
)
replace(
    "verify-refs/SKILL.md",
    "2. Run:\n   `python3 scripts/verify-refs.py --bib {path} --json`",
    "2. Resolve the bundled helper at `scripts/verify-refs.py` relative to this `SKILL.md`, then run it from the project root:\n"
    "   `python3 {skill_dir}/scripts/verify-refs.py --bib {path} --json`",
)
replace(
    "verify-refs/SKILL.md",
    "   `python3 scripts/verify-refs.py --bib {path} --json --online`",
    "   `python3 {skill_dir}/scripts/verify-refs.py --bib {path} --json --online`",
)
replace(
    "export/SKILL.md",
    "   python .claude/skills/export/scripts/convert_to_docx.py \\",
    "   python {skill_dir}/scripts/convert_to_docx.py \\",
)
PY
}

if [[ "$MODE" == "--check" ]]; then
    tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' EXIT
    generate_skills "$tmp/skills"
    if diff -ru "$tmp/skills" "$PLUGIN_SKILLS"; then
        ok "plugin skills are synced"
        exit 0
    fi
    die "plugin skills drifted; run make plugin-sync"
fi

generate_skills "$PLUGIN_SKILLS"
ok "synced plugin skills from .claude/skills"
