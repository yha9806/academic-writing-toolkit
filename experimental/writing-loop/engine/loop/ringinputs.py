"""What the manuscript ring can see beyond the coverage summary (spec 2026-09-29-ring-rounds-and-stages).

  landing    the build report (overview.build_report) at the ref: ready to upload, its source commit's time, and
             whether a draft file changed after that commit (R1).
  decisions  every decided register item with the time of the author's message that decided it, found by its uuid in
             the transcripts; its date when the message is not found (R2, R4).
  design     the intent card (target.intent_card) and when it last changed (R3).
  freeze     the claims ledger's stage begins with a word of ring.freeze_stages (default 冻结, 终检), or ring.freeze (R5).

Each is gathered on its own: one that cannot be read is None and the ring keeps its old behaviour for it, and the
reason goes to `problems`. Nothing is written but the uuid-time cache under the workspace.
"""
import datetime as dt
import json
import os
import subprocess
from pathlib import Path

FREEZE_STAGES = ("冻结", "终检")
UUID_TIMES = "uuid-times.json"


def _git(repo, *args):
    r = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else None


def landing(cfg):
    """{"commit", "at", "changed"} or None (no build report configured, or not ready)."""
    from . import catalogue as K
    from . import coverage as V
    from . import overview as O
    path = K.get(cfg, "overview.build_report")
    if not path:
        return None
    repo, ref = cfg["repo"], cfg.get("ref") or "HEAD"
    rep = O.build_report(repo, ref, path)
    if not rep or not rep.get("ready_to_upload") or not rep.get("source_commit"):
        return None
    src = str(rep["source_commit"])
    at = _git(repo, "show", "-s", "--format=%cI", src)
    head = _git(repo, "rev-parse", ref)
    if not at or not head:
        return None
    drafts = V.draft_files(cfg, head)
    changed = bool(drafts) and bool(_git(repo, "diff", "--name-only", src, head, "--", *drafts))
    return {"commit": src[:7], "at": at, "changed": changed}


def _transcript_files(cfg):
    from . import doctor
    files = doctor.all_transcript_files(cfg)
    return files


def uuid_times(cfg, uuids, cache):
    """{uuid: ISO time} for the author messages found. A cache keeps found times; a miss is retried only when the
    transcripts have grown since it was looked for."""
    try:
        known = json.loads(Path(cache).read_text(encoding="utf-8")) if cache and Path(cache).is_file() else {}
    except (OSError, ValueError):
        known = {}
    times, misses = dict(known.get("times") or {}), dict(known.get("misses") or {})
    want = [u for u in uuids if u and u not in times]
    if not want:
        return {u: times[u] for u in uuids if u in times}
    files = _transcript_files(cfg)
    size = sum(os.path.getsize(f) for f in files if os.path.isfile(f))
    want = [u for u in want if misses.get(u) != size]
    needles = {f'"uuid":"{u}"'.encode(): u for u in want}
    for f in files if needles else ():
        try:
            with open(f, "rb") as fh:
                for line in fh:
                    if b'"type":"user"' not in line:
                        continue
                    for n, u in list(needles.items()):
                        if n in line:
                            try:
                                ts = json.loads(line).get("timestamp")
                            except ValueError:
                                ts = None
                            if ts:
                                times[u] = ts
                                del needles[n]
        except OSError:
            continue
        if not needles:
            break
    for u in needles.values():
        misses[u] = size
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        tmp = Path(cache).with_name(f".{Path(cache).name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"times": times, "misses": misses}), encoding="utf-8")
        tmp.replace(cache)
    return {u: times[u] for u in uuids if u in times}


def decisions(cfg, ws, coverage):
    """[{"id", "at"}] for every decided register item, or None when there is no register."""
    risks = (coverage or {}).get("risks")
    if not risks:
        return None
    decided = risks.get("decided") or []
    found = uuid_times(cfg, [d.get("uuid") for d in decided if d.get("uuid")], Path(ws) / "cache" / UUID_TIMES)
    out = []
    for d in decided:
        at = found.get(d.get("uuid")) or d.get("decided_on")
        if at:
            out.append({"id": d.get("id"), "at": at})
    return out


def design(cfg):
    from . import catalogue as K
    card = K.get(cfg, "target.intent_card")
    if not card:
        return {"configured": False, "at": None}
    p = Path(card).expanduser()
    if not p.is_file():
        return {"configured": True, "at": None}
    return {"configured": True, "at": dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat()}


def freeze(cfg, ws):
    from . import catalogue as K
    if K.get(cfg, "ring.freeze") is True:
        return True
    words = K.get(cfg, "ring.freeze_stages") or FREEZE_STAGES
    if not cfg.get("claims"):
        return False
    from . import state as S
    try:
        stage = S.read_ledger(Path(cfg["claims"]).expanduser().read_text(encoding="utf-8"))["stage"]
    except OSError:
        return False
    return any(stage.startswith(w) for w in words)


def parts(cfg, ws):
    """The part-by-part state (loop/parts.py), or None when no part of a rewrite plan is open or there is no ledger."""
    if not cfg.get("claims"):
        return None
    from . import catalogue as K
    from . import overview as O
    from . import parts as P
    from . import state as S
    st = S.compute(cfg, ws)
    path = K.get(cfg, "overview.build_report")
    build = O.build_report(cfg["repo"], cfg.get("ref") or "HEAD", path) if path else None
    return P.compute(cfg, ws, st, build)


def gather(cfg, ws, coverage, problems):
    out = {}
    for key, fn in (("landing", lambda: landing(cfg)), ("decisions", lambda: decisions(cfg, ws, coverage)),
                    ("design", lambda: design(cfg)), ("freeze", lambda: freeze(cfg, ws)), ("parts", lambda: parts(cfg, ws))):
        try:
            out[key] = fn()
        except Exception as e:  # noqa: BLE001 -- one input the ring cannot read leaves the others
            problems.append(f"环·{key}：{type(e).__name__}：{e}")
            out[key] = None if key != "freeze" else False
    return out
