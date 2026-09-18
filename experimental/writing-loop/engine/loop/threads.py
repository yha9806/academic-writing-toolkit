"""Attach the author's messages to sentences, and pair each message with the replies that followed it.

A message is attached only by evidence a reader can check on the spot:
  - "句子编号": it names a positional label (A06, I4.4) that exists in the draft version current at that time;
  - "引号原文": a quoted or `> `-quoted fragment of it occurs verbatim in a sentence (or contains a whole sentence).
Everything else stays in 未挂到句子. No similarity guessing here.
"""
import re

from .text import norm, split_sentences

LABEL = re.compile(r"(?<![A-Za-z0-9.])(T\d{2}|A\d{2}|I\d{1,2}\.\d{1,2})(?![0-9.]?\d)")
_QUOTED = re.compile(r"“([^”]{8,})”|\"([^\"]{8,})\"|「([^」]{8,})」|『([^』]{8,})』")
MIN_QUOTE = 12


def version_at(versions, t):
    cur = None
    for v in versions:
        if v["time"] <= t:
            cur = v
        else:
            break
    return cur


def quoted_fragments(text):
    out = []
    for m in _QUOTED.finditer(text):
        out.append(next(g for g in m.groups() if g))
    block = [ln[2:] for ln in text.splitlines() if ln.startswith("> ")]
    if block:
        out.extend(split_sentences(" ".join(block)))
    return [q for q in (norm(x) for x in out) if len(q) >= MIN_QUOTE]


def attach(message, versions):
    v = version_at(versions, message["t"])
    if v is None:
        return None, []
    hits, seen = [], set()
    by_label = {s["label"]: s for s in v["sentences"]}
    for m in LABEL.finditer(message["text"]):
        s = by_label.get(m.group(1))
        if s and s["sid"] not in seen:
            seen.add(s["sid"])
            hits.append({"sid": s["sid"], "label": s["label"], "method": "句子编号", "evidence": m.group(1)})
    frags = quoted_fragments(message["text"])
    for s in v["sentences"]:
        sn = norm(s["text"])
        for q in frags:
            if q in sn or (len(sn) >= 20 and sn in q):
                if s["sid"] not in seen:
                    seen.add(s["sid"])
                    hits.append({"sid": s["sid"], "label": s["label"], "method": "引号原文", "evidence": q[:120]})
                break
    return v["sha"], hits


def build(conv, versions):
    """threads = one per author message: its words, the draft version it was read against, attachments, reply ids."""
    humans, assistants = conv["human"], conv["assistant"]
    out = []
    for k, h in enumerate(humans):
        nxt = humans[k + 1]["t"] if k + 1 < len(humans) else float("inf")
        replies = [a["aid"] for a in assistants if h["t"] <= a["t"] < nxt and a["session"] in h["sessions"]]
        sha, hits = attach(h, versions)
        out.append({"mid": h["mid"], "ts": h["ts"], "channel": h["channel"], "text": h["text"], "sessions": h["sessions"],
                    "draft_version": sha, "attached": hits, "replies": replies})
    return out
