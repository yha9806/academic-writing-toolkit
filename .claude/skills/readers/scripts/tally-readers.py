#!/usr/bin/env python3
"""Tally a reader panel: only what can be counted. Whether a reader carried away an intended point is judged by
people and sub-agents (--judgments), never inferred here.

    python3 tally-readers.py --packet <dir>/packet.json --outputs <dir> [--judgments j.tsv] [--min-readers 8]
                             [--injected truth.tsv] [--derived coded.tsv] [--repeat-outputs D --repeat-judgments J]
                             [--compare-packet P --compare-outputs D --compare-judgments J] [--json]

Reader output files are named <persona>_<model>_<n>.json (e.g. R1_haiku_1.json); the name is how the panel's cells
are counted. Only outputs that pass check-reader-output.py's rules are tallied; the others are named.

--judgments: TSV, one row per judge per reader per intended point: reader<TAB>point<TAB>judge<TAB>verdict, verdict
one of ✓ △ ✗ ≠ (or hit / partial / miss / misattributed). ≠ is a point said but credited to the wrong thing (one
model's result told as another's): it is not carried, and it is counted apart, because a judge asked only whether a
point was mentioned graded it ✓.

--injected: TSV reader<TAB>point<TAB>truth for answers whose grade is known (correct, misattributed, reversed, a
bare number), judged with the panel under the same reader ids. More than two judge-by-answer misses on it records the
panel as a failure: the judges cannot yet be trusted with the real answers. A reader counts as carrying a point only when every judge wrote ✓; judges
who disagree count as not carried, which is the conservative reading. Agreement between judges is reported.

--compare-*: a second panel on another version. Per point, a two-sided Fisher exact p is reported beside the counts.
A single round's rise or fall is not a result: an eight-reader panel separates only large differences.

--derived: TSV metric<TAB>reader<TAB>coder<TAB>0|1 for a count read off the outputs (a misreading, a complaint). A
metric coded only by `main`, the side that revised the text, is reported as uncoded, not as a count: in one panel the
reviser's coding showed a large drop after its own rewrite and a blind coder's showed none. With a blind coder the
count is the blind coder's.

--ask-relations packets: each reader's two quoted sentences are placed at the turn between them. A turn that more
than half of the readers who named one share, and at least three, is reported as a place where the order may need
changing, to check against the story page before adding a connector (one case, 10-07, so a question, not a rule).

A packet not built from a loop workspace, or built as a targeted comparison, is not recorded in the loop; the last
line says so and why.

--repeat-*: a second panel on the same packet. Its spread per point is the panel's own noise: a change between
versions no larger than it is reported as inside the noise, whatever its p. Without a repeat the report says the
comparison has no noise floor (one panel run twice on one text moved a point by three readers of sixteen).

Counts are also given per model (the reader model mattered more than the persona in calibration), and the blank
reader's judgments (reader id BLANK, see build-reader-packet.py) mark the points that copying the first paragraph
already scores.

With a packet built from a loop workspace, the tally is recorded as the readers check's last run, so the loop knows
which version of which sections the panel read. A panel smaller than --min-readers, or with fewer than two personas
or two models, is recorded as a failure: it is not the panel the method was calibrated on.

Writes report.md beside the packet. Exit: 0 tallied; 2 nothing qualified to tally, or an unreadable packet.
"""
import argparse
import datetime as dt
import importlib.util
import json
import os
import math
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
# AWT_LOOP_ENGINE: the engine copy a mutation run is testing; otherwise the one in this checkout.
ENGINE = Path(os.environ.get("AWT_LOOP_ENGINE") or ROOT / "experimental" / "writing-loop" / "engine")
if not ENGINE.is_dir():
    # A user-scope install has no engine beside it; the installer records the checkout's (references/loop-engine.txt).
    _rec = Path(__file__).resolve().parent.parent / "references" / "loop-engine.txt"
    if _rec.is_file():
        ENGINE = Path(_rec.read_text(encoding="utf-8").strip())
# The panel the method was calibrated on: two personas x two models x two samples. --min-readers may raise it.
MIN_PANEL = 8
MIN_JUDGES = 2
BLANK = "BLANK"
NAME = re.compile(r"^(?P<persona>[A-Za-z0-9]+)_(?P<model>[A-Za-z0-9.\-]+)_(?P<n>\d+)\.json$")
HIT = {"✓": "hit", "hit": "hit", "△": "partial", "partial": "partial", "✗": "miss", "miss": "miss",
       "≠": "misattributed", "misattributed": "misattributed", "归属错": "misattributed"}
INJECT_TOLERANCE = 2
REVISER = "main"
# The same place, the same kind of complaint: from this many readers it is named with ⚑. Below it a single reader's
# taste cannot be told from a property of the text.
SAME_PLACE = 3
NOTHING = re.compile(r"^\s*(?:nothing|none|n/?a|no|无|没有)?\s*[.。]?\s*$", re.I)
# writing_got_in_way is free text. A closed keyword list sorts it for reading, and the sort is descriptive: a reader
# who writes "the logic jumps" and one who writes "hard to see why this follows" may land in different kinds, or
# none. The count to compare versions by is a blind coder's, read with --derived as writing:<kind>. Checked against one
# real panel: "reading flow" is not a complaint about links, "section numbers" is one about placeholders, "repeated use
# of placeholders" is not repetition; the patterns below leave those out.
WRITING_KINDS = [
    ("density", r"dense|density|packed|qualif|hedg|caveat|stack|nested|parenthe|too much (?:in|per)|overload"),
    ("sentences", r"long sentence|sentence length|convoluted|run-on|clause|syntax|complex sentence|wordy|verbose"),
    ("links", r"transition|signpost|abrupt|logical (?:gap|jump|leap|link)|(?:jumps?|leaps?) (?:from|between|to)|"
              r"how .{0,40}(?:relates?|connects?|follows)|(?:relation|connection|link)s? between|hard to follow the "
              r"(?:argument|logic|reasoning)"),
    ("terms", r"jargon|acronym|abbreviat|undefined|terminolog|\bterms?\b|notation|coined|label"),
    ("repetition", r"repetitive|repetition|redundan|restat|repeats? (?:itself|the same|what)|said (?:twice|again)"),
    ("numbers", r"numbers?-heavy|(?:many|multiple|several|too many) (?:numbers|statistics|percentages)|statistic|"
                r"p-values?|q-values?|percentages|hit.counts|decimal"),
    ("placeholders", r"§x|placeholder|cross-ref|section numbers?|see section"),
]
# The directed question build-reader-packet.py --ask-relations adds. Its quotes are located in the packet's paragraphs.
RELATION_ID = "relation_guessed"
QUOTE = re.compile(r"[\"\u201c]([^\"\u201d]{12,}?)[\"\u201d]")
LIMITS = [
    "Readers are sub-agents told to ignore what they can see beyond the text; they are not readers who never knew. "
    "Each reports the outside knowledge it used.",
    "Eight readers separate only large differences. When this method was calibrated, repeated panels on the same "
    "text agreed only moderately and the reader model mattered more than the persona; a one-round rise or fall "
    "after a wording change did not reproduce.",
    "Whether a sentence changed its meaning is the author's call: in calibration a machine checker missed most "
    "of the meaning changes planted for it.",
    "Guessed words are descriptive only: at the level of single words the readers rarely matched where the author "
    "got stuck. Punctuation is not seen.",
    "Free-text summaries overstate misreadings; a directed question is the way to confirm one.",
    "Free recall is zero-sum: three remember lines hold every point a reader takes, so one point rising pushes another "
    "out. The rank at which a point was recalled is not recorded; a drop in free recall alone, with the directed "
    "question holding, is not evidence the text got worse.",
]


def die(msg):
    sys.stderr.write(f"tally-readers: {msg}\n")
    sys.exit(2)


def _checker():
    spec = importlib.util.spec_from_file_location("check_reader_output", HERE / "check-reader-output.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_panel(packet_path, outputs_dir):
    chk = _checker()
    try:
        packet = json.loads(Path(packet_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        die(f"packet unreadable: {e}")
    readers, rejected, seen = [], [], {}
    for f in sorted(Path(outputs_dir).glob("*.json")):
        m = NAME.match(f.name)
        try:
            data = chk.parse(f.read_text(encoding="utf-8"))
            why = chk.problems(data, packet) + chk.duplicate_of(data, f.name, seen)
        except (OSError, ValueError) as e:
            data, why = None, [f"unreadable: {e}"]
        if not m:
            why = why + ["file name is not <persona>_<model>_<n>.json"]
        if why:
            rejected.append({"file": f.name, "problems": why})
        else:
            readers.append({"file": f.name, "reader": f.stem, "persona": m["persona"], "model": m["model"], "data": data})
    return packet, readers, rejected


def load_judgments(path):
    rows = {}
    if not path:
        return None
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 4 or parts[3].strip() not in HIT:
            die(f"{path}:{i}: expected reader<TAB>point<TAB>judge<TAB>verdict (✓ △ ✗ ≠)")
        reader, point, judge, verdict = (p.strip() for p in parts)
        rows.setdefault((reader, point), {})[judge] = HIT[verdict]
    return rows


def carried(judgments, readers):
    """{point: {"carried": n, "judged": n}} and the judges' agreement."""
    if judgments is None:
        return None, None
    names = {r["reader"] for r in readers}
    points = sorted({p for (_, p) in judgments})
    out, agree, pairs = {}, 0, 0
    for p in points:
        c = j = 0
        for r in names:
            v = judgments.get((r, p))
            if not v:
                continue
            vals = list(v.values())
            if len(vals) < MIN_JUDGES:
                continue  # one judge's reading is not a judgment here; the pair counts as not judged
            j += 1
            pairs += 1
            agree += len(set(vals)) == 1
            c += all(x == "hit" for x in vals)
        out[p] = {"carried": c, "judged": j}
    return out, (agree / pairs if pairs else None)


def misattributed(judgments, readers):
    """{point: readers every judge graded ≠}: said, but credited to the wrong thing."""
    if judgments is None:
        return None
    names, out = {r["reader"] for r in readers}, {}
    for (reader, p), v in judgments.items():
        vals = list(v.values())
        if reader in names and len(vals) >= MIN_JUDGES and all(x == "misattributed" for x in vals):
            out[p] = out.get(p, 0) + 1
    return out


def injected_misses(path, judgments):
    """(misses, cells): each judge's grade of each injected answer against its known grade; a judge that left one
    ungraded missed it. None when no --injected was given."""
    if not path:
        return None
    truth = {}
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("\t")]
        if len(parts) != 3 or parts[2] not in HIT:
            die(f"{path}:{i}: expected reader<TAB>point<TAB>truth (✓ △ ✗ ≠)")
        truth[(parts[0], parts[1])] = HIT[parts[2]]
    if not truth:
        die(f"{path}: no injected answer: an empty set checks nothing")
    judges = sorted({j for v in (judgments or {}).values() for j in v})
    if not judges:
        return len(truth), len(truth)
    misses = sum((judgments or {}).get(pair, {}).get(j) != want for pair, want in truth.items() for j in judges)
    return misses, len(truth) * len(judges)


def derived_metrics(path, readers):
    """{metric: {"coded_by", "blind", "count"}}: count is the blind coders' readers with a 1, None when only the reviser
    coded it. A blind coder is anyone but REVISER; with several, a reader counts when every blind coder wrote 1."""
    if not path:
        return None
    rows = {}
    names = {r["reader"] for r in readers}
    for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = [x.strip() for x in line.split("\t")]
        if len(parts) != 4 or parts[3] not in ("0", "1"):
            die(f"{path}:{i}: expected metric<TAB>reader<TAB>coder<TAB>0|1")
        metric, reader, coder, v = parts
        if reader in names:
            rows.setdefault(metric, {}).setdefault(reader, {})[coder] = v == "1"
    out = {}
    for metric, by_reader in rows.items():
        coders = sorted({c for v in by_reader.values() for c in v})
        blind = [c for c in coders if c != REVISER]
        count = sum(all(v.get(c, False) for c in blind) for v in by_reader.values() if any(c in v for c in blind)) \
            if blind else None
        out[metric] = {"coded_by": coders, "blind": bool(blind), "count": count}
    return out


def carried_by_model(judgments, readers):
    """{model: {point: {"carried", "judged"}}}: the same rule as carried(), one model's readers at a time."""
    if judgments is None:
        return None
    return {m: carried(judgments, [r for r in readers if r["model"] == m])[0] for m in sorted({r["model"] for r in readers})}


def blank_carried(judgments):
    """{point: carried} for the blank reader (reader id BLANK), under the rule readers are held to."""
    if judgments is None:
        return None
    out = {}
    for (reader, p), v in judgments.items():
        vals = list(v.values())
        if reader == BLANK and len(vals) >= MIN_JUDGES:
            out[p] = all(x == "hit" for x in vals)
    return out


def noise_floor(hits, rhits):
    """{point: {"carried", "judged", "spread"}}: a repeat panel on the same packet, and the gap between the two runs
    as a share of readers judged."""
    out = {}
    for p, v in (hits or {}).items():
        r = (rhits or {}).get(p)
        if r and v["judged"] and r["judged"]:
            out[p] = {**r, "spread": abs(v["carried"] / v["judged"] - r["carried"] / r["judged"])}
    return out


def fisher_two_sided(a, n1, b, n2):
    """Two-sided Fisher exact p for a of n1 against b of n2."""
    k, n = a + b, n1 + n2

    def pmf(x):
        return math.comb(n1, x) * math.comb(n2, k - x) / math.comb(n, k)
    obs = pmf(a)
    lo, hi = max(0, k - n2), min(k, n1)
    return min(1.0, sum(pmf(x) for x in range(lo, hi + 1) if pmf(x) <= obs * (1 + 1e-9)))


def tally(packet, readers):
    paras = []
    for para in packet["paragraphs"]:
        rr = [r for r in readers if any(e.get("p") == para["p"] and e.get("reread") for e in r["data"]["paragraphs"])]
        guessed = Counter(w.strip() for r in readers for e in r["data"]["paragraphs"] if e.get("p") == para["p"]
                          for w in e.get("guessed") or [] if isinstance(w, str) and w.strip())
        paras.append({"p": para["p"], "reread_by": len(rr), "guessed": guessed.most_common(8)})
    for p in paras:
        p["flag"] = p["reread_by"] >= SAME_PLACE
    directed = {q["id"]: [(r["reader"], r["data"][q["id"]]) for r in readers] for q in packet.get("questions") or []}
    writing = [(r["reader"], r["data"]["writing_got_in_way"]) for r in readers
               if not NOTHING.match(str(r["data"]["writing_got_in_way"]))]
    kinds = {k: sorted({rd for rd, txt in writing if re.search(pat, str(txt), re.I)}) for k, pat in WRITING_KINDS}
    return {"paragraphs": paras, "directed": directed,
            "writing": writing,
            "writing_kinds": {k: {"readers": v, "flag": len(v) >= SAME_PLACE} for k, v in kinds.items() if v},
            "relations": relations(packet, directed.get(RELATION_ID)),
            "remember": [(r["reader"], r["data"]["remember"]) for r in readers],
            "closest_prior_work": [(r["reader"], r["data"]["closest_prior_work"]) for r in readers],
            "reuse": [(r["reader"], r["data"]["reuse"]) for r in readers],
            "outside_knowledge": [(r["reader"], r["data"]["outside_knowledge"]) for r in readers
                                  if r["data"]["outside_knowledge"].strip().lower() not in ("none", "none.", "无")]}


def _norm(text):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", str(text).lower())).strip()


# A sentence ends at . ! ? before the next one's capital (or at 。！？); an abbreviation or an initial ends none.
SENT_END = re.compile(r"[.!?][\"\u201d\u2019)\]]*\s+(?=[\"\u201c(\[]?[A-Z0-9])|[\u3002\uff01\uff1f]\s*")
NOT_END = re.compile(r"(?:\b(?:e\.g|i\.e|cf|vs|al|etc|Fig|Figs|Sec|Eq|Tab|No|approx|resp)|\b[A-Z])\.[\"\u201d\u2019)\]]*\s*$")


def _sentences(text):
    out, start = [], 0
    for m in SENT_END.finditer(text):
        if NOT_END.search(text[start:m.end()]):
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    if text[start:].strip():
        out.append(text[start:].strip())
    return out


def _quotes(answer):
    """The sentence openings a reader quoted: each "…" in a string, or each item of a list (readers also answer with a
    list of the two openings, quoted or not)."""
    if isinstance(answer, list):
        out = []
        for x in answer:
            found = QUOTE.findall(str(x))
            bare = str(x).strip().strip("\"'\u201c\u201d")
            out += found or ([bare] if len(bare) >= 12 else [])
        return out
    return QUOTE.findall(str(answer))


def _opening(sentence, words=6):
    w = sentence.split()
    return " ".join(w[:words]) + ("…" if len(w) > words else "")


def relations(packet, answers):
    """Where readers had to guess how one sentence follows from another: each quote placed in the paragraph that
    holds it, readers counted once per paragraph; and each reader's two quotes placed at the turn between the two
    sentences that hold them (an abstract is one paragraph, so the paragraph alone does not say where). None when the
    packet did not ask."""
    if answers is None:
        return None
    paras = [(p["p"], _norm(p["text"])) for p in packet["paragraphs"]]
    sents = {}
    for p in packet["paragraphs"]:
        ss = _sentences(p["text"])
        starts, joined = [], ""
        for x in ss:
            starts.append(len(joined))
            joined += _norm(x) + " "
        sents[p["p"]] = (ss, starts, joined)
    named, where, unplaced, turns = [], {}, [], {}
    for reader, answer in answers:
        if NOTHING.match(str(answer)) or answer in ([], None):
            continue
        named.append(reader)
        hit, at = set(), []
        for q in _quotes(answer):
            q = _norm(q)
            hit |= {p for p, text in paras if q and q in text}
            for p, (ss, starts, joined) in sents.items():
                i = joined.find(q) if q else -1
                if i >= 0:
                    loc = (p, sum(1 for s0 in starts if s0 <= i))
                    if loc not in at:
                        at.append(loc)
                    break
        if not hit:
            unplaced.append(reader)
        for p in hit:
            where.setdefault(p, []).append(reader)
        if at:
            a, b = (sorted(at[:2]) + [None])[:2]
            turns.setdefault((a, b), []).append(reader)
    out = []
    for (a, b), rs in sorted(turns.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1] or (0, 0))):
        out.append({"from": list(a), "to": list(b) if b else None, "readers": sorted(rs),
                    "flag": len(rs) >= SAME_PLACE, "most": 2 * len(rs) > len(named),
                    "from_text": _opening(sents[a[0]][0][a[1] - 1]),
                    "to_text": _opening(sents[b[0]][0][b[1] - 1]) if b else None})
    return {"named": named, "unplaced": unplaced, "turns": out,
            "paragraphs": {p: {"readers": sorted(v), "flag": len(v) >= SAME_PLACE} for p, v in sorted(where.items())}}


def models(readers, rejected):
    """{model: {"qualified", "rejected"}}: a panel's make-up. One round qualified one reader of eight from one model
    and seven of eight from the other; two panels built that way are not the same instrument."""
    out = {}
    for r in readers:
        out.setdefault(r["model"], {"qualified": 0, "rejected": 0})["qualified"] += 1
    for r in rejected:
        m = NAME.match(r["file"])
        out.setdefault(m["model"] if m else "?", {"qualified": 0, "rejected": 0})["rejected"] += 1
    return dict(sorted(out.items()))


def _makeup(ms):
    return "、".join(f"{m} {v['qualified']}/{v['qualified'] + v['rejected']}" for m, v in ms.items())


def compare_kind(point, packet, cpacket):
    """directed: both versions asked the same question; mismatch: one did not, or asked it differently, so the counts
    are not of one thing; recall: a free-recall point, where not mentioning a misreading is not avoiding it."""
    qa = {q["id"]: q["question"] for q in packet.get("questions") or []}
    qb = {q["id"]: q["question"] for q in cpacket.get("questions") or []}
    if point in qa and point in qb and qa[point] == qb[point]:
        return "directed"
    return "mismatch" if point in qa or point in qb else "recall"


def panel_shape(readers, min_readers):
    personas, models = {r["persona"] for r in readers}, {r["model"] for r in readers}
    problems = []
    if len(readers) < min_readers:
        problems.append(f"只有 {len(readers)} 位合格读者，少于 {min_readers}")
    if len(personas) < 2:
        problems.append("画像少于 2 种")
    if len(models) < 2:
        problems.append("模型少于 2 种")
    return problems, sorted(personas), sorted(models)


def report(packet, readers, rejected, t, hits, agreement, shape, compare, extra=None):
    extra = extra or {}
    L = [f"# 读者组 · {len(readers)} 位读者 × {len(packet['paragraphs'])} 段 · 机器草稿",
         "",
         f"读的是：{json.dumps(packet.get('source') or {}, ensure_ascii=False)[:300]}",
         ""]
    if shape[0]:
        L += ["**面板不全**：" + "；".join(shape[0]) + "。结果只作描述，不记为这一版已读过。", ""]
    stale_aux = (packet.get("references") or {}).get("aux_older_than_source")
    if stale_aux:
        L += [f"**交叉引用编号可能过期**：出题用的 .aux 编译于 {stale_aux['aux']}，早于稿子最后一次改动（{stale_aux['source']}）。"
              "读者对编号的抱怨可能来自这里，不是稿子。", ""]
    if rejected:
        L += ["不合格、没计入的输出：", *[f"- {r['file']}：{'; '.join(r['problems'])}" for r in rejected], ""]
    ms = extra.get("models")
    if ms:
        L += [f"按模型的合格读者（合格/交回）：{_makeup(ms)}", ""]
    cms = extra.get("compare_models")
    if ms and cms and {m: v["qualified"] for m, v in ms.items()} != {m: v["qualified"] for m, v in cms.items()}:
        L += [f"**两组合格读者的模型构成不同**：本版 {_makeup(ms)}；对照版 {_makeup(cms)}。读者模型对结果的影响比画像大，"
              "这次对照不同质，版本之间的差可能来自读者组成。", ""]
    L += ["## 记忆点（判定者判，不是机器判）"]
    if hits is not None and not any(v["judged"] for v in hits.values()):
        hits = None
        L.append(f"未判：每对「读者 × 记忆点」要 {MIN_JUDGES} 位判定者，给的判定不够。这里不报命中。")
    elif hits is None:
        L.append("未判：没有给 --judgments。这里不报命中。")
    else:
        for p, v in hits.items():
            line = f"- {p}：{v['carried']} / {v['judged']} 位读者带走了"
            floor = (extra.get("floor") or {}).get(p)
            if floor:
                line += f"；同包重跑 {floor['carried']} / {floor['judged']}（面板自身波动 {floor['spread']:.2f}）"
            if compare and p in compare and compare[p].get("kind") == "mismatch":
                c = compare[p]
                line += f"；对照版 {c['carried']} / {c['judged']}，**不可比**：这道定向题只有一版问了，或两版问法不同"
            elif compare and p in compare:
                c = compare[p]
                line += f"；对照版 {c['carried']} / {c['judged']}，双侧 Fisher p = {c['p']:.3f}"
                if c.get("kind") == "directed":
                    line += "（两版同一道定向题）"
                if c.get("inside_noise") is True:
                    line += "，**在噪声内**（不大于同包重跑的波动）"
                elif c.get("inside_noise") is False:
                    line += "，超过同包重跑的波动"
            wrong = (extra.get("misattributed") or {}).get(p)
            if wrong:
                line += f"；{wrong} 位说到了但归属错（不算带走）"
            if (extra.get("blank") or {}).get(p):
                line += "；**空白读者也带走了**：照抄第一段就能得分，不能当作读懂的证据"
            L.append(line)
        inj = extra.get("injected")
        if inj is None:
            L.append("没有注入集（--injected）：判定者没有先在答案已知的答卷上查过。")
        else:
            L.append(f"注入集：判定者判错 {inj[0]} / {inj[1]} 格（允许 {INJECT_TOLERANCE}）。")
        if compare and any(c.get("kind") == "recall" for c in compare.values()):
            L.append("自由回忆的点在两版之间比的是「提到没有」：一处误读在新版没人提，不等于没人误读。要确认一处误读改好了，"
                     "在两版上问同一道定向题（配对设计），再比那道题。")
        if compare and not extra.get("floor"):
            L.append("没有同包重跑（--repeat-*）：看不出版本之间的变化是否大于面板自身的波动。")
        by_model = extra.get("by_model") or {}
        if by_model:
            L.append("按模型：" + "；".join(f"{m} " + "、".join(f"{p} {v['carried']}/{v['judged']}" for p, v in hm.items())
                                             for m, hm in by_model.items() if hm))
        L.append(f"判定者一致率：{agreement:.2f}" if agreement is not None else "只有一位判定者：没有一致率")
    der = extra.get("derived")
    if der:
        L += ["", "## 派生指标（从输出里数的）"]
        for m, v in der.items():
            L.append(f"- {m}：{v['count']} 位（盲编：{'、'.join(c for c in v['coded_by'] if c != REVISER)}）" if v["blind"]
                     else f"- {m}：未盲编（只有改稿的一方 {REVISER} 编过），不报数")
    rep = packet.get("repetition")
    if rep:
        L += ["", "## 引言第一段与摘要的重复（量的，不是问的）",
              f"P{rep['introduction_first']} 的四词组有 {rep['shared_four_word_share']:.0%} 也在摘要里；最长逐字重合 "
              f"{rep['longest_verbatim_words']} 词：「{rep['longest_verbatim']}」"]
    wr, n = t.get("writing") or [], len(readers)
    L += ["", f"## 写法挡路（原话）：{len(wr)} / {n} 位读者说有"]
    L += [f"- {r}：{a}" for r, a in wr]
    if t.get("writing_kinds"):
        L.append("关键词预分（描述，不是编码；" + f"同一类 {SAME_PLACE} 位以上标 ⚑）：" + "；".join(
            f"{k} {len(v['readers'])} 位" + (" ⚑" if v["flag"] else "") for k, v in t["writing_kinds"].items()))
    if wr:
        L.append("要跨版本比较，请盲编：每位读者每一类一行 `writing:<类>\t<读者>\t<编者>\t0|1`，用 --derived 读；类："
                 + "、".join(k for k, _ in WRITING_KINDS) + "。")
    rel = t.get("relations")
    if rel is not None:
        L += ["", f"## 句间关系要猜（定向问题 {RELATION_ID}）：{len(rel['named'])} / {n} 位读者指出"]
        for p, v in rel["paragraphs"].items():
            L.append(f"- P{p}：{len(v['readers'])} 位" + (" ⚑" if v["flag"] else "") + f"（{'、'.join(v['readers'])}）")
        if rel["turns"]:
            L.append("- 句与句之间（按读者引的两句定位）：")
            for x in rel["turns"]:
                L.append(f"  - {_turn(x)}：{len(x['readers'])} 位" + (" ⚑" if x["flag"] else "")
                         + f"（{'、'.join(x['readers'])}）「{x['from_text']}」" + (f"→「{x['to_text']}」" if x["to"] else ""))
        for x in (y for y in rel["turns"] if y["most"] and y["flag"]):
            # 10-07: most readers of one abstract guessed at the same turn; a connector added there did not make it
            # followable, and putting the steps in the story page's order did. One case, so a question, not a rule.
            L.append(f"- 过半读者（{len(x['readers'])} / {len(rel['named'])}）卡在 {_turn(x)}：这里可能要重排。"
                     "先对照讲法页查这一处的先后，再决定加不加连接词：连接词能把关系说出来，改不了先后。")
        if rel["unplaced"]:
            L.append(f"- 引文在稿里找不到、没能定位：{'、'.join(rel['unplaced'])}")
    L += ["", "## 定向问题"]
    for qid, answers in t["directed"].items():
        L += [f"- {qid}"] + [f"  - {r}：{a}" for r, a in answers]
    L += ["", "## 最像哪类已有工作（原话）"] + [f"- {r}：{a}" for r, a in t["closest_prior_work"]]
    L += ["", "## 能带走什么（原话）"] + [f"- {r}：{a}" for r, a in t["reuse"]]
    hot = [f"P{p['p']}" for p in t["paragraphs"] if p.get("flag")]
    L += ["", "## 逐段：要重读的读者数与猜着读的词"
          + (f"（{SAME_PLACE} 位以上重读：{'、'.join(hot)}）" if hot else "")]
    for p in t["paragraphs"]:
        g = "，".join(f"{w}×{n}" for w, n in p["guessed"])
        L.append(f"- P{p['p']}：重读 {p['reread_by']} 位" + (" ⚑" if p.get("flag") else "") + (f"；猜：{g}" if g else ""))
    if t["outside_knowledge"]:
        L += ["", "## 读者自报的文外知识"] + [f"- {r}：{a}" for r, a in t["outside_knowledge"]]
    L += ["", "## 这个方法的局限", *[f"- {x}" for x in LIMITS]]
    return "\n".join(L) + "\n"


def _turn(x):
    (p, i), to = x["from"], x["to"]
    if not to:
        return f"P{p} 第 {i} 句"
    return f"P{p} 第 {i} 句 → " + (f"第 {to[1]} 句" if to[0] == p else f"P{to[0]} 第 {to[1]} 句")


def not_recorded(packet):
    """Why the loop will not have this panel, or None when it will: said, because a tally the loop did not take reads
    the same as one it did (10-07: the last line was only the report's path)."""
    src = packet.get("source") or {}
    if not src.get("workspace"):
        return "packet 不是从循环工作区建的（没有 --workspace），结果只在 report.md"
    if not packet.get("snapshot"):
        return "packet 读的节与工作区配置的不同（定向比较，没有快照），结果只在 report.md"
    return None


def record(packet, readers, shape, hits):
    """The readers check's last run in the loop workspace the packet was built from."""
    src = packet.get("source") or {}
    ws = src.get("workspace")
    if not ws or not packet.get("snapshot"):
        return None
    if not ENGINE.is_dir():
        die(f"cannot record the run: the writing loop engine is not at {ENGINE}")
    sys.path.insert(0, str(ENGINE))
    from loop import coverage as V  # noqa: E402
    if shape[0]:
        verdict, summary = "failed", "面板不全：" + "；".join(shape[0])
    elif hits is None or not any(v["judged"] for v in hits.values()):
        verdict, summary = "findings", f"{len(readers)} 位读者；记忆点未判"
    else:
        verdict = "findings"
        summary = f"{len(readers)} 位读者；" + "，".join(f"{p} {v['carried']}/{v['judged']}" for p, v in hits.items())
    card = (src.get("intent_card") or {}).get("state")
    if card == "draft":
        summary += "（意图卡是草稿）"
    elif card == "delegated":
        summary += "（意图卡：作者授权 Claude 定稿）"
    rec = {"id": "readers", "commit": src.get("commit"), "at": dt.datetime.now(dt.timezone.utc).isoformat(),
           "snapshot": packet["snapshot"], "verdict": verdict, "summary": summary, "exit": None,
           "panel": {"readers": len(readers), "personas": shape[1], "models": shape[2]}}
    V.save_run(ws, rec)
    return rec


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--packet", required=True)
    ap.add_argument("--outputs", required=True)
    ap.add_argument("--judgments")
    ap.add_argument("--min-readers", type=int, default=8)
    ap.add_argument("--injected", help="answers of known grade: reader<TAB>point<TAB>truth")
    ap.add_argument("--derived", help="counts read off the outputs: metric<TAB>reader<TAB>coder<TAB>0|1")
    ap.add_argument("--repeat-outputs", help="a second panel's outputs on the same packet")
    ap.add_argument("--repeat-judgments")
    ap.add_argument("--compare-packet")
    ap.add_argument("--compare-outputs")
    ap.add_argument("--compare-judgments")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        sys.exit(2 if e.code else 0)
    packet, readers, rejected = load_panel(a.packet, a.outputs)
    if not readers:
        die(f"no qualified reader output in {a.outputs} ({len(rejected)} rejected): nothing tallied is not a result")
    t = tally(packet, readers)
    judgments = load_judgments(a.judgments)
    hits, agreement = carried(judgments, readers)
    floor = None
    if a.repeat_outputs and hits is not None:
        _, rreaders, _ = load_panel(a.packet, a.repeat_outputs)
        floor = noise_floor(hits, carried(load_judgments(a.repeat_judgments), rreaders)[0])
    extra = {"floor": floor, "by_model": carried_by_model(judgments, readers), "blank": blank_carried(judgments),
             "misattributed": misattributed(judgments, readers), "injected": injected_misses(a.injected, judgments),
             "derived": derived_metrics(a.derived, readers), "models": models(readers, rejected)}
    compare = None
    if a.compare_packet and a.compare_outputs and hits is not None:
        cpacket, creaders, crejected = load_panel(a.compare_packet, a.compare_outputs)
        extra["compare_models"] = models(creaders, crejected)
        chits, _ = carried(load_judgments(a.compare_judgments), creaders)
        compare = {}
        for p, v in hits.items():
            c = (chits or {}).get(p)
            if c and v["judged"] and c["judged"]:
                kind = compare_kind(p, packet, cpacket)
                compare[p] = {**c, "kind": kind, "p": None if kind == "mismatch" else
                              fisher_two_sided(v["carried"], v["judged"], c["carried"], c["judged"])}
                f = (floor or {}).get(p)
                delta = abs(v["carried"] / v["judged"] - c["carried"] / c["judged"])
                compare[p]["inside_noise"] = (delta <= f["spread"] + 1e-9) if f else None
    shape = panel_shape(readers, max(a.min_readers, MIN_PANEL))
    if extra["injected"] and extra["injected"][0] > INJECT_TOLERANCE:
        shape[0].append(f"判定者在注入集上判错 {extra['injected'][0]} 格（允许 {INJECT_TOLERANCE}）")
    text = report(packet, readers, rejected, t, hits, agreement, shape, compare, extra)
    out = Path(a.packet).parent / "report.md"
    out.write_text(text, encoding="utf-8")
    rec = record(packet, readers, shape, hits)
    if a.json:
        print(json.dumps({"readers": len(readers), "rejected": rejected, "carried": hits, "agreement": agreement,
                          "panel_problems": shape[0], "compare": compare, "tally": t, "noise_floor": floor,
                          "by_model": extra["by_model"], "blank": extra["blank"], "repetition": packet.get("repetition"),
                          "misattributed": extra["misattributed"], "injected": extra["injected"], "derived": extra["derived"],
                          "models": extra["models"], "compare_models": extra.get("compare_models"),
                          "recorded": bool(rec), "not_recorded": not_recorded(packet)}, ensure_ascii=False, indent=1))
    else:
        print(text.splitlines()[0])
        print(f"report: {out}" + ("；已记为这一版的读者组" if rec and rec["verdict"] != "failed" else
                                  "；面板不全，已记为失败" if rec else f"；没记进循环：{not_recorded(packet)}"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
