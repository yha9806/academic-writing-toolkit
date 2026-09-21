#!/usr/bin/env python3
"""Build a baseline corpus of papers published in a target venue.

The prose fingerprint compares a manuscript against a corpus. Until now that
corpus was always an input someone had assembled by hand, and nothing checked
what it represented. On one project the directory was named for the target
journal, held the manuscript's own bibliography, and contained no article that
journal had ever published -- so "inside the published range" meant "inside the
range of the papers we cite" for seven rounds without anyone saying so.

This builds the other corpus: papers the venue actually published. It is a
different question from the bibliography baseline, not a better answer to the
same one, and the two are never merged.

Membership is verified against the registrar, never the author. arXiv's
journal_ref is free text -- one real record reads "Just accpeted by ACM
Computing Surveys 2026", typo included -- so a record is admitted only when it
carries a DOI whose registered container-title equals the venue. That is the
same DOI content negotiation the writing rules already require for
bibliography entries.

Every candidate leaves a trace. The manifest's dispositions sum to the number
of candidates, and a run that cannot reach the corpus floor fails with a named
code rather than returning a short corpus that reads like a complete one.

Python 3.8 stdlib only. Network: export.arxiv.org, doi.org, arxiv.org.
"""

import argparse
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
API = "http://export.arxiv.org/api/query"
# arxiv.org answers 406 to a VERSIONED pdf path from a non-browser client --
# /pdf/2407.17215v1 is refused while /pdf/2407.17215 is served. Dropping the
# version would fix the fetch and lose the record of which version was
# measured. export.arxiv.org is the host arXiv designates for automated
# access, and it serves the versioned path. Measured 2026-09-20: 24 of 75
# downloads failed this way against the main site and none against export.
PDF_HOST = "https://export.arxiv.org/pdf/"
DOWNLOAD_ATTEMPTS = 3
UA = "awt-venue-baseline/0.1 (academic prose baseline construction)"
PAGE = 100
# The prose method refuses to report percentiles against fewer than twenty
# published papers. A corpus under that is not a small corpus, it is not a
# corpus, and returning it quietly is how a short baseline gets quoted.
CORPUS_FLOOR = 20


def die(code: str, message: str, remedy: str = "") -> None:
    sys.stderr.write("%s: %s\n" % (code, message))
    if remedy:
        sys.stderr.write("  remedy: %s\n" % remedy)
    sys.exit(2)


def norm(s: Optional[str]) -> str:
    return " ".join((s or "").split()).strip()


def fetch(url: str, accept: Optional[str] = None, timeout: int = 90) -> bytes:
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=headers), timeout=timeout).read()


def query_arxiv(venue: str, delay: float) -> List[Dict]:
    """Every arXiv record whose journal_ref names the venue. Author-supplied."""
    out, start = [], 0
    while True:
        url = API + "?" + urllib.parse.urlencode(
            {"search_query": 'jr:"%s"' % venue, "start": start,
             "max_results": PAGE, "sortBy": "submittedDate",
             "sortOrder": "descending"})
        try:
            root = ET.fromstring(fetch(url))
        except (urllib.error.URLError, ET.ParseError) as exc:
            die("VENUE_ARXIV_UNREACHABLE",
                "the arXiv API did not answer: %s" % exc,
                "check the network and re-run; nothing has been written")
        entries = root.findall(ATOM + "entry")
        for e in entries:
            doi = e.findtext(ARXIV + "doi")
            pub = e.findtext(ATOM + "published") or ""
            out.append({
                "arxiv_id": (e.findtext(ATOM + "id") or "").rsplit("/", 1)[-1],
                "title": norm(e.findtext(ATOM + "title")),
                "year": int(pub[:4]) if pub[:4].isdigit() else None,
                "published": pub or None,
                "primary_category": (e.find(ARXIV + "primary_category").get("term")
                                     if e.find(ARXIV + "primary_category") is not None else None),
                "journal_ref": norm(e.findtext(ARXIV + "journal_ref")),
                "doi": norm(doi) if doi else None,
            })
        if len(entries) < PAGE:
            return out
        start += PAGE
        time.sleep(delay)


def venue_phrasings(venue: str) -> List[str]:
    """The venue as given, then with every free-standing "&" and "and" swapped.

    journal_ref is typed by authors, and they spell a journal whose name holds
    an ampersand both ways. The phrase search matches only the spelling it is
    given, so one query returns part of the frame. "&" inside a word ("R&D") is
    not a conjunction and is left alone.
    """
    out = [venue]
    for alt in (re.sub(r"(?<=\s)&(?=\s)", "and", venue),
                re.sub(r"(?<=\s)and(?=\s)", "&", venue, flags=re.IGNORECASE)):
        if alt not in out:
            out.append(alt)
    return out


def container_title(doi: str, delay: float) -> Optional[str]:
    """What the registrar says the DOI was published in, not what the author typed."""
    try:
        d = json.loads(fetch("https://doi.org/" + urllib.parse.quote(doi),
                             accept="application/vnd.citationstyles.csl+json",
                             timeout=45).decode("utf-8", "replace"))
    except Exception:
        return None
    finally:
        time.sleep(delay)
    ct = d.get("container-title")
    if isinstance(ct, list):
        ct = ct[0] if ct else None
    # The registrar can send the title HTML-escaped: a journal named "X & Y"
    # arrives as "X &amp; Y", and compared verbatim it is some other journal.
    return norm(html.unescape(ct)) if ct else None


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Build a prose baseline from papers a venue published.")
    ap.add_argument("--venue", required=True,
                    help='journal name, matched against the registrar\'s '
                         'container-title (e.g. "ACM Computing Surveys")')
    ap.add_argument("--from-year", type=int, default=2021,
                    help="earliest arXiv submission year to admit (default 2021). "
                         "House genre drifts; the window is part of the frame")
    ap.add_argument("--out", help="directory the PDFs are written to")
    ap.add_argument("--manifest", required=True,
                    help="where the record of the sampling frame is written")
    ap.add_argument("--max", type=int, default=200, help="cap on admitted records")
    ap.add_argument("--allow-unverified", action="store_true",
                    help="admit records whose DOI does not resolve. They are "
                         "recorded as unverified and the manifest says so")
    ap.add_argument("--dry-run", action="store_true",
                    help="build the manifest and download nothing")
    ap.add_argument("--delay", type=float, default=3.0,
                    help="seconds between network calls (default 3.0)")
    args = ap.parse_args()

    if not args.dry_run and not args.out:
        die("VENUE_NO_OUTPUT_DIR", "--out is required unless --dry-run is passed",
            "name a directory for the PDFs, outside the repository")

    venue_key = args.venue.lower()
    phrasings = venue_phrasings(args.venue)
    candidates: List[Dict] = []
    seen = set()
    for i, phrase in enumerate(phrasings):
        if i:
            time.sleep(args.delay)
        for c in query_arxiv(phrase, args.delay):
            # A journal_ref found under both spellings is one candidate.
            if c["arxiv_id"] not in seen:
                seen.add(c["arxiv_id"])
                candidates.append(c)
    # Each query comes back newest first. Merged, keep that order, so --max
    # still cuts the oldest rather than whichever spelling was queried second.
    candidates.sort(key=lambda c: c.get("published") or "", reverse=True)
    if not candidates:
        die("VENUE_NO_CANDIDATES",
            "no arXiv record carries a journal_ref naming %s"
            % " or ".join('"%s"' % p for p in phrasings),
            "check the venue string; the API matches it as a phrase")

    admitted: List[Dict] = []
    rejected: Dict[str, List[Dict]] = {
        "out_of_window": [], "no_doi": [], "doi_unresolvable": [],
        "container_title_mismatch": [], "over_max": [], "download_failed": []}

    for c in candidates:
        if c["year"] is None or c["year"] < args.from_year:
            rejected["out_of_window"].append(c); continue
        if not c["doi"]:
            # journal_ref alone is the author's own claim of where it appeared.
            rejected["no_doi"].append(c); continue
        ct = container_title(c["doi"], args.delay)
        if ct is None:
            if args.allow_unverified:
                c["container_title"] = None
                c["venue_verified"] = False
                admitted.append(c)
            else:
                rejected["doi_unresolvable"].append(c)
            continue
        c["container_title"] = ct
        if ct.lower() != venue_key:
            rejected["container_title_mismatch"].append(c); continue
        c["venue_verified"] = True
        admitted.append(c)

    if len(admitted) > args.max:
        rejected["over_max"] = admitted[args.max:]
        admitted = admitted[: args.max]

    downloaded = 0
    if not args.dry_run:
        outdir = Path(args.out)
        outdir.mkdir(parents=True, exist_ok=True)
        kept = []
        for c in admitted:
            dest = outdir / ("%s.pdf" % c["arxiv_id"].replace("/", "_"))
            if dest.exists() and dest.stat().st_size > 0:
                c["file"] = dest.name; kept.append(c); continue
            last = None
            for attempt in range(DOWNLOAD_ATTEMPTS):
                try:
                    blob = fetch(PDF_HOST + c["arxiv_id"], accept="application/pdf",
                                 timeout=180)
                    if not blob.startswith(b"%PDF"):
                        raise ValueError("not a PDF")
                    dest.write_bytes(blob)
                    c["file"] = dest.name
                    kept.append(c); downloaded += 1
                    last = None
                    break
                except Exception as exc:
                    # A truncated read is transient and was 4 of 28 failures in
                    # one real run; retrying it is the difference between a
                    # corpus and a corpus with holes in it.
                    last = exc
                    time.sleep(args.delay * (attempt + 1))
            if last is not None:
                c["error"] = "%s (after %d attempts)" % (str(last)[:100], DOWNLOAD_ATTEMPTS)
                rejected["download_failed"].append(c)
            time.sleep(args.delay)
        admitted = kept

    manifest = {
        # 2: "query" is a list, one entry per phrasing queried (1 held a string).
        "schema_version": 2,
        "venue": args.venue,
        "retrieved": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "api": API,
        "query": ['jr:"%s"' % p for p in phrasings],
        "from_year": args.from_year,
        "verification": "arXiv journal_ref is author-supplied free text; a record "
                        "is admitted only when its DOI resolves to a registered "
                        "container-title equal to the venue",
        "stage": "authors' accepted manuscripts on arXiv, not the publisher's "
                 "copyedited pages",
        "corpus_dir": str(Path(args.out).resolve()) if args.out else None,
        "dry_run": bool(args.dry_run),
        "allow_unverified": bool(args.allow_unverified),
        "candidates": len(candidates),
        "admitted": len(admitted),
        "rejected": {k: len(v) for k, v in rejected.items()},
        "accounting_closes": len(admitted) + sum(len(v) for v in rejected.values())
                             == len(candidates),
        "downloaded_now": downloaded,
        "records": admitted,
        "rejected_records": {k: v for k, v in rejected.items() if v},
    }
    Path(args.manifest).parent.mkdir(parents=True, exist_ok=True)
    Path(args.manifest).write_text(json.dumps(manifest, indent=1), encoding="utf-8")

    sys.stderr.write(
        "venue baseline: %d candidate(s) -> %d admitted (%s)\n" % (
            len(candidates), len(admitted),
            ", ".join("%s %d" % (k, len(v)) for k, v in rejected.items() if v) or "none rejected"))
    sys.stderr.write("manifest: %s\n" % args.manifest)

    if not manifest["accounting_closes"]:
        die("VENUE_ACCOUNTING_OPEN",
            "dispositions do not sum to the candidate count; the manifest is "
            "not a complete record of the frame")
    if len(admitted) < CORPUS_FLOOR:
        die("VENUE_CORPUS_TOO_SMALL",
            "%d document(s) admitted; the prose method reports no percentile "
            "below %d" % (len(admitted), CORPUS_FLOOR),
            "widen --from-year, or accept that this venue has too little on "
            "arXiv to measure against and say so rather than measuring anyway")
    return 0


if __name__ == "__main__":
    sys.exit(main())
