#!/usr/bin/env python3
"""Validate argument-governance CSV packets."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set


REQUIRED_COLUMNS = {
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
        "intent", "gap", "contribution", "claim", "evidence", "limitation",
    },
    "attack_category": {
        "novelty", "significance", "gap_validity",
        "claim_evidence_mismatch", "method_validity", "evaluation_strength",
        "generalization", "causal_overclaim", "related_work_coverage",
        "positioning", "reproducibility", "scope_boundary",
    },
    "defense_strength": {"none", "weak", "partial", "adequate", "strong"},
}

SEVERITY_ORDER = {"critical", "high", "medium", "low", "info"}
WEAK_DEFENSES = {"none", "weak", "partial"}
HIGH_SEVERITIES = {"critical", "high"}


def split_ids(value: str) -> List[str]:
    if not value:
        return []
    return [part.strip() for part in re.split(r"[;,|]", value) if part.strip()]


def issue(kind: str, severity: str, location: str, message: str) -> Dict[str, str]:
    return {
        "kind": kind,
        "severity": severity,
        "location": location,
        "message": message,
    }


def read_csv(path: Path) -> tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
        return rows, list(reader.fieldnames or [])


def validate_columns(evidence_dir: Path, issues: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    tables: Dict[str, List[Dict[str, str]]] = {}
    for filename, required in REQUIRED_COLUMNS.items():
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate argument-governance CSV files.")
    parser.add_argument("project_root", help="Project root containing evidence/")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()

    root = Path(args.project_root)
    if not root.is_dir():
        sys.stderr.write("error: project_root is not a directory\n")
        return 2

    evidence_dir = root / "evidence"
    issues: List[Dict[str, str]] = []
    if not evidence_dir.is_dir():
        issues.append(issue("missing-directory", "high", str(evidence_dir), "evidence/ directory is missing"))
        tables: Dict[str, List[Dict[str, str]]] = {name: [] for name in REQUIRED_COLUMNS}
    else:
        tables = validate_columns(evidence_dir, issues)
        for filename, rows in tables.items():
            check_enums(filename, rows, issues)
        validate_relationships(tables, issues)

    payload = {
        "schema_version": 1,
        "project_root": str(root),
        "issue_count": len(issues),
        "issues": issues,
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
