#!/usr/bin/env python3
"""Tally a reader panel: only what can be counted. Whether a reader carried away an intended point is judged by
people and sub-agents (--judgments), never inferred here.

    python3 tally-readers.py --packet <dir>/packet.json --outputs <dir> [--judgments j.tsv] [--min-readers 8]
                             [--compare-packet P --compare-outputs D --compare-judgments J] [--json]

Reader output files are named <persona>_<model>_<n>.json (e.g. R1_haiku_1.json); the name is how the panel's cells
are counted. Only outputs that pass check-reader-output.py's rules are tallied; the others are named.

--judgments: TSV, one row per judge per reader per intended point: reader<TAB>point<TAB>judge<TAB>verdict, verdict
one of ✓ △ ✗ (or hit / partial / miss). A reader counts as carrying a point only when every judge wrote ✓; judges
who disagree count as not carried, which is the conservative reading. Agreement between judges is reported.

--compare-*: a second panel on another version. Per point, a two-sided Fisher exact p is reported beside the counts.
A single round's rise or fall is not a result: an eight-reader panel separates only large differences.

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
NAME = re.compile(r"^(?P<persona>[A-Za-z0-9]+)_(?P<model>[A-Za-z0-9.\-]+)_(?P<n>\d+)\.json$")
HIT = {"✓": "hit", "hit": "hit", "△": "partial", "partial": "partial", "✗": "miss", "miss": "miss"}
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
            die(f"{path}:{i}: expected reader<TAB>point<TAB>judge<TAB>verdict (✓ △ ✗)")
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
    directed = {q["id"]: [(r["reader"], r["data"][q["id"]]) for r in readers] for q in packet.get("questions") or []}
    return {"paragraphs": paras, "directed": directed,
            "remember": [(r["reader"], r["data"]["remember"]) for r in readers],
            "closest_prior_work": [(r["reader"], r["data"]["closest_prior_work"]) for r in readers],
            "reuse": [(r["reader"], r["data"]["reuse"]) for r in readers],
            "outside_knowledge": [(r["reader"], r["data"]["outside_knowledge"]) for r in readers
                                  if r["data"]["outside_knowledge"].strip().lower() not in ("none", "none.", "无")]}


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


def report(packet, readers, rejected, t, hits, agreement, shape, compare):
    L = [f"# 读者组 · {len(readers)} 位读者 × {len(packet['paragraphs'])} 段 · 机器草稿",
         "",
         f"读的是：{json.dumps(packet.get('source') or {}, ensure_ascii=False)[:300]}",
         ""]
    if shape[0]:
        L += ["**面板不全**：" + "；".join(shape[0]) + "。结果只作描述，不记为这一版已读过。", ""]
    if rejected:
        L += ["不合格、没计入的输出：", *[f"- {r['file']}：{'; '.join(r['problems'])}" for r in rejected], ""]
    L += ["## 记忆点（判定者判，不是机器判）"]
    if hits is not None and not any(v["judged"] for v in hits.values()):
        hits = None
        L.append(f"未判：每对「读者 × 记忆点」要 {MIN_JUDGES} 位判定者，给的判定不够。这里不报命中。")
    elif hits is None:
        L.append("未判：没有给 --judgments。这里不报命中。")
    else:
        for p, v in hits.items():
            line = f"- {p}：{v['carried']} / {v['judged']} 位读者带走了"
            if compare and p in compare:
                c = compare[p]
                line += f"；对照版 {c['carried']} / {c['judged']}，双侧 Fisher p = {c['p']:.3f}"
            L.append(line)
        L.append(f"判定者一致率：{agreement:.2f}" if agreement is not None else "只有一位判定者：没有一致率")
    L += ["", "## 定向问题"]
    for qid, answers in t["directed"].items():
        L += [f"- {qid}"] + [f"  - {r}：{a}" for r, a in answers]
    L += ["", "## 最像哪类已有工作（原话）"] + [f"- {r}：{a}" for r, a in t["closest_prior_work"]]
    L += ["", "## 能带走什么（原话）"] + [f"- {r}：{a}" for r, a in t["reuse"]]
    L += ["", "## 逐段：要重读的读者数与猜着读的词"]
    for p in t["paragraphs"]:
        g = "，".join(f"{w}×{n}" for w, n in p["guessed"])
        L.append(f"- P{p['p']}：重读 {p['reread_by']} 位" + (f"；猜：{g}" if g else ""))
    if t["outside_knowledge"]:
        L += ["", "## 读者自报的文外知识"] + [f"- {r}：{a}" for r, a in t["outside_knowledge"]]
    L += ["", "## 这个方法的局限", *[f"- {x}" for x in LIMITS]]
    return "\n".join(L) + "\n"


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
    hits, agreement = carried(load_judgments(a.judgments), readers)
    compare = None
    if a.compare_packet and a.compare_outputs and hits is not None:
        cpacket, creaders, _ = load_panel(a.compare_packet, a.compare_outputs)
        chits, _ = carried(load_judgments(a.compare_judgments), creaders)
        compare = {}
        for p, v in hits.items():
            c = (chits or {}).get(p)
            if c and v["judged"] and c["judged"]:
                compare[p] = {**c, "p": fisher_two_sided(v["carried"], v["judged"], c["carried"], c["judged"])}
    shape = panel_shape(readers, max(a.min_readers, MIN_PANEL))
    text = report(packet, readers, rejected, t, hits, agreement, shape, compare)
    out = Path(a.packet).parent / "report.md"
    out.write_text(text, encoding="utf-8")
    rec = record(packet, readers, shape, hits)
    if a.json:
        print(json.dumps({"readers": len(readers), "rejected": rejected, "carried": hits, "agreement": agreement,
                          "panel_problems": shape[0], "compare": compare, "tally": t,
                          "recorded": bool(rec)}, ensure_ascii=False, indent=1))
    else:
        print(text.splitlines()[0])
        print(f"report: {out}" + ("；已记为这一版的读者组" if rec and rec["verdict"] != "failed" else
                                  "；面板不全，已记为失败" if rec else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
