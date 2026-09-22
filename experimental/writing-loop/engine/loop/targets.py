"""The target profile: where the manuscript is going, read from the workspace config and checked, never assumed.

    "target": {
      "venue": "Journal Name",                       the registered container-title
      "guide": "path/in/repo/guide.txt",             the archived author guide (optional)
      "venue_corpus": {"manifest": "path/in/repo/or/absolute.json", "dir": "~/corpus"},
      "intent_card": "/abs/path/intent-card.md",     what the author wants readers to carry away
      "readers": {"sections": ["A", "I"]}
    }

A journal or conference workspace without a venue is reported, not defaulted: a prose baseline "of the venue" that
is really something else was measured for seven rounds once, and the fix was to make the venue an input. A venue
corpus is accepted only when its manifest names the same venue (HTML entities undone: registrars return "&amp;"),
admitted at least CORPUS_FLOOR papers with closed accounting, and every admitted file is in the corpus directory.

Experiments: when the workspace names an experiments directory, every experiment's README must say what became of
it (处置：已晋升 → where / 退役 — why / 进行中 — the gate; 复查 YYYY-MM-DD). A prototype that works and is never
promoted is the failure this reports.
"""
import datetime as dt
import html
import json
import re
import subprocess
from pathlib import Path

from . import catalogue as K

CORPUS_FLOOR = 20
VENUE_GENRES = ("journal", "conference")
DISPOSITION = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?处置(?:\*\*)?\s*[:：]\s*(?:\*\*)?(已晋升|退役|进行中)(.*)$", re.M)
REVIEW_DATE = re.compile(r"复查\s*(\d{4}-\d{2}-\d{2})")


def _norm(s):
    return " ".join(html.unescape(s or "").split()).casefold()


def _read(cfg, path):
    """A path in the manuscript repository at the configured ref, or an absolute / home path on disk."""
    p = Path(path).expanduser()
    if p.is_absolute():
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None
    r = subprocess.run(["git", "-C", str(cfg["repo"]), "show", f"{cfg['ref']}:{path}"], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def venue_corpus_problems(cfg):
    venue = K.get(cfg, "target.venue")
    vc = K.get(cfg, "target.venue_corpus") or {}
    if not venue:
        return ["目标未登记：target.venue 为空，文风没有刊物可比"]
    if not vc.get("manifest") or not vc.get("dir"):
        return [f"{venue} 的刊物语料未登记（target.venue_corpus 要有 manifest 与 dir）"]
    raw = _read(cfg, vc["manifest"])
    if raw is None:
        return [f"刊物语料 manifest 读不到：{vc['manifest']}"]
    try:
        m = json.loads(raw)
    except ValueError:
        return [f"刊物语料 manifest 不是 JSON：{vc['manifest']}"]
    out = []
    if _norm(m.get("venue")) != _norm(venue):
        out.append(f"刊物语料是「{m.get('venue')}」的，不是「{venue}」的")
    admitted = m.get("admitted") if isinstance(m.get("admitted"), int) else len(m.get("records") or [])
    if admitted < CORPUS_FLOOR:
        out.append(f"刊物语料只有 {admitted} 篇，少于 {CORPUS_FLOOR} 篇不报百分位")
    if m.get("accounting_closes") is False:
        out.append("刊物语料的账目不闭合")
    d = Path(vc["dir"]).expanduser()
    if not d.is_dir():
        out.append(f"刊物语料目录不存在：{vc['dir']}")
    else:
        files = [r.get("file") for r in m.get("records") or [] if r.get("file")]
        gone = [f for f in files if not (d / f).is_file()]
        if not files:
            out.append("manifest 没记下任何文件名，无法核对语料目录")
        elif gone:
            out.append(f"语料目录少了 {len(gone)} 个 manifest 里的文件（如 {gone[0]}）")
    return out


APPROVAL = re.compile(r"作者授权定稿[:：]\s*uuid\s+([0-9a-f-]{8,})")


def _approval_in_transcripts(cfg, uuid):
    """Whether a session transcript of this workspace carries the author's message with that uuid. The result is
    cached per uuid in the workspace: the transcripts are large and a message's existence does not change."""
    ws = Path(cfg["_ws"]) if cfg.get("_ws") else None
    cache = ws / "cache" / "coverage" / "approvals.json" if ws else None
    try:
        known = json.loads(cache.read_text(encoding="utf-8")) if cache and cache.is_file() else {}
    except (OSError, ValueError):
        known = {}
    if known.get(uuid) is True:
        return True
    from . import doctor
    t = cfg.get("transcripts") or {}
    files = list(doctor.transcript_files(cfg) or [])
    for s in t.get("also") or []:
        if isinstance(s, dict) and s.get("cwd_prefix"):
            files += list(doctor.transcript_files(cfg, s["cwd_prefix"]) or [])
    needle = f'"uuid":"{uuid}'.encode()
    found = False
    for f in files:
        try:
            with open(f, "rb") as fh:
                for line in fh:
                    if needle in line and b'"type":"user"' in line:
                        found = True
                        break
        except OSError:
            continue
        if found:
            break
    if found and cache:
        known[uuid] = True
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(known), encoding="utf-8")
    return found


def intent_card_state(cfg):
    """(state, path). author: the card is in the workspace's human/ folder (only the author writes there).
    delegated: the card names the author's message that asked Claude to finalise it, and that message is in this
    workspace's transcripts. draft: anything else."""
    card = K.get(cfg, "target.intent_card")
    if not card:
        return None, None
    p = Path(card).expanduser()
    if not p.is_file():
        return "missing", str(p)
    m = APPROVAL.search(p.read_text(encoding="utf-8", errors="replace"))
    if m and cfg.get("transcripts") and _approval_in_transcripts(cfg, m.group(1)):
        return "delegated", str(p)
    human = (Path(cfg["_ws"]) / "human").resolve() if cfg.get("_ws") else None
    try:
        authored = human is not None and p.resolve().is_relative_to(human)
    except AttributeError:  # Python < 3.9
        authored = human is not None and str(p.resolve()).startswith(str(human) + "/")
    return ("author" if authored else "draft"), str(p)


def problems_for(check_id, cfg):
    """Prerequisite problems beyond a missing config key, for the checks that have them."""
    check = next((c for c in K.CHECKS if c["id"] == check_id), None)
    if check and "target.venue_corpus.dir" in check["needs"]:
        # Every check measured against the venue's corpus needs that corpus to be the venue's.
        return venue_corpus_problems(cfg) if K.get(cfg, "target.venue_corpus.dir") else []
    if check_id == "readers":
        state, path = intent_card_state(cfg)
        return [f"意图卡不存在：{path}"] if state == "missing" else []
    return []


def describe(cfg):
    """{venue, line, problems, intent_card}. problems is empty only when the target is fully usable."""
    venue = K.get(cfg, "target.venue")
    problems = []
    if not venue and cfg.get("genre") in VENUE_GENRES:
        problems.append(f"目标未登记（genre = {cfg.get('genre')}，target.venue 为空）")
    if venue:
        problems += venue_corpus_problems(cfg)
    state, _ = intent_card_state(cfg)
    if venue and state is None:
        problems.append("意图卡未登记（target.intent_card）")
    elif state == "missing":
        problems.append("意图卡文件不存在")
    card = {"author": "作者定稿", "delegated": "Claude 定稿（作者授权，会话记录可查）",
            "draft": "草稿（未经作者定稿）"}.get(state, "—")
    line = f"{venue or '未登记'} · 意图卡 {card}"
    guide = K.get(cfg, "target.guide")
    if guide and _read(cfg, guide) is None:
        problems.append(f"投稿指南快照读不到：{guide}")
    return {"venue": venue, "line": line, "problems": problems, "intent_card": state}


HEAD_LINES = 8
BACKTICKED = re.compile(r"`([^`\s]+)`")


def _promoted_target_exists(rest, roots, dirs):
    """Every path named in backticks after 已晋升 must exist strictly inside the toolkit or the experiments'
    repository -- not a root, not the home directory, not an experiments directory or anything in one. A
    promotion to a place that is not there, or to a place that proves nothing (`./`, `~/`, the experiment itself),
    is not a promotion."""
    target = re.split(r"[；;（(]", rest, maxsplit=1)[0]   # the promotion target, not the notes after it
    paths = [p for p in BACKTICKED.findall(target) if "/" in p.strip("/") or p.endswith((".py", ".mjs"))]
    if not paths:
        return False
    banned = [d.resolve() for d in dirs]

    def ok(p):
        for r in roots:
            q = (r / p).resolve()
            if not q.exists() or not str(q).startswith(str(r.resolve()) + "/"):
                continue  # missing, or not strictly inside the root (the root itself, a parent, the home directory)
            if any(q == b or str(q).startswith(str(b) + "/") for b in banned):
                continue
            return True
        return False
    return all(ok(p) for p in paths)


def experiments(cfg, today=None):
    d = cfg.get("experiments_dir")
    if not d:
        return None
    dirs = [Path(x).expanduser() for x in (d if isinstance(d, list) else [d])]
    today = today or dt.date.today()
    out = {"dir": ", ".join(map(str, dirs)), "total": 0, "undisposed": [], "overdue": [], "in_progress": [],
           "promoted": [], "retired": [], "promoted_missing": []}
    roots = [K.ENGINE_ROOT] + [x.parent for x in dirs]
    for root in dirs:
        if not root.is_dir():
            out["undisposed"].append(f"（目录不存在：{root}）")
            continue
        for exp in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
            _one(exp, out, today, roots, dirs)
    return out


def _one(exp, out, today, roots, dirs):
    out["total"] += 1
    try:
        text = (exp / "README.md").read_text(encoding="utf-8")
    except OSError:
        out["undisposed"].append(exp.name)
        return
    # The disposition is a heading-level fact: it must sit just under the title, not anywhere in the body.
    text = re.sub(r"(?ms)^```.*?^```", "", text)   # a disposition quoted in a code block is not one
    head = "\n".join([ln for ln in text.splitlines() if ln.strip()][:HEAD_LINES])
    m = DISPOSITION.search(head)
    if not m:
        out["undisposed"].append(exp.name)
        return
    if True:
        kind, rest = m.group(1), m.group(2)
        if kind == "已晋升" and not _promoted_target_exists(rest, roots, dirs):
            out["promoted_missing"].append(exp.name)
        elif kind == "已晋升":
            out["promoted"].append(exp.name)
        elif kind == "退役" and len(re.sub(r"[\s—\-–:：◌]", "", rest)) < 6:
            out["undisposed"].append(exp.name)  # retired, but not a word about why: not a disposition
        elif kind == "退役":
            out["retired"].append(exp.name)
        else:
            dm = REVIEW_DATE.search(rest)
            if not dm:
                out["undisposed"].append(exp.name)
            elif dt.date.fromisoformat(dm.group(1)) < today:
                out["overdue"].append(exp.name)
            else:
                out["in_progress"].append([exp.name, dm.group(1)])



# ---------------------------------------------------------------- open decisions: gates and strategic risks

RISK_HEAD = re.compile(r"^##\s+(门|风险)\s+(\S+)\s+(.+?)\s*$", re.M)
RISK_FIELD = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(来源|消除它的证据|由哪个门决定|状态|规模)(?:\*\*)?\s*[:：]\s*(?:\*\*)?\s*(.*?)\s*$",
                        re.M)
RISK_NEEDS = ("来源", "消除它的证据", "由哪个门决定", "状态")
RISK_DECIDED = re.compile(r"^已决\s+(\d{4}-\d{2}-\d{2})\s*(.*?)(?:\s*[—–-]+\s*作者\s*[:：]?\s*uuid\s+([0-9a-f-]{8,}))?\s*$")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _scale(text):
    """`我们 18 · 同类 46、120 · 单位 查询` -> {ours, least, unit, below}; None when the line does not say both sides."""
    parts = {m.group(1): m.group(2).strip() for m in re.finditer(r"(我们|同类|单位)\s*[:：]?\s*([^·]*)", text)}
    ours = NUMBER.findall(parts.get("我们", ""))
    theirs = [float(x.replace(",", "")) for x in NUMBER.findall(parts.get("同类", ""))]
    if not ours or not theirs:
        return None
    o, least = float(ours[0].replace(",", "")), min(theirs)
    fmt = lambda x: str(int(x)) if x == int(x) else str(x)  # noqa: E731
    return {"ours": fmt(o), "least": fmt(least), "comparators": len(theirs), "unit": parts.get("单位", "").strip(),
            "below": o < least}


def risks(cfg):
    """The workspace's register of open gates and strategic risks, or None when none is configured.

    An item is open until its status says 已决 with a date and the uuid of the author's message that decided it, and
    that message is in this workspace's transcripts; a register kept under the workspace's human/ folder is the
    author's own and needs no uuid. Whatever cannot be read is reported, never taken for "no risks": an item missing a
    field or with a status nobody can parse stays open and says why, and a register that cannot be read or holds no
    item is a problem of its own."""
    path = cfg.get("risks")
    if not path:
        return None
    p = Path(path).expanduser()
    out = {"path": str(p), "open": [], "decided": [], "below": [], "problems": []}
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        out["problems"].append(f"台账读不到：{p}")
        return out
    register = re.sub(r"(?ms)^```.*?^```", "", raw)  # an item quoted as an example is not an item
    human = (Path(cfg["_ws"]) / "human").resolve() if cfg.get("_ws") else None
    try:
        authored = human is not None and p.resolve().is_relative_to(human)
    except AttributeError:  # Python < 3.9
        authored = human is not None and str(p.resolve()).startswith(str(human) + "/")
    heads = list(RISK_HEAD.finditer(register))
    if not heads:
        out["problems"].append(f"台账里没有一项（要 `## 门 <id> <标题>` 或 `## 风险 <id> <标题>`）：{p.name}")
    for i, h in enumerate(heads):
        body = register[h.end(): heads[i + 1].start() if i + 1 < len(heads) else len(register)]
        fields = {}
        for m in RISK_FIELD.finditer(body):
            fields.setdefault(m.group(1), m.group(2))
        item = {"kind": h.group(1), "id": h.group(2), "title": h.group(3), "gate": fields.get("由哪个门决定", ""),
                "source": fields.get("来源", ""), "status": fields.get("状态", "")}
        if fields.get("规模"):
            sc = _scale(fields["规模"])
            if sc:
                item["scale"] = sc
                if sc["below"]:
                    out["below"].append({"id": item["id"], "kind": item["kind"], **sc})
        missing = [f for f in RISK_NEEDS if not fields.get(f)]
        status = fields.get("状态", "")
        if missing:
            item["detail"] = "格式不全：缺 " + "、".join(missing)
            out["open"].append(item)
            continue
        if status.startswith("未决"):
            item["detail"] = "未过" if item["kind"] == "门" else f"待 {item['gate']}"
            out["open"].append(item)
            continue
        d = RISK_DECIDED.match(status)
        if not d:
            item["detail"] = f"状态读不懂：{status[:40]}"
            out["open"].append(item)
            continue
        item["decided_on"], item["decision"], uuid = d.group(1), d.group(2).strip(), d.group(3)
        if authored:
            out["decided"].append(item)
        elif not uuid:
            item["detail"] = "写了已决，但没指向作者的消息（uuid）"
            out["open"].append(item)
        elif cfg.get("transcripts") and _approval_in_transcripts(cfg, uuid):
            item["uuid"] = uuid
            out["decided"].append(item)
        else:
            item["detail"] = f"已决所指的作者消息在会话记录里查不到（uuid {uuid[:8]}）"
            out["open"].append(item)
    return out


def doctor_problems(cfg):
    """(item, message) pairs for `loop doctor`, whose contract is narrower than coverage's: a path the config names
    must resolve. A target that is not registered, or a corpus that is too small, is a coverage gap and is shown by
    `loop coverage`, the notch and the agent's reminder; it is not a broken tool. (The notch producer runs doctor
    every round and treats any problem as a tool fault that hides the card, so the line matters.)"""
    out = []
    vc = K.get(cfg, "target.venue_corpus") or {}
    if vc.get("manifest") and _read(cfg, vc["manifest"]) is None:
        out.append(("target.venue_corpus.manifest", f"读不到：{vc['manifest']}"))
    if vc.get("dir") and not Path(vc["dir"]).expanduser().is_dir():
        out.append(("target.venue_corpus.dir", f"目录不存在：{vc['dir']}"))
    state, path = intent_card_state(cfg)
    if state == "missing":
        out.append(("target.intent_card", f"文件不存在：{path}"))
    guide = K.get(cfg, "target.guide")
    if guide and _read(cfg, guide) is None:
        out.append(("target.guide", f"读不到：{guide}"))
    return out
