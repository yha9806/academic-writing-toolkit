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
        return "追到你的话"
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
    the changed words); whole sentences stay in the panel. Then 你说 (only if traced) and Claude 读成 (only if written).
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
    if lc["traced"] and lc["verbatim"]:
        pages.append({"kind": "section", "title": "你说", "items": [{"kind": "para", "tone": "white85", "text": _clip(lc["verbatim"], 140)}]})
    if lc["reading"]:
        pages.append({"kind": "section", "title": "Claude 读成", "items": [{"kind": "para", "tone": "white85", "text": _clip(lc["reading"], 140)}]})
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
            out.append({"id": h["id"], "tag": label or where or "改了", "badge": f"{h['n']} 句", "duration": h["id"][:7],
                        "at": _iso(h["time"]) if h["time"] else None, "expandable": True,
                        "lines": lines, "rows": _rows(h, names) or None, "sections": secs([h["id"]])})
            i += 1
            continue
        kind_ = origin(h)
        run = []
        while i < len(hist) and not hist[i]["traced"] and origin(hist[i]) == kind_ and len(run) < FOLD_MAX:
            run.append(hist[i]); i += 1
        out.append({"id": f"fold-{run[0]['id']}", "tag": f"{FOLD_WORD[kind_]} ×{len(run)}", "badge": f"{sum(r['n'] for r in run)} 句",
                    "at": _iso(run[0]["time"]) if run[0]["time"] else None, "expandable": True, "lines": [],
                    "rows": [{"label": r["id"][:7], "where": _clip(f"{r['n']} 句 · {_hm(r['time'])}", 256), "copy": r["id"],
                              "new": _clip(detex(r.get("subject") or ""), 200) or "（没有提交信息）"} for r in run],
                    "sections": secs([r["id"] for r in run])})
    return out


def _detail(summary, lc, bad, notices, overview=None, coverage=NOT_GIVEN):
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
        "historyNote": _clip(f"有空再看：拦下 {len(notices)} 次 · 缺依据 {bad} 条", 64),
        # 进度按改动集（作者 09-21），三色：追到靛蓝、对不上橙、别处灰。
        "strip": {"title": "改动集 · 旧 → 新",
                  "cells": [cell[k] for k in reversed(kinds)],
                  "legend": [{"name": "追到", "count": traced, "swatch": IDENTITY},
                             {"name": "对不上", "count": kinds.count("unmatched"), "swatch": UNMATCHED},
                             {"name": "别处", "count": kinds.count("elsewhere"), "swatch": UNTRACED}]},
        "stats": [
            {"label": "追到", "value": f"{traced}/{len(hist)}"},
            {"label": "拦下", "value": str(len(notices)), "tone": "orange" if notices else None},
            {"label": "缺依据", "value": str(bad), "tone": "orange" if bad else None},
        ],
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
        # 有总览时数据条换成总览的五格（分镜 ㊾）：句 / 版 / 这一段改动集 / 缺依据 / 标题页待填。
        if overview.get("stats"):
            d["stats"] = overview["stats"]
    if coverage is not NOT_GIVEN:
        # 检查覆盖（spec 2026-09-21 D4）：不在当前稿上的检查有几项。没算过也要说，不能留空当作都查过了。
        d["stats"] = (list(d["stats"]) + _coverage_stats(coverage))[:8]
    return d



def _coverage_stats(summary):
    """检查待办 = what this draft's work can act on (a summary for an older HEAD counts); AWT 读不了 = checks the
    toolkit has that cannot read this draft. Neither is ever left out as a way of saying zero."""
    from . import coverage as V
    if summary is None:
        return [{"label": "检查", "value": "没算过", "tone": "orange"}]
    try:
        n = len(V.attention(summary)) + (1 if (summary.get("target") or {}).get("problems") else 0)
        gap = len(V.gaps(summary))
    except (KeyError, TypeError, AttributeError):
        return [{"label": "检查", "value": "读不出", "tone": "orange"}]
    out = [{"label": "检查待办", "value": str(n), "tone": "orange" if n else None}]
    if gap:
        out.append({"label": "AWT 读不了", "value": str(gap)})
    wv = len(V.waived(summary))
    if wv:
        out.append({"label": "豁免", "value": str(wv)})
    return out


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


def build(summary, *, now, problems=(), notices=(), overview=None, coverage=NOT_GIVEN, turn=None, readers=None,
          built_at=None):
    """从索引摘要（`index.summarize`）生成活动：一个稿件一个，永远只有一个。
    `problems` 是引擎自己的毛病；`notices` 是该知道但不是故障的事（被拦下的写入）。
    `turn` 是最近一轮（`turns.current`），`readers` 是最近一次读者组（`turns.readers_run`），`built_at` 是索引最近一次建成的时刻。
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
    caught_up = ended is not None and built_at is not None and built_at >= ended
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
        popup = [("你说", lc["verbatim"] or "（没有原话）", "primary", 1),
                 ("改了", sections(lc), "primary", 1)]
        if lc["reading"]:
            popup.append(("读成", lc["reading"], "secondary", 2))
        events.append((f"changed:{lc['id']}", "changed"))
        if landed:
            # 落地弹卡（分镜 ⑤⑧）：两行，改了什么（几句 · 追得牢不牢 · 哪几节）/ 检查此刻的现状。身份仍是这个改动集（M2）。
            how = STRENGTH.get(lc.get("strength"))
            popup = [("改了", " · ".join(x for x in (f"{n} 句", how, sections(lc)) if x), "primary", 1),
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
        "detail": _detail(summary, lc, bad, notices, overview, coverage),
        "events": [{"id": i, "type": ty, "at": _iso(_event_at(ty, i, when_lc, start, ended, now))} for i, ty in events],
    }
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
