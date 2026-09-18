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
