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


def _on_branch(files, branch):
    needle = re.compile(rb'"gitBranch"\s*:\s*' + re.escape(json.dumps(branch).encode()))
    return [f for f in files if needle.search(f.read_bytes())]


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
        if not hits and history:
            # 刚改绑到新仓、还没在那里开过会话：记录在历史来源里。这是「还没开始」，不是故障（F6，负担实测 2026-09-18）。
            facts.append(("transcripts", "主来源还没有会话；历史来源里有记录，等第一次在主来源开会话"))
        elif not hits:
            bad("transcripts.git_branch", "没有任何会话记录在这个分支上")
    return problems, facts
