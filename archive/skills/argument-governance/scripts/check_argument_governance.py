#!/usr/bin/env python3
"""Validate argument-governance CSV packets."""

from __future__ import annotations

import argparse
import csv
import fnmatch
import hashlib
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Set, Tuple


BASE_REQUIRED_COLUMNS = {
    "intent_register.csv": [
        "intent_id", "paper_title", "central_problem", "target_venue",
        "target_readers", "field_positioning", "core_gap",
        "current_dominant_narrative", "narrative_to_correct", "why_now",
        "main_contribution_ids", "boundary_statement", "success_criterion",
        "reviewer_risk_level", "notes",
    ],
    "contribution_chain.csv": [
        "contribution_id", "intent_id", "gap_id", "gap_statement", "gap_type",
        "why_gap_matters", "insight", "contribution_statement",
        "contribution_type", "method_or_artifact_id", "primary_claim_ids",
        "required_evidence_type", "current_evidence_ids", "evidence_coverage",
        "limitation", "boundary_language", "reviewer_defense_note",
    ],
    "claim_hierarchy.csv": [
        "claim_id", "parent_claim_id", "root_intent_id", "contribution_id",
        "section_id", "claim_level", "claim_role", "claim_text",
        "depends_on_claim_ids", "evidence_requirement", "evidence_ids",
        "citation_keys", "evidence_status", "evidence_strength",
        "support_balance", "system_role", "overclaim_risk",
        "boundary_language", "revision_action",
    ],
    "argument_system_map.csv": [
        "node_id", "parent_node_id", "node_type", "node_label",
        "linked_gap_id", "linked_contribution_id", "linked_claim_id",
        "linked_evidence_ids", "section_id", "status", "risk_level", "notes",
    ],
    "reviewer_attack_matrix.csv": [
        "attack_id", "target_type", "target_id", "reviewer_question",
        "attack_category", "severity", "likely_reviewer_profile",
        "current_defense", "evidence_needed", "current_evidence_ids",
        "defense_strength", "revision_needed", "response_strategy",
        "owner", "status",
    ],
}

RELATION_REQUIRED_COLUMNS = {
    "gap_register.csv": [
        "gap_id", "intent_id", "gap_statement", "gap_type", "gap_priority",
        "gap_status", "scope", "search_or_problem_evidence_ids",
        "boundary_language", "notes",
    ],
    "evidence_objects.csv": [
        "object_id", "object_type", "statement_or_description",
        "artifact_or_source", "version", "scope", "method_or_measure",
        "provenance_status", "quality_status", "uncertainty", "status", "notes",
    ],
    "innovation_register.csv": [
        "innovation_id", "contribution_id", "innovation_type",
        "innovation_dimension", "comparison_set", "difference_statement",
        "materiality_statement", "novelty_scope", "comparison_evidence_ids",
        "comparison_status", "boundary_language", "notes",
    ],
    "argument_relations.csv": [
        "relation_id", "source_type", "source_id", "relation_type",
        "target_type", "target_id", "evidence_ids", "directness",
        "scope_match", "status", "rationale", "notes",
    ],
    "contribution_focus.csv": [
        "contribution_id", "current_role", "core_gap_fit", "target_reader_fit",
        "narrative_emphasis", "author_locked", "section_ids",
        "decision_status", "notes",
    ],
}

RELATION_REQUIRED_VALUES = {
    "gap_register.csv": {
        "gap_id", "intent_id", "gap_statement", "gap_type", "gap_priority",
        "gap_status", "scope",
    },
    "evidence_objects.csv": {
        "object_id", "object_type", "statement_or_description",
        "artifact_or_source", "provenance_status", "quality_status", "status",
    },
    "innovation_register.csv": {
        "innovation_id", "contribution_id", "innovation_type",
        "innovation_dimension", "comparison_set", "difference_statement",
        "materiality_statement", "novelty_scope", "comparison_status",
    },
    "argument_relations.csv": {
        "relation_id", "source_type", "source_id", "relation_type",
        "target_type", "target_id", "directness", "scope_match", "status",
        "rationale",
    },
    "contribution_focus.csv": {
        "contribution_id", "current_role", "core_gap_fit",
        "target_reader_fit", "narrative_emphasis", "author_locked",
        "decision_status",
    },
}


ENUMS = {
    "gap_type": {
        "empirical_gap", "methodological_gap", "conceptual_gap",
        "evaluation_gap", "governance_gap", "translation_gap",
        "reproducibility_gap",
    },
    "contribution_type": {
        "conceptual_reframing", "method_or_tool", "dataset_or_benchmark",
        "empirical_finding", "evaluation_protocol", "governance_framework",
        "case_study",
    },
    "evidence_coverage": {
        "missing", "thin", "adequate", "strong", "over_supported",
        "misaligned",
    },
    "claim_level": {
        "paper_thesis", "contribution_claim", "section_claim",
        "subsection_claim", "paragraph_claim",
    },
    "claim_role": {
        "gap_claim", "background_claim", "method_claim", "artifact_claim",
        "result_claim", "interpretive_claim", "limitation_claim",
        "implication_claim",
    },
    "support_balance": {
        "unsupported", "under_supported", "adequately_supported",
        "over_cited", "misaligned_evidence",
    },
    "system_role": {
        "motivates_gap", "defines_gap", "answers_gap", "justifies_method",
        "supports_result", "interprets_result", "states_boundary",
        "states_implication",
    },
    "node_type": {
        "intent", "gap", "contribution", "main_claim", "subclaim",
        "evidence_cluster", "limitation", "reviewer_risk",
    },
    "target_type": {
        "intent", "gap", "contribution", "claim", "data", "result",
        "innovation", "source", "prior_work", "evidence", "artifact",
        "analysis", "limitation",
    },
    "attack_category": {
        "novelty", "significance", "gap_validity",
        "claim_evidence_mismatch", "method_validity", "evaluation_strength",
        "generalization", "causal_overclaim", "related_work_coverage",
        "positioning", "reproducibility", "scope_boundary",
    },
    "defense_strength": {"none", "weak", "partial", "adequate", "strong"},
    "gap_priority": {"core", "supporting", "exploratory", "out_of_scope"},
    "gap_status": {
        "candidate", "scoped", "evidence_supported", "contested",
        "partially_closed", "closed", "superseded",
    },
    "object_type": {
        "data", "result", "source", "prior_work", "evidence", "artifact",
        "analysis", "limitation",
    },
    "provenance_status": {
        "verified", "traceable", "partial", "unverified", "unavailable",
        "restricted",
    },
    "quality_status": {
        "unknown", "raw", "checked", "validated", "frozen", "unstable",
        "contradicted", "not_applicable",
    },
    "object_status": {
        "planned", "available", "verified", "contested", "deprecated",
        "superseded",
    },
    "innovation_type": {
        "new_problem", "new_method", "new_evidence", "new_data",
        "new_evaluation", "new_workflow", "transfer", "integration",
    },
    "comparison_status": {
        "unverified", "pending", "partial", "supported", "contradicted",
    },
    "entity_type": {
        "intent", "gap", "contribution", "claim", "data", "result",
        "innovation", "source", "prior_work", "evidence", "artifact",
        "analysis", "limitation",
    },
    "relation_type": {
        "supports", "contradicts", "limits", "addresses", "produces",
        "bounds", "substantiates", "characterises", "differentiates",
        "compares_with", "qualifies", "refutes", "depends_on", "duplicates",
        "supersedes",
    },
    "directness": {
        "direct", "partial", "indirect", "conflicting", "unverified", "absent",
    },
    "scope_match": {"exact", "partial", "mismatch", "unknown"},
    "relation_status": {
        "candidate", "verified", "contested", "rejected", "superseded",
    },
    "current_role": {
        "primary", "secondary", "enabling", "boundary", "exploratory",
        "deprioritised",
    },
    "core_gap_fit": {"direct", "partial", "weak", "unknown"},
    "target_reader_fit": {"high", "medium", "low", "unknown"},
    "narrative_emphasis": {"dominant", "balanced", "light", "absent", "unknown"},
    "decision_status": {"current", "under_review", "approved", "superseded"},
}

SEVERITY_ORDER = {"critical", "high", "medium", "low", "info"}
WEAK_DEFENSES = {"none", "weak", "partial"}
HIGH_SEVERITIES = {"critical", "high"}
ACTIVE_RELATION_STATUSES = {"candidate", "verified", "contested"}
RELIABLE_RELATION_STATUSES = {"verified"}
RELIABLE_DIRECTNESS = {"direct", "partial"}
RELIABLE_SCOPE_MATCH = {"exact", "partial"}
ACTIVE_OBJECT_STATUSES = {"available", "verified", "contested"}
RELIABLE_OBJECT_STATUSES = {"available", "verified"}
RELIABLE_PROVENANCE_STATUSES = {"verified", "traceable"}
RELIABLE_QUALITY_STATUSES = {"checked", "validated", "frozen", "not_applicable"}
MAIN_CLAIM_LEVELS = {"paper_thesis", "contribution_claim"}
EMPIRICAL_CONTRIBUTION_TYPES = {"empirical_finding", "case_study"}
TESTED_CONTRIBUTION_TYPES = {"method_or_tool", "evaluation_protocol"}
RESOURCE_CONTRIBUTION_TYPES = {"dataset_or_benchmark"}
SOURCE_LED_CONTRIBUTION_TYPES = {"conceptual_reframing", "governance_framework"}

OBJECT_ID_PREFIXES = {
    "data": "DAT-",
    "result": "RES-",
    "source": "SRC-",
    "prior_work": "SRC-",
    "evidence": "EVD-",
    "artifact": "ART-",
    "analysis": "ANL-",
    "limitation": "LIM-",
}

ALLOWED_RELATION_TRIPLES = {
    ("source", "supports", "gap"),
    ("source", "contradicts", "gap"),
    ("source", "limits", "gap"),
    ("prior_work", "supports", "gap"),
    ("prior_work", "contradicts", "gap"),
    ("prior_work", "limits", "gap"),
    ("evidence", "supports", "gap"),
    ("evidence", "contradicts", "gap"),
    ("evidence", "limits", "gap"),
    ("contribution", "addresses", "gap"),
    ("data", "produces", "result"),
    ("data", "bounds", "result"),
    ("data", "bounds", "claim"),
    ("data", "bounds", "contribution"),
    ("result", "supports", "claim"),
    ("result", "limits", "claim"),
    ("result", "contradicts", "claim"),
    ("result", "qualifies", "claim"),
    ("result", "refutes", "claim"),
    ("result", "substantiates", "contribution"),
    ("claim", "substantiates", "contribution"),
    ("claim", "depends_on", "claim"),
    ("source", "supports", "claim"),
    ("source", "contradicts", "claim"),
    ("source", "limits", "claim"),
    ("source", "refutes", "claim"),
    ("prior_work", "supports", "claim"),
    ("prior_work", "contradicts", "claim"),
    ("prior_work", "limits", "claim"),
    ("prior_work", "refutes", "claim"),
    ("evidence", "supports", "claim"),
    ("evidence", "contradicts", "claim"),
    ("evidence", "limits", "claim"),
    ("evidence", "refutes", "claim"),
    ("artifact", "supports", "claim"),
    ("analysis", "supports", "claim"),
    ("data", "supports", "claim"),
    ("innovation", "characterises", "contribution"),
    ("source", "supports", "innovation"),
    ("source", "contradicts", "innovation"),
    ("source", "limits", "innovation"),
    ("source", "differentiates", "innovation"),
    ("prior_work", "supports", "innovation"),
    ("prior_work", "contradicts", "innovation"),
    ("prior_work", "limits", "innovation"),
    ("prior_work", "differentiates", "innovation"),
    ("evidence", "supports", "innovation"),
    ("evidence", "contradicts", "innovation"),
    ("evidence", "limits", "innovation"),
    ("evidence", "differentiates", "innovation"),
    ("innovation", "compares_with", "source"),
    ("innovation", "compares_with", "prior_work"),
    ("limitation", "bounds", "claim"),
    ("limitation", "bounds", "contribution"),
    ("limitation", "bounds", "result"),
    ("contribution", "duplicates", "contribution"),
    ("contribution", "supersedes", "contribution"),
    ("claim", "supersedes", "claim"),
    ("result", "supersedes", "result"),
    ("innovation", "supersedes", "innovation"),
    ("gap", "supersedes", "gap"),
}

CYCLE_CHECK_RELATIONS = {
    "addresses", "produces", "substantiates", "characterises", "depends_on",
    "supersedes",
}


def split_ids(value: str) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;,|]", value) if part.strip()]


def issue(
    kind: str,
    severity: str,
    location: str,
    message: str,
    rule_id: str = "",
    confidence: str = "",
) -> Dict[str, str]:
    payload = {
        "kind": kind,
        "severity": severity,
        "location": location,
        "message": message,
    }
    if rule_id:
        payload["rule_id"] = rule_id
    if confidence:
        payload["confidence"] = confidence
    return payload


def read_csv(path: Path) -> tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: List[Dict[str, str]] = []
        for row in reader:
            if None in row:
                raise csv.Error(f"row {reader.line_num} has more fields than the header")
            rows.append({k: (v or "").strip() for k, v in row.items()})
        return rows, list(reader.fieldnames or [])


def validate_columns(
    evidence_dir: Path,
    issues: List[Dict[str, str]],
    required_columns: Dict[str, List[str]],
) -> Dict[str, List[Dict[str, str]]]:
    tables: Dict[str, List[Dict[str, str]]] = {}
    for filename, required in required_columns.items():
        path = evidence_dir / filename
        if not path.is_file():
            issues.append(issue("missing-file", "high", str(path), "required argument-governance CSV is missing"))
            tables[filename] = []
            continue
        try:
            rows, columns = read_csv(path)
        except UnicodeDecodeError:
            issues.append(issue("csv-decode-error", "high", str(path), "file is not valid UTF-8 CSV"))
            tables[filename] = []
            continue
        except csv.Error as exc:
            issues.append(issue("csv-parse-error", "high", str(path), str(exc)))
            tables[filename] = []
            continue
        missing = [name for name in required if name not in columns]
        if missing:
            issues.append(issue("missing-columns", "high", filename, "missing columns: " + ", ".join(missing)))
        duplicates = sorted({name for name in columns if columns.count(name) > 1})
        if duplicates:
            issues.append(issue(
                "duplicate-columns",
                "high",
                filename,
                "duplicate columns: " + ", ".join(duplicates),
            ))
        tables[filename] = rows
    return tables


def check_enums(filename: str, rows: Sequence[Dict[str, str]], issues: List[Dict[str, str]]) -> None:
    for index, row in enumerate(rows, start=2):
        for column, allowed in ENUMS.items():
            if column not in row:
                continue
            value = row.get(column, "")
            if value and value not in allowed:
                issues.append(issue(
                    "invalid-enum",
                    "medium",
                    f"{filename}:{index}:{column}",
                    f"invalid value {value!r}; expected one of {sorted(allowed)}",
                ))
        severity = row.get("severity", "")
        if severity and severity not in SEVERITY_ORDER:
            issues.append(issue(
                "invalid-severity",
                "medium",
                f"{filename}:{index}:severity",
                "severity should be one of critical, high, medium, low, info",
            ))


def check_required_values(
    filename: str,
    rows: Sequence[Dict[str, str]],
    issues: List[Dict[str, str]],
) -> None:
    required = RELATION_REQUIRED_VALUES.get(filename, set())
    for index, row in enumerate(rows, start=2):
        for column in sorted(required):
            if not row.get(column, ""):
                issues.append(issue(
                    "missing-required-value",
                    "high",
                    f"{filename}:{index}:{column}",
                    f"{column} must not be blank in the strict relation profile",
                    confidence="confirmed",
                ))


def collect_ids(rows: Iterable[Dict[str, str]], key: str) -> Set[str]:
    return {row.get(key, "") for row in rows if row.get(key, "")}


def detect_cycles(edges: Dict[str, str]) -> Set[str]:
    cyclic: Set[str] = set()
    for start in edges:
        seen: Set[str] = set()
        current = start
        while current:
            if current in seen:
                cyclic.update(seen)
                break
            seen.add(current)
            current = edges.get(current, "")
    return cyclic


def duplicate_ids(rows: Iterable[Dict[str, str]], key: str) -> Set[str]:
    seen: Set[str] = set()
    duplicates: Set[str] = set()
    for row in rows:
        value = row.get(key, "")
        if not value:
            continue
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def detect_directed_cycles(edges: Dict[str, Set[str]]) -> Set[str]:
    cyclic: Set[str] = set()
    visiting: Set[str] = set()
    visited: Set[str] = set()

    def visit(node: str, path: List[str]) -> None:
        if node in visiting:
            if node in path:
                cyclic.update(path[path.index(node):])
            else:
                cyclic.add(node)
            return
        if node in visited:
            return
        visiting.add(node)
        path.append(node)
        for target in edges.get(node, set()):
            visit(target, path)
        path.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(edges):
        visit(node, [])
    return cyclic


def is_true(value: str) -> bool:
    return value.strip().lower() == "true"


def active_relation(row: Dict[str, str]) -> bool:
    return row.get("status", "") in ACTIVE_RELATION_STATUSES


def usable_support_relation(row: Dict[str, str]) -> bool:
    return (
        row.get("status", "") in RELIABLE_RELATION_STATUSES
        and row.get("directness", "") in RELIABLE_DIRECTNESS
        and row.get("scope_match", "") in RELIABLE_SCOPE_MATCH
    )


def relation_matches(
    row: Dict[str, str],
    source_type: str = "",
    source_id: str = "",
    relation_types: Iterable[str] = (),
    target_type: str = "",
    target_id: str = "",
    usable_only: bool = False,
) -> bool:
    if usable_only and not usable_support_relation(row):
        return False
    if source_type and row.get("source_type") != source_type:
        return False
    if source_id and row.get("source_id") != source_id:
        return False
    allowed_relations = set(relation_types)
    if allowed_relations and row.get("relation_type") not in allowed_relations:
        return False
    if target_type and row.get("target_type") != target_type:
        return False
    if target_id and row.get("target_id") != target_id:
        return False
    return True


def overlap_ratio(left: Set[str], right: Set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / float(len(left | right))


def normalise_text(value: str) -> str:
    return re.sub(r"[\W_]+", " ", value.lower(), flags=re.UNICODE).strip()


def validate_focus_snapshot(
    evidence_dir: Path,
    focus_review_candidates: Sequence[Dict[str, object]],
    tables: Dict[str, List[Dict[str, str]]],
    issues: List[Dict[str, str]],
) -> None:
    if not focus_review_candidates:
        return
    path = evidence_dir / "contribution_focus_snapshot.json"
    if not path.is_file():
        issues.append(issue(
            "missing-focus-snapshot",
            "high",
            str(path),
            "focus review requires a frozen before-state snapshot before any decision or prose edit",
            rule_id="FIT-02",
            confidence="confirmed",
        ))
        return
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        issues.append(issue(
            "invalid-focus-snapshot",
            "high",
            str(path),
            f"focus snapshot is not valid UTF-8 JSON: {exc}",
            rule_id="FIT-02",
            confidence="confirmed",
        ))
        return
    if not isinstance(payload, dict):
        issues.append(issue(
            "invalid-focus-snapshot",
            "high",
            str(path),
            "focus snapshot must be a JSON object",
            rule_id="FIT-02",
            confidence="confirmed",
        ))
        return
    required_fields = {
        "schema_version",
        "intent_ids",
        "current_primary_ids",
        "author_approved_manuscript_path",
        "author_approved_manuscript_sha256",
        "relation_packet_sha256",
        "captured_from_files",
        "status",
    }
    for field in sorted(required_fields):
        value = payload.get(field)
        if value in (None, "", []):
            issues.append(issue(
                "invalid-focus-snapshot",
                "high",
                f"{path}:{field}",
                f"focus snapshot field {field} is required",
                rule_id="FIT-02",
                confidence="confirmed",
            ))
    if payload.get("schema_version") != 1:
        issues.append(issue(
            "invalid-focus-snapshot",
            "medium",
            f"{path}:schema_version",
            "focus snapshot schema_version must be 1",
            rule_id="FIT-02",
            confidence="confirmed",
        ))
    if payload.get("status") != "pending_author_review":
        issues.append(issue(
            "invalid-focus-snapshot",
            "high",
            f"{path}:status",
            "focus snapshot status must be pending_author_review",
            rule_id="FIT-02",
            confidence="confirmed",
        ))
    for field in ("intent_ids", "current_primary_ids", "captured_from_files"):
        if field in payload and not isinstance(payload[field], list):
            issues.append(issue(
                "invalid-focus-snapshot",
                "high",
                f"{path}:{field}",
                f"{field} must be a JSON list",
                rule_id="FIT-02",
                confidence="confirmed",
            ))
    for field in (
        "author_approved_manuscript_sha256",
        "relation_packet_sha256",
    ):
        value = payload.get(field)
        if value and value != "unavailable" and not re.fullmatch(
            r"[0-9a-fA-F]{64}", str(value)
        ):
            issues.append(issue(
                "invalid-focus-snapshot",
                "high",
                f"{path}:{field}",
                f"{field} must be a SHA-256 hex digest or unavailable",
                rule_id="FIT-02",
                confidence="confirmed",
            ))

    def snapshot_error(field: str, message: str) -> None:
        issues.append(issue(
            "invalid-focus-snapshot",
            "high",
            f"{path}:{field}",
            message,
            rule_id="FIT-02",
            confidence="confirmed",
        ))

    contribution_intents = {
        row.get("contribution_id", ""): row.get("intent_id", "")
        for row in tables.get("contribution_chain.csv", [])
        if row.get("contribution_id")
    }
    expected_intent_ids = {
        contribution_intents.get(str(candidate.get("current_primary_id", "")), "")
        for candidate in focus_review_candidates
    }
    expected_intent_ids.discard("")
    expected_primary_ids = {
        row.get("contribution_id", "")
        for row in tables.get("contribution_focus.csv", [])
        if (
            row.get("current_role") == "primary"
            and contribution_intents.get(row.get("contribution_id", ""))
            in expected_intent_ids
        )
    }
    expected_primary_ids.discard("")

    for field, expected_values in (
        ("intent_ids", expected_intent_ids),
        ("current_primary_ids", expected_primary_ids),
    ):
        value = payload.get(field)
        if not isinstance(value, list):
            continue
        if any(not isinstance(item, str) or not item.strip() for item in value):
            snapshot_error(field, f"{field} must contain only non-empty strings")
            continue
        normalised_values = [item.strip() for item in value]
        if len(normalised_values) != len(set(normalised_values)):
            snapshot_error(field, f"{field} must not contain duplicate IDs")
            continue
        if set(normalised_values) != expected_values:
            snapshot_error(
                field,
                f"{field} must exactly match the affected current packet IDs: "
                f"{sorted(expected_values)}",
            )

    project_root = evidence_dir.parent
    project_root_resolved = project_root.resolve()
    manuscript_path: Optional[Path] = None
    manuscript_value = payload.get("author_approved_manuscript_path")
    if isinstance(manuscript_value, str) and manuscript_value.strip():
        manuscript_text = manuscript_value.strip().replace("\\", "/")
        manuscript_relative = Path(manuscript_text)
        if (
            manuscript_relative.is_absolute()
            or ".." in manuscript_relative.parts
            or any(token in manuscript_text for token in ("*", "?", "[", "]"))
        ):
            snapshot_error(
                "author_approved_manuscript_path",
                "author-approved manuscript path must be a non-glob project-relative path",
            )
        else:
            resolved = (project_root / manuscript_relative).resolve()
            try:
                resolved.relative_to(project_root_resolved)
            except ValueError:
                snapshot_error(
                    "author_approved_manuscript_path",
                    "author-approved manuscript path resolves outside the project root",
                )
            else:
                if not resolved.is_file():
                    snapshot_error(
                        "author_approved_manuscript_path",
                        "author-approved manuscript path does not identify an existing file",
                    )
                else:
                    manuscript_path = resolved
    elif manuscript_value not in (None, ""):
        snapshot_error(
            "author_approved_manuscript_path",
            "author-approved manuscript path must be a string",
        )

    manuscript_hash = payload.get("author_approved_manuscript_sha256")
    if (
        manuscript_path is not None
        and isinstance(manuscript_hash, str)
        and re.fullmatch(r"[0-9a-fA-F]{64}", manuscript_hash)
    ):
        actual_hash = hashlib.sha256(manuscript_path.read_bytes()).hexdigest()
        if manuscript_hash.lower() != actual_hash:
            snapshot_error(
                "author_approved_manuscript_sha256",
                "author-approved manuscript hash does not match the referenced file",
            )

    captured_value = payload.get("captured_from_files")
    capture_patterns: List[str] = []
    unavailable_notes: List[str] = []
    if isinstance(captured_value, list):
        for index, entry in enumerate(captured_value):
            location = f"captured_from_files[{index}]"
            if not isinstance(entry, str) or not entry.strip():
                snapshot_error(location, "captured file entries must be non-empty strings")
                continue
            captured_text = entry.strip()
            if captured_text.lower().startswith("hash unavailable:"):
                if not captured_text.split(":", 1)[1].strip():
                    snapshot_error(location, "hash unavailable note must state a reason")
                else:
                    unavailable_notes.append(captured_text)
                continue
            pattern = captured_text.replace("\\", "/")
            relative_pattern = Path(pattern)
            if relative_pattern.is_absolute() or ".." in relative_pattern.parts:
                snapshot_error(
                    location,
                    "captured file pattern must stay within the project root",
                )
                continue
            try:
                matches = [item for item in project_root.glob(pattern) if item.is_file()]
            except (OSError, ValueError):
                matches = []
            safe_matches: List[Path] = []
            for matched in matches:
                resolved_match = matched.resolve()
                try:
                    resolved_match.relative_to(project_root_resolved)
                except ValueError:
                    continue
                safe_matches.append(resolved_match)
            if not safe_matches:
                snapshot_error(
                    location,
                    "captured file pattern does not match an existing in-project file",
                )
                continue
            capture_patterns.append(pattern)

        required_packet_paths = {
            f"evidence/{filename}"
            for filename in set(BASE_REQUIRED_COLUMNS) | set(RELATION_REQUIRED_COLUMNS)
        }
        uncovered_paths = sorted(
            required_path
            for required_path in required_packet_paths
            if not any(
                fnmatch.fnmatchcase(required_path, pattern)
                for pattern in capture_patterns
            )
        )
        if uncovered_paths:
            snapshot_error(
                "captured_from_files",
                "captured file patterns must cover every required argument packet CSV; "
                f"uncovered: {uncovered_paths}",
            )

    if any(
        payload.get(field) == "unavailable"
        for field in (
            "author_approved_manuscript_sha256",
            "relation_packet_sha256",
        )
    ) and not unavailable_notes:
        snapshot_error(
            "captured_from_files",
            "an unavailable hash requires a 'hash unavailable: <reason>' note",
        )


def validate_relationships(tables: Dict[str, List[Dict[str, str]]], issues: List[Dict[str, str]]) -> None:
    intents = tables.get("intent_register.csv", [])
    contributions = tables.get("contribution_chain.csv", [])
    claims = tables.get("claim_hierarchy.csv", [])
    nodes = tables.get("argument_system_map.csv", [])
    attacks = tables.get("reviewer_attack_matrix.csv", [])

    intent_ids = collect_ids(intents, "intent_id")
    contribution_ids = collect_ids(contributions, "contribution_id")
    claim_ids = collect_ids(claims, "claim_id")
    gap_ids = collect_ids(contributions, "gap_id")
    node_ids = collect_ids(nodes, "node_id")

    for index, row in enumerate(intents, start=2):
        location = f"intent_register.csv:{index}"
        if not row.get("intent_id"):
            issues.append(issue("missing-id", "high", location, "intent_id is required"))
        for column in ["central_problem", "core_gap", "boundary_statement"]:
            if not row.get(column):
                issues.append(issue("missing-intent-field", "medium", f"{location}:{column}", f"{column} should not be blank"))
        for cid in split_ids(row.get("main_contribution_ids", "")):
            if cid not in contribution_ids:
                issues.append(issue("unknown-contribution", "high", f"{location}:main_contribution_ids", f"unknown contribution_id {cid!r}"))

    for index, row in enumerate(contributions, start=2):
        location = f"contribution_chain.csv:{index}"
        cid = row.get("contribution_id", "")
        if not cid:
            issues.append(issue("missing-id", "high", location, "contribution_id is required"))
        if row.get("intent_id", "") not in intent_ids:
            issues.append(issue("unknown-intent", "high", f"{location}:intent_id", "contribution must reference an existing intent_id"))
        for column in ["gap_id", "gap_statement", "contribution_statement", "required_evidence_type"]:
            if not row.get(column):
                issues.append(issue("missing-contribution-field", "high", f"{location}:{column}", f"{column} should not be blank"))
        if not split_ids(row.get("primary_claim_ids", "")):
            issues.append(issue("missing-primary-claims", "high", f"{location}:primary_claim_ids", "contribution should link to primary claim IDs"))
        for claim_id in split_ids(row.get("primary_claim_ids", "")):
            if claim_id not in claim_ids:
                issues.append(issue("unknown-claim", "high", f"{location}:primary_claim_ids", f"unknown claim_id {claim_id!r}"))
        if row.get("evidence_coverage") in {"missing", "thin", "misaligned"} and not row.get("limitation"):
            issues.append(issue("coverage-needs-limitation", "medium", f"{location}:limitation", "weak or misaligned evidence coverage needs a limitation"))

    parent_edges: Dict[str, str] = {}
    paper_thesis_count = 0
    for index, row in enumerate(claims, start=2):
        location = f"claim_hierarchy.csv:{index}"
        claim_id = row.get("claim_id", "")
        if not claim_id:
            issues.append(issue("missing-id", "high", location, "claim_id is required"))
            continue
        if row.get("claim_level") == "paper_thesis":
            paper_thesis_count += 1
        if row.get("root_intent_id", "") not in intent_ids:
            issues.append(issue("unknown-intent", "high", f"{location}:root_intent_id", "claim must reference an existing root_intent_id"))
        contribution_id = row.get("contribution_id", "")
        if row.get("claim_level") == "contribution_claim" and contribution_id not in contribution_ids:
            issues.append(issue("main-claim-missing-contribution", "high", f"{location}:contribution_id", "contribution_claim must reference an existing contribution_id"))
        if contribution_id and contribution_id not in contribution_ids:
            issues.append(issue("unknown-contribution", "high", f"{location}:contribution_id", f"unknown contribution_id {contribution_id!r}"))
        parent = row.get("parent_claim_id", "")
        if parent:
            parent_edges[claim_id] = parent
            if parent == claim_id:
                issues.append(issue("self-parent-claim", "high", f"{location}:parent_claim_id", "claim cannot be its own parent"))
            elif parent not in claim_ids:
                issues.append(issue("unknown-parent-claim", "high", f"{location}:parent_claim_id", f"unknown parent claim {parent!r}"))
        elif row.get("claim_level") in {"section_claim", "subsection_claim", "paragraph_claim"}:
            issues.append(issue("orphan-lower-claim", "medium", f"{location}:parent_claim_id", "lower-level claim should support a parent claim"))
        for dep in split_ids(row.get("depends_on_claim_ids", "")):
            if dep not in claim_ids:
                issues.append(issue("unknown-dependent-claim", "medium", f"{location}:depends_on_claim_ids", f"unknown claim_id {dep!r}"))
        has_evidence = bool(split_ids(row.get("evidence_ids", "")) or split_ids(row.get("citation_keys", "")))
        if not has_evidence and row.get("support_balance") != "unsupported":
            issues.append(issue("missing-evidence-link", "high", f"{location}:evidence_ids", "claim needs evidence_ids or citation_keys, or support_balance=unsupported"))
        if row.get("support_balance") in {"unsupported", "under_supported", "misaligned_evidence"} and row.get("claim_level") in {"paper_thesis", "contribution_claim"}:
            issues.append(issue("weak-main-claim-support", "high", f"{location}:support_balance", "main claims need adequate support before submission-facing use"))
        if row.get("support_balance") == "over_cited" and row.get("claim_level") == "paragraph_claim":
            issues.append(issue("over-cited-minor-claim", "low", f"{location}:support_balance", "paragraph-level claim may be citation-padded"))
    if paper_thesis_count > 3:
        issues.append(issue("too-many-paper-theses", "medium", "claim_hierarchy.csv", "paper_thesis claims should normally be limited to 1-3"))
    for cyclic in sorted(detect_cycles(parent_edges)):
        issues.append(issue("claim-cycle", "high", f"claim_hierarchy.csv:{cyclic}", "claim parent links contain a cycle"))

    node_edges: Dict[str, str] = {}
    for index, row in enumerate(nodes, start=2):
        location = f"argument_system_map.csv:{index}"
        node_id = row.get("node_id", "")
        if not node_id:
            issues.append(issue("missing-id", "high", location, "node_id is required"))
            continue
        parent = row.get("parent_node_id", "")
        if parent:
            node_edges[node_id] = parent
            if parent == node_id:
                issues.append(issue("self-parent-node", "high", f"{location}:parent_node_id", "node cannot be its own parent"))
            elif parent not in node_ids:
                issues.append(issue("unknown-parent-node", "medium", f"{location}:parent_node_id", f"unknown parent node {parent!r}"))
        linked_gap = row.get("linked_gap_id", "")
        if linked_gap and linked_gap not in gap_ids:
            issues.append(issue("unknown-gap", "medium", f"{location}:linked_gap_id", f"unknown gap_id {linked_gap!r}"))
        linked_contribution = row.get("linked_contribution_id", "")
        if linked_contribution and linked_contribution not in contribution_ids:
            issues.append(issue("unknown-contribution", "medium", f"{location}:linked_contribution_id", f"unknown contribution_id {linked_contribution!r}"))
        linked_claim = row.get("linked_claim_id", "")
        if linked_claim and linked_claim not in claim_ids:
            issues.append(issue("unknown-claim", "medium", f"{location}:linked_claim_id", f"unknown claim_id {linked_claim!r}"))
    for cyclic in sorted(detect_cycles(node_edges)):
        issues.append(issue("argument-map-cycle", "high", f"argument_system_map.csv:{cyclic}", "argument map parent links contain a cycle"))

    target_sets = {
        "intent": intent_ids,
        "gap": gap_ids,
        "contribution": contribution_ids,
        "claim": claim_ids,
    }
    for index, row in enumerate(attacks, start=2):
        location = f"reviewer_attack_matrix.csv:{index}"
        target_type = row.get("target_type", "")
        target_id = row.get("target_id", "")
        if target_type in target_sets and target_id and target_id not in target_sets[target_type]:
            issues.append(issue("unknown-review-target", "medium", f"{location}:target_id", f"unknown {target_type} target {target_id!r}"))
        if row.get("severity") in HIGH_SEVERITIES and row.get("defense_strength") in WEAK_DEFENSES:
            issues.append(issue("weak-high-risk-defense", "high", f"{location}:defense_strength", "high-severity reviewer attack has weak defense"))
        if row.get("severity") in HIGH_SEVERITIES and not row.get("response_strategy"):
            issues.append(issue("missing-response-strategy", "high", f"{location}:response_strategy", "high-severity reviewer attack needs a response strategy"))


def validate_relation_profile(
    tables: Dict[str, List[Dict[str, str]]],
    issues: List[Dict[str, str]],
    redundancy_threshold: float,
) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    intents = tables.get("intent_register.csv", [])
    contributions = tables.get("contribution_chain.csv", [])
    claims = tables.get("claim_hierarchy.csv", [])
    gaps = tables.get("gap_register.csv", [])
    objects = tables.get("evidence_objects.csv", [])
    innovations = tables.get("innovation_register.csv", [])
    relations = tables.get("argument_relations.csv", [])
    focus_rows = tables.get("contribution_focus.csv", [])

    intent_ids = collect_ids(intents, "intent_id")
    contribution_ids = collect_ids(contributions, "contribution_id")
    claim_ids = collect_ids(claims, "claim_id")
    gap_ids = collect_ids(gaps, "gap_id")
    object_ids = collect_ids(objects, "object_id")
    innovation_ids = collect_ids(innovations, "innovation_id")

    object_ids_by_type: DefaultDict[str, Set[str]] = defaultdict(set)
    object_by_id: Dict[str, Dict[str, str]] = {}
    for row in objects:
        object_id = row.get("object_id", "")
        if object_id:
            object_ids_by_type[row.get("object_type", "")].add(object_id)
            object_by_id[object_id] = row

    id_sets: Dict[str, Set[str]] = {
        "intent": intent_ids,
        "gap": gap_ids,
        "contribution": contribution_ids,
        "claim": claim_ids,
        "innovation": innovation_ids,
    }
    for object_type in ENUMS["object_type"]:
        id_sets[object_type] = set(object_ids_by_type.get(object_type, set()))

    id_specs = [
        ("gap_register.csv", gaps, "gap_id", "GAP-"),
        ("evidence_objects.csv", objects, "object_id", ""),
        ("innovation_register.csv", innovations, "innovation_id", "NOV-"),
        ("argument_relations.csv", relations, "relation_id", "REL-"),
        ("contribution_focus.csv", focus_rows, "contribution_id", ""),
    ]
    for filename, rows, id_key, prefix in id_specs:
        for duplicate in sorted(duplicate_ids(rows, id_key)):
            issues.append(issue(
                "duplicate-id",
                "high",
                filename,
                f"duplicate {id_key} {duplicate!r}",
                confidence="confirmed",
            ))
        for index, row in enumerate(rows, start=2):
            value = row.get(id_key, "")
            if not value:
                issues.append(issue(
                    "missing-id",
                    "high",
                    f"{filename}:{index}:{id_key}",
                    f"{id_key} is required",
                    confidence="confirmed",
                ))
            elif prefix and not value.startswith(prefix):
                issues.append(issue(
                    "invalid-id-prefix",
                    "medium",
                    f"{filename}:{index}:{id_key}",
                    f"{id_key} should start with {prefix}",
                    confidence="confirmed",
                ))

    intent_by_id = {
        row.get("intent_id", ""): row for row in intents if row.get("intent_id")
    }
    gap_by_id = {row.get("gap_id", ""): row for row in gaps if row.get("gap_id")}
    contribution_by_id = {
        row.get("contribution_id", ""): row
        for row in contributions
        if row.get("contribution_id")
    }
    claim_by_id = {row.get("claim_id", ""): row for row in claims if row.get("claim_id")}
    innovation_by_id = {
        row.get("innovation_id", ""): row
        for row in innovations
        if row.get("innovation_id")
    }

    for index, row in enumerate(gaps, start=2):
        location = f"gap_register.csv:{index}"
        if row.get("intent_id", "") not in intent_ids:
            issues.append(issue(
                "unknown-intent",
                "high",
                f"{location}:intent_id",
                "gap must reference an existing intent_id",
                confidence="confirmed",
            ))
        for evidence_id in split_ids(row.get("search_or_problem_evidence_ids", "")):
            if evidence_id not in object_ids:
                issues.append(issue(
                    "unknown-gap-evidence",
                    "high",
                    f"{location}:search_or_problem_evidence_ids",
                    f"unknown evidence object {evidence_id!r}",
                    rule_id="GAP-01",
                    confidence="confirmed",
                ))

    for index, row in enumerate(objects, start=2):
        location = f"evidence_objects.csv:{index}"
        object_id = row.get("object_id", "")
        object_type = row.get("object_type", "")
        expected_prefix = OBJECT_ID_PREFIXES.get(object_type, "")
        if object_id and expected_prefix and not object_id.startswith(expected_prefix):
            issues.append(issue(
                "object-id-type-mismatch",
                "high",
                f"{location}:object_id",
                f"{object_type} objects should use the {expected_prefix} prefix",
                confidence="confirmed",
            ))
        status = row.get("status", "")
        if status and status not in ENUMS["object_status"]:
            issues.append(issue(
                "invalid-object-status",
                "medium",
                f"{location}:status",
                f"invalid object status {status!r}; expected one of {sorted(ENUMS['object_status'])}",
                confidence="confirmed",
            ))
        if object_type == "result" and not row.get("method_or_measure"):
            issues.append(issue(
                "result-missing-method",
                "high",
                f"{location}:method_or_measure",
                "result objects need the method, analysis, or measure that produced them",
                rule_id="DATA-02",
                confidence="confirmed",
            ))
        if object_type == "data" and not row.get("artifact_or_source"):
            issues.append(issue(
                "data-missing-source",
                "high",
                f"{location}:artifact_or_source",
                "data objects need a traceable artifact or source",
                rule_id="DATA-02",
                confidence="confirmed",
            ))

    for index, row in enumerate(innovations, start=2):
        location = f"innovation_register.csv:{index}"
        contribution_id = row.get("contribution_id", "")
        if contribution_id not in contribution_ids:
            issues.append(issue(
                "unknown-contribution",
                "high",
                f"{location}:contribution_id",
                "innovation must reference an existing contribution_id",
                confidence="confirmed",
            ))
        if not row.get("comparison_set") or not split_ids(row.get("comparison_evidence_ids", "")):
            issues.append(issue(
                "innovation-evidence-thin",
                "high",
                location,
                "innovation needs an explicit comparison set and comparison evidence IDs",
                rule_id="NOV-01",
                confidence="confirmed",
            ))
        for evidence_id in split_ids(row.get("comparison_evidence_ids", "")):
            if evidence_id not in object_ids:
                issues.append(issue(
                    "unknown-innovation-evidence",
                    "high",
                    f"{location}:comparison_evidence_ids",
                    f"unknown evidence object {evidence_id!r}",
                    rule_id="NOV-01",
                    confidence="confirmed",
                ))

    focus_by_contribution: Dict[str, Dict[str, str]] = {}
    for index, row in enumerate(focus_rows, start=2):
        location = f"contribution_focus.csv:{index}"
        contribution_id = row.get("contribution_id", "")
        if contribution_id not in contribution_ids:
            issues.append(issue(
                "unknown-contribution",
                "high",
                f"{location}:contribution_id",
                "focus row must reference an existing contribution_id",
                confidence="confirmed",
            ))
        if row.get("author_locked", "").lower() not in {"true", "false"}:
            issues.append(issue(
                "invalid-author-locked",
                "medium",
                f"{location}:author_locked",
                "author_locked must be true or false",
                confidence="confirmed",
            ))
        if row.get("decision_status") != "superseded" and contribution_id:
            focus_by_contribution[contribution_id] = row

    for contribution_id in sorted(contribution_ids - set(focus_by_contribution)):
        issues.append(issue(
            "missing-contribution-focus-row",
            "high",
            f"contribution_focus.csv:{contribution_id}",
            "every current contribution needs one non-superseded focus row",
            rule_id="FIT-01",
            confidence="confirmed",
        ))

    verified_relation_edges: DefaultDict[str, Set[str]] = defaultdict(set)
    provisional_relation_edges: DefaultDict[str, Set[str]] = defaultdict(set)
    for index, row in enumerate(relations, start=2):
        location = f"argument_relations.csv:{index}"
        source_type = row.get("source_type", "")
        source_id = row.get("source_id", "")
        relation_type = row.get("relation_type", "")
        target_type = row.get("target_type", "")
        target_id = row.get("target_id", "")
        status = row.get("status", "")
        if source_type not in ENUMS["entity_type"]:
            issues.append(issue(
                "invalid-source-type", "medium", f"{location}:source_type",
                f"invalid source_type {source_type!r}", confidence="confirmed",
            ))
        if target_type not in ENUMS["entity_type"]:
            issues.append(issue(
                "invalid-target-type", "medium", f"{location}:target_type",
                f"invalid target_type {target_type!r}", confidence="confirmed",
            ))
        if status and status not in ENUMS["relation_status"]:
            issues.append(issue(
                "invalid-relation-status", "medium", f"{location}:status",
                f"invalid relation status {status!r}", confidence="confirmed",
            ))
        if source_type in id_sets and source_id not in id_sets[source_type]:
            issues.append(issue(
                "unknown-relation-source",
                "high",
                f"{location}:source_id",
                f"unknown {source_type} source {source_id!r}",
                confidence="confirmed",
            ))
        if target_type in id_sets and target_id not in id_sets[target_type]:
            issues.append(issue(
                "unknown-relation-target",
                "high",
                f"{location}:target_id",
                f"unknown {target_type} target {target_id!r}",
                confidence="confirmed",
            ))
        if (source_type, relation_type, target_type) not in ALLOWED_RELATION_TRIPLES:
            issues.append(issue(
                "invalid-relation-triple",
                "medium",
                location,
                f"unsupported relation: {source_type} --{relation_type}--> {target_type}",
                confidence="confirmed",
            ))
        if source_type == target_type and source_id and source_id == target_id:
            issues.append(issue(
                "self-relation",
                "high",
                location,
                "an entity cannot relate to itself",
                confidence="confirmed",
            ))
        for evidence_id in split_ids(row.get("evidence_ids", "")):
            if evidence_id not in object_ids:
                issues.append(issue(
                    "unknown-relation-evidence",
                    "medium",
                    f"{location}:evidence_ids",
                    f"unknown evidence object {evidence_id!r}",
                    confidence="confirmed",
                ))
        if active_relation(row) and relation_type in CYCLE_CHECK_RELATIONS:
            edge_map = (
                verified_relation_edges
                if status == "verified"
                else provisional_relation_edges
            )
            edge_map[f"{source_type}:{source_id}"].add(
                f"{target_type}:{target_id}"
            )

    verified_cycles = detect_directed_cycles(verified_relation_edges)
    for cyclic in sorted(verified_cycles):
        issues.append(issue(
            "relation-cycle",
            "high",
            f"argument_relations.csv:{cyclic}",
            "typed argument relations contain a structural cycle",
            confidence="confirmed",
        ))

    combined_relation_edges: DefaultDict[str, Set[str]] = defaultdict(set)
    for source, targets in verified_relation_edges.items():
        combined_relation_edges[source].update(targets)
    for source, targets in provisional_relation_edges.items():
        combined_relation_edges[source].update(targets)
    provisional_cycles = detect_directed_cycles(combined_relation_edges) - verified_cycles
    for cyclic in sorted(provisional_cycles):
        issues.append(issue(
            "provisional-relation-cycle",
            "low",
            f"argument_relations.csv:{cyclic}",
            "candidate or contested relations would form a structural cycle if accepted",
            confidence="possible",
        ))

    for contribution in contributions:
        gap_id = contribution.get("gap_id", "")
        if gap_id not in gap_ids:
            issues.append(issue(
                "unknown-gap",
                "high",
                f"contribution_chain.csv:{contribution.get('contribution_id', '')}:gap_id",
                f"strict relation profile requires gap_id {gap_id!r} in gap_register.csv",
                confidence="confirmed",
            ))
            continue
        gap = gap_by_id[gap_id]
        if contribution.get("gap_type") and contribution.get("gap_type") != gap.get("gap_type"):
            issues.append(issue(
                "gap-type-mismatch",
                "medium",
                f"contribution_chain.csv:{contribution.get('contribution_id', '')}:gap_type",
                "contribution gap_type differs from gap_register.csv",
                confidence="confirmed",
            ))
        if contribution.get("intent_id") != gap.get("intent_id"):
            issues.append(issue(
                "cross-table-relation-mismatch",
                "high",
                f"contribution_chain.csv:{contribution.get('contribution_id', '')}:intent_id",
                "contribution and declared gap belong to different intents",
                rule_id="FIT-01",
                confidence="confirmed",
            ))

    active_relations = [row for row in relations if active_relation(row)]

    def relation_objects_available(row: Dict[str, str]) -> bool:
        for side in ("source", "target"):
            entity_type = row.get(f"{side}_type", "")
            entity_id = row.get(f"{side}_id", "")
            if entity_type not in ENUMS["object_type"]:
                continue
            obj = object_by_id.get(entity_id)
            if (
                not obj
                or obj.get("status") not in RELIABLE_OBJECT_STATUSES
                or obj.get("provenance_status") not in RELIABLE_PROVENANCE_STATUSES
                or obj.get("quality_status") not in RELIABLE_QUALITY_STATUSES
            ):
                return False
        return True

    reliable_relations = [
        row for row in relations
        if usable_support_relation(row) and relation_objects_available(row)
    ]

    def incoming(
        target_type: str,
        target_id: str,
        relation_types: Iterable[str],
        source_types: Iterable[str] = (),
        usable_only: bool = False,
    ) -> List[Dict[str, str]]:
        allowed_sources = set(source_types)
        relation_pool = reliable_relations if usable_only else active_relations
        return [
            row for row in relation_pool
            if relation_matches(
                row,
                relation_types=relation_types,
                target_type=target_type,
                target_id=target_id,
                usable_only=False,
            ) and (not allowed_sources or row.get("source_type") in allowed_sources)
        ]

    def outgoing(
        source_type: str,
        source_id: str,
        relation_types: Iterable[str],
        target_types: Iterable[str] = (),
        usable_only: bool = False,
    ) -> List[Dict[str, str]]:
        allowed_targets = set(target_types)
        relation_pool = reliable_relations if usable_only else active_relations
        return [
            row for row in relation_pool
            if relation_matches(
                row,
                source_type=source_type,
                source_id=source_id,
                relation_types=relation_types,
                usable_only=False,
            ) and (not allowed_targets or row.get("target_type") in allowed_targets)
        ]

    core_gap_ids = {
        row.get("gap_id", "") for row in gaps
        if row.get("gap_priority") == "core"
        and row.get("gap_status") not in {"closed", "superseded"}
    }

    for contribution_id, contribution in contribution_by_id.items():
        declared_gap_id = contribution.get("gap_id", "")
        exact_gap_links = [
            row for row in outgoing(
                "contribution", contribution_id, {"addresses"}, {"gap"}, True,
            )
            if row.get("target_id") == declared_gap_id
        ]
        if declared_gap_id in gap_ids and not exact_gap_links:
            issues.append(issue(
                "cross-table-relation-mismatch",
                "high",
                f"contribution_chain.csv:{contribution_id}:gap_id",
                "declared gap_id lacks a reliable contribution --addresses--> gap relation",
                rule_id="FIT-01",
                confidence="confirmed",
            ))

        declared_primary_claim_ids = set(
            split_ids(contribution.get("primary_claim_ids", ""))
        )
        for claim_id in sorted(declared_primary_claim_ids & claim_ids):
            claim = claim_by_id[claim_id]
            if claim.get("contribution_id") != contribution_id:
                issues.append(issue(
                    "cross-table-relation-mismatch",
                    "high",
                    f"claim_hierarchy.csv:{claim_id}:contribution_id",
                    "primary claim points to a different contribution than contribution_chain.csv",
                    rule_id="CLM-01",
                    confidence="confirmed",
                ))
                continue
            exact_claim_links = [
                row for row in outgoing(
                    "claim", claim_id, {"substantiates"}, {"contribution"}, True,
                )
                if row.get("target_id") == contribution_id
            ]
            if not exact_claim_links:
                issues.append(issue(
                    "cross-table-relation-mismatch",
                    "high",
                    f"claim_hierarchy.csv:{claim_id}",
                    "declared primary claim lacks a reliable relation to its contribution",
                    rule_id="CLM-01",
                    confidence="confirmed",
                ))

    for row in active_relations:
        if row.get("source_type") != "claim" or row.get("relation_type") != "substantiates":
            continue
        claim = claim_by_id.get(row.get("source_id", ""), {})
        declared_contribution = claim.get("contribution_id", "")
        if declared_contribution and row.get("target_id") != declared_contribution:
            issues.append(issue(
                "cross-table-relation-mismatch",
                "high",
                f"argument_relations.csv:{row.get('relation_id', '')}",
                "claim substantiates a different contribution than claim_hierarchy.csv declares",
                rule_id="CLM-01",
                confidence="confirmed",
            ))

    claims_by_normalised_text: DefaultDict[str, List[str]] = defaultdict(list)
    for claim in claims:
        normalised = normalise_text(claim.get("claim_text", ""))
        if normalised:
            claims_by_normalised_text[normalised].append(claim.get("claim_id", ""))
    for duplicate_claim_ids in claims_by_normalised_text.values():
        valid_ids = sorted(claim_id for claim_id in duplicate_claim_ids if claim_id)
        if len(valid_ids) > 1:
            issues.append(issue(
                "duplicate-claim-candidate",
                "medium",
                "claim_hierarchy.csv:" + ",".join(valid_ids),
                "claims repeat the same normalised text; review merge or distinct roles",
                rule_id="CLM-03",
                confidence="confirmed",
            ))

    for gap in gaps:
        gap_id = gap.get("gap_id", "")
        if gap.get("gap_priority") != "core" or gap.get("gap_status") in {"closed", "superseded"}:
            continue
        gap_support = incoming(
            "gap", gap_id, {"supports"}, {"source", "prior_work", "evidence"}, True,
        )
        if not gap_support:
            issues.append(issue(
                "core-gap-evidence-thin",
                "high",
                f"gap_register.csv:{gap_id}",
                "core gap has no scope-matched source or problem-evidence relation",
                rule_id="GAP-01",
                confidence="confirmed",
            ))
        gap_contributions = incoming(
            "gap", gap_id, {"addresses"}, {"contribution"}, True,
        )
        if not gap_contributions:
            issues.append(issue(
                "unaddressed-core-gap",
                "high",
                f"gap_register.csv:{gap_id}",
                "core gap has no current contribution that addresses it",
                rule_id="GAP-02",
                confidence="confirmed",
            ))

    for claim in claims:
        claim_id = claim.get("claim_id", "")
        if claim.get("claim_level") not in MAIN_CLAIM_LEVELS:
            continue
        claim_support = incoming(
            "claim",
            claim_id,
            {"supports", "qualifies"},
            {"result", "source", "prior_work", "evidence", "artifact", "analysis", "data"},
            True,
        )
        if not claim_support:
            issues.append(issue(
                "main-claim-relation-thin",
                "high",
                f"claim_hierarchy.csv:{claim_id}",
                "main claim has no direct result, source, or evidence support relation",
                rule_id="CLM-01",
                confidence="confirmed",
            ))
        mismatched = [
            row for row in incoming(
                "claim", claim_id, {"supports", "qualifies"}, usable_only=False,
            )
            if row.get("status") == "verified"
            and row.get("directness") not in {"absent", "unverified"}
        ]
        if any(row.get("scope_match") == "mismatch" for row in mismatched):
            issues.append(issue(
                "claim-scope-exceeds-evidence",
                "critical",
                f"claim_hierarchy.csv:{claim_id}",
                "a supporting relation explicitly records a scope mismatch",
                rule_id="CLM-02",
                confidence="confirmed",
            ))
        refutations = incoming(
            "claim", claim_id, {"refutes", "contradicts"}, {"result", "source", "prior_work", "evidence"}, True,
        )
        if refutations and not claim.get("boundary_language"):
            issues.append(issue(
                "unbounded-conflicting-result",
                "high",
                f"claim_hierarchy.csv:{claim_id}",
                "a current relation refutes or contradicts the main claim but no boundary language is recorded",
                rule_id="RES-03",
                confidence="confirmed",
            ))

    active_data_ids = {
        row.get("object_id", "") for row in objects
        if row.get("object_type") == "data" and row.get("status") in ACTIVE_OBJECT_STATUSES
    }
    active_result_ids = {
        row.get("object_id", "") for row in objects
        if row.get("object_type") == "result" and row.get("status") in ACTIVE_OBJECT_STATUSES
    }
    for data_id in sorted(active_data_ids):
        if not outgoing("data", data_id, {"produces"}, {"result"}, True):
            issues.append(issue(
                "orphan-data",
                "low",
                f"evidence_objects.csv:{data_id}",
                "available data produce no result in the current argument graph",
                rule_id="DATA-01",
                confidence="confirmed",
            ))
    for result_id in sorted(active_result_ids):
        if not incoming("result", result_id, {"produces"}, {"data"}, True):
            issues.append(issue(
                "result-missing-data",
                "high",
                f"evidence_objects.csv:{result_id}",
                "result has no traceable data input",
                rule_id="DATA-02",
                confidence="confirmed",
            ))
        result_use = outgoing(
            "result", result_id, {"supports", "contradicts", "limits", "qualifies", "refutes", "substantiates"}, {"claim", "contribution"}, True,
        )
        if not result_use:
            issues.append(issue(
                "orphan-result",
                "medium",
                f"evidence_objects.csv:{result_id}",
                "result is not linked to a claim or contribution",
                rule_id="RES-01",
                confidence="confirmed",
            ))
            if object_by_id[result_id].get("status") == "verified":
                issues.append(issue(
                    "unclaimed-verified-result",
                    "medium",
                    f"evidence_objects.csv:{result_id}",
                    "verified result may be under-emphasised, but it is not automatically a new contribution",
                    rule_id="CON-03",
                    confidence="possible",
                ))

    innovation_signals: Dict[str, Dict[str, object]] = {}
    for innovation in innovations:
        innovation_id = innovation.get("innovation_id", "")
        contribution_id = innovation.get("contribution_id", "")
        declared_comparison_ids = set(
            split_ids(innovation.get("comparison_evidence_ids", ""))
        )
        positive_comparison_links = [
            row for row in incoming(
                "innovation",
                innovation_id,
                {"supports", "differentiates"},
                {"source", "prior_work", "evidence"},
                True,
            )
            if row.get("source_id") in declared_comparison_ids
        ]
        contradictory_links = incoming(
            "innovation",
            innovation_id,
            {"contradicts"},
            {"source", "prior_work", "evidence"},
            True,
        )
        limiting_links = incoming(
            "innovation",
            innovation_id,
            {"limits"},
            {"source", "prior_work", "evidence"},
            True,
        )
        characterisation = [
            row for row in outgoing(
                "innovation", innovation_id, {"characterises"}, {"contribution"}, True,
            )
            if row.get("target_id") == contribution_id
        ]
        any_characterisation = outgoing(
            "innovation", innovation_id, {"characterises"}, {"contribution"}, False,
        )
        if any_characterisation and not characterisation:
            issues.append(issue(
                "cross-table-relation-mismatch",
                "high",
                f"innovation_register.csv:{innovation_id}:contribution_id",
                "innovation characterises a different contribution than the register declares",
                rule_id="NOV-01",
                confidence="confirmed",
            ))
        if not positive_comparison_links or not characterisation:
            issues.append(issue(
                "innovation-relation-thin",
                "high",
                f"innovation_register.csv:{innovation_id}",
                "innovation needs positive declared comparison evidence and a reliable relation to its declared contribution",
                rule_id="NOV-01",
                confidence="confirmed",
            ))
        focus = focus_by_contribution.get(contribution_id, {})
        comparison_status = innovation.get("comparison_status", "")
        conflicted = bool(contradictory_links) or comparison_status == "contradicted"
        supported = bool(
            positive_comparison_links
            and characterisation
            and comparison_status == "supported"
            and not conflicted
        )
        partial = bool(limiting_links) or comparison_status == "partial"
        innovation_signals[innovation_id] = {
            "supported": supported,
            "partial": partial,
            "conflicted": conflicted,
            "positive_relation_ids": sorted(
                row.get("relation_id", "") for row in positive_comparison_links
            ),
            "counter_relation_ids": sorted(
                row.get("relation_id", "")
                for row in contradictory_links + limiting_links
            ),
        }
        if conflicted:
            issues.append(issue(
                "contradicted-innovation-evidence",
                "high" if focus.get("current_role") == "primary" else "medium",
                f"innovation_register.csv:{innovation_id}",
                "innovation comparison is contradicted by the register or a verified relation",
                rule_id="NOV-02",
                confidence="confirmed",
            ))
        if contradictory_links and comparison_status == "supported":
            issues.append(issue(
                "innovation-status-conflict",
                "high",
                f"innovation_register.csv:{innovation_id}:comparison_status",
                "comparison_status=supported conflicts with verified contradictory relations",
                rule_id="NOV-02",
                confidence="confirmed",
            ))

    contribution_signals: Dict[str, Dict[str, object]] = {}
    for contribution_id, contribution in contribution_by_id.items():
        declared_primary_claim_ids = set(
            split_ids(contribution.get("primary_claim_ids", ""))
        )
        linked_claim_rows = incoming(
            "contribution", contribution_id, {"substantiates"}, {"claim"}, True,
        )
        linked_claim_ids = {
            row.get("source_id", "") for row in linked_claim_rows
            if row.get("source_id") in declared_primary_claim_ids
            and claim_by_id.get(row.get("source_id", ""), {}).get("contribution_id")
            == contribution_id
        }
        direct_result_rows = incoming(
            "contribution", contribution_id, {"substantiates"}, {"result"}, True,
        )
        result_ids = {row.get("source_id", "") for row in direct_result_rows}
        for claim_id in linked_claim_ids:
            result_ids.update(
                row.get("source_id", "")
                for row in incoming(
                    "claim", claim_id, {"supports", "qualifies"}, {"result"}, True,
                )
            )
        data_ids: Set[str] = set()
        for result_id in result_ids:
            data_ids.update(
                row.get("source_id", "")
                for row in incoming("result", result_id, {"produces"}, {"data"}, True)
            )
        source_support_ids: Set[str] = set()
        artifact_support_ids: Set[str] = set()
        for claim_id in linked_claim_ids:
            source_support_ids.update(
                row.get("source_id", "")
                for row in incoming(
                    "claim", claim_id, {"supports"}, {"source", "prior_work", "evidence"}, True,
                )
            )
            artifact_support_ids.update(
                row.get("source_id", "")
                for row in incoming(
                    "claim", claim_id, {"supports"}, {"artifact", "analysis", "data"}, True,
                )
            )
        gap_rows = outgoing(
            "contribution", contribution_id, {"addresses"}, {"gap"}, True,
        )
        addressed_gap_ids = {row.get("target_id", "") for row in gap_rows}
        gap_relation_ids = {
            row.get("relation_id", "") for row in gap_rows
            if row.get("relation_id")
        }
        declared_gap_id = contribution.get("gap_id", "")
        declared_gap_addressed = declared_gap_id in addressed_gap_ids
        addresses_active_core_gap = bool(addressed_gap_ids & core_gap_ids)
        innovation_rows = incoming(
            "contribution", contribution_id, {"characterises"}, {"innovation"}, True,
        )
        linked_innovation_ids = {
            row.get("source_id", "") for row in innovation_rows
            if innovation_by_id.get(row.get("source_id", ""), {}).get("contribution_id")
            == contribution_id
        }
        declared_innovation_ids = {
            innovation_id for innovation_id, innovation in innovation_by_id.items()
            if innovation.get("contribution_id") == contribution_id
        }
        innovation_supported = any(
            bool(innovation_signals.get(innovation_id, {}).get("supported"))
            for innovation_id in declared_innovation_ids
        )
        innovation_conflicted = any(
            bool(innovation_signals.get(innovation_id, {}).get("conflicted"))
            for innovation_id in declared_innovation_ids
        )
        innovation_partial = any(
            bool(innovation_signals.get(innovation_id, {}).get("partial"))
            for innovation_id in declared_innovation_ids
        )
        innovation_support_ids: Set[str] = set()
        innovation_counter_relation_ids: Set[str] = set()
        for innovation_id in declared_innovation_ids:
            innovation_support_ids.update(split_ids(
                innovation_by_id.get(innovation_id, {}).get(
                    "comparison_evidence_ids", ""
                )
            ))
            innovation_counter_relation_ids.update(
                str(relation_id)
                for relation_id in innovation_signals.get(
                    innovation_id, {}
                ).get("counter_relation_ids", [])
                if relation_id
            )
        contribution_type = contribution.get("contribution_type", "")
        if contribution_type in EMPIRICAL_CONTRIBUTION_TYPES:
            evidence_chain_complete = bool(linked_claim_ids and result_ids and data_ids)
        elif contribution_type in TESTED_CONTRIBUTION_TYPES:
            evidence_chain_complete = bool(linked_claim_ids and (result_ids or artifact_support_ids))
        elif contribution_type in RESOURCE_CONTRIBUTION_TYPES:
            evidence_chain_complete = bool(linked_claim_ids and (data_ids or artifact_support_ids))
        elif contribution_type in SOURCE_LED_CONTRIBUTION_TYPES:
            evidence_chain_complete = bool(linked_claim_ids and source_support_ids)
        else:
            evidence_chain_complete = bool(linked_claim_ids and (result_ids or source_support_ids or artifact_support_ids))
        chain_complete = bool(evidence_chain_complete and declared_gap_addressed)
        conflict_count = 0
        for claim_id in linked_claim_ids:
            conflict_count += len(incoming(
                "claim", claim_id, {"refutes", "contradicts"}, {"result", "source", "prior_work", "evidence"}, True,
            ))
        support_ids = (
            result_ids | data_ids | source_support_ids | artifact_support_ids
            | innovation_support_ids
        )
        contribution_signals[contribution_id] = {
            "chain_complete": chain_complete,
            "evidence_chain_complete": evidence_chain_complete,
            "declared_gap_id": declared_gap_id,
            "declared_gap_addressed": declared_gap_addressed,
            "addresses_active_core_gap": addresses_active_core_gap,
            "addressed_gap_ids": sorted(addressed_gap_ids),
            "gap_relation_ids": sorted(gap_relation_ids),
            "claim_ids": sorted(linked_claim_ids),
            "result_ids": sorted(result_ids),
            "data_ids": sorted(data_ids),
            "innovation_ids": sorted(declared_innovation_ids),
            "reliably_linked_innovation_ids": sorted(linked_innovation_ids),
            "support_ids": support_ids,
            "conflict_count": conflict_count,
            "innovation_supported": innovation_supported,
            "innovation_conflicted": innovation_conflicted,
            "innovation_partial": innovation_partial,
            "innovation_counter_relation_ids": sorted(
                innovation_counter_relation_ids
            ),
        }
        focus = focus_by_contribution.get(contribution_id, {})
        if focus.get("current_role") == "primary" and not chain_complete:
            issues.append(issue(
                "primary-contribution-chain-thin",
                "critical",
                f"contribution_chain.csv:{contribution_id}",
                f"primary {contribution_type or 'contribution'} lacks its required evidence path",
                rule_id="CON-01",
                confidence="confirmed",
            ))
        if focus.get("current_role") == "primary" and not declared_gap_addressed:
            issues.append(issue(
                "primary-contribution-gap-orphan",
                "high",
                f"contribution_chain.csv:{contribution_id}",
                "primary contribution does not reliably address its declared current gap",
                rule_id="FIT-01",
                confidence="confirmed",
            ))
        gap_status = gap_by_id.get(declared_gap_id, {}).get("gap_status", "")
        if focus.get("current_role") == "primary" and gap_status in {"closed", "superseded"}:
            issues.append(issue(
                "primary-relies-on-inactive-gap",
                "high",
                f"contribution_chain.csv:{contribution_id}:gap_id",
                "current primary contribution still relies on a closed or superseded gap",
                rule_id="FIT-01",
                confidence="confirmed",
            ))

    for left_id, right_id in combinations(sorted(contribution_ids), 2):
        left = contribution_by_id.get(left_id, {})
        right = contribution_by_id.get(right_id, {})
        if left.get("contribution_type") != right.get("contribution_type"):
            continue
        left_support = set(contribution_signals.get(left_id, {}).get("support_ids", set()))
        right_support = set(contribution_signals.get(right_id, {}).get("support_ids", set()))
        if overlap_ratio(left_support, right_support) < redundancy_threshold:
            continue
        left_gaps = set(contribution_signals.get(left_id, {}).get("addressed_gap_ids", []))
        right_gaps = set(contribution_signals.get(right_id, {}).get("addressed_gap_ids", []))
        if not left_gaps.intersection(right_gaps):
            continue
        issues.append(issue(
            "redundant-contribution-candidate",
            "medium",
            f"contribution_chain.csv:{left_id},{right_id}",
            f"same-type contributions share at least {redundancy_threshold:.2f} of their mapped support and address the same gap; review merge or boundary clarification",
            rule_id="CON-02",
            confidence="possible",
        ))

    primary_ids = sorted(
        contribution_id for contribution_id, row in focus_by_contribution.items()
        if row.get("current_role") == "primary"
    )
    if not primary_ids:
        issues.append(issue(
            "missing-primary-contribution",
            "high",
            "contribution_focus.csv",
            "no current primary contribution is declared",
            rule_id="FIT-01",
            confidence="confirmed",
        ))
    if len(primary_ids) > 3:
        issues.append(issue(
            "many-primary-contributions",
            "medium",
            "contribution_focus.csv",
            "more than three primary contributions is an advisory focus warning, not proof of excess",
            rule_id="CON-02",
            confidence="possible",
        ))

    for intent_id, intent in intent_by_id.items():
        declared_main_ids = set(split_ids(intent.get("main_contribution_ids", "")))
        focus_primary_ids = {
            contribution_id for contribution_id in primary_ids
            if contribution_by_id.get(contribution_id, {}).get("intent_id") == intent_id
        }
        if declared_main_ids != focus_primary_ids:
            issues.append(issue(
                "cross-table-focus-mismatch",
                "medium",
                f"intent_register.csv:{intent_id}:main_contribution_ids",
                "intent main_contribution_ids and current focus primary roles differ",
                rule_id="FIT-01",
                confidence="confirmed",
            ))

    focus_review_candidates: List[Dict[str, object]] = []
    secondary_ids = sorted(
        contribution_id for contribution_id, row in focus_by_contribution.items()
        if row.get("current_role") in {"secondary", "enabling"}
    )
    for primary_id in primary_ids:
        focus = focus_by_contribution[primary_id]
        primary_intent_id = contribution_by_id.get(primary_id, {}).get(
            "intent_id", ""
        )
        signals = contribution_signals.get(primary_id, {})
        negative_dimensions: Dict[str, str] = {}
        if not signals.get("evidence_chain_complete"):
            negative_dimensions["evidence_chain"] = (
                "required evidence chain is incomplete"
            )
        gap_fit_signals: List[str] = []
        if focus.get("core_gap_fit") == "weak":
            gap_fit_signals.append("declared core-gap fit is weak")
        if not signals.get("addresses_active_core_gap"):
            gap_fit_signals.append(
                "no reliable relation reaches an active core gap"
            )
        if gap_fit_signals:
            negative_dimensions["gap_fit"] = "; ".join(gap_fit_signals)
        if focus.get("target_reader_fit") == "low":
            negative_dimensions["reader_fit"] = "target-reader fit is low"
        if focus.get("narrative_emphasis") == "absent":
            negative_dimensions["narrative"] = (
                "primary contribution is absent from the narrative"
            )
        if int(signals.get("conflict_count", 0)) > 0:
            negative_dimensions["result_consistency"] = (
                "current evidence includes unresolved conflicting relations"
            )
        if signals.get("innovation_conflicted"):
            negative_dimensions["innovation"] = (
                "current innovation comparison is contradicted"
            )
        elif signals.get("innovation_ids") and not signals.get("innovation_supported"):
            negative_dimensions["innovation"] = (
                "current innovation comparison is not fully supported"
            )
        negative_signals = [
            f"{dimension}: {message}"
            for dimension, message in sorted(negative_dimensions.items())
        ]
        if negative_signals:
            issues.append(issue(
                "primary-focus-misaligned",
                "high" if len(negative_signals) >= 2 else "medium",
                f"contribution_focus.csv:{primary_id}",
                "; ".join(negative_signals),
                rule_id="FIT-01",
                confidence="likely" if len(negative_signals) >= 2 else "possible",
            ))
        if len(negative_dimensions) < 2:
            continue
        for candidate_id in secondary_ids:
            candidate_focus = focus_by_contribution[candidate_id]
            candidate_signals = contribution_signals.get(candidate_id, {})
            candidate_intent_id = contribution_by_id.get(candidate_id, {}).get(
                "intent_id", ""
            )
            if (
                not primary_intent_id
                or candidate_intent_id != primary_intent_id
            ):
                continue
            if not candidate_signals.get("chain_complete"):
                continue
            if not candidate_signals.get("addresses_active_core_gap"):
                continue
            if candidate_focus.get("core_gap_fit") != "direct":
                continue
            if candidate_focus.get("target_reader_fit") not in {"high", "medium"}:
                continue
            if int(candidate_signals.get("conflict_count", 0)) > 0:
                continue
            if candidate_signals.get("innovation_conflicted"):
                continue
            counter_signals: List[Dict[str, object]] = []
            if is_true(focus.get("author_locked", "")):
                counter_signals.append({
                    "dimension": "author_governance",
                    "message": "current primary contribution is author-locked",
                    "relation_ids": [],
                })
            if candidate_focus.get("narrative_emphasis") in {"light", "absent"}:
                counter_signals.append({
                    "dimension": "narrative",
                    "message": "candidate is not yet prominent in the manuscript narrative",
                    "relation_ids": [],
                })
            if not candidate_signals.get("innovation_ids"):
                counter_signals.append({
                    "dimension": "innovation_coverage",
                    "message": "candidate has no registered innovation comparison",
                    "relation_ids": [],
                })
            elif not candidate_signals.get("innovation_supported"):
                counter_signals.append({
                    "dimension": "innovation_support",
                    "message": "candidate innovation comparison is partial or pending",
                    "relation_ids": candidate_signals.get(
                        "innovation_counter_relation_ids", []
                    ),
                })
            elif candidate_signals.get("innovation_partial"):
                counter_signals.append({
                    "dimension": "innovation_limits",
                    "message": "candidate innovation has verified limiting evidence",
                    "relation_ids": candidate_signals.get(
                        "innovation_counter_relation_ids", []
                    ),
                })
            if (
                candidate_signals.get("declared_gap_id")
                != signals.get("declared_gap_id")
            ):
                counter_signals.append({
                    "dimension": "gap_change",
                    "message": (
                        "candidate addresses a different declared gap; "
                        "paper-wide reframing may be required"
                    ),
                    "relation_ids": candidate_signals.get(
                        "gap_relation_ids", []
                    ),
                })
            candidate_positive_signals = [
                "required evidence chain uses verified, direct/partial, scope-matched relations",
                "a reliable relation connects the candidate to an active core gap",
                f"target-reader fit is {candidate_focus.get('target_reader_fit')}",
                "no verified unresolved conflicting claim relation is recorded",
            ]
            if candidate_signals.get("innovation_supported"):
                candidate_positive_signals.append(
                    "registered innovation has positive, declared comparison evidence"
                )
            candidate = {
                "intent_id": primary_intent_id,
                "current_primary_id": primary_id,
                "candidate_id": candidate_id,
                "trigger_rule_ids": ["FIT-01", "FIT-02"],
                "current_signals": negative_signals,
                "current_signal_dimensions": sorted(negative_dimensions),
                "candidate_signals": candidate_positive_signals,
                "counter_signals": counter_signals,
                "candidate_actions": [
                    "keep", "narrow", "promote", "demote", "merge", "remove",
                    "evidence_needed",
                ],
                "requires_author_approval": True,
                "approval_status": "required",
                "affected_section_ids": split_ids(
                    candidate_focus.get("section_ids", "")
                ),
                "revision_scope": "cannot_assess_before_author_decision",
                "snapshot_required": True,
                "recommended_next_skill": "pending_author_decision",
                "post_approval_routes": {
                    "manuscript-reframe": (
                        "use if the approved decision changes the research question, "
                        "core gap, title, abstract thesis, or paper-wide narrative"
                    ),
                    "thesis-control": (
                        "use for bounded section edits after the contribution focus is approved"
                    ),
                },
            }
            focus_review_candidates.append(candidate)
            issues.append(issue(
                "contribution-focus-review",
                "high",
                f"contribution_focus.csv:{primary_id}->{candidate_id}",
                "a secondary contribution has a complete, better-aligned chain while the current primary has multiple weaknesses; author review is required",
                rule_id="FIT-02",
                confidence="likely",
            ))

    summary = {
        "gaps": len(gaps),
        "claims": len(claims),
        "data_objects": len(object_ids_by_type.get("data", set())),
        "result_objects": len(object_ids_by_type.get("result", set())),
        "contributions": len(contributions),
        "innovations": len(innovations),
        "relations": len(relations),
        "primary_contributions": len(primary_ids),
        "focus_review_candidates": len(focus_review_candidates),
    }
    return focus_review_candidates, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate argument-governance CSV files.")
    parser.add_argument("project_root", help="Project root containing evidence/")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    parser.add_argument(
        "--strict-relations",
        action="store_true",
        help=(
            "require and validate the explicit gap/claim/data/result/contribution/"
            "innovation relation profile"
        ),
    )
    parser.add_argument(
        "--redundancy-threshold",
        type=float,
        default=0.8,
        help=(
            "support-set overlap used only to flag contribution merge candidates "
            "(default: 0.8)"
        ),
    )
    args = parser.parse_args()

    if not 0.0 <= args.redundancy_threshold <= 1.0:
        sys.stderr.write("error: --redundancy-threshold must be between 0 and 1\n")
        return 2

    root = Path(args.project_root)
    if not root.is_dir():
        sys.stderr.write("error: project_root is not a directory\n")
        return 2

    evidence_dir = root / "evidence"
    issues: List[Dict[str, str]] = []
    focus_review_candidates: List[Dict[str, object]] = []
    relation_summary: Dict[str, int] = {}
    if not evidence_dir.is_dir():
        issues.append(issue("missing-directory", "high", str(evidence_dir), "evidence/ directory is missing"))
        tables: Dict[str, List[Dict[str, str]]] = {
            name: [] for name in BASE_REQUIRED_COLUMNS
        }
        if args.strict_relations:
            tables.update({name: [] for name in RELATION_REQUIRED_COLUMNS})
    else:
        tables = validate_columns(evidence_dir, issues, BASE_REQUIRED_COLUMNS)
        for filename, rows in list(tables.items()):
            check_enums(filename, rows, issues)
        validate_relationships(tables, issues)
        if args.strict_relations:
            relation_tables = validate_columns(
                evidence_dir, issues, RELATION_REQUIRED_COLUMNS
            )
            for filename, rows in relation_tables.items():
                check_enums(filename, rows, issues)
                check_required_values(filename, rows, issues)
            tables.update(relation_tables)
            focus_review_candidates, relation_summary = validate_relation_profile(
                tables,
                issues,
                args.redundancy_threshold,
            )
            validate_focus_snapshot(
                evidence_dir,
                focus_review_candidates,
                tables,
                issues,
            )

    payload = {
        "schema_version": 2 if args.strict_relations else 1,
        "project_root": str(root),
        "profile": (
            "research-relations-v2" if args.strict_relations else "legacy-v1"
        ),
        "issue_count": len(issues),
        "issues": issues,
        "relation_summary": relation_summary,
        "focus_review_candidates": focus_review_candidates,
        "interpretation_boundary": (
            "Rule-based structural diagnostics do not establish scientific novelty, "
            "importance, correctness, or the right contribution focus. Focus changes "
            "require author approval."
        ),
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        for item in issues:
            print("{severity}: {location}: {kind}: {message}".format(**item))
        if not issues:
            print("argument governance packet looks structurally valid")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
