"""第 0 层：把「等你反应的事」写成 lintel 的活动文件（plan 阶段 4.2）。

刘海由 lintel 统一画（spec D-L0），这里只交内容。样式归宿主，所以能挑的只有宿主词表里的词。

**一个稿件一个活动**（设计研究 2026-09-18 平衡规则 P1，作者 09-18 定稿）。活动 id 是 `loop-<稿件名>`，
登记表里的每个稿件各有一个常驻产出，各写各的那一份；
两翼、胶囊、弹出、展开态只说眼下最要紧的一件事，按 P2/P3 的顺序：

    引擎出事                      跑挂了     ⚠ anomaly，红
    最新改动集追不到你哪句话      改动无出处  Time Sensitive：drift 事件（登记时标 attention）弹精简卡
    最新改动集追到了你的话        为什么改    Active：右翼是 Claude 在解释块里写的 ≤6 字标签（没写就「改了 N 句」），
                                             小数字是改动句数；changed 事件不弹
    还没有改动                    还没有改动  idle

Passive 的事（缺依据的台账条目、被拦下的 human/ 写入）不上刘海：只进面板（detail），并作为
不带 attention 的事件记下来。看过就撤（P4）：labelUntilSeen / pillUntilSeen。

「同一件事没有新变化不重写」靠 revision：内容算一个哈希，和磁盘上那份一样就不写。
例外是文件旧到快过心跳——lintel 拿文件的修改时间判来源程序还活着（1.5 倍心跳没动就画 ⚠），
所以到点要把同样的字节再写一遍：字节一样 → revision 一样 → 宿主不会把你已经看过的又标成没看过。
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

PRODUCER = "awt-loop"
HOME = "~/Library/Application Support/lintel"


def lintel_home():
    """lintel's directory, read at call time so tests (and other hosts) can point it elsewhere."""
    return os.environ.get("LOOP_LINTEL_HOME") or HOME
HEARTBEAT = 120.0

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


#: 作者 09-18 定的身份色是靛蓝；lintel 调色板里最近的一档（◌）。
IDENTITY = "deepBlue"
#: 09-18 之前的产出一个稿件写六张卡；同一目录里遇到就删（它们的事现在都在一个活动里）。
LEGACY_IDS = ("draft", "reply", "ledger", "triggers", "guard", "tool")


def activity_id(name):
    """`loop-<稿件名>`, with anything the host might not accept in a file name folded to `-`."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "ws"
    return f"loop-{slug}"[:128]
#: 右翼放得下约 6 个汉字（lintel slots.md §1）；拉丁字母算半个，所以「colSmol 说反」正好是 6。
LABEL_MAX = 6
#: 展开态总高 ≤470pt（slots.md §3）：三段加四行两行的句子刚好，多了看不到。
ROWS_SHOWN = 4


def width(text):
    """Display width in CJK-character units: a CJK character is 1, anything narrower is ½."""
    return sum(1.0 if ord(ch) >= 0x2E80 else 0.5 for ch in text)


def _clip(text, n):
    """Cut to n code points, with an ellipsis. For the wing use `_fit`, which counts width."""
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


def detex(text):
    """LaTeX as the reader would see it, for the card only; the index keeps the source."""
    text = re.sub(r"\$([^$]*)\$", r"\1", text or "")
    for a, b in (("\\times", "×"), ("{,}", ","), ("\\%", "%"), ("--", "–"), ("~", " "), ("{=}", "="), ("\\,", " ")):
        text = text.replace(a, b)
    text = re.sub(r"\\[A-Za-z]+\{([^}]*)\}", r"\1", text)
    return re.sub(r"[{}]", "", text)


def _fit(text, w):
    """Cut to a display width of w CJK units, ellipsis included."""
    text = (text or "").replace("\n", " ").strip()
    if width(text) <= w:
        return text
    out = ""
    for ch in text:
        if width(out + ch) + 0.5 > w:
            break
        out += ch
    return out.rstrip() + "…"


def _sha(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def _prune(x):
    """Drop None values: the host rejects unknown types, and None is not a string."""
    if isinstance(x, dict):
        return {k: _prune(v) for k, v in x.items() if v is not None}
    if isinstance(x, list):
        return [_prune(v) for v in x]
    return x


def sections(lc):
    """「X6.2、X7.2、X9.3 等 15 处」: the first labels and the count, never the sentences themselves."""
    labels = [r["label"] for r in lc["rows"] if r["label"]]
    head = "、".join(labels[:3])
    if not head:
        return f"{lc['n']} 处"
    return f"{head} 等 {lc['n']} 处" if lc["n"] > 3 else f"{head} · {lc['n']} 处"


KIND_WORD = {"added": "新增", "removed": "删去", "edited": "改写", "split": "拆分", "merge": "合并"}


def _body(lc):
    """The expanded card (storyboard ⑧): your words, Claude's reading, then the rows, two lines each."""
    if not lc:
        return []
    items = []
    for r in lc["rows"][:ROWS_SHOWN]:
        text = detex(r["new"] or r["old"])
        items.append({"kind": "para", "tone": "white85",
                      "text": f"{r['label']} {KIND_WORD.get(r['kind'], r['kind'])}  {_clip(text, 110)}"})
    if lc["n"] > ROWS_SHOWN:
        items.append({"kind": "para", "tone": "white55", "text": f"…还有 {lc['n'] - ROWS_SHOWN} 行，在面板里"})
    return [
        {"kind": "section", "title": "你说",
         "items": [{"kind": "para", "tone": "white85",
                    "text": _clip(lc["verbatim"], 140) if lc["verbatim"] else "追不到你哪句话"}]},
        {"kind": "section", "title": "Claude 读成",
         "items": [{"kind": "para", "tone": "white85", "text": _clip(lc["reading"], 140) if lc["reading"] else "没有写「读成」"}]},
        {"kind": "section", "title": f"改了 · {lc['n']} 行", "badge": _clip(lc["changed"], 64) if lc["changed"] else None,
         "items": items},
    ]


def _detail(summary, lc, bad, notices):
    """The panel (storyboard ⑨): every changeset newest first, and the Passive things that never reach the notch."""
    hist = summary.get("history") or []
    traced = sum(1 for h in hist if h["traced"])
    history = []
    for h in hist[:500]:
        history.append({
            "id": h["id"], "tag": h["id"], "badge": None if h["traced"] else "△",
            "at": _iso(h["time"]) if h["time"] else None, "expandable": True,
            "lines": [
                {"label": "你说", "text": h["verbatim"] or "追不到你哪句话", "tone": "white85" if h["verbatim"] else "orange"},
                {"label": "改了", "text": f"{h['n']} 行", "tone": "white55"},
            ]})
    if lc:
        head = f"刚改 {lc['n']} 行 · " + ("已追到" if lc["traced"] else "无出处")
    else:
        head = "没有改动"
    return {
        "listTitle": _clip(f"{summary['name']} · {head}", 64),
        "dot": IDENTITY,
        "history": history,
        "historyNote": _clip(f"有空再看：拦下 {len(notices)} 次 · 缺依据 {bad} 条", 64),
        "stats": [
            {"label": "版本", "value": str(summary["versions"])},
            {"label": "句", "value": str(summary["sentences"])},
            {"label": "改动集", "value": str(summary["changesets"])},
            {"label": "追到", "value": f"{traced}/{len(hist)}"},
            {"label": "拦下", "value": str(len(notices)), "tone": "orange" if notices else None},
            {"label": "缺依据", "value": str(bad), "tone": "orange" if bad else None},
        ],
        "chart": {
            "title": "改动集",
            "headline": _clip(f"{len(hist)} 个改动集里 {traced} 个追到你的话", 64),
            "bars": [{"seconds": float(h["n"]), "swatch": IDENTITY if h["traced"] else "orange"} for h in reversed(hist)][:500],
            "legend": [{"name": "追到", "count": traced, "swatch": IDENTITY},
                       {"name": "追不到", "count": len(hist) - traced, "swatch": "orange"}],
        },
    }


def build(summary, *, now, problems=(), notices=()):
    """从索引摘要（`index.summarize`）生成活动：一个稿件一个，永远只有一个。
    `problems` 是引擎自己的毛病；`notices` 是该知道但不是故障的事（被拦下的写入）。"""
    ws = summary["name"]
    lc = summary.get("latest_changeset")
    st = summary.get("ledger_status") or {}
    bad = st.get("not_found", 0) + st.get("file_missing", 0) + st.get("no_source", 0) + summary.get("unattached_ledger", 0)
    n = lc["n"] if lc else 0
    events = []

    if problems:
        text = "；".join(problems)[:20000]
        label, tone, center, rank, flagged = "跑挂了", "red", "broken", "anomaly", True
        tag, pill = f"{len(problems)} 处", f"{len(problems)} ⚠"
        popup = [("谁说的", "工具", "secondary", 1), ("跑挂了", text, "warning", 2)]
        events.append((f"tool-broken:{_sha(text)}", "tool-broken"))
    elif lc and not lc["traced"]:
        # Time Sensitive（P2）：改了，但不知道因为你哪句话。drift 登记时标 attention，会弹精简卡。
        label, tone, center, rank, flagged = "改动无出处", "orange", "flagged", "event", True
        tag, pill = f"{n} △", f"{n} △"
        popup = [("你说", "追不到你哪句话", "warning", 1),
                 ("改了", sections(lc), "primary", 1),
                 ("读成", lc["reading"] or "没有写「读成」", "secondary", 2)]
        events.append((f"drift:{lc['id']}", "drift"))
    elif lc:
        # Active（P2）：右翼 = 为什么改（Claude 在解释块里写的 ≤6 字），小数字 = 改了几句。changed 不弹。
        label = _fit(lc["label"], LABEL_MAX) if lc.get("label") else f"改了{n}句"
        tone, center, rank, flagged = IDENTITY, "done", "event", False
        tag, pill = f"{n} 句", str(n)
        popup = [("你说", lc["verbatim"] or "（没有原话）", "primary", 1),
                 ("改了", sections(lc), "primary", 1),
                 ("读成", lc["reading"] or "没有写「读成」", "secondary", 2)]
        events.append((f"changed:{lc['id']}", "changed"))
    else:
        label, tone, center, rank, flagged = "还没有改动", IDENTITY, "idle", "none", False
        tag, pill = f"{summary['sentences']} 句", None
        popup = [("谁说的", "原文 · git", "secondary", 1),
                 ("稿件", f"{summary['sentences']} 句，{summary['versions']} 个版本，最新 {summary['head']}", "primary", 2)]

    # Passive（P2）：不上刘海，只进面板；事件不带 attention。
    if notices:
        events.append((f"guard:{_sha('；'.join(notices))}", "guard"))
    if bad:
        events.append((f"evidence-missing:{bad}", "evidence-missing"))

    a = {
        "schema": 1, "id": activity_id(ws),
        "open": True, "running": False, "inProgress": False, "stale": False,
        "flagged": flagged, "rank": rank,
        "labelUntilSeen": True, "pillUntilSeen": True,
        "heartbeatSeconds": HEARTBEAT,
        "updatedAt": _iso(now), "activityAt": _iso(now),
        "status": {"center": center, "lastWriteAt": _iso(now)},
        "label": {"text": label, "tone": tone},
        # 左耳很窄：来源名宿主已经画了（识别字 / 登记名），这里只放稿件名。
        "ears": {"leading": _clip(ws, 64), "phase": (lc["id"] if lc else summary["head"]),
                 "tag": {"text": tag, "tone": tone}},
        "popup": [{"label": l, "text": _clip(t, 20000), "tone": tn, "lines": ln} for l, t, tn, ln in popup],
        # 另一件活动展开时，底部翻页行写的是这一件的 flip；没有它宿主写「还没有标签」。
        "flip": {"title": label, "subtitle": _clip(ws, 64), "phase": (lc["id"] if lc else summary["head"])},
        "body": _body(lc),
        "detail": _detail(summary, lc, bad, notices),
        "events": [{"id": i, "type": t, "at": _iso(now)} for i, t in events],
    }
    if pill:
        a["pill"] = {"pulse": False, "title": pill, "tint": tone}
    a = _prune(a)
    a["revision"] = revision(a)
    return [a]


class NotRegistered(Exception):
    """lintel has no producer by this id. Off by default (spec v2 D5): write nothing, create nothing."""


def registered(home=None, producer=PRODUCER):
    """True only if lintel's registry.json is readable, has the expected shape, and names this producer.
    Anything else — no file, bad JSON, a list where a mapping belongs — counts as not registered."""
    try:
        data = json.loads((Path(os.path.expanduser(home or lintel_home())) / "registry.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    producers = data.get("producers") if isinstance(data, dict) else None
    return isinstance(producers, dict) and producer in producers


def sync(acts, *, home=HOME, producer=PRODUCER, now=None, heartbeat=HEARTBEAT):
    """写进 lintel 的活动目录。返回 {"written","touched","unchanged","removed"}。

    写法照协议：先写临时文件再改名（读的人永远看到完整的一份）。只清掉旧版六张卡留下的文件；
    别的稿件的活动由它们自己的产出管，这里不碰。"""
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
        if p.name not in keep and p.stem in LEGACY_IDS:
            p.unlink()
            counts["removed"] += 1
    return counts
