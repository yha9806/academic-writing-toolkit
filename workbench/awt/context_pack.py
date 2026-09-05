"""Deterministic, hash-bound context packing for evidence-rich MVP reviews.

The module only parses local text.  It never executes uploaded code and never
consults model output when selecting excerpts or producing the preflight.
"""

from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


ALGORITHM_NAME = "generic_claim_anchor_pack"
ALGORITHM_VERSION = 2
SUPPORTED_ALGORITHM_VERSIONS = frozenset({1, 2})
ROUTE = "bounded_preflight"
WORKFLOW_SCOPES = {
    "argument-governance": "claim_evidence_alignment_only",
    "audit": "evidence_rich_accuracy_check",
    "self-review": "evidence_verification_only",
}
ELIGIBLE_WORKFLOWS_BY_VERSION = {
    1: frozenset({"audit", "self-review"}),
    2: frozenset(WORKFLOW_SCOPES),
}
ELIGIBLE_WORKFLOWS = ELIGIBLE_WORKFLOWS_BY_VERSION[ALGORITHM_VERSION]
FULL_CONTEXT_THRESHOLD = 20_000
MODEL_CONTEXT_TOKEN_LIMIT = 16_500
MAX_EXCERPT_CHARS = 2_800
MAX_ANCHORS = 80
MAX_CLAIM_ANCHORS = 20
MAX_STRUCTURE_ITEMS = 8
MAX_PARALLEL_JSON_BRANCHES = 4
MAX_PARALLEL_JSON_SCALAR_FIELDS = 6
MAX_PARALLEL_JSON_SEQUENCE_FIELDS = 2
MAX_PARALLEL_JSON_MAP_FIELDS = 1
MAX_PARALLEL_JSON_MAP_ITEMS = 12
MAX_DIRECT_COMPARISONS = 20
MAX_SELECTION_CANDIDATES = 140
NOTICE_ZH = "已使用相关片段和本地核验摘要，原文件未修改"

_NUMBER_RE = re.compile(r"(?<![\w.])[-+]?\d+(?:\.\d+)?%?(?![\w.])")
_RANGE_RE = re.compile(
    r"[\[(]\s*([-+]?\d+(?:\.\d+)?)\s*[,，–—-]\s*"
    r"([-+]?\d+(?:\.\d+)?)\s*[\])]"
)
_NUMERIC_PAIR_RE = re.compile(r"[-+]?\d+(?:\.\d+)?\s*(?:/|:)\s*[-+]?\d+(?:\.\d+)?")
_CITATION_RE = re.compile(
    r"\\cite\w*\{[^}]+\}|\[@?[A-Za-z][^]\n]{1,100}\]|"
    r"\([A-Z][A-Za-z-]+(?:\s+et\s+al\.)?,?\s+\d{4}[a-z]?\)"
)
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,}")
_CLAIM_RE = re.compile(
    r"\b(?:show|shows|shown|find|finds|found|demonstrat\w*|indicat\w*|"
    r"report\w*|result\w*|conclud\w*|support\w*|increase\w*|decrease\w*|"
    r"outperform\w*|compare\w*|estimate\w*|measure\w*|implement\w*)\b|"
    r"(?:结果|显示|表明|发现|证明|支持|提升|下降|比较|估计|测量|实现)",
    re.IGNORECASE,
)
_CODE_SUFFIXES = {".py", ".r", ".sh", ".ts", ".js"}
_TEXT_SUFFIXES = {
    ".bib",
    ".cfg",
    ".ini",
    ".log",
    ".md",
    ".tex",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_STOPWORDS = {
    "about",
    "after",
    "against",
    "also",
    "among",
    "and",
    "are",
    "been",
    "before",
    "between",
    "check",
    "from",
    "have",
    "into",
    "paper",
    "reported",
    "result",
    "results",
    "that",
    "the",
    "their",
    "this",
    "using",
    "value",
    "values",
    "were",
    "with",
}


class ContextPackError(ValueError):
    """A deterministic packing or verification failure."""


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


def estimate_tokens(text: str) -> dict[str, Any]:
    """Estimate prompt tokens with o200k when available, otherwise conservatively."""

    try:
        import tiktoken

        encoding = tiktoken.get_encoding("o200k_base")
        return {
            "estimator": "tiktoken",
            "encoding": "o200k_base",
            "version": getattr(tiktoken, "__version__", "unknown"),
            "tokens": len(encoding.encode(text)),
            "is_billing_value": False,
        }
    except (ImportError, KeyError):
        # The byte proxy deliberately overestimates typical English prose.
        return {
            "estimator": "utf8_bytes_div_3_ceiling",
            "encoding": None,
            "version": 1,
            "tokens": math.ceil(len(text.encode("utf-8")) / 3),
            "is_billing_value": False,
        }


def _normalise_number(value: str) -> str:
    suffix = "%" if value.endswith("%") else ""
    numeric = value[:-1] if suffix else value
    try:
        normalised = f"{float(numeric):.12g}"
    except ValueError:
        return value
    return normalised + suffix


def _terms(text: str) -> list[str]:
    counts = Counter(
        match.group(0).lower()
        for match in _WORD_RE.finditer(text)
        if match.group(0).lower() not in _STOPWORDS
    )
    return sorted(
        counts,
        key=lambda value: (-counts[value], -len(value), value),
    )[:MAX_ANCHORS]


def _line_spans(text: str) -> list[tuple[int, int, str, int]]:
    spans: list[tuple[int, int, str, int]] = []
    offset = 0
    lines = text.splitlines(keepends=True)
    if not lines and text:
        lines = [text]
    for number, line in enumerate(lines, start=1):
        end = offset + len(line)
        spans.append((offset, end, line, number))
        offset = end
    return spans


def _merge_ranges(ranges: Sequence[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if start >= end:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _bounded_window(
    spans: Sequence[tuple[int, int, str, int]], index: int, neighbours: int = 2
) -> tuple[int, int]:
    first = max(0, index - neighbours)
    last = min(len(spans) - 1, index + neighbours)
    start, end = spans[first][0], spans[last][1]
    if end - start <= MAX_EXCERPT_CHARS:
        return start, end
    centre = (spans[index][0] + spans[index][1]) // 2
    start = max(0, centre - MAX_EXCERPT_CHARS // 2)
    end = min(spans[-1][1], start + MAX_EXCERPT_CHARS)
    return max(0, end - MAX_EXCERPT_CHARS), end


def _chunk_ranges(text: str) -> list[tuple[int, int]]:
    spans = _line_spans(text)
    if not spans:
        return []
    chunks: list[tuple[int, int]] = []
    start = spans[0][0]
    end = start
    for line_start, line_end, _line, _number in spans:
        if line_end - start > MAX_EXCERPT_CHARS and end > start:
            chunks.append((start, end))
            start = line_start
        end = line_end
    if end > start:
        chunks.append((start, end))
    return chunks


def _source_documents(
    manuscript_text: str,
    filename: str,
    source_sha256: str,
    evidence_documents: Sequence[Mapping[str, object]],
) -> list[dict[str, Any]]:
    manuscript_bytes = manuscript_text.encode("utf-8")
    if _digest(manuscript_bytes) != source_sha256:
        raise ContextPackError("manuscript-hash-mismatch")
    documents: list[dict[str, Any]] = [
        {
            "source_id": "manuscript",
            "filename": Path(filename).name,
            "sha256": source_sha256,
            "text": manuscript_text,
            "kind": "manuscript",
        }
    ]
    for item in evidence_documents:
        content = item.get("content_bytes")
        if not isinstance(content, bytes):
            raise ContextPackError("evidence-content-missing")
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ContextPackError("evidence-not-utf8") from error
        source_id = str(item.get("evidence_id", ""))
        digest = _digest(content)
        if digest != item.get("sha256"):
            raise ContextPackError(f"evidence-hash-mismatch:{source_id}")
        documents.append(
            {
                "source_id": source_id,
                "filename": str(item.get("filename", "")),
                "sha256": digest,
                "text": text,
                "kind": "evidence",
            }
        )
    return documents


def _csv_structure(text: str) -> tuple[dict[str, Any], list[str]]:
    limitations: list[str] = []
    try:
        rows = list(csv.reader(io.StringIO(text)))
    except csv.Error as error:
        return {"parse_status": "blocked", "error": str(error)[:200]}, [
            "CSV could not be parsed; no row-level comparison was inferred."
        ]
    if not rows:
        return {"parse_status": "parsed", "row_count": 0, "columns": []}, limitations
    columns = rows[0][:MAX_STRUCTURE_ITEMS]
    counters = [Counter() for _ in columns]
    numeric_ranges: list[list[float]] = [[] for _ in columns]
    for row in rows[1:]:
        for index, value in enumerate(row[: len(columns)]):
            stripped = value.strip()
            if stripped:
                counters[index][stripped] += 1
                try:
                    numeric_ranges[index].append(float(stripped.rstrip("%")))
                except ValueError:
                    pass
    profiles = []
    for index, name in enumerate(columns):
        profile: dict[str, Any] = {
            "name": name,
            "nonempty": sum(counters[index].values()),
            "top_values": [
                {"value": value[:80], "count": count}
                for value, count in sorted(
                    counters[index].items(), key=lambda item: (-item[1], item[0])
                )[:3]
            ],
        }
        if numeric_ranges[index]:
            profile["numeric_min"] = min(numeric_ranges[index])
            profile["numeric_max"] = max(numeric_ranges[index])
        profiles.append(profile)
    if len(rows[0]) > MAX_STRUCTURE_ITEMS:
        limitations.append("CSV column profiles were capped deterministically.")
    return {
        "parse_status": "parsed",
        "row_count": max(0, len(rows) - 1),
        "columns": profiles,
    }, limitations


def _flatten_json(
    value: object,
    path: str = "$",
    output: list[dict[str, Any]] | None = None,
    *,
    limit: int = MAX_STRUCTURE_ITEMS,
) -> list[dict[str, Any]]:
    if output is None:
        output = []
    if len(output) >= limit:
        return output
    if isinstance(value, Mapping):
        for key in sorted(value, key=str):
            _flatten_json(value[key], f"{path}.{key}", output, limit=limit)
            if len(output) >= limit:
                break
    elif isinstance(value, list):
        output.append({"path": path, "type": "array", "length": len(value)})
        for index, item in enumerate(value[:5]):
            _flatten_json(item, f"{path}[{index}]", output, limit=limit)
            if len(output) >= limit:
                break
    else:
        scalar = value
        if isinstance(scalar, str):
            scalar = scalar[:80]
        output.append({"path": path, "type": type(value).__name__, "value": scalar})
    return output


def _json_scalar(value: object) -> object:
    if isinstance(value, str):
        return value[:80]
    return value


def _parallel_json_object_summary(value: object) -> dict[str, Any] | None:
    """Expose bounded sibling-object values without inferring their meaning."""

    if not isinstance(value, Mapping):
        return None
    branches = [
        (str(key), child)
        for key, child in sorted(value.items(), key=lambda item: str(item[0]))
        if isinstance(child, Mapping)
    ][:MAX_PARALLEL_JSON_BRANCHES]
    if len(branches) < 2:
        return None

    shared_fields = set.intersection(
        *(set(str(key) for key in child) for _branch, child in branches)
    )
    scalar_fields = [
        field
        for field in sorted(shared_fields)
        if all(
            not isinstance(child.get(field), (Mapping, list))
            for _branch, child in branches
        )
    ][:MAX_PARALLEL_JSON_SCALAR_FIELDS]
    sequence_fields = [
        field
        for field in sorted(shared_fields)
        if all(
            isinstance(child.get(field), list)
            and len(child[field]) <= 8
            and all(not isinstance(item, (Mapping, list)) for item in child[field])
            for _branch, child in branches
        )
    ][:MAX_PARALLEL_JSON_SEQUENCE_FIELDS]

    scalar_map_fields: list[dict[str, Any]] = []
    for field in sorted(shared_fields):
        if not all(
            isinstance(child.get(field), Mapping) for _branch, child in branches
        ):
            continue
        shared_map_keys = set.intersection(
            *(set(str(key) for key in child[field]) for _branch, child in branches)
        )
        scalar_map_keys = [
            key
            for key in sorted(shared_map_keys)
            if all(
                not isinstance(child[field].get(key), (Mapping, list))
                for _branch, child in branches
            )
        ][:MAX_PARALLEL_JSON_MAP_ITEMS]
        if not scalar_map_keys:
            continue
        scalar_map_fields.append(
            {
                "field": field,
                "keys": scalar_map_keys,
                "values": {
                    branch: {
                        key: _json_scalar(child[field][key]) for key in scalar_map_keys
                    }
                    for branch, child in branches
                },
            }
        )
        if len(scalar_map_fields) >= MAX_PARALLEL_JSON_MAP_FIELDS:
            break

    if not scalar_fields and not sequence_fields and not scalar_map_fields:
        return None
    return {
        "parent_path": "$",
        "branches": [branch for branch, _child in branches],
        "shared_scalar_values": [
            {
                "field": field,
                "values": {
                    branch: _json_scalar(child[field]) for branch, child in branches
                },
            }
            for field in scalar_fields
        ],
        "shared_sequence_values": [
            {
                "field": field,
                "values": {
                    branch: [_json_scalar(item) for item in child[field]]
                    for branch, child in branches
                },
            }
            for field in sequence_fields
        ],
        "shared_scalar_maps": scalar_map_fields,
        "scientific_interpretation": "not_inferred",
    }


def _json_structure(
    text: str, *, algorithm_version: int
) -> tuple[dict[str, Any], list[str]]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as error:
        return {
            "parse_status": "blocked",
            "error": f"line {error.lineno}: {error.msg}",
        }, ["JSON could not be parsed; no key/value comparison was inferred."]
    scalars = _flatten_json(value)
    limitations = []
    if len(scalars) >= MAX_STRUCTURE_ITEMS:
        limitations.append("JSON structural paths were capped deterministically.")
    structure = {
        "parse_status": "parsed",
        "root_type": type(value).__name__,
        "paths": scalars,
    }
    if algorithm_version >= 2:
        parallel_summary = _parallel_json_object_summary(value)
        if parallel_summary is not None:
            structure["parallel_object_summary"] = parallel_summary
    return structure, limitations


def _python_structure(text: str) -> tuple[dict[str, Any], list[str]]:
    try:
        tree = ast.parse(text)
    except SyntaxError as error:
        return {
            "parse_status": "blocked",
            "error": f"line {error.lineno}: {error.msg}",
        }, ["Python syntax could not be parsed; the file was never executed."]
    symbols = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols.append(
                {
                    "kind": type(node).__name__,
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": getattr(node, "end_lineno", node.lineno),
                }
            )
    symbols.sort(key=lambda item: (int(item["line_start"]), str(item["name"])))
    return {
        "parse_status": "parsed",
        "symbols": symbols[:MAX_STRUCTURE_ITEMS],
        "executed": False,
    }, (
        ["Python symbol inventory was capped deterministically."]
        if len(symbols) > MAX_STRUCTURE_ITEMS
        else []
    )


def _inspect_document(
    document: Mapping[str, Any], *, algorithm_version: int
) -> tuple[dict[str, Any], list[str]]:
    text = str(document["text"])
    suffix = Path(str(document["filename"])).suffix.lower()
    if suffix == ".csv":
        structure, limitations = _csv_structure(text)
        file_type = "csv"
    elif suffix == ".json":
        structure, limitations = _json_structure(
            text, algorithm_version=algorithm_version
        )
        file_type = "json"
    elif suffix == ".py":
        structure, limitations = _python_structure(text)
        file_type = "python"
    elif suffix in _CODE_SUFFIXES:
        structure = {
            "parse_status": "text_only",
            "line_count": len(text.splitlines()),
            "executed": False,
        }
        limitations = ["Code was treated as text and was never executed."]
        file_type = "code_text"
    else:
        headings = [
            {"line": number, "text": line.strip()[:160]}
            for _start, _end, line, number in _line_spans(text)
            if line.lstrip().startswith(("#", "\\section", "\\subsection"))
        ][:MAX_STRUCTURE_ITEMS]
        structure = {
            "parse_status": "text",
            "line_count": len(text.splitlines()),
            "headings": headings,
        }
        limitations = []
        file_type = "text" if suffix in _TEXT_SUFFIXES else "unknown_text"
    if document["kind"] == "evidence" and file_type in {
        "python",
        "code_text",
        "text",
        "unknown_text",
    }:
        numeric_statements = []
        for _start, _end, line, number in _line_spans(text):
            values = _NUMBER_RE.findall(line)
            percentages = [value for value in values if value.endswith("%")]
            if not (
                len(percentages) >= 2
                or _RANGE_RE.search(line)
                or _NUMERIC_PAIR_RE.search(line)
            ):
                continue
            numeric_statements.append(
                {
                    "line": number,
                    "values": values[:8],
                    "text": line.strip()[:200],
                    "scientific_interpretation": "not_inferred",
                }
            )
        if numeric_statements:
            structure["numeric_statement_anchors"] = numeric_statements[:2]
    return {
        "source_id": document["source_id"],
        "filename": document["filename"],
        "sha256": document["sha256"],
        "size_bytes": len(text.encode("utf-8")),
        "file_type": file_type,
        "structure": structure,
    }, limitations


def _claim_anchors(
    text: str, *, limit: int = MAX_CLAIM_ANCHORS
) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for _start, _end, line, number in _line_spans(text):
        stripped = line.strip()
        if not stripped:
            continue
        reasons = []
        if _NUMBER_RE.search(stripped):
            reasons.append("number")
        if _CITATION_RE.search(stripped):
            reasons.append("citation")
        if _CLAIM_RE.search(stripped):
            reasons.append("claim_statement")
        if reasons:
            anchors.append(
                {
                    "line": number,
                    "reasons": reasons,
                    "text": stripped[:480],
                }
            )
        if len(anchors) >= limit:
            break
    return anchors


def _find_line_candidates(
    document: Mapping[str, Any],
    anchor_terms: Sequence[str],
    anchor_numbers: set[str],
    *,
    manuscript: bool,
) -> list[dict[str, Any]]:
    text = str(document["text"])
    spans = _line_spans(text)
    candidates: list[dict[str, Any]] = []
    suffix = Path(str(document["filename"])).suffix.lower()
    for index, (_start, _end, line, number) in enumerate(spans):
        lowered = line.lower()
        numbers = {_normalise_number(item) for item in _NUMBER_RE.findall(line)}
        term_hits = sum(term in lowered for term in anchor_terms)
        number_hits = len(numbers & anchor_numbers)
        score = term_hits * 2 + number_hits * 4
        if manuscript:
            score += int(bool(_CLAIM_RE.search(line))) * 3
            score += int(bool(_CITATION_RE.search(line))) * 2
            score += int(bool(_NUMBER_RE.search(line))) * 2
        if score <= 0:
            continue
        start, end = _bounded_window(spans, index, neighbours=2)
        candidates.append(
            {
                "source_id": document["source_id"],
                "filename": document["filename"],
                "source_sha256": document["sha256"],
                "char_start": start,
                "char_end": end,
                "score": score,
                "line": number,
                "selection_reason": "claim_or_shared_anchor",
            }
        )
    unique = {
        (str(item["source_id"]), int(item["char_start"]), int(item["char_end"])): item
        for item in candidates
    }
    candidates = list(unique.values())
    candidates.sort(
        key=lambda item: (
            -int(item["score"]),
            str(item["source_id"]),
            int(item["char_start"]),
        )
    )
    # Raw structured evidence is only sent when it contains a shared anchor.
    if suffix in {".csv", ".json"}:
        candidates = [item for item in candidates if int(item["score"]) >= 4]
    return candidates[: (60 if manuscript else 12)]


def _range_candidates(
    manuscript_text: str, documents: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    manuscript_ranges = [
        [float(match.group(1)), float(match.group(2))]
        for match in _RANGE_RE.finditer(manuscript_text)
    ][:20]
    evidence_ranges: list[dict[str, Any]] = []
    for document in documents[1:]:
        if Path(str(document["filename"])).suffix.lower() != ".json":
            continue
        try:
            value = json.loads(str(document["text"]))
        except json.JSONDecodeError:
            continue
        flattened = _flatten_json(value, output=[], limit=200)
        numeric = {
            str(item["path"]): float(item["value"])
            for item in flattened
            if isinstance(item.get("value"), (int, float))
        }
        for path, lower in sorted(numeric.items()):
            match = re.search(r"(.+?)(?:[._-](?:y_?)?min)$", path, re.IGNORECASE)
            if not match:
                continue
            prefix = match.group(1)
            upper_path = next(
                (
                    candidate
                    for candidate in numeric
                    if re.fullmatch(
                        re.escape(prefix) + r"(?:[._-](?:y_?)?max)",
                        candidate,
                        re.IGNORECASE,
                    )
                ),
                None,
            )
            if upper_path:
                evidence_ranges.append(
                    {
                        "source_id": document["source_id"],
                        "lower_path": path,
                        "upper_path": upper_path,
                        "range": [lower, numeric[upper_path]],
                    }
                )
    comparisons = []
    for reported in manuscript_ranges:
        for observed in evidence_ranges[:20]:
            comparisons.append(
                {
                    "kind": "range_literal_comparison",
                    "manuscript_range": reported,
                    "evidence_source_id": observed["source_id"],
                    "evidence_paths": [
                        observed["lower_path"],
                        observed["upper_path"],
                    ],
                    "evidence_range": observed["range"],
                    "result": (
                        "same_literal_values"
                        if reported == observed["range"]
                        else "different_literal_values"
                    ),
                    "scientific_interpretation": "not_inferred",
                }
            )
    comparisons.sort(
        key=lambda item: (
            -sum(
                left == right
                for left, right in zip(item["manuscript_range"], item["evidence_range"])
            ),
            sum(
                abs(left - right)
                for left, right in zip(item["manuscript_range"], item["evidence_range"])
            ),
            str(item["evidence_source_id"]),
            str(item["evidence_paths"]),
            str(item["manuscript_range"]),
        )
    )
    return comparisons[:10]


def _direct_comparisons(
    manuscript_text: str, documents: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    manuscript_numbers = {
        _normalise_number(value) for value in _NUMBER_RE.findall(manuscript_text)
    }
    comparisons = _range_candidates(manuscript_text, documents)
    for document in documents[1:]:
        evidence_numbers = {
            _normalise_number(value)
            for value in _NUMBER_RE.findall(str(document["text"]))
        }
        for value in sorted(manuscript_numbers & evidence_numbers)[:6]:
            comparisons.append(
                {
                    "kind": "shared_numeric_literal",
                    "value": value,
                    "source_id": document["source_id"],
                    "result": "same_literal_observed",
                    "scientific_interpretation": "not_inferred",
                }
            )
            if len(comparisons) >= MAX_DIRECT_COMPARISONS:
                return comparisons
    return comparisons[:MAX_DIRECT_COMPARISONS]


def _excerpt(
    document: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    start = int(candidate["char_start"])
    end = int(candidate["char_end"])
    text = str(document["text"])[start:end]
    return {
        "source_id": document["source_id"],
        "filename": document["filename"],
        "source_sha256": document["sha256"],
        "char_start": start,
        "char_end": end,
        "excerpt_sha256": _digest(text.encode("utf-8")),
        "selection_reason": candidate["selection_reason"],
        "text": text,
    }


def _omitted_summary(
    documents: Sequence[Mapping[str, Any]], excerpts: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    summaries = []
    for document in documents:
        ranges = _merge_ranges(
            [
                (int(item["char_start"]), int(item["char_end"]))
                for item in excerpts
                if item["source_id"] == document["source_id"]
            ]
        )
        included = sum(end - start for start, end in ranges)
        total = len(str(document["text"]))
        summaries.append(
            {
                "source_id": document["source_id"],
                "total_chars": total,
                "included_chars": included,
                "omitted_chars": total - included,
                "coverage": "partial" if included < total else "complete",
            }
        )
    return summaries


def _preflight(
    documents: Sequence[Mapping[str, Any]],
    manuscript_anchors: Sequence[Mapping[str, Any]],
    comparisons: Sequence[Mapping[str, Any]],
    excerpts: Sequence[Mapping[str, Any]],
    *,
    algorithm_version: int,
) -> dict[str, Any]:
    inventory = []
    limitations: list[str] = []
    for document in documents:
        inspected, item_limitations = _inspect_document(
            document, algorithm_version=algorithm_version
        )
        inventory.append(inspected)
        limitations.extend(
            f"{document['source_id']}: {limitation}" for limitation in item_limitations
        )
    omitted = _omitted_summary(documents, excerpts)
    if any(item["omitted_chars"] for item in omitted):
        limitations.append(
            "Only listed ranges and structural summaries were available to the model; "
            "omitted bytes were not checked."
        )
    if len(manuscript_anchors) >= MAX_CLAIM_ANCHORS:
        limitations.append("Manuscript claim anchors were capped deterministically.")
    return {
        "schema_version": 1,
        "kind": "generic_deterministic_preflight",
        "algorithm": {
            "name": ALGORITHM_NAME,
            "version": algorithm_version,
        },
        "inventory": inventory,
        "manuscript_claim_anchors": list(manuscript_anchors),
        "direct_comparisons": list(comparisons),
        "missing_materials": (
            []
            if len(documents) > 1
            else ["No evidence file was supplied for local comparison."]
        ),
        "omitted_material": omitted,
        "limitations": sorted(set(limitations)),
        "scientific_facts_inferred": False,
        "code_executed": False,
        "human_effect_evidence": False,
    }


def _pack_payload(
    author_goal: str,
    workflow_scope: str,
    documents: Sequence[Mapping[str, Any]],
    excerpts: Sequence[Mapping[str, Any]],
    *,
    algorithm_version: int,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "generic_hash_bound_context_pack",
        "algorithm": {"name": ALGORITHM_NAME, "version": algorithm_version},
        "author_goal": author_goal,
        "workflow_scope": workflow_scope,
        "source_inventory": [
            {
                "source_id": document["source_id"],
                "filename": document["filename"],
                "sha256": document["sha256"],
                "size_bytes": len(str(document["text"]).encode("utf-8")),
            }
            for document in documents
        ],
        "excerpts": list(excerpts),
    }


def _model_context(pack: Mapping[str, Any], preflight: Mapping[str, Any]) -> str:
    limitations = preflight.get("limitations", [])
    boundary = (
        "Do not claim to have checked omitted material. Reflect the coverage boundary "
        "in limitations and required_materials whenever it affects a finding."
    )
    if pack.get("workflow_scope") == "evidence_verification_only":
        boundary += (
            " For self-review, use this bounded route only for evidence verification; "
            "do not assess whole-manuscript structure or contribution from excerpts."
        )
    elif pack.get("workflow_scope") == "claim_evidence_alignment_only":
        boundary += (
            " For argument-governance, assess only claim-evidence-inference-boundary "
            "relationships visible in the included excerpts and inventory; do not "
            "claim complete argument hierarchy, cross-section coverage, contribution "
            "completeness, or global evidence balance from omitted material."
        )
    return "\n".join(
        [
            "<bounded-context-pack>",
            _json_bytes(pack).decode("utf-8").rstrip(),
            "</bounded-context-pack>",
            "<deterministic-preflight>",
            _json_bytes(preflight).decode("utf-8").rstrip(),
            "</deterministic-preflight>",
            "<coverage-boundary>",
            boundary,
            *[f"- {item}" for item in limitations if isinstance(item, str)],
            "</coverage-boundary>",
        ]
    )


def build_context_route(
    *,
    full_context: str,
    manuscript_text: str,
    filename: str,
    source_sha256: str,
    workflow_id: str,
    author_goal: str,
    evidence_documents: Sequence[Mapping[str, object]],
    full_context_threshold: int = FULL_CONTEXT_THRESHOLD,
    model_context_token_limit: int = MODEL_CONTEXT_TOKEN_LIMIT,
    algorithm_version: int | None = None,
) -> dict[str, Any]:
    """Return the unchanged full route or a deterministic bounded-preflight route."""

    version = ALGORITHM_VERSION if algorithm_version is None else algorithm_version
    if version not in SUPPORTED_ALGORITHM_VERSIONS:
        raise ContextPackError(f"unsupported-algorithm-version:{version}")
    original_estimate = estimate_tokens(full_context)
    if (
        workflow_id not in ELIGIBLE_WORKFLOWS_BY_VERSION[version]
        or not evidence_documents
        or int(original_estimate["tokens"]) <= full_context_threshold
    ):
        return {
            "route": "full_context",
            "model_context": full_context,
            "original_context_estimate": original_estimate,
            "model_context_estimate": original_estimate,
            "context_pack_manifest": None,
            "deterministic_preflight": None,
            "coverage_notice": None,
            "coverage_limitations": [],
        }

    documents = _source_documents(
        manuscript_text,
        filename,
        source_sha256,
        evidence_documents,
    )
    meaningful = [
        line.strip()
        for line in manuscript_text.splitlines()
        if len(line.strip()) >= 24 and len(_WORD_RE.findall(line)) >= 4
    ]
    if not meaningful:
        raise ContextPackError("insufficient-manuscript-context")

    selection_anchors = _claim_anchors(manuscript_text, limit=2_000)
    manuscript_anchors = sorted(
        selection_anchors,
        key=lambda item: (
            -len(item["reasons"]),
            -len(_NUMBER_RE.findall(str(item["text"]))),
            int(item["line"]),
        ),
    )[:MAX_CLAIM_ANCHORS]
    goal_terms = _terms(author_goal)
    anchor_terms = _terms(
        author_goal + "\n" + "\n".join(item["text"] for item in selection_anchors)
    )
    anchor_terms = list(dict.fromkeys([*goal_terms, *anchor_terms]))[:MAX_ANCHORS]
    anchor_numbers = {
        _normalise_number(value)
        for item in selection_anchors
        for value in _NUMBER_RE.findall(str(item["text"]))
    }
    comparisons = _direct_comparisons(manuscript_text, documents)
    workflow_scope = WORKFLOW_SCOPES[workflow_id]

    candidates: list[dict[str, Any]] = []
    manuscript_chunks = _chunk_ranges(manuscript_text)
    if not manuscript_chunks:
        raise ContextPackError("insufficient-manuscript-context")
    candidates.append(
        {
            "source_id": "manuscript",
            "filename": filename,
            "source_sha256": source_sha256,
            "char_start": manuscript_chunks[0][0],
            "char_end": manuscript_chunks[0][1],
            "score": 10_000,
            "line": 1,
            "selection_reason": "required_manuscript_context",
            "required": True,
            "priority": 0,
        }
    )
    for document in documents:
        document_candidates = _find_line_candidates(
            document,
            anchor_terms,
            anchor_numbers,
            manuscript=document["source_id"] == "manuscript",
        )
        for rank, candidate in enumerate(document_candidates):
            candidates.append(
                {
                    **candidate,
                    "required": False,
                    "priority": (1 if rank == 0 else min(3, rank + 1)),
                }
            )
    for start, end in manuscript_chunks[1:]:
        candidates.append(
            {
                "source_id": "manuscript",
                "filename": filename,
                "source_sha256": source_sha256,
                "char_start": start,
                "char_end": end,
                "score": 0,
                "line": 0,
                "selection_reason": "deterministic_manuscript_fill",
                "required": False,
                "priority": 4,
            }
        )
    unique_candidates: dict[tuple[str, int, int], dict[str, Any]] = {}
    for item in candidates:
        key = (
            str(item["source_id"]),
            int(item["char_start"]),
            int(item["char_end"]),
        )
        if key not in unique_candidates or item["required"]:
            unique_candidates[key] = item
    candidates = list(unique_candidates.values())
    candidates.sort(
        key=lambda item: (
            int(item["priority"]),
            -int(item["score"]),
            str(item["source_id"]),
            int(item["char_start"]),
        )
    )
    candidates = candidates[:MAX_SELECTION_CANDIDATES]

    by_id = {document["source_id"]: document for document in documents}
    selected: list[dict[str, Any]] = []
    selected_ranges: dict[str, list[tuple[int, int]]] = {}
    for candidate in candidates:
        source_id = str(candidate["source_id"])
        start, end = int(candidate["char_start"]), int(candidate["char_end"])
        if any(
            existing_start < end and start < existing_end
            for existing_start, existing_end in selected_ranges.get(source_id, [])
        ):
            continue
        proposed = [
            *selected,
            _excerpt(by_id[source_id], candidate),
        ]
        proposed.sort(
            key=lambda item: (str(item["source_id"]), int(item["char_start"]))
        )
        proposed_preflight = _preflight(
            documents,
            manuscript_anchors,
            comparisons,
            proposed,
            algorithm_version=version,
        )
        proposed_pack = _pack_payload(
            author_goal,
            workflow_scope,
            documents,
            proposed,
            algorithm_version=version,
        )
        proposed_context = _model_context(proposed_pack, proposed_preflight)
        if int(estimate_tokens(proposed_context)["tokens"]) > model_context_token_limit:
            if candidate["required"]:
                raise ContextPackError("required-context-exceeds-token-budget")
            continue
        selected = proposed
        selected_ranges.setdefault(source_id, []).append((start, end))

    if not any(item["source_id"] == "manuscript" for item in selected):
        raise ContextPackError("bounded-pack-missing-manuscript")
    preflight = _preflight(
        documents,
        manuscript_anchors,
        comparisons,
        selected,
        algorithm_version=version,
    )
    pack = _pack_payload(
        author_goal,
        workflow_scope,
        documents,
        selected,
        algorithm_version=version,
    )
    model_context = _model_context(pack, preflight)
    model_estimate = estimate_tokens(model_context)
    if int(model_estimate["tokens"]) > model_context_token_limit:
        raise ContextPackError("bounded-pack-token-budget-exceeded")

    pack_bytes = _json_bytes(pack)
    preflight_bytes = _json_bytes(preflight)
    omitted = preflight["omitted_material"]
    manifest = {
        "schema_version": 1,
        "route": ROUTE,
        "algorithm": {
            "name": ALGORITHM_NAME,
            "version": version,
            "selection_inputs": [
                "workflow",
                "author_goal",
                "manuscript_claim_number_citation_anchors",
                "file_type",
                "local_line_neighbourhood",
            ],
            "response_used_for_selection": False,
            "code_executed": False,
        },
        "workflow_scope": workflow_scope,
        "original_context_estimate": original_estimate,
        "pack_tokens": estimate_tokens(pack_bytes.decode("utf-8")),
        "model_context_tokens": model_estimate,
        "token_limit": model_context_token_limit,
        "pack_sha256": _digest(pack_bytes),
        "model_context_sha256": _digest(model_context.encode("utf-8")),
        "preflight_sha256": _digest(preflight_bytes),
        "source_hashes": {
            document["source_id"]: document["sha256"] for document in documents
        },
        "included_ranges": [
            {
                key: item[key]
                for key in (
                    "source_id",
                    "filename",
                    "source_sha256",
                    "char_start",
                    "char_end",
                    "excerpt_sha256",
                    "selection_reason",
                )
            }
            for item in selected
        ],
        "omitted_material": omitted,
        "human_effect_evidence": False,
    }
    coverage_limitations = [
        (
            f"{item['source_id']}: included {item['included_chars']} of "
            f"{item['total_chars']} characters; omitted material was not checked."
        )
        for item in omitted
        if item["omitted_chars"]
    ]
    return {
        "route": ROUTE,
        "model_context": model_context,
        "original_context_estimate": original_estimate,
        "model_context_estimate": model_estimate,
        "context_pack_manifest": manifest,
        "deterministic_preflight": preflight,
        "coverage_notice": NOTICE_ZH,
        "coverage_limitations": coverage_limitations,
    }
