#!/usr/bin/env python3
"""Check every reader's output against the packet it read. A reader whose output is incomplete did not read.

    python3 check-reader-output.py --packet <dir>/packet.json <reader output .json> [...]
    python3 check-reader-output.py --packet <dir>/packet.json --outputs <dir of .json>

A qualified output is one JSON object with: one entry per paragraph of the packet (p, believe, expect, reread,
guessed); remember (a non-empty list); why_accept, closest_prior_work, reuse, writing_got_in_way; an answer to every
directed question in the packet; and outside_knowledge, the reader's own report of what it knew beyond the text.
The reader is a sub-agent told to forget, not a reader who never knew, so a missing self-report disqualifies.

Prints one line per file, then "qualified N of M". --json prints the same as an object.
Exit: 0 every output qualified; 1 some did not; 2 none did, or there was nothing to check.
"""
import argparse
import json
import sys
from pathlib import Path

PARA_KEYS = ("believe", "expect", "reread", "guessed")
TOP_TEXT = ("why_accept", "closest_prior_work", "reuse", "writing_got_in_way", "outside_knowledge")


def die(msg):
    sys.stderr.write(f"check-reader-output: {msg}\n")
    sys.exit(2)


def parse(text):
    """The JSON object in a reader's reply; a reply wrapped in a code fence is accepted, prose around it is not."""
    t = text.strip()
    if t.startswith("```"):
        t = t.strip("`")
        t = t[t.find("{"):] if "{" in t else t
    return json.loads(t)


def problems(data, packet):
    out = []
    if not isinstance(data, dict):
        return ["not a JSON object"]
    paras = data.get("paragraphs")
    want = [p["p"] for p in packet["paragraphs"]]
    if not isinstance(paras, list):
        out.append("paragraphs missing")
    else:
        seen = {}
        for e in paras:
            if isinstance(e, dict) and isinstance(e.get("p"), int):
                seen[e["p"]] = e
        missing = [p for p in want if p not in seen]
        if missing:
            out.append(f"paragraphs {missing[:6]} missing")
        for p, e in seen.items():
            bad = [k for k in PARA_KEYS if k not in e]
            if bad:
                out.append(f"P{p} lacks {', '.join(bad)}")
            for k in ("reread", "guessed"):
                if k in e and not isinstance(e[k], list):
                    out.append(f"P{p} {k} is not a list")
    rem = data.get("remember")
    if not isinstance(rem, list) or not [x for x in rem if isinstance(x, str) and x.strip()]:
        out.append("remember missing or empty")
    for k in TOP_TEXT:
        if not isinstance(data.get(k), str) or not data[k].strip():
            out.append(f"{k} missing")
    for q in packet.get("questions") or []:
        if not isinstance(data.get(q["id"]), str) or not data[q["id"]].strip():
            out.append(f"directed question {q['id']} unanswered")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--outputs", help="a directory of reader outputs (*.json)")
    ap.add_argument("files", nargs="*")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        sys.exit(2 if e.code else 0)
    try:
        packet = json.loads(Path(a.packet).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"packet unreadable: {e}")
    if not packet.get("paragraphs"):
        die("the packet has no paragraphs")
    files = [Path(f) for f in a.files]
    if a.outputs:
        files += sorted(Path(a.outputs).glob("*.json"))
    if not files:
        die("no reader output to check: nothing examined is not a pass")
    rows = []
    for f in files:
        try:
            data = parse(f.read_text(encoding="utf-8"))
            why = problems(data, packet)
        except (OSError, ValueError) as e:
            why = [f"unreadable: {e}"]
        rows.append({"file": f.name, "qualified": not why, "problems": why})
    ok = sum(r["qualified"] for r in rows)
    if a.json:
        print(json.dumps({"qualified": ok, "checked": len(rows), "outputs": rows}, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"{'ok ' if r['qualified'] else 'NO '} {r['file']}" + ("" if r["qualified"] else ": " + "; ".join(r["problems"])))
        print(f"qualified {ok} of {len(rows)}")
    if ok == 0:
        return 2
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
