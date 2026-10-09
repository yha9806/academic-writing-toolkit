"""Paper state: whether the manuscript's claims stand, not whether the checks have run.

Coverage answers "has every check looked at the draft as it is now". A draft can be current everywhere and still
claim more than its evidence carries, or wait on an analysis nobody has run; a per-turn line that reports only
coverage then reads as "nothing is wrong". This module reads the workspace's claims ledger (config key `claims`)
and says, every turn and ahead of coverage:

- the verdict. 未就绪 while any claim is weak or unestablished, any sentence of the whole draft says a claim more
  strongly than the ledger allows, a wording the ledger requires is absent or said more often than it allows, the
  ledger cannot be read, any work
  item is open, or a step of the intent card's story page has no author's approval on record. 已投稿 once the stage
  names a submission, with whatever still stands in the way listed for the revision. Otherwise 待作者终审: there is no green, because whether the paper is ready is the author's call.
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
    - 必须出现：<regex> @ A, I1      ... in each named place (a label prefix: A the abstract, I1 its first paragraph)
    - 至多：<regex> ‖ <regex> @ 2    at most 2 sentences of the draft may match any of them (one cap per claim)
    - 至多：<regex> @ 1 A, I1        ... counted over the named places together
    - 承载：<regex> ‖ <regex>        the sentences that state the claim, listed for a grill whether changed or not
    - 限定词：<regex> ‖ <regex>      each must match every sentence 承载 finds: the allowed wording's qualifiers
    - 依据：<test or run>            required when the claim is a universal negation (no / none / never / 没有 ...)
    - 缺：N1、N2

    ## 待做 N1 <what>
    - 类型：分析 | 出处 | 交付 | 写作 | 决定
    - 节：W、sections/02_x.tex        a 写作 item with sections is a part of a part-by-part rewrite (loop/parts.py)
    - 讲法：<story page path>         optional: the plain-language story the author approved for the part
    - 改变：C1
    - 状态：未做 | 在做 | 等作者 | 已做 YYYY-MM-DD <evidence> | 不做 YYYY-MM-DD <reason>

    全称量词查：A、I1                 where universal quantifiers are held to a set (default: the abstract, A)
    全称量词不查：<regex> ‖ <regex>   quantified phrases a person has read and let stand (each query ...)

    ## 集合 S1 <what the set is>
    - 名词：<regex>                   the noun a quantifier ranges over (encoders?)
    - 定义：<regex>                   the sentence that says what is in the set
    - 大小：<n>                       shown, not checked
    - 集合外：<regex> ‖ <regex>       names of systems outside the set: a sentence using the noun with one is listed

The whole draft is scanned, not what changed: a claim corrected in one section and left as it was in the abstract is
the failure this exists for. Whatever cannot be read is said and counts against readiness, never skipped.
"""
import json
import os
import re
from pathlib import Path

HEAD = re.compile(r"^##\s+(主张|待做|集合)\s+(\S+)\s+(.+?)\s*$", re.M)
FIELD = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(证据|强度|允许的说法|越界|必须出现|至多|承载|限定词|依据|缺|类型|改变|状态|名词|定义|大小|集合外|节|讲法)(?:\*\*)?\s*[:：]\s*"
                   r"(?:\*\*)?\s*(.*?)\s*$", re.M)
STAGE = re.compile(r"^\s*(?:\*\*)?阶段(?:\*\*)?\s*[:：]\s*(.+?)\s*$", re.M)
SCOPE_AT = re.compile(r"^\s*(?:\*\*)?全称量词查(?:\*\*)?\s*[:：]\s*(.+?)\s*$", re.M)
SCOPE_SKIP = re.compile(r"^\s*(?:\*\*)?全称量词不查(?:\*\*)?\s*[:：]\s*(.+?)\s*$", re.M)
SET_NEEDS = ("名词", "定义")
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

# A claim stated as a universal negation: it needs the test that could have found the thing (spec 2026-09-25 §4.4).
NEGATION = re.compile(r"\b(no|none|never|nothing|neither|nor|zero|without|not)\b|没有|从未|无一|都不|均不|不存在|并未|未能", re.I)
# "A significant, B not" read as a difference between A and B.
SIG_DIFF = re.compile(r"(?<!不)(显著|significant)[^。；;.\n]{0,60}(不显著|not significant|n\.s\.)|"
                      r"(不显著|not significant|n\.s\.)[^。；;.\n]{0,60}(?<!不)(显著|significant)", re.I)
# Method sentences that close off an alternative, and sentences that name a cue left open.
CLOSING = re.compile(r"\bonly (?:the )?\w+(?: \w+)? differs?\b|\bno (?:other |non-semantic |remaining )?cues? (?:is |are )?"
                     r"(?:left|remains?)\b|\bnothing else (?:changes|differs)\b|\b(?:is|are) otherwise identical\b|"
                     r"\ball else (?:being )?equal\b|只有.{0,12}不同|没有.{0,8}线索(?:剩下|留下)|其余(?:都)?相同", re.I)
REMAINING = re.compile(r"\b(cues?|shortcuts?|confound\w*|not control\w*|uncontrolled|leak\w*|residual)\b|线索|捷径|混淆|未控制|没有控制", re.I)
PLACE_SEP = re.compile(r"\s+@\s+")
# A universal quantifier and the words after it (09-28: an abstract said "every" of a kind of system; which systems
# was said only far into the introduction, and the body used the same word for systems added later; an outside review
# read it the wide way, while the reader panel, the changed-sentence check and the ledger had all passed it).
QUANT = re.compile(r"\b(every|all|each|none of|no)\s+((?:[\w'-]+\s+){0,3}[\w'-]+)|"
                   r"(所有|全部|任何|每一?[个位项种篇张条组]?)(\S{1,8})", re.I)
QUANT_LEAD = {"of", "the", "our", "its", "their", "these", "those", "his", "her", "this", "that"}
NUMERAL = re.compile(r"^(\d[\d,.]*|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
                     r"fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|"
                     r"ninety|hundred|[一二两三四五六七八九十百千0-9])", re.I)
DEFAULT_SCOPE_AT = ["A"]

NOT_READY = "未就绪"
AUTHOR = "待作者终审"
SUBMITTED = "已投稿"
# 10-01: the author submitted and the ledger's stage said so, yet the line still read 待作者终审 and asked whether to
# submit. A stage that names a submission makes the verdict 已投稿; what still stands in the way stays listed.
SUBMITTED_STAGE = re.compile(r"已投稿|已提交|审稿中|(?<!not )(?<!yet )\bsubmitted\b|under review", re.I)
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


def in_place(label, place):
    """Whether a sentence label lies in a place: letters name a section prefix (A: A01, A02 ...), letters and digits a
    paragraph (I1: I1.1, I1.2 ..., not I10.1)."""
    label, place = str(label or ""), str(place or "")
    if not place or not label.startswith(place):
        return False
    rest = label[len(place):]
    return rest == "" or (rest[0] == "." if place[-1].isdigit() else rest[0].isdigit())


def _must(text, where, problems):
    """Required wordings, and the places each must be found in ({} when anywhere will do)."""
    parts = PLACE_SEP.split(text or "", maxsplit=1)
    pats = _patterns(parts[0], where, problems)
    places = [x for x in ID_LIST.split(parts[1]) if x] if len(parts) > 1 else []
    return pats, ({raw: places for raw, _ in pats} if places else {})


def _at_most(text, where, problems):
    """A cap on how often the draft says something: {patterns, limit, places}, or None when there is none."""
    if not text:
        return None
    parts = PLACE_SEP.split(text, maxsplit=1)
    rest = _ids(parts[1]) if len(parts) > 1 else []
    if not rest or not rest[0].isdecimal():
        problems.append(f"{where} 的至多要写成「<说法> ‖ <说法> @ N」或「… @ N A, I1」，N 是句数：{text[:30]}")
        return None
    pats = _patterns(parts[0], where, problems)
    return {"patterns": pats, "limit": int(rest[0]), "places": rest[1:]} if pats else None


def parse(raw):
    """(stage, claims, todo, problems) from the ledger's text. Items quoted in a fenced block are examples."""
    d = read_ledger(raw)
    return d["stage"], d["claims"], d["todo"], d["problems"]


def read_ledger(raw):
    """The ledger as a dict: stage, claims, todo, sets, where quantifiers are held to a set (scope_at), the phrases let
    stand (scope_skip) and problems."""
    text = re.sub(r"(?ms)^```.*?^```", "", raw)
    problems, claims, todo, sets = [], [], [], []
    m = STAGE.search(text)
    stage = m.group(1) if m else ""
    m = SCOPE_AT.search(text)
    scope_at = _ids(m.group(1)) if m else list(DEFAULT_SCOPE_AT)
    m = SCOPE_SKIP.search(text)
    scope_skip = _patterns(m.group(1), "全称量词不查", problems) if m else []
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
        if kind == "集合":
            missing = [k for k in SET_NEEDS if not fields.get(k)]
            if missing:
                problems.append(f"{where} 缺「{'、'.join(missing)}」")
            nouns = _patterns(fields.get("名词"), where, problems)
            defs = _patterns(fields.get("定义"), where, problems)
            sets.append({"id": iid, "title": title, "noun": nouns, "define": defs, "size": fields.get("大小", ""),
                         "outside": _patterns(fields.get("集合外"), where, problems)})
        elif kind == "主张":
            must, places = _must(fields.get("必须出现"), where, problems)
            missing = [k for k in CLAIM_NEEDS if not fields.get(k)]
            strength = fields.get("强度", "")
            if missing:
                problems.append(f"{where} 缺「{'、'.join(missing)}」")
            if strength and strength not in STRENGTHS:
                problems.append(f"{where} 的强度读不懂：{strength[:12]}（要 {'/'.join(STRENGTHS)}）")
            claims.append({"id": iid, "title": title, "strength": strength if strength in STRENGTHS else "",
                           "evidence": fields.get("证据", ""), "allowed": fields.get("允许的说法", ""),
                           "over": _patterns(fields.get("越界"), where, problems),
                           "must": must, "places": places, "at_most": _at_most(fields.get("至多"), where, problems),
                           "carry": _patterns(fields.get("承载"), where, problems),
                           "qualify": _patterns(fields.get("限定词"), where, problems),
                           "basis": fields.get("依据", ""), "needs": _ids(fields.get("缺"))})
            if claims[-1]["qualify"] and not fields.get("承载"):
                problems.append(f"{where} 写了限定词没写承载：限定词查的是承载句，没有承载就一句也查不到")
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
                         "closed": closed, "status": status, "changes": _ids(fields.get("改变")),
                         # a part of a part-by-part rewrite (spec 2026-09-29-part-by-part-revision): its sections, by
                         # label prefix (W, I2) or file, and the story page the author approved for it
                         "sections": _ids(fields.get("节")), "story": fields.get("讲法", "")})
    known_todo, known_claims = {t["id"] for t in todo}, {c["id"] for c in claims}
    for c in claims:
        for n in c["needs"]:
            if n not in known_todo:
                problems.append(f"主张 {c['id']} 缺的 {n} 不在待做里")
    for t in todo:
        for n in t["changes"]:
            if n not in known_claims:
                problems.append(f"待做 {t['id']} 改变的 {n} 不是清单里的主张")
    return {"stage": stage, "claims": claims, "todo": todo, "sets": sets, "scope_at": scope_at,
            "scope_skip": scope_skip, "problems": problems}


EXTRA_SCAN_VERSION = 1  # bump when extraction changes, so a cached scan is not reused


def _listed(cfg, key, problems):
    """A config list of paths, or [] with a problem said: a bare string would be read one character per path."""
    from . import catalogue as K
    v = K.get(cfg, key)
    if v is None:
        return []
    if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
        problems.append(f"{key} 要写成路径的列表，现在是 {type(v).__name__}")
        return []
    return v


def extra_sentences(cfg, head, problems, ws=None):
    """Text submitted with the draft but not tracked sentence by sentence (inputs.also_checked, e.g. a supplement) and
    text inside figure and table sources (inputs.also_scanned: paths, directories or globs where * stays within a
    path segment and ** spans them), read at the index's commit. Files that are already draft files are left to the
    index. Scanned for wordings a claim forbids; never used to satisfy a required wording. Every listed entry that
    yields nothing is said. Read through one cat-file process and cached by commit and list, since the per-turn line
    computes this."""
    from . import coverage as V
    from . import gitio
    from . import text as T
    listed = _listed(cfg, "inputs.also_checked", problems) + _listed(cfg, "inputs.also_scanned", problems)
    if not listed or not head:
        return []
    cache = Path(ws) / "cache" / "coverage" / "extra_scan.json" if ws else None
    key = json.dumps([EXTRA_SCAN_VERSION, head, listed, cfg["draft"].get("glob")], ensure_ascii=False)
    if cache is not None:
        try:
            got = json.loads(cache.read_text(encoding="utf-8"))
            if isinstance(got, dict) and got.get("key") == key and isinstance(got.get("sentences"), list) \
                    and isinstance(got.get("problems"), list):
                problems.extend(got["problems"])
                return got["sentences"]
        except (OSError, ValueError):
            pass  # an unreadable cache is rebuilt, never trusted
    repo = cfg["repo"]
    files = set(gitio.ls_tree(repo, head, "."))
    drafts = set(V.draft_files(cfg, head))
    found, said = [], []
    for spec, names in T.resolve_listed(listed, files):
        names = [n for n in names if n not in drafts]
        if not names:
            said.append(f"额外扫描的 {spec} 在 {head[:7]} 上没有可读的文件（不在仓里、是空目录，或只有正文文件）")
        found += [n for n in names if n not in found]
    out = []
    with gitio.batch(repo):
        for path in found:
            raw = gitio.show(repo, head, path)
            if raw is None:
                said.append(f"额外扫描的文件在 {head[:7]} 上读不出：{path}")
                continue
            plain = T.tex_plain(raw) if path.endswith(".tex") else re.sub(r"\s+", " ", raw)
            out += [{"label": f"{path}#{i}", "text": s} for i, s in enumerate(T.split_sentences(plain), 1)]
    problems.extend(said)
    if cache is not None:
        try:
            cache.parent.mkdir(parents=True, exist_ok=True)
            tmp = cache.with_name(f".extra_scan.{os.getpid()}.tmp")
            tmp.write_text(json.dumps({"key": key, "problems": said, "sentences": out}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(cache)
        except OSError:
            pass
    return out


def scan(claims, sentences, extra=()):
    """Sentences anywhere in the draft that say a claim more strongly than allowed, and required wordings absent.
    extra: text outside the index (supplement, figure and table sources), searched for forbidden wordings only."""
    over, absent = [], []
    for c in claims:
        for raw, rx in c["over"]:
            labels = [s.get("label") or s.get("sid") or "?" for s in list(sentences) + list(extra)
                      if rx.search(s.get("text") or "")]
            if labels:
                over.append({"claim": c["id"], "pattern": raw, "labels": labels})
        for raw, rx in c["must"]:
            places = (c.get("places") or {}).get(raw)
            if not places:
                if not any(rx.search(s.get("text") or "") for s in sentences):
                    absent.append({"claim": c["id"], "pattern": raw})
                continue
            for place in places:
                if not any(rx.search(s.get("text") or "") for s in sentences if in_place(s.get("label"), place)):
                    absent.append({"claim": c["id"], "pattern": raw, "place": place})
    return over, absent


def last_seen(claims, absent, earlier):
    """Each required wording absent from the current draft that an earlier indexed version still said (in the place the
    ledger names, when it names one) gets that version as a["last_seen"] = {"sha", "subject"}, the latest such version.
    The draft may have been reworded on purpose and the ledger not; the commit tells the author where to look. A
    wording no version said gets nothing: the ledger then asks for something not yet written."""
    rx_of = {(c["id"], raw): rx for c in claims for raw, rx in c["must"]}
    for a in absent:
        rx = rx_of.get((a["claim"], a["pattern"]))
        if rx is None:
            continue
        place = a.get("place")
        for v in reversed(earlier):
            if any(rx.search(s.get("text") or "") for s in v.get("sentences") or []
                   if not place or in_place(s.get("label"), place)):
                a["last_seen"] = {"sha": v.get("sha") or "", "subject": v.get("subject") or ""}
                break


def said(claims, sentences):
    """How often each capped wording is said (probe-growth #4: one limitation restated in six sentences, each worded
    differently, and a ledger could require a wording or forbid it but not cap it). Counts sentences of the draft, not
    matches: a sentence that says it twice counts once. Supplement and figure sources are not counted. Only the
    wordings listed are seen; a seventh paraphrase the ledger does not name is not."""
    out = []
    for c in claims:
        m = c.get("at_most")
        if not m:
            continue
        labels = [_label(s) for s in sentences
                  if (not m["places"] or any(in_place(s.get("label"), p) for p in m["places"]))
                  and any(rx.search(s.get("text") or "") for _, rx in m["patterns"])]
        out.append({"claim": c["id"], "limit": m["limit"], "places": m["places"], "labels": labels})
    return out


def question(claims, sentences, extra=()):
    """What the ledger itself is asked (spec 2026-09-25 §4.4): the sentences that carry each claim, universal
    negations with no named test, evidence notes that read one significant and one not as a difference, and method
    sentences that close off an alternative beside the sentences that name a cue left open. extra (figure and table
    text, the supplement) is read for method sentences too: a figure said no cue was left while the text named one."""
    label = lambda s: s.get("label") or s.get("sid") or "?"
    carrying = {c["id"]: [label(s) for s in sentences if any(rx.search(s.get("text") or "") for _, rx in c["carry"])]
                for c in claims if c.get("carry")}
    negations = [c["id"] for c in claims if NEGATION.search(c.get("title") or "") and not (c.get("basis") or "").strip()]
    warnings = [{"claim": c["id"], "why": "一个显著一个不显著被读成两者不同"} for c in claims
                if SIG_DIFF.search((c.get("evidence") or "") + " " + (c.get("allowed") or ""))]
    everything = list(sentences) + list(extra)
    closing = [label(s) for s in everything if CLOSING.search(s.get("text") or "")]
    remaining = [label(s) for s in everything if label(s) not in closing and REMAINING.search(s.get("text") or "")]
    return {"carrying": carrying, "negations": negations, "warnings": warnings, "closing": closing, "remaining": remaining}


def _label(s):
    return s.get("label") or s.get("sid") or "?"


def _quantified(text):
    """(the quantified phrase, the words it ranges over with articles dropped) for each universal quantifier."""
    out = []
    for m in QUANT.finditer(text or ""):
        if m.group(1):
            words = m.group(2).split()
            while words and words[0].lower() in QUANT_LEAD:
                words = words[1:]
            out.append((m.group(0), " ".join(words[:3])))
        else:
            out.append((m.group(0), m.group(4)))
    return out


def scope(sets, places, skip, sentences, extra=()):
    """Universal quantifiers held to a set (FOR-AWT encoder-scope 1). In the places named, every / all / each / no
    + noun either says its size where it stands (all five systems) or ranges over a set in the ledger whose defining
    sentence comes first; a set's noun used anywhere with a name outside the set is listed for a person to read."""
    unscoped, early, undefined, outside = [], [], [], []
    first = {}
    for x in sets:
        first[x["id"]] = next((i for i, s in enumerate(sentences)
                               if any(rx.search(s.get("text") or "") for _, rx in x["define"])), None)
        if x["define"] and first[x["id"]] is None:
            undefined.append(x["id"])
        if x["outside"]:
            labels = [_label(s) for s in list(sentences) + list(extra)
                      if any(rx.search(s.get("text") or "") for _, rx in x["noun"])
                      and any(rx.search(s.get("text") or "") for _, rx in x["outside"])]
            if labels:
                outside.append({"set": x["id"], "labels": labels})
    for i, s in enumerate(sentences):
        if not any(in_place(_label(s), p) for p in places):
            continue
        for phrase, rest in _quantified(s.get("text")):
            if not rest or NUMERAL.match(rest) or any(rx.search(phrase) for _, rx in skip):
                continue
            x = next((x for x in sets if any(rx.search(rest) for _, rx in x["noun"])), None)
            if x is None:
                unscoped.append({"label": _label(s), "phrase": phrase})
            elif first[x["id"]] is not None and first[x["id"]] > i:
                early.append({"set": x["id"], "label": _label(s), "phrase": phrase,
                              "defined": _label(sentences[first[x["id"]]])})
    return {"unscoped": unscoped, "early": early, "undefined": undefined, "outside": outside}


def qualify(claims, sentences):
    """Sentences that carry a claim without a qualifier its allowed wording needs (FOR-AWT encoder-scope 2: the
    ledger's allowed wording named two qualifiers; a discussion sentence had neither and passed, because only 越界
    and 必须出现 were patterns)."""
    out = []
    for c in claims:
        if not c.get("qualify") or not c.get("carry"):
            continue
        for raw, rx in c["qualify"]:
            labels = [_label(s) for s in sentences if any(r.search(s.get("text") or "") for _, r in c["carry"])
                      and not rx.search(s.get("text") or "")]
            if labels:
                out.append({"claim": c["id"], "pattern": raw, "labels": labels})
    return out


def gates(cfg, st):
    """Required gates (config state.required_gates: words a gate's title must hold) not yet decided in the risk
    register. A person closes them; the loop only reports them open."""
    wanted = list(((cfg.get("state") or {}).get("required_gates")) or [])
    if not wanted:
        return []
    from . import targets as TG
    reg = TG.risks(cfg) or {"decided": [], "open": []}
    done = [d.get("title") or "" for d in reg.get("decided") or []]
    return [w for w in wanted if not any(w in t for t in done)]


# The story page (spec 2026-09-28-story-layer S3): the plain-language order of the paper, settled with the author before
# sentence work, in the intent card's 讲法页 section. Its steps are the first run of numbered items; a later numbered
# list (a history kept below the page) is not the page.
STORY_HEAD = re.compile(r"^(#{2,3})\s+.*(?:讲法页|讲法顺序|[Ss]tory page)")
STORY_STEP = re.compile(r"^\s{0,3}\d+[.、．]\s+\S")
FULL_UUID = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b")


def story_page(cfg):
    """{found, path, steps, approved, unapproved: [step numbers]} for the intent card's story page, or None when the
    workspace names no readable intent card. A step is approved when an author's message it names by uuid is in this
    workspace's transcripts, or, naming none, when the page's own approval (a uuid above the first step) is; a step
    marked ◌ is not approved whatever the page says."""
    card = (cfg.get("target") or {}).get("intent_card")
    if not card:
        return None
    p = Path(card).expanduser()
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None   # a missing card is said by the target check
    out = {"found": False, "path": str(p), "steps": 0, "approved": 0, "unapproved": []}
    start = next((i for i, ln in enumerate(lines) if STORY_HEAD.match(ln)), None)
    if start is None:
        return out
    out["found"] = True
    level = len(STORY_HEAD.match(lines[start]).group(1))
    head, steps = [lines[start]], []
    for ln in lines[start + 1:]:
        if re.match(r"^#{1,%d}\s" % level, ln):
            break
        if STORY_STEP.match(ln):
            steps.append([ln])
        elif steps and ln.strip() and ln[:1].isspace():
            steps[-1].append(ln)        # a step's continuation line
        elif steps:
            break                       # the run of steps is over
        else:
            head.append(ln)
    from . import targets as TG
    page = [u for u in FULL_UUID.findall("\n".join(head))]
    page_ok = any(TG._approval_in_transcripts(cfg, u) for u in page)
    for n, step in enumerate(steps, 1):
        text = "\n".join(step)
        own = FULL_UUID.findall(text)
        ok = "◌" not in text and (any(TG._approval_in_transcripts(cfg, u) for u in own) if own else page_ok)
        out["approved"] += ok
        if not ok:
            out["unapproved"].append(n)
    out["steps"] = len(steps)
    return out


def judge(st):
    """The verdict, what stands in its way, and the next open items. Never green: the best is 待作者终审."""
    weak = [c for c in st["claims"] if c["strength"] in WEAK or not c["strength"]]
    open_ = [t for t in st["todo"] if not t["closed"]]
    labels = sorted({lab for o in st["over"] for lab in o["labels"]})
    blockers = []
    if st["problems"]:
        blockers.append(f"清单读不懂 {len(st['problems'])} 处")
    if st.get("scan_problems"):
        blockers.append(f"额外扫描读不到 {len(st['scan_problems'])} 处")
    if weak:
        blockers.append("没立住 " + "、".join(c["id"] for c in weak))
    if labels:
        blockers.append(f"越界 {len(labels)} 句")
    if st["absent"]:
        blockers.append("缺该有的说法 " + "、".join(sorted({a["claim"] for a in st["absent"]})))
    too_many = sorted({x["claim"] for x in st.get("at_most") or [] if len(x["labels"]) > x["limit"]})
    if too_many:
        blockers.append("说太多遍 " + "、".join(too_many))
    if st.get("unqualified"):
        blockers.append("承载句缺限定词 " + "、".join(sorted({u["claim"] for u in st["unqualified"]})))
    if st.get("unscoped"):
        blockers.append(f"全称量词没对集合 {len(st['unscoped'])} 处")
    if st.get("early"):
        blockers.append("集合在用之后才定义 " + "、".join(sorted({e["set"] for e in st["early"]})))
    if st.get("undefined"):
        blockers.append("集合的定义句找不到 " + "、".join(st["undefined"]))
    if st.get("negations"):
        blockers.append("全称否定没写依据 " + "、".join(st["negations"]))
    if st.get("gates_open"):
        blockers.append("门没关 " + "、".join(st["gates_open"]))
    sp = st.get("story")
    if sp and not sp["found"]:
        # 10-07: said and not blocking, a missing page let an abstract whose order nothing could check reach the
        # author with every reader point carried. A missing page is at least as open as an unapproved step.
        blockers.append("意图卡里没有讲法页")
    elif sp and not sp["steps"]:
        blockers.append("讲法页没列出编号的步骤")
    elif sp and sp["approved"] < sp["steps"]:
        # The author's call (spec S3), taken as recommended: an unapproved step keeps the paper from the author.
        blockers.append(f"讲法页 {sp['approved']}/{sp['steps']} 步认可")
    if open_:
        blockers.append(f"待做开着 {len(open_)}")
    st.update(weak=[c["id"] for c in weak], open=[t["id"] for t in open_], over_labels=labels, blockers=blockers,
              verdict=(SUBMITTED if SUBMITTED_STAGE.search(st.get("stage") or "") else NOT_READY if blockers else AUTHOR),
              next=[t["id"] for t in open_[:3]])
    return st


def compute(cfg, ws):
    """The state of this workspace's paper. Reads the ledger and the sentence index; runs nothing."""
    path = cfg.get("claims")
    if not path:
        return {"configured": False, "verdict": NO_LEDGER}
    p = Path(path).expanduser()
    st = {"configured": True, "path": str(p), "stage": "", "claims": [], "todo": [], "problems": [], "over": [],
          "absent": [], "index_head": None, "scan_problems": [], "carrying": {}, "negations": [], "warnings": [],
          "closing": [], "remaining": [], "gates_open": [], "gates_wanted": [], "questioned": False, "sets": [],
          "scope_at": [], "unqualified": [], "at_most": [], "unscoped": [], "early": [], "undefined": [], "outside": []}
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        st["problems"].append(f"主张清单读不到：{p}")
        st["unread"] = True  # its to-do items are unknown, not none (outlet.py)
        return judge(st)
    d = read_ledger(raw)
    st.update(stage=d["stage"], claims=d["claims"], todo=d["todo"], problems=d["problems"], sets=d["sets"],
              scope_at=d["scope_at"])
    from . import coverage as V
    versions, st["index_head"] = V.indexed_versions(ws)
    sentences = None if versions is None else (versions[-1]["sentences"] if versions else [])
    if sentences is None:
        st["problems"].append("句子索引没建（loop update），整篇的越界扫描没做")
    else:
        extra = extra_sentences(cfg, st["index_head"], st["scan_problems"], ws)
        st["over"], st["absent"] = scan(st["claims"], sentences, extra)
        last_seen(st["claims"], st["absent"], versions[:-1])
        st.update(question(st["claims"], sentences, extra))
        st["unqualified"] = qualify(st["claims"], sentences)
        st["at_most"] = said(st["claims"], sentences)
        st.update(scope(d["sets"], d["scope_at"], d["scope_skip"], sentences, extra))
        st["questioned"] = True
    st["gates_open"] = gates(cfg, st)
    st["gates_wanted"] = list(((cfg.get("state") or {}).get("required_gates")) or [])
    try:
        st["story"] = story_page(cfg)
    except Exception as e:  # noqa: BLE001 -- said, never taken for an approved page
        st["story"] = None
        st["problems"].append(f"讲法页读不出（{type(e).__name__}）")
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


# The stage is a name (09-28, the author: the stage line holds the stage's name only). One ledger's stage had grown into
# an account of the round, what was left and the conversation's list items, kept by hand beside that list and repeated
# in every turn's line. The line shows the name, cut at the first full stop within the width, and says the rest is there.
STAGE_MAX = 20  # display width: a CJK character counts one, anything else a half


def _width(t):
    return sum(1 if ord(c) >= 0x2E80 else 0.5 for c in t)


def stage_name(stage):
    """(the stage as the line shows it, the stage's width when it is longer than a name, else None)."""
    if _width(stage) <= STAGE_MAX:
        return stage, None
    cut, w = "", 0
    for c in stage:
        w += 1 if ord(c) >= 0x2E80 else 0.5
        if w > STAGE_MAX:
            break
        cut += c
    m = re.search(r"[。；;.]", cut)
    if m and m.start() > 0:
        cut = cut[:m.start()]
    elif re.match(r"[A-Za-z]", stage[len(cut):len(cut) + 1]) and " " in cut:
        cut = cut[:cut.rindex(" ")]  # not in the middle of a word
    return cut.rstrip("，,、 （(") + "…", round(_width(stage))


def ready(st):
    """Whether nothing stands between the paper and the author's call: 待作者终审, or 已投稿 with nothing in the way.
    `loop state` exits 0 on this, and willow's note carries it as verdict.ready (outlet.py); always a bool."""
    return bool(st.get("configured")) and st.get("verdict") in (AUTHOR, SUBMITTED) and not st.get("blockers")


def head(st):
    """The line's first part, the verdict and the stage: what willow's note carries as verdict.text (outlet.py)."""
    if not st.get("configured"):
        return "论文状态：没登记主张清单"
    shown, _long = stage_name(st.get("stage") or "")
    return f"论文状态：{st['verdict']}" + (f"（阶段：{shown}）" if shown else "")


def line(st):
    """The per-turn line. Said every turn, whatever the checks say."""
    if not st.get("configured"):
        return (head(st) + "（配置的 claims）——循环只知道检查跑没跑，"
                "不知道主张立没立住、还缺哪个分析")
    _shown, long_ = stage_name(st.get("stage") or "")
    head_ = head(st)
    bits = []
    if st["claims"]:
        bits.append(f"主张 {len(st['claims'])}：{_count(st)}")
    bits += [b for b in st["blockers"] if not b.startswith("待做开着")]
    open_ = [t for t in st["todo"] if not t["closed"]]
    if open_:
        # 每一项写编号、类型与状态：对话里的清单要引用稿件那边的一项（「等：稿件 ipm 的 N4」）得对得上号，
        # 只给按类型的计数时对不上（09-28 spec「清单与下一步的分工」D3）。
        bits.append(f"待做开着 {len(open_)}：" + "、".join(f"{t['id']} {t['kind'] or '?'}·{t['state'] or '?'}" for t in open_))
    if st["next"]:
        bits.append("下一步 " + "、".join(_todo_name(st, i) for i in st["next"]))
    if long_:
        bits.append(f"阶段写成了一段话（{long_} 字）：只写阶段名，过程进日志、待办进对话的清单")
    sp = st.get("story")
    if sp and sp["steps"] and sp["approved"] == sp["steps"]:
        bits.append(f"讲法页 {sp['steps']}/{sp['steps']} 步认可")   # the other cases are blockers, said above
    if st["verdict"] == AUTHOR:
        bits.append("能不能投由作者定")
    elif st["verdict"] == SUBMITTED:
        bits.append("已投出：之后的改动等审稿意见")
    return head_ + "——" + "；".join(bits)


# A change is said once, apart from the line (09-28: a blocker stood in the per-turn line from one commit on and was
# not read, because the line reads the same every turn). The record is what the state was at the last prompt of the
# manuscript's own session, when the hook said it; a history session's prompt does not use the change up.
TOLD = "state-told.json"


def told_view(st):
    """What a change is measured on: the verdict and the blockers the line names (open to-dos are listed apart)."""
    if not st.get("configured"):
        return {"verdict": None, "blockers": []}
    return {"verdict": st["verdict"], "blockers": [b for b in st["blockers"] if not b.startswith("待做开着")]}


def change_since_told(ws, st, name):
    """One sentence on how the state differs from the one last said at a prompt, or None: nothing recorded yet (the
    first prompt says the whole line anyway), nothing changed, or a record that cannot be read."""
    try:
        old = json.loads((Path(ws) / "cache" / TOLD).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(old, dict):
        return None
    now, before = told_view(st), [b for b in old.get("blockers") or [] if isinstance(b, str)]
    parts = []
    if old.get("verdict") != now["verdict"]:
        parts.append(f"论文状态 {old.get('verdict') or '没登记'} → {now['verdict'] or '没登记'}")
    new = [b for b in now["blockers"] if b not in before]
    gone = [b for b in before if b not in now["blockers"]]
    if new:
        parts.append("新：" + "、".join(new))
    if gone:
        parts.append("已解：" + "、".join(gone))
    return f"写作循环 · {name}：上一条消息以来，论文状态有变化——" + "；".join(parts) + "。" if parts else None


def mark_told(ws, st):
    """Record the state as said at this prompt; written whole or not at all."""
    p = Path(ws) / "cache" / TOLD
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(told_view(st), ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def table(st):
    """The terminal view: every claim, every open item, every sentence over the line."""
    if not st.get("configured"):
        return line(st)
    out = [line(st), f"清单：{st['path']}" + (f" · 索引 {str(st['index_head'])[:7]}" if st.get("index_head") else "")]
    for p in st["problems"]:
        out.append(f"  读不懂  {p}")
    for p in st.get("scan_problems") or []:
        out.append(f"  读不到  {p}")
    for c in st["claims"]:
        out.append(f"  主张 {c['id']}  {c['strength'] or '?'}  {c['title']}")
        out.append(f"      允许的说法：{c['allowed'] or '—'}")
        for o in (x for x in st["over"] if x["claim"] == c["id"]):
            out.append(f"      越界「{o['pattern']}」：{'、'.join(o['labels'])}")
        for a in (x for x in st["absent"] if x["claim"] == c["id"]):
            seen = a.get("last_seen")
            out.append((f"      缺「{a['pattern']}」@ {a['place']}：这一处没有" if a.get("place")
                        else f"      缺「{a['pattern']}」：整篇没有一句")
                       + (f"——可能是台账过期：该短语在 {seen['sha'][:7]} 之后不再出现" if seen else ""))
        for x in (y for y in st.get("at_most") or [] if y["claim"] == c["id"]):
            where = f"（{'、'.join(x['places'])}）" if x["places"] else ""
            out.append(f"      至多 {x['limit']} 句{where}，现有 {len(x['labels'])} 句：{'、'.join(x['labels']) or '—'}"
                       + ("——说太多遍：删到上限，或读过后改上限" if len(x["labels"]) > x["limit"] else ""))
        if c["id"] in (st.get("carrying") or {}):
            out.append(f"      承载句：{'、'.join(st['carrying'][c['id']]) or '一句也没有'}")
        for u in (x for x in st.get("unqualified") or [] if x["claim"] == c["id"]):
            out.append(f"      承载句缺限定词「{u['pattern']}」：{'、'.join(u['labels'])}")
        if c["id"] in (st.get("negations") or []):
            out.append("      全称否定：要写「依据」（哪个检验、检验力多少）")
        for w in (x for x in st.get("warnings") or [] if x["claim"] == c["id"]):
            out.append(f"      要人看：{w['why']}")
        if c["needs"]:
            out.append(f"      缺：{'、'.join(c['needs'])}")
    for t in st["todo"]:
        out.append(f"  待做 {t['id']}  {t['kind'] or '?'}  {t['status'] or '?'}  {t['title']}")
    for x in st.get("sets") or []:
        out.append(f"  集合 {x['id']}  {x['title']}" + (f"（{x['size']}）" if x["size"] else ""))
        for e in (y for y in st.get("early") or [] if y["set"] == x["id"]):
            out.append(f"      {e['label']}「{e['phrase']}」用在定义（{e['defined']}）之前：写出数目，或把定义挪到前面")
        if x["id"] in (st.get("undefined") or []):
            out.append("      定义句找不到：「定义」的正则一句也没对上")
        for o in (y for y in st.get("outside") or [] if y["set"] == x["id"]):
            out.append(f"      名词用在集合外的系统上：{'、'.join(o['labels'])}——要人读，读者会不会把它们算进去")
    for u in st.get("unscoped") or []:
        out.append(f"  全称量词没对集合  {u['label']}「{u['phrase']}」：写出数目、登记集合，或读过后写进「全称量词不查」")
    if st.get("questioned") and not st.get("unscoped") and not st.get("early"):
        out.append(f"  全称量词：查过 {'、'.join(st.get('scope_at') or [])}，每一处都写了数目或对上了集合"
                   "（只认 every / all / each / none of / no 与 所有 / 全部 / 任何 / 每）")
    # Silence is said as what it is. A workspace read these rules as not yet built because nothing of them showed:
    # no method sentence matched, and no gate was configured.
    if st.get("closing"):
        out.append(f"  方法句（排除了别的解释）：{'、'.join(st['closing'])}；对照提到剩余线索的句子："
                   f"{'、'.join(st.get('remaining') or []) or '没有'}——要人读")
    elif st.get("questioned"):
        out.append("  方法句（排除了别的解释）：查过全文与图表文字，没有一句是「only X differs / no cue left / 其余相同」"
                   "这类写法（只认这些写法，换个说法的看不见）")
    for g in st.get("gates_open") or []:
        out.append(f"  门没关  {g}（风险台账里还没有已决的这道门）")
    if not st.get("gates_wanted"):
        out.append("  必需的门：没配置（state.required_gates），冻结前的统计审查、上传前的外部领域审阅不会被报")
    elif not st.get("gates_open"):
        out.append(f"  必需的门：{'、'.join(st['gates_wanted'])} 都已在风险台账里决定")
    return "\n".join(out)


def cell(st):
    """The overview's first 待办 cell: the paper, before the checks."""
    if not st.get("configured"):
        return {"title": "论文", "text": "没登记主张清单", "value": "没登记", "tone": "orange",
                "sub": "所以只知道检查跑没跑，不知道主张立没立住"}
    text = "；".join(st["blockers"]) or "没有挡着的"
    sub = (("下一步 " + "、".join(st["next"])) if st["next"]
           else "已投出，等审稿意见" if st["verdict"] == SUBMITTED else "能不能投由作者定")
    return {"title": "论文", "text": text[:64], "value": st["verdict"], "sub": sub[:120],
            "tone": "orange" if st["verdict"] == NOT_READY else "white"}
