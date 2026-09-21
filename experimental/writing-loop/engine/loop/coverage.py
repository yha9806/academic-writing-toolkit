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
from . import history as H
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
    """The draft's files at head, by the index's own rule (history._draft_at): a list names every file of one draft;
    a glob names one file per version and only the highest-numbered is the draft. A check that read the superseded
    versions too would report on text nobody is revising."""
    got = H._draft_at(cfg, head)
    if not got:
        return []
    return list(got) if isinstance(got, list) else [got]


def also_checked(cfg):
    """Files that are submitted with the draft but not tracked sentence by sentence (a supplement, an appendix):
    whole-text checks read them, and a change to them makes those checks stale."""
    return list(K.get(cfg, "inputs.also_checked") or [])


def check_inputs(check, cfg):
    """{role: repo path} a check reads besides the draft: its own inputs, plus the also-checked files for a check
    whose scope is the whole text."""
    out = dict(check["inputs"](cfg))
    if check["scope"]["kind"] == "all":
        out.update({f"also{i}": q for i, q in enumerate(also_checked(cfg))})
    return out


def optional_inputs(check, cfg, head):
    """{role: repo path} the check reads when the repository has them (reading notes beside Markdown chapters)."""
    opt = check.get("optional")
    if not opt:
        return {}
    return {r: p for r, p in opt(cfg).items() if _git(cfg["repo"], "cat-file", "-e", f"{head}:{p}") is not None}


def waivers(ws):
    """Waivers count only from the workspace's human/ folder, which the hooks refuse to let the agent write: a
    decision not to run a check is the author's. A waiver in config.json is reported and ignored."""
    try:
        d = json.loads((Path(ws) / "human" / "waivers.json").read_text(encoding="utf-8"))
        return {k: str(v) for k, v in d.items() if str(v).strip()} if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


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


def _scope_sentences(check, cfg, sentences):
    kind = check["scope"]["kind"]
    fmt = draft_format(cfg)
    if kind in ("none", "tree"):
        return []
    if kind == "all":
        return list(sentences)
    if kind == "cite":
        if fmt != "latex":
            # Markdown citations take many forms (author-year in and outside brackets, [@key]); the checks' own
            # extractors find more than any one pattern here, so a Markdown citation check watches the whole text.
            return list(sentences)
        return [s for s in sentences if CITE["latex"].search(s["text"])]
    if kind == "numbers":
        return [s for s in sentences if DIGIT.search(s["text"])]
    if kind == "sections":
        prefixes = K.get(cfg, check["scope"]["config"]) or check["scope"]["default"]
        return [s for s in sentences if in_sections(s.get("section"), prefixes)]
    raise ValueError(f"unknown scope kind {kind}")


def scope_of(check, cfg, sentences):
    """{sid: hash} for the indexed sentences whose change makes this check stale."""
    return {s["sid"]: s["hash"] for s in _scope_sentences(check, cfg, sentences)}


def order_of(check, cfg, sentences):
    """The sequence of those sentences with their section and paragraph: a reordering or a merge of paragraphs
    changes what a reader (or a sentence-rhythm measure) sees without changing any sentence."""
    seq = [[s["sid"], s.get("section"), s.get("par")] for s in _scope_sentences(check, cfg, sentences)]
    return _sha(json.dumps(seq)) if seq else None


def unindexed_of(check, cfg, head):
    """What the index cannot see but the check reads: text outside the indexed sections (a preamble's keywords,
    a section with no rule). For a whole-text check, every draft file's blob; for a citation or number check, the
    draft's lines that carry a citation or a digit."""
    kind = check["scope"]["kind"]
    if kind == "tree":
        return {"tree": _git(cfg["repo"], "rev-parse", f"{head}^{{tree}}")}
    if kind == "all" or (kind == "cite" and draft_format(cfg) != "latex"):
        return {f: _git(cfg["repo"], "rev-parse", f"{head}:{f}") for f in draft_files(cfg, head)}
    if kind in ("cite", "numbers"):
        rx = CITE.get(draft_format(cfg), CITE["markdown"]) if kind == "cite" else DIGIT
        lines = []
        for f in draft_files(cfg, head):
            text = _git(cfg["repo"], "show", f"{head}:{f}") or ""
            lines += [f"{f}\0{ln}" for ln in text.splitlines() if rx.search(ln)]
        return {"lines": _sha("\n".join(lines))}
    return {}


_OUTSIDE_CACHE = {}


def outside_hash(path):
    """A file or a directory by content (a directory: every file's relative path and bytes). A missing path: None.
    Content, not size: a replaced PDF of the same size is a different corpus. File digests are memoised on
    (path, size, mtime) for the life of the process."""
    p = Path(path)

    def file_digest(q):
        st = q.stat()
        key = (str(q), st.st_size, st.st_mtime_ns)
        if key not in _OUTSIDE_CACHE:
            _OUTSIDE_CACHE[key] = _sha(q.read_bytes())
        return _OUTSIDE_CACHE[key]
    if p.is_file():
        return file_digest(p)
    if p.is_dir():
        rows = sorted(f"{q.relative_to(p)}\0{file_digest(q)}" for q in p.rglob("*") if q.is_file())
        return _sha("\n".join(rows))
    return None


def script_hash(check):
    """The check's scripts and everything beside them: a skill's scripts directory is hashed whole, because a
    script's behaviour lives in the libraries it imports from there too."""
    h = hashlib.sha1()
    if check.get("project"):
        # A project check's "script" is its definition in the workspace, and any file outside the repository its
        # command names (a script kept elsewhere): a changed command or a changed outside script is a different check.
        h.update(json.dumps(check.get("definition"), sort_keys=True, ensure_ascii=False).encode())
        for a in (check.get("definition") or {}).get("argv") or []:
            q = Path(str(a)).expanduser()
            if q.is_absolute() and q.is_file():
                h.update(str(q).encode() + b"\0" + q.read_bytes())
    for s in check["scripts"]:
        p = K.script_path(s)
        files = [p] if (Path(s).is_absolute() or s.startswith("scripts/")) else \
            sorted(q for q in p.parent.rglob("*") if q.is_file() and "__pycache__" not in q.parts)
        for q in files:
            h.update(str(q.name).encode() + b"\0" + (q.read_bytes() if q.is_file() else b"<missing>"))
    return h.hexdigest()


def config_hash(check, cfg):
    """The configuration this check's run depends on, and nothing else: its prerequisites, the keys it declares it
    reads, the paths of its inputs and the draft rule. An unrelated change must not make an expensive check (a paid
    reader panel) stale."""
    keep = {"needs": {n: K.get(cfg, n) for n in check["needs"]},
            "keys": {n: K.get(cfg, n) for n in check.get("config_keys") or []},
            "inputs": check_inputs(check, cfg),
            "draft": {k: cfg["draft"].get(k) for k in ("glob", "format")}}
    return _sha(json.dumps(keep, sort_keys=True, ensure_ascii=False, default=str))


def snapshot(check, cfg, sentences, head):
    """What a run of this check at head looks at. Two runs with equal snapshots would see the same thing."""
    inputs = {role: _git(cfg["repo"], "rev-parse", f"{head}:{path}") for role, path in check_inputs(check, cfg).items()}
    for role, path in (check.get("optional") or (lambda c: {}))(cfg).items():
        inputs[f"?{role}"] = _git(cfg["repo"], "rev-parse", f"{head}:{path}")
    return {"scope": scope_of(check, cfg, sentences),
            "order": order_of(check, cfg, sentences),
            "unindexed": unindexed_of(check, cfg, head),
            "inputs": inputs,
            "outside": {q: outside_hash(q) for q in check["outside"](cfg)},
            "script": script_hash(check),
            "config": config_hash(check, cfg)}


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
    elif old.get("order") != new["order"]:
        reasons.append("句子顺序或分段变了")
    if old.get("unindexed") != new["unindexed"]:
        reasons.append("索引外的正文变了")
    for role in sorted(set(old.get("inputs") or {}) | set(new["inputs"])):
        if (old.get("inputs") or {}).get(role) != new["inputs"].get(role):
            reasons.append(f"输入 {role} 变了")
    for q in sorted(set(old.get("outside") or {}) | set(new["outside"])):
        if (old.get("outside") or {}).get(q) != new["outside"].get(q):
            reasons.append(f"外部文件 {Path(q).name} 变了")
    if old.get("script") != new["script"]:
        reasons.append("检查脚本本身改过")
    if old.get("config") != new["config"]:
        reasons.append("工作区配置改过")
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
    if isinstance(data, dict) and data.get("citations_checked") and data.get("notes_sources_indexed") == 0:
        # Citations were checked against no reading notes at all: every quote went unverified.
        return "failed", f"查了 {data['citations_checked']} 条引用，却一份阅读笔记都没读到"
    if code not in (0, 1):
        return "failed", f"退出码 {code}：" + ((stderr or "").strip().splitlines() or [first or "（无输出）"])[-1][:160]
    if not isinstance(data, dict):
        # Every catalogued check is run with --json and prints its result as one object. Exit 0 or 1 without one is
        # a crash (a traceback, a malformed ledger's error line, a missing file): nothing was examined.
        tail = ((stderr or "").strip().splitlines() or [first or "（无输出）"])[-1][:160]
        return "failed", f"退出码 {code} 却没有给出结果：{tail}"
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
    if check.get("project"):
        tar = _git(cfg["repo"], "archive", head, binary=True)
        if tar is None:
            return None, "git archive 失败"
        return _extract(tar, dest, {})
    inputs = check_inputs(check, cfg)
    missing = [f"{role}={p}" for role, p in inputs.items() if _git(cfg["repo"], "cat-file", "-e", f"{head}:{p}") is None]
    if missing:
        return None, "配置的输入在 HEAD 上不存在：" + "，".join(missing)
    paths = sorted(set(draft_files(cfg, head)) | set(inputs.values()) | set(optional_inputs(check, cfg, head).values()))
    if not paths:
        return None, "HEAD 上没有草稿文件"
    tar = _git(cfg["repo"], "archive", head, "--", *paths, binary=True)
    if tar is None:
        return None, "git archive 失败"
    return _extract(tar, dest, inputs)


def _extract(tar, dest, inputs):
    """Unpack an archive for one check. A member the safe filter refuses (a symlink out of the repository, say a
    bibliography linked to a reference manager's export) fails this check with its name, never the whole summary."""
    try:
        tarfile.open(fileobj=io.BytesIO(tar)).extractall(dest, filter="data")
    except (tarfile.TarError, OSError) as e:
        return None, f"打包的稿件解不开（{type(e).__name__}：{str(e)[:120]}）；仓里若有指向仓外的链接，检查读不到它指的内容"
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
            r = subprocess.run(argv, cwd=tmp, capture_output=True, text=True,
                               timeout=check.get("timeout") or timeout)
            if check.get("project"):
                # A project's own script makes no JSON promise: pass or not, with its last line as the reason.
                last = ((r.stdout or "") + (r.stderr or "")).strip().splitlines()[-1:] or ["（无输出）"]
                verdict, summary = ("ok", "通过") if r.returncode == 0 else ("failed", f"退出码 {r.returncode}：{last[0][:160]}")
            else:
                verdict, summary = interpret(check["id"], r.returncode, r.stdout, r.stderr)
            rec.update({"exit": r.returncode, "verdict": verdict, "summary": summary})
            if r.stdout and r.stdout.lstrip().startswith("{"):
                try:
                    rec["result"] = json.loads(r.stdout)
                except ValueError:
                    pass
        except subprocess.TimeoutExpired:
            rec.update({"exit": None, "verdict": "failed", "summary": f"超时（{check.get('timeout') or timeout} 秒）"})
        except OSError as e:
            rec.update({"exit": None, "verdict": "failed", "summary": f"起不来：{e}"})
        rec["seconds"] = round(time.time() - t0, 2)
    save_run(ws, rec)
    return rec


# ---------------------------------------------------------------- status

def row(check, cfg, ws, head, sentences, index_head=None):
    base = {"id": check["id"], "name": check["name"], "kind": check["kind"]}
    fmt = draft_format(cfg)
    if fmt not in check["formats"]:
        instead = check["instead"].get(fmt)
        return {**base, "status": NOT_APPLICABLE, "instead": instead,
                "detail": (f"只读 {'/'.join(check['formats'])}；这里由 {instead} 覆盖" if instead
                           else f"只读 {'/'.join(check['formats'])}，这种稿件没有别的检查替它")}
    rec = load_run(ws, check["id"])
    reason = waivers(ws).get(check["id"])
    if reason:
        if rec is not None and rec.get("verdict") == "failed":
            # A waiver records a decision not to run a check; it does not turn a run that failed into a decision.
            return {**base, "status": FAILED, "detail": f"已豁免，但上次运行失败：{rec.get('summary') or ''}",
                    "due": False}
        return {**base, "status": WAIVED, "detail": str(reason)}
    missing = [n for n in check["needs"] if K.get(cfg, n) is None]
    if missing:
        return {**base, "status": MISSING, "detail": "配置里缺 " + "、".join(missing)}
    problems = TG.problems_for(check["id"], cfg)
    if problems:
        return {**base, "status": MISSING, "detail": "；".join(problems)}
    if not head:
        return {**base, "status": FAILED, "detail": f"ref {cfg.get('ref')} 解析不了，说不出查过哪一版", "due": False}
    if sentences is None:
        return {**base, "status": NEVER, "detail": "索引还没建，说不出查过什么"}
    if rec is None:
        if check.get("project"):
            detail = "由 loop update 自动跑" if check.get("auto") else f"项目检查，不自动跑：loop coverage <工作区> --run --only {check['id']}"
        elif check["kind"] == "script":
            detail = "由 loop update 自动跑"
        else:
            detail = f"按 {K.script_path(check['scripts'][0]).parent.parent / 'SKILL.md'} 开读者组"
        return {**base, "status": NEVER, "detail": detail}
    new = snapshot(check, cfg, sentences, head)
    reasons, n = diff(rec.get("snapshot") or {}, new)
    if index_head and index_head != head:
        # The sentences compared above are the index's, and the index is older than HEAD: nothing can be called
        # current until it catches up.
        reasons.insert(0, f"索引建于 {index_head[:7]}，落后于 HEAD {head[:7]}（先跑 loop update）")
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
    checks = K.all_checks(cfg)
    if do_run and sentences is not None and head:
        for check in checks:
            if only and check["id"] not in only:
                continue
            if not check.get("auto", True) and not (only and check["id"] in only):
                continue  # a slow project check runs only when named
            r = row(check, cfg, ws, head, sentences, index_head)
            if check["kind"] == "script" and (due(r) or (force and r["status"] in (OK, FAILED, STALE, NEVER))):
                run(check, cfg, ws, head, sentences, now=now)
                ran.append(check["id"])
    rows = [row(c, cfg, ws, head, sentences, index_head) for c in checks]
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    summary = {"schema": SCHEMA, "workspace": cfg["name"], "ref": cfg.get("ref"), "head": head,
               "index_head": index_head, "index_behind": bool(head and index_head and head != index_head),
               "computed_at": dt.datetime.fromtimestamp(now or time.time(), dt.timezone.utc).isoformat(),
               "format": draft_format(cfg), "rows": rows, "counts": counts, "ran": ran,
               "fingerprint": fingerprint(cfg, ws),
               "config_waivers_ignored": sorted((cfg.get("waive") or {}).keys()),
               "target": TG.describe(cfg),
               "experiments": TG.experiments(cfg),
               "unwired": [{"script": k, "reason": v} for k, v in sorted(K.UNWIRED.items())]}
    d = Path(ws) / "cache" / "coverage"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".summary.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(d / "summary.json")
    return summary


STATUSES = (OK, STALE, NEVER, MISSING, NOT_APPLICABLE, WAIVED, FAILED)


def _stat_sig(path):
    p = Path(path)
    if p.is_file():
        st = p.stat()
        return [st.st_size, st.st_mtime_ns]
    if p.is_dir():
        return _sha("\n".join(f"{q.relative_to(p)}\0{q.stat().st_size}\0{q.stat().st_mtime_ns}"
                               for q in sorted(p.rglob("*")) if q.is_file()))
    return None


def fingerprint(cfg, ws):
    """A cheap digest of everything besides HEAD that a summary's rows depend on: the checks and their scripts,
    each check's configuration, the files read in place (by size and time, not content: this runs every turn),
    and the author's waivers. A summary whose fingerprint no longer matches is not current."""
    rows = [[c["id"], script_hash(c), config_hash(c, cfg), [_stat_sig(p) for p in c["outside"](cfg)]]
            for c in K.all_checks(cfg)]
    rows.append(["_waivers", sorted(waivers(ws).items())])
    return _sha(json.dumps(rows, ensure_ascii=False, default=str))


def load_summary(ws, cfg=None):
    """The summary on disk, or None when there is none or it cannot be trusted: another schema, another workspace,
    rows of the wrong shape or an unknown status. With cfg, a summary computed for an older HEAD is marked
    (`stale_head`), and every surface then treats coverage as not current."""
    try:
        s = json.loads((Path(ws) / "cache" / "coverage" / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    ok = (isinstance(s, dict) and s.get("schema") == SCHEMA and isinstance(s.get("rows"), list) and s["rows"]
          and all(isinstance(r, dict) and r.get("status") in STATUSES and r.get("name") for r in s["rows"]))
    if not ok or (cfg and s.get("workspace") != cfg.get("name", s.get("workspace"))):
        return None
    if cfg and cfg.get("draft"):
        # A full config: every check must have its row, and nothing a row depends on may have moved.
        if {c["id"] for c in K.all_checks(cfg)} - {r.get("id") for r in s["rows"]}:
            return None
        try:
            if fingerprint(cfg, ws) != s.get("fingerprint"):
                s["stale_inputs"] = True
        except Exception:  # noqa: BLE001 -- an unreadable input is itself a reason not to trust the summary
            s["stale_inputs"] = True
    if cfg and cfg.get("repo") and cfg.get("ref"):
        now = _git(cfg["repo"], "rev-parse", "--verify", f"{cfg['ref']}^{{commit}}")
        if now != s.get("head"):
            s["stale_head"] = now or "?"
    return s


# ---------------------------------------------------------------- the three places it is shown

def attention(summary):
    """The rows this manuscript's work can act on: not current, never run, missing a prerequisite, failed. A summary
    computed for an older HEAD, or from an index behind HEAD, is itself a row: nothing in it is current."""
    out = []
    if summary.get("stale_head"):
        out.append({"id": "_summary", "name": "覆盖摘要", "status": STALE,
                    "detail": f"算于 {(summary.get('head') or '?')[:7]}，HEAD 已到 {summary['stale_head'][:7]}"})
    elif summary.get("stale_inputs"):
        out.append({"id": "_summary", "name": "覆盖摘要", "status": STALE,
                    "detail": "检查脚本、配置、外部文件或豁免在摘要之后变了"})
    # Failures first: when the line is cut, what drops off is the least severe.
    order = {FAILED: 0, STALE: 1, NEVER: 2, MISSING: 3}
    return out + sorted((r for r in summary["rows"] if r["status"] in ATTENTION), key=lambda r: order[r["status"]])


def gaps(summary):
    """Checks the toolkit has that cannot read this kind of draft, with nothing covering for them. A gap in the
    toolkit, not a task for this turn: listed in the table, counted on the notch and in the to-do cell, kept out of
    the per-turn line so the line does not become wallpaper the agent learns to skip."""
    return [r for r in summary["rows"] if r["status"] == NOT_APPLICABLE and not r.get("instead")]


def waived(summary):
    return [r for r in summary["rows"] if r["status"] == WAIVED]


def findings(summary):
    """Checks that looked at the current draft and found something. Looking is not the same as acting on it."""
    return [r for r in summary["rows"] if r["status"] == OK and r.get("verdict") == "findings"]


def _short(text, limit=28):
    """The first clause of a detail, never cut inside a word or a config key."""
    first = re.split(r"[；;：:]", text or "", maxsplit=1)[0].strip()
    return first if len(first) <= limit else first[: limit].rsplit(" ", 1)[0].rstrip("、，,") + "…"


def _name(r):
    d = r.get("detail") or ""
    if r["status"] == MISSING and d.startswith("配置里缺 "):
        return f"{r['name']}（{d[len('配置里缺 '):]}）"
    return r["name"] + (f"（{_short(d)}）" if r["status"] in (STALE, MISSING, FAILED) and d else "")


def reminder_line(summary, ws):
    """One line for the agent's context, or None when there is nothing to say."""
    if summary is None:
        return f"覆盖：还没有算过（loop coverage {ws} --run）。"
    rows = attention(summary)
    t, e = summary.get("target") or {}, summary.get("experiments") or {}
    bits = []
    for status in (FAILED, STALE, NEVER, MISSING):
        xs = [_name(r) for r in rows if r["status"] == status]
        if xs:
            bits.append(f"{status} " + "、".join(xs))
    found = findings(summary)
    if found:
        bits.append("有发现 " + "、".join(f"{r['name']}（{_short(r.get('result'))}）" for r in found[:3])
                    + (f" 等 {len(found)} 项" if len(found) > 3 else ""))
    wv = waived(summary)
    if wv:
        bits.append("已豁免 " + "、".join(f"{r['name']}（{_short(r.get('detail'), 16)}）" for r in wv))
    if summary.get("config_waivers_ignored"):
        bits.append("config.json 里的豁免不生效（豁免只认 human/waivers.json）："
                    + "、".join(summary["config_waivers_ignored"]))
    if t.get("problems"):
        bits.append("目标档案：" + "；".join(t["problems"]))
    pending = (e.get("undisposed") or []) + (e.get("overdue") or []) + (e.get("promoted_missing") or [])
    if pending:
        bits.append(f"原型待处置 {len(pending)}（{'、'.join(pending[:3])}）")
    if not bits:
        return None
    line = f"覆盖（{(summary.get('head') or '')[:7]}）：" + "；".join(bits)
    return line[:420] + f"。全表：loop coverage {ws}"


def todo_cell(summary):
    """The overview's 还差什么 cell for coverage: counts, and the first names."""
    if summary is None:
        return {"title": "检查", "text": "没算过", "value": "没算过", "sub": "loop coverage --run", "tone": "orange"}
    rows, gap, found, wv = attention(summary), gaps(summary), findings(summary), waived(summary)
    target = (summary.get("target") or {}).get("problems")
    running = len((summary.get("experiments") or {}).get("in_progress") or [])
    c = {}
    for r in rows:
        c[r["status"]] = c.get(r["status"], 0) + 1
    tail = ((f"；有发现 {len(found)} 项" if found else "") + (f"；另有 {len(gap)} 项 AWT 读不了这种稿件" if gap else "")
            + (f"；豁免 {len(wv)} 项" if wv else "") + (f"；原型进行中 {running}" if running else ""))
    if not rows and not target:
        if not gap and not wv:
            return {"title": "检查", "text": "都查过当前稿", "sub": ("按改动自动判过期" + tail)[:120],
                    "value": "全部最新", "tone": "white"}
        # Everything that ran has looked at this draft, but not everything the toolkit has: say which, and never
        # call a waived check "checked".
        value = f"豁免 {len(wv)}" if wv else f"缺口 {len(gap)}"
        text = "没豁免的都查过当前稿" if wv else "能跑的都查过当前稿"
        return {"title": "检查", "text": text, "sub": tail.lstrip("；")[:120], "value": value, "tone": "white"}
    text = " · ".join(f"{k} {v}" for k, v in c.items()) or "目标档案有问题"
    names = "、".join(r["name"] for r in rows[:3])
    return {"title": "检查", "text": text[:64], "sub": (names + tail)[:120], "value": text[:16], "tone": "orange"}


def table(summary, ws):
    """The terminal view."""
    lines = [f"覆盖 · {summary['workspace']} · HEAD {(summary.get('head') or '?')[:7]} · 格式 {summary['format']}"]
    if summary.get("index_behind"):
        lines.append(f"  注意：索引建于 {(summary.get('index_head') or '?')[:7]}，落后于 HEAD；先跑 loop update")
    w = max(len(r["name"]) for r in summary["rows"]) + 2
    for r in summary["rows"]:
        last = f" · 上次 {r['last_commit']}" if r.get("last_commit") else ""
        res = f" · {r['result']}" if r.get("result") and r["status"] == STALE else ""
        lines.append(f"  {r['status']:<4} {r['name']:<{w}} {r.get('detail', '')}{last}{res}".rstrip())
    t = summary.get("target") or {}
    lines.append("目标档案：" + ("；".join(t["problems"]) if t.get("problems") else (t.get("line") or "—")))
    e = summary.get("experiments")
    if e:
        bad = e["undisposed"] + e["overdue"] + e.get("promoted_missing", [])
        lines.append(f"原型：{e['total']} 个，未处置 {len(e['undisposed'])}，逾期 {len(e['overdue'])}，"
                     f"晋升目标不存在 {len(e.get('promoted_missing', []))}，进行中 {len(e['in_progress'])}"
                     + (f"（{'、'.join(bad)}）" if bad else "")
                     + ("；进行中：" + "、".join(f"{n}（复查 {d}）" for n, d in e["in_progress"]) if e["in_progress"] else ""))
    gap = gaps(summary)
    if gap:
        lines.append("AWT 读不了这种稿件、也没有别的检查替它的（工具的缺口，不是这篇稿子的待办）：" + "、".join(r["name"] for r in gap))
    lines.append("由模型阅读完成、循环没有运行记录的检查（catalogue.MODEL_READ）：")
    for k, v in sorted(K.MODEL_READ.items()):
        lines.append(f"  {v}")
    lines.append("不接进循环的检查（理由写在 catalogue.UNWIRED）：")
    for u in summary["unwired"]:
        lines.append(f"  {u['script']}：{u['reason']}")
    return "\n".join(lines)
