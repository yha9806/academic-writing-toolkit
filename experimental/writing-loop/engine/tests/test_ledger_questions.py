"""The claims ledger is questioned, not only checked (spec 2026-09-25 §4.2, §4.4): a required wording can be held to
a place (the problem in the abstract and the first introduction paragraph), each claim lists the sentences that state
it, a universal negation needs a named test, "A significant, B not" is flagged as evidence of a difference, method
sentences that close off an alternative are set beside sentences that name a remaining cue, and required gates
(statistical review, a domain reader) hold the paper until a person closes them. Synthetic wording; no manuscript."""
import json
import unittest
from pathlib import Path

from loop import config as C
from loop import history as H
from loop import state as S

from fixtures import TempDir, git, make_repo, workspace

MAIN = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We audit a bridge survey. Gauges on two bridges read 12 points.
\end{abstract}
\input{sections/01_intro}
\end{document}
"""
INTRO = r"""\section{Introduction}\label{sec:intro}
Surveys may rate a bridge by its gauges alone. We ask whether gauge readings rate the bridge or the gauge.

Only the gauge model differs between the two spans. The paint shade is a cue the survey does not control.
"""
RULES = [{"match": r"^Abstract$", "prefix": "A", "kind": "prose", "flat": True},
         {"match": r"^Introduction$", "prefix": "I", "kind": "prose"}]

BASE = """阶段：终检

## 主张 C1 两座桥的读数是 12
- 证据：表 1
- 强度：强
- 允许的说法：两座桥
"""


def setup(root, ledger, register=None, gates=None):
    repo = make_repo(root, [({"main.tex": MAIN, "sections/01_intro.tex": INTRO}, "v1", 1_700_000_000)])
    ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex"])
    cfg = C.load(ws)
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = RULES
    cfg["genre"] = "note"
    p = Path(root) / "claims.md"
    p.write_text(ledger, encoding="utf-8")
    cfg["claims"] = str(p)
    if register is not None:
        r = Path(ws) / "human" / "risks.md"   # the author's own register: decided items need no uuid
        r.parent.mkdir(parents=True, exist_ok=True)
        r.write_text(register, encoding="utf-8")
        cfg["risks"] = str(r)
    if gates is not None:
        cfg["state"] = {"required_gates": gates}
    C.save(ws, cfg)
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    head = git(cfg["repo"], "rev-parse", "HEAD")
    (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
    return ws, C.load(ws)


class PlaceTest(unittest.TestCase):
    def test_a_wording_required_in_named_places_is_absent_from_a_place_it_does_not_reach(self):
        # A wording required anywhere is satisfied by one sentence deep in the text; "the problem comes first" needs
        # the abstract and the first introduction paragraph each to carry it.
        with TempDir() as root:
            ws, cfg = setup(root, BASE + "- 必须出现：we ask whether gauge readings @ A, I1\n")
            st = S.compute(cfg, ws)
            self.assertEqual([(a["claim"], a.get("place")) for a in st["absent"]], [("C1", "A")])
            self.assertEqual(st["verdict"], S.NOT_READY)
            self.assertIn("@ A", S.table(st))

    def test_a_place_names_a_paragraph_not_every_paragraph_whose_number_starts_with_it(self):
        self.assertTrue(S.in_place("I1.2", "I1"))
        self.assertFalse(S.in_place("I10.2", "I1"))
        self.assertTrue(S.in_place("A01", "A"))
        self.assertFalse(S.in_place("Ab1.1", "A"), "a place of letters names that prefix, not a longer one")

    def test_an_unscoped_wording_keeps_its_meaning(self):
        with TempDir() as root:
            ws, cfg = setup(root, BASE + "- 必须出现：we ask whether gauge readings\n")
            self.assertEqual(S.compute(cfg, ws)["absent"], [])


class CarryTest(unittest.TestCase):
    def test_each_claim_lists_every_sentence_that_states_it_changed_or_not(self):
        with TempDir() as root:
            ws, cfg = setup(root, BASE + "- 承载：two bridges\n")
            st = S.compute(cfg, ws)
            self.assertEqual(st["carrying"], {"C1": ["A02"]})
            self.assertIn("承载句：A02", S.table(st))


class NegationTest(unittest.TestCase):
    NEG = """阶段：终检

## 主张 C1 No gauge model reads the paint
- 证据：表 2
- 强度：中
- 允许的说法：检测不到
"""

    def test_a_universal_negation_without_a_named_test_holds_the_paper(self):
        with TempDir() as root:
            ws, cfg = setup(root, self.NEG)
            st = S.compute(cfg, ws)
            self.assertIn("C1", st["negations"])
            self.assertTrue(any("全称否定" in b for b in st["blockers"]), st["blockers"])
            ws, cfg = setup(Path(root) / "b", self.NEG + "- 依据：遮漆检验（运行 r-3，检验力 0.8）\n")
            st = S.compute(cfg, ws)
            self.assertEqual(st["negations"], [])
            self.assertEqual(st["verdict"], S.AUTHOR)

    def test_one_significant_and_one_not_is_flagged_as_evidence_of_a_difference(self):
        with TempDir() as root:
            ws, cfg = setup(root, BASE.replace("- 证据：表 1", "- 证据：北桥显著、南桥不显著，所以两桥不同"))
            st = S.compute(cfg, ws)
            self.assertEqual([w["claim"] for w in st["warnings"]], ["C1"])
            self.assertEqual(st["verdict"], S.AUTHOR, "a warning is for a person to read, not a blocker")
            self.assertIn("一个显著一个不显著", S.table(st))


class MethodTest(unittest.TestCase):
    def test_a_sentence_that_closes_off_an_alternative_is_set_beside_one_that_names_a_remaining_cue(self):
        with TempDir() as root:
            ws, cfg = setup(root, BASE)
            st = S.compute(cfg, ws)
            self.assertEqual(st["closing"], ["I2.1"])
            self.assertEqual(st["remaining"], ["I2.2"])
            self.assertIn("方法句", S.table(st))

    def test_figure_text_is_read_for_method_sentences_too(self):
        # A figure said no cue was left while the text named one; the sentence index holds only the text.
        q = S.question([], [], [{"label": "figures/f.tex:1", "text": "The design leaves no non-semantic cue left to remove."}])
        self.assertEqual(q["closing"], ["figures/f.tex:1"])


class GateTest(unittest.TestCase):
    OPEN = """## 门 G1 冻结前的统计审查
- 来源：synthetic
- 消除它的证据：审查记录
- 由哪个门决定：G1
- 状态：未决
"""

    def test_a_required_gate_holds_the_paper_until_the_register_closes_it(self):
        with TempDir() as root:
            ws, cfg = setup(root, BASE, register=self.OPEN, gates=["统计审查", "领域审阅"])
            st = S.compute(cfg, ws)
            self.assertEqual(st["gates_open"], ["统计审查", "领域审阅"])
            self.assertEqual(st["verdict"], S.NOT_READY)
            done = self.OPEN.replace("状态：未决", "状态：已决 2026-01-02 审过") + self.OPEN.replace("G1", "G2").replace(
                "冻结前的统计审查", "上传前的领域审阅").replace("状态：未决", "状态：已决 2026-01-03 读过")
            ws, cfg = setup(Path(root) / "b", BASE, register=done, gates=["统计审查", "领域审阅"])
            st = S.compute(cfg, ws)
            self.assertEqual(st["gates_open"], [])
            self.assertEqual(st["verdict"], S.AUTHOR)

    def test_no_required_gate_changes_nothing(self):
        with TempDir() as root:
            ws, cfg = setup(root, BASE)
            self.assertEqual(S.compute(cfg, ws)["verdict"], S.AUTHOR)


if __name__ == "__main__":
    unittest.main()
