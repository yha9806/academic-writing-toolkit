#!/usr/bin/env python3
"""Opt-in, public-fixture model checks. Default: plan only, no model requests."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from awt.mvp import MvpError, WORKFLOWS, analyse_document
from awt.providers import ProviderError, load_provider_config


FIXTURE = b"""# Fictional writing-support pilot

Twelve volunteer students used a reading-note checklist for one week.
Six students reported that their notes were easier to organise. No control
group, random allocation, or independent writing-quality rating was used.
The pilot proves that the checklist improves academic writing for all students.
No additional evidence files or bibliography are supplied with this fixture.
"""
FIELDS = {
    "provider": "AWT_PROVIDER", "model": "AWT_MODEL", "base_url": "AWT_BASE_URL",
    "protocol": "AWT_PROTOCOL", "api_key_env": "AWT_API_KEY_ENV",
    "response_format": "AWT_RESPONSE_FORMAT", "max_output_tokens": "AWT_MAX_OUTPUT_TOKENS",
    "timeout_seconds": "AWT_REQUEST_TIMEOUT",
    "supports_images": "AWT_SUPPORTS_IMAGES",
}


def read_profiles(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("profiles"), list):
        raise ValueError("Profiles require schema_version=1 and a profiles list.")
    names = set()
    for profile in value["profiles"]:
        if not isinstance(profile, dict) or set(profile) - ({"name"} | set(FIELDS)):
            raise ValueError("Unknown profile fields; credentials must be environment-variable names only.")
        name = profile.get("name")
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError("Profile names must be nonempty and unique.")
        names.add(name)
        if not profile.get("provider") or not profile.get("model"):
            raise ValueError("Each profile must explicitly name a provider and a model.")
        if any(type(item) not in (str, int) for item in profile.values()):
            raise ValueError("Profile values must be strings or integers.")
        load_provider_config(profile_environment(profile))
    if not names:
        raise ValueError("At least one profile is required.")
    return value["profiles"]


def profile_environment(profile: dict) -> dict[str, str]:
    return {target: str(profile[source]) for source, target in FIELDS.items() if source in profile}


@contextmanager
def use_profile(profile: dict):
    # Sequential runner: preserve real key variables, replace only AWT routing.
    previous = {key: os.environ.get(key) for key in FIELDS.values()}
    try:
        for key in FIELDS.values():
            os.environ.pop(key, None)
        os.environ.update(profile_environment(profile))
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=Path, default=Path(__file__).resolve().parents[1] / "examples/model-compatibility/profiles.json")
    parser.add_argument("--only", action="append", help="run only this profile name; repeat for several profiles")
    parser.add_argument("--live", action="store_true", help="send the fixed fictional fixture; provider charges may apply")
    parser.add_argument("--all-workflows", action="store_true", help="five requests per profile instead of one accuracy check")
    parser.add_argument("--output", type=Path, help="write a new report file; existing files are not overwritten")
    args = parser.parse_args()
    try:
        profiles = read_profiles(args.profiles)
        if args.only:
            if set(args.only) - {profile["name"] for profile in profiles}:
                parser.error("--only names a profile absent from the profile file")
            profiles = [profile for profile in profiles if profile["name"] in args.only]
        if args.output and args.output.exists():
            parser.error("--output already exists; choose a new report path")
    except (OSError, ValueError, ProviderError) as error:
        parser.error(str(error))
    workflows = list(WORKFLOWS) if args.all_workflows else ["audit"]
    report = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "live_public_fixture" if args.live else "dry_run",
        "fixture_sha256": hashlib.sha256(FIXTURE).hexdigest(),
        "planned_requests": len(profiles) * len(workflows),
        "writing_effect_proven": False,
        "scope": "Output schema, evidence-reference bindings, and copy-protection contracts. No human writing-quality evaluation.",
        "results": [],
    }
    failed = False
    for profile in profiles:
        config = load_provider_config(profile_environment(profile))
        for workflow in workflows:
            row = {"profile": profile["name"], "workflow": workflow, "configuration": config.public_metadata(), "status": "not_run"}
            if args.live:
                try:
                    with use_profile(profile):
                        analysis = analyse_document(FIXTURE, "public-fictional-pilot.md", workflow, "preprint")
                    row.update(status="output_contract_passed", model_run=analysis["model_run"], review_status=analysis["result"]["status"], review=analysis["result"], source_unchanged=analysis["source_unchanged"])
                except (MvpError, ProviderError, OSError) as error:
                    failed = True
                    row.update(status="failed", error=str(error))
            report["results"].append(row)
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as output:
            output.write(encoded)
    else:
        print(encoded, end="")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
