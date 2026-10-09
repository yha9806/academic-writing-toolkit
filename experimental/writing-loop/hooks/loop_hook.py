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

REGISTRY = C.REGISTRY  # one definition: `loop doctor` checks a workspace against the same file (config.registry_path)
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
    p = Path(os.path.expanduser(path)) if path else C.registry_path()
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
    """The registered workspace this session works on: one whose transcripts.sessions names this session's id, wherever
    it runs; otherwise cwd under the configured prefix, on the configured branch. The id list is read through
    C.session_ids, the one rule transcript reading, doctor, approvals and the ring also go by."""
    sid = payload.get("session_id")
    if isinstance(sid, str) and sid:
        for ws, cfg in regs:
            if sid in C.session_ids(cfg):
                return ws, cfg
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


def history_wss(payload, regs):
    """Every workspace this session belongs to as a history source (transcripts.also): read-only for the hooks, which
    write nothing for it, but the author working there should still see which checks are not current. One session can
    be history for several manuscripts (2026-10-04: one conversation works on two papers).

    A session can also be named by its id (transcripts.history_sessions, read only here): a conversation
    shares its checkout and branch with other lines, so a directory + branch rule would take them in too. Only the
    hook reads that key; transcript reading, targets and doctor still go by `also`, so its turns are not counted.
    A session that does work on the manuscript belongs in transcripts.sessions instead (see session_ws): that key
    makes it a primary session, and every reader counts it."""
    cwd, sid = payload.get("cwd"), payload.get("session_id")
    br, out = None, []
    for ws, cfg in regs:
        if isinstance(sid, str) and any(isinstance(s, dict) and s.get("id") == sid
                                        for s in cfg["transcripts"].get("history_sessions") or []):
            out.append((ws, cfg))
            continue
        if not isinstance(cwd, str):
            continue
        for s in cfg["transcripts"].get("also") or []:
            if isinstance(s, dict) and s.get("cwd_prefix") and s.get("git_branch") and _under(cwd, s["cwd_prefix"]):
                br = br or branch_of(cwd)
                if br == s.get("git_branch"):
                    out.append((ws, cfg))
                    break
    return out


LOG_CAP = 1 << 20   # bytes; past this a log moves to <name>.1 (one older file kept) before the next run appends


def open_log(ws, name):
    """cache/<name> for appending, with a ceiling: the logs used to grow without one (2026-10-08: 4.9 MB of notch
    log on one manuscript). A process already running keeps writing to the file it opened, now named <name>.1."""
    (ws / "cache").mkdir(parents=True, exist_ok=True)
    p = ws / "cache" / name
    try:
        if p.stat().st_size > LOG_CAP:
            p.replace(p.with_name(name + ".1"))
    except OSError:
        pass
    return open(p, "a")


def spawn_update(ws, reason):
    """Start `loop update` detached from this hook process; its output goes to cache/update.log."""
    log = open_log(ws, "update.log")
    subprocess.Popen([sys.executable, "-m", "loop", "update", str(ws), "--reason", reason],
                     cwd=str(ENGINE), env=dict(os.environ, PYTHONPATH=str(ENGINE)),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    log.close()


def spawn_card(ws):
    """Write this workspace's notch card once (`loop lintel --once`), detached; its output goes to cache/lintel.log."""
    log = open_log(ws, "lintel.log")
    subprocess.Popen([sys.executable, "-m", "loop", "lintel", str(ws), "--once"], cwd=str(ENGINE),
                     env=dict(os.environ, PYTHONPATH=str(ENGINE)),
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    log.close()


def refresh_card(ws):
    """After a session is first noted as history: the card lists its sessions (`within`) from the note, and a
    manuscript read only as history has no resident producer to rewrite it. Registered with lintel and no producer
    alive: write the card once. A failure is recorded; the hook goes on."""
    try:
        from loop import lintel as LN
        from loop.cli import _producer_alive
        if LN.registered(LN.lintel_home(), LN.PRODUCER) and not _producer_alive(ws / "cache" / "lintel.pid"):
            spawn_card(ws)
    except Exception as e:  # noqa: BLE001 -- the notch is optional
        HL.record_event(ws, "hook_error", f"卡片没重写（{type(e).__name__}：{e}）")


def spawn_producer(ws):
    """Start the resident `loop lintel` for this workspace, detached; it keeps the notch cards and heartbeat."""
    log = open_log(ws, "lintel.log")
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
        from loop import config as C
        from loop import lintel as LN
        from loop.cli import _producer_alive, _submitted
    except Exception as e:  # noqa: BLE001 -- the notch is optional; the guard and the reminder are not
        HL.record_event(ws, "hook_error", f"刘海模块读不进来：{type(e).__name__}：{e}")
        return False
    # K10 功耗：稿子投出去以后不再拉起（阶段改回别的就照常拉起）。配置读不出就照旧拉起，让来源进程自己报。
    try:
        if _submitted(C.load(ws)):
            return False
    except Exception:  # noqa: BLE001
        pass
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


def willow_rule():
    """(rule, path) for which records are not the author's words, from the wishing-willow plugin, or (None, None).

    The rule is kept once, by the plugin (plugin/hooks/envelopes.json); this hook only reads it. Two copies had drifted
    before: the plugin never learnt `!` shell input, which this file had. WILLOW_ENVELOPES names the file for a test."""
    cands = []
    if os.environ.get("WILLOW_ENVELOPES"):
        cands.append(Path(os.environ["WILLOW_ENVELOPES"]))
    else:
        try:
            reg = json.loads((Path.home() / ".claude" / "plugins" / "installed_plugins.json").read_text(encoding="utf-8"))
            for e in (reg.get("plugins") or {}).get("willow@wishing-willow") or []:
                cands.append(Path(e["installPath"]) / "hooks" / "envelopes.json")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            pass
    for c in cands:
        try:
            r = json.loads(c.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(r, dict) and isinstance(r.get("tags"), list) and isinstance(r.get("prefixes"), list):
            return r, str(c)
    return None, None


def is_envelope(prompt, rule):
    """Not the author's words: with the plugin's rule, a record that is nothing but listed blocks (each removed whole)
    or starts with a listed prefix; text left over is the author's. Without it, the built-in ENVELOPE above."""
    if rule is None:
        return bool(ENVELOPE.match(prompt))
    t = prompt.strip()
    if not t:
        return False
    if any(t.startswith(x) for x in rule["prefixes"]):
        return True
    if not t.startswith("<") or not rule["tags"]:
        return False
    block = re.compile(r"<(%s)\b[^>]*>[\s\S]*?</\1>" % "|".join(re.escape(x) for x in rule["tags"]), re.I)
    prev = None
    while prev != t:
        prev, t = t, block.sub("", t)
    return t.strip() == ""


def reminder_text(ws, cfg, line=None):
    """The explanation block the author asked for, plus one line on which checks have not looked at the draft as it
    is now. The line is read from the summary `loop update` wrote; nothing is computed here, so the hook stays fast.
    An unreadable summary is said, not skipped: silence would read as "all checked"."""
    text = REMINDER.format(name=cfg["name"])
    line = coverage_line(ws, cfg) if line is None else line
    if willow_rule()[0] is None:
        # Said, not silent: without the plugin's rule the built-in copy decides what reaches human/, and it may lag.
        line = (line + "；" if line else "") + "哪些不是作者说的：没找到许愿柳的规则文件，用的是写作循环内置的旧规则"
    return text + ("\n" + line if line else "")


HISTORY_HEAD = "稿件「{name}」（这个会话是它的历史来源，不记录原话）"


def coverage_line(ws, cfg):
    try:
        from loop import coverage as V
        line = V.live_line(ws, cfg)
    except Exception as e:  # noqa: BLE001 -- any failure here must still reach the agent as text
        line = f"覆盖：摘要读不出（{type(e).__name__}），不能当作都查过了"
    return line


def willow_speaks():
    """Whether the installed wishing-willow speaks for other sources ("inbox": 1 in its rule file)."""
    rule = willow_rule()[0]
    return isinstance(rule, dict) and rule.get("inbox") == 1


def refresh_note(ws, cfg, now):
    """After a write that can change the coverage line (the draft, the ledger, a git command), rewrite willow's note
    at once: the update it starts runs detached, and the next prompt must not hear the line from before the write."""
    if not willow_speaks():
        return
    try:
        from loop import outlet as O
        O.refresh(ws, coverage_line(ws, cfg))
    except Exception as e:  # noqa: BLE001 -- said; the next prompt corrects the line in any case
        HL.record_event(ws, "hook_error", f"许愿柳的留言没刷新（{type(e).__name__}：{e}），下一条消息时会更正", now=now)


def _said(text):
    return {"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": text}} if text else None


def state_change(ws, cfg, now):
    """How the paper's state changed since the last prompt of this manuscript's own session, said once and here: the
    line itself reads the same every turn, and willow's note may be read before this prompt writes it. Uses the state
    coverage_line just computed. None when nothing changed; a failure is recorded, never raised."""
    try:
        from loop import coverage as V
        from loop import state as S
        st = V.last_state(ws)
        if st is None:
            return None
        said = S.change_since_told(ws, st, cfg["name"])
        S.mark_told(ws, st)
        return said
    except Exception as e:  # noqa: BLE001 -- the line still reaches the model; only the change note is lost
        HL.record_event(ws, "hook_error", f"论文状态的变化没算出来（{type(e).__name__}：{e}），这一轮只有那一行", now=now)
        return None


def through_willow(ws, cfg, payload, role, line, now):
    """One outlet: None when this hook says everything itself (the installed wishing-willow does not speak for other
    sources, this is the session's first prompt, or leaving the note failed); otherwise what the hook must still add,
    "" when willow's note already reads as the line does now. The note (engine/loop/outlet.py) lists the sessions this
    manuscript has; the two UserPromptSubmit hooks run in parallel, so willow reads the note as it was before this
    prompt, and a line that has changed since (an edit outside Claude) is corrected here rather than left standing."""
    if not willow_speaks():
        return None
    head = HISTORY_HEAD.format(name=cfg["name"])
    try:
        from loop import outlet as O
        first, said = O.enrol(ws, cfg, payload.get("session_id"), role, payload.get("prompt_id"),
                              full=REMINDER.format(name=cfg["name"]), line=line, history_head=head)
    except Exception as e:  # noqa: BLE001 -- the author must still be told; the hook then says it itself
        HL.record_event(ws, "hook_error", f"留言没写进许愿柳（{type(e).__name__}：{e}），写作循环这一轮自己说", now=now)
        return None
    if first:
        if role == "history":
            refresh_card(ws)
        return None
    want = ((head + line) if line else "") if role == "history" else (line or "")
    if (said or "") == want:
        return ""
    return f"写作循环 · {cfg['name']}：更正许愿柳刚转达的那一行，以这一行为准——" + (want or "现在没有要说的")


def on_prompt(payload, regs, now):
    ws, cfg = session_ws(payload, regs)
    if ws is None:
        said = []
        for hws, hcfg in history_wss(payload, regs):
            line = coverage_line(hws, hcfg)
            extra = through_willow(hws, hcfg, payload, "history", line, now)
            if extra is None:
                extra = HISTORY_HEAD.format(name=hcfg["name"]) + line if line else ""
            if extra:
                said.append(extra)
        return _said("\n".join(said))
    prompt = payload.get("prompt")
    if not isinstance(prompt, str):
        HL.record_event(ws, "hook_error", "UserPromptSubmit 的载荷里没有字符串字段 prompt（运行时字段名变了？）", now=now)
        return None
    line = coverage_line(ws, cfg)
    change = state_change(ws, cfg, now)
    extra = through_willow(ws, cfg, payload, "primary", line, now)
    body = reminder_text(ws, cfg, line) if extra is None else extra
    reminder = _said("\n".join(x for x in (change, body) if x))
    if is_envelope(prompt, willow_rule()[0]):
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


def _manuscript_top(t, cfg):
    """The git top of the manuscript checkout holding path t (the configured prefix or the repository, or a worktree
    inside either), or None when t lies in neither. t need not exist yet: the nearest existing parent is asked."""
    d = os.path.dirname(_real(t))
    while d and not os.path.isdir(d) and os.path.dirname(d) != d:
        d = os.path.dirname(d)
    top = toplevel(d) if d else None
    roots = [r for r in (cfg["transcripts"].get("cwd_prefix"), cfg.get("repo")) if r]
    return top if top and any(_under(top, r) for r in roots) else None


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
        if t and payload.get("session_id") in C.session_ids(cfg) and not _under(payload.get("cwd"), cfg["transcripts"]["cwd_prefix"]):
            # A session named by id that runs elsewhere edits the draft by absolute path: the path counts against the
            # manuscript's checkout that holds it, never against the other repository the session happens to run in.
            top = _manuscript_top(t, cfg)
        if t and top and _under(t, top):
            rel = os.path.relpath(_real(t), _real(top)).replace(os.sep, "/")
            led = cfg.get("ledger") or {}
            if _is_draft(rel, cfg["draft"]["glob"]) or rel == led.get("path") or \
                    (led.get("evidence_dir") and rel.startswith(led["evidence_dir"].rstrip("/") + "/")):
                spawn(ws, f"write:{rel}")
                refresh_note(ws, cfg, now)
                ensure_producer(ws)
    elif tool == "Bash" and GIT_RE.search(ti.get("command") or ""):
        spawn(ws, "git")
        refresh_note(ws, cfg, now)
        # 来源进程空闲 30 分钟会自退；一轮很长时改稿与提交都在轮内，等不到下一次提示（10-04 一张卡片落后一小时）。
        ensure_producer(ws)
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
    """The gate is read before the stop is recorded: a Stop the gate blocks does not end the turn, and the notch must
    not say it did (grill 09-22 #2). Either way an update runs, so the index is rebuilt at every Stop."""
    ws, cfg = session_ws(payload, regs)
    if ws is None:
        return None
    out = None
    try:
        ensure_producer(ws)
        if (cfg.get("gates") or {}).get("rewrites"):
            out = stop_gate(payload, ws, cfg, now)
    finally:
        spawn(ws, "stop" if out is None else "stop:blocked")
    return out


def on_stop_failure(payload, regs, now, spawn):
    """An API error ended the turn (Claude Code fires StopFailure instead of Stop; its output is ignored). The turn is
    over, so the notch stops saying "running"; it was not finished, so no landing card. No gate: nothing can be blocked."""
    ws, _cfg = session_ws(payload, regs)
    if ws is not None:
        spawn(ws, "stop:error")
    return None


def _unless_submitted(spawn):
    """K11 power (2026-10-01): an update with the checks it makes due costs most of a minute of one core, and every Stop, draft
    write and git command asks for one. A paper whose claims-ledger stage names a submission needs none until the stage
    changes back; `loop update` by hand still runs. A config that cannot be read starts the update as before."""
    def run(ws, reason):
        try:
            from loop import config as C
            from loop.cli import _submitted
            if _submitted(C.load(ws)):
                return None
        except Exception:  # noqa: BLE001 -- the update reports its own trouble
            pass
        return spawn(ws, reason)
    return run


def handle(payload, regs, spawn=spawn_update, now=None):
    now = time.time() if now is None else now
    spawn = _unless_submitted(spawn)
    ev = payload.get("hook_event_name")
    if ev == "UserPromptSubmit":
        return on_prompt(payload, regs, now)
    if ev == "PreToolUse":
        return on_pre_tool(payload, regs, now)
    if ev == "PostToolUse":
        return on_post_tool(payload, regs, now, spawn)
    if ev == "Stop":
        return on_stop(payload, regs, now, spawn)
    if ev == "StopFailure":
        return on_stop_failure(payload, regs, now, spawn)
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
