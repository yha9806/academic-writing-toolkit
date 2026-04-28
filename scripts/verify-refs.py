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
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

CROSSREF_BASE = "https://api.crossref.org/works/"
SEMANTIC_SCHOLAR_BASE = "https://api.semanticscholar.org/graph/v1/paper/"
ARXIV_BASE = "https://export.arxiv.org/api/query"


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


def normalize_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def jaccard_similarity(a: str, b: str) -> float:
    left = set(normalize_text(a).split())
    right = set(normalize_text(b).split())
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return float(len(left & right)) / float(len(left | right))


def bib_year(entry: dict) -> Optional[int]:
    raw = entry["fields"].get("year", "")
    m = re.search(r"\d{4}", raw)
    return int(m.group(0)) if m else None


def bib_author_count(entry: dict) -> int:
    authors = entry["fields"].get("author", "")
    if not authors:
        return 0
    return len([p for p in re.split(r"\s+and\s+", authors) if p.strip()])


def safe_id(value: str) -> str:
    return value.replace("/", "_").replace(":", "_")


def read_json_fixture(metadata_dir: Optional[Path], source: str, identifier: str) -> Optional[dict]:
    if metadata_dir is None:
        return None
    path = metadata_dir / source / (safe_id(identifier) + ".json")
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def read_text_fixture(metadata_dir: Optional[Path], source: str, identifier: str, suffix: str) -> Optional[str]:
    if metadata_dir is None:
        return None
    path = metadata_dir / source / (safe_id(identifier) + suffix)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def fetch_json(url: str) -> Optional[dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "academic-writing-toolkit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 400:
                return None
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def fetch_text(url: str) -> Optional[str]:
    request = urllib.request.Request(url, headers={"User-Agent": "academic-writing-toolkit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            if response.status >= 400:
                return None
            return response.read().decode("utf-8")
    except Exception:
        return None


def crossref_metadata(entry: dict, metadata_dir: Optional[Path]) -> Optional[dict]:
    doi = entry["fields"].get("doi")
    if not doi:
        return None
    fixture = read_json_fixture(metadata_dir, "crossref", doi)
    if fixture is not None:
        return fixture
    url = CROSSREF_BASE + urllib.parse.quote(doi, safe="")
    return fetch_json(url)


def semantic_scholar_metadata(entry: dict, metadata_dir: Optional[Path]) -> Optional[dict]:
    identifier = entry["fields"].get("doi") or entry["fields"].get("arxiv_id") or entry["fields"].get("eprint")
    if not identifier:
        return None
    fixture = read_json_fixture(metadata_dir, "semantic-scholar", identifier)
    if fixture is not None:
        return fixture
    if entry["fields"].get("doi"):
        paper_id = "DOI:" + identifier
    else:
        paper_id = "ARXIV:" + identifier
    url = SEMANTIC_SCHOLAR_BASE + urllib.parse.quote(paper_id, safe=":") + "?fields=title,authors,year,venue"
    return fetch_json(url)


def arxiv_metadata(entry: dict, metadata_dir: Optional[Path]) -> Optional[str]:
    arxiv_id = entry["fields"].get("arxiv_id") or entry["fields"].get("eprint")
    if not arxiv_id:
        return None
    fixture = read_text_fixture(metadata_dir, "arxiv", arxiv_id, ".xml")
    if fixture is not None:
        return fixture
    url = ARXIV_BASE + "?id_list=" + urllib.parse.quote(arxiv_id)
    return fetch_text(url)


def year_from_crossref(message: dict) -> Optional[int]:
    for key in ("published-print", "published-online", "published", "issued"):
        parts = message.get(key, {}).get("date-parts")
        if parts and parts[0]:
            return int(parts[0][0])
    return None


def compare_metadata(entry: dict, source: str, title: str, year: Optional[int], author_count: int) -> Tuple[List[dict], Optional[dict]]:
    issues: List[dict] = []
    key = entry["key"]
    bib_title = entry["fields"].get("title", "")
    sim = jaccard_similarity(bib_title, title)
    if sim < 0.60:
        issues.append({
            "kind": "metadata-title-low-similarity",
            "severity": "high",
            "entry": key,
            "source": source,
            "message": "Title similarity to {} metadata is below 60%.".format(source),
        })
    elif sim < 0.90:
        issues.append({
            "kind": "metadata-title-minor-diff",
            "severity": "medium",
            "entry": key,
            "source": source,
            "message": "Title similarity to {} metadata is below 90%.".format(source),
        })
    byear = bib_year(entry)
    if byear is not None and year is not None:
        diff = abs(byear - year)
        if diff > 2:
            issues.append({
                "kind": "metadata-year-mismatch",
                "severity": "high",
                "entry": key,
                "source": source,
                "message": "Year differs from {} metadata by more than two years.".format(source),
            })
        elif diff > 0:
            issues.append({
                "kind": "metadata-year-mismatch",
                "severity": "medium",
                "entry": key,
                "source": source,
                "message": "Year differs from {} metadata.".format(source),
            })
    bcount = bib_author_count(entry)
    if bcount and author_count:
        ratio = abs(bcount - author_count) / float(max(bcount, author_count))
        if ratio > 0.50:
            issues.append({
                "kind": "metadata-author-count-mismatch",
                "severity": "high",
                "entry": key,
                "source": source,
                "message": "Author count differs from {} metadata by more than 50%.".format(source),
            })
        elif ratio > 0.20:
            issues.append({
                "kind": "metadata-author-count-mismatch",
                "severity": "medium",
                "entry": key,
                "source": source,
                "message": "Author count differs from {} metadata.".format(source),
            })
    if issues:
        return issues, None
    return issues, {"entry": key, "source": source, "title_similarity": sim}


def parse_crossref_result(payload: dict) -> Tuple[str, Optional[int], int]:
    message = payload.get("message", payload)
    title = (message.get("title") or [""])[0]
    year = year_from_crossref(message)
    author_count = len(message.get("author") or [])
    return title, year, author_count


def parse_semantic_scholar_result(payload: dict) -> Tuple[str, Optional[int], int]:
    title = payload.get("title", "")
    year = payload.get("year")
    author_count = len(payload.get("authors") or [])
    return title, int(year) if year else None, author_count


def parse_arxiv_result(xml_text: str) -> Optional[Tuple[str, Optional[int], int]]:
    root = ET.fromstring(xml_text)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entry = root.find("atom:entry", ns)
    if entry is None:
        return None
    title_el = entry.find("atom:title", ns)
    published_el = entry.find("atom:published", ns)
    authors = entry.findall("atom:author", ns)
    title = " ".join((title_el.text or "").split()) if title_el is not None else ""
    year = None
    if published_el is not None and published_el.text:
        m = re.search(r"\d{4}", published_el.text)
        year = int(m.group(0)) if m else None
    return title, year, len(authors)


def verify_online(entries: List[dict], metadata_dir: Optional[Path]) -> Tuple[List[dict], List[dict], List[dict]]:
    issues: List[dict] = []
    verified: List[dict] = []
    checks: List[dict] = []
    for entry in entries:
        key = entry["key"]
        checked = False
        crossref = crossref_metadata(entry, metadata_dir)
        if crossref is not None:
            checked = True
            title, year, author_count = parse_crossref_result(crossref)
            new_issues, ok = compare_metadata(entry, "crossref", title, year, author_count)
            issues.extend(new_issues)
            checks.append({"entry": key, "source": "crossref", "status": "checked"})
            if ok:
                verified.append(ok)
        elif entry["fields"].get("doi"):
            issues.append({"kind": "doi-not-found", "severity": "high", "entry": key, "source": "crossref", "message": "DOI was not found in Crossref metadata."})

        semantic = semantic_scholar_metadata(entry, metadata_dir)
        if semantic is not None:
            checked = True
            title, year, author_count = parse_semantic_scholar_result(semantic)
            new_issues, ok = compare_metadata(entry, "semantic-scholar", title, year, author_count)
            issues.extend(new_issues)
            checks.append({"entry": key, "source": "semantic-scholar", "status": "checked"})
            if ok:
                verified.append(ok)

        arxiv_xml = arxiv_metadata(entry, metadata_dir)
        if arxiv_xml is not None:
            checked = True
            parsed = parse_arxiv_result(arxiv_xml)
            checks.append({"entry": key, "source": "arxiv", "status": "checked"})
            if parsed is None:
                issues.append({"kind": "arxiv-not-found", "severity": "high", "entry": key, "source": "arxiv", "message": "arXiv metadata did not contain an entry."})
            else:
                title, year, author_count = parsed
                new_issues, ok = compare_metadata(entry, "arxiv", title, year, author_count)
                issues.extend(new_issues)
                if ok:
                    verified.append(ok)
        elif entry["fields"].get("arxiv_id") or entry["fields"].get("eprint"):
            issues.append({"kind": "arxiv-not-found", "severity": "high", "entry": key, "source": "arxiv", "message": "arXiv identifier was not found."})

        if not checked:
            checks.append({"entry": key, "source": "none", "status": "skipped"})
    return issues, verified, checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify academic references from BibTeX.")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--bib", dest="bib_path")
    parser.add_argument("--json", action="store_true", dest="emit_json")
    parser.add_argument("--online", action="store_true", help="Verify records against external metadata sources.")
    parser.add_argument("--metadata-dir", help="Read metadata fixtures from DIR instead of live APIs when present.")
    args = parser.parse_args()
    target = Path(args.bib_path or args.path or "")
    if not target.is_file():
        sys.stderr.write("error: input file not found\n")
        return 2
    text = extract_bibtex(target.read_text(encoding="utf-8"))
    entries = parse_bibtex(text)
    issues = audit_entries(entries)
    verified: List[dict] = []
    metadata_checks: List[dict] = []
    if args.online:
        metadata_dir = Path(args.metadata_dir) if args.metadata_dir else None
        online_issues, verified, metadata_checks = verify_online(entries, metadata_dir)
        issues.extend(online_issues)
    payload = {
        "schema_version": 1,
        "entries": len(entries),
        "issues": issues,
        "issue_count": len(issues),
        "verified": verified,
        "metadata_checks": metadata_checks,
        "online_sources": sorted(set(c["source"] for c in metadata_checks if c["source"] != "none")),
    }
    if args.emit_json:
        print(json.dumps(payload, indent=2))
    else:
        print("entries: {}".format(len(entries)))
        for issue in issues:
            print("{entry}: {kind}: {message}".format(**issue))
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
