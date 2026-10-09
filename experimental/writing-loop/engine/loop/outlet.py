"""What the writing loop would say to the model, left for the wishing-willow plugin to say (one outlet).

Two UserPromptSubmit hooks used to talk to the model in one session, this loop's and wishing-willow's, with different
rules for which turns get what. When the installed wishing-willow says it speaks for other sources (`"inbox": 1` in
its envelopes.json), the hook leaves a note in `<willow state dir>/inbox/awt-loop.<digest>.json` instead:

  {"schema": 1, "source": "awt-loop", "label": "写作循环 · <name>", "workspace": <name>,
   "sessions": {<session id>: {"role": "primary" | "history", "since": <id of the first prompt seen>}},
   "full": <the explanation block>, "always": <the coverage line>, "history_head": ..., "history": ...,
   "todo": [{"id", "title", "state", "closed"}] | null, "todo_why": <why null>, "hookup": true | false,
   "verdict": {"ready": true | false, "text": <one line>}, "updatedAt": ...}

`todo` and `hookup` let willow match its list against the manuscript's to-do items (spec 2026-10-04
manuscript-todo-hookup, D1 and D4): closed items are kept, so willow can tell "closed" from "not there"; with no ledger
or a state that could not be computed it is null with the reason, never [], which would read as "all closed". `hookup`
is the workspace config's `hookup`, off when absent; willow matches only when it is true.

`verdict` lets willow hold a reply that says the paper is done against the paper's state: `ready` is true only where
`loop state` exits 0 (state.ready: 待作者终审, or 已投稿 with nothing in the way), `text` is the first part of the
line, the verdict and the stage (state.head), never the whole line. Willow reads exactly this shape: ready a real
boolean, text a non-empty string; anything else, null included, it reports every turn as unreadable. A state that
could not be computed is written as not ready, never left out: no key would read as nothing to hold the reply against.

Which sessions belong to the manuscript is still decided here (cwd prefix and branch, or the session ids listed under
transcripts.sessions); willow only matches the session ids written here, so that rule is not copied. The two hooks run in parallel and a note written during a prompt is not read for
it, so the first prompt of a session is said by the hook, and `since` tells willow to skip that one.

The coverage line is judged current when it is read (fingerprint and HEAD, `coverage.load_summary`), so every refresh
goes through that same read (`coverage.live_line`) and the note is refreshed wherever the line can change: after a
summary is written or removed, and after a tool writes the draft, the ledger or runs git. What is left (an edit made
outside Claude) the hook catches on the next prompt by comparing the note with the line as it reads then.
"""
import hashlib
import json
import os
import time
from pathlib import Path

SCHEMA = 1
KEEP = 50  # sessions kept in one note; the oldest go first


def available(rule):
    """Whether the wishing-willow rule file (loop_hook.willow_rule) says that plugin speaks for other sources."""
    return isinstance(rule, dict) and rule.get("inbox") == 1


def state_dir():
    return Path(os.environ.get("WILLOW_STATE_DIR") or Path.home() / ".claude" / "willow")


def note_path(ws):
    digest = hashlib.sha1(str(Path(ws).resolve()).encode("utf-8")).hexdigest()[:10]
    return state_dir() / "inbox" / f"awt-loop.{digest}.json"


def read(ws):
    try:
        n = json.loads(note_path(ws).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return n if isinstance(n, dict) else None


def _write(ws, note):
    p = note_path(ws)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(f".{p.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(note, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(p)  # willow reads the old note or the new one, never half of one


def _texts(note, line):
    head = note.get("history_head") or ""
    return {"always": line or "", "history": (head + line) if (head and line) else ""}


def _todo(ws):
    """The to-do items of the state the line was just computed from (coverage.live_line), as {"todo", "todo_why"}."""
    from . import coverage as V
    st = V.last_state(ws)
    if st is None:
        return {"todo": None, "todo_why": "论文状态算不出"}
    if not st.get("configured"):
        return {"todo": None, "todo_why": "没登记主张清单"}
    if st.get("unread"):
        return {"todo": None, "todo_why": "主张清单读不到"}
    return {"todo": [{"id": t["id"], "title": t["title"], "state": t["state"], "closed": bool(t["closed"])}
                     for t in st.get("todo") or []]}


def _verdict(ws):
    """The paper's verdict from the same state as the line (coverage.live_line), as {"verdict": {"ready", "text"}}."""
    from . import coverage as V
    from . import state as S
    st = V.last_state(ws)
    if st is None:
        return {"verdict": {"ready": False, "text": "论文状态：算不出"}}
    text = " ".join(S.head(st).split()) or "论文状态：算不出"
    return {"verdict": {"ready": S.ready(st) is True, "text": text}}


def enrol(ws, cfg, session_id, role, prompt_id, *, full, line, history_head):
    """Note this session and the texts as they read now. Returns (first, said): `first` when the session was not
    noted in this role before (the caller says everything itself this prompt), and `said`, the line willow was going
    to say for it this prompt, as the note held it before this write (the caller corrects it when it differs)."""
    if not isinstance(session_id, str) or not session_id:
        raise ValueError("载荷里没有会话 id")
    old = read(ws) or {}
    sessions = old.get("sessions") if isinstance(old.get("sessions"), dict) else {}
    cur = sessions.get(session_id)
    first = not (isinstance(cur, dict) and cur.get("role") == role)
    said = None if first else (old.get("history") if role == "history" else old.get("always"))
    if first:
        sessions.pop(session_id, None)
        sessions[session_id] = {"role": role, "since": prompt_id}
        sessions = dict(list(sessions.items())[-KEEP:])
    name = cfg["name"]
    note = {"schema": SCHEMA, "source": "awt-loop", "label": f"写作循环 · {name}", "workspace": name,
            "sessions": sessions, "full": full, "history_head": history_head, "hookup": cfg.get("hookup") is True}
    note.update(_texts(note, line))
    note.update(_todo(ws))
    note.update(_verdict(ws))
    note["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write(ws, note)
    return first, said


def refresh(ws, line):
    """Rewrite the lines of an existing note; a workspace no session has met gets none. Returns whether one was."""
    note = read(ws)
    if note is None:
        return False
    note.update(_texts(note, line))
    note.pop("todo_why", None)
    note.update(_todo(ws))  # the switch stays as the last prompt read it from the config
    note.update(_verdict(ws))
    note["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    _write(ws, note)
    return True
