"""Sentence alignment between two versions: one-to-one pairs, splits (1→n), merges (n→1), moves.

The prototype matched every new sentence to its best old sentence independently, so one old
sentence could be claimed twice and a split looked like an edit plus a deletion. Here each old
and each new sentence is used at most once, and splits/merges are recognised explicitly.
"""
import difflib
import re

from .text import norm

EDIT_MIN = 0.6    # a pair below this is not the same sentence
JOIN_MIN = 0.75   # a split/merge must reach this when the parts are joined
JOIN_GAIN = 0.1   # ... and beat the best single pairing by this much
PART_COVER = 0.5  # a candidate part must have at least this share of its characters inside the whole
DERIVED_COVER = 0.5  # an added sentence with at least this share of its words (in 3+-word runs) from one old sentence is shown as reusing it, with the share


def ratio(a, b):
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


MIN_RUN = 3  # shared words only count in runs of at least this many
_WORD = re.compile(r"\w[\w'’-]*")  # punctuation is not part of a word: "alone." and "alone," are the same word


def _cover(part, whole):
    """Share of part's words that appear in whole inside shared runs of MIN_RUN+ words.
    Character-level matching blocks were tried first and rejected: scattered one- and
    two-character matches gave a five-word sentence 0.58 against an unrelated long one."""
    pw, ww = _WORD.findall(part.lower()), _WORD.findall(whole.lower())
    sm = difflib.SequenceMatcher(None, pw, ww, autojunk=False)
    need = min(MIN_RUN, len(pw))
    return sum(b.size for b in sm.get_matching_blocks() if b.size >= need and b.size) / max(1, len(pw))


def _rel(i, n):
    return i / n if n else 0.0


def _runs_around(k, n, lengths=(2, 3)):
    for L in lengths:
        for start in range(k - L + 1, k + 1):
            if start >= 0 and start + L <= n:
                yield list(range(start, start + L))


def _lis_indices(seq):
    """Indices (into seq) of one longest strictly increasing subsequence."""
    import bisect
    tails, tails_idx, prev = [], [], [None] * len(seq)
    for k, x in enumerate(seq):
        p = bisect.bisect_left(tails, x)
        if p == len(tails):
            tails.append(x)
            tails_idx.append(k)
        else:
            tails[p] = x
            tails_idx[p] = k
        prev[k] = tails_idx[p - 1] if p else None
    out, k = [], tails_idx[-1] if tails_idx else None
    while k is not None:
        out.append(k)
        k = prev[k]
    return set(out)


def align(old, new, old_groups=None, new_groups=None):
    """old, new: lists of sentence texts. *_groups: optional paragraph keys; a split or merge
    only joins sentences that share a group.

    Returns {"pairs": [(i, j, r)], "splits": [(i, [j..], r, [r_part..])], "merges": [([i..], j, r, [r_part..])],
             "added": [j], "removed": [i], "moved": [j],
             "derived": [(j, i, cover)], "absorbed": [(i, j, cover)]}
    """
    O = [norm(s) for s in old]
    N = [norm(s) for s in new]
    og = old_groups or [0] * len(O)
    ng = new_groups or [0] * len(N)
    mo, mn = {}, {}  # i -> (j, r), j -> (i, r)

    # 1. identical text, nearest relative position first
    by_text = {}
    for i, s in enumerate(O):
        by_text.setdefault(s, []).append(i)
    for j, s in enumerate(N):
        free = [i for i in by_text.get(s, []) if i not in mo]
        if free:
            i = min(free, key=lambda i: abs(_rel(i, len(O)) - _rel(j, len(N))))
            mo[i], mn[j] = (j, 1.0), (i, 1.0)

    # 2. edited: greedy by similarity, ties broken by relative position
    cand = []
    for i in range(len(O)):
        if i in mo:
            continue
        for j in range(len(N)):
            if j in mn:
                continue
            sm = difflib.SequenceMatcher(None, O[i], N[j], autojunk=False)
            if sm.real_quick_ratio() < EDIT_MIN or sm.quick_ratio() < EDIT_MIN:
                continue
            r = sm.ratio()
            if r >= EDIT_MIN:
                cand.append((-r, abs(_rel(i, len(O)) - _rel(j, len(N))), i, j, r))
    for _, _, i, j, r in sorted(cand):
        if i not in mo and j not in mn:
            mo[i], mn[j] = (j, r), (i, r)

    # 3. splits (one old → consecutive new) and merges (consecutive old → one new)
    def joins(whole_idx, whole_txt, whole_match, parts_txt, parts_match, groups):
        found = []
        n = len(parts_txt)
        for k in range(n):
            if k in parts_match or _cover(parts_txt[k], whole_txt) < PART_COVER:
                continue
            for run in _runs_around(k, n):
                if len({groups[x] for x in run}) != 1:
                    continue
                if any(x in parts_match and parts_match[x][0] != whole_idx for x in run):
                    continue
                R = ratio(whole_txt, " ".join(parts_txt[x] for x in run))
                single = whole_match[1] if whole_match else 0.0
                if R >= JOIN_MIN and R >= single + JOIN_GAIN:
                    found.append((R, whole_idx, run))
        return found

    split_c, merge_c = [], []
    for i in range(len(O)):
        if mo.get(i, (None, 0.0))[1] < 0.999:
            split_c += joins(i, O[i], mo.get(i), N, mn, ng)
    for j in range(len(N)):
        if mn.get(j, (None, 0.0))[1] < 0.999:
            merge_c += joins(j, N[j], mn.get(j), O, mo, og)

    splits, merges, used_o, used_n = [], [], set(), set()
    events = [(R, "split", w, run) for R, w, run in split_c] + [(R, "merge", w, run) for R, w, run in merge_c]
    for R, kind, w, run in sorted(events, key=lambda e: (-e[0], e[1], e[2], e[3])):
        olds, news = ([w], run) if kind == "split" else (run, [w])
        if used_o & set(olds) or used_n & set(news):
            continue
        # every sentence involved must be free, or paired only inside this event
        if any(i in mo and mo[i][0] not in news for i in olds) or any(j in mn and mn[j][0] not in olds for j in news):
            continue
        for i in olds:
            if i in mo:
                del mn[mo.pop(i)[0]]
        for j in news:
            if j in mn:
                del mo[mn.pop(j)[0]]
        used_o |= set(olds)
        used_n |= set(news)
        if kind == "split":
            splits.append((w, run, round(R, 4), [round(ratio(O[w], N[j]), 4) for j in run]))
        else:
            merges.append((run, w, round(R, 4), [round(ratio(O[i], N[w]), 4) for i in run]))

    pairs = sorted((i, j, round(r, 4)) for i, (j, r) in mo.items())
    # 4. moves: pairs outside one longest order-preserving chain
    by_new = sorted(pairs, key=lambda p: p[1])
    keep = _lis_indices([p[0] for p in by_new])
    moved = sorted(p[1] for k, p in enumerate(by_new) if k not in keep)
    added = sorted(j for j in range(len(N)) if j not in mn and j not in used_n)
    removed = sorted(i for i in range(len(O)) if i not in mo and i not in used_o)
    # 5. text reused across a gap: an "added" sentence whose words mostly come from one old sentence
    #    (a split whose halves are no longer adjacent) is not new writing, and says so.
    derived = []
    for j in added:
        best = max(((round(_cover(N[j], O[i]), 4), -i) for i in range(len(O))), default=None)
        if best and best[0] >= DERIVED_COVER:
            derived.append((j, -best[1], best[0]))
    absorbed = []
    for i in removed:
        best = max(((round(_cover(O[i], N[j]), 4), -j) for j in range(len(N))), default=None)
        if best and best[0] >= DERIVED_COVER:
            absorbed.append((i, -best[1], best[0]))
    return {"pairs": pairs, "splits": sorted(splits), "merges": sorted(merges), "added": added, "removed": removed,
            "moved": moved, "derived": derived, "absorbed": absorbed}


def word_ops(a, b):
    """Word-level edit script from a to b: [["eq"|"del"|"ins", text]]."""
    aw, bw = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, aw, bw, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(["eq", " ".join(aw[i1:i2])])
        if op in ("delete", "replace"):
            out.append(["del", " ".join(aw[i1:i2])])
        if op in ("insert", "replace"):
            out.append(["ins", " ".join(bw[j1:j2])])
    return out
