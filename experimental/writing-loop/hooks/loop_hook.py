#!/usr/bin/env python3
"""Claude Code hook for the writing loop (plan steps 2.1-2.3). One script, dispatched on hook_event_name.

  UserPromptSubmit  in a registered manuscript session: append the prompt verbatim to human/comments.jsonl
                    and ask for the explanation block at the end of manuscript replies
  PreToolUse        in any session: refuse a model write into a registered workspace's human/ (spec T2)
  PostToolUse       in a registered session: a write to the draft or the ledger, or a git command -> update; with
                    gates.rewrites on, after any write tool or shell command the working tree's changed sentences are
                    read and what was flagged is added to the agent's context
  Stop              in a registered session: -> update (the transcript grew); with gates.rewrites on, a flagged rewrite
                    left unhandled in the working tree or the reply blocks the stop once (stop_hook_active then lets it
                    through and records stop_gate_overridden)

Field names are the runtime's, read from the Claude Code binary (2.1.252), not from the documentation:
prompt, tool_name, tool_input, session_id, cwd. The documentation's names have been wrong before, and a
hook reading a field that is never sent does nothing, looks normal, and passes every test written from the
same documentation. So a payload without the field its event needs is recorded in health.json as a hook
error, never skipped quietly.

Updates run detached, so the hook returns at once; the updater merges overlapping requests.
Registered workspaces: one directory per line in ~/.awt/loop-workspaces (or $AWT_LOOP_REGISTRY).

What this does not do: the guard matches the tool call statically, and for shell commands it lets through
a segment that names human/ only as the argument of a reading command (cat, grep, ...) and redirects
nothing into it. Segments end where the shell would end them, outside quotes; a segment that names human/
and contains a command substitution, or that cannot be parsed, is refused. A shell command that builds the
path at run time (variables, encodings) gets through. It guards this harness's tool channel, not the file
system, and a person editing files by hand never passes through it.
"""
import fnmatch
import json
import os
import re
import shlex
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
    "标签：不超过 6 个字，说这一轮为什么改（刘海右翼要显示的；没有改就省略这一行）\n"
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


def history_ws(payload, regs):
    """A workspace this session belongs to as a history source (transcripts.also): read-only for the hooks, which
    write nothing for it, but the author working there should still see which checks are not current."""
    cwd = payload.get("cwd")
    if not isinstance(cwd, str):
        return None, None
    br = None
    for ws, cfg in regs:
        for s in cfg["transcripts"].get("also") or []:
            if isinstance(s, dict) and s.get("cwd_prefix") and s.get("git_branch") and _under(cwd, s["cwd_prefix"]):
                br = br or branch_of(cwd)
                if br == s.get("git_branch"):
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


def spawn_producer(ws):
    """Start the resident `loop lintel` for this workspace, detached; it keeps the notch cards and heartbeat."""
    (ws / "cache").mkdir(parents=True, exist_ok=True)
    log = open(ws / "cache" / "lintel.log", "a")
    subprocess.Popen([sys.executable, "-m", "loop", "lintel", str(ws)], cwd=str(ENGINE),
                     env=dict(os.environ, PYTHONPATH=str(ENGINE)),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    log.close()


def ensure_producer(ws, start=spawn_producer):
    """If lintel has registered this producer and no producer process is alive for ws, start one.
    Unregistered: do nothing and create nothing (the notch display is off by default).

    The notch module is imported here, not at the top: the hook command ends in `|| true`, so a notch module that
    failed to import at the top would take the human/ guard down with it and look like a hook that allowed the write.
    A failure here is recorded and the hook goes on."""
    try:
        from loop import lintel as LN
        from loop.cli import _producer_alive
    except Exception as e:  # noqa: BLE001 -- the notch is optional; the guard and the reminder are not
        HL.record_event(ws, "hook_error", f"刘海模块读不进来：{type(e).__name__}：{e}")
        return False
    if LN.registered(LN.lintel_home(), LN.PRODUCER) and not _producer_alive(ws / "cache" / "lintel.pid"):
        start(ws)
        return True
    return False


def _target(tool, ti, cwd):
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not isinstance(fp, str) or not fp:
        return None
    return fp if os.path.isabs(os.path.expanduser(fp)) else os.path.join(cwd or "", fp)


PATHLIKE = re.compile(r"[^\s;&|<>()'\"`=]+")
SEGMENTS = re.compile(r"&&|\|\||[;|\n]")
# Command substitution runs inside double quotes too, so its text cannot be judged by the command around it.
SUBSTITUTION = re.compile(r"\$\(|`|<\(|>\(")
# A reading command named by its full path counts only from a system directory: a file called grep
# elsewhere could be anything.
SYSTEM_BIN = {"/bin", "/usr/bin", "/usr/local/bin", "/opt/homebrew/bin"}
OPERATOR = set("<>&|0123456789")


def _resolves_under(tok, human, cwd):
    """A path-like word that resolves under human/ (absolute, ~, relative to cwd, via symlinks)."""
    if "/" not in tok and not tok.startswith("~"):
        return False
    p = os.path.expanduser(tok)
    if not os.path.isabs(p):
        if not isinstance(cwd, str):
            return False
        p = os.path.join(cwd, p)
    return _under(p, human)


def _segments(cmd):
    """Split where the shell ends a command: ; & && || | and newlines, outside quotes.

    Found in live use (2026-09-19): splitting on every | refused `jq '.a|.b' human/c` and `grep 'a|b' human/c`,
    reads both. Unbalanced quotes (a heredoc body, a typo) fall back to splitting everywhere, as before."""
    segs, cur, q, i = [], [], None, 0
    while i < len(cmd):
        c = cmd[i]
        if q:
            cur.append(c)
            if c == "\\" and q == '"' and i + 1 < len(cmd):
                cur.append(cmd[i + 1])
                i += 1
            elif c == q:
                q = None
        elif c == "\\" and i + 1 < len(cmd):
            cur.append(cmd[i:i + 2])
            i += 1
        elif c in "'\"":
            q = c
            cur.append(c)
        elif c in ";|\n" or (c == "&" and cmd[i - 1:i] not in (">", "<") and cmd[i + 1:i + 2] != ">"):
            segs.append("".join(cur))
            cur = []
            if cmd[i:i + 2] in ("&&", "||"):
                i += 1
        else:
            cur.append(c)
        i += 1
    if q:
        return SEGMENTS.split(cmd)
    segs.append("".join(cur))
    return segs


def _words(seg):
    """The shell words of one segment with their quotes kept, so a quoted > stays a word; None if unparseable."""
    try:
        lex = shlex.shlex(seg, posix=False, punctuation_chars=True)
        lex.whitespace_split = True
        return list(lex)
    except ValueError:
        return None


def _unquote(word):
    try:
        parts = shlex.split(word)
    except ValueError:
        return word
    return parts[0] if len(parts) == 1 else word


def _command_name(word):
    d, base = os.path.split(_unquote(word))
    return base if d in SYSTEM_BIN else _unquote(word)


def _redirect_targets(words):
    """The word after each unquoted output redirection (>, >>, 2>, &>, >| ...)."""
    return [_unquote(words[i + 1]) for i, w in enumerate(words[:-1]) if ">" in w and set(w) <= OPERATOR]


def _shell_write_hit(cmd, human, cwd):
    """The human/ path a shell command may write, or None.

    Only the segments (split, outside quotes, on ; & && || | and newlines) that name a path under human/ are
    judged. Such a segment passes only if it starts with a reading command and redirects nothing into human/.
    Segments that do not touch human/ do not matter, so `ls human/; cd x && python3 y` is a read, while
    `cat a > human/b`, `cat a > "human/b"`, `… | tee human/b`, `cp a human/b`, `cat "$(cp a human/b)"` and
    `cd human && rm b` are writes. Heuristic, and stated as one."""
    for seg in (s.strip() for s in _segments(cmd)):
        if not seg:
            continue
        touched = [tok for tok in PATHLIKE.findall(seg) if _resolves_under(tok, human, cwd)]
        if not touched:
            continue
        words = _words(seg)
        if not words or SUBSTITUTION.search(seg):
            return touched[0]
        writes_human = any(_resolves_under(t, human, cwd) for t in _redirect_targets(words))
        if _command_name(words[0]) not in READ_ONLY or writes_human:
            return touched[0]
    return None


# Reading the author's words is legitimate; only writing them is reserved to hooks and the interface.
READ_ONLY = {"cat", "head", "tail", "less", "more", "wc", "grep", "rg", "ls", "jq", "stat", "file", "diff", "sha256sum", "shasum", "md5"}

# Said to the model, not by the author. Background-task notices, messages from another Claude session and the
# like reach UserPromptSubmit as well (checked against real transcripts, 2026-09-17); none of them belongs in
# human/. Started from the wishing-willow plugin's envelope rule; bash-input/-stdout/-stderr (a `!cmd` the author
# runs: a shell command and its output, not words about the draft) added 2026-09-21.
ENVELOPE = re.compile(r"\s*(?:<(?:task-notification|ci-monitor-event|system-reminder|command-name|command-message|"
                      r"bash-input|bash-stdout|bash-stderr|"
                      r"local-command-stdout|cross-session-message)\b|\[SYSTEM NOTIFICATION)", re.I)


def reminder_text(ws, cfg):
    """The explanation block the author asked for, plus one line on which checks have not looked at the draft as it
    is now. The line is read from the summary `loop update` wrote; nothing is computed here, so the hook stays fast.
    An unreadable summary is said, not skipped: silence would read as "all checked"."""
    text = REMINDER.format(name=cfg["name"])
    line = coverage_line(ws, cfg)
    return text + ("\n" + line if line else "")


def coverage_line(ws, cfg):
    try:
        from loop import coverage as V
        line = V.reminder_line(V.load_summary(ws, cfg), ws)
    except Exception as e:  # noqa: BLE001 -- any failure here must still reach the agent as text
        line = f"覆盖：摘要读不出（{type(e).__name__}），不能当作都查过了"
    return line


def on_prompt(payload, regs, now):
    ws, cfg = session_ws(payload, regs)
    if ws is None:
        hws, hcfg = history_ws(payload, regs)
        if hws is None:
            return None
        line = coverage_line(hws, hcfg)
        if not line:
            return None
        return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                       "additionalContext": f"稿件「{hcfg['name']}」（这个会话是它的历史来源，不记录原话）" + line}}
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        HL.record_event(ws, "hook_error", "UserPromptSubmit 的载荷里没有字符串字段 prompt（运行时字段名变了？）", now=now)
        return None
    reminder = {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit",
                                       "additionalContext": reminder_text(ws, cfg)}}
    if ENVELOPE.match(prompt):
        return reminder  # the turn it starts can still edit the draft
    (ws / "human").mkdir(parents=True, exist_ok=True)
    rec = {"at": _iso(now), "session_id": payload.get("session_id"), "prompt_id": payload.get("prompt_id"),
           "prompt": prompt, "origin": "hook:UserPromptSubmit"}
    with open(ws / "human" / "comments.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    ensure_producer(ws)
    return reminder


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
            hit = _shell_write_hit(ti.get("command") or "", human, cwd)
        if hit:
            HL.record_event(ws, "guard_denied", f"{tool} → {hit}", now=now)
            return {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"human/ 只能由钩子或界面写入（写作循环 T2）：{hit}。"
                    "作者的原话、反应和批准不由模型写；要记录作者说了什么，引用会话记录即可。")}}
    return None


def _is_draft(rel, glob):
    """A string is a glob naming one file per version; a list names the files that together are the draft
    (a LaTeX main file and its sections), matched file by file, as history.py reads it."""
    return rel in glob if isinstance(glob, list) else fnmatch.fnmatch(rel, glob)


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
            if _is_draft(rel, cfg["draft"]["glob"]) or rel == led.get("path") or \
                    (led.get("evidence_dir") and rel.startswith(led["evidence_dir"].rstrip("/") + "/")):
                spawn(ws, f"write:{rel}")
    elif tool == "Bash" and GIT_RE.search(ti.get("command") or ""):
        spawn(ws, "git")
    if (cfg.get("gates") or {}).get("rewrites") and (tool in WRITE_TOOLS or tool == "Bash"):
        ctx = rewrite_context(ws, cfg, now)
        if ctx:
            return {"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": ctx}}
    return None


def rewrite_context(ws, cfg, now):
    """After any tool that can write the draft, a script run in a shell included: the changed-sentence audit on the
    working tree. Nothing when the draft is unchanged since the last read (a content fingerprint, so this costs a
    hash); otherwise one line naming what was flagged. Imported here, not at the top: a broken coverage module must
    not take the human/ guard down with it."""
    try:
        from loop import coverage as V
        r = V.worktree_check(cfg, ws)
    except Exception as e:  # noqa: BLE001 -- the agent must hear that the gate is down
        HL.record_event(ws, "hook_error", f"改句门：{type(e).__name__}：{e}", now=now)
        return f"改句门自己坏了（{type(e).__name__}：{e}），这一次的改动没有查。"
    if r.get("error"):
        HL.record_event(ws, "hook_error", f"改句门：{r['error']}", now=now)
        return f"改句检查没能跑：{r['error']}"
    if r.get("cached") or not r.get("unresolved"):
        return None
    items = "；".join(f"[{s['key']}] {'、'.join(s['flags'])}：{s['new'][:80]}" for s in r["unresolved"][:5])
    return (f"改句检查（{r.get('summary', '')}）：{len(r['unresolved'])} 句标出、未处理——{items}。"
            f"结束这一轮前改掉，或在接受台账写理由。")


def stop_gate(payload, ws, cfg, now):
    """The turn may not end while a flagged rewrite is unhandled, in the working tree or in the reply. Blocked once:
    when the runtime says a Stop hook already blocked this turn (stop_hook_active), the turn ends and the override is
    recorded for the notch, rather than blocking until the runtime's own cap forces it."""
    reply = payload.get("last_assistant_message")
    if not isinstance(reply, str):
        HL.record_event(ws, "hook_error", "Stop 的载荷里没有字符串字段 last_assistant_message：回复里的改句这一轮没查", now=now)
        reply = None
    try:
        from loop import coverage as V
        reason = V.stop_verdict(cfg, ws, reply)
    except Exception as e:  # noqa: BLE001 -- an audit that did not run is not a pass
        HL.record_event(ws, "hook_error", f"改句门：{type(e).__name__}：{e}", now=now)
        reason = f"改句门自己坏了（{type(e).__name__}：{e}）。修好，或在回复里说明为什么这一轮不需要它。"
    if not reason:
        return None
    if payload.get("stop_hook_active"):
        HL.record_event(ws, "stop_gate_overridden", reason[:300], now=now)
        return None
    return {"decision": "block", "reason": reason}


def on_stop(payload, regs, now, spawn):
    ws, cfg = session_ws(payload, regs)
    if ws is not None:
        spawn(ws, "stop")
        ensure_producer(ws)
        if (cfg.get("gates") or {}).get("rewrites"):
            return stop_gate(payload, ws, cfg, now)
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
