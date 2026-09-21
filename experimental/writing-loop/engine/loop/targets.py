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


def intent_card_state(cfg):
    card = K.get(cfg, "target.intent_card")
    if not card:
        return None, None
    p = Path(card).expanduser()
    if not p.is_file():
        return "missing", str(p)
    human = (Path(cfg["_ws"]) / "human").resolve() if cfg.get("_ws") else None
    try:
        authored = human is not None and p.resolve().is_relative_to(human)
    except AttributeError:  # Python < 3.9
        authored = human is not None and str(p.resolve()).startswith(str(human) + "/")
    return ("author" if authored else "draft"), str(p)


def problems_for(check_id, cfg):
    """Prerequisite problems beyond a missing config key, for the checks that have them."""
    if check_id == "fingerprint-venue":
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
    card = {"author": "作者定稿", "draft": "草稿（未经作者定稿）"}.get(state, "—")
    line = f"{venue or '未登记'} · 意图卡 {card}"
    guide = K.get(cfg, "target.guide")
    if guide and _read(cfg, guide) is None:
        problems.append(f"投稿指南快照读不到：{guide}")
    return {"venue": venue, "line": line, "problems": problems, "intent_card": state}


def experiments(cfg, today=None):
    d = cfg.get("experiments_dir")
    if not d:
        return None
    root = Path(d).expanduser()
    today = today or dt.date.today()
    out = {"dir": str(root), "total": 0, "undisposed": [], "overdue": [], "in_progress": [], "promoted": [],
           "retired": []}
    if not root.is_dir():
        out["undisposed"].append(f"（目录不存在：{d}）")
        return out
    for exp in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
        out["total"] += 1
        try:
            text = (exp / "README.md").read_text(encoding="utf-8")
        except OSError:
            out["undisposed"].append(exp.name)
            continue
        m = DISPOSITION.search(text)
        if not m:
            out["undisposed"].append(exp.name)
            continue
        kind, rest = m.group(1), m.group(2)
        if kind == "已晋升":
            out["promoted"].append(exp.name)
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
