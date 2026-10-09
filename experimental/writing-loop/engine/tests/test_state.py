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
全称量词不查：every bridge

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


def capped(text):
    """CLEAN with a 至多 line on its claim C1."""
    return CLEAN.replace("- 越界：three bridges", "- 越界：three bridges\n- 至多：" + text)


def setup(root, ledger=LEDGER, main=MAIN, intro=INTRO):
    repo = make_repo(root, [({"main.tex": main, "sections/01_intro.tex": intro}, "v1", 1_700_000_000)])
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
            self.assertIn("待做开着 2：N2 分析·未做、N1 出处·等作者", line,
                          "each open item by ID, kind and state, so a conversation's list can refer to it")
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

    def test_a_stage_that_names_a_submission_says_submitted_and_stops_asking(self):
        # 10-01: the author submitted and the ledger's stage said so, yet every turn's line still read 待作者终审 and
        # asked whether to submit. A stage that names a submission makes the verdict 已投稿; what still stands in the
        # way stays listed, for the revision.
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN.replace("阶段：终检", "阶段：已投稿，冻结"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.SUBMITTED)
            line = S.line(st)
            self.assertTrue(line.startswith("论文状态：已投稿（阶段：已投稿，冻结）"), line)
            self.assertNotIn("能不能投由作者定", line)
            self.assertIn("已投出：之后的改动等审稿意见", line)
            c = S.cell(st)
            self.assertEqual((c["value"], c["sub"], c["tone"]), ("已投稿", "已投出，等审稿意见", "white"))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["state", str(ws)]), 0)
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER.replace("阶段：分析", "阶段：submitted"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.SUBMITTED)
            self.assertTrue(st["blockers"], "what stood in the way is still there after submission")
            for b in st["blockers"]:
                if not b.startswith("待做开着"):
                    self.assertIn(b, S.line(st))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(["state", str(ws)]), 1, "submitted with blockers is not a clean exit")
        for stage in ("未投稿", "待投稿", "not yet submitted", "准备提交"):
            with TempDir() as root:
                ws, cfg = setup(root, CLEAN.replace("阶段：终检", "阶段：" + stage))
                self.assertEqual(S.compute(cfg, ws)["verdict"], S.AUTHOR, stage)

    def test_the_stage_is_a_name_and_a_paragraph_there_is_cut_and_said(self):
        # 09-28: a stage line had grown into an account of the round, what was left and the conversation's list items,
        # repeated in every turn's line. The author: the stage line holds the stage's name only.
        long_stage = ("终检，只收正确性。桥梁读数表按第二轮意见重排过，三座桥的补测跑完并进了附表，"
                      "剩：寄给合作者、上传、推送")
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN.replace("阶段：终检", "阶段：" + long_stage))
            st = S.compute(cfg, ws)
            self.assertEqual(st["verdict"], S.AUTHOR, "a long stage is untidy, not a reason to hold the paper")
            line = S.line(st)
            self.assertTrue(line.startswith("论文状态：待作者终审（阶段：终检，只收正确性…）"), line)
            self.assertNotIn("剩：", line)
            self.assertIn(f"阶段写成了一段话（{len(long_stage)} 字）：只写阶段名，过程进日志、待办进对话的清单", line)
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN.replace("阶段：终检", "阶段：冻结，只收正确性"))
            line = S.line(S.compute(cfg, ws))
            self.assertTrue(line.startswith("论文状态：待作者终审（阶段：冻结，只收正确性）"), line)
            self.assertNotIn("阶段写成了一段话", line)

    def test_a_universal_quantifier_in_the_abstract_says_its_size_or_names_a_set(self):
        # 09-28: an abstract said "every" of a kind of system; which ones came much later, and the word was also used
        # for systems added since. An outside review read it the wide way; every check had passed it.
        with TempDir() as root:
            ws, cfg = setup(root)
            st = S.compute(cfg, ws)
            self.assertEqual([(u["label"][0], u["phrase"]) for u in st["unscoped"]], [("A", "every bridge is safe")])
            self.assertIn("全称量词没对集合 1 处", S.line(st))
            self.assertIn("全称量词没对集合", S.table(st))
        with TempDir() as root:
            ws, cfg = setup(root, main=MAIN.replace("every bridge is safe", "all three gauges are sound"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["unscoped"], [], "a quantifier that says its size is scoped where it stands")
            self.assertIn("每一处都写了数目或对上了集合", S.table(st), "silence is said as what was looked at")
        with TempDir() as root:
            ws, cfg = setup(root, "全称量词不查：every bridge\n" + LEDGER)
            self.assertEqual(S.compute(cfg, ws)["unscoped"], [], "a phrase a person has read and let stand")
        with TempDir() as root:
            ws, cfg = setup(root, "全称量词查：I\n" + LEDGER)
            self.assertEqual(S.compute(cfg, ws)["unscoped"], [], "the places are the ledger's to name")

    def test_a_set_used_before_it_is_defined_or_never_defined_is_said(self):
        bridges = "\n## 集合 S1 测过的桥\n- 名词：bridges?\n- 定义：{define}\n- 大小：2\n"
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER + bridges.format(define="Gauges on two bridges"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["unscoped"], [])
            [e] = st["early"]
            self.assertEqual((e["set"], e["label"][0], e["defined"][0]), ("S1", "A", "I"))
            self.assertIn("集合在用之后才定义 S1", S.line(st))
            self.assertIn("用在定义", S.table(st))
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER + bridges.format(define="audit a bridge survey"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["early"], [], "defined in the abstract before the quantifier: in order")
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER + bridges.format(define="a sentence nobody wrote"))
            st = S.compute(cfg, ws)
            self.assertEqual(st["undefined"], ["S1"])
            self.assertIn("集合的定义句找不到 S1", S.line(st))
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER + "\n## 集合 S1 测过的桥\n- 大小：2\n")
            self.assertTrue(any("集合 S1 缺「名词、定义」" in p for p in S.compute(cfg, ws)["problems"]))

    def test_the_sets_noun_used_with_a_name_outside_it_is_listed_for_a_person(self):
        extra = "\n## 集合 S1 测过的桥\n- 名词：bridges?\n- 定义：audit a bridge survey\n- 集合外：gauges?\n"
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN + extra)
            st = S.compute(cfg, ws)
            [o] = st["outside"]
            self.assertEqual((o["set"], sorted({lab[0] for lab in o["labels"]})), ("S1", ["A", "I"]))
            self.assertIn("名词用在集合外的系统上", S.table(st))
            self.assertEqual(st["verdict"], S.AUTHOR, "reading it is a person's call, not a blocker")

    def test_a_carrying_sentence_without_the_allowed_qualifier_is_said(self):
        # 09-28: the allowed wording named two qualifiers; a discussion sentence had neither and passed, because only
        # the forbidden and the required wordings were patterns.
        c1 = "- 必须出现：do not test whether drivers"
        with TempDir() as root:
            ws, cfg = setup(root, CLEAN.replace("- 越界：three bridges", "- 越界：three bridges\n- 承载：two bridges\n"
                                                                    "- 限定词：gauges? ‖ in 2025"))
            st = S.compute(cfg, ws)
            [u] = st["unqualified"]
            self.assertEqual((u["claim"], u["pattern"], u["labels"][0][0]), ("C1", "in 2025", "I"))
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertIn("承载句缺限定词 C1", S.line(st))
            self.assertIn("承载句缺限定词「in 2025」", S.table(st))
        with TempDir() as root:
            ws, cfg = setup(root, LEDGER.replace(c1, c1 + "\n- 限定词：gauges?"))
            st = S.compute(cfg, ws)
            self.assertTrue(any("写了限定词没写承载" in p for p in st["problems"]), st["problems"])

    def test_a_wording_said_more_often_than_the_ledger_allows_is_said(self):
        # probe-growth #4: one limitation restated in six sentences of the draft, each worded differently; every check
        # passed, because a ledger could require a wording or forbid it but not cap how often it is said.
        main = MAIN.replace("The gauges prove that every bridge is safe.", "Drivers were not asked.")
        intro = INTRO.replace("Inspections are rare.", "Inspections are rare. No driver was surveyed. Whether drivers "
                                                       "notice is left untested.")
        cap = CLEAN.replace("- 越界：three bridges", "- 越界：three bridges\n- 至多：drivers? were not asked ‖ "
                                                     "do not test whether drivers ‖ no driver was surveyed ‖ drivers notice @ 2")
        with TempDir() as root:
            ws, cfg = setup(root, cap, main=main, intro=intro)
            st = S.compute(cfg, ws)
            [r] = [x for x in st["at_most"] if len(x["labels"]) > x["limit"]]
            self.assertEqual((r["claim"], r["limit"], [lab[0] for lab in r["labels"]]), ("C1", 2, ["A", "I", "I", "I"]))
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertIn("说太多遍 C1", S.line(st))
            self.assertIn("至多 2 句，现有 4 句", S.table(st))
        with TempDir() as root:  # the corrected twin: said twice, once where it is first raised and once in the abstract
            ws, cfg = setup(root, cap, main=main, intro=INTRO)
            st = S.compute(cfg, ws)
            self.assertEqual([len(x["labels"]) for x in st["at_most"]], [2])
            self.assertEqual(st["verdict"], S.AUTHOR)
            self.assertIn("至多 2 句，现有 2 句", S.table(st), "a cap that holds is said, not left silent")

    def test_a_sentence_is_counted_once_and_a_cap_can_hold_in_named_places(self):
        intro = INTRO.replace("Inspections are rare.", "No driver was surveyed, so we do not test whether drivers notice.")
        with TempDir() as root:
            ws, cfg = setup(root, capped("do not test whether drivers ‖ no driver was surveyed @ 1 I2"), intro=intro)
            st = S.compute(cfg, ws)
            self.assertEqual([x["labels"] for x in st["at_most"]], [["I2.1"]])
            self.assertEqual(st["verdict"], S.AUTHOR, "the first paragraph's mention lies outside I2")
        with TempDir() as root:
            ws, cfg = setup(root, capped("do not test whether drivers ‖ no driver was surveyed @ 1 I"), intro=intro)
            self.assertEqual(S.compute(cfg, ws)["verdict"], S.NOT_READY)

    def test_a_cap_without_a_number_is_a_ledger_problem(self):
        for cap in ("drivers? notice", "drivers? notice @ two", "drivers? notice @ I1"):
            with self.subTest(cap=cap), TempDir() as root:
                ws, cfg = setup(root, capped(cap))
                st = S.compute(cfg, ws)
                self.assertTrue(any("至多要写成" in p for p in st["problems"]), st["problems"])
                self.assertEqual(st["verdict"], S.NOT_READY)

    def test_quantifiers_are_read_in_english_and_chinese(self):
        self.assertEqual(S._quantified("We read all of the five gauges."), [("all of the five gauges", "five gauges")])
        self.assertTrue(S.NUMERAL.match(S._quantified("所有五座桥都更稳")[0][1]))
        self.assertEqual(S._quantified("每个仪表都更准")[0][1][:2], "仪表")
        self.assertEqual(S._quantified("None of the gauges fails")[0][1], "gauges fails")

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


class StaleLedgerHintTest(unittest.TestCase):
    """A required wording the whole draft no longer has, that an earlier indexed version still said: the draft may have
    been reworded on purpose and the ledger not, so `loop state` names the last commit that said it. A wording no
    version ever said gets no hint: then the ledger asks for something not yet written."""

    REWORDED = INTRO.replace("We do not test whether drivers notice.", "Drivers were not asked.")

    def setup_history(self, root, ledger, intros):
        """One commit per intro text, oldest first; the index built over all of them. Returns ws, cfg, shas."""
        commits = [({"main.tex": MAIN, "sections/01_intro.tex": t}, f"v{i}", 1_700_000_000 + i)
                   for i, t in enumerate(intros, 1)]
        repo = make_repo(root, commits)
        ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex"])
        cfg = C.load(ws)
        cfg["draft"]["format"] = "latex"
        cfg["draft"]["sections"] = RULES
        cfg["genre"] = "note"
        p = Path(root) / "claims.md"
        p.write_text(ledger, encoding="utf-8")
        cfg["claims"] = str(p)
        C.save(ws, cfg)
        cfg = C.load(ws)
        vs = H.load_versions(cfg)
        H.assign_ids(vs)
        head = git(cfg["repo"], "rev-parse", "HEAD")
        (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
        shas = git(cfg["repo"], "log", "--reverse", "--format=%H").split()
        return ws, cfg, shas

    def test_the_last_commit_that_said_it_is_named(self):
        intros = [INTRO, INTRO.replace("Inspections are rare.", "Inspections are scarce."), self.REWORDED,
                  self.REWORDED.replace("Inspections are rare.", "Inspections are few.")]
        with TempDir() as root:
            ws, cfg, shas = self.setup_history(root, LEDGER, intros)
            st = S.compute(cfg, ws)
            [a] = [x for x in st["absent"] if x["claim"] == "C1"]
            self.assertEqual(a["last_seen"]["sha"], shas[1], "the last version that still said it, not the first")
            self.assertIn(f"缺「do not test whether drivers」：整篇没有一句——可能是台账过期：该短语在 {shas[1][:7]} 之后不再出现",
                          S.table(st))

    def test_a_wording_no_version_said_gets_no_hint(self):
        ledger = LEDGER.replace("- 必须出现：do not test whether drivers", "- 必须出现：drivers were surveyed")
        with TempDir() as root:
            ws, cfg, _shas = self.setup_history(root, ledger, [INTRO, self.REWORDED])
            st = S.compute(cfg, ws)
            [a] = [x for x in st["absent"] if x["claim"] == "C1"]
            self.assertNotIn("last_seen", a)
            self.assertIn("缺「drivers were surveyed」：整篇没有一句", S.table(st))
            self.assertNotIn("台账过期", S.table(st))

    def test_a_wording_required_in_one_place_is_looked_for_in_that_place(self):
        """Moved out of the abstract into the introduction is absent where the ledger wants it; the hint names the
        last commit that had it in the abstract, and a version that had it only elsewhere does not count."""
        ledger = LEDGER.replace("- 必须出现：do not test whether drivers", "- 必须出现：drivers notice @ A")
        main_said = MAIN.replace("We audit a bridge survey.", "We audit a bridge survey. Whether drivers notice is open.")
        commits = [(main_said, INTRO), (MAIN, INTRO), (MAIN, INTRO.replace("Inspections are rare.", "Checks are rare."))]
        with TempDir() as root:
            repo = make_repo(root, [({"main.tex": m, "sections/01_intro.tex": t}, f"v{i}", 1_700_000_000 + i)
                                    for i, (m, t) in enumerate(commits, 1)])
            ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex"])
            cfg = C.load(ws)
            cfg["draft"].update(format="latex", sections=RULES)
            cfg["genre"] = "note"
            p = Path(root) / "claims.md"
            p.write_text(ledger, encoding="utf-8")
            cfg["claims"] = str(p)
            C.save(ws, cfg)
            cfg = C.load(ws)
            vs = H.load_versions(cfg)
            H.assign_ids(vs)
            (Path(ws) / "index" / "sentences.json").write_text(
                json.dumps({"head": git(cfg["repo"], "rev-parse", "HEAD"), "versions": vs}), encoding="utf-8")
            shas = git(cfg["repo"], "log", "--reverse", "--format=%H").split()
            st = S.compute(cfg, ws)
            [a] = [x for x in st["absent"] if x["claim"] == "C1"]
            self.assertEqual(a["place"], "A")
            self.assertEqual(a["last_seen"]["sha"], shas[0], "v2 has it only in the introduction, which is not A")


if __name__ == "__main__":
    unittest.main()


PAGE_UUID = "aaaa1111-0000-4000-8000-000000000001"
STEP_UUID = "bbbb2222-0000-4000-8000-000000000002"
CARD = """# 意图卡

## 讲法页 · Story page（作者认可：uuid {page}）

1. 问题：桥的读数可能被别的东西带偏。
2. 缺口：没人换过测量点。{step2}
3. 结果：换测量点以后读数变了。{step3}

不放进讲法页：仪器型号。

以下是历史：
1. 旧的第一步
2. 旧的第二步

## 读者
- 记忆点 M1
"""


class StoryPageTest(unittest.TestCase):
    """spec 2026-09-28-story-layer S3: the loop reads the story page's steps and their approvals; a step no author has
    approved keeps the paper from 待作者终审 (the author's call, taken as recommended; one line to reverse)."""

    def run_card(self, root, page=PAGE_UUID, step2="", step3="", on_record=(PAGE_UUID,), card=None):
        from fixtures import make_transcripts
        ws, cfg = setup(root, CLEAN)
        make_transcripts(root, cfg["transcripts"]["cwd_prefix"], cfg["transcripts"]["git_branch"],
                         [{"type": "user", "uuid": u, "timestamp": "2026-09-28T00:00:00Z",
                           "message": {"role": "user", "content": "可以"}} for u in on_record])
        p = Path(root) / "card.md"
        p.write_text(card if card is not None else CARD.format(page=page, step2=step2, step3=step3), encoding="utf-8")
        cfg["target"] = {"intent_card": str(p)}
        return S.compute(cfg, ws)

    def test_every_step_under_an_approved_page_counts_and_the_paper_can_reach_the_author(self):
        with TempDir() as root:
            st = self.run_card(root)
            self.assertEqual((st["story"]["approved"], st["story"]["steps"]), (3, 3), "the history list is not the page")
            self.assertEqual(st["verdict"], S.AUTHOR)
            self.assertIn("讲法页 3/3 步认可", S.line(st))

    def test_a_step_marked_unapproved_keeps_the_paper_from_the_author(self):
        with TempDir() as root:
            st = self.run_card(root, step3="◌")
            self.assertEqual((st["story"]["approved"], st["story"]["steps"]), (2, 3))
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertIn("讲法页 2/3 步认可", S.line(st))

    def test_an_approval_that_is_not_on_record_approves_nothing(self):
        with TempDir() as root:
            st = self.run_card(root, on_record=())
            self.assertEqual(st["story"]["approved"], 0)
            self.assertEqual(st["verdict"], S.NOT_READY)

    def test_a_step_approved_on_its_own_counts_without_a_page_approval(self):
        with TempDir() as root:
            st = self.run_card(root, page="cccc3333-0000-4000-8000-000000000003", step2=f"（uuid {STEP_UUID}）",
                               on_record=(STEP_UUID,))
            self.assertEqual(st["story"]["approved"], 1)

    def test_a_card_without_a_story_page_keeps_the_paper_from_the_author(self):
        # 10-07: a card without a page used to be said and block nothing, so an abstract whose order no page
        # could check reached the author with every reader point carried, and the author could not follow it. A
        # missing page is at least as open as an unapproved step, which already blocks (S3).
        for card, said in (("# 意图卡\n\n## 读者\n- 记忆点 M1\n", "意图卡里没有讲法页"),
                           ("# 意图卡\n\n## 讲法页\n\n先讲问题，再讲修法。\n", "讲法页没列出编号的步骤")):
            with self.subTest(said=said), TempDir() as root:
                st = self.run_card(root, card=card)
                self.assertEqual(st["story"]["steps"], 0)
                self.assertEqual(st["verdict"], S.NOT_READY)
                self.assertIn(said, st["blockers"])
                self.assertEqual(S.line(st).count(said), 1, "said once, as a blocker")
