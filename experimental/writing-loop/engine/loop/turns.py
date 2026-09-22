"""这一轮在做什么（设计 lintel `docs/design/2026-09-22-awt-live.md` §3.5，B1 ②）。只读写作循环自己的记录，不借许愿柳。

- **开工**：钩子在登记会话里把每条作者消息写进 `human/comments.jsonl`。这里只取时刻、会话、消息 id 和字数，不取原话。
- **碰稿与一轮结束**：钩子在改正文 / 台账、跑 git、Stop 时起 `loop update`。update 一进门就把原因追加进
  `cache/turns.jsonl`（`record`），重建后稿件的 HEAD 变了再追加一条 `head:<提交号>`。只有时刻与原因，没有内容。
- **算什么是「碰了稿子」**：改正文、改台账、稿件 HEAD 变了（= 往稿件仓提交）。钩子的 `git` 原因不算：它对任何仓的 git 命令都触发，
  登记会话里不少 git 命令是在别的仓跑的。跑检查、派读者没有碰稿时的信号：读者组的结果是全部回来后一次存盘的，
  所以只在落地时认得出（`readers_landed`）。

一轮 = 最近一条作者消息到它之后的 `stop`。钩子在改句门拦下 Stop 时记 `stop:blocked`（不算结束），API 报错结束一轮时
（StopFailure）记 `stop:error`（算结束，但不弹落地）。stop 之后又有碰稿，仍当作那次 Stop 没放行（别的 Stop 钩子拦的），
这一轮还没完，等下一次 stop。

记录按时刻排序后再读：`head:` 行记的是提交自己的时刻，写进文件时往往已经在 stop 之后（grill 09-22 #1）。
"""
import json
import os
import re
import time
from pathlib import Path

FILE = "turns.jsonl"
KEEP = 2000                 # 行数上限：超过就只留最近这些行
STUCK = 3600.0              # 一小时没动静不算在跑（许愿柳 stuckAfter）
PREVIOUS_STOP = 2.0         # 消息时刻只到秒：消息那一秒之后 2 秒内的 stop 属于上一轮
TAIL = 262144               # comments.jsonl 只读尾部这么多字节

ACTION = {"draft": "改正文", "ledger": "改台账", "head": "提交"}
ENDS = {"stop": False, "stop:error": True}   # reason -> the turn ended on an API error


def _path(ws):
    return Path(ws) / "cache" / FILE


def record(ws, reason, now=None):
    """Append one line. Never raises: a notch signal that failed to record must not fail the update that carries it."""
    now = time.time() if now is None else now
    p = _path(ws)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"t": round(now, 3), "reason": str(reason)[:300]}, ensure_ascii=False) + "\n")
        if p.stat().st_size > KEEP * 200:
            lines = p.read_text(encoding="utf-8").splitlines()[-KEEP:]
            tmp = p.with_name(f".{FILE}.{os.getpid()}.tmp")
            tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
            tmp.replace(p)
    except OSError:
        pass


def read(ws):
    try:
        text = _path(ws).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if isinstance(r, dict) and isinstance(r.get("t"), (int, float)) and isinstance(r.get("reason"), str):
            out.append(r)
    return out


def _epoch(iso):
    """'2026-01-02T03:04:05Z' or with an offset -> seconds; None if unreadable."""
    if not isinstance(iso, str):
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def last_prompt(ws):
    """The author's latest message in a registered session: time, session, id, length. The text itself is not returned."""
    p = Path(ws) / "human" / "comments.jsonl"
    try:
        with open(p, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - TAIL))
            tail = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return None
    for line in reversed(tail.splitlines()):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        t = _epoch(r.get("at")) if isinstance(r, dict) else None
        if t is None:
            continue
        prompt = r.get("prompt")
        return {"t": t, "session": r.get("session_id"), "id": r.get("prompt_id") or f"t{int(t)}",
                "chars": len(prompt) if isinstance(prompt, str) else 0}
    return None


def _is_draft(rel, glob):
    import fnmatch
    return rel in glob if isinstance(glob, list) else fnmatch.fnmatch(rel, glob)


def kind(reason, cfg):
    """What a recorded reason says about the manuscript: draft / ledger / head, or None (not a touch)."""
    if reason.startswith("head:"):
        return "head"
    if reason.startswith("write:"):
        rel = reason[len("write:"):]
        return "draft" if _is_draft(rel, cfg["draft"]["glob"]) else "ledger"
    return None


def current(ws, cfg, now=None):
    """The latest turn, or None when the author has not written in a registered session yet."""
    p = last_prompt(ws)
    if p is None:
        return None
    touches, ended, error = [], None, False
    for r in sorted(read(ws), key=lambda r: r["t"]):
        if r["t"] < p["t"]:
            continue
        if r["reason"] in ENDS:
            if r["t"] >= p["t"] + PREVIOUS_STOP:
                ended, error = r["t"], ENDS[r["reason"]]
            continue
        k = kind(r["reason"], cfg)
        if k:
            touches.append((r["t"], k))
            ended, error = None, False   # a touch after a stop: that Stop was not let through, the turn goes on
    return {"start": p["t"], "session": p["session"], "key": p["id"], "chars": p["chars"],
            "touches": touches, "ended": ended, "error": error}


def running(turn, now):
    """B1 ②: this turn touched the manuscript, has not ended, and something happened in the last hour."""
    return bool(turn and turn["touches"] and turn["ended"] is None and now - turn["touches"][-1][0] < STUCK)


def action(turn):
    return ACTION[turn["touches"][-1][1]] if turn and turn["touches"] else None


RECALL = re.compile(r"(M\d+)\.recall (\d+)/(\d+)")


def weakest_reader(summary):
    """The weakest free-recall item in a readers run summary ('M2.recall 4/9' -> ('M2', 4, 9)), or None."""
    hits = [(m, int(k), int(n)) for m, k, n in RECALL.findall(summary or "") if int(n) > 0]
    return min(hits, key=lambda h: h[1] / h[2]) if hits else None


def readers_run(ws):
    """The latest readers run record (cache/coverage/runs/readers.json): its time and summary, or None."""
    try:
        r = json.loads((Path(ws) / "cache" / "coverage" / "runs" / "readers.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    t = _epoch(r.get("at")) if isinstance(r, dict) else None
    return {"t": t, "summary": r.get("summary") or "", "verdict": r.get("verdict")} if t is not None else None
