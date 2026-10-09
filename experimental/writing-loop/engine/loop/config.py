"""Workspace configuration: where the manuscript, ledger and transcripts live.

A workspace is a directory holding config.json plus human/, model/, index/, cache/.
The manuscript repository itself is only ever read.
"""
import json
import os
import re
from pathlib import Path

SCHEMA = 1
SUBDIRS = ("human", "model", "index", "cache")
# The hooks act only on the workspaces listed here, one directory per line ($AWT_LOOP_REGISTRY overrides it).
REGISTRY = "~/.awt/loop-workspaces"


def registry_path():
    """The hook registry the hooks read (hooks/loop_hook.py) and `loop doctor` checks against."""
    return Path(os.path.expanduser(os.environ.get("AWT_LOOP_REGISTRY") or REGISTRY))


def registered(ws):
    """(listed, registry path). listed: True when a line of the registry names this workspace directory (compared
    resolved, so a trailing slash or a `..` does not matter), False when none does, None when the registry cannot be
    read. None is not "listed": with no registry the hooks act on no workspace at all."""
    p = registry_path()
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None, p
    me = os.path.realpath(os.path.expanduser(str(ws)))
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#") and os.path.realpath(os.path.expanduser(line)) == me:
            return True, p
    return False, p


def registry_warning(ws):
    """One line saying the hooks will not act on this workspace, or None when the registry lists it."""
    listed, p = registered(ws)
    if listed:
        return None
    where = f"钩子登记表读不到（{p}）" if listed is None else f"这个工作区不在钩子登记表 {p} 里"
    return (f"{where}：钩子不会触发——作者的话不记进 human/，改稿后不自动 update，没有会话收到「论文状态」那一行。"
            f"登记：把 {os.path.realpath(os.path.expanduser(str(ws)))} 加成登记表里的一行")


def session_ids(cfg):
    """Primary sessions named by id (transcripts.sessions: [{"id", "note"}]). Such a session is this manuscript's own
    wherever it runs: one that edits the draft by absolute path from another checkout and branch matches no
    directory + branch rule, and a rule wide enough to take it in would take its neighbours in too. The hooks
    (hooks/loop_hook.py session_ws), transcript reading (transcripts.py), doctor, approvals and the ring all read this
    one list, so a session the hooks treat as the manuscript's is counted as such everywhere else."""
    out = []
    for s in (cfg.get("transcripts") or {}).get("sessions") or []:
        sid = s.get("id") if isinstance(s, dict) else None
        if isinstance(sid, str) and sid and sid not in out:
            out.append(sid)
    return out


def default_config(name, repo, ref, draft_glob, genre="conference"):
    return {
        "schema": SCHEMA,
        "name": name,
        "genre": genre,
        "repo": str(repo),
        "ref": ref,
        "draft": {
            "glob": draft_glob,
            "sections": [
                {"match": r"^Title candidates?\b", "prefix": "T", "kind": "title"},
                {"match": r"^Abstract\b", "prefix": "A", "kind": "prose", "flat": True},
                {"match": r"^1 Introduction\b", "prefix": "I", "kind": "prose"},
            ],
        },
        "ledger": None,
        "transcripts": {
            "projects_dir": "~/.claude/projects",
            "git_branch": ref,
            "cwd_prefix": str(repo),
        },
    }


def load(ws):
    ws = Path(ws)
    cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
    if cfg.get("schema") != SCHEMA:
        raise ValueError(f"config schema {cfg.get('schema')} is not {SCHEMA}")
    cfg["_ws"] = str(ws.resolve())
    return cfg


def save(ws, cfg):
    ws = Path(ws)
    clean = {k: v for k, v in cfg.items() if not k.startswith("_")}
    (ws / "config.json").write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def expand(p):
    return Path(os.path.expanduser(p))


def version_key(path):
    """DRAFT-abstract-intro-v10.md sorts after -v9.md."""
    m = re.search(r"v(\d+)(?:\.\w+)?$", path)
    return (int(m.group(1)) if m else -1, path)


def escaped_project_dir(path):
    """Claude Code names a project directory by replacing / and . with -."""
    return re.sub(r"[/.]", "-", str(path))
