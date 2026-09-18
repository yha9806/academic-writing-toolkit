"""Index: everything under workspace/index/ is derived and can be rebuilt byte for byte (spec T9).

Sources of truth: the manuscript's git history, the session transcripts, the saved source texts (in git).
index/sources.json records what the index was built from, so `rebuild --check` can say why bytes differ:
  - the sources moved on (new commit, transcript grew)   → 索引落后于真源
  - the engine code changed                               → 引擎改过
  - neither                                                → 索引被改动过
"""
import hashlib
import json
import os
from pathlib import Path

from . import align as A
from . import changesets as CS
from . import checks as K
from . import config as C
from . import explain as EX
from . import gitio
from . import history as H
from . import threads as TH
from . import transcripts as T

FILES = ("sentences.json", "changesets.json", "checks.json", "threads.json", "explanations.json", "sources.json")


def dump(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=1) + "\n").encode("utf-8")


def engine_hash():
    here = Path(__file__).resolve().parent
    h = hashlib.sha1()
    for p in sorted(here.glob("*.py")):
        h.update(p.name.encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:12]


def cached_aligner(cache_dir):
    """A.align with its results kept on disk, keyed by the inputs and the engine code.

    Alignment is the slow part of a rebuild (difflib over every consecutive pair of versions), and a new
    commit adds one pair; without this every update re-aligns the whole history. A result is always passed
    through JSON, computed or loaded, so a cold and a warm cache give the same bytes. An unreadable cache
    file is recomputed, never trusted."""
    d = Path(cache_dir)
    salt = engine_hash()

    def aligner(old, new, old_groups=None, new_groups=None):
        key = hashlib.sha1(json.dumps([salt, old, new, old_groups, new_groups], ensure_ascii=False).encode()).hexdigest()
        p = d / f"{key}.json"
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
        res = json.loads(json.dumps(A.align(old, new, old_groups, new_groups)))
        d.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{key}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(res), encoding="utf-8")
        tmp.replace(p)
        return res
    return aligner


def build(cfg, cache=None):
    """Return {filename: bytes} for the whole index, plus a small summary dict."""
    with gitio.batch(cfg["repo"]):  # one cat-file for every blob read below (load report F3)
        return _build(cfg, cache)


def _build(cfg, cache):
    head = gitio.rev_parse(cfg["repo"], cfg["ref"])
    versions = H.load_versions(cfg, until=head)
    transitions = H.assign_ids(versions, aligner=cached_aligner(Path(cfg["_ws"]) / "cache" / "align"))
    conv = T.read(cfg, scan_cache=Path(cfg["_ws"]) / "cache" / "transcript-scan.json")
    threads = TH.build(conv, versions)
    changesets = CS.build(versions, transitions, conv)
    explanations = EX.build(conv)
    current = versions[-1] if versions else None
    chk = K.check_version(cfg, current, cache, at=head) if current and cfg.get("ledger") else None
    if chk:
        chk = {k: v for k, v in chk.items() if k not in ("evaluated", "reused")}  # cache state is not content
        chk["draft_version"] = current["sha"]
    ws = Path(cfg["_ws"])
    docs = {
        "sentences.json": {"head": head, "versions": [{k: v[k] for k in ("sha", "time", "subject", "path", "blob", "sentences")}
                                                      for v in versions]},
        "changesets.json": {"head": head, "changesets": changesets},
        "checks.json": chk,
        "threads.json": {"threads": threads, "assistant": conv["assistant"], "unclassified": conv["unclassified"]},
        "explanations.json": {"explanations": explanations},
        "sources.json": {"ref": cfg["ref"], "head": head, "engine": engine_hash(),
                         "transcripts": sorted([str(Path(p).relative_to(C.expand(cfg["transcripts"]["projects_dir"]))), n]
                                               for p, n in conv["branch_files"])},
    }
    summary = summarize(cfg, head, versions, changesets, chk, threads, explanations)
    return {name: dump(doc) for name, doc in docs.items()}, summary


def summarize(cfg, head, versions, changesets, chk, threads, explanations=()):
    st = {}
    if chk:
        for x in chk["sentences"].values():
            for e in x["ledger"]:
                st[e["status"]] = st.get(e["status"], 0) + 1
    return {
        "name": cfg["name"], "head": head[:7], "versions": len(versions),
        "sentences": len(versions[-1]["sentences"]) if versions else 0,
        "changesets": len(changesets),
        "mixed": sum(c["status"] == "mixed" for c in changesets),
        "all_unknown": sum(c["status"] == "none" for c in changesets),
        "ledger": chk["ledger_total"] if chk else 0, "ledger_status": st,
        "unattached_ledger": len(chk["unattached"]) if chk else 0,
        "messages": len(threads), "messages_attached": sum(1 for t in threads if t["attached"]),
        "messages_before_first_version": sum(1 for t in threads if t["draft_version"] is None),
        "explained": sum(1 for e in explanations if e["reading"] is not None),
        "latest": _latest(explanations),
    }


def _latest(explanations):
    """The author's most recent message and what has been said since, for the notch's reply card."""
    if not explanations:
        return None
    e = explanations[-1]
    return {"mid": e["mid"], "ts": e["ts"], "replies": len(e["replies"]),
            "last_reply": e["replies"][-1] if e["replies"] else None,
            "reading": e["reading"], "changed": e["changed"]}


def load_summary(cfg):
    """The summary of the index as it is on disk, without rebuilding anything. None if it is not there."""
    d = Path(cfg["_ws"]) / "index"
    try:
        docs = {name: json.loads((d / name).read_text(encoding="utf-8")) for name in FILES}
    except (OSError, ValueError):
        return None
    versions = docs["sentences.json"]["versions"]
    return summarize(cfg, docs["sources.json"]["head"], versions, docs["changesets.json"]["changesets"],
                     docs["checks.json"], docs["threads.json"]["threads"], docs["explanations.json"]["explanations"])


def write(cfg, files):
    d = Path(cfg["_ws"]) / "index"
    d.mkdir(exist_ok=True)
    for name, data in files.items():
        tmp = d / f".{name}.tmp"
        tmp.write_bytes(data)
        tmp.replace(d / name)


def check(cfg, fresh):
    """Compare on-disk index with freshly built bytes. Returns (differences, cause or None)."""
    d = Path(cfg["_ws"]) / "index"
    diffs = []
    for name in FILES:
        p = d / name
        if not p.exists():
            diffs.append((name, "缺失"))
        elif p.read_bytes() != fresh[name]:
            diffs.append((name, "不同"))
    if not diffs:
        return [], None
    try:
        old = json.loads((d / "sources.json").read_bytes())
    except (OSError, json.JSONDecodeError):
        return diffs, "sources.json 读不出，无法判断原因"
    new = json.loads(fresh["sources.json"])
    if (old.get("head"), old.get("transcripts")) != (new["head"], new["transcripts"]):
        return diffs, "索引落后于真源（分支有新提交或会话记录有新内容）"
    if old.get("engine") != new["engine"]:
        return diffs, "引擎代码改过，索引是旧引擎生成的"
    return diffs, "真源与引擎都没变，索引却不同：索引被改动过"
