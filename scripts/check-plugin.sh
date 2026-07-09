#!/usr/bin/env bash
# scripts/check-plugin.sh
#
# Validates the local Codex plugin package before publishing or marketplace use.
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib.sh"

PLUGIN_ROOT="$REPO_ROOT/plugins/academic-writing-toolkit"
PLUGIN_JSON="$PLUGIN_ROOT/.codex-plugin/plugin.json"
MARKETPLACE_JSON="$REPO_ROOT/.agents/plugins/marketplace.json"

find_python() {
    if [[ -n "${PYTHON:-}" ]]; then
        "$PYTHON" -c 'import sys' >/dev/null 2>&1 || die "PYTHON is set but not usable: $PYTHON"
        printf '%s\n' "$PYTHON"
        return 0
    fi
    local candidate
    for candidate in python3 python; do
        if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys' >/dev/null 2>&1; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    die "missing usable Python interpreter; set PYTHON=/path/to/python"
}

PYTHON_BIN="$(find_python)"

[[ -f "$PLUGIN_JSON" ]] || die "missing plugin manifest: $PLUGIN_JSON"
[[ -f "$MARKETPLACE_JSON" ]] || die "missing marketplace manifest: $MARKETPLACE_JSON"

PYTHON="$PYTHON_BIN" bash "$SCRIPT_DIR/sync-plugin.sh" --check >/dev/null

"$PYTHON_BIN" -m json.tool "$PLUGIN_JSON" >/dev/null
"$PYTHON_BIN" -m json.tool "$MARKETPLACE_JSON" >/dev/null

"$PYTHON_BIN" - "$PLUGIN_JSON" "$MARKETPLACE_JSON" <<'PY'
import json
import sys
from pathlib import Path

plugin_path = Path(sys.argv[1])
marketplace_path = Path(sys.argv[2])
plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

name = "academic-writing-toolkit"
if plugin.get("name") != name:
    raise SystemExit("plugin name must be academic-writing-toolkit")
if plugin.get("skills") != "./skills/":
    raise SystemExit("plugin skills path must be ./skills/")
if "hooks" in plugin or "mcpServers" in plugin or "apps" in plugin:
    raise SystemExit("plugin manifest should not reference absent hooks, MCP, or app manifests")

interface = plugin.get("interface")
if not isinstance(interface, dict):
    raise SystemExit("plugin interface must be an object")
for field in [
    "displayName",
    "shortDescription",
    "longDescription",
    "developerName",
    "category",
    "defaultPrompt",
    "websiteURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "composerIcon",
    "logo",
    "screenshots",
]:
    if not interface.get(field):
        raise SystemExit(f"plugin interface.{field} is required")
if len(interface.get("defaultPrompt", [])) > 3:
    raise SystemExit("plugin interface.defaultPrompt must contain at most 3 entries")

for field in ["composerIcon", "logo"]:
    value = interface[field]
    if not isinstance(value, str) or not value.startswith("./assets/") or not value.endswith(".png"):
        raise SystemExit(f"plugin interface.{field} must point to a PNG under ./assets/")

screenshots = interface["screenshots"]
if not isinstance(screenshots, list) or not 1 <= len(screenshots) <= 3:
    raise SystemExit("plugin interface.screenshots must contain 1-3 PNG paths")
for screenshot in screenshots:
    if not isinstance(screenshot, str) or not screenshot.startswith("./assets/") or not screenshot.endswith(".png"):
        raise SystemExit("plugin screenshots must be PNG files under ./assets/")

entries = [entry for entry in marketplace.get("plugins", []) if entry.get("name") == name]
if len(entries) != 1:
    raise SystemExit("marketplace must contain exactly one academic-writing-toolkit entry")
entry = entries[0]
if entry.get("source", {}).get("path") != "./plugins/academic-writing-toolkit":
    raise SystemExit("marketplace source.path is incorrect")
policy = entry.get("policy", {})
if policy.get("installation") != "AVAILABLE":
    raise SystemExit("marketplace policy.installation must be AVAILABLE")
if policy.get("authentication") != "ON_INSTALL":
    raise SystemExit("marketplace policy.authentication must be ON_INSTALL")
if not entry.get("category"):
    raise SystemExit("marketplace category is required")
PY

"$PYTHON_BIN" - "$PLUGIN_ROOT" "$PLUGIN_JSON" <<'PY'
import json
import struct
import sys
from pathlib import Path

plugin_root = Path(sys.argv[1])
plugin = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
interface = plugin["interface"]
assets = [interface["composerIcon"], interface["logo"], *interface["screenshots"]]

for asset in assets:
    relative_asset = asset[2:] if asset.startswith("./") else asset
    path = plugin_root / relative_asset
    if not path.is_file():
        raise SystemExit(f"missing asset: {asset}")
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise SystemExit(f"asset is not a PNG: {asset}")
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise SystemExit(f"asset has invalid PNG header: {asset}")
    width, height = struct.unpack(">II", data[16:24])
    if width < 64 or height < 64:
        raise SystemExit(f"asset is too small: {asset}")
PY

if grep -R "\[TODO\]\|TODO:" "$PLUGIN_ROOT" "$MARKETPLACE_JSON" >/dev/null; then
    die "plugin package contains TODO placeholders"
fi

for skill in audit evidence-review export human-eval-handoff-repair integrate logic-review manuscript-reframe map note progress read release-governance revision-escalation style thesis-control verify verify-refs; do
    [[ -f "$PLUGIN_ROOT/skills/$skill/SKILL.md" ]] || die "missing plugin skill: $skill"
done

"$PYTHON_BIN" "$PLUGIN_ROOT/skills/audit/scripts/audit-citations.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/style/scripts/audit-british-english.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/logic-review/scripts/audit-logic.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/verify-refs/scripts/verify-refs.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/export/scripts/convert_to_docx.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/evidence-review/scripts/check_review_package.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/release-governance/scripts/check_release_packet.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/thesis-control/scripts/check_thesis_control.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/thesis-control/scripts/scaffold_thesis_control.py" --help >/dev/null
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/thesis-control/scripts/upgrade_thesis_control_revision_tracking.py" --help >/dev/null

ok "plugin package validates"
