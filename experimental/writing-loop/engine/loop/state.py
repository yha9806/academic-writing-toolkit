"""Paper state: whether the manuscript's claims stand, not whether the checks have run.

Coverage answers "has every check looked at the draft as it is now". A draft can be current everywhere and still
claim more than its evidence carries, or wait on an analysis nobody has run; a per-turn line that reports only
coverage then reads as "nothing is wrong". This module reads the workspace's claims ledger (config key `claims`)
and says, every turn and ahead of coverage:

- the verdict. 未就绪 while any claim is weak or unestablished, any sentence of the whole draft says a claim more
  strongly than the ledger allows, a wording the ledger requires is absent, the ledger cannot be read, or any work
  item is open. Otherwise 待作者终审: there is no green, because whether the paper is ready is the author's call.
- the stage the ledger names, and the next open work items in the ledger's own order. A work item can be an
  analysis or a source to find, not only writing: missing evidence is not fixed by rewording.

The ledger is Markdown, like the risk register:

    阶段：分析

    ## 主张 C1 <the claim>
    - 证据：<where the draft shows it>
    - 强度：强 | 中 | 弱 | 未立 | 推论 | 范围
    - 允许的说法：<the strongest wording the evidence carries>
    - 越界：<regex> ‖ <regex>        no sentence of the draft may match (case-insensitive)
    - 必须出现：<regex> ‖ <regex>    each must match at least one sentence
    - 缺：N1、N2

    ## 待做 N1 <what>
    - 类型：分析 | 出处 | 交付 | 写作 | 决定
    - 改变：C1
    - 状态：未做 | 在做 | 等作者 | 已做 YYYY-MM-DD <evidence> | 不做 YYYY-MM-DD <reason>

The whole draft is scanned, not what changed: a claim corrected in one section and left as it was in the abstract is
the failure this exists for. Whatever cannot be read is said and counts against readiness, never skipped.
"""
import re
from pathlib import Path

HEAD = re.compile(r"^##\s+(主张|待做)\s+(\S+)\s+(.+?)\s*$", re.M)
FIELD = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(证据|强度|允许的说法|越界|必须出现|缺|类型|改变|状态)(?:\*\*)?\s*[:：]\s*"
                   r"(?:\*\*)?\s*(.*?)\s*$", re.M)
STAGE = re.compile(r"^\s*(?:\*\*)?阶段(?:\*\*)?\s*[:：]\s*(.+?)\s*$", re.M)
STRENGTHS = ("强", "中", "弱", "未立", "推论", "范围")
WEAK = ("弱", "未立")
KINDS = ("分析", "出处", "交付", "写作", "决定")
OPEN = ("未做", "在做", "等作者")
OPEN_RX = re.compile(r"^(未做|在做|等作者)")
CLOSED = re.compile(r"^(已做|不做)\s+(\d{4}-\d{2}-\d{2})\s+(\S.*)$")
SEP = re.compile(r"\s*‖\s*")
ID_LIST = re.compile(r"[、,，;；\s]+")
CLAIM_NEEDS = ("证据", "强度", "允许的说法")
TODO_NEEDS = ("类型", "状态")

NOT_READY = "未就绪"
AUTHOR = "待作者终审"
NO_LEDGER = "没有主张清单"


def _ids(text):
    return [x for x in ID_LIST.split(text or "") if x]


def _patterns(text, where, problems):
    out = []
    for raw in SEP.split(text or ""):
        if not raw:
            continue
        try:
            out.append((raw, re.compile(raw, re.I)))
        except re.error as e:
            problems.append(f"{where} 的正则写错了（{e}）：{raw[:30]}")
    return out


def parse(raw):
    """(stage, claims, todo, problems) from the ledger's text. Items quoted in a fenced block are examples."""
    text = re.sub(r"(?ms)^```.*?^```", "", raw)
    problems, claims, todo = [], [], []
    m = STAGE.search(text)
    stage = m.group(1) if m else ""
    heads = list(HEAD.finditer(text))
    if not heads:
        problems.append("清单里没有一项（要 `## 主张 <id> <主张>` 或 `## 待做 <id> <事>`）")
    seen = set()
    for i, h in enumerate(heads):
        kind, iid, title = h.group(1), h.group(2), h.group(3)
        body = text[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(text)]
        fields = {}
        for f in FIELD.finditer(body):
            fields.setdefault(f.group(1), f.group(2))
        if iid in seen:
            problems.append(f"{kind} {iid} 重复了")
        seen.add(iid)
        where = f"{kind} {iid}"
        if kind == "主张":
            missing = [k for k in CLAIM_NEEDS if not fields.get(k)]
            strength = fields.get("强度", "")
            if missing:
                problems.append(f"{where} 缺「{'、'.join(missing)}」")
            if strength and strength not in STRENGTHS:
                problems.append(f"{where} 的强度读不懂：{strength[:12]}（要 {'/'.join(STRENGTHS)}）")
            claims.append({"id": iid, "title": title, "strength": strength if strength in STRENGTHS else "",
                           "evidence": fields.get("证据", ""), "allowed": fields.get("允许的说法", ""),
                           "over": _patterns(fields.get("越界"), where, problems),
                           "must": _patterns(fields.get("必须出现"), where, problems),
                           "needs": _ids(fields.get("缺"))})
        else:
            missing = [k for k in TODO_NEEDS if not fields.get(k)]
            if missing:
                problems.append(f"{where} 缺「{'、'.join(missing)}」")
            k = fields.get("类型", "")
            if k and k not in KINDS:
                problems.append(f"{where} 的类型读不懂：{k[:12]}（要 {'/'.join(KINDS)}）")
            status = fields.get("状态", "")
            c = CLOSED.match(status)
            if c:
                state, closed = c.group(1), True
            elif OPEN_RX.match(status):
                state, closed = OPEN_RX.match(status).group(1), False
            else:
                state, closed = "", False
                if status:
                    problems.append(f"{where} 的状态读不懂：{status[:20]}（已做、不做要写日期和证据或理由）")
            todo.append({"id": iid, "title": title, "kind": k if k in KINDS else "", "state": state,
                         "closed": closed, "status": status, "changes": _ids(fields.get("改变"))})
    known_todo, known_claims = {t["id"] for t in todo}, {c["id"] for c in claims}
    for c in claims:
        for n in c["needs"]:
            if n not in known_todo:
                problems.append(f"主张 {c['id']} 缺的 {n} 不在待做里")
    for t in todo:
        for n in t["changes"]:
            if n not in known_claims:
                problems.append(f"待做 {t['id']} 改变的 {n} 不是清单里的主张")
    return stage, claims, todo, problems


def scan(claims, sentences):
    """Sentences anywhere in the draft that say a claim more strongly than allowed, and required wordings absent."""
    over, absent = [], []
    for c in claims:
        for raw, rx in c["over"]:
            labels = [s.get("label") or s.get("sid") or "?" for s in sentences if rx.search(s.get("text") or "")]
            if labels:
                over.append({"claim": c["id"], "pattern": raw, "labels": labels})
        for raw, rx in c["must"]:
            if not any(rx.search(s.get("text") or "") for s in sentences):
                absent.append({"claim": c["id"], "pattern": raw})
    return over, absent


def judge(st):
    """The verdict, what stands in its way, and the next open items. Never green: the best is 待作者终审."""
    weak = [c for c in st["claims"] if c["strength"] in WEAK or not c["strength"]]
    open_ = [t for t in st["todo"] if not t["closed"]]
    labels = sorted({lab for o in st["over"] for lab in o["labels"]})
    blockers = []
    if st["problems"]:
        blockers.append(f"清单读不懂 {len(st['problems'])} 处")
    if weak:
        blockers.append("没立住 " + "、".join(c["id"] for c in weak))
    if labels:
        blockers.append(f"越界 {len(labels)} 句")
    if st["absent"]:
        blockers.append("缺该有的说法 " + "、".join(sorted({a["claim"] for a in st["absent"]})))
    if open_:
        blockers.append(f"待做开着 {len(open_)}")
    st.update(weak=[c["id"] for c in weak], open=[t["id"] for t in open_], over_labels=labels, blockers=blockers,
              verdict=NOT_READY if blockers else AUTHOR, next=[t["id"] for t in open_[:3]])
    return st


def compute(cfg, ws):
    """The state of this workspace's paper. Reads the ledger and the sentence index; runs nothing."""
    path = cfg.get("claims")
    if not path:
        return {"configured": False, "verdict": NO_LEDGER}
    p = Path(path).expanduser()
    st = {"configured": True, "path": str(p), "stage": "", "claims": [], "todo": [], "problems": [], "over": [],
          "absent": [], "index_head": None}
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        st["problems"].append(f"主张清单读不到：{p}")
        return judge(st)
    st["stage"], st["claims"], st["todo"], st["problems"] = parse(raw)
    from . import coverage as V
    sentences, st["index_head"] = V.current_sentences(ws)
    if sentences is None:
        st["problems"].append("句子索引没建（loop update），整篇的越界扫描没做")
    else:
        st["over"], st["absent"] = scan(st["claims"], sentences)
    return judge(st)


def _count(st):
    c = {}
    for x in st["claims"]:
        k = x["strength"] or "读不懂"
        c[k] = c.get(k, 0) + 1
    return "、".join(f"{k} {c[k]}" for k in STRENGTHS + ("读不懂",) if c.get(k))


def _todo_name(st, iid):
    t = next(x for x in st["todo"] if x["id"] == iid)
    title = t["title"] if len(t["title"]) <= 14 else t["title"][:14] + "…"
    return f"{iid} {title}" + ("（等作者）" if t["state"] == "等作者" else "")


def line(st):
    """The per-turn line. Said every turn, whatever the checks say."""
    if not st.get("configured"):
        return ("论文状态：没登记主张清单（配置的 claims）——循环只知道检查跑没跑，"
                "不知道主张立没立住、还缺哪个分析")
    head = f"论文状态：{st['verdict']}" + (f"（阶段：{st['stage']}）" if st.get("stage") else "")
    bits = []
    if st["claims"]:
        bits.append(f"主张 {len(st['claims'])}：{_count(st)}")
    bits += [b for b in st["blockers"] if not b.startswith("待做开着")]
    open_ = [t for t in st["todo"] if not t["closed"]]
    if open_:
        kinds = {}
        for t in open_:
            kinds[t["kind"] or "?"] = kinds.get(t["kind"] or "?", 0) + 1
        bits.append(f"待做开着 {len(open_)}（" + "、".join(f"{k} {v}" for k, v in kinds.items()) + "）")
    if st["next"]:
        bits.append("下一步 " + "、".join(_todo_name(st, i) for i in st["next"]))
    if st["verdict"] == AUTHOR:
        bits.append("能不能投由作者定")
    return head + "——" + "；".join(bits)


def table(st):
    """The terminal view: every claim, every open item, every sentence over the line."""
    if not st.get("configured"):
        return line(st)
    out = [line(st), f"清单：{st['path']}" + (f" · 索引 {str(st['index_head'])[:7]}" if st.get("index_head") else "")]
    for p in st["problems"]:
        out.append(f"  读不懂  {p}")
    for c in st["claims"]:
        out.append(f"  主张 {c['id']}  {c['strength'] or '?'}  {c['title']}")
        out.append(f"      允许的说法：{c['allowed'] or '—'}")
        for o in (x for x in st["over"] if x["claim"] == c["id"]):
            out.append(f"      越界「{o['pattern']}」：{'、'.join(o['labels'])}")
        for a in (x for x in st["absent"] if x["claim"] == c["id"]):
            out.append(f"      缺「{a['pattern']}」：整篇没有一句")
        if c["needs"]:
            out.append(f"      缺：{'、'.join(c['needs'])}")
    for t in st["todo"]:
        out.append(f"  待做 {t['id']}  {t['kind'] or '?'}  {t['status'] or '?'}  {t['title']}")
    return "\n".join(out)


def cell(st):
    """The overview's first 待办 cell: the paper, before the checks."""
    if not st.get("configured"):
        return {"title": "论文", "text": "没登记主张清单", "value": "没登记", "tone": "orange",
                "sub": "所以只知道检查跑没跑，不知道主张立没立住"}
    text = "；".join(st["blockers"]) or "没有挡着的"
    sub = ("下一步 " + "、".join(st["next"])) if st["next"] else "能不能投由作者定"
    return {"title": "论文", "text": text[:64], "value": st["verdict"], "sub": sub[:120],
            "tone": "orange" if st["verdict"] == NOT_READY else "white"}
