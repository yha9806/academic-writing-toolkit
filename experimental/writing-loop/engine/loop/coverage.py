"""Coverage: for every check in the catalogue, has it looked at the draft as it is now?

Nothing here is a standing table. The status of each check is computed from three things that already exist: the
index (the tracked draft, sentence by sentence, with a stable id and a text hash), the record of that check's last
run (cache/coverage/runs/<id>.json, written by the run itself), and the workspace config. Delete the cache and the
answer becomes 从未运行, which is true.

A status is one of the constants below, and only 最新 is green. In particular a check that cannot read this draft's
format, lacks a prerequisite, was waived, failed, or never ran is shown as such; none of them is ever reported as
up to date. That is the property this module exists for: a capability that sits beside a manuscript without being
run on it has to be visible, in the terminal, on the notch, and in the line the agent reads every turn.
"""
import datetime as dt
import fnmatch
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path

from . import catalogue as K
from . import targets as TG

OK = "最新"
STALE = "过期"
NEVER = "从未运行"
MISSING = "缺前提"
NOT_APPLICABLE = "不适用"
WAIVED = "已豁免"
FAILED = "失败"
ATTENTION = (STALE, NEVER, MISSING, FAILED)
TIMEOUT = 60
SCHEMA = 1

CITE = {"latex": re.compile(r"\\[a-zA-Z]*cite[a-zA-Z]*\*?(?:\[[^\]]*\])*\{"),
        "markdown": re.compile(r"\[@[^\]]+\]|\([A-Z][A-Za-z'’\-]+(?: et al\.)?(?:,| and [A-Z][A-Za-z'’\-]+,)? \d{4}")}
DIGIT = re.compile(r"\d")


# ---------------------------------------------------------------- inputs

def _git(repo, *args, binary=False):
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if r.returncode:
        return None
    return r.stdout if binary else r.stdout.decode("utf-8", "replace").strip()


def _sha(data):
    return hashlib.sha1(data if isinstance(data, bytes) else data.encode("utf-8")).hexdigest()


def draft_format(cfg):
    return cfg["draft"].get("format") or "markdown"


def draft_files(cfg, head):
    """The draft's files at head, by the same rule the index uses (a list of paths, or one glob)."""
    names = (_git(cfg["repo"], "ls-tree", "-r", "--name-only", head) or "").splitlines()
    g = cfg["draft"]["glob"]
    if isinstance(g, list):
        have = set(names)
        return [p for p in g if p in have]
    return [p for p in names if fnmatch.fnmatch(p, g)]


def current_sentences(ws):
    """The latest version's sentences from the index on disk, and the head it was built from. (None, None) if the
    index is not there: coverage then refuses to say anything is up to date."""
    try:
        d = json.loads((Path(ws) / "index" / "sentences.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, None
    vs = d.get("versions") or []
    return (vs[-1]["sentences"] if vs else []), d.get("head")


def in_sections(sec, prefixes):
    """A sentence of section `sec` belongs to prefix p if it is p or a subsection of p (p + lower-case letters)."""
    sec = sec or ""
    for p in prefixes:
        rest = sec[len(p):]
        if sec == p or (sec.startswith(p) and rest.isalpha() and rest.islower()):
            return True
    return False


def scope_of(check, cfg, sentences):
    """{sid: hash} for the sentences whose change makes this check stale."""
    kind = check["scope"]["kind"]
    fmt = draft_format(cfg)
    if kind == "none":
        return {}
    if kind == "all":
        keep = sentences
    elif kind == "cite":
        rx = CITE.get(fmt, CITE["markdown"])
        keep = [s for s in sentences if rx.search(s["text"])]
    elif kind == "numbers":
        keep = [s for s in sentences if DIGIT.search(s["text"])]
    elif kind == "sections":
        prefixes = K.get(cfg, check["scope"]["config"]) or check["scope"]["default"]
        keep = [s for s in sentences if in_sections(s.get("section"), prefixes)]
    else:
        raise ValueError(f"unknown scope kind {kind}")
    return {s["sid"]: s["hash"] for s in keep}


def outside_hash(path):
    """A file: its bytes. A directory: the names and sizes of its files (a corpus of PDFs is not re-read each time).
    Missing: None."""
    p = Path(path)
    if p.is_file():
        return _sha(p.read_bytes())
    if p.is_dir():
        rows = sorted(f"{q.relative_to(p)}\0{q.stat().st_size}" for q in p.rglob("*") if q.is_file())
        return _sha("\n".join(rows))
    return None


def script_hash(check):
    h = hashlib.sha1()
    for s in check["scripts"]:
        p = K.script_path(s)
        h.update(s.encode() + b"\0" + (p.read_bytes() if p.is_file() else b"<missing>"))
    return h.hexdigest()


def snapshot(check, cfg, sentences, head):
    """What a run of this check at head looks at. Two runs with equal snapshots would see the same thing."""
    inputs = {role: _git(cfg["repo"], "rev-parse", f"{head}:{path}") for role, path in check["inputs"](cfg).items()}
    return {"scope": scope_of(check, cfg, sentences),
            "inputs": inputs,
            "outside": {p: outside_hash(p) for p in check["outside"](cfg)},
            "script": script_hash(check)}


def diff(old, new):
    """Reasons a past snapshot no longer matches, and how many scope sentences changed."""
    reasons, n = [], 0
    o, c = old.get("scope") or {}, new["scope"]
    edited = sum(1 for k in o.keys() & c.keys() if o[k] != c[k])
    added, removed = len(c.keys() - o.keys()), len(o.keys() - c.keys())
    n = edited + added + removed
    if n:
        parts = [f"改 {edited}" if edited else "", f"新增 {added}" if added else "", f"删 {removed}" if removed else ""]
        reasons.append("句子" + " ".join(x for x in parts if x))
    for role in sorted(set(old.get("inputs") or {}) | set(new["inputs"])):
        if (old.get("inputs") or {}).get(role) != new["inputs"].get(role):
            reasons.append(f"输入 {role} 变了")
    for p in sorted(set(old.get("outside") or {}) | set(new["outside"])):
        if (old.get("outside") or {}).get(p) != new["outside"].get(p):
            reasons.append(f"外部文件 {Path(p).name} 变了")
    if old.get("script") != new["script"]:
        reasons.append("检查脚本本身改过")
    return reasons, n


# ---------------------------------------------------------------- records

def runs_dir(ws):
    return Path(ws) / "cache" / "coverage" / "runs"


def load_run(ws, cid):
    try:
        return json.loads((runs_dir(ws) / f"{cid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def save_run(ws, rec):
    d = runs_dir(ws)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{rec['id']}.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(rec, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    tmp.replace(d / f"{rec['id']}.json")


def interpret(check_id, code, stdout, stderr):
    """(verdict, summary). verdict: ok | findings | failed. Exit 2 is never a pass: it means nothing was examined or
    a precondition failed, and the check says so on stderr."""
    first = next((x.strip() for x in (stdout or stderr or "").splitlines() if x.strip()), "")
    try:
        data = json.loads(stdout) if stdout and stdout.lstrip().startswith("{") else None
    except ValueError:
        data = None
    if code == 2:
        return "failed", "没有查到任何对象或前提不满足（退出码 2）：" + (stderr.strip().splitlines() or [first])[-1][:160]
    if code not in (0, 1):
        return "failed", f"退出码 {code}：" + ((stderr or "").strip().splitlines() or [first or "（无输出）"])[-1][:160]
    summary = ""
    if isinstance(data, dict):
        if "outliers" in data:
            out = data.get("outliers") or []
            summary = f"越界 {len(out)} 项" + (f"：{', '.join(out)}" if out else "")
        elif "hard_finding_count" in data:
            summary = f"硬错 {data['hard_finding_count']}"
        else:
            for key in ("issues", "findings", "problems", "errors"):
                if isinstance(data.get(key), list):
                    summary = f"{len(data[key])} 条"
                    break
    return ("ok" if code == 0 else "findings"), (summary or first[:160] or ("通过" if code == 0 else "有发现"))


def materialize(cfg, check, head, dest):
    """Archive the draft and the check's inputs at head into dest. Returns ({role: path}, error or None)."""
    inputs = check["inputs"](cfg)
    missing = [f"{role}={p}" for role, p in inputs.items() if _git(cfg["repo"], "cat-file", "-e", f"{head}:{p}") is None]
    if missing:
        return None, "配置的输入在 HEAD 上不存在：" + "，".join(missing)
    paths = sorted(set(draft_files(cfg, head)) | set(inputs.values()))
    if not paths:
        return None, "HEAD 上没有草稿文件"
    tar = _git(cfg["repo"], "archive", head, "--", *paths, binary=True)
    if tar is None:
        return None, "git archive 失败"
    tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest, filter="data")
    return inputs, None


def run(check, cfg, ws, head, sentences, now=None, timeout=TIMEOUT):
    """Run one script check at head and record it. The record is written whatever happens, a failure included."""
    now = now or time.time()
    snap = snapshot(check, cfg, sentences, head)
    rec = {"id": check["id"], "commit": head, "at": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(),
           "snapshot": snap}
    with tempfile.TemporaryDirectory(prefix="loop-coverage-") as tmp:
        inputs, err = materialize(cfg, check, head, tmp)
        if err:
            rec.update({"verdict": "failed", "summary": err, "exit": None})
            save_run(ws, rec)
            return rec
        ctx = {"cfg": cfg, "ws": str(ws), "tmp": tmp, "inputs": inputs, "head": head}
        argv = check["argv"](ctx)
        rec["argv"] = [a.replace(tmp, "<draft>") for a in argv]
        t0 = time.time()
        try:
            r = subprocess.run(argv, cwd=tmp, capture_output=True, text=True, timeout=timeout)
            verdict, summary = interpret(check["id"], r.returncode, r.stdout, r.stderr)
            rec.update({"exit": r.returncode, "verdict": verdict, "summary": summary})
            if r.stdout and r.stdout.lstrip().startswith("{"):
                try:
                    rec["result"] = json.loads(r.stdout)
                except ValueError:
                    pass
        except subprocess.TimeoutExpired:
            rec.update({"exit": None, "verdict": "failed", "summary": f"超时（{timeout} 秒）"})
        except OSError as e:
            rec.update({"exit": None, "verdict": "failed", "summary": f"起不来：{e}"})
        rec["seconds"] = round(time.time() - t0, 2)
    save_run(ws, rec)
    return rec


# ---------------------------------------------------------------- status

def row(check, cfg, ws, head, sentences):
    base = {"id": check["id"], "name": check["name"], "kind": check["kind"]}
    fmt = draft_format(cfg)
    if fmt not in check["formats"]:
        instead = check["instead"].get(fmt)
        return {**base, "status": NOT_APPLICABLE, "instead": instead,
                "detail": (f"只读 {'/'.join(check['formats'])}；这里由 {instead} 覆盖" if instead
                           else f"只读 {'/'.join(check['formats'])}，这种稿件没有别的检查替它")}
    reason = (cfg.get("waive") or {}).get(check["id"])
    if reason:
        return {**base, "status": WAIVED, "detail": str(reason)}
    missing = [n for n in check["needs"] if K.get(cfg, n) is None]
    if missing:
        return {**base, "status": MISSING, "detail": "配置里缺 " + "、".join(missing)}
    problems = TG.problems_for(check["id"], cfg)
    if problems:
        return {**base, "status": MISSING, "detail": "；".join(problems)}
    if sentences is None:
        return {**base, "status": NEVER, "detail": "索引还没建，说不出查过什么"}
    rec = load_run(ws, check["id"])
    if rec is None:
        return {**base, "status": NEVER, "detail": "由 loop update 自动跑" if check["kind"] == "script"
                else "要由宿主代理开读者组（readers 技能）"}
    new = snapshot(check, cfg, sentences, head)
    reasons, n = diff(rec.get("snapshot") or {}, new)
    last = {"last_commit": (rec.get("commit") or "")[:7], "last_at": rec.get("at"), "result": rec.get("summary"),
            "verdict": rec.get("verdict")}
    if rec.get("verdict") == "failed":
        return {**base, **last, "status": FAILED, "changed": n, "detail": rec.get("summary") or "失败",
                "due": bool(reasons)}
    if reasons:
        return {**base, **last, "status": STALE, "changed": n, "detail": "；".join(reasons)}
    return {**base, **last, "status": OK, "changed": 0, "detail": rec.get("summary") or ""}


def due(r):
    """A script check the loop should run now."""
    return r["kind"] == "script" and (r["status"] in (NEVER, STALE) or (r["status"] == FAILED and r.get("due")))


def compute(cfg, ws, do_run=False, now=None, only=None, force=False):
    """Rows for every check, running the due script checks first when do_run. Writes cache/coverage/summary.json."""
    sentences, index_head = current_sentences(ws)
    head = _git(cfg["repo"], "rev-parse", "--verify", f"{cfg['ref']}^{{commit}}")
    ran = []
    if do_run and sentences is not None and head:
        for check in K.CHECKS:
            if only and check["id"] not in only:
                continue
            r = row(check, cfg, ws, head, sentences)
            if check["kind"] == "script" and (due(r) or (force and r["status"] in (OK, FAILED, STALE, NEVER))):
                run(check, cfg, ws, head, sentences, now=now)
                ran.append(check["id"])
    rows = [row(c, cfg, ws, head, sentences) for c in K.CHECKS]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    summary = {"schema": SCHEMA, "workspace": cfg["name"], "head": head, "index_head": index_head,
               "index_behind": bool(head and index_head and head != index_head),
               "computed_at": dt.datetime.fromtimestamp(now or time.time(), dt.timezone.utc).isoformat(),
               "format": draft_format(cfg), "rows": rows, "counts": counts, "ran": ran,
               "target": TG.describe(cfg),
               "experiments": TG.experiments(cfg),
               "unwired": [{"script": k, "reason": v} for k, v in sorted(K.UNWIRED.items())]}
    d = Path(ws) / "cache" / "coverage"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".summary.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / "summary.json")
    return summary


def load_summary(ws):
    try:
        return json.loads((Path(ws) / "cache" / "coverage" / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------- the three places it is shown

def attention(summary):
    """The rows that are not green and are not a decision already written down (waived, or covered by another)."""
    out = [r for r in summary["rows"] if r["status"] in ATTENTION]
    out += [r for r in summary["rows"] if r["status"] == NOT_APPLICABLE and not r.get("instead")]
    return out


def _name(r):
    extra = f"（{r['detail'][:24]}）" if r["status"] in (STALE, MISSING, FAILED) and r.get("detail") else ""
    return r["name"] + extra


def reminder_line(summary, ws):
    """One line for the agent's context, or None when there is nothing to say."""
    if summary is None:
        return f"覆盖：还没有算过（loop coverage {ws} --run）。"
    rows = attention(summary)
    t, e = summary.get("target") or {}, summary.get("experiments") or {}
    bits = []
    for status in (STALE, NEVER, FAILED, MISSING):
        xs = [_name(r) for r in rows if r["status"] == status]
        if xs:
            bits.append(f"{status} " + "、".join(xs))
    orphan = [r["name"] for r in rows if r["status"] == NOT_APPLICABLE]
    if orphan:
        bits.append("这种稿件没人查 " + "、".join(orphan))
    if t.get("problems"):
        bits.append("目标档案：" + "；".join(t["problems"]))
    if e.get("undisposed") or e.get("overdue"):
        bits.append(f"原型待处置 {len(e.get('undisposed') or []) + len(e.get('overdue') or [])}")
    if summary.get("index_behind"):
        bits.append("索引落后于 HEAD")
    if not bits:
        return None
    line = f"覆盖（{(summary.get('head') or '')[:7]}）：" + "；".join(bits)
    return line[:420] + f"。全表：loop coverage {ws}"


def todo_cell(summary):
    """The overview's 还差什么 cell for coverage: counts, and the first names."""
    if summary is None:
        return {"title": "检查", "text": "没算过", "sub": "loop coverage --run", "tone": "orange"}
    rows = attention(summary)
    c = {}
    for r in rows:
        c[r["status"]] = c.get(r["status"], 0) + 1
    if not rows and not (summary.get("target") or {}).get("problems"):
        return {"title": "检查", "text": f"{len(summary['rows'])} 项都查过当前稿", "sub": "按改动自动判过期",
                "value": "全部最新", "tone": "white"}
    text = " · ".join(f"{k} {v}" for k, v in c.items())
    names = "、".join(r["name"] for r in rows[:3])
    return {"title": "检查", "text": text[:64] or "目标档案有问题", "sub": names[:120], "value": text[:16],
            "tone": "orange"}


def table(summary, ws):
    """The terminal view."""
    lines = [f"覆盖 · {summary['workspace']} · HEAD {(summary.get('head') or '?')[:7]} · 格式 {summary['format']}"]
    if summary.get("index_behind"):
        lines.append(f"  注意：索引建于 {(summary.get('index_head') or '?')[:7]}，落后于 HEAD；先跑 loop update")
    w = max(len(r["name"]) for r in summary["rows"]) + 2
    for r in summary["rows"]:
        last = f" · 上次 {r['last_commit']}" if r.get("last_commit") else ""
        res = f" · {r['result']}" if r.get("result") and r["status"] in (OK, STALE) else ""
        lines.append(f"  {r['status']:<4} {r['name']:<{w}} {r.get('detail', '')}{last}{res}".rstrip())
    t = summary.get("target") or {}
    lines.append("目标档案：" + ("；".join(t["problems"]) if t.get("problems") else (t.get("line") or "—")))
    e = summary.get("experiments")
    if e:
        lines.append(f"原型：{e['total']} 个实验，未处置 {len(e['undisposed'])}，逾期 {len(e['overdue'])}，"
                     f"进行中 {len(e['in_progress'])}"
                     + (f"（{'、'.join(e['undisposed'] + e['overdue'])}）" if e['undisposed'] or e['overdue'] else ""))
    lines.append("不接进循环的检查（理由写在 catalogue.UNWIRED）：")
    for u in summary["unwired"]:
        lines.append(f"  {u['script']}：{u['reason']}")
    return "\n".join(lines)
