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
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

plugin_path = Path(sys.argv[1])
marketplace_path = Path(sys.argv[2])
plugin = json.loads(plugin_path.read_text(encoding="utf-8"))
marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))

name = "academic-writing-toolkit"
if plugin.get("name") != name:
    raise SystemExit("plugin name must be academic-writing-toolkit")
if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name):
    raise SystemExit("plugin name must satisfy final directory format and length limits")
version = plugin.get("version", "")
if not re.fullmatch(
    r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
    version,
):
    raise SystemExit("plugin version must be valid SemVer")
if len(version) > 64:
    raise SystemExit("plugin version must contain at most 64 characters")
description = plugin.get("description")
if not isinstance(description, str) or not description or len(description) > 1024:
    raise SystemExit("plugin description must contain 1-1024 characters")
author = plugin.get("author")
if not isinstance(author, dict):
    raise SystemExit("plugin author must be an object")
author_name = author.get("name")
if (
    not isinstance(author_name, str)
    or not author_name
    or "\n" in author_name
    or len(author_name) > 120
):
    raise SystemExit("plugin author.name must contain 1-120 single-line characters")
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
    "supportURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
    "composerIcon",
    "logo",
]:
    if not interface.get(field):
        raise SystemExit(f"plugin interface.{field} is required")
short_description = interface["shortDescription"]
if (
    not isinstance(short_description, str)
    or not short_description
    or "\n" in short_description
    or len(short_description) > 30
):
    raise SystemExit(
        "plugin interface.shortDescription must contain 1-30 single-line characters"
    )

display_name = interface["displayName"]
if (
    not isinstance(display_name, str)
    or not display_name
    or "\n" in display_name
    or len(display_name) > 30
):
    raise SystemExit(
        "plugin interface.displayName must contain 1-30 single-line characters"
    )

long_description = interface["longDescription"]
if (
    not isinstance(long_description, str)
    or not long_description
    or len(long_description) > 4000
):
    raise SystemExit("plugin interface.longDescription must contain 1-4000 characters")

developer_name = interface["developerName"]
if (
    not isinstance(developer_name, str)
    or not developer_name
    or "\n" in developer_name
    or len(developer_name) > 80
):
    raise SystemExit(
        "plugin interface.developerName must contain 1-80 single-line characters"
    )
if developer_name != author_name:
    raise SystemExit("plugin author.name and interface.developerName must match")

allowed_categories = {
    "Productivity",
    "Creativity",
    "Developer Tools",
    "Business & Operations",
    "Data & Analytics",
    "Communication",
    "Education & Research",
    "Security",
    "Finance",
    "Healthcare",
    "Travel",
    "Entertainment",
    "Other",
}
if interface["category"] not in allowed_categories:
    raise SystemExit("plugin interface.category is not supported")

capabilities = interface.get("capabilities")
if not isinstance(capabilities, list) or len(capabilities) > 20:
    raise SystemExit("plugin interface.capabilities must contain at most 20 entries")
for capability in capabilities:
    if (
        not isinstance(capability, str)
        or not capability
        or "\n" in capability
        or len(capability) > 120
    ):
        raise SystemExit(
            "each plugin capability must contain 1-120 single-line characters"
        )

default_prompts = interface["defaultPrompt"]
if not isinstance(default_prompts, list) or not 1 <= len(default_prompts) <= 3:
    raise SystemExit("plugin interface.defaultPrompt must contain 1-3 entries")
normalised_prompts = set()
for prompt in default_prompts:
    if (
        not isinstance(prompt, str)
        or not prompt
        or "\n" in prompt
        or len(prompt) > 128
        or "@" in prompt
    ):
        raise SystemExit(
            "each default prompt must be single-line, mention-free, and 1-128 characters"
        )
    normalised = " ".join(unicodedata.normalize("NFKC", prompt).split()).casefold()
    if normalised in normalised_prompts:
        raise SystemExit("plugin default prompts must be unique after normalisation")
    normalised_prompts.add(normalised)

for field in [
    "homepage",
    "repository",
]:
    value = plugin.get(field)
    parsed = urlparse(value) if isinstance(value, str) else None
    if (
        not parsed
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
    ):
        raise SystemExit(f"plugin {field} must be an HTTPS URL")

author_url = author.get("url")
author_url_parsed = urlparse(author_url) if isinstance(author_url, str) else None
if (
    not author_url_parsed
    or author_url_parsed.scheme != "https"
    or not author_url_parsed.netloc
    or author_url_parsed.username
    or author_url_parsed.password
    or len(author_url) > 1024
):
    raise SystemExit("plugin author.url must be a credential-free HTTPS URL")

for field in [
    "websiteURL",
    "supportURL",
    "privacyPolicyURL",
    "termsOfServiceURL",
]:
    value = interface[field]
    parsed = urlparse(value) if isinstance(value, str) else None
    if (
        not parsed
        or parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or len(value) > 1024
    ):
        raise SystemExit(f"plugin interface.{field} must be an HTTPS URL")

brand_color = interface.get("brandColor")
if brand_color is not None and not re.fullmatch(r"#[0-9A-Fa-f]{6}", brand_color):
    raise SystemExit("plugin interface.brandColor must be a six-digit hex colour")

for field in ["composerIcon", "logo"]:
    value = interface[field]
    if not isinstance(value, str) or not value.startswith("./assets/") or not value.endswith(".png"):
        raise SystemExit(f"plugin interface.{field} must point to a PNG under ./assets/")

if "screenshots" in interface:
    raise SystemExit("skills-only plugins must not declare screenshots")

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
assets = [interface["composerIcon"], interface["logo"]]

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

"$PYTHON_BIN" - "$PLUGIN_ROOT" <<'PY'
import ast
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

plugin_root = Path(sys.argv[1])
skill_paths = sorted((plugin_root / "skills").glob("*/SKILL.md"))
if len(skill_paths) != 20:
    raise SystemExit(f"expected 20 plugin skills, observed {len(skill_paths)}")

for path in skill_paths:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SystemExit(f"missing YAML frontmatter: {path}")
    try:
        frontmatter = text.split("---", 2)[1]
    except IndexError as error:
        raise SystemExit(f"unterminated YAML frontmatter: {path}") from error

    if yaml is not None:
        try:
            metadata = yaml.safe_load(frontmatter)
        except yaml.YAMLError as error:
            raise SystemExit(f"invalid YAML frontmatter in {path}: {error}") from error
    else:
        metadata = {}
        for line_number, line in enumerate(frontmatter.splitlines(), start=2):
            if not line.strip():
                continue
            if line[:1].isspace() or ":" not in line:
                raise SystemExit(
                    f"unsupported YAML frontmatter at {path}:{line_number}"
                )
            key, raw_value = line.split(":", 1)
            raw_value = raw_value.strip()
            if raw_value.startswith(("'", '"')):
                try:
                    value = ast.literal_eval(raw_value)
                except (SyntaxError, ValueError) as error:
                    raise SystemExit(
                        f"invalid quoted YAML scalar at {path}:{line_number}"
                    ) from error
            else:
                if ": " in raw_value:
                    raise SystemExit(
                        f"ambiguous unquoted YAML scalar at {path}:{line_number}"
                    )
                value = raw_value
            metadata[key.strip()] = value

    if not isinstance(metadata, dict):
        raise SystemExit(f"frontmatter must be a mapping: {path}")
    if metadata.get("name") != path.parent.name:
        raise SystemExit(f"skill name does not match directory: {path}")
    description = metadata.get("description")
    if not isinstance(description, str) or not description.strip():
        raise SystemExit(f"skill description is required: {path}")
PY

if grep -R "\[TODO\]\|TODO:" "$PLUGIN_ROOT" "$MARKETPLACE_JSON" >/dev/null; then
    die "plugin package contains TODO placeholders"
fi

for skill in argument-governance audit evidence-review export human-eval-handoff-repair integrate logic-review manuscript-reframe map note peer-review progress read release-governance revision-escalation self-review style thesis-control verify verify-refs; do
    [[ -f "$PLUGIN_ROOT/skills/$skill/SKILL.md" ]] || die "missing plugin skill: $skill"
done

"$PYTHON_BIN" "$PLUGIN_ROOT/skills/argument-governance/scripts/check_argument_governance.py" --help >/dev/null
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
"$PYTHON_BIN" "$PLUGIN_ROOT/skills/self-review/scripts/check_self_review_packet.py" --help >/dev/null

ok "plugin package validates"
