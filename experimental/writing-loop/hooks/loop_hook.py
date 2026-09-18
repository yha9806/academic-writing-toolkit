#!/usr/bin/env python3
"""Claude Code hook for the writing loop (plan steps 2.1-2.3). One script, dispatched on hook_event_name.

  UserPromptSubmit  in a registered manuscript session: append the prompt verbatim to human/comments.jsonl
                    and ask for the explanation block at the end of manuscript replies
  PreToolUse        in any session: refuse a model write into a registered workspace's human/ (spec T2)
  PostToolUse       in a registered session: a write to the draft or the ledger, or a git command -> update
  Stop              in a registered session: -> update (the transcript grew)

Field names are the runtime's, read from the Claude Code binary (2.1.252), not from the documentation:
prompt, tool_name, tool_input, session_id, cwd. The documentation's names have been wrong before, and a
hook reading a field that is never sent does nothing, looks normal, and passes every test written from the
same documentation. So a payload without the field its event needs is recorded in health.json as a hook
error, never skipped quietly.

Updates run detached, so the hook returns at once; the updater merges overlapping requests.
Registered workspaces: one directory per line in ~/.awt/loop-workspaces (or $AWT_LOOP_REGISTRY).

What this does not do: the guard matches the tool call statically, and for shell commands it lets through
anything made only of reading commands (cat, grep, ...) with no redirection. A shell command that builds the path at
run time (variables, encodings) gets through. It guards this harness's tool channel, not the file system,
and a person editing files by hand never passes through it.
"""
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ENGINE = Path(__file__).resolve().parents[1] / "engine"
sys.path.insert(0, str(ENGINE))

from loop import config as C  # noqa: E402
from loop import health as HL  # noqa: E402

REGISTRY = "~/.awt/loop-workspaces"
WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
GIT_RE = re.compile(r"\bgit\b[^\n;&|]*\b(commit|merge|rebase|cherry-pick|reset|revert|pull|am)\b")
REMINDER = (
    "写作循环：这个会话属于已登记的稿件「{name}」。如果这一轮的回答涉及稿件（改了句子、解释了改动、回应了对稿件的评论），"
    "在回复最后加上不超过六行的解释块：\n"
    "〔循环〕\n"
    "读成：你把作者上一条消息读成了什么（本轮开头已经写了「我读成了」就省略这一行）\n"
    "改了：改动的句子编号；没有改就写「无」\n"
    "依据：这次改动依据的是作者哪句话或哪条证据\n"
    "〔/循环〕\n"
    "不涉及稿件的回答不要加。")


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + "Z"


def _real(p):
    return os.path.realpath(os.path.expanduser(str(p)))


def _under(path, root):
    path, root = _real(path), _real(root)
    return path == root or path.startswith(root.rstrip(os.sep) + os.sep)


def registry(path=None):
    """[(workspace, cfg)] for every readable line; a line that does not load is skipped, and returned as bad."""
    p = Path(os.path.expanduser(path or os.environ.get("AWT_LOOP_REGISTRY") or REGISTRY))
    good, bad = [], []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()
    except OSError:
        return good, bad
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            cfg = C.load(Path(os.path.expanduser(line)))
            good.append((Path(cfg["_ws"]), cfg))
        except (OSError, ValueError, KeyError):
            bad.append(line)
    return good, bad


def branch_of(cwd):
    r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def toplevel(cwd):
    r = subprocess.run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def session_ws(payload, regs):
    """The registered workspace this session works on: cwd under the configured prefix, on the configured branch."""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str):
        return None, None
    cands = [(ws, cfg) for ws, cfg in regs if _under(cwd, cfg["transcripts"]["cwd_prefix"])]
    if not cands:
        return None, None
    br = branch_of(cwd)
    for ws, cfg in cands:
        if br == cfg["transcripts"]["git_branch"]:
            return ws, cfg
    return None, None


def spawn_update(ws, reason):
    """Start `loop update` detached from this hook process; its output goes to cache/update.log."""
    (ws / "cache").mkdir(parents=True, exist_ok=True)
    log = open(ws / "cache" / "update.log", "a")
    subprocess.Popen([sys.executable, "-m", "loop", "update", str(ws), "--reason", reason],
                     cwd=str(ENGINE), env=dict(os.environ, PYTHONPATH=str(ENGINE)),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    log.close()


def _target(tool, ti, cwd):
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not isinstance(fp, str) or not fp:
        return None
    return fp if os.path.isabs(os.path.expanduser(fp)) else os.path.join(cwd or "", fp)


PATHLIKE = re.compile(r"[^\s;&|<>()'\"`=]+")


def _shell_hit(cmd, human, cwd):
    """A path-like word of the command that resolves under human/ (absolute, ~, relative to cwd, via symlinks)."""
    for tok in PATHLIKE.findall(cmd):
        if "/" not in tok and not tok.startswith("~"):
            continue
        p = os.path.expanduser(tok)
        if not os.path.isabs(p):
            if not isinstance(cwd, str):
                continue
            p = os.path.join(cwd, p)
        if _under(p, human):
            return tok
    return None


READ_ONLY = {"cat", "head", "tail", "less", "more", "wc", "grep", "rg", "ls", "jq", "stat", "file", "diff", "sha256sum", "shasum", "md5"}


def _read_only(cmd):
    """Heuristic: no redirection or tee, and every piped or chained segment starts with a reading command.
    Reading the author's words is legitimate; only writing them is reserved to hooks and the interface."""
    if ">" in cmd or re.search(r"\btee\b", cmd):
        return False
    segs = [s.strip() for s in re.split(r"&&|\|\||[;|\n]", cmd) if s.strip()]
    return bool(segs) and all(s.split()[0] in READ_ONLY for s in segs)


def on_prompt(payload, regs, now):
    ws, cfg = session_ws(payload, regs)
    if ws is None:
        return None
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        HL.record_event(ws, "hook_error", "UserPromptSubmit 的载荷里没有字符串字段 prompt（运行时字段名变了？）", now=now)
        return None
    (ws / "human").mkdir(parents=True, exist_ok=True)
    rec = {"at": _iso(now), "session_id": payload.get("session_id"), "prompt_id": payload.get("prompt_id"),
           "prompt": prompt, "origin": "hook:UserPromptSubmit"}
    with open(ws / "human" / "comments.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                   "additionalContext": REMINDER.format(name=cfg["name"])}}


def on_pre_tool(payload, regs, now):
    tool, ti, cwd = payload.get("tool_name"), payload.get("tool_input"), payload.get("cwd")
    if not isinstance(ti, dict):
        return None
    for ws, _cfg in regs:
        human = ws / "human"
        hit = None
        if tool in WRITE_TOOLS:
            t = _target(tool, ti, cwd)
            if t and _under(t, human):
                hit = t
        elif tool == "Bash":
            cmd = ti.get("command") or ""
            hit = _shell_hit(cmd, human, cwd)
            if hit and _read_only(cmd):
                hit = None
        if hit:
            HL.record_event(ws, "guard_denied", f"{tool} → {hit}", now=now)
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"human/ 只能由钩子或界面写入（写作循环 T2）：{hit}。"
                    "作者的原话、反应和批准不由模型写；要记录作者说了什么，引用会话记录即可。")}}
    return None


def on_post_tool(payload, regs, now, spawn):
    ws, cfg = session_ws(payload, regs)
    if ws is None:
        return None
    tool, ti = payload.get("tool_name"), payload.get("tool_input")
    if not isinstance(ti, dict):
        HL.record_event(ws, "hook_error", "PostToolUse 的载荷里没有字典字段 tool_input", now=now)
        return None
    if tool in WRITE_TOOLS:
        t, top = _target(tool, ti, payload.get("cwd")), toplevel(payload.get("cwd"))
        if t and top and _under(t, top):
            rel = os.path.relpath(_real(t), _real(top)).replace(os.sep, "/")
            led = cfg.get("ledger") or {}
            if fnmatch.fnmatch(rel, cfg["draft"]["glob"]) or rel == led.get("path") or \
                    (led.get("evidence_dir") and rel.startswith(led["evidence_dir"].rstrip("/") + "/")):
                spawn(ws, f"write:{rel}")
    elif tool == "Bash" and GIT_RE.search(ti.get("command") or ""):
        spawn(ws, "git")
    return None


def on_stop(payload, regs, now, spawn):
    ws, _cfg = session_ws(payload, regs)
    if ws is not None:
        spawn(ws, "stop")
    return None


def handle(payload, regs, spawn=spawn_update, now=None):
    now = time.time() if now is None else now
    ev = payload.get("hook_event_name")
    if ev == "UserPromptSubmit":
        return on_prompt(payload, regs, now)
    if ev == "PreToolUse":
        return on_pre_tool(payload, regs, now)
    if ev == "PostToolUse":
        return on_post_tool(payload, regs, now, spawn)
    if ev == "Stop":
        return on_stop(payload, regs, now, spawn)
    return None


def main():
    regs, _bad = registry()
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    try:
        out = handle(payload, regs)
    except Exception as e:  # a broken hook must show up in health, and must not block the session
        for ws, _cfg in regs:
            HL.record_event(ws, "hook_error", f"{payload.get('hook_event_name')}：{type(e).__name__}：{e}")
        print(f"writing-loop hook: {type(e).__name__}: {e}", file=sys.stderr)
        return 0
    if out is not None:
        print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
