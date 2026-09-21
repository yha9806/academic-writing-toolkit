"""Change sets: one per commit that changed the draft, sentence by sentence, each row with a trigger or △.

Trigger sources, in order:
  (a) the commit message carries `Loop-Trigger: <message id>` — source 提交信息;
  (b) an author message between the previous draft version and this commit names the row's sentence,
      quotes it, or shares distinctive changed words with it — source 脚本推断, with the evidence.
      A word is distinctive if this commit brings it into the draft or removes it from the draft entirely
      (one such word is enough), or if it occurs in at most RARE_DF sentences of the
      previous version (two such words needed). Words spread across the draft ("image", "evaluation") never count:
      a first version that accepted any two shared words attributed whole commits on exactly those;
  (c) otherwise △ 追不到触发源.
A change set whose rows point to more than one trigger, or mix a trigger with △, is marked mixed (spec T13).
"""
import re

from . import align as A
from .text import norm
from .threads import LABEL, quoted_fragments

TRAILER = re.compile(r"^Loop-Trigger:\s*(\S+)\s*$", re.M)
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]{4,}")
STOP = set("""about above after again against because before being below between could doing during every first
further having other their there these those through under until where which while would should since shall
might whose within without also only than then them they this that with from into were been have more most
such some each both much many very what when your ours ourselves itself""".split())
# Words the author uses about the document itself; "看看这个 pattern" is not about a sentence containing "pattern".
PROCESS_WORDS = set("""paper papers pattern patterns abstract introduction section sections sentence sentences draft drafts
title titles version versions reference references citation citations figure figures table tables paragraph
paragraphs words style review reviewer reviewers submission""".split())
MIN_SHARED_RARE = 2
RARE_DF = 2


def _sent(s):
    d = {"sid": s["sid"], "label": s["label"], "text": s["text"]}
    for k in ("section", "par", "path", "line"):   # 定位（候选 A）；老索引里没有就没有
        if k in s:
            d[k] = s[k]
    return d


def _changed_words(old_text, new_text):
    words = set()
    for op, seg in A.word_ops(old_text, new_text):
        if op != "eq":
            words |= {w.lower() for w in _WORD.findall(seg)}
    return words - STOP - PROCESS_WORDS


def rows_for(prev, cur, al):
    P, S = prev["sentences"], cur["sentences"]
    rows = []
    moved = set(al["moved"])
    for i, j, r in al["pairs"]:
        if r < 0.999:
            rows.append({"kind": "edited", "old": _sent(P[i]), "new": _sent(S[j]), "ratio": r, "moved": j in moved,
                         "ops": A.word_ops(P[i]["text"], S[j]["text"])})
        elif j in moved:
            rows.append({"kind": "moved", "old": _sent(P[i]), "new": _sent(S[j])})
    for i, run, r, parts in al["splits"]:
        joined = " ".join(S[j]["text"] for j in run)
        rows.append({"kind": "split", "old": _sent(P[i]), "new": [_sent(S[j]) for j in run], "ratio": r,
                     "ops": A.word_ops(P[i]["text"], joined)})
    for run, j, r, parts in al["merges"]:
        joined = " ".join(P[i]["text"] for i in run)
        rows.append({"kind": "merge", "old": [_sent(P[i]) for i in run], "new": _sent(S[j]), "ratio": r,
                     "ops": A.word_ops(joined, S[j]["text"])})
    derived = {j: (i, c) for j, i, c in al.get("derived", [])}
    for j in al["added"]:
        row = {"kind": "added", "new": _sent(S[j])}
        if j in derived:
            i, c = derived[j]
            row["reuses"] = {**_sent(P[i]), "share": c}
        rows.append(row)
    absorbed = {i: (j, c) for i, j, c in al.get("absorbed", [])}
    for i in al["removed"]:
        row = {"kind": "removed", "old": _sent(P[i])}
        if i in absorbed:
            j, c = absorbed[i]
            row["survives_in"] = {**_sent(S[j]), "share": c}
        rows.append(row)
    return rows


def _row_texts(row):
    olds = row.get("old")
    news = row.get("new")
    olds = [] if olds is None else (olds if isinstance(olds, list) else [olds])
    news = [] if news is None else (news if isinstance(news, list) else [news])
    return olds, news


def vocabulary(version):
    """word -> number of sentences containing it."""
    df = {}
    for s in version["sentences"]:
        for w in {w.lower() for w in _WORD.findall(s["text"])} - STOP:
            df[w] = df.get(w, 0) + 1
    return df


def infer_trigger(row, messages, df_prev, df_cur):
    """Return (message id, evidence) or (None, None). Only checkable evidence counts."""
    olds, news = _row_texts(row)
    labels = {s["label"] for s in olds}  # labels are read against the version the author was looking at
    old_text = " ".join(s["text"] for s in olds)
    new_text = " ".join(s["text"] for s in news)
    changed = _changed_words(old_text, new_text)
    best = None
    for m in reversed(messages):  # latest first: the nearest request wins ties
        named = sorted({x.group(1) for x in LABEL.finditer(m["text"])} & labels)
        if named:
            return m["mid"], {"method": "句子编号", "matched": named}
        quotes = [q for q in quoted_fragments(m["text"]) if q in norm(old_text) or q in norm(new_text)]
        if quotes:
            return m["mid"], {"method": "引号原文", "matched": [q[:120] for q in quotes]}
        mw = {w.lower() for w in _WORD.findall(m["text"])}
        shared = changed & mw
        entering_or_leaving = sorted(w for w in shared if (w in df_prev) != (w in df_cur))
        rare = sorted(w for w in shared if 0 < df_prev.get(w, 0) <= RARE_DF)
        if entering_or_leaving:
            ev = {"method": "消息里的词是这次提交带进或删出稿子的", "matched": entering_or_leaving}
        elif len(rare) >= MIN_SHARED_RARE:
            ev = {"method": "消息里有两个以上这次改动的少见词", "matched": rare}
        else:
            continue
        if best is None or len(ev["matched"]) > len(best[1]["matched"]):
            best = (m["mid"], ev)
    return best if best else (None, None)


def build(versions, transitions, conv):
    humans = conv["human"]
    known = {h["mid"] for h in humans}
    out = []
    for tr in transitions:
        prev, cur = versions[tr["from"]], versions[tr["to"]]
        rows = rows_for(prev, cur, tr["align"])
        if not rows:
            # 提交碰了稿件文件但没有一句被盯的句子变化（一份真实稿件的 39 个里 22 个是这种）：不是改动集，不进索引。
            continue
        trailer = TRAILER.findall(cur.get("body", ""))
        window = [h for h in humans if prev["time"] < h["t"] <= cur["time"]]
        df_prev, df_cur = vocabulary(prev), vocabulary(cur)
        for k, row in enumerate(rows):
            row["rid"] = f"{cur['sha'][:7]}:{k:02d}"
            if trailer:
                mid = trailer[0]
                if mid in known:
                    row["trigger"] = {"source": "提交信息", "mid": mid}
                else:
                    row["trigger"] = {"source": "△", "why": f"提交信息指向的消息 {mid} 不在会话记录里"}
                continue
            mid, ev = infer_trigger(row, window, df_prev, df_cur)
            if mid:
                row["trigger"] = {"source": "脚本推断", "mid": mid, **ev}
            else:
                row["trigger"] = {"source": "△", "why": "追不到触发源" if window else "上一版定稿到这次提交之间没有你的消息"}
        mids = sorted({r["trigger"]["mid"] for r in rows if r["trigger"].get("mid")})
        unknown = sum(1 for r in rows if r["trigger"]["source"] == "△")
        if len(mids) > 1 or (mids and unknown):
            status = "mixed"
        elif mids:
            status = "one"
        else:
            status = "none"
        out.append({"id": cur["sha"][:7], "commit": cur["sha"], "time": cur["time"], "subject": cur["subject"],
                    "from": prev["sha"], "path_from": prev["path"], "path_to": cur["path"],
                    "window_messages": [h["mid"] for h in window], "rows": rows,
                    "triggers": mids, "unknown_rows": unknown, "status": status})
    return out
