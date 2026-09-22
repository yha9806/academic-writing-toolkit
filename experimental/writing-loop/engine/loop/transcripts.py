"""Read Claude Code session transcripts for one manuscript: the author's messages verbatim and Claude's replies.

Transcripts are the source of truth for the conversation (spec T9); nothing here writes to them.
Field names were read from real records, not from documentation:
  - an author-typed message is a `type: user` record with `origin.kind == "human"`;
  - tool results are `type: user` records carrying `toolUseResult`;
  - a message typed while Claude is still working is not a user record at all: it is a
    `type: attachment` record with `attachment.type == "queued_command"`, `attachment.origin.kind == "human"`
    and the words in `attachment.prompt`. A reader that only looks at user records misses
    these, and in real use they included comments on specific sentences;
  - a continued session copies earlier records, so the same message appears in several files and is
    deduplicated by (timestamp, text).
"""
import hashlib
import json
import os
import re
from datetime import datetime

from . import config as C
from pathlib import Path

_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>\s*", re.S)
#: A Bash call whose command commits. Only such a call counts: a commit line in `git log` output is not the session committing.
GIT_COMMIT = re.compile(r"\bgit\b[^\n;&|]*\bcommit\b")


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


def _user_text(content):
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text")


def _unclassified_kind(text):
    t = text.lstrip()
    for tag in ("<local-command-stdout>", "<local-command-caveat>", "<command-name>", "[Request interrupted", "The app was quit", "<task-notification>"):
        if t.startswith(tag):
            return tag
    return "其他"


def sources(cfg):
    """(branch, cwd_prefix) pairs whose sessions belong to this manuscript: the primary one, plus any listed under
    transcripts.also. `also` is read-only history (e.g. a session that once worked on the manuscript); hooks act
    only on the primary source."""
    t = cfg["transcripts"]
    return [(t["git_branch"], str(t["cwd_prefix"]))] + [(s["git_branch"], str(s["cwd_prefix"])) for s in t.get("also", [])]


def session_files(cfg):
    t = cfg["transcripts"]
    root = C.expand(t["projects_dir"])
    prefixes = {C.escaped_project_dir(p) for _, p in sources(cfg)}
    if not root.is_dir():
        return []
    return sorted({p for d in root.iterdir() if d.is_dir() and any(d.name.startswith(x) for x in prefixes)
                   for p in d.glob("*.jsonl")})


def _under(path, root):
    """path is root or inside it (both resolved)."""
    if not path or not root:
        return False
    p = str(Path(path).resolve())
    return p == root or p.startswith(root.rstrip("/") + "/")


def _load_scan(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_scan(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
    tmp.replace(p)


def read(cfg, files=None, scan_cache=None):
    """Return {"human": [...], "assistant": [...], "commit_calls": [...], "unclassified": {kind: n}, "files": [(path, bytes)],
    "bad_lines": n}. `commit_calls` are the `git … commit` calls a session in scope made on this manuscript's repository
    (the command names the repository, or the session works inside it): {"t0", "t1", "session"}, when the call was made
    and when its result came back. git's own output is not read: `git commit -q` prints nothing, and that is how the
    sessions commit.

    scan_cache: optional path to a JSON file remembering, per session file, (size, mtime_ns, holds the branch).
    A file whose size and mtime are unchanged and that did not hold the branch is not read again: most session
    files under a busy repository belong to other branches. Any change to a file means it is read in full."""
    t = cfg["transcripts"]
    srcs = sources(cfg)
    files = session_files(cfg) if files is None else files
    humans, assistants, uncl, bad, seen_files, branch_files = {}, {}, {}, 0, [], []
    tool_cmds, calls = {}, []
    # The repository as a command may name it: as configured, resolved (/var → /private/var), or with ~ for home.
    repo_raw = os.path.expanduser(str(cfg.get("repo") or "")) if cfg.get("repo") else ""
    repo_path = str(Path(repo_raw).resolve()) if repo_raw else ""
    home = str(Path.home())
    repo_names = {n for n in (repo_raw, repo_path) if n}
    repo_names |= {"~" + n[len(home):] for n in repo_names if n.startswith(home + "/")}
    needle = re.compile(rb'"gitBranch"\s*:\s*(?:' + b"|".join(re.escape(json.dumps(b).encode()) for b, _ in srcs) + rb")")

    def add_human(r, raw, channel, command_mode):
        text = _REMINDER.sub("", raw).strip()
        key = (r["timestamp"], text)
        h = humans.get(key)
        if h is None:
            mid = "h-" + hashlib.sha1(f"{r['timestamp']}\x00{text}".encode()).hexdigest()[:10]
            humans[key] = h = {"mid": mid, "ts": r["timestamp"], "t": _ts(r["timestamp"]), "text": text,
                               "channel": channel, "command_mode": command_mode, "sessions": [],
                               "stripped_chars": len(raw) - len(text)}
        if r.get("sessionId") not in h["sessions"]:
            h["sessions"].append(r.get("sessionId"))
    scan = _load_scan(scan_cache) if scan_cache else {}
    for f in files:
        st = f.stat()
        known = scan.get(str(f))
        if isinstance(known, list) and known == [st.st_size, st.st_mtime_ns, False]:
            seen_files.append((str(f), st.st_size))
            continue
        data = f.read_bytes()
        seen_files.append((str(f), len(data)))
        holds = bool(needle.search(data))
        scan[str(f)] = [len(data), st.st_mtime_ns, holds] if len(data) == st.st_size else None
        if not holds:
            continue
        branch_files.append((str(f), len(data)))
        for line in data.decode("utf-8", "replace").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                bad += 1  # a session being written can end mid-line
                continue
            if r.get("isSidechain") or not any(r.get("gitBranch") == b and str(r.get("cwd", "")).startswith(p) for b, p in srcs):
                continue
            typ = r.get("type")
            att = r.get("attachment") if typ == "attachment" else None
            if att and att.get("type") == "queued_command" and (att.get("origin") or {}).get("kind") == "human":
                add_human(r, str(att.get("prompt") or ""), "queued", att.get("commandMode"))
            elif typ == "user" and "toolUseResult" not in r:
                msg = r.get("message") or {}
                raw = _user_text(msg.get("content"))
                if (r.get("origin") or {}).get("kind") == "human":
                    if raw.lstrip().startswith("<bash-input>"):  # `!cmd`: a shell command and its output
                        uncl["<bash-input>"] = uncl.get("<bash-input>", 0) + 1
                    else:
                        add_human(r, raw, "prompt", None)
                elif not r.get("isMeta") and not r.get("isCompactSummary"):
                    kind = (r.get("origin") or {}).get("kind")
                    k = f"origin:{kind}" if kind else _unclassified_kind(raw)
                    uncl[k] = uncl.get(k, 0) + 1
            elif typ == "user":
                # A tool result. Only a commit call on this manuscript's repository is kept: when it ran, in which session.
                for b in (r.get("message") or {}).get("content") or []:
                    if not (isinstance(b, dict) and b.get("type") == "tool_result"):
                        continue
                    cmd, t0, cwd = tool_cmds.get(b.get("tool_use_id"), ("", None, ""))
                    if t0 is None or not GIT_COMMIT.search(cmd):
                        continue
                    if not (repo_path and (any(n and n in cmd for n in repo_names) or _under(cwd, repo_path))):
                        continue
                    calls.append({"t0": t0, "t1": _ts(r["timestamp"]), "session": r.get("sessionId")})
            elif typ == "assistant":
                msg = r.get("message") or {}
                for b in msg.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "Bash":
                        tool_cmds[b.get("id")] = (str((b.get("input") or {}).get("command") or ""), _ts(r["timestamp"]), str(r.get("cwd") or ""))
                texts = [b.get("text", "") for b in msg.get("content") or [] if isinstance(b, dict) and b.get("type") == "text"]
                texts = [x for x in texts if x.strip()]
                if not texts or not msg.get("id"):
                    continue
                a = assistants.setdefault(msg["id"], {"aid": msg["id"], "ts": r["timestamp"], "t": _ts(r["timestamp"]),
                                                      "session": r.get("sessionId"), "parts": []})
                for x in texts:
                    if x not in a["parts"]:
                        a["parts"].append(x)
    if scan_cache:
        _save_scan(scan_cache, {k: v for k, v in scan.items() if v is not None})
    for h in humans.values():
        h["sessions"].sort()
    human = sorted(humans.values(), key=lambda h: (h["t"], h["mid"]))
    assistant = sorted(({**a, "text": "\n\n".join(a.pop("parts"))} for a in assistants.values()), key=lambda a: (a["t"], a["aid"]))
    calls.sort(key=lambda c: (c["t0"], c["t1"], c["session"] or ""))
    return {"human": human, "assistant": assistant, "commit_calls": calls, "unclassified": dict(sorted(uncl.items())), "files": seen_files, "branch_files": branch_files, "bad_lines": bad}
