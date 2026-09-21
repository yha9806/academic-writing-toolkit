"""点进去的第一层：整份稿子按阶段走到哪（lintel 分镜 ㊸–㊽，作者 2026-09-21 定五点默认）。

悬停卡说这一轮改了什么；这里说整份稿子：

    阶段        版本之间空了 gap_days 天以上就分段；每天改过或新加几句；登记表里可以给段命名，不命名只写日期
    剖面        这一段里每一节改过的比例（相对上一段末；第一段相对第一版正文）
    依据        稿件仓里的主张台账（TSV），按提交跑 AWT 的 audit-claim-ledger，得到走势与逐句清单；
                或者循环自己的 JSON 台账（checks.json），只有现在一个点
    还差什么    稿件仓的 issue（已关 / 共几条，范围写出来）与投稿构建报告；没有清单就不写完成度
    最近一轮    lintel.py 按面板第一行填

面板里能把一句缺依据的标成「方法署名」：动作的 id 写着 key 与程序短语，宿主写进收件，常驻只认自己
当前给出的动作，写进工作区 human/credits.txt（稿件仓只读），审计用 --credits 读它。

算一次要读整份索引并按提交跑审计，所以：索引、台账、credits 不变就用上一次的结果；每个提交的审计结果
按（提交、credits、审计脚本）存在 cache/overview-audit/；issue 十分钟问一次 gh，问不到写「取不到」，不写 0。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

GAP_DAYS = 3
ISSUES_TTL = 600.0
ENGINE_ROOT = Path(__file__).resolve().parents[4]
AUDIT = ENGINE_ROOT / ".claude/skills/audit/scripts/audit-claim-ledger.py"
CITE = re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{([^}]*)\}")
ACTION_CREDIT = "credit"
PHRASE_WORDS = 3
ITEMS_MAX = 64
CELLS_MAX = 120


def audit_script():
    p = Path(os.environ.get("LOOP_CLAIM_AUDIT") or AUDIT)
    if not p.is_file():
        raise RuntimeError(f"找不到台账审计脚本 {p}（设 LOOP_CLAIM_AUDIT 指过去）")
    return p


def _day(t):
    return time.strftime("%m-%d", time.localtime(t))


def _hm(t):
    return time.strftime("%m-%d %H:%M", time.localtime(t))


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def _sha(data):
    return hashlib.sha1(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- stages

def split_stages(versions, gap_days=GAP_DAYS):
    """Versions (old → new) cut wherever two neighbours are gap_days or more apart."""
    stages, cur = [], []
    for v in versions:
        if cur and v["time"] - cur[-1]["time"] >= gap_days * 86400:
            stages.append(cur)
            cur = []
        cur.append(v)
    if cur:
        stages.append(cur)
    return stages


def first_draft(stage):
    """The first version that is the manuscript rather than a stub: at least a quarter of the stage's final size."""
    last = len(stage[-1]["sentences"])
    return next((v for v in stage if len(v["sentences"]) * 4 >= last), stage[0])


def _hashes(v):
    return {x["hash"] for x in v["sentences"]}


def day_bars(versions, stages, gap_days=GAP_DAYS):
    """One bar per calendar day from the first draft to the last version: sentences changed or added that day.
    A run of gap_days or more empty days collapses to one gap marker."""
    start = first_draft(stages[0])
    stage_of = {v["sha"]: k for k, s in enumerate(stages) for v in s}
    per_day, prev = {}, None
    for v in versions:
        if v["time"] < start["time"]:
            continue
        hs = _hashes(v)
        d = time.strftime("%Y-%m-%d", time.localtime(v["time"]))
        slot = per_day.setdefault(d, [0, stage_of[v["sha"]]])
        if prev is not None:
            slot[0] += len(hs - prev)
        prev = hs
    if not per_day:
        return []
    import datetime as _dt
    d0 = _dt.date.fromisoformat(min(per_day))
    d1 = _dt.date.fromisoformat(max(per_day))
    bars, empty, month, stage = [], [], None, 0
    d = d0
    while d <= d1:
        key = d.isoformat()
        if key not in per_day:
            empty.append(d)
        else:
            if len(empty) >= gap_days:
                bars.append({"gapDays": len(empty)})
            else:
                for e in empty:
                    bars.append({"label": e.strftime("%m/%d") if e.month != month else e.strftime("%d"), "value": 0, "stage": stage})
                    month = e.month
            empty = []
            n, stage = per_day[key]
            bars.append({"label": d.strftime("%m/%d") if d.month != month else d.strftime("%d"), "value": n, "stage": stage})
            month = d.month
        d += _dt.timedelta(days=1)
    return bars[:60]


# ---------------------------------------------------------------- profile

def chapter(short):
    return short.split(".")[0] if short.startswith("§") else short


def changeset_sections(c):
    out = []
    for r in c.get("rows") or []:
        for side in ("new", "old"):
            v = r.get(side)
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, dict) and x.get("section") and x["section"] not in out:
                    out.append(x["section"])
    return out


def heat(base, head, names, touches=None, labels=None):
    """Per section of `head` in document order: sentences, changed-or-added since `base`, removed, new heading, and the
    tooltip line naming how many change sets of the stage touched it and the latest one."""
    bh, hh = _hashes(base), _hashes(head)
    bsec = {x["section"] for x in base["sentences"]}
    removed = {}
    for x in base["sentences"]:
        if x["hash"] not in hh:
            removed[x["section"]] = removed.get(x["section"], 0) + 1
    cells = {}
    for x in head["sentences"]:
        c = cells.setdefault(x["section"], {"id": x["section"], "label": names.get(x["section"], x["section"]),
                                            "weight": 0, "changed": 0, "mark": x["section"] not in bsec})
        c["weight"] += 1
        c["changed"] += x["hash"] not in bh
    out = []
    for c in cells.values():
        c["removed"] = removed.get(c["id"], 0)
        c["chapter"] = chapter(c["label"])
        c["value"] = round(c["changed"] / c["weight"], 4)
        hit = [cs for cs in (touches or []) if c["id"] in cs["sections"]]
        last = ""
        if hit:
            h = hit[0]
            last = f" · 最近一次 {_hm(h['time'])}「{(labels or {}).get(h['id']) or '没追到理由'}」"
        c["note"] = (f"{c['label']} · {c['weight']} 句 · 这一段改过或新加 {c['changed']} 句 · 删 {c['removed']} 句"
                     f" · {len(hit)} 个改动集碰过它{last}")[:256]
        out.append(c)
    return out[:CELLS_MAX]


def profile_block(cells, note, base):
    """剖面块。数字进图例格、读法进标题悬停：第一页不留说明段（分镜 ㊾ ㊿，作者 09-21 晚「第一页字太多」）。"""
    total = sum(c["weight"] for c in cells)
    ch = sum(c["changed"] for c in cells)
    rem = sum(c["removed"] for c in cells)
    still = sum(1 for c in cells if c["changed"] == 0)
    marks = sum(1 for c in cells if c["mark"])
    legend = [{"name": "改过或新加", "swatch": "indigo", "value": str(ch)},
              {"name": "删", "value": str(rem)},
              {"name": "一句没动", "swatch": "white28", "value": f"{still} 节"}]
    if marks:
        legend.append({"name": "新开", "swatch": "white", "value": f"{marks} 节"})
    return {"title": "剖面", "note": note[:64],
            "hint": (f"一格一节 · 宽 = 句数 · 高 = 这一段改过的比例 · 白点 = 这一段新开的节 · {base} · 共 {total} 句"
                     " · 点一格 = 只看碰过那一节的改动集")[:256],
            "legend": legend,
            "cells": [{k: c[k] for k in ("id", "label", "chapter", "weight", "value", "mark", "note")} for c in cells]}


# ---------------------------------------------------------------- alignment

def phrase_before(sentence, key, words=PHRASE_WORDS):
    """The few words the sentence credits `key` for: the prose right before the \\cite that names it (right after it when
    the cite opens the sentence). What the audit then matches the credit against, so it covers this use and not every
    use of the key."""
    for m in CITE.finditer(sentence):
        if key in [k.strip() for k in m.group(1).split(",")]:
            ws = re.findall(r"[\w'’\-]+", CITE.sub(" ", sentence[:m.start()]))
            if ws:
                return " ".join(ws[-words:])
            return " ".join(re.findall(r"[\w'’\-]+", CITE.sub(" ", sentence[m.end():]))[:words])
    return ""


def credit_action(finding):
    """The action id for 「这句是方法署名」: credit|key=phrase;key=phrase. None when a key has no usable phrase."""
    keys = [k for k in finding["cite_key"].split(",") if k]
    parts = []
    for k in keys:
        p = phrase_before(finding.get("sentence") or "", k)
        if not p or not re.fullmatch(r"[A-Za-z0-9_.:\-]+", k):
            return None
        parts.append(f"{k}={p}")
    return f"{ACTION_CREDIT}|" + ";".join(parts)


def parse_credit(action):
    """[(key, phrase)] from an action id this module made; None if it is not one."""
    kind, _, rest = (action or "").partition("|")
    if kind != ACTION_CREDIT or not rest:
        return None
    out = []
    for part in rest.split(";"):
        k, _, p = part.partition("=")
        if not re.fullmatch(r"[A-Za-z0-9_.:\-]+", k) or not p or re.search(r"[=#|;\n]", p):
            return None
        out.append((k, p))
    return out


EMPTY_LEDGER = "claim\tcite_key\tsnippet\tsource_file\tlevel\n"


def audit_at(repo, sha, led, credits, cache_dir):
    """The audit's JSON at one commit, cached per (commit, credits, script). A commit from before the ledger existed is
    run against an empty ledger (`"_no_ledger": true`): nothing is bound there, and every asserting sentence is missing."""
    has = _git(repo, "cat-file", "-e", f"{sha}:{led['path']}") is not None
    paths = [x for x in led["archive"] if _git(repo, "cat-file", "-e", f"{sha}:{x}") is not None]
    if led["base_dir"] not in paths:
        return None
    script = audit_script()
    ckey = _sha(sha + _sha(credits or "") + _sha(script.read_bytes()) + json.dumps(led, sort_keys=True))[:20]
    cfile = Path(cache_dir) / f"{sha[:12]}-{ckey}.json"
    if cfile.exists():
        try:
            return json.loads(cfile.read_text(encoding="utf-8"))
        except ValueError:
            pass
    tar = subprocess.run(["git", "-C", str(repo), "archive", sha, *paths], capture_output=True)
    if tar.returncode:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        tarfile.open(fileobj=io.BytesIO(tar.stdout)).extractall(tmp, filter="data")
        ledger = led["path"]
        if not has:
            ledger = ".loop-empty-ledger.tsv"
            (Path(tmp) / ledger).write_text(EMPTY_LEDGER, encoding="utf-8")
        args = [sys.executable, str(script), "--base-dir", led["base_dir"], "--ledger", ledger, "--json"]
        if not has:
            args.append("--allow-empty")
        if credits:
            cpath = Path(tmp) / ".loop-credits.txt"
            cpath.write_text(credits, encoding="utf-8")
            args += ["--credits", str(cpath)]
        r = subprocess.run(args, cwd=tmp, capture_output=True, text=True)
    try:
        out = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError(f"台账审计在 {sha[:7]} 没给出结果：{(r.stderr or '').strip()[:200]}")
    out["_no_ledger"] = not has
    cfile.parent.mkdir(parents=True, exist_ok=True)
    cfile.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _count(a):
    k = lambda n: [f for f in a["findings"] if f["kind"] == n]
    ua, uc, q = k("unledgered-assertion"), k("unledgered-credit"), k("qualifier-dropped")
    return {"cite": a["citing_sentences"], "rows": a["ledger_rows"], "hard": a["hard_finding_count"],
            "ua": ua, "uc": uc, "q": q, "credited": k("credited"),
            "bound": a["citing_sentences"] - len(ua) - len(uc) - len(k("credited"))}


def _words(sentence, n=12):
    s = CITE.sub("", sentence)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s).replace("{", "").replace("}", "").replace("$", "")
    ws = s.split()
    return " ".join(ws[:n]) + (" …" if len(ws) > n else "")


def _file_chapters(head, names):
    """sections/05_evaluation_protocol.tex -> the chapter of the first section written in that file (§4)."""
    out = {}
    for x in head["sentences"]:
        f = Path(x.get("path") or "").name
        if f and f not in out:
            out[f] = chapter(names.get(x["section"], x["section"]))
    return out


def ledger_alignment(repo, commits, led, credits, cache_dir, head, names, scope):
    """Alignment block for one stage from the TSV claim ledger; the trend has one point per commit of the stage."""
    title = "依据"
    # 这一段最后一个提交里没有台账，就不跑：整段都没有东西可以对。
    if not commits or _git(repo, "cat-file", "-e", f"{commits[-1][0]}:{led['path']}") is None:
        return {"title": title, "empty": "这一段还没有台账，不画这一块"}
    results = [(sha, t, a) for sha, t in commits for a in [audit_at(repo, sha, led, credits, cache_dir)] if a is not None]
    if not results or results[-1][2].get("_no_ledger"):
        return {"title": title, "empty": "这一段还没有台账，不画这一块"}
    now = _count(results[-1][2])
    points = [{"scope": c["cite"], "done": c["bound"], "missing": len(c["ua"])} for c in (_count(a) for _, _, a in results)]
    first = next(i for i, (_, _, a) in enumerate(results) if not a.get("_no_ledger"))
    # 三条线的键（走势图自己的图例）；面板第一页画的是下面那张带数的图例格，线的键只在没有格的老宿主上用。
    keys = [{"name": "引用", "swatch": "white45", "value": str(now["cite"])},
            {"name": "已绑", "swatch": "indigo", "value": str(now["bound"])},
            {"name": "缺", "swatch": "orange", "dashed": True, "value": f"{points[0]['missing']}→{len(now['ua'])}"}]
    trend = None
    if len(points) >= 2:
        trend = {"points": points[-200:], "marker": first or None,
                 "markerLabel": f"{_day(results[first][1])} 建台账" if first else None,
                 "startLabel": _day(results[0][1]), "endLabel": _day(results[-1][1]), "legend": keys}
    files = _file_chapters(head, names)
    items = []
    for f in now["ua"]:
        items.append({"place": files.get(Path(f["location"]).name, Path(f["location"]).stem)[:64], "tag": "缺依据",
                      "key": f["cite_key"][:256], "text": _words(f.get("sentence") or f["detail"])[:256], "tone": "orange",
                      "action": ({"title": "是方法署名", "id": credit_action(f)} if credit_action(f) else None)})
    for f in now["q"]:
        hedges = re.findall(r"'([^']+)'", f["detail"].split(";")[0])
        items.append({"place": f"台账 {f['location'].split(':')[-1]} 行", "tag": "限定词", "key": f["cite_key"][:256],
                      "text": f"原文有「{'、'.join(hedges)}」，稿里那句没有"[:256], "tone": "orange"})
    for f in now["credited"]:
        items.append({"place": files.get(Path(f["location"]).name, Path(f["location"]).stem)[:64], "tag": "方法署名",
                      "key": f["cite_key"][:256], "text": _words(f.get("sentence") or f["detail"])[:256], "tone": "white45"})
    headline = [{"value": str(len(now["ua"])), "text": "句在转述文献却没绑原文", "tone": "orange" if now["ua"] else "white"},
                {"value": str(len(now["q"])), "text": "处限定词丢了", "tone": "orange" if now["q"] else "white"}]
    # 一句下面的图例格：数不再写成句子（分镜 ㊾）。范围与「片段都在存档原文里」进标题悬停。
    legend = keys + [{"name": "只署名", "value": str(len(now["uc"]))}]
    if now["credited"]:
        legend.append({"name": "方法署名", "value": str(len(now["credited"]))})
    if now["hard"]:
        legend.append({"name": "硬错", "swatch": "orange", "value": str(now["hard"])})
    hint = " · ".join(x for x in [scope, f"硬错 {now['hard']} 处" if now["hard"] else "片段都在存档原文里", "点一下 = 逐句清单"] if x)
    return {"title": title, "note": f"台账 {now['rows']} 行", "hint": hint[:256], "headline": headline, "legend": legend[:6],
            "trend": trend, "items": items[:ITEMS_MAX],
            "folded": f"只署名的 {len(now['uc'])} 句收起了" if now["uc"] else None}


def checks_alignment(chk):
    """Alignment from the loop's own JSON ledger (checks.json): the head only, no trend."""
    if not chk:
        return None
    xs = list(chk["sentences"].values())
    cited = [x for x in xs if x["keys"]]
    bound = [x for x in cited if x["ledger"]]
    nosrc = sum(1 for x in xs for e in x["ledger"] if e.get("status") != "found")
    hold = sum(1 for x in xs if x.get("placeholders"))
    return {"title": "依据", "note": f"台账 {chk['ledger_total']} 条",
            "headline": [{"value": f"{len(bound)}/{len(cited)}", "text": "句带引用的都绑了原文" if len(bound) == len(cited) else "句带引用的绑了原文",
                          "tone": "white"},
                         {"value": str(nosrc), "text": "条原文没存到", "tone": "orange" if nosrc else "white"},
                         {"value": str(hold), "text": "处占位没填", "tone": "orange" if hold else "white"}]}


# ---------------------------------------------------------------- what is left

def issues(repo, remote, cache_dir, now, ttl=ISSUES_TTL):
    """[{state}] of the manuscript repo's issues, asked at most every ttl seconds; None when gh cannot answer."""
    cfile = Path(cache_dir) / "overview-issues.json"
    try:
        c = json.loads(cfile.read_text(encoding="utf-8"))
        if now - c["at"] < ttl:
            return c["issues"]
    except (OSError, ValueError, KeyError):
        pass
    url = _git(repo, "remote", "get-url", remote) or ""
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", url)
    out = None
    if m:
        try:
            r = subprocess.run(["gh", "issue", "list", "--repo", m.group(1), "--state", "all", "--limit", "200",
                                "--json", "number,state"], capture_output=True, text=True, timeout=15)
            if r.returncode == 0:
                out = json.loads(r.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            out = None
    cfile.parent.mkdir(parents=True, exist_ok=True)
    cfile.write_text(json.dumps({"at": now, "issues": out}), encoding="utf-8")
    return out


def build_report(repo, ref, rpath):
    """The submission build report (the registry's `build_report` path) at `ref`; None when there is none or it is not a report."""
    if not rpath:
        return None
    raw = _git(repo, "show", f"{ref}:{rpath}")
    try:
        rep = json.loads(raw) if raw else None
    except ValueError:
        rep = None
    return rep if isinstance(rep, dict) and "ready_to_upload" in rep else None


def todo_block(cfg_ov, repo, ref, cache_dir, now, rep=None):
    """待办：左栏一行一条，右边只放一个数（`value`）；整句（`text`）与预防针（`sub`）进悬停（分镜 51）。"""
    cells = []
    iss = cfg_ov.get("issues")
    if iss:
        xs = issues(repo, iss.get("remote", "origin"), cache_dir, now)
        if xs is None:
            cells.append({"title": "稿件仓 issue", "text": "取不到", "value": "取不到", "sub": "gh 没登录或断网，不写数"})
        else:
            closed = sum(1 for i in xs if i.get("state") == "CLOSED")
            cells.append({"title": "稿件仓 issue", "text": f"已关 {closed} / 共 {len(xs)}", "value": f"{closed}/{len(xs)}",
                          "sub": f"范围就是这 {len(xs)} 条，加条目比例会降"})
    else:
        cells.append({"title": "清单", "text": "没有登记清单", "value": "没登记",
                      "sub": "所以不写完成度；登记一个（issue 或清单文件）之后这里才出比例"})
    rpath = cfg_ov.get("build_report")
    if rpath:
        rep = rep if rep is not None else build_report(repo, ref, rpath)
        if rep:
            fails = len(rep.get("failures") or [])
            ph = rep.get("title_page_placeholders") or 0
            ready = bool(rep.get("ready_to_upload"))
            text = f"失败 {fails} 项" + (f" · 标题页 {ph} 处待填" if ph else "")
            value = f"待填 {ph}" if ph else ("可上传" if ready else f"失败 {fails}")
            cells.append({"title": "投稿构建", "text": text, "value": value[:16],
                          "sub": ("可以上传" if ready else "所以还不能上传") + f" · 构建于 {str(rep.get('source_commit') or '?')[:7]}",
                          "tone": "white" if ready else "orange"})
        else:
            cells.append({"title": "投稿构建", "text": "读不出构建报告", "value": "读不出", "sub": f"{rpath}（{ref}）", "tone": "orange"})
    from . import coverage as V
    cells.append(V.todo_cell(V.load_summary(Path(cache_dir).parent, {"repo": repo, "ref": ref})))  # 检查覆盖（D4）
    return {"title": "待办", "hint": "只对着清单算，不打总分", "cells": cells[:4]}


def stats_strip(versions, stage_cs, alignment, ledger, rep):
    """数据条五格（分镜 ㊾，借许愿柳）：句 / 版 / 这一段改动集 / 缺依据 / 标题页待填。没有的格不写。"""
    out = [{"label": "句", "value": str(len(versions[-1]["sentences"]))},
           {"label": "版", "value": str(len(versions))},
           {"label": "改动集 · 这一段", "value": str(stage_cs)}]
    hl = (alignment or {}).get("headline") or []
    if ledger and hl and not (alignment or {}).get("empty"):
        out.append({"label": "缺依据", "value": hl[0]["value"], "tone": "orange" if hl[0].get("tone") == "orange" else None})
    if rep:
        ph = rep.get("title_page_placeholders") or 0
        ready = bool(rep.get("ready_to_upload"))
        out.append({"label": "标题页待填" if ph else "投稿构建",
                    "value": str(ph) if ph else ("可上传" if ready else f"失败 {len(rep.get('failures') or [])}"),
                    "tone": None if ready else "orange"})
    return out[:8]


# ---------------------------------------------------------------- the whole thing

class Overview:
    """Keeps the last result in memory; the resident calls `get` every tick."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.memo_key = None
        self.memo = None

    def _files(self):
        d = Path(self.cfg["_ws"]) / "index"
        # The coverage summary changes without the index changing (a check ran); it is part of what the panel shows.
        return [d / "sentences.json", d / "changesets.json", d / "checks.json", d / "explanations.json",
                Path(self.cfg["_ws"]) / "cache" / "coverage" / "summary.json"]

    def credits_path(self):
        ov = self.cfg.get("overview") or {}
        led = ov.get("ledger") or {}
        return Path(os.path.expanduser(led.get("credits") or str(Path(self.cfg["_ws"]) / "human" / "credits.txt")))

    def credits(self):
        try:
            return self.credits_path().read_text(encoding="utf-8")
        except OSError:
            return ""

    def get(self, now):
        if self.cfg.get("overview") is None:
            return None
        stat = []
        for f in self._files():
            try:
                s = f.stat()
                stat.append((s.st_mtime_ns, s.st_size))
            except OSError:
                stat.append(None)
        repo = self.cfg["repo"]
        head = _git(repo, "rev-parse", self.cfg["ref"])
        key = (tuple(stat), head, _sha(self.credits()), int(now // ISSUES_TTL))
        if key != self.memo_key:
            self.memo = build(self.cfg, now)
            self.memo_key = key
        return self.memo


def _labels(explanations, changesets):
    """change set id -> Claude's ≤6-character label, where the trigger message has one."""
    by_mid = {e["mid"]: e.get("label") for e in explanations if e.get("label")}
    out = {}
    for c in changesets:
        for t in c.get("triggers") or ():
            if isinstance(t, str) and by_mid.get(t):
                out[c["id"]] = by_mid[t]
                break
    return out


def build(cfg, now):
    """{"payload": detail.overview, "touches": {change set id: [section]}, "actions": {action id}, "stage_changesets": n}."""
    ov = cfg.get("overview") or {}
    d = Path(cfg["_ws"]) / "index"
    versions = json.loads((d / "sentences.json").read_text(encoding="utf-8"))["versions"]
    changesets = json.loads((d / "changesets.json").read_text(encoding="utf-8"))["changesets"]
    try:
        chk = json.loads((d / "checks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        chk = None
    try:
        explanations = json.loads((d / "explanations.json").read_text(encoding="utf-8"))["explanations"]
    except (OSError, ValueError, KeyError):
        explanations = []
    if not versions:
        return None
    names = {r["prefix"]: r.get("short") or r["prefix"] for r in cfg["draft"]["sections"]}
    labels = _labels(explanations, changesets)
    gap = ov.get("gap_days", GAP_DAYS)
    stages = split_stages(versions, gap)
    repo, ref = cfg["repo"], cfg["ref"]
    cache_dir = Path(cfg["_ws"]) / "cache" / "overview-audit"
    stage_names = ov.get("stage_names") or {}
    led = ov.get("ledger")
    credits = Overview(cfg).credits() if led else ""
    touches_all = {c["id"]: changeset_sections(c) for c in changesets}
    out_stages, actions, stage_cs = [], set(), 0
    for k, s in enumerate(stages):
        start = s[0]["time"]
        end = stages[k + 1][0]["time"] if k + 1 < len(stages) else float("inf")
        cs = sorted(({"id": c["id"], "time": c.get("time") or 0, "sections": touches_all[c["id"]]} for c in changesets
                     if start <= (c.get("time") or 0) < end), key=lambda c: -c["time"])
        if k == len(stages) - 1:
            stage_cs = len(cs)
        base = stages[k - 1][-1] if k else first_draft(s)
        base_long = (f"相对 {_day(base['time'])} 第 {k} 段末（{base['sha'][:7]}）" if k
                     else f"相对 {_day(base['time'])} 第一版正文（{base['sha'][:7]}）")
        cells = heat(base, s[-1], names, cs, labels)
        n0 = len(first_draft(s)["sentences"]) if k == 0 else len(stages[k - 1][-1]["sentences"])
        title = f"{_day(s[0]['time'])} – " + ("今天" if k == len(stages) - 1 and _day(s[-1]["time"]) == _day(now) else _day(s[-1]["time"]))
        entry = {"title": title, "name": stage_names.get(s[0]["sha"][:7]),
                 "caption": f"{len(s)} 版 · {n0}→{len(s[-1]['sentences'])} 句",
                 "profile": profile_block(cells, f"相对 {_day(base['time'])} · {base['sha'][:7]}", base_long)}
        if led:
            last = k == len(stages) - 1
            lo = s[0]["sha"]
            hi = ref if last else s[-1]["sha"]
            log = _git(repo, "log", "--reverse", "--format=%H %ct", f"{lo}^..{hi}") or _git(repo, "log", "--reverse", "--format=%H %ct", hi) or ""
            commits = [(x.split()[0], int(x.split()[1])) for x in log.splitlines() if x.strip()]
            al = ledger_alignment(repo, commits, led, credits, cache_dir, s[-1], names, ov.get("ledger_scope"))
            if last:
                actions |= {i["action"]["id"] for i in al.get("items") or [] if i.get("action")}
            entry["alignment"] = al
        elif k == len(stages) - 1:
            al = checks_alignment(chk)
            if al:
                entry["alignment"] = al
        out_stages.append(entry)
    shown = out_stages[-8:]
    span = shown[0]["title"].split(" – ")[0] + " → " + shown[-1]["title"].split(" – ")[-1]
    rep = build_report(repo, ref, ov.get("build_report"))
    payload = {
        # 标题两个字、右边一个数、读法进悬停（分镜 ㊾ ㊿）。
        "days": {"title": "阶段", "note": f"{span} · {len(versions)} 版",
                 "hint": f"柱 = 那天改过或新加的句数 · 靛蓝 = 选中的段 · 空 {gap} 天以上就分段 · 点左栏的段换段",
                 "bars": day_bars(versions, stages, gap)},
        "stages": shown,
        "selected": len(shown) - 1,
        "todo": todo_block(ov, repo, ref, Path(cfg["_ws"]) / "cache", now, rep),
    }
    return {"payload": payload, "touches": touches_all, "actions": actions, "stage_changesets": stage_cs,
            "stats": stats_strip(versions, stage_cs, shown[-1].get("alignment"), bool(led), rep)}


def apply_action(ovw, action, now=None):
    """Write one 「是方法署名」 into the credits file. Only an action the current overview offers is taken;
    returns (ok, reason)."""
    now = time.time() if now is None else now
    cur = ovw.get(now)
    if not cur or action not in cur["actions"]:
        return False, "这个动作不在当前面板上（可能已经处理过，或面板是旧的）"
    parts = parse_credit(action)
    if not parts:
        return False, "动作格式不对"
    path = ovw.credits_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime(now))
    with path.open("a", encoding="utf-8") as fh:
        for k, p in parts:
            fh.write(f"{k} = {p}  # lintel {stamp}\n")
    ovw.memo_key = None
    return True, f"记下 {len(parts)} 条方法署名"
