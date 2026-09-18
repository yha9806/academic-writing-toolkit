"""`loop doctor`: every configured path must resolve, or the command names the one that does not."""
import fnmatch
import json
import posixpath
import re

from . import config as C
from . import gitio
from .text import sentences_of


def draft_paths(cfg, commit):
    g = cfg["draft"]["glob"]
    names = gitio.ls_tree(cfg["repo"], commit, posixpath.dirname(g) or ".")
    return sorted([n for n in names if fnmatch.fnmatch(n, g)], key=C.version_key)


def transcript_files(cfg):
    t = cfg["transcripts"]
    root = C.expand(t["projects_dir"])
    prefix = C.escaped_project_dir(t["cwd_prefix"])
    if not root.is_dir():
        return None
    return sorted(p for d in root.iterdir() if d.is_dir() and d.name.startswith(prefix) for p in d.glob("*.jsonl"))


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
        latest = drafts[-1]
        n = len(sentences_of(gitio.show(repo, head, latest) or "", cfg["draft"]["sections"]))
        facts.append(("draft", f"{len(drafts)} 个版本文件，最新 {latest}，{n} 句"))
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
    files = transcript_files(cfg)
    if files is None:
        bad("transcripts.projects_dir", f"目录不存在：{cfg['transcripts']['projects_dir']}")
    else:
        needle = re.compile(rb'"gitBranch"\s*:\s*' + re.escape(json.dumps(cfg["transcripts"]["git_branch"]).encode()))
        hits = [f for f in files if needle.search(f.read_bytes())]
        facts.append(("transcripts", f"{len(files)} 个会话文件在该仓下，{len(hits)} 个记在分支 {cfg['transcripts']['git_branch']} 上"))
        if not hits:
            bad("transcripts.git_branch", "没有任何会话记录在这个分支上")
    return problems, facts
