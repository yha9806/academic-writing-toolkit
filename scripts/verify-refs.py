#!/usr/bin/env python3
"""Offline-first academic reference verifier.

The default mode is deterministic and CI-safe: parse BibTeX, validate required
fields, duplicate keys, DOI shape, URL shape, and arXiv identifier shape.
Online metadata checks can be added later behind an explicit flag without
changing the offline contract.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

REQUIRED = {
    "article": ["title", "author", "year", "journal"],
    "inproceedings": ["title", "author", "year", "booktitle"],
    "book": ["title", "author", "year", "publisher"],
    "misc": ["title", "year"],
    "phdthesis": ["title", "author", "year", "school"],
    "techreport": ["title", "author", "year", "institution"],
}

ARXIV_NEW = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
ARXIV_OLD = re.compile(r"^[a-z-]+/\d{7}(v\d+)?$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def extract_bibtex(text: str) -> str:
    blocks = re.findall(r"```(?:bibtex|bib)\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
    return "\n\n".join(blocks) if blocks else text


def parse_bibtex(text: str) -> List[dict]:
    entries: List[dict] = []
    for m in re.finditer(r"@(?P<type>\w+)\s*\{\s*(?P<key>[^,]+),(?P<body>.*?)\n\}", text, flags=re.DOTALL):
        fields: Dict[str, str] = {}
        body = m.group("body")
        for fm in re.finditer(r"(?P<name>[A-Za-z_]+)\s*=\s*[\{\"](?P<value>.*?)[\}\"]\s*,?", body, flags=re.DOTALL):
            value = " ".join(fm.group("value").split())
            fields[fm.group("name").lower()] = value
        entries.append({"type": m.group("type").lower(), "key": m.group("key").strip(), "fields": fields})
    return entries


def audit_entries(entries: List[dict]) -> List[dict]:
    issues: List[dict] = []
    seen: Dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        key = entry["key"]
        if key in seen:
            issues.append({"kind": "duplicate-key", "severity": "high", "entry": key, "message": "BibTeX key is repeated."})
        seen[key] = index
        required = REQUIRED.get(entry["type"], ["title", "year"])
        for field in required:
            if not entry["fields"].get(field):
                issues.append({"kind": "missing-required-field", "severity": "high", "entry": key, "message": "Missing required field: {}".format(field)})
        doi = entry["fields"].get("doi")
        if doi and not DOI_RE.match(doi):
            issues.append({"kind": "doi-invalid", "severity": "medium", "entry": key, "message": "DOI format is invalid."})
        arxiv = entry["fields"].get("arxiv_id") or entry["fields"].get("eprint")
        if arxiv and not (ARXIV_NEW.match(arxiv) or ARXIV_OLD.match(arxiv)):
            issues.append({"kind": "arxiv-invalid", "severity": "medium", "entry": key, "message": "arXiv identifier format is invalid."})
        url = entry["fields"].get("url")
        if url and not re.match(r"^https?://", url):
            issues.append({"kind": "url-invalid", "severity": "medium", "entry": key, "message": "URL must start with http:// or https://."})
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify academic references from BibTeX.")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--bib", dest="bib_path")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    args = parser.parse_args()
    target = Path(args.bib_path or args.path or "")
    if not target.is_file():
        sys.stderr.write("error: input file not found\n")
        return 2
    text = extract_bibtex(target.read_text(encoding="utf-8"))
    entries = parse_bibtex(text)
    issues = audit_entries(entries)
    payload = {"schema_version": 1, "entries": len(entries), "issues": issues, "issue_count": len(issues)}
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        print("entries: {}".format(len(entries)))
        for issue in issues:
            print("{entry}: {kind}: {message}".format(**issue))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
