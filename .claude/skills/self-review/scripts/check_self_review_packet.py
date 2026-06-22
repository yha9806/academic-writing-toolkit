#!/usr/bin/env python3
"""Validate clean-room self-review packets."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PureWindowsPath
from typing import Dict, List


REQUIRED_FORBIDDEN = {
    "prior_chat_memory",
    "unstated_project_assumptions",
    "model_background_knowledge_as_evidence",
    "unpublished_notes_not_listed_in_manifest",
}


def issue(kind: str, severity: str, location: str, message: str) -> Dict[str, str]:
    return {
        "kind": kind,
        "severity": severity,
        "location": location,
        "message": message,
    }


def normalise_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def parse_simple_yaml(path: Path) -> tuple[Dict[str, object], List[Dict[str, str]]]:
    issues: List[Dict[str, str]] = []
    data: Dict[str, object] = {}
    current_key = ""
    text = path.read_text(encoding="utf-8-sig")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if re.match(r"(?i)api[_-]?key\s*:", stripped) and "api_key_env_var" not in stripped:
            issues.append(issue("secret-in-manifest", "critical", f"{path}:{line_no}", "store API key values in environment variables, not the manifest"))
        if re.search(r"(?i)(sk-[A-Za-z0-9_-]{12,}|AIza[0-9A-Za-z_-]{20,}|api[_-]?key\s*:\s*['\"]?[A-Za-z0-9_-]{16,})", stripped):
            issues.append(issue("possible-secret-in-manifest", "critical", f"{path}:{line_no}", "manifest appears to contain a credential-like value"))
        if stripped.startswith("- "):
            if not current_key:
                issues.append(issue("yaml-list-without-key", "high", f"{path}:{line_no}", "list item has no parent key"))
                continue
            value = stripped[2:].strip().strip("'\"")
            data.setdefault(current_key, [])
            if isinstance(data[current_key], list):
                data[current_key].append(value)
            else:
                issues.append(issue("yaml-type-conflict", "high", f"{path}:{line_no}", f"{current_key} cannot be both scalar and list"))
            continue
        if ":" not in stripped:
            issues.append(issue("yaml-parse-warning", "medium", f"{path}:{line_no}", "expected key: value or key:"))
            continue
        key, value = stripped.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value:
            data[current_key] = value.strip("'\"")
        else:
            data[current_key] = []
    return data, issues


def is_abs_path(value: str) -> bool:
    path = Path(value)
    win = PureWindowsPath(value)
    return path.is_absolute() or win.is_absolute()


def list_value(data: Dict[str, object], key: str) -> List[str]:
    value = data.get(key, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def validate_packet(packet_dir: Path) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    manifest = packet_dir / "review_manifest.yaml"
    if not manifest.is_file():
        alt = packet_dir / "review_manifest.yml"
        if alt.is_file():
            manifest = alt
        else:
            return [issue("missing-manifest", "high", str(packet_dir), "review_manifest.yaml is required")]

    try:
        data, parse_issues = parse_simple_yaml(manifest)
        issues.extend(parse_issues)
    except UnicodeDecodeError:
        return [issue("manifest-decode-error", "high", str(manifest), "manifest is not valid UTF-8")]

    mode = str(data.get("review_mode", "")).strip()
    if mode != "self_review_clean_room":
        issues.append(issue("invalid-review-mode", "high", "review_manifest.yaml:review_mode", "review_mode must be self_review_clean_room"))

    allowed = list_value(data, "allowed_sources")
    forbidden = list_value(data, "forbidden_sources")
    if not allowed:
        issues.append(issue("missing-allowed-sources", "high", "review_manifest.yaml:allowed_sources", "at least one allowed source is required"))
    if not forbidden:
        issues.append(issue("missing-forbidden-sources", "high", "review_manifest.yaml:forbidden_sources", "forbidden sources must be explicit"))

    forbidden_tokens = {normalise_token(item) for item in forbidden}
    missing_forbidden = sorted(REQUIRED_FORBIDDEN - forbidden_tokens)
    if missing_forbidden:
        issues.append(issue("missing-required-forbidden-source", "high", "review_manifest.yaml:forbidden_sources", "missing: " + ", ".join(missing_forbidden)))

    for source in allowed:
        token = normalise_token(source)
        if token in REQUIRED_FORBIDDEN:
            issues.append(issue("forbidden-source-allowed", "critical", f"review_manifest.yaml:allowed_sources:{source}", "forbidden source appears in allowed_sources"))
        if is_abs_path(source):
            issues.append(issue("absolute-source-path", "medium", f"review_manifest.yaml:allowed_sources:{source}", "allowed sources should be relative packet paths"))
            continue
        candidate = packet_dir / source
        if source.endswith("/"):
            if not candidate.is_dir():
                issues.append(issue("allowed-directory-missing", "high", f"review_manifest.yaml:allowed_sources:{source}", "listed directory does not exist"))
        elif not candidate.is_file() and not candidate.is_dir():
            issues.append(issue("allowed-source-missing", "high", f"review_manifest.yaml:allowed_sources:{source}", "listed source does not exist"))

    report = packet_dir / "self_review_report.md"
    if report.is_file():
        text = report.read_text(encoding="utf-8", errors="replace")
        for heading in ["Supported By Packet", "Not Supported By Packet", "Reviewer-Risk Inference"]:
            if heading not in text and heading.replace("By", "by") not in text:
                issues.append(issue("report-missing-section", "medium", f"self_review_report.md:{heading}", "clean-room report should keep findings separated"))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a clean-room self-review packet.")
    parser.add_argument("packet_dir", help="Directory containing review_manifest.yaml")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()

    packet_dir = Path(args.packet_dir)
    if not packet_dir.is_dir():
        sys.stderr.write("error: packet_dir is not a directory\n")
        return 2

    issues = validate_packet(packet_dir)
    payload = {
        "schema_version": 1,
        "packet_dir": str(packet_dir),
        "issue_count": len(issues),
        "issues": issues,
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for item in issues:
            print("{severity}: {location}: {kind}: {message}".format(**item))
        if not issues:
            print("self-review packet is clean-room valid")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
