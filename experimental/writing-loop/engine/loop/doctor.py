"""`loop doctor`: every configured path must resolve, or the command names the one that does not."""
import fnmatch
import json
import posixpath
import re

from . import config as C
from . import gitio
from . import transcripts as T
from .text import sentences_of


def draft_paths(cfg, commit):
    g = cfg["draft"]["glob"]
    if isinstance(g, list):  # a draft made of several files: all must exist
        return [p for p in g if gitio.ls_tree(cfg["repo"], commit, p)]
    names = gitio.ls_tree(cfg["repo"], commit, posixpath.dirname(g) or ".")
    return sorted([n for n in names if fnmatch.fnmatch(n, g)], key=C.version_key)


def transcript_files(cfg, cwd_prefix=None):
    t = cfg["transcripts"]
    root = C.expand(t["projects_dir"])
    prefix = C.escaped_project_dir(cwd_prefix or t["cwd_prefix"])
    if not root.is_dir():
        return None
    return sorted(p for d in root.iterdir() if d.is_dir() and d.name.startswith(prefix) for p in d.glob("*.jsonl"))


def all_transcript_files(cfg):
    """Every transcript file that can hold this manuscript's sessions: under the primary prefix, under each `also`
    prefix, and the files of the sessions named by id (transcripts.sessions). Approvals and the ring look up an author
    message by uuid here, so a message given in a named session is on record as one given under the prefix is."""
    t = cfg.get("transcripts") or {}
    files = list(transcript_files(cfg) or [])
    for s in t.get("also") or []:
        if isinstance(s, dict) and s.get("cwd_prefix"):
            files += list(transcript_files(cfg, s["cwd_prefix"]) or [])
    files += [p for found in T.named_files(cfg).values() for p in found]
    return list(dict.fromkeys(files))


def _branch_exists(cwd_prefix, branch):
    """Whether `branch` is a local branch of the repository the sessions would run in."""
    p = C.expand(cwd_prefix)
    if not p.is_dir() or not gitio.is_repo(p):
        return False
    return gitio._run(p, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}", check=False).returncode == 0


# 2026-10-08：常驻来源进程每轮都跑 doctor，这里原来把每个会话文件整份读进内存只为找一个分支名（一份稿子两个前缀下
# 44 个文件 1.8 GB，最大一份 375 MB，单这一步瞬时 375 MB）。现在分块读、找到就停；会话文件只会往后追加，
# 没找到的记下读到哪，下一轮只读新增的尾部。
_CHUNK = 1 << 20
_OVERLAP = 4096          # 一处命中被块边界切开时，下一块带着上一块的尾巴还能找到
_SCANNED = {}            # (文件, 分支) -> (已读到的大小, 是否找到)


def _holds(f, needle, key):
    try:
        size = f.stat().st_size
    except OSError:
        return False
    seen, hit = _SCANNED.get(key, (0, False))
    if seen > size:      # 文件被改短了：不是追加，从头读
        seen, hit = 0, False
    if hit:
        return True
    try:
        with open(f, "rb") as fh:
            fh.seek(max(0, seen - _OVERLAP))
            tail = b""
            while True:
                chunk = fh.read(_CHUNK)
                if not chunk:
                    break
                buf = tail + chunk
                if needle.search(buf):
                    _SCANNED[key] = (size, True)
                    return True
                tail = buf[-_OVERLAP:]
    except OSError:
        return False
    _SCANNED[key] = (size, False)
    return False


def _on_branch(files, branch):
    needle = re.compile(rb'"gitBranch"\s*:\s*' + re.escape(json.dumps(branch).encode()))
    return [f for f in files if _holds(f, needle, (str(f), branch))]


def run(ws):
    """Return (problems, facts). problems is a list of (item, message); empty means nothing was found missing."""
    problems, facts = [], []

    def bad(item, msg):
        problems.append((item, msg))

    try:
        cfg = C.load(ws)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        return [("config.json", f"读不出：{e}")], facts
    for sub in C.SUBDIRS:
        if not (C.Path(cfg["_ws"]) / sub).is_dir():
            bad(f"workspace/{sub}", "目录不存在")
    repo = cfg["repo"]
    if not gitio.is_repo(repo):
        bad("repo", f"不是 git 仓库：{repo}")
        return problems, facts
    try:
        head = gitio.rev_parse(repo, cfg["ref"])
        facts.append(("ref", f"{cfg['ref']} → {head[:7]}"))
    except gitio.GitError as e:
        bad("ref", str(e))
        return problems, facts
    drafts = draft_paths(cfg, head)
    if not drafts:
        bad("draft.glob", f"在 {head[:7]} 上没有匹配 {cfg['draft']['glob']} 的文件")
    else:
        multi = isinstance(cfg["draft"]["glob"], list)
        latest = "+".join(drafts) if multi else drafts[-1]
        text = "\n\n".join(gitio.show(repo, head, p) or "" for p in (drafts if multi else [drafts[-1]]))
        n = len(sentences_of(text, cfg["draft"]["sections"], cfg["draft"].get("format", "markdown")))
        facts.append(("draft", (f"{len(drafts)} 个文件合为一份" if multi else f"{len(drafts)} 个版本文件") + f"，最新 {latest}，{n} 句"))
        if n == 0:
            bad("draft.sections", f"{latest} 按 sections 规则切不出任何句子")
    led = cfg.get("ledger")
    if led:
        raw = gitio.show(repo, head, led["path"])
        if raw is None:
            bad("ledger.path", f"在 {head[:7]} 上不存在：{led['path']}")
        else:
            try:
                entries = json.loads(raw)
                facts.append(("ledger", f"{len(entries)} 条"))
            except json.JSONDecodeError as e:
                bad("ledger.path", f"不是 JSON：{e}")
        for key in ("evidence_dir", "keymap_from"):
            p = led.get(key)
            if p and not gitio.ls_tree(repo, head, p):
                bad(f"ledger.{key}", f"在 {head[:7]} 上不存在：{p}")
    from . import targets as TG
    for item, msg in TG.doctor_problems(cfg):
        bad(item, msg)
    facts.append(("target", TG.describe(cfg)["line"]))
    files = transcript_files(cfg)
    if files is None:
        bad("transcripts.projects_dir", f"目录不存在：{cfg['transcripts']['projects_dir']}")
    else:
        hits = _on_branch(files, cfg["transcripts"]["git_branch"])
        facts.append(("transcripts", f"{len(files)} 个会话文件在该仓下，{len(hits)} 个记在分支 {cfg['transcripts']['git_branch']} 上"))
        history = 0
        for i, s in enumerate(cfg["transcripts"].get("also", [])):
            n = len(_on_branch(transcript_files(cfg, s["cwd_prefix"]) or [], s["git_branch"]))
            history += n
            facts.append((f"transcripts.also[{i}]", f"历史来源（只读）{n} 个会话记在分支 {s['git_branch']} 上"))
        named, raw = T.named_files(cfg), cfg["transcripts"].get("sessions") or []
        for i, s in enumerate(raw):
            sid = s.get("id") if isinstance(s, dict) else None
            if not (isinstance(sid, str) and sid):
                bad(f"transcripts.sessions[{i}]", "缺 id：每一项写成 {\"id\": 会话号, \"note\": 为什么算这篇的}")
            elif not named.get(sid):
                bad(f"transcripts.sessions[{i}]", f"{cfg['transcripts']['projects_dir']} 下找不到会话 {sid} 的记录（{sid}.jsonl）")
        if raw:
            n_found = sum(1 for sid in named if named[sid])
            facts.append(("transcripts.sessions", f"按会话号指定的主会话 {n_found}/{len(named)} 个找得到记录"))
        if not hits and any(named.values()):
            # 这篇的会话都在别处跑、按会话号指定：分支上没有会话不是故障。
            facts.append(("transcripts", "主来源分支上没有会话；按会话号指定的主会话有记录"))
        elif not hits and history:
            # 刚改绑到新仓、还没在那里开过会话：记录在历史来源里。这是「还没开始」，不是故障（F6，负担实测 2026-09-18）。
            facts.append(("transcripts", "主来源还没有会话；历史来源里有记录，等第一次在主来源开会话"))
        elif not hits and _branch_exists(cfg["transcripts"]["cwd_prefix"], cfg["transcripts"]["git_branch"]):
            # 新建的工作区：分支在仓里，只是还没在上面开过会话，也是「还没开始」。分支不存在的仍算故障：那和分支名写错分不开
            # （2026-10-04：两篇稿件刚 init 完，刘海就挂红「跑挂了」）。
            facts.append(("transcripts", "主来源分支在、还没有会话；在这个分支上开会话，或改绑到正在做这篇的会话"))
        elif not hits:
            bad("transcripts.git_branch", "没有任何会话记录在这个分支上")
    return problems, facts
