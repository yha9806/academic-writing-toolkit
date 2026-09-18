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
# [ \t] rather than \s at both ends: \s would swallow the line break and run past the blank line that ends a reading
WILLOW = re.compile(r"^[ \t]*⚠?[ \t]*我读成了[ \t]*[：:][ \t]*(.*?)[ \t]*$", re.M)
WILLOW_STOP = re.compile(r"^\s*(?:我补上的|标签|你批准的)\s*[：:]")
LIST_MARK = re.compile(r"^\s*(?:[-*•]|\d+[.、])\s*")
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
        w = willow_reading(text)
        if w:
            out["reading"], out["source"] = w, "我读成了"
    return out


def willow_reading(text):
    """The "我读成了" line and its continuation: a reading written as a list runs on until the next field
    ("我补上的" / "标签" / "你批准的") or a blank line. Found in use: taking only the first line lost the list."""
    m = WILLOW.search(text)
    if not m:
        return None
    parts = [m.group(1)]
    for line in text[m.end():].split("\n")[1:]:
        if not line.strip() or WILLOW_STOP.match(line):
            break
        parts.append(LIST_MARK.sub("", line).strip())
    return " ".join(x for x in parts if x) or None


def build(conv):
    """One record per author message: the verbatim text and what the replies said about it.

    Turns decide who owns what (found in use: a question typed while Claude was working took the explanation
    of the turn it interrupted). A turn starts at a message sent normally and includes messages queued during it.
      - the explanation block belongs to the message that started the turn;
      - a "我读成了" line belongs to the latest author message before the reply that carries it.
    Replies count only in the sessions the message was seen in."""
    humans, replies = conv["human"], conv["assistant"]
    turn_of, cur = {}, None
    for h in humans:
        if cur is None or h.get("channel", "prompt") != "queued":
            cur = h
        turn_of[h["mid"]] = cur["mid"]
    own = {h["mid"]: [] for h in humans}     # replies whose latest preceding author message is this one
    turn = {h["mid"]: [] for h in humans}    # replies inside the turn this message started
    for a in replies:
        before = [h for h in humans if h["t"] < a["t"] and a["session"] in h["sessions"]]
        if before:
            own[before[-1]["mid"]].append(a)
            turn[turn_of[before[-1]["mid"]]].append(a)
    out = []
    for h in humans:
        starts_turn = turn_of[h["mid"]] == h["mid"]
        block = parse("\n\n".join(a["text"] for a in turn[h["mid"]])) if starts_turn else None
        rec = {"mid": h["mid"], "ts": h["ts"], "verbatim": h["text"], "replies": [a["aid"] for a in own[h["mid"]]],
               "reading": None, "changed": None, "basis": None, "source": None, "block": False, "over_limit": False}
        if block and block["block"]:
            rec.update(changed=block["changed"], basis=block["basis"], block=True, over_limit=block["over_limit"])
            if block["source"] == "解释块":
                rec.update(reading=block["reading"], source="解释块")
        if rec["reading"] is None:
            w = willow_reading("\n\n".join(a["text"] for a in own[h["mid"]]))
            if w:
                rec.update(reading=w, source="我读成了")
        out.append(rec)
    return out
