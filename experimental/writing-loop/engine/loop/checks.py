"""Mechanical checks per sentence, recomputed only for sentences whose inputs changed.

For one draft version:
  - ledger: each ledger entry is attached to the sentence(s) its `draft` fragment occurs in; its `span` is looked up
    verbatim (after the same normalisation) in the saved source file at that commit. Status is a fact, never a verdict:
    found / not_found / file_missing / no_source. `at` gives the offsets in the normalised source, for cutting (T3).
  - citation keys in brackets, mapped through the manuscript's own KEYMAP; unknown bracket tokens are listed.
  - placeholders ([X1%], [N], …) are listed.
  - dagger: a key whose ledger evidence is only unverified/title_only must carry †, and only such keys may.
  - keys cited here with no ledger entry anywhere.
Ledger entries whose fragment occurs in no sentence are returned as unattached.
"""
import ast
import hashlib
import json
import re

from . import gitio
from .text import norm

WEAK = {"unverified", "title_only"}
_PLACEHOLDER = re.compile(r"[A-Z]\d?%|Δ\w|[A-Z]\d? range|meets/misses|lowers/does not lower")


def load_keymaps(cfg, commit):
    src = gitio.show(cfg["repo"], commit, cfg["ledger"]["keymap_from"])
    maps = {"KEYMAP": {}, "NARR": {}, "PLACE": set()}
    if src is None:
        return maps
    for node in ast.parse(src).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and getattr(node.targets[0], "id", None) in maps:
            maps[node.targets[0].id] = ast.literal_eval(node.value)
    maps["PLACE"] = set(maps["PLACE"])
    return maps


def _brackets(text):
    return re.findall(r"\[([^\]]+)\]", text)


def _sentence_keys(text, maps):
    keys, unmapped, placeholders = {}, [], []
    for b in _brackets(text):
        if b.startswith("Findings:") or b in maps["PLACE"]:
            placeholders.append(b)
            continue
        for part in (x.strip() for x in b.split(";")):
            dag = part.endswith("†")
            bare = part.rstrip("†").strip()
            if bare in maps["KEYMAP"]:
                keys.setdefault(maps["KEYMAP"][bare], set()).add(dag)
            elif not bare:
                placeholders.append(part)  # a lone [†]
            elif bare in maps["PLACE"] or _PLACEHOLDER.fullmatch(bare):
                placeholders.append(part)
            else:
                unmapped.append(part)
    for phrase, key in maps["NARR"].items():
        if phrase in text:
            keys.setdefault(key, set()).add("[†]" in text[text.find(phrase):text.find(phrase) + len(phrase) + 4])
    return keys, unmapped, placeholders


class RawCache:
    """Normalised source texts, keyed on blob id so an unchanged file is read once."""

    def __init__(self, cfg, commit):
        self.cfg, self.commit, self.by_blob = cfg, commit, {}
        self.blobs = gitio.tree_blobs(cfg["repo"], commit, cfg["ledger"]["evidence_dir"])

    def blob(self, path):
        return self.blobs.get(path)

    def get(self, path):
        blob = self.blobs.get(path)
        if blob is None:
            return None, None
        if blob not in self.by_blob:
            self.by_blob[blob] = norm(gitio.show(self.cfg["repo"], self.commit, path) or "")
        return blob, self.by_blob[blob]


def _attach_ledger(sentences, ledger):
    """sid -> [entry]; plus entries attached nowhere. A fragment may span sentences: attach to every one it overlaps."""
    offsets, pos, parts = [], 0, []
    for s in sentences:
        t = norm(s["text"])
        offsets.append((pos, pos + len(t), s["sid"]))
        parts.append(t)
        pos += len(t) + 1
    body = " ".join(parts)
    attached, unattached = {}, []
    for e in ledger:
        frag = norm(e.get("draft") or "")
        i = body.find(frag) if frag else -1
        if i < 0:
            unattached.append(e)
            continue
        for a, b, sid in offsets:
            if a < i + len(frag) and i < b:
                attached.setdefault(sid, []).append(e)
    return attached, unattached


def _entry_status(cfg, e, raws):
    out = {"id": e.get("id"), "key": e.get("key"), "tier": e.get("tier"), "source": e.get("source")}
    if not e.get("source") or not e.get("span"):
        return {**out, "status": "no_source"}
    blob, raw = raws.get(f"{cfg['ledger']['evidence_dir']}/{e['source']}")
    if raw is None:
        return {**out, "status": "file_missing"}
    span = norm(e["span"])
    i = raw.find(span)
    if i < 0:
        return {**out, "status": "not_found", "source_blob": blob}
    return {**out, "status": "found", "source_blob": blob, "at": [i, i + len(span)]}


def check_version(cfg, version, cache=None, at=None, ledger=None):
    """Return {"sentences": {sid: result}, "unattached": [...], "evaluated": n, "reused": n}.
    at: commit whose ledger, key maps and sources are used (default: the version's own commit; the index passes the
        branch head, because the ledger can change without the draft changing).
    cache: dict persisted by the caller; a sentence is re-evaluated only when its text, its attached ledger entries,
        the blobs of their source files, or the key maps change.
    ledger: override the ledger read from git (used to inject faults in tests)."""
    commit = at or version["sha"]
    if ledger is None:
        ledger = json.loads(gitio.show(cfg["repo"], commit, cfg["ledger"]["path"]) or "[]")
    maps = load_keymaps(cfg, commit)
    maps_sig = hashlib.sha1(json.dumps([maps["KEYMAP"], maps["NARR"], sorted(maps["PLACE"])], sort_keys=True).encode()).hexdigest()
    weak_only = {}
    for e in ledger:
        weak_only.setdefault(e["key"], True)
        weak_only[e["key"]] &= e.get("tier") in WEAK
    attached, unattached = _attach_ledger(version["sentences"], ledger)
    raws = RawCache(cfg, commit)
    cache = {} if cache is None else cache
    results, evaluated, reused = {}, 0, 0
    for s in version["sentences"]:
        entries = attached.get(s["sid"], [])
        blobs = [raws.blob(f"{cfg['ledger']['evidence_dir']}/{e['source']}") if e.get("source") else None for e in entries]
        sig = hashlib.sha1(json.dumps([norm(s["text"]), entries, blobs, maps_sig,
                                       {k: weak_only.get(k) for k in sorted({e["key"] for e in entries})}],
                                      sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        if sig in cache:
            results[s["sid"]] = cache[sig]
            reused += 1
            continue
        keys, unmapped, placeholders = _sentence_keys(s["text"], maps)
        ledger_rows = [_entry_status(cfg, e, raws) for e in entries]
        no_entry = sorted(k for k in keys if k not in weak_only)
        dagger = []
        for k, dags in sorted(keys.items()):
            if k not in weak_only:
                continue
            if weak_only[k] and False in dags:
                dagger.append({"key": k, "fact": "只有未核实或仅标题的证据，但这里没加 †"})
            if not weak_only[k] and True in dags:
                dagger.append({"key": k, "fact": "有存档原文证据，但这里加了 †"})
        res = {"keys": sorted(keys), "unmapped": unmapped, "placeholders": placeholders, "ledger": ledger_rows,
               "keys_without_ledger": no_entry, "dagger": dagger}
        cache[sig] = res
        results[s["sid"]] = res
        evaluated += 1
    return {"commit": commit, "sentences": results, "evaluated": evaluated, "reused": reused,
            "unattached": [{"id": e.get("id"), "key": e.get("key"), "draft": e.get("draft")} for e in unattached],
            "ledger_total": len(ledger)}
