"""Health (plan step 2.4, spec T8): is the index keeping up, and has anything gone wrong on the way?

workspace/health.json is runtime state, not a record: it carries no authority and is not part of the index.
It holds the last successful update, the last error, and recent events such as a refused write to human/.
`assess` turns it, plus a comparison with the sources, into problems that stay visible until they are fixed:
"quiet" must never look the same as "fine".

Writers are the updater and the hooks, possibly at the same moment, so every write happens under a lock.
"""
import fcntl
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path

FILE = "health.json"
MAX_EVENTS = 50


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + "Z"


@contextmanager
def _locked(ws):
    lock = Path(ws) / "cache" / "health.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load(ws):
    try:
        data = json.loads((Path(ws) / FILE).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(ws, data):
    p = Path(ws) / FILE
    tmp = p.with_name(f".{FILE}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(p)


def _update(ws, fn):
    with _locked(ws):
        data = load(ws)
        fn(data)
        data["schema"] = 1
        _save(ws, data)


def record_ok(ws, reason, took, now=None):
    now = time.time() if now is None else now

    def f(d):
        d["last_ok"] = {"at": _iso(now), "t": now, "reason": reason, "seconds": round(took, 3)}
        if d.get("last_error") and d["last_error"].get("t", 0) <= now:
            d["last_error"]["cleared_at"] = _iso(now)
    _update(ws, f)


def record_error(ws, message, now=None):
    now = time.time() if now is None else now
    _update(ws, lambda d: d.__setitem__("last_error", {"at": _iso(now), "t": now, "message": message}))


def record_event(ws, kind, detail, now=None):
    now = time.time() if now is None else now

    def f(d):
        ev = d.setdefault("events", [])
        ev.append({"at": _iso(now), "t": now, "kind": kind, "detail": detail})
        del ev[:-MAX_EVENTS]
    _update(ws, f)


def ack(ws, now=None):
    """The author has seen the events so far: hook errors and refused writes before now stop being shown.
    Nothing is deleted; events stay in health.json with their times."""
    now = time.time() if now is None else now
    _update(ws, lambda d: d.__setitem__("acked", {"at": _iso(now), "t": now}))


def _unacked(h, kind):
    since = (h.get("acked") or {}).get("t", 0)
    return [e for e in h.get("events", []) if e.get("kind") == kind and e.get("t", 0) > since]


def file_problems(ws):
    """What health.json alone says is wrong: an uncleared error, no success ever, unacknowledged hook errors.
    A refused write is not a problem (the guard worked); it is a notice, see file_notices."""
    h = load(ws)
    problems = []
    err = h.get("last_error")
    if err and not err.get("cleared_at"):
        problems.append(("更新失败", f"{err.get('at')}：{err.get('message')}"))
    if not h.get("last_ok"):
        problems.append(("从未更新", "health.json 里没有一次成功的更新"))
    bad = _unacked(h, "hook_error")
    if bad:
        problems.append(("钩子异常", f"{len(bad)} 次，最近一次：{bad[-1]['detail']}"))
    return problems


def file_notices(ws):
    """Things the author should know about that are not faults: refused writes since the last ack."""
    denied = _unacked(load(ws), "guard_denied")
    if denied:
        return [("拦下写入", f"模型试图写 human/ 共 {len(denied)} 次，最近一次 {denied[-1]['at']}：{denied[-1]['detail']}")]
    return []


def assess(cfg, check_index=True):
    """Problems a person has to see. Each is (item, message). Empty list = nothing is known to be wrong."""
    from . import gitio
    from . import index as X
    from . import transcripts as T
    ws = cfg["_ws"]
    problems = file_problems(ws)
    try:
        src = json.loads((Path(ws) / "index" / "sources.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        problems.append(("索引", "index/sources.json 读不出"))
        return problems
    head = gitio.rev_parse(cfg["repo"], cfg["ref"])
    if src.get("head") != head:
        n = gitio.count_between(cfg["repo"], src.get("head"), head)
        problems.append(("落后", f"分支比索引多 {n if n is not None else '?'} 个提交"))
    now_files = sorted([str(Path(p).relative_to(Path(os.path.expanduser(cfg["transcripts"]["projects_dir"])))), n]
                       for p, n in T.read(cfg)["branch_files"])
    if src.get("transcripts") != now_files:
        problems.append(("落后", "会话记录有新内容还没折进索引"))
    if check_index and not any(p[0] == "落后" for p in problems):
        diffs, cause = X.check(cfg, X.build(cfg)[0])
        if diffs:
            problems.append(("索引不一致", cause))
    return problems
