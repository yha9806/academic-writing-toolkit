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

`revision` 是刘海上这件事的身份（设计 2026-09-22-awt-live M2）：宿主按它记你看过没有，所以它只由事的种类与 id 组成，
面板、标签、事件、时刻都不进来。先前它是整份活动的哈希，面板一变看过的旧改动就又算没看过，09-22 一天重亮四次。
「内容没变不重写」另用 `content_hash`，每轮对磁盘上那份现算。例外是文件旧到快过心跳——lintel 拿文件的修改时间
判来源程序还活着（1.5 倍心跳没动就画 ⚠），所以到点要把同样的字节再写一遍。
"""
import hashlib
import json
import os
import re
import time
from pathlib import Path

PRODUCER = "awt-loop"
HOME = "~/Library/Application Support/lintel"


# build(coverage=...) not given: callers that know no workspace (tests, benches) add no coverage cell.
NOT_GIVEN = object()

def lintel_home():
    """lintel's directory, read at call time so tests (and other hosts) can point it elsewhere."""
    return os.environ.get("LOOP_LINTEL_HOME") or HOME
HEARTBEAT = 120.0

#: 写盘判据里不算的字段：它们每轮都可能变，算进去就等于每轮都重写。
VOLATILE = ("updatedAt", "activityAt")
#: 同上，只是埋在 status 里（新鲜度用的时刻）。
VOLATILE_STATUS = ("lastWriteAt",)
#: 改动无出处在提交后这么久里算「刚发生的事」（rank event），之后回到普通一级（设计 2026-09-22-awt-live M4）。
#: 其余的事一律不用 event：协议里它是「刚发生、只停几秒」，长期挂着会一直抢主位。
DRIFT_FRESH = 3600.0
# 开工弹卡（作者 09-22：每发一条就弹）在消息之后停这么久：许愿柳先弹 6 秒、冷却 10 秒，写作循环的排在它后面，
# 要等到那时这件事还在，排队的那张才弹得出来（lintel C2：两个来源各排各的）。
START_FRESH = 45.0
# 只有读者组结果的落地（分镜 ⑤⑨）留这么久；改了句子的落地就是那个改动集自己，不另计时。
LANDED_HOLD = 3600.0


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + ".000Z"


def identity(key):
    """刘海上这件事的身份，宿主按它记你看过没有。key 只写事的种类与 id（见 build）。"""
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def content_hash(a):
    """写不写盘的判据：整份活动去掉每轮都变的时刻。事件的 id 与类型算在里面（只多了一个事件也要写，
    不然事件到不了宿主），事件的时刻不算。"""
    body = {k: v for k, v in a.items() if k not in VOLATILE}
    if "status" in body:
        body["status"] = {k: v for k, v in body["status"].items() if k not in VOLATILE_STATUS}
    body["events"] = [{k: v for k, v in e.items() if k != "at"} for e in body.get("events", [])]
    return hashlib.sha1(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _when(lc, default):
    """改动集的提交时刻（索引里是字符串或数）；读不出就用 default。"""
    try:
        return float(lc.get("time"))
    except (TypeError, ValueError):
        return default


#: 作者 09-18 定的身份色是靛蓝；登记表里也是 indigo（09-21 之前这里写 deepBlue，面板圆点与括号成了两种蓝）。
IDENTITY = "indigo"
#: 进度条里「别处」的格子（窗口里没有你的消息：别的会话或你自己提交的，只是历史）；只染标记不染字。
UNTRACED = "white28"
#: 进度条里「对不上」的格子（窗口里有你的消息，没一条对上：Claude 改了你没让改的）——橙 = 要你看。
UNMATCHED = "orange"
#: 展开第一页的逐词改动行数上限：作者 09-21 要在展开卡里上下滚动看全部改动，所以尽量全给（宿主一节最多 64 条）；
#: 超过的才写「…还有 N 句，在面板里」。
DIFF_ROWS = 40
#: 09-18 之前的产出一个稿件写六张卡；同一目录里遇到就删（它们的事现在都在一个活动里）。
LEGACY_IDS = ("draft", "reply", "ledger", "triggers", "guard", "tool")


def activity_id(name):
    """`loop-<稿件名>`, with anything the host might not accept in a file name folded to `-`."""
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "ws"
    return f"loop-{slug}"[:128]
#: 右翼放得下约 6 个汉字（lintel slots.md §1）；拉丁字母算半个，所以「betaVal 说反」正好是 6。
LABEL_MAX = 6
#: 展开态总高 ≤470pt（slots.md §3）：三段加四行两行的句子刚好，多了看不到。
# 展开态分页之后（候选 E）「改了」那一节独占一页，能放下更多行；470pt 里两行一句约放 8 句。
ROWS_SHOWN = 8


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
    """「X6.2、X7.2、X9.3 等 15 句」: the first labels and the count, never the sentences themselves. The unit is 句 everywhere."""
    labels = [r["label"] for r in lc["rows"] if r["label"]]
    head = "、".join(labels[:3])
    if not head:
        return f"{lc['n']} 句"
    return f"{head} 等 {lc['n']} 句" if lc["n"] > 3 else f"{head} · {lc['n']} 句"


def touched(lc, names):
    """The sections a change set touched, as the short names from the registry (「摘要 · §3.2」), in order of first appearance.
    A row without a section prefix in the index falls back to the first letter of its label."""
    seen = []
    for r in lc.get("rows") or []:   # 面板的压缩历史项可能没有 rows
        p = r.get("section") or (r.get("label") or "")[:1]
        if p and p not in seen:
            seen.append(p)
    return " · ".join(names.get(p, p) for p in seen)


def _hm(t):
    return time.strftime("%H:%M", time.localtime(t)) if t else ""


KIND_WORD = {"added": "新增", "removed": "删去", "edited": "改写", "split": "拆分", "merge": "合并"}


def origin(lc):
    """Where a change set came from: traced to your message; untraced with your messages in the window but none matched
    (Claude changed what you did not ask: 对不上); or untraced with no message of yours in the window (someone else's
    commit, or your own: 别处). The author 09-21: only the middle one is worth an alert."""
    if lc["traced"]:
        return "traced"
    return "unmatched" if lc.get("messages_in_window", 0) else "elsewhere"


def _reason(lc):
    o = origin(lc)
    if o == "traced":
        how = STRENGTH.get(lc.get("strength"))
        return "追到你的话" + (f" · {how}" if how else "")
    if o == "unmatched":
        return f"窗口里 {lc.get('messages_in_window', 0)} 条消息都对不上"
    return "窗口里没有你的消息"


def _headline(lc):
    o = origin(lc)
    if o == "traced":
        return _fit(lc["label"], LABEL_MAX) if lc.get("label") else "改了"
    return "改动无出处" if o == "unmatched" else "别处改了"


def _body(lc):
    """The expanded card (分镜 ㊱ ㊲, the author 09-21): the first page answers why · where · how many — a headline
    (Claude's label, or what kind of change this is), the reason, then at most three word-diff rows (the host draws only
    the changed words); whole sentences stay in the panel. Then 依据 when Claude wrote one; 你说 and Claude 读成 are wishing-willow's (one conversation layer, #28).
    No page says 「追不到」 or 「没有写」— an absent thing is not drawn."""
    if not lc:
        return []
    tone = {"traced": "white", "unmatched": "orange", "elsewhere": "white55"}[origin(lc)]
    items = []
    # 追到但 Claude 没写标签时不画理由行：兜底的「改了」会和页标题「改了」重一次（09-21 真屏）。
    if not (origin(lc) == "traced" and not lc.get("label")):
        items.append({"kind": "para", "tone": tone, "text": _headline(lc)})
    items.append({"kind": "para", "tone": "white55", "text": _reason(lc)})
    for r in lc["rows"][:DIFF_ROWS]:
        word = KIND_WORD.get(r["kind"], r["kind"]) if r["kind"] not in ("edited", "moved") else ""
        item = {"kind": "diff", "label": f"{r['label']}{' ' + word if word else ''}", "new": _clip(detex(r["new"] or ""), 20000)}
        if r["old"]:
            item["old"] = _clip(detex(r["old"]), 20000)
        items.append(item)
    if lc["n"] > DIFF_ROWS:
        items.append({"kind": "para", "tone": "white55", "text": f"…还有 {lc['n'] - DIFF_ROWS} 句，在面板里"})
    pages = [{"kind": "section", "title": "改了", "items": items}]
    # 「你说」「Claude 读成」不再画：对话层只有一份，由许愿柳说（#28，作者 09-24 认可）。
    if lc.get("basis"):
        # 缺口 5：Claude 在解释块里写的「依据」，先前从不上前端
        pages.append({"kind": "section", "title": "依据", "items": [{"kind": "para", "tone": "white85", "text": _clip(lc["basis"], 140)}]})
    return pages


ROWS_LOCATED = 16


def _rows(h, names):
    """The rows the panel shows when a changeset is opened (候选 A, 作者 09-21 定甲+乙): which sentence, where it is
    (section · paragraph · file:line, whichever the index knows), what to paste, and the texts before and after."""
    out = []
    for r in (h.get("rows") or [])[:ROWS_LOCATED]:
        sec = names.get(r.get("section") or "", r.get("section") or "")
        at = f"{r['path']}:{r['line']}" if r.get("path") and r.get("line") else None
        where = " · ".join(x for x in (sec, f"第 {r['par']} 段" if r.get("par") else None, at) if x)
        first = " ".join(detex(r.get("new") or r.get("old") or "").split()[:6])
        copy = " · ".join(x for x in (at, r.get("label"), f"“{first}…”" if first else None) if x)
        out.append({"label": r.get("label") or "", "where": _clip(where, 256) or None, "copy": _clip(copy, 1024) or None,
                    "old": detex(r["old"]) if r.get("old") else None, "new": detex(r.get("new") or "")})
    return out


#: 一个折叠组最多摊开这么多改动集（协议 rows ≤16）；更长的连续无出处切成几组。
FOLD_MAX = 16


FOLD_WORD = {"unmatched": "△ 对不上", "elsewhere": "别处"}


def _fold_rows(run, names):
    """缺口 2（分镜 ⑥④）：折叠的对不上 / 别处点开给逐句，和追到的一样；每句的定位前面加提交号与时刻。
    精简历史里没有句子的改动集（旧索引）退回一行：提交号、句数与时刻、提交说明。"""
    out = []
    for r in run:
        rows = _rows(r, names)
        if not rows:
            out.append({"label": r["id"][:7], "where": _clip(f"{r['n']} 句 · {_hm(r['time'])}", 256), "copy": r["id"],
                        "new": _clip(detex(r.get("subject") or ""), 200) or "（没有提交信息）"})
        for x in rows:
            x = dict(x)
            x["where"] = _clip(" · ".join(y for y in (r["id"][:7], _hm(r["time"]), x.get("where")) if y), 256)
            out.append(x)
        if len(out) >= ROWS_LOCATED:
            break
    return out[:ROWS_LOCATED]


def _history(hist, names, touches=None):
    """The panel timeline (分镜 ㉚ ㊴): a traced change set is its own row (your words, the count as the badge, the commit
    as the dim trailing text, the sentence rows when opened); consecutive untraced ones of the same kind fold into one
    row 「△ 对不上 ×k」 or 「别处 ×k」 that opens to one line per change set.
    `touches` (change set id -> section prefixes, from the overview) lets the panel's second layer keep only the rows
    that touched one section (分镜 ㊻)."""
    touches = touches or {}

    def secs(ids):
        out_ = []
        for i in ids:
            for x in touches.get(i) or ():
                if x not in out_:
                    out_.append(x)
        return out_ or None
    out = []
    i = 0
    while i < len(hist):
        h = hist[i]
        if h["traced"]:
            # 2026-09-21: the panel rows all read 你说 …, which carries little; the row now leads with why (Claude's label)
            # 次行写改到哪；原话不再在面板里重复（弹出卡与展开卡第 2 页有）。没有标签时行头写改到的节。
            where = touched(h, names)
            label = _fit(h["label"], LABEL_MAX) if h.get("label") else None
            lines = [{"label": "改到", "text": where, "tone": "white55"}] if (label and where) else []
            if STRENGTH.get(h.get("strength")):
                lines.append({"label": "追到", "text": STRENGTH[h["strength"]], "tone": "white55"})   # 缺口 3
            if h["n"] > ROWS_LOCATED:
                lines.append({"label": "还有", "text": f"{h['n'] - ROWS_LOCATED} 句没列出", "tone": "white55"})   # 缺口 7
            out.append({"id": h["id"], "tag": label or where or "改了", "badge": f"{h['n']} 句", "duration": h["id"][:7],
                        "at": _iso(h["time"]) if h["time"] else None, "expandable": True,
                        "lines": lines, "rows": _rows(h, names) or None, "sections": secs([h["id"]])})
            i += 1
            continue
        kind_ = origin(h)
        run = []
        while i < len(hist) and not hist[i]["traced"] and origin(hist[i]) == kind_ and len(run) < FOLD_MAX:
            run.append(hist[i]); i += 1
        total = sum(r["n"] for r in run)
        out.append({"id": f"fold-{run[0]['id']}", "tag": f"{FOLD_WORD[kind_]} ×{len(run)}", "badge": f"{total} 句",
                    "at": _iso(run[0]["time"]) if run[0]["time"] else None, "expandable": True,
                    "lines": [{"label": "还有", "text": f"{total - ROWS_LOCATED} 句没列出", "tone": "white55"}] if total > ROWS_LOCATED else [],
                    "rows": _fold_rows(run, names),
                    "sections": secs([r["id"] for r in run])})
    return out


def _detail(summary, lc, bad, notices, overview=None, coverage=NOT_GIVEN, denials=(), overrides=(), readers=None):
    """The panel (分镜 ㉚): timeline with the untraced folded, a progress strip one cell per change set (the author 09-21:
    progress by change set), and three cells — 追到 / 拦下 / 缺依据. No chart: the host's chart is a duration histogram."""
    hist = summary.get("history") or []
    names = summary.get("section_names") or {}
    traced = sum(1 for h in hist if h["traced"])
    if lc:
        head = f"{lc['n']} 句 · " + {"traced": "已追到", "unmatched": "对不上", "elsewhere": "别处"}[origin(lc)]
    else:
        head = "没有改动"
    cell = {"traced": IDENTITY, "unmatched": UNMATCHED, "elsewhere": UNTRACED}
    kinds = [origin(h) for h in hist[:500]]
    history = _history(hist[:500], names, overview and overview.get("touches"))
    d = {
        "listTitle": _clip(f"{summary['name']} · {head}", 64),
        "dot": IDENTITY,
        "history": history,
        # 缺口 4：拦下按次数算（health 的 guard_denied），不按提醒的行数（那一行总是 1）。没给次数的旧调用照旧数行。
        "historyNote": _clip(f"有空再看：拦下 {len(denials) if denials else len(notices)} 次 · 缺依据 {bad} 条", 64),
        # 进度按改动集（作者 09-21），三色：追到靛蓝、对不上橙、别处灰。
        "strip": {"title": "改动集 · 旧 → 新",
                  "cells": [cell[k] for k in reversed(kinds)],
                  "legend": [{"name": "追到", "count": traced, "swatch": IDENTITY},
                             {"name": "对不上", "count": kinds.count("unmatched"), "swatch": UNMATCHED},
                             {"name": "别处", "count": kinds.count("elsewhere"), "swatch": UNTRACED}]},
        # 其余的格由 _strip 排（分镜 ⑥③）；没有总览时第一格是追到。
        "stats": [{"label": "追到", "value": f"{traced}/{len(hist)}"}],
    }
    if overview and overview.get("payload"):
        # 点进去的第一层（分镜 ㊸）：总览；上面这张改动集列表退到第二层。最下一行 = 最近一轮，点它进第二层。
        ov = dict(overview["payload"])
        if history:
            h = history[0]
            where = next((l["text"] for l in h.get("lines") or [] if l["label"] == "改到"), None)
            ov["latest"] = {"at": h.get("at"), "tag": h["tag"], "badge": (h.get("badge") or "").split(" ")[0] or None,
                            "where": where, "more": f"这一段 {overview.get('stage_changesets', 0)} 个改动集"}
        d["overview"] = ov
    # 数据条（分镜 ⑥③）：有总览时以总览的格（分镜 ㊾）为底，再加有发现 / 拦下 / 读者 / 构建落后；最多 8 格。
    # 没给拦下明细的旧调用，按提醒行数算（每行一次）。
    denied = list(denials) or [{"at": None, "detail": n} for n in notices]
    d["stats"] = _strip(d["stats"][0], bad, overview, coverage, denied, list(overrides), readers)
    return d



#: 数据条放不下 8 格时，先把这几格挪进「句」的悬停（分镜 ⑥③ 的默认：数据条最多 8 格，挤掉的进悬停）。
STRIP_DROP = ("版", "读者·最弱", "构建落后", "拦下")


def _found_cell(summary):
    """缺口 1：查出东西的检查。先前数据条只有「检查待办」（过期 / 没跑过），查出东西的不算进去。
    悬停列名字与一句结果，再写检查待办、AWT 读不了与豁免（分镜 ⑥③：挤掉的进悬停）。"""
    from . import coverage as V
    if summary is None:
        return {"label": "检查", "value": "没算过", "tone": "orange"}
    try:
        found, todo = V.findings(summary), V.attention(summary)
        gap, wv = V.gaps(summary), V.waived(summary)
        target = 1 if (summary.get("target") or {}).get("problems") else 0
    except (KeyError, TypeError, AttributeError):
        return {"label": "检查", "value": "读不出", "tone": "orange"}
    bits = [f"{r['name']}：{' '.join(str(r.get('result') or '有发现').split())[:40]}" for r in found[:6]]
    if len(found) > 6:
        bits.append(f"另 {len(found) - 6} 项")
    n_todo = len(todo) + target
    if n_todo:
        bits.append(f"检查待办 {n_todo}：" + "、".join(r["name"] for r in todo[:4]) + ("、目标档案" if target else ""))
    if gap:
        bits.append(f"AWT 读不了 {len(gap)}")
    if wv:
        bits.append(f"豁免 {len(wv)}")
    return {"label": "有发现", "value": str(len(found)), "tone": "orange" if found or n_todo else None,
            "hint": _clip("；".join(bits), 20000) or None}


def _strip(first, bad, overview, coverage, denials, overrides, readers):
    """数据条（分镜 ⑥③，缺口 1、4、6、8）：句 / 版 / 缺依据 / 有发现 / 拦下 / 读者·最弱 / 构建落后 / 标题页待填，
    另有两格只在不为 0 时出现：未决（作者还没定的风险与没过的门）、门放行（改句门拦过一次、这一轮仍带着标出句结束）。
    最多 8 格，多出来的按 STRIP_DROP 挪进第一格的悬停。"""
    from . import coverage as V
    from . import turns as TN
    ov = {c["label"]: c for c in (overview or {}).get("stats") or []}
    if ov:
        cells = [dict(c) for c in (ov.get("句"), ov.get("版"), ov.get("缺依据")) if c]
        stage = ov.get("改动集 · 这一段")
        for c in cells:
            if c["label"] == "版" and stage:
                c["hint"] = f"改动集 · 这一段 {stage['value']}"
    else:
        cells = [first, {"label": "缺依据", "value": str(bad), "tone": "orange" if bad else None}]
    if coverage is not NOT_GIVEN:
        cells.append(_found_cell(coverage))
    pending = getattr(V, "pending", None)
    try:
        rows = pending(coverage) if pending and isinstance(coverage, dict) else []
    except (KeyError, TypeError, AttributeError):
        rows = []
    if rows:
        cells.append({"label": "未决", "value": str(len(rows)), "tone": "orange",
                      "hint": _clip("；".join(r.get("name") or r.get("id") or "?" for r in rows), 20000)})
    if overrides:
        cells.append({"label": "门放行", "value": str(len(overrides)), "tone": "orange",
                      "hint": _clip(f"最近一次 {overrides[-1].get('at')}：{overrides[-1].get('detail')}", 20000)})
    last = "；".join(f"{d.get('at')} {d.get('detail')}" for d in denials[-3:])
    cells.append({"label": "拦下", "value": str(len(denials)), "tone": "orange" if denials else None,
                  "hint": _clip(f"模型想写 human/ 被拒 {len(denials)} 次，最近：{last}", 20000) if denials else None})
    w = TN.weakest_reader(readers.get("summary")) if readers else None
    if w:
        items = " · ".join(f"{m} {k}/{n}" for m, k, n in TN.RECALL.findall(readers.get("summary") or ""))
        cells.append({"label": "读者·最弱", "value": f"{w[1]}/{w[2]}", "hint": _clip(f"自由回忆：{items}（最弱 {w[0]}）", 20000)})
    for k in ("构建落后", "标题页待填", "投稿构建"):
        if ov.get(k):
            cells.append(dict(ov[k]))
    dropped = []
    for label in STRIP_DROP:
        if len(cells) <= 8:
            break
        c = next((c for c in cells if c["label"] == label), None)
        if c:
            cells.remove(c)
            dropped.append(f"{c['label']} {c['value']}")
    if dropped:
        cells[0] = dict(cells[0], hint="；".join(x for x in (cells[0].get("hint"), "另有 " + " · ".join(dropped)) if x))
    return [_prune(c) for c in cells[:8]]


def _status_line(summary, bad, coverage):
    """开工 / 在跑卡的第二行：稿子此刻的三个数（分镜 ⑤⑤）。检查没算过就写没算过，不写 0。"""
    from . import coverage as V
    try:
        found = f"有发现 {len(V.findings(coverage))}" if isinstance(coverage, dict) else "检查没算过"
    except (KeyError, TypeError, AttributeError):
        found = "检查读不出"
    return f"{summary['sentences']} 句 · 缺依据 {bad} · {found}"


def _checks_line(coverage):
    """落地卡的第二行（分镜 ⑤⑧）。检查结论没有「上一次」可比（设计 §2），所以写的是现状：有发现的是哪几项。"""
    from . import coverage as V
    if not isinstance(coverage, dict):
        return "检查没算过"
    try:
        found = V.findings(coverage)
    except (KeyError, TypeError, AttributeError):
        return "检查读不出"
    if not found:
        return "检查都过了"
    return f"有发现 {len(found)}：" + "、".join(r["name"] for r in found[:3]) + ("…" if len(found) > 3 else "")


STRENGTH = {"session": "○ 按会话", "sentence": "● 按句子"}


#: 有环时胶囊写「稿名 · 等你 N」：宿主胶囊宽封顶 120pt，环形小图标与内边距之外约放 7.5 个汉字宽，稿名先截。
RING_PILL_MAX = 7.5
RING_SIGHT = {"看得见": "seen", "推出来": "inferred", "只有提交": "commits"}
RING_LABELS = {"title": "这一轮", "current": "当前", "latest": "最近动静", "unhung": "没挂上环节", "closed": "已关的门", "waiting": "等你"}


def _ring(coverage, *, name, last_comment_at, last_change_at):
    """The manuscript ring as lintel draws it (plan step 4a; `ring.ring` computes it): each stage's state, sight and
    the few words in its box. A stage an item waits on is 等你 when an item is the author's to decide, 过期 when only
    a check or the reader panel is out of date. A ring that cannot be computed says so; it is never dropped."""
    from . import ring as RG
    try:
        r = RG.ring(coverage, last_comment_at=_iso(last_comment_at) if last_comment_at else None,
                    last_change_at=_iso(last_change_at) if last_change_at else None, name=name)
    except Exception as e:  # noqa: BLE001 -- the card still goes up; the ring says it could not be computed
        return {"name": _clip(name, 64), "since": "", "segments": [], "unhung": [], "waiting": 0, "closed": [],
                "labels": RING_LABELS, "error": f"环算不出来：{type(e).__name__}：{_clip(str(e), 200)}"}
    item = lambda x: {"id": _clip(str(x.get("id")), 32), "text": _clip(x.get("text") or "", 20000), "you": bool(x.get("you"))}
    segs = []
    for g in r["segments"]:
        mine = sum(1 for x in g["items"] if x.get("you"))
        state = {"hanging": "waiting" if mine else "stale", "unseen": "unseen", "done": "done", "open": "open"}[g["state"]]
        note = {"waiting": f"等你 {mine}", "stale": "过期", "done": "做过", "open": "还没到", "unseen": "看不见"}[state]
        segs.append({"key": g["key"], "name": g["name"], "state": state, "sight": RING_SIGHT[g["seen"]], "sightNote": g["seen"],
                     "note": note, "items": [item(x) for x in g["items"][:32]]})
    out = {"name": _clip(name, 64), "since": r["sinceNote"], "segments": segs, "unhung": [item(x) for x in r["unhung"][:32]],
           "waiting": r["waiting"], "labels": RING_LABELS,
           "closed": [{"date": c["date"][:16], "items": [_clip(x, 64) for x in c["items"][:64]]} for c in r["closed"][:32]]}
    for k, v in (("current", r["current"]), ("latest", r["latest"])):
        if v:
            out[k] = v
    if r.get("latest_at"):
        out["latestAt"] = _iso(RG._utc(r["latest_at"]).timestamp())
    return out


#: lintel 收的嵌套条数上限。
WITHIN_MAX = 16


def _within(note):
    """The wishing-willow sessions this draft is nested in (the author 09-24: the loop is an extension of the
    conversation, not a second app beside it), read from the note the hook keeps for willow (`outlet`): primary
    sessions first, at most WITHIN_MAX. lintel draws the draft inside one of them that is open, alone otherwise."""
    sessions = note.get("sessions") if isinstance(note, dict) else None
    if not isinstance(sessions, dict):
        return []
    rows = [(sid, v.get("role")) for sid, v in sessions.items() if isinstance(sid, str) and sid and isinstance(v, dict)
            and v.get("role") in ("primary", "history")]
    rows.sort(key=lambda r: r[1] != "primary")   # stable: the note's order within each role
    return [{"producer": "willow", "id": sid[:128], "role": role} for sid, role in rows[:WITHIN_MAX]]


def build(summary, *, now, problems=(), notices=(), overview=None, coverage=NOT_GIVEN, turn=None, readers=None,
          built_at=None, denials=(), overrides=(), note=None):
    """从索引摘要（`index.summarize`）生成活动：一个稿件一个，永远只有一个。
    `problems` 是引擎自己的毛病；`notices` 是该知道但不是故障的事（被拦下的写入）。
    `turn` 是最近一轮（`turns.current`），`readers` 是最近一次读者组（`turns.readers_run`），`built_at` 是索引最近一次建成的时刻；
    `denials` / `overrides` 是 health 里没确认过的拦下写入与改句门放行（`health.guard_denials` / `gate_overrides`）。
    一件事的先后（设计 B3，作者 09-22 定 B1 ②）：引擎出事 > 开工 > 本轮新出的无出处 > 在跑 > 只有读者组的落地 > 改动集 > 没有改动。"""
    from . import turns as TN
    ws = summary["name"]
    lc = summary.get("latest_changeset")
    st = summary.get("ledger_status") or {}
    bad = st.get("not_found", 0) + st.get("file_missing", 0) + st.get("no_source", 0) + summary.get("unattached_ledger", 0)
    n = lc["n"] if lc else 0
    names = summary.get("section_names") or {}
    where = touched(lc, names) if lc else ""
    events = []
    when_lc = _when(lc, now) if lc else None
    count = None   # 右翼的小数字（label.count）：字里不再有数（channel-separation §5）
    start = turn["start"] if turn else None
    ended = turn["ended"] if turn else None
    started = bool(turn and 0 <= now - start < START_FRESH)
    is_running = TN.running(turn, now)
    # 落地（B2）：这一轮结束了，索引是在结束之后建的（追平），这一轮的时间窗里有这个改动集。
    in_window = lambda t: t is not None and start is not None and ended is not None and start <= t <= ended + 5
    # 以 API 报错结束的一轮（StopFailure）不算落地：活没干完，只是停了。
    caught_up = ended is not None and built_at is not None and built_at >= ended and not turn.get("error")
    landed = bool(lc and lc["traced"] and n and caught_up and in_window(when_lc))
    readers_landed = bool(readers and caught_up and in_window(readers.get("t")) and not in_window(when_lc)
                          and now - ended < LANDED_HOLD)
    drift_now = bool(lc and not lc["traced"] and origin(lc) == "unmatched" and (not is_running or (start and when_lc >= start)))
    run_state = False
    status_line = _status_line(summary, bad, None if coverage is NOT_GIVEN else coverage)
    clock = None   # None = 按 when 画「几时前」；否则 (样式, 起点)
    phase = None

    if problems:
        text = "；".join(problems)[:20000]
        label, tone, center, rank, flagged = "跑挂了", "red", "broken", "anomaly", True
        key, when = f"problem:{_sha(text)}", now
        count, tag, pill = len(problems), f"{len(problems)} 处", f"{len(problems)} ⚠"
        popup = [("谁说的", "工具", "secondary", 1), ("跑挂了", text, "warning", 2)]
        events.append((f"tool-broken:{_sha(text)}", "tool-broken"))
    elif started:
        # 开工弹卡（作者 09-22：本稿件会话里每发一条就弹）：第一行收到哪一条（时刻 · 字数，不抄原话），第二行稿子此刻的三个数。
        label, tone, center, rank, flagged = "开工", "white", "live", "event", False
        key, when = f"started:{turn['key']}", start
        tag, pill = "开工", None
        popup = [("收到", f"你 {_hm(start)} 的消息 · {turn['chars']} 字", "primary", 1), ("稿子", status_line, "secondary", 1)]
        events.append((f"started:{turn['key']}", "started"))
        clock, phase = ("live", start), f"开工 · {_hm(start)}"
    elif is_running and not drift_now:
        # 在跑（B1 ②）：这一轮碰过稿子、还没结束。右翼写动作，不放数（分镜 ⑤⑦）；跑表从第一次碰稿算。不弹（Active）。
        act, first = TN.action(turn), turn["touches"][0][0]
        label, tone, center, rank, flagged = act, "white", "live", "none", False
        key, when = f"running:{turn['key']}", first
        tag, pill = act, None
        popup = [("在跑", f"{act} · 从 {_hm(first)}", "primary", 1), ("稿子", status_line, "secondary", 1)]
        clock, phase, run_state = ("live", first), act, True
    elif readers_landed:
        # 只跑出读者组结果、没改句子的一轮（分镜 ⑤⑨，默认弹，写最弱的一项）。
        w = TN.weakest_reader(readers.get("summary"))
        text = f"最弱 {w[0]} {w[1]}/{w[2]}" if w else "有结果"
        label, tone, center, rank, flagged = "读者组", "orange" if readers.get("verdict") == "findings" else "white", "done", "none", False
        key, when = f"landed-readers:{int(readers['t'])}", readers["t"]
        tag, pill = "读者组", (f"{w[1]}/{w[2]}" if w else None)
        popup = [("读者", text, "warning" if tone == "orange" else "primary", 1), ("改了", "无", "quiet", 1)]
        events.append((f"landed:readers-{int(readers['t'])}", "landed"))
        phase = f"落地 · {_hm(ended)}"
    elif lc and not lc["traced"]:
        if origin(lc) == "unmatched":
            # Time Sensitive（P2）：窗口里有你的消息，没一条对上 = Claude 改了你没让改的。橙 = 要你看；胶囊保留 △（作者 09-21）。
            label, tone, center, flagged = "改动无出处", "orange", "flagged", True
            rank = "event" if now - when_lc < DRIFT_FRESH else "none"
            key, when = f"change:{lc['id']}:unmatched", when_lc
            count, tag, pill = n, f"{n} 句", f"{n} △"
            popup = [("改了", sections(lc), "primary", 1), ("无出处", _reason(lc), "warning", 1)]
            events.append((f"drift:{lc['id']}", "drift"))
        else:
            # Active（P2）：窗口里没有你的消息 = 别的会话或你自己提交的，只是历史（分镜 ㊳，作者 09-21）。翼换字、不弹、灰。
            label, tone, center, rank, flagged = "别处改了", "white55", "idle", "none", False
            key, when = f"change:{lc['id']}:elsewhere", when_lc
            count, tag, pill = n, f"{n} 句", str(n)
            popup = [("改了", sections(lc), "primary", 1), ("别处", _reason(lc), "secondary", 1)]
            events.append((f"changed:{lc['id']}", "changed"))
    elif lc:
        # Active（P2）：右翼 = 为什么改（Claude 在解释块里写的 ≤6 字，没有就「改了」），小数字 = 几句。changed 不弹。
        label = _fit(lc["label"], LABEL_MAX) if lc.get("label") else "改了"
        tone, center, rank, flagged = "white", "done", "none", False
        key, when = f"change:{lc['id']}:traced", when_lc
        count, tag, pill = n, f"{n} 句", str(n)
        # 「你说」「读成」归许愿柳（#28）：弹卡只说改了哪些节，有依据再说依据。
        popup = [("改了", sections(lc), "primary", 1)]
        if lc.get("basis"):
            popup.append(("依据", lc["basis"], "secondary", 2))
        events.append((f"changed:{lc['id']}", "changed"))
        if landed:
            # 落地弹卡（分镜 ⑤⑧）：两行，改了什么（几句 · 追得牢不牢 · 哪几节）/ 检查此刻的现状。身份仍是这个改动集（M2）。
            how = STRENGTH.get(lc.get("strength"))
            popup = [("改了", " · ".join(x for x in (sections(lc), how) if x), "primary", 1),   # sections() already says how many
                     ("检查", _checks_line(None if coverage is NOT_GIVEN else coverage), "secondary", 1)]
            events.append((f"landed:{lc['id']}", "landed"))
            phase = f"落地 · {_hm(ended)}"
    elif summary.get("just_registered"):
        # 候选 B：刚从刘海上拖进来登记好的稿件（分镜 ⑯ 右半）。下一轮常驻产出会把它换成「还没有改动」。
        label, tone, center, rank, flagged = "登记好了", "white", "done", "none", False
        key, when = f"registered:{summary['head']}", now
        tag, pill = f"{summary['sentences']} 句", str(summary["sentences"])
        popup = [("谁说的", "拖放 · lintel", "secondary", 1),
                 ("稿件", f"{summary['sentences']} 句 · {len(summary.get('section_names') or {})} 节 · {summary.get('ref') or summary['head']}", "primary", 2)]
        events.append((f"changed:registered-{summary['head']}", "changed"))
    else:
        label, tone, center, rank, flagged = "还没有改动", "white", "idle", "none", False
        key, when = f"none:{ws}", None
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
        "open": True, "running": run_state, "inProgress": run_state, "stale": False,
        "flagged": flagged, "rank": rank,
        # 在跑期间看过也不撤（设计 B3）；开工的胶囊是跑表，也不撤。
        "labelUntilSeen": not run_state, "pillUntilSeen": not (run_state or started and not problems),
        "heartbeatSeconds": HEARTBEAT,
        # activityAt = 这件事发生的时刻（改动集 = 提交时刻），不是这一轮重建的时刻：宿主拿它排先后（设计 M5）。
        "updatedAt": _iso(now), "activityAt": _iso(when) if when is not None else None,
        "status": {"center": center, "lastWriteAt": _iso(now),
                   "clock": ({"style": clock[0], "since": _iso(clock[1])} if clock else
                             {"style": "ago", "since": _iso(when)} if when is not None and not problems else None)},
        "label": {"text": label, "tone": tone, "count": count},
        # 左耳很窄：来源名宿主已经画了（识别字 / 登记名），这里只放稿件名；第二格是改到的节（作者 09-21），不是提交号。
        "ears": {"leading": _clip(ws, 64), "phase": _clip(phase or where or ("没有改动" if not lc else ""), 64),
                 "tag": {"text": tag, "tone": tone}},
        "popup": [{"label": l, "text": _clip(t, 20000), "tone": tn, "lines": ln} for l, t, tn, ln in popup],
        # 另一件活动展开时，底部翻页行写的是这一件的 flip；没有它宿主写「还没有标签」。
        "flip": {"title": label, "subtitle": _clip(ws, 64), "phase": _clip(where or "没有改动", 64)},
        # 2026-09-21: hover-to-turn pages was awkward once the card could scroll; the three sections stack and the card scrolls
        # (the host keeps its paging for producers that want it).
        "body": _body(lc),
        "detail": _detail(summary, lc, bad, notices, overview, coverage, denials, overrides, readers),
        "events": [{"id": i, "type": ty, "at": _iso(_event_at(ty, i, when_lc, start, ended, now))} for i, ty in events],
    }
    ring = None
    if coverage is not NOT_GIVEN and coverage is not None:
        ring = _ring(coverage, name=ws, last_comment_at=start, last_change_at=when_lc)
        a["ring"] = ring
    if ring is not None and not ring.get("error") and not (problems or clock or flagged):
        # 胶囊写这一篇、等你几件（spec V2，第 4 步）：看过也留着——等你的事没裁完就一直在。
        # 警报（跑挂了、无出处、在跑的跑表）照旧用自己的胶囊。
        n_wait = ring["waiting"]
        tail = f" · 等你 {n_wait}" if n_wait else ""
        pill, tone = _fit(ws, RING_PILL_MAX - width(tail)) + tail, "white"
        a["pillUntilSeen"] = False
    within = _within(note)
    if within:
        a["within"] = within
    if pill:
        a["pill"] = {"pulse": False, "title": pill, "tint": tone}
    if clock and not problems:
        # 胶囊里是括号 + 跑表（分镜 ⑤⑥）
        a["pill"] = {"pulse": False, "clockSince": _iso(clock[1]), "tint": "white"}
    if a.get("pill") and a["pillUntilSeen"] and when is not None and not problems:
        # 看过之后胶囊不撤，只剩括号加「几时前」（作者 09-22；宿主 C3 的 pillSeen）
        a["pillSeen"] = {"pulse": False, "agoSince": _iso(when)}
    a = _prune(a)
    a["revision"] = identity(key)
    return [a]


def _event_at(ty, eid, when_lc, start, ended, now):
    """事件的时刻 = 事发时刻（设计 M5）：改动集 = 提交时刻，开工 = 消息时刻，落地 = 这一轮结束的时刻。"""
    if ty in ("changed", "drift") and when_lc is not None:
        return when_lc
    if ty == "started" and start is not None:
        return start
    if ty == "landed" and ended is not None:
        return ended
    return now


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
        same = old is not None and content_hash(old) == content_hash(a)
        if same and not stale:
            counts["unchanged"] += 1
            continue
        if same:
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
