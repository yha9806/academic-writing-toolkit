"""`loop bench` (plan 2.5, spec T15): time from an event to an index that reflects it, through the real hook path.

A throwaway manuscript repository, transcripts directory, workspace and registry are built in a temporary
directory. Each event is produced the way it happens in use and handed to the hook script's own handle(),
with the detached updater, as Claude Code would hand it over. The clock stops when index/ shows the event.

Targets (spec T15): median <= 2 s transcript, 3 s manuscript save, 5 s commit, 5 s ledger; p95 <= 2x target.
"Manuscript save" means an uncommitted edit; the engine reads committed versions only, so it is reported as
unsupported rather than timed.
"""
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import config as C

TARGETS = {"transcript": 2.0, "save": 3.0, "commit": 5.0, "ledger": 5.0}
HOOKS = Path(__file__).resolve().parents[2] / "hooks"


def _git(repo, *args):
    e = dict(os.environ, GIT_AUTHOR_NAME="b", GIT_AUTHOR_EMAIL="b@b", GIT_COMMITTER_NAME="b", GIT_COMMITTER_EMAIL="b@b")
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, env=e).stdout.decode().strip()


def _draft(n):
    intro = " ".join(f"Sentence {i} of version {n} describes span {i}." for i in range(1, 6))
    return (f"# Draft\n\n## Title candidate\n\nBench title {n}\n\n## Abstract\n\nThe abstract, version {n}.\n\n"
            f"## 1 Introduction\n\n{intro}\n")


def _ledger(k):
    return json.dumps([{"id": f"E{i}", "key": "K", "tier": "raw_abstract", "source": "raw/k.txt",
                        "draft": "Sentence 1 of version", "span": "a measured span"} for i in range(1, k + 1)])


def _record(cwd, branch, typ, ts, text, mid=None):
    base = {"cwd": str(cwd), "gitBranch": branch, "sessionId": "bench", "isSidechain": False, "timestamp": ts, "type": typ}
    if typ == "user":
        return {**base, "origin": {"kind": "human"}, "message": {"role": "user", "content": text}}
    return {**base, "message": {"id": mid, "role": "assistant", "content": [{"type": "text", "text": text}]}}


def _setup(root):
    repo = Path(root) / "ms"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "drafts").mkdir()
    (repo / "ev" / "raw").mkdir(parents=True)
    (repo / "drafts" / "DRAFT-v1.md").write_text(_draft(1), encoding="utf-8")
    (repo / "ev" / "claims.json").write_text(_ledger(1), encoding="utf-8")
    (repo / "ev" / "raw" / "k.txt").write_text("Here is a measured span.", encoding="utf-8")
    (repo / "ev" / "check.py").write_text('KEYMAP = {"K": "K"}\nNARR = {}\nPLACE = set()\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "v1")
    projects = Path(root) / "projects"
    proj = projects / C.escaped_project_dir(repo)
    proj.mkdir(parents=True)
    ws = Path(root) / "ws"
    for sub in C.SUBDIRS:
        (ws / sub).mkdir(parents=True)
    cfg = C.default_config("bench", repo, "main", "drafts/DRAFT-v*.md")
    cfg["transcripts"]["projects_dir"] = str(projects)
    cfg["ledger"] = {"path": "ev/claims.json", "evidence_dir": "ev", "keymap_from": "ev/check.py"}
    C.save(ws, cfg)
    reg = Path(root) / "registry"
    reg.write_text(f"{ws}\n", encoding="utf-8")
    return repo, proj / "bench.jsonl", ws, reg


def _index(ws, name):
    try:
        return json.loads((ws / "index" / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _idle(ws, timeout=60):
    """Wait until no update holds the lock and none is queued, so runs do not overlap."""
    end = time.time() + timeout
    while time.time() < end:
        if not (ws / "cache" / "update.lock").exists() and not (ws / "cache" / "update.dirty").exists():
            return True
        time.sleep(0.02)
    return False


def _wait(pred, timeout):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if pred():
            return time.time() - t0
        time.sleep(0.02)
    return None


def run(runs=10, timeout=30.0):
    sys.path.insert(0, str(HOOKS))
    import loop_hook as LH
    out = {k: [] for k in ("transcript", "commit", "ledger")}
    with tempfile.TemporaryDirectory() as root:
        repo, tfile, ws, reg = _setup(root)
        regs, _ = LH.registry(str(reg))
        LH.spawn_update(ws, "bench-warmup")
        _wait(lambda: (_index(ws, "sources.json") or {}).get("head") is not None, timeout)
        _idle(ws)
        version, entries = 1, 1
        for i in range(runs):
            # transcript: the author writes, Claude answers, the turn ends
            text = f"bench message {i}"
            with open(tfile, "a", encoding="utf-8") as fh:
                ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{i:03d}Z"
                fh.write(json.dumps(_record(repo, "main", "user", ts, text)) + "\n")
                fh.write(json.dumps(_record(repo, "main", "assistant", ts, "ok", mid=f"m{i}")) + "\n")
            t0 = time.time()
            LH.handle({"hook_event_name": "Stop", "cwd": str(repo), "stop_hook_active": False}, regs)
            took = _wait(lambda: text in json.dumps(_index(ws, "threads.json") or {}, ensure_ascii=False), timeout)
            out["transcript"].append(None if took is None else time.time() - t0)
            _idle(ws)
            # commit: a new draft version is committed
            version += 1
            (repo / "drafts" / f"DRAFT-v{version}.md").write_text(_draft(version), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-qm", f"v{version}")
            sha = _git(repo, "rev-parse", "HEAD")
            t0 = time.time()
            LH.handle({"hook_event_name": "PostToolUse", "cwd": str(repo), "tool_name": "Bash",
                       "tool_input": {"command": f"git commit -qm v{version}"}}, regs)
            took = _wait(lambda: (_index(ws, "sources.json") or {}).get("head") == sha, timeout)
            out["commit"].append(None if took is None else time.time() - t0)
            _idle(ws)
            # ledger: an entry is added and committed
            entries += 1
            (repo / "ev" / "claims.json").write_text(_ledger(entries), encoding="utf-8")
            _git(repo, "commit", "-qam", f"ledger {entries}")
            t0 = time.time()
            LH.handle({"hook_event_name": "PostToolUse", "cwd": str(repo), "tool_name": "Bash",
                       "tool_input": {"command": "git commit -qam ledger"}}, regs)
            took = _wait(lambda: (_index(ws, "checks.json") or {}).get("ledger_total") == entries, timeout)
            out["ledger"].append(None if took is None else time.time() - t0)
            _idle(ws)
    return out


def report(res):
    rows, ok = [], True
    for kind in ("transcript", "save", "commit", "ledger"):
        if kind == "save":
            rows.append((kind, "不支持：引擎只读已提交的版本", None, None, TARGETS[kind], None))
            continue
        xs = res[kind]
        missing = sum(x is None for x in xs)
        got = sorted(x for x in xs if x is not None)
        if not got:
            rows.append((kind, f"全部超时（{missing}/{len(xs)}）", None, None, TARGETS[kind], False))
            ok = False
            continue
        med = statistics.median(got)
        p95 = got[min(len(got) - 1, round(0.95 * (len(got) - 1)))]
        passed = missing == 0 and med <= TARGETS[kind] and p95 <= 2 * TARGETS[kind]
        ok = ok and passed
        rows.append((kind, f"n={len(got)}" + (f"，超时 {missing}" if missing else ""), med, p95, TARGETS[kind], passed))
    return rows, ok
