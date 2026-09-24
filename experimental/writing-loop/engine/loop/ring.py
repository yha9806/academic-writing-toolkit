"""The manuscript ring: one revision round as seven stages, what hangs on each, and which the engine only infers.

The conversation-layer spec (W1-W4), plus a design stage the author approved: the loop had no "design before
writing" step. The engine has no notion of a revision round,
only of a turn, so a round is read off the register: it starts at the last review gate the author decided (the
register keeps dates, not times, and the ring says so). Nothing here is guessed where the engine cannot see:

  - 你的意见, 改稿, 检查, 读者组 are seen (the author's comments, change sets, the coverage summary, reader results);
  - 设计 and 你核对 are inferred (the intent card is never read; a review is only known by the decision it closed);
  - 落稿 is only a commit (只有提交): whether it followed the review cannot be told.

Open register items hang on the stage their gate names (the first part of 由哪个门决定, by word); a gate id or a
gate no word matches is listed apart. Each hung item says whether it is the author's to decide (a register item) or only
out of date (a check, the reader panel). Checks that are not current hang on 检查; a reader panel older than the last
rewrite hangs on 读者组. This module only reads a summary and two times; the caller supplies both.
"""
import datetime as dt

from . import coverage as V

SEEN = "看得见"
INFERRED = "推出来"
# 「只有提交」：刘海上一格 56pt 宽，六个字放不下又不许缩字（HIG 最小 10pt；09-24 grill 实拍被截成「只看得到…」）。
COMMITS_ONLY = "只有提交"

STAGES = [("comment", "你的意见", SEEN), ("design", "设计", INFERRED), ("rewrite", "改稿", SEEN), ("check", "检查", SEEN),
          ("readers", "读者组", SEEN), ("review", "你核对", INFERRED), ("land", "落稿", COMMITS_ONLY)]

# The first part of a gate, by word. Order matters: 「改稿核对页」 names the review, not the rewrite.
GATE_WORDS = [("design", ("意图卡", "设计")), ("readers", ("读者组",)), ("review", ("核对", "核完")), ("rewrite", ("改稿",))]
NOT_CURRENT = (V.STALE, V.FAILED, V.NEVER, V.MISSING)


def stage_of(gate):
    """The stage a gate names, or None (a gate id such as G2, or words no rule knows)."""
    first = (gate or "").replace(";", "；").split("；")[0]
    for key, words in GATE_WORDS:
        if any(w in first for w in words):
            return key
    return None


def _utc(t):
    """An ISO time as an aware UTC datetime, or None. Times come as …Z (the hooks) and …+01:00 (git): compared as
    strings they order wrongly across offsets."""
    if not t:
        return None
    try:
        d = dt.datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    except ValueError:
        return None
    return (d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)


def _before(a, b):
    ua, ub = _utc(a), _utc(b)
    return bool(ua and ub and ua < ub)


def _after(t, since):
    """Whether an ISO time falls in the round: on or after its start date (dates only in the register, which are the
    author's local dates, so the time's own date is compared)."""
    return bool(_utc(t)) and (since is None or str(t)[:10] >= since)


def ring(summary, *, last_comment_at=None, last_change_at=None, name=None):
    risks = (summary or {}).get("risks") or {}
    open_, decided = risks.get("open") or [], risks.get("decided") or []
    reviews = [d.get("decided_on") for d in decided if stage_of(d.get("gate")) == "review" and d.get("decided_on")]
    since = max(reviews) if reviews else None

    items = {k: [] for k, _, _ in STAGES}
    unhung = []
    for x in open_:
        entry = {"id": x.get("id"), "text": f"{x.get('kind', '')} {x.get('id')} {x.get('title', '')}".strip(),
                 "detail": x.get("detail") or "", "you": True}
        if x.get("moved"):
            entry["moved"] = x["moved"]
        key = stage_of(x.get("gate"))
        (items[key] if key else unhung).append(entry)
    rows = (summary or {}).get("rows") or []
    for r in rows:
        if r.get("id") == "readers":
            continue
        if r.get("status") in NOT_CURRENT:
            items["check"].append({"id": r.get("id"), "text": f"{r.get('name', r.get('id'))} {r.get('status')}", "detail": r.get("detail") or "",
                                   "you": False})
    readers = next((r for r in rows if r.get("id") == "readers"), None)
    if readers is not None:
        at = readers.get("last_at")
        if readers.get("status") in NOT_CURRENT or _before(at, last_change_at):
            items["readers"].append({"id": "readers", "text": "读者组 · 过期：稿子改过了，要重读" if at else "读者组 · 还没跑",
                                     "detail": readers.get("detail") or "", "you": False})

    happened = {
        "comment": _after(last_comment_at, since),
        "design": None,
        "rewrite": _after(last_change_at, since),
        "check": _after(last_change_at, since) and not items["check"],
        "readers": bool(readers and _after(readers.get("last_at"), since) and not _before(readers.get("last_at"), last_change_at)),
        "review": False,
        "land": None,
    }
    segments = []
    for key, label, seen in STAGES:
        if items[key]:
            state = "hanging"
        elif happened[key] is None:
            state = "unseen"
        else:
            state = "done" if happened[key] else "open"
        segments.append({"key": key, "name": label, "seen": seen, "state": state, "items": items[key]})
    current = next((s["key"] for s in segments if s["state"] == "hanging"), None) \
        or next((s["key"] for s in segments if s["state"] == "open"), None)

    # Where the round last moved, beside where it waits (a real manuscript waited at 设计 while the day's work was rewriting).
    check_at = max((r.get("last_at") for r in rows if r.get("id") != "readers" and _utc(r.get("last_at"))), key=_utc, default=None)
    moves = [(k, t) for k, t in (("comment", last_comment_at), ("rewrite", last_change_at), ("check", check_at),
                                 ("readers", readers.get("last_at") if readers else None)) if _utc(t)]
    last = max(moves, key=lambda kt: _utc(kt[1])) if moves else None
    latest, latest_at = (last[0], last[1]) if last else (None, None)
    # How far the round got: the furthest stage that moved within it. Neither `current` (the first stage something
    # waits on) nor `latest` (a comment restarts it) says this; the author asked 09-24 why a draft ready to upload
    # still read 设计. A stage reached and then left behind by a later rewrite still counts: the round did get there.
    order = [k for k, _, _ in STAGES]
    within = [k for k, t in moves if _after(t, since)]
    reached = max(within, key=order.index) if within else None

    # Gates one message closed are said once: 「W1、W2、W3、W4（288498c5）」, not the same uuid four times (a real
    # register closed four in one message, and the panel line ran out of width).
    by_date = {}
    for d in decided:
        if d.get("decided_on"):
            by_date.setdefault(d["decided_on"], {}).setdefault((d.get("uuid") or "")[:8], []).append(str(d.get("id")))
    closed = [{"date": k, "items": [f"{'、'.join(ids)}（{u}）" if u else "、".join(ids) for u, ids in v.items()]}
              for k, v in sorted(by_date.items(), reverse=True)]
    return {"title": name, "since": since,
            "sinceNote": f"这一轮从 {since} 算起（台账只记日期，精确到日）" if since else "还没有核对页关过门：从头算起",
            "current": current, "latest": latest, "latest_at": latest_at, "reached": reached, "segments": segments, "unhung": unhung,
            "waiting": len(open_), "closed": closed}
