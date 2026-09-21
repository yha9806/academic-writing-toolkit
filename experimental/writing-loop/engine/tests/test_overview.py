import json
import unittest
from pathlib import Path

from loop import config as C
from loop import inbox as IB
from loop import lintel as L
from loop import overview as O

from fixtures import TempDir, make_repo, workspace

DAY = 86400
T0 = 1_789_000_000

SMITH = "Smith et al. show that the effect holds across pools~\\cite{smith2020}."
USE = "We use the ranking procedure~\\cite{y2019}."
REPORT = "We report bootstrap intervals~\\cite{z1934} for every cell."
LEDGER = ("claim\tcite_key\tsnippet\tsource_file\tlevel\n"
          "Smith et al. show that the effect holds across pools\tsmith2020\tthe effect holds across pools\tsources/smith2020.txt\tfulltext\n")


def sent(i, section, text):
    return {"hash": f"h{abs(hash(text)) % 10**10}", "section": section, "sid": f"S{i}", "path": "sections/a.tex", "text": text}


def build_ws(root, report=None, issues=None):
    """Two stages (a nine-day gap between the second and third version); the ledger arrives in a commit after the last
    version, so the current stage has one commit without it and one with it."""
    one = f"\\section{{Introduction}}\n{SMITH}\n{USE}\n"
    three = one + REPORT + "\n"
    extra = {"build/report.json": json.dumps(report)} if report else {}
    repo = make_repo(root, [
        ({"sections/a.tex": one}, "first", T0),
        ({"sections/a.tex": one + "A plain sentence.\n"}, "second", T0 + DAY),
        ({"sections/a.tex": three + "A plain sentence.\n"}, "third", T0 + 10 * DAY),
        ({"audit/ledger/ledger.tsv": LEDGER, "audit/ledger/sources/smith2020.txt": "We find that the effect holds across pools.\n",
          **extra}, "ledger", T0 + 11 * DAY),
    ])
    from fixtures import git
    shas = git(repo, "log", "--reverse", "--format=%H").split()
    ws = workspace(root, repo, "main", glob="sections/*.tex")
    cfg = json.loads((ws / "config.json").read_text(encoding="utf-8"))
    cfg["draft"]["sections"] = [{"match": "^Introduction$", "prefix": "I", "kind": "prose", "short": "§1"}]
    cfg["overview"] = {"ledger": {"path": "audit/ledger/ledger.tsv", "base_dir": "sections", "archive": ["sections", "audit"]},
                       "ledger_scope": "正文", **({"issues": issues} if issues else {}),
                       **({"build_report": "build/report.json"} if report else {})}
    C.save(ws, cfg)
    v1 = [sent(1, "I", SMITH), sent(2, "I", USE)]
    v2 = v1 + [sent(3, "I", "A plain sentence.")]
    v3 = v1 + [sent(4, "I", REPORT), sent(3, "I", "A plain sentence.")]
    versions = [{"sha": shas[0], "time": T0, "sentences": v1}, {"sha": shas[1], "time": T0 + DAY, "sentences": v2},
                {"sha": shas[2], "time": T0 + 10 * DAY, "sentences": v3}]
    idx = ws / "index"
    (idx / "sentences.json").write_text(json.dumps({"head": shas[2], "versions": versions}), encoding="utf-8")
    (idx / "changesets.json").write_text(json.dumps({"head": shas[2], "changesets": [
        {"id": shas[2][:7], "time": T0 + 10 * DAY, "triggers": ["h-1"], "status": "one",
         "rows": [{"kind": "added", "new": {"label": "I1.3", "section": "I"}}]}]}), encoding="utf-8")
    (idx / "checks.json").write_text("null", encoding="utf-8")
    (idx / "explanations.json").write_text(json.dumps({"explanations": [{"mid": "h-1", "label": "补区间"}]}), encoding="utf-8")
    return C.load(ws), shas


class StagesTest(unittest.TestCase):
    """分镜 ㊸ 的第一块：版本之间空 3 天以上就分段；每天改过或新加几句；长空档折成一格。"""

    def test_a_gap_of_three_days_or_more_starts_a_stage(self):
        vs = [{"sha": "a", "time": T0, "sentences": []}, {"sha": "b", "time": T0 + 2 * DAY, "sentences": []},
              {"sha": "c", "time": T0 + 6 * DAY, "sentences": []}]
        self.assertEqual([[v["sha"] for v in s] for s in O.split_stages(vs)], [["a", "b"], ["c"]])

    def test_a_long_empty_run_folds_into_one_gap_bar(self):
        with TempDir() as t:
            cfg, _ = build_ws(t)
            bars = O.build(cfg, T0 + 12 * DAY)["payload"]["days"]["bars"]
        gaps = [b for b in bars if "gapDays" in b]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["gapDays"], 8)
        self.assertEqual([b["stage"] for b in bars if "stage" in b], [0, 0, 1])

    def test_the_first_stage_starts_from_the_first_draft_not_a_stub(self):
        stub = {"sha": "s", "time": T0, "sentences": [{"hash": "x", "section": "I"}]}
        full = {"sha": "f", "time": T0 + 60, "sentences": [{"hash": str(i), "section": "I"} for i in range(40)]}
        self.assertEqual(O.first_draft([stub, full])["sha"], "f")


class ProfileTest(unittest.TestCase):
    """剖面：一格一节，宽 = 句数，高 = 这一段改过的比例；小卡写碰过它的改动集。"""

    def test_changed_removed_and_new_sections_against_the_stage_base(self):
        base = {"sentences": [{"hash": "a", "section": "A"}, {"hash": "b", "section": "A"}, {"hash": "c", "section": "B"}]}
        head = {"sentences": [{"hash": "a", "section": "A"}, {"hash": "d", "section": "A"}, {"hash": "e", "section": "C"}]}
        cells = O.heat(base, head, {"A": "§1", "C": "§2.1"},
                       [{"id": "c1", "time": T0, "sections": ["A"]}], {"c1": "补一句"})
        a, c = cells
        self.assertEqual((a["weight"], a["changed"], a["removed"], a["mark"]), (2, 1, 1, False))
        self.assertEqual((c["weight"], c["changed"], c["mark"], c["chapter"]), (1, 1, True, "§2"))
        self.assertIn("1 个改动集碰过它", a["note"])
        self.assertIn("「补一句」", a["note"])
        self.assertIn("0 个改动集碰过它", c["note"])


class AlignmentTest(unittest.TestCase):
    """依据：稿件仓的主张台账，按提交跑 AWT 的审计；建台账之前的提交也有点（什么都没绑）。"""

    def test_trend_marks_when_the_ledger_arrived_and_items_name_what_is_missing(self):
        with TempDir() as t:
            cfg, _ = build_ws(t)
            st = O.build(cfg, T0 + 12 * DAY)["payload"]["stages"]
        self.assertEqual(st[0]["alignment"]["empty"], "这一段还没有台账，不画这一块")
        al = st[1]["alignment"]
        self.assertEqual([(p["scope"], p["done"], p["missing"]) for p in al["trend"]["points"]], [(3, 0, 2), (3, 1, 1)])
        self.assertEqual(al["trend"]["marker"], 1)
        self.assertEqual(al["headline"][0]["value"], "1")
        [item] = [i for i in al["items"] if i["tag"] == "缺依据"]
        self.assertEqual(item["key"], "z1934")
        self.assertEqual(item["action"]["id"], "credit|z1934=report bootstrap intervals")

    def test_marking_a_method_credit_takes_the_sentence_out_of_missing(self):
        with TempDir() as t:
            cfg, _ = build_ws(t)
            ovw = O.Overview(cfg)
            now = T0 + 12 * DAY
            ok, _ = O.apply_action(ovw, "credit|z1934=report bootstrap intervals", now)
            self.assertTrue(ok)
            self.assertIn("z1934 = report bootstrap intervals", ovw.credits_path().read_text(encoding="utf-8"))
            self.assertEqual(ovw.credits_path(), Path(cfg["_ws"]) / "human" / "credits.txt")
            al = ovw.get(now)["payload"]["stages"][1]["alignment"]
        self.assertEqual(al["headline"][0]["value"], "0")
        self.assertEqual([i["tag"] for i in al["items"]], ["方法署名"])
        self.assertIn("1 句你标了方法署名", al["caption"])

    def test_an_action_the_panel_did_not_offer_writes_nothing(self):
        with TempDir() as t:
            cfg, _ = build_ws(t)
            ovw = O.Overview(cfg)
            ok, why = O.apply_action(ovw, "credit|smith2020=anything at all", T0 + 12 * DAY)
            self.assertFalse(ok)
            self.assertIn("不在当前面板上", why)
            self.assertFalse(ovw.credits_path().exists())

    def test_a_malformed_credit_is_not_parsed(self):
        self.assertIsNone(O.parse_credit("credit|k=a = b"))
        self.assertIsNone(O.parse_credit("credit|bad key=x"))
        self.assertIsNone(O.parse_credit("drop|k=x"))


class TodoTest(unittest.TestCase):
    """还差什么：只对着清单算；问不到就说问不到，没有清单就不写完成度。"""

    def test_no_list_means_no_ratio(self):
        with TempDir() as t:
            cfg, _ = build_ws(t)
            cells = O.build(cfg, T0 + 12 * DAY)["payload"]["todo"]["cells"]
        self.assertEqual(cells[0]["text"], "没有登记清单")
        self.assertNotIn("%", json.dumps(cells, ensure_ascii=False))

    def test_issues_that_cannot_be_asked_say_so_instead_of_zero(self):
        with TempDir() as t:
            cfg, _ = build_ws(t, issues={"remote": "origin"})   # the fixture repo has no GitHub remote
            cells = O.build(cfg, T0 + 12 * DAY)["payload"]["todo"]["cells"]
        self.assertEqual(cells[0]["text"], "取不到")

    def test_the_build_report_says_what_blocks_the_upload(self):
        with TempDir() as t:
            cfg, _ = build_ws(t, report={"ready_to_upload": False, "failures": [], "title_page_placeholders": 2,
                                         "source_commit": "abcdef123"})
            cells = O.build(cfg, T0 + 12 * DAY)["payload"]["todo"]["cells"]
        self.assertEqual(cells[1]["text"], "失败 0 项 · 标题页 2 处待填")
        self.assertEqual(cells[1]["sub"], "所以还不能上传 · 构建于 abcdef1")
        self.assertEqual(cells[1]["tone"], "orange")


class InboxActionTest(unittest.TestCase):
    """面板上的动作和拖放共用收件目录：拖放归 `loop inbox`，动作归那份稿子的常驻产出。"""

    def _home(self, root):
        home = Path(root) / "lintel"
        (home / "producers" / "awt-loop" / "inbox").mkdir(parents=True)
        (home / "registry.json").write_text(json.dumps({"schema": 1, "producers": {"awt-loop": {"name": "写作循环"}}}), encoding="utf-8")
        return home

    def _action(self, home, name, activity, action):
        p = home / "producers" / "awt-loop" / "inbox" / f"{name}.json"
        p.write_text(json.dumps({"schema": 1, "kind": "action", "activity": activity, "action": action,
                                 "at": "2026-09-21T12:00:00Z", "from": "lintel"}), encoding="utf-8")
        return p

    def test_actions_for_another_manuscript_are_left_alone(self):
        with TempDir() as t:
            home = self._home(t)
            mine = self._action(home, "a1", "loop-paper", "credit|k=a b")
            other = self._action(home, "a2", "loop-other", "credit|k=a b")
            got = IB.take_actions(home, "loop-paper", lambda a: (True, "ok"))
            self.assertEqual([(n, ok) for n, ok, _ in got], [("a1.json", True)])
            self.assertFalse(mine.exists())
            self.assertTrue(other.exists())
            done = json.loads((home / "producers/awt-loop/inbox/done/a1.json").read_text(encoding="utf-8"))
            self.assertEqual(done["outcome"], {"ok": True, "reason": "ok"})

    def test_loop_inbox_does_not_refuse_an_action_as_a_bad_drop(self):
        with TempDir() as t:
            home = self._home(t)
            p = self._action(home, "a1", "loop-paper", "credit|k=a b")
            self.assertEqual(IB.process(home, Path(t) / "workspaces"), [])
            self.assertTrue(p.exists())


class PanelTest(unittest.TestCase):
    """面板：detail.overview 在，最下一行 = 最近一轮；第二层每行带碰过的节，好按节筛。"""

    def test_overview_rides_on_the_detail_and_history_rows_name_their_sections(self):
        hist = [{"id": "c1", "time": T0, "n": 2, "traced": True, "label": "补区间", "verbatim": "v", "status": "one",
                 "rows": [{"label": "I1.3", "section": "I"}]}]
        s = {"name": "ws", "head": "abc1234", "versions": 3, "sentences": 4, "changesets": 1, "ledger_status": {},
             "unattached_ledger": 0, "latest_changeset": None, "history": hist, "section_names": {"I": "§1"}}
        ov = {"payload": {"days": {"title": "t", "bars": []}, "stages": [], "selected": 0,
                          "todo": {"title": "还差什么", "cells": []}},
              "touches": {"c1": ["I", "B"]}, "actions": set(), "stage_changesets": 1}
        d = L.build(s, now=T0, overview=ov)[0]["detail"]
        self.assertEqual(d["history"][0]["sections"], ["I", "B"])
        self.assertEqual(d["overview"]["latest"]["tag"], "补区间")
        self.assertEqual(d["overview"]["latest"]["more"], "这一段 1 个改动集")
        self.assertNotIn("overview", L.build(s, now=T0)[0]["detail"])


if __name__ == "__main__":
    unittest.main()
