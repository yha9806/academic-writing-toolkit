"""Drops from lintel (候选 B, the author 2026-09-21: folders only, no PDFs yet).

The author drags a manuscript folder onto the notch; lintel writes
``producers/awt-loop/inbox/<uuid>.json`` = ``{"schema": 1, "kind": "drop", "path": ..., "at": ..., "from": "lintel"}``
and nothing else — it never runs us. ``loop inbox --workspaces <root>`` reads those files, registers each folder as a
workspace (repo root, branch, the LaTeX main file and what it \\input s, one prose rule per heading), builds the index,
writes the "登记好了" activity, and moves the drop file to ``inbox/done/`` with the outcome beside it.

Not here yet: asking which sections to watch (storyboard ⑯ choice card) and the answer path back; every heading is watched.
"""
import json
import os
import re
import subprocess
import time
from pathlib import Path

from . import config as C
from . import index as X
from . import lintel as LN
from . import text as T

INPUT = re.compile(r"\\(?:input|include)\{([^}]+)\}")
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__"}


class Refused(Exception):
    """The drop is not something we can register; the reason is written beside the drop file."""


def pending(home, producer=LN.PRODUCER):
    d = Path(os.path.expanduser(home)) / "producers" / producer / "inbox"
    return sorted(p for p in d.glob("*.json") if not p.name.startswith(".")) if d.is_dir() else []


def read_drop(p):
    d = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(d, dict) or d.get("schema") != 1 or d.get("kind") != "drop" or not isinstance(d.get("path"), str):
        raise Refused("收件文件不是 lintel 的拖放格式")
    return d


def git_root(path):
    r = subprocess.run(["git", "-C", str(path), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def branch(repo):
    r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def _read(p):
    return p.read_text(encoding="utf-8", errors="ignore")


def tex_draft(root):
    """The LaTeX main file (the one with \\documentclass, shallowest first) and every file it \\input s or \\include s,
    breadth first, as repo-relative paths. None if there is no such file."""
    root = Path(root)
    mains = [p for p in root.rglob("*.tex") if not (SKIP_DIRS & set(p.relative_to(root).parts)) and "\\documentclass" in _read(p)]
    if not mains:
        return None
    main = sorted(mains, key=lambda p: (len(p.parts), str(p)))[0]
    files, queue, seen = [main], [main], {main}
    while queue:
        f = queue.pop(0)
        for name in INPUT.findall(_read(f)):
            for cand in (f.parent / name, root / name):
                cand = cand if cand.suffix else cand.with_suffix(".tex")
                if cand.exists() and cand not in seen:
                    seen.add(cand)
                    files.append(cand)
                    queue.append(cand)
                    break
    return [p.relative_to(root).as_posix() for p in files]


def section_rules(texts):
    """One prose rule per heading in order of appearance, prefixes A, B, C…; the abstract is flat (A01, A02…).
    Which of them the author actually wants watched is the choice-card step that is not built yet."""
    headings = []
    for t in texts:
        headings += [h for h, _ in T.latex_sections(t)]
    rules = []
    for i, h in enumerate(dict.fromkeys(headings)):
        prefix = chr(ord("A") + i) if i < 26 else f"S{i}"
        rule = {"match": "^" + re.escape(h) + "$", "prefix": prefix, "kind": "prose", "short": h if len(h) <= 8 else h[:7] + "…"}
        if h == "Abstract":
            rule["flat"] = True
        rules.append(rule)
    return rules


def resolve(path, projects_dir=None):
    """What the folder tells us by itself (storyboard ⑰): repo root, branch, draft files, format, sections, transcripts."""
    root = git_root(path)
    if root is None:
        raise Refused("不是 git 目录")
    glob = tex_draft(root)
    if glob is None:
        raise Refused("找不到带 \\documentclass 的 .tex")
    cfg = C.default_config(root.name, root, branch(root), glob, genre="journal")
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = section_rules([_read(root / p) for p in glob])
    if projects_dir:
        cfg["transcripts"]["projects_dir"] = str(projects_dir)
    return cfg


def process(home, workspaces, *, producer=LN.PRODUCER, projects_dir=None, now=None):
    """Handle every pending drop. Returns [(drop file name, outcome)]; each outcome is written beside the moved drop."""
    results = []
    for p in pending(home, producer):
        try:
            drop = read_drop(p)
        except (ValueError, Refused) as e:
            drop, outcome = {"file": p.name}, {"ok": False, "reason": str(e) or "读不出收件文件"}
        else:
            try:
                cfg = resolve(Path(drop["path"]), projects_dir)
                ws = Path(workspaces) / cfg["name"]
                if (ws / "config.json").exists():
                    raise Refused(f"工作区 {cfg['name']} 已存在")
                for sub in C.SUBDIRS:
                    (ws / sub).mkdir(parents=True, exist_ok=True)
                C.save(ws, cfg)
                cfg = C.load(ws)   # the loaded form carries the workspace path the index needs
                files, summary = X.build(cfg)
                X.write(cfg, files)
                summary["just_registered"] = True
                summary["ref"] = cfg["ref"]
                LN.sync(LN.build(summary, now=now or time.time()), home=home, producer=producer)
                outcome = {"ok": True, "workspace": str(ws), "sentences": summary["sentences"],
                           "sections": len(cfg["draft"]["sections"]), "ref": cfg["ref"]}
            except Refused as e:
                outcome = {"ok": False, "reason": str(e)}
        done = p.parent / "done"
        done.mkdir(exist_ok=True)
        moved = done / p.name
        p.rename(moved)
        moved.write_text(json.dumps({**drop, "outcome": outcome}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        results.append((p.name, outcome))
    return results
