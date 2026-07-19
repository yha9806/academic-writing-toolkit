#!/usr/bin/env python3
"""Validate the OpenAI skills-only submission packet and packaged Skills."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


EXPECTED_COVERAGE = {
    "project_intent",
    "argument_levels",
    "evidence_licence",
    "contribution_focus",
    "three_revision_escalation",
}
ALLOWED_FRONTMATTER_KEYS = {
    "name",
    "description",
    "allowed-tools",
    "license",
    "metadata",
}
ALLOWED_NEGATIVE_MODES = {"no_trigger", "refusal", "safe_fallback"}
ALLOWED_ACCOUNT_STATUSES = {"owner_action_required", "confirmed"}
WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)(?:^|[\s\"'])[a-z]:[\\/]")
POSIX_PRIVATE_RE = re.compile(r"(?:^|[\s\"'])(?:/Users/|/home/|/private/)")


class SubmissionError(ValueError):
    """Raised when a submission contract is invalid."""


def fail(message: str) -> None:
    raise SubmissionError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing JSON file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"invalid JSON in {path}: {exc}")
    if not isinstance(payload, dict):
        fail(f"JSON root must be an object: {path}")
    return payload


def require_text(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{location} must be a non-empty string")
    return value.strip()


def require_https_url(value: Any, location: str) -> str:
    text = require_text(value, location)
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc:
        fail(f"{location} must be a public HTTPS URL")
    return text


def parse_frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\r?\n(.*?)\r?\n---(?:\r?\n|$)", text, re.DOTALL)
    if not match:
        fail(f"missing or malformed YAML frontmatter: {path}")
    fields: dict[str, str] = {}
    for line_number, raw_line in enumerate(match.group(1).splitlines(), start=2):
        if not raw_line.strip() or raw_line.startswith((" ", "\t")):
            continue
        key_match = re.match(r"^([A-Za-z0-9_-]+):(?:\s*(.*))?$", raw_line)
        if not key_match:
            fail(f"malformed frontmatter at {path}:{line_number}")
        key, value = key_match.group(1), (key_match.group(2) or "").strip()
        if key in fields:
            fail(f"duplicate frontmatter key {key!r}: {path}")
        fields[key] = value
    unexpected = sorted(set(fields) - ALLOWED_FRONTMATTER_KEYS)
    if unexpected:
        fail(f"unexpected frontmatter key(s) in {path}: {', '.join(unexpected)}")
    for required in ("name", "description"):
        if not fields.get(required):
            fail(f"frontmatter {required} is required: {path}")
    return fields


def validate_skills(plugin_root: Path) -> set[str]:
    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        fail(f"missing skills directory: {skills_root}")
    names: set[str] = set()
    for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir()):
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            fail(f"missing SKILL.md: {skill_dir}")
        fields = parse_frontmatter(skill_file)
        if fields["name"] != skill_dir.name:
            fail(
                f"frontmatter name {fields['name']!r} does not match "
                f"directory {skill_dir.name!r}"
            )
        names.add(skill_dir.name)
    if len(names) != 21:
        fail(f"expected exactly 21 packaged skills, found {len(names)}")
    return names


def validate_fixture(value: Any, location: str) -> None:
    if not isinstance(value, dict):
        fail(f"{location} must be an object")
    if value.get("delivery") != "inline":
        fail(f"{location}.delivery must be inline")
    for field in (
        "attachments_required",
        "authentication_required",
        "contains_private_data",
    ):
        if value.get(field) is not False:
            fail(f"{location}.{field} must be false")


def validate_case_text(case: dict[str, Any], location: str) -> None:
    serialized = json.dumps(case, ensure_ascii=False)
    if WINDOWS_ABSOLUTE_RE.search(serialized) or POSIX_PRIVATE_RE.search(serialized):
        fail(f"{location} contains an absolute or private local path")
    require_text(case.get("user_prompt"), f"{location}.user_prompt")
    expected = case.get("expected_behavior")
    if not isinstance(expected, list) or not expected:
        fail(f"{location}.expected_behavior must be a non-empty list")
    for index, item in enumerate(expected):
        require_text(item, f"{location}.expected_behavior[{index}]")
    validate_fixture(case.get("fixture_data"), f"{location}.fixture_data")


def validate_submission(
    repo_root: Path,
    submission_path: Path,
    manifest_path: Path,
) -> None:
    submission = load_json(submission_path)
    manifest = load_json(manifest_path)
    plugin_root = manifest_path.parent.parent
    skills = validate_skills(plugin_root)

    if submission.get("schema_version") != 1:
        fail("submission.schema_version must be 1")
    if submission.get("submission_type") != "skills_only":
        fail("submission.submission_type must be skills_only")
    if submission.get("plugin_name") != manifest.get("name"):
        fail("submission plugin_name must match the plugin manifest")
    if submission.get("version") != manifest.get("version"):
        fail("submission version must match the plugin manifest")
    require_text(submission.get("release_notes"), "submission.release_notes")

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        fail("manifest.interface must be an object")
    prompts = interface.get("defaultPrompt")
    if not isinstance(prompts, list) or not 1 <= len(prompts) <= 3:
        fail("manifest.interface.defaultPrompt must contain 1-3 prompts")
    for index, prompt in enumerate(prompts):
        prompt_text = require_text(prompt, f"manifest defaultPrompt[{index}]")
        if len(prompt_text) > 128:
            fail(
                f"manifest defaultPrompt[{index}] exceeds 128 characters: "
                f"{len(prompt_text)}"
            )

    listing = submission.get("listing")
    if not isinstance(listing, dict):
        fail("submission.listing must be an object")
    for field in (
        "display_name",
        "short_description",
        "long_description",
        "category",
    ):
        require_text(listing.get(field), f"submission.listing.{field}")
    for field in (
        "website_url",
        "support_url",
        "privacy_policy_url",
        "terms_of_service_url",
    ):
        require_https_url(listing.get(field), f"submission.listing.{field}")
    listing_manifest_pairs = {
        "display_name": "displayName",
        "short_description": "shortDescription",
        "long_description": "longDescription",
        "category": "category",
        "website_url": "websiteURL",
        "privacy_policy_url": "privacyPolicyURL",
        "terms_of_service_url": "termsOfServiceURL",
    }
    for listing_field, manifest_field in listing_manifest_pairs.items():
        if listing.get(listing_field) != interface.get(manifest_field):
            fail(
                f"submission listing {listing_field} must match "
                f"manifest interface.{manifest_field}"
            )
    if listing.get("starter_prompts") != prompts:
        fail("submission listing starter_prompts must match manifest defaultPrompt")
    availability = listing.get("availability")
    if not isinstance(availability, dict):
        fail("submission.listing.availability must be an object")
    if availability.get("selection") != "all_supported_regions":
        fail("availability.selection must be all_supported_regions")
    if not isinstance(availability.get("owner_confirmed"), bool):
        fail("availability.owner_confirmed must be a boolean")
    require_text(availability.get("owner_action"), "availability.owner_action")

    account_gates = submission.get("account_gates")
    if not isinstance(account_gates, dict):
        fail("submission.account_gates must be an object")
    for gate in (
        "verified_publisher_identity",
        "apps_management_write",
        "portal_submit",
        "post_approval_publish",
    ):
        value = account_gates.get(gate)
        if not isinstance(value, dict):
            fail(f"missing account gate: {gate}")
        if value.get("status") not in ALLOWED_ACCOUNT_STATUSES:
            fail(f"invalid account gate status: {gate}")
        require_text(value.get("requirement"), f"account_gates.{gate}.requirement")

    attestations = submission.get("policy_attestations")
    if not isinstance(attestations, list) or not attestations:
        fail("submission.policy_attestations must be a non-empty list")
    attestation_ids: set[str] = set()
    for index, attestation in enumerate(attestations):
        if not isinstance(attestation, dict):
            fail(f"policy_attestations[{index}] must be an object")
        attestation_id = require_text(
            attestation.get("id"), f"policy_attestations[{index}].id"
        )
        if attestation_id in attestation_ids:
            fail(f"duplicate policy attestation id: {attestation_id}")
        attestation_ids.add(attestation_id)
        require_text(
            attestation.get("status"), f"policy_attestations[{index}].status"
        )
        require_text(
            attestation.get("statement"), f"policy_attestations[{index}].statement"
        )

    positive = submission.get("test_cases")
    negative = submission.get("negative_test_cases")
    if not isinstance(positive, list) or len(positive) != 5:
        fail("submission must contain exactly 5 positive test cases")
    if not isinstance(negative, list) or len(negative) != 3:
        fail("submission must contain exactly 3 negative test cases")

    ids: set[str] = set()
    coverage: set[str] = set()
    for index, case in enumerate(positive):
        location = f"test_cases[{index}]"
        if not isinstance(case, dict):
            fail(f"{location} must be an object")
        case_id = require_text(case.get("id"), f"{location}.id")
        if case_id in ids:
            fail(f"duplicate test case id: {case_id}")
        ids.add(case_id)
        case_coverage = require_text(case.get("coverage"), f"{location}.coverage")
        coverage.add(case_coverage)
        for field in ("entry_skill", "expected_primary_skill"):
            skill = require_text(case.get(field), f"{location}.{field}")
            if skill not in skills:
                fail(f"{location}.{field} references unknown skill: {skill}")
        require_text(
            case.get("expected_result_shape"),
            f"{location}.expected_result_shape",
        )
        validate_case_text(case, location)
    if coverage != EXPECTED_COVERAGE:
        fail(
            "positive test coverage must be exactly: "
            + ", ".join(sorted(EXPECTED_COVERAGE))
        )

    for index, case in enumerate(negative):
        location = f"negative_test_cases[{index}]"
        if not isinstance(case, dict):
            fail(f"{location} must be an object")
        case_id = require_text(case.get("id"), f"{location}.id")
        if case_id in ids:
            fail(f"duplicate test case id: {case_id}")
        ids.add(case_id)
        if case.get("negative_mode") not in ALLOWED_NEGATIVE_MODES:
            fail(f"{location}.negative_mode is invalid")
        require_text(case.get("why_not_complete"), f"{location}.why_not_complete")
        validate_case_text(case, location)

    artifact_gate = submission.get("artifact_gate")
    if not isinstance(artifact_gate, dict):
        fail("submission.artifact_gate must be an object")
    for field in ("source_zip", "plugin_zip", "checksums", "status"):
        require_text(artifact_gate.get(field), f"artifact_gate.{field}")

    canonical_skills = repo_root / ".claude" / "skills"
    if not canonical_skills.is_dir():
        fail(f"missing canonical skills directory: {canonical_skills}")
    canonical_names = {
        path.name
        for path in canonical_skills.iterdir()
        if path.is_dir() and (path / "SKILL.md").is_file()
    }
    if canonical_names != skills:
        fail("canonical and packaged skill sets differ")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the OpenAI skills-only submission packet."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="repository root (default: current directory)",
    )
    parser.add_argument(
        "--submission",
        default="submission/openai/skills-only-submission.json",
        help="submission JSON path relative to repo root",
    )
    parser.add_argument(
        "--manifest",
        default=(
            "plugins/academic-writing-toolkit/.codex-plugin/plugin.json"
        ),
        help="plugin manifest path relative to repo root",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    submission_path = (repo_root / args.submission).resolve()
    manifest_path = (repo_root / args.manifest).resolve()
    try:
        validate_submission(repo_root, submission_path, manifest_path)
    except SubmissionError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1
    print(
        "skills-only submission validates: "
        "21 skills, 5 positive cases, 3 negative cases"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
