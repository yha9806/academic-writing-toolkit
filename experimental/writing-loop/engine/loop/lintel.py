"""第 0 层：把「等你反应的事」写成 lintel 的活动文件（plan 阶段 4.2）。

刘海由 lintel 统一画（spec D-L0），这里只交内容。样式归宿主，所以能挑的只有宿主词表里的词；
spec 6.2 的来源色照下面这张表对到 lintel 的调色板，来源之外一律同时写文字。

一件事一张卡（spec 6.1）。今天产五种，其中三种只在有事时存在：

    draft     稿件现状，永远在
    reply     我回了你最新的一条消息，你还没看     ◐
    ledger    台账里没落到原文上的条目             △
    triggers  不知道因为你哪句话而改的改动集       △ / ◌
    tool      引擎自己出事                         ⚠

「同一件事没有新变化不重写」靠 revision：内容算一个哈希，和磁盘上那份一样就不写。
例外是文件旧到快过心跳——lintel 拿文件的修改时间判来源程序还活着（1.5 倍心跳没动就画 ⚠），
所以到点要把同样的字节再写一遍：字节一样 → revision 一样 → 宿主不会把你已经看过的又标成没看过。
"""
import hashlib
import json
import os
import time
from pathlib import Path

PRODUCER = "awt-loop"
HOME = "~/Library/Application Support/lintel"
HEARTBEAT = 120.0

#: spec 6.2 的来源色 → lintel 调色板。琥珀在调色板里最近的一档是 orange。
SOURCE = {"you": "blue", "text": "slate", "claude": "orange", "external": "purple", "tool": "red"}
SOURCE_WORD = {"you": "你", "text": "原文 · git", "claude": "Claude", "external": "外部", "tool": "工具"}

#: 不参与 revision 的字段：它们每次都变，算进去就等于每次都「有新变化」——
#: 而「有新变化」在宿主那边意味着你已经看过的卡又被标成没看过，于是刘海每隔几秒重新弹一次。
VOLATILE = ("updatedAt", "activityAt", "events")
#: 同上，只是埋在 status 里（新鲜度用的时刻）。
VOLATILE_STATUS = ("lastWriteAt",)


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"


def revision(a):
    body = {k: v for k, v in a.items() if k not in VOLATILE and k != "revision"}
    if "status" in body:
        body["status"] = {k: v for k, v in body["status"].items() if k not in VOLATILE_STATUS}
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def card(aid, *, source, label, phase, tag, center, lines, ws, rank="none",
         flagged=False, open_=True, pill=None, stats=None, events=(), now=None):
    """一张卡。`lines` 是弹出卡第二行（第一行永远是「谁说的」，spec 6.1）。"""
    a = {
        "schema": 1, "id": aid,
        "open": open_, "running": False, "inProgress": False, "stale": False,
        "flagged": flagged, "rank": rank,
        "labelUntilSeen": False, "pillUntilSeen": False,
        "heartbeatSeconds": HEARTBEAT,
        "updatedAt": _iso(now), "activityAt": _iso(now),
        "status": {"center": center, "lastWriteAt": _iso(now)},
        "label": {"text": label, "tone": SOURCE[source]},
        "ears": {"leading": ws, "phase": phase, "tag": {"text": tag, "tone": SOURCE[source]}},
        "popup": [
            {"label": "谁说的", "text": SOURCE_WORD[source], "tone": "secondary", "lines": 1},
            {"label": label, "text": lines, "tone": "primary", "lines": 2},
        ],
        "body": [],
        "events": [{"id": i, "type": t, "at": _iso(now)} for i, t in events],
    }
    if pill:
        a["pill"] = {"pulse": False, "title": pill, "tint": SOURCE[source]}
    if stats:
        a["body"] = [{"kind": "stats", "cells": [{"label": k, "value": str(v)} for k, v in stats]}]
    a["revision"] = revision(a)
    return a


def build(summary, *, now, problems=()):
    """从索引摘要（`index.summarize`）生成活动。`problems` 是引擎自己的毛病，有就出 ⚠ 那张卡。"""
    ws = summary["name"]
    st = summary.get("ledger_status") or {}
    out = []

    out.append(card(
        "draft", source="text", label="稿件", phase=summary["head"], tag=f"{summary['sentences']} 句",
        center="idle", ws=ws, pill=f"{summary['versions']} 版", now=now,
        lines=f"{summary['sentences']} 句，{summary['versions']} 个定稿版本，最新 {summary['head']}",
        stats=[("句", summary["sentences"]), ("版", summary["versions"]),
               ("改动集", summary["changesets"]), ("你的消息", summary["messages"])]))

    bad = st.get("not_found", 0) + st.get("file_missing", 0) + st.get("no_source", 0) + summary["unattached_ledger"]
    if bad:
        out.append(card(
            "ledger", source="text", label="缺依据", phase="台账", tag=f"{bad} 条",
            center="flagged", rank="waiting", flagged=True, ws=ws, pill=f"{bad} 条", now=now,
            lines=f"{summary['ledger']} 条台账里有 {bad} 条没落到原文上",
            stats=[("找到", st.get("found", 0)), ("找不到", st.get("not_found", 0)),
                   ("文件缺失", st.get("file_missing", 0)), ("无原文", st.get("no_source", 0)),
                   ("没挂上句子", summary["unattached_ledger"])],
            events=[(f"evidence-missing:{bad}", "evidence-missing")]))

    unknown, mixed = summary["all_unknown"], summary["mixed"]
    if unknown or mixed:
        # 全 △ 是「不知道」，只有推断是「我替你定的，你还没确认」——挤进同一个词就分不出哪种要你看。
        out.append(card(
            "triggers", source="claude", label="触发源", phase="改动集",
            tag=f"{unknown} △" if unknown else f"{mixed} ◌",
            center="flagged" if unknown else "assumed", rank="waiting" if unknown else "none",
            flagged=bool(unknown), ws=ws, pill=f"{unknown + mixed}/{summary['changesets']}", now=now,
            lines=f"{summary['changesets']} 个改动集里，{unknown} 个不知道因为你哪句话而改，{mixed} 个是脚本推断的",
            stats=[("改动集", summary["changesets"]), ("全 △", unknown), ("推断", mixed)],
            events=[(f"drift:{unknown}:{mixed}", "drift")]))

    if problems:
        text = "；".join(problems)[:20000]
        out.append(card(
            "tool", source="tool", label="跑挂了", phase="引擎", tag=f"{len(problems)} 处",
            center="broken", rank="anomaly", flagged=True, ws=ws, now=now, lines=text,
            events=[(f"tool-broken:{hashlib.sha1(text.encode()).hexdigest()[:12]}", "tool-broken")]))

    return out


class NotRegistered(Exception):
    """lintel has no producer by this id. Off by default (spec v2 D5): write nothing, create nothing."""


def registered(home=HOME, producer=PRODUCER):
    """True only if lintel's registry.json is readable, has the expected shape, and names this producer.
    Anything else — no file, bad JSON, a list where a mapping belongs — counts as not registered."""
    try:
        data = json.loads((Path(os.path.expanduser(home)) / "registry.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    producers = data.get("producers") if isinstance(data, dict) else None
    return isinstance(producers, dict) and producer in producers


def sync(acts, *, home=HOME, producer=PRODUCER, now=None, heartbeat=HEARTBEAT):
    """写进 lintel 的活动目录。返回 {"written","touched","unchanged","removed"}。

    写法照协议：先写临时文件再改名（读的人永远看到完整的一份）。不在 `acts` 里的旧卡直接删掉——
    事情了了就该从刘海上消失。"""
    if not registered(home, producer):
        raise NotRegistered(f"lintel 里没有登记来源 {producer}（{home}/registry.json）：没登记就不写，也不建目录")
    now = time.time() if now is None else now
    d = Path(os.path.expanduser(home)) / "producers" / producer / "activities"
    d.mkdir(parents=True, exist_ok=True)
    counts = {"written": 0, "touched": 0, "unchanged": 0, "removed": 0}
    keep = set()
    for a in acts:
        p = d / f"{a['id']}.json"
        keep.add(p.name)
        data = (json.dumps(a, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
        old = None
        if p.exists():
            try:
                old = json.loads(p.read_text(encoding="utf-8"))
            except ValueError:
                old = None
        stale = not p.exists() or now - p.stat().st_mtime > heartbeat / 2
        if old is not None and old.get("revision") == a["revision"] and not stale:
            counts["unchanged"] += 1
            continue
        if old is not None and old.get("revision") == a["revision"]:
            # 心跳：内容没变，把原来那份原样再写一遍，只为更新修改时间。
            data = (json.dumps(old, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")
            counts["touched"] += 1
        else:
            counts["written"] += 1
        tmp = d / f".{a['id']}.json.tmp"
        tmp.write_bytes(data)
        tmp.replace(p)
    for p in d.glob("*.json"):
        if p.name not in keep:
            p.unlink()
            counts["removed"] += 1
    return counts
