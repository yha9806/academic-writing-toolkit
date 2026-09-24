"""Paper state: the per-turn line says whether the claims stand, and a draft whose checks are all current is not
thereby ready. Synthetic wording throughout; no manuscript text."""
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from loop import cli
from loop import config as C
from loop import coverage as V
from loop import history as H
from loop import overview as O
from loop import state as S

from fixtures import TempDir, git, make_repo, workspace

MAIN = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We audit a bridge survey. The gauges prove that every bridge is safe.
\end{abstract}
\input{sections/01_intro}
\end{document}
"""
INTRO = r"""\section{Introduction}\label{sec:intro}
Gauges on two bridges read 12 points. We do not test whether drivers notice.

Inspections are rare.
"""
RULES = [{"match": r"^Abstract$", "prefix": "A", "kind": "prose", "flat": True},
         {"match": r"^Introduction$", "prefix": "I", "kind": "prose"}]

LEDGER = """# 主张清单
阶段：分析

## 主张 C1 两座桥的读数是 12
- 证据：表 1
- 强度：强
- 允许的说法：两座桥
- 越界：every bridge is safe
- 必须出现：do not test whether drivers

## 主张 C2 读数说明桥安全
- 证据：没有
- 强度：弱
- 允许的说法：只能说读数
- 缺：N2

## 待做 N2 再测一座桥
- 类型：分析
- 改变：C2
- 状态：未做

## 待做 N1 找读数标准的出处
- 类型：出处
- 改变：C1
- 状态：等作者（先定找哪几本）
"""

CLEAN = """阶段：终检

## 主张 C1 两座桥的读数是 12
- 证据：表 1
- 强度：强
- 允许的说法：两座桥
- 越界：three bridges

## 待做 N1 再测一座桥
- 类型：分析
- 改变：C1
- 状态：已做 2026-01-02 运行记录 run-1
"""


def setup(root, ledger=LEDGER):
    repo = make_repo(root, [({"main.tex": MAIN, "sections/01_intro.tex": INTRO}, "v1", 1_700_000_000)])
    ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex"])
    cfg = C.load(ws)
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = RULES
    cfg["genre"] = "note"
    if ledger is not None:
        p = Path(root) / "claims.md"
        p.write_text(ledger, encoding="utf-8")
        cfg["claims"] = str(p)
    C.save(ws, cfg)
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    head = git(cfg["repo"], "rev-parse", "HEAD")
    (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
    return ws, C.load(ws)


class StateTest(unittest.TestCase):
    def test_without_a_ledger_the_line_says_the_loop_does_not_know(self):
        with TempDir() as root:
            ws, cfg = setup(root, ledger=None)
            line = V.live_line(ws, cfg)
            self.assertTrue(line.startswith("论文状态：没登记主张清单"), line)
            self.assertIn("不知道主张立没立住", line)

    def test_a_weak_claim_keeps_the_paper_not_ready_and_leads_the_line(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertEqual(st["weak"], ["C2"])
            line = V.live_line(ws, cfg)
            self.assertTrue(line.startswith("论文状态：未就绪（阶段：分析）"), line)
            self.assertIn("没立住 C2", line)
            self.assertIn("主张 2：强 1、弱 1", line)

    def test_an_overclaim_anywhere_in_the_draft_is_found_though_nothing_changed(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            st = S.compute(cfg, ws)
            [o] = st["over"]
            self.assertEqual(o["claim"], "C1")
            self.assertTrue(o["labels"] and o["labels"][0].startswith("A"), o)
            self.assertIn("越界 1 句", S.line(st))

    def test_a_required_wording_that_is_gone_is_said(self):
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER.replace("do not test whether drivers", "we measured the drivers"))
            st = S.compute(cfg, ws)
            self.assertEqual([a["claim"] for a in st["absent"]], ["C1"])
            self.assertIn("缺该有的说法 C1", S.line(st))

    def test_open_work_blocks_and_the_next_items_follow_the_ledger(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            st = S.compute(cfg, ws)
            self.assertEqual(st["next"], ["N2", "N1"], "the author's order, not sorted")
            line = S.line(st)
            self.assertIn("待做开着 2（分析 1、出处 1）", line)
            self.assertIn("N1 找读数标准的出处（等作者）", line)

    def test_a_closed_item_needs_a_date_and_evidence(self):
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN.replace("已做 2026-01-02 运行记录 run-1", "已做"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["open"], ["N1"], "「已做」 without a date and evidence is not done")
            self.assertTrue(any("状态读不懂" in p for p in st["problems"]), st["problems"])

    def test_everything_closed_is_at_best_for_the_author_never_green(self):
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN)
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.AUTHOR)
            self.assertIn("能不能投由作者定", S.line(st))
            c = S.cell(st)
            self.assertEqual(c["value"], "待作者终审")
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["state", str(ws)])
            self.assertEqual(rc, 0)
            self.assertIn("主张 C1", buf.getvalue())

    def test_an_unreadable_ledger_is_not_read_as_fine(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            cfg["claims"] = str(Path(root) / "gone.md")
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertIn("读不到", st["problems"][0])
            bad = LEDGER.replace("强度：强", "强度：很强").replace("越界：every bridge is safe", "越界：every (bridge")
            bad = bad.replace("改变：C2", "改变：C9")
            ws2, cfg2 = setup(Path(root) / "b", bad)
            st2 = S.compute(cfg2, ws2)
            joined = "；".join(st2["problems"])
            for needle in ("强度读不懂", "正则写错了", "C9 不是清单里的主张"):
                self.assertIn(needle, joined)
            self.assertIn("C1", st2["weak"], "a strength nobody can read counts as not established")

    def test_an_index_that_was_never_built_is_said(self):
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN)
            (Path(ws) / "index" / "sentences.json").unlink()
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertTrue(any("索引没建" in p for p in st["problems"]))

    def test_the_overview_puts_the_paper_before_the_checks(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            block = O.todo_block({}, cfg["repo"], cfg["ref"], str(Path(ws) / "cache"), 0)
            self.assertEqual(block["cells"][0]["title"], "论文")
            self.assertEqual(block["cells"][0]["value"], "未就绪")
            self.assertEqual(block["cells"][0]["tone"], "orange")


if __name__ == "__main__":
    unittest.main()
