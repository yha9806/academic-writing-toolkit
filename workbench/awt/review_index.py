"""Local, quote-grounded thesis navigation and sparse candidate retrieval."""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter, defaultdict


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def chapter_key(document, block):
    return "c" + fingerprint([document["filename"], block.get("chapter", block["section"])])[:20]


def chapter_nodes(job):
    checked, reused = set(), set()
    for step in job["steps"]:
        if step["status"] == "completed" and step["phase"] == "text":
            checked.update(step["block_ids"])
            if step.get("reused_from"):
                reused.update(step["block_ids"])
    nodes = {}
    for document in job["documents"]:
        for block in document["blocks"]:
            key = chapter_key(document, block)
            node = nodes.setdefault(key, {"id": key, "document_id": document["id"], "filename": document["filename"],
                "title": block.get("chapter", block["section"]), "role": block["role"], "sections": [],
                "block_ids": [], "pages": [], "characters": 0, "checked_blocks": 0, "reused_blocks": 0})
            node["block_ids"].append(block["id"])
            node["characters"] += len(block["text"])
            node["checked_blocks"] += block["id"] in checked
            node["reused_blocks"] += block["id"] in reused
            if block["section"] not in node["sections"]:
                node["sections"].append(block["section"])
            if block["page"] is not None and block["page"] not in node["pages"]:
                node["pages"].append(block["page"])
    block_lookup = {b["id"]: b for d in job["documents"] for b in d["blocks"]}
    for node in nodes.values():
        node["total_blocks"] = len(node["block_ids"])
        node["content_hash"] = fingerprint([[block_lookup[i]["text"], block_lookup[i]["kind"],
            block_lookup[i]["section"], block_lookup[i]["role"]] for i in node["block_ids"]])
        node["page_start"] = min(node["pages"], default=None)
        node["page_end"] = max(node["pages"], default=None)
        node["status"] = "text_reviewed" if node["checked_blocks"] == node["total_blocks"] else "partial" if node["checked_blocks"] else "not_checked"
    return list(nodes.values())


def terms(text):
    words = re.findall(r"[a-z]{3,}|\d+(?:\.\d+)?%?|[\u3400-\u9fff]+", text.lower())
    stop = {"the", "and", "for", "with", "from", "this", "that", "were", "was", "are", "has", "have", "not", "page"}
    values = []
    for word in words:
        if word in stop:
            continue
        if re.match(r"[\u3400-\u9fff]", word):
            values.extend(word[i:i + 2] for i in range(max(1, len(word) - 1)))
        else:
            values.append(word)
    return set(values[:128])


def distributed(items, maximum):
    """Keep candidates from the entire source range, including the final pages."""
    if maximum <= 0:
        return []
    if maximum == 1:
        return list(items[:1])
    if len(items) <= maximum:
        return list(items)
    return [items[round(i * (len(items) - 1) / (maximum - 1))] for i in range(maximum)]


def related_pairs(left, right):
    """Symmetric sparse retrieval; every selected anchor gets a counterpart."""
    pairs, seen = [], set()
    for sources, targets, reverse in ((left, right, False), (right, left, True)):
        inverted = defaultdict(list)
        for index, item in enumerate(targets):
            for term in terms(item["text"]):
                inverted[term].append(index)
        for number, source in enumerate(sources):
            scores = Counter()
            for term in terms(source["text"]):
                matches = inverted.get(term, ())
                weight = math.log(1 + len(targets) / (1 + len(matches)))
                for index in matches:
                    scores[index] += weight
            if scores:
                best = max(scores.values())
                tied = [i for i, score in scores.items() if abs(score - best) < 1e-9]
                choice = tied[number % len(tied)]
            else:
                choice = number % len(targets)
            pair = (targets[choice], source) if reverse else (source, targets[choice])
            key = (pair[0]["id"], pair[1]["id"])
            if key not in seen:
                seen.add(key)
                pairs.append(pair)
    return pairs


def block_identity(block):
    return fingerprint([block["text"], block["kind"], block["section"], block["role"], block.get("chapter")])


def remap_result(value, mapping):
    if isinstance(value, list):
        return [remap_result(item, mapping) for item in value]
    if isinstance(value, dict):
        return {key: mapping.get(item, item) if key == "locator" else remap_result(item, mapping) for key, item in value.items()}
    return value
