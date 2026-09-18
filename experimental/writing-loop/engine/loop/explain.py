"""Explanation blocks (plan step 2.3): what Claude says it read, changed and why, next to the author's words.

In a registered manuscript session the UserPromptSubmit hook asks Claude to end manuscript replies with

    〔循环〕
    读成：<how it read the author's last message>
    改了：<sentence labels, or 无>
    依据：<what the change rests on>
    〔/循环〕

A first line of the form "我读成了：…" (the wishing-willow plugin asks for one) counts as 读成 when the block
omits it. Everything here is parsed from the transcript, so explanations.json is a projection that rebuilds
byte for byte. It carries no authority: a reading is what Claude says, shown beside the verbatim message and
never in its place (spec T14; v2 red line 7).
"""
import re

BLOCK = re.compile(r"〔循环〕[ \t]*\n(.*?)\n[ \t]*〔/循环〕", re.S)
FIELD = re.compile(r"^\s*(读成|改了|依据)\s*[：:]\s*(.*?)\s*$")
WILLOW = re.compile(r"^\s*⚠?\s*我读成了\s*[：:]\s*(.*?)\s*$", re.M)
MAX_LINES = 6
KEYS = {"读成": "reading", "改了": "changed", "依据": "basis"}


def parse(text):
    """Return {"reading", "changed", "basis", "source", "block", "over_limit"} for one turn's reply text.

    The last complete block wins; within a block the first occurrence of a field wins. An unclosed block is
    not a block. A reading taken from a "我读成了" line is marked as such, so the two sources are never mixed up."""
    out = {"reading": None, "changed": None, "basis": None, "source": None, "block": False, "over_limit": False}
    blocks = list(BLOCK.finditer(text))
    if blocks:
        out["block"] = True
        lines = [ln for ln in blocks[-1].group(1).splitlines() if ln.strip()]
        out["over_limit"] = len(lines) > MAX_LINES
        for ln in lines:
            f = FIELD.match(ln)
            if f and out[KEYS[f.group(1)]] is None and f.group(2):
                out[KEYS[f.group(1)]] = f.group(2)
        if out["reading"] is not None:
            out["source"] = "解释块"
    if out["reading"] is None:
        w = WILLOW.search(text)
        if w and w.group(1):
            out["reading"], out["source"] = w.group(1), "我读成了"
    return out


def build(conv):
    """One record per author message: the verbatim text, and what the replies up to the next author message said.

    Replies are taken from the sessions the message was seen in, in time order, joined, then parsed once, so a
    "我读成了" line at the start of the turn and a block at its end are both found."""
    humans, replies = conv["human"], conv["assistant"]
    out = []
    for i, h in enumerate(humans):
        end = humans[i + 1]["t"] if i + 1 < len(humans) else float("inf")
        turn = [a for a in replies if h["t"] < a["t"] < end and a["session"] in h["sessions"]]
        p = parse("\n\n".join(a["text"] for a in turn))
        out.append({"mid": h["mid"], "ts": h["ts"], "verbatim": h["text"], "replies": [a["aid"] for a in turn], **p})
    return out
