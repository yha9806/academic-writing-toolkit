import json
import os
import unittest
from pathlib import Path

from loop import coverage as V
from loop import index as X
from loop import lintel as L

from fixtures import TempDir

NOW = 1_789_700_000

CLEAN = {"name": "ws", "head": "abc1234", "versions": 15, "sentences": 82, "changesets": 14,
         "mixed": 0, "all_unknown": 0, "ledger": 91,
         "ledger_status": {"found": 91}, "unattached_ledger": 0,
         "messages": 64, "messages_attached": 1, "messages_before_first_version": 17,
         "latest_changeset": None, "history": []}


def summary(**over):
    s = dict(CLEAN)
    s["ledger_status"] = dict(CLEAN["ledger_status"])
    s["history"] = list(CLEAN["history"])
    s.update(over)
    return s


def change(n=15, traced=True, label=None, reading="改正 §3.2 那几句", verbatim="改 §3.2 那句 betaVal", cid="c0ffee1"):
    rows = [{"kind": "edited", "label": f"X{i}", "old": f"old {i}", "new": f"new {i}"} for i in range(n)]
    return {"id": cid, "subject": "s", "time": NOW - 60, "status": "one" if traced else "none",
            "rows": rows, "n": n, "traced": traced, "mid": "h-1" if traced else None,
            "verbatim": verbatim if traced else None, "reading": reading if traced else None,
            "changed": "X6.2、X7.2" if traced else None, "basis": None, "label": label}


def with_change(**kw):
    lc = change(**kw)
    return summary(latest_changeset=lc, changesets=CLEAN["changesets"],
                   history=[{"id": lc["id"], "time": lc["time"], "n": lc["n"], "traced": lc["traced"],
                             "verbatim": lc["verbatim"], "status": lc["status"]}])


def only(acts):
    return acts[0]


class CoverageStatTest(unittest.TestCase):
    """The card's data strip says how many checks have not looked at the draft as it is now (spec 2026-09-21 D4).
    Since the strip of storyboard ⑥③ the cell is 有发现 (checks that found something, gap 1); the to-do, the checks AWT
    cannot run here and the waivers are in its hover hint, never dropped."""

    def stat(self, act):
        return [x for x in act["detail"]["stats"] if x["label"].startswith("检查") or x["label"] == "有发现"]

    def test_no_coverage_given_adds_nothing(self):
        self.assertEqual(self.stat(only(L.build(summary(), now=NOW))), [])

    def test_a_workspace_never_computed_says_so_in_orange(self):
        got = self.stat(only(L.build(summary(), now=NOW, coverage=None)))
        self.assertEqual(got, [{"label": "检查", "value": "没算过", "tone": "orange"}])

    def test_checks_needing_attention_are_counted_and_none_is_quiet(self):
        rows = [{"id": "a", "name": "甲", "status": "过期"}, {"id": "b", "name": "乙", "status": "最新"},
                {"id": "c", "name": "丙", "status": "不适用", "instead": None}]
        got = self.stat(only(L.build(summary(), now=NOW, coverage={"rows": rows, "target": {}})))
        self.assertEqual((got[0]["value"], got[0]["tone"]), ("0", "orange"), "nothing found, but a stale check: orange")
        self.assertIn("检查待办 1：甲", got[0]["hint"],
                      "the stale check counts; a check the toolkit cannot run on this draft is a gap, not a task")
        rows = [{"id": "b", "name": "乙", "status": "最新"}]
        got = self.stat(only(L.build(summary(), now=NOW, coverage={"rows": rows, "target": {}})))
        self.assertEqual(got, [{"label": "有发现", "value": "0"}], "no None reaches the host")

    def test_a_check_the_toolkit_cannot_run_here_is_counted_as_a_gap(self):
        rows = [{"id": "b", "name": "乙", "status": "最新"}, {"id": "c", "name": "丙", "status": "不适用", "instead": None}]
        got = self.stat(only(L.build(summary(), now=NOW, coverage={"rows": rows, "target": {}})))
        self.assertIn("AWT 读不了 1", got[0]["hint"])
        self.assertEqual(got[0]["value"], "0")

    def test_a_waiver_is_counted_on_the_card(self):
        rows = [{"id": "b", "name": "乙", "status": "已豁免", "detail": "作者：不做"}]
        got = self.stat(only(L.build(summary(), now=NOW, coverage={"rows": rows, "target": {}})))
        self.assertIn("豁免 1", got[0]["hint"])

    def test_a_summary_of_the_wrong_shape_is_not_read_as_clean(self):
        got = self.stat(only(L.build(summary(), now=NOW, coverage={"rows": 5})))
        self.assertEqual(got[0]["value"], "读不出")


class OneActivityTest(unittest.TestCase):
    """设计研究 P1（作者 09-18 定稿）：一个稿件一个活动，两个位置各归一个来源，谁也挤不掉谁。"""

    def test_one_activity_whatever_the_state(self):
        cases = [
            (summary(), (), ()),
            (with_change(), (), ()),
            (with_change(traced=False), (), ()),
            (with_change(), ["doctor: 台账路径读不到"], ["拦下写入：1 次"]),
            (summary(ledger_status={"found": 88, "no_source": 3}, all_unknown=12, mixed=2), ["x"], ["y"]),
        ]
        for s, problems, notices in cases:
            acts = L.build(s, now=NOW, problems=problems, notices=notices)
            self.assertEqual([a["id"] for a in acts], ["loop-ws"], (problems, notices))

    def test_each_manuscript_has_its_own_activity_id(self):
        self.assertEqual(only(L.build(summary(name="Demo"), now=NOW))["id"], "loop-Demo")
        self.assertEqual(L.activity_id("draft v2 / 2026"), "loop-draft-v2-2026")

    def test_the_wing_is_the_reason_claude_wrote_else_the_count(self):
        # channel-separation §5（作者 09-21）：字里不再有数，数在 label.count
        a = only(L.build(with_change(label="betaVal 说反"), now=NOW))
        self.assertEqual((a["label"]["text"], a["label"]["count"]), ("betaVal 说反", 15))
        b = only(L.build(with_change(label=None), now=NOW))
        self.assertEqual((b["label"]["text"], b["label"]["count"]), ("改了", 15))
        self.assertNotIn("15", b["label"]["text"])
        # a reason longer than the wing is cut, not dropped
        long = only(L.build(with_change(label="这一句说反了要改回来"), now=NOW))["label"]["text"]
        self.assertLessEqual(L.width(long), L.LABEL_MAX)
        self.assertTrue(long.endswith("…"))
        # width, not code points: seven Latin letters and two characters fit; ten characters do not
        self.assertEqual(L.width("betaVal 说反"), 6)

    def test_a_traced_change_is_active_not_attention(self):
        a = only(L.build(with_change(), now=NOW))
        self.assertFalse(a["flagged"])
        self.assertEqual(a["rank"], "none")   # 设计 2026-09-22-awt-live M4：event 在协议里是「只停几秒」
        self.assertEqual([e["type"] for e in a["events"]], ["changed"])
        # 「你说」「读成」由许愿柳说（对话层只有一份，#28）；写作循环留「改了」，有依据时加「依据」
        self.assertEqual([p["label"] for p in a["popup"]], ["改了"])
        self.assertNotIn("改 §3.2 那句 betaVal", json.dumps(a["popup"], ensure_ascii=False))
        s = with_change(); s["latest_changeset"]["basis"] = "你 09-24 的第二条"
        self.assertEqual([p["label"] for p in only(L.build(s, now=NOW))["popup"]], ["改了", "依据"])
        self.assertEqual(a["pill"]["title"], "15")

    def test_an_untraced_change_is_time_sensitive(self):
        # 分镜 ㊳（作者 09-21）：窗口里有你的消息但没一条对上 = Claude 改了你没让改的 → Time Sensitive
        s = with_change(traced=False); s["latest_changeset"]["messages_in_window"] = 3
        a = only(L.build(s, now=NOW))
        self.assertEqual(a["label"]["text"], "改动无出处")
        self.assertTrue(a["flagged"])
        self.assertEqual(a["status"]["center"], "flagged")
        self.assertEqual([e["type"] for e in a["events"]], ["drift"])
        self.assertEqual([p["label"] for p in a["popup"]], ["改了", "无出处"])
        self.assertEqual(a["popup"][1]["text"], "窗口里 3 条消息都对不上")
        self.assertEqual((a["label"]["count"], a["pill"]["title"]), (15, "15 △"))   # 胶囊保留 △（作者 09-21）
        # 刚发生的一小时里压过普通的事；之后只靠 flagged
        self.assertEqual(a["rank"], "event")
        self.assertEqual(only(L.build(s, now=NOW - 60 + L.DRIFT_FRESH))["rank"], "none")

    def test_a_change_with_no_message_of_yours_in_the_window_is_history_not_an_alert(self):
        # 分镜 ㊳：窗口里没有你的消息 = 别的会话或你自己提交的；翼换字、不弹、灰、changed
        a = only(L.build(with_change(traced=False), now=NOW))
        self.assertEqual((a["label"]["text"], a["label"]["tone"], a["label"]["count"]), ("别处改了", "white55", 15))
        self.assertFalse(a["flagged"])
        self.assertEqual((a["rank"], a["status"]["center"]), ("none", "idle"))
        self.assertEqual([e["type"] for e in a["events"]], ["changed"])
        self.assertEqual([p["label"] for p in a["popup"]], ["改了", "别处"])
        self.assertEqual(a["popup"][1]["text"], "窗口里没有你的消息")
        self.assertEqual(a["pill"]["title"], "15")

    def test_a_fault_outranks_a_change(self):
        a = only(L.build(with_change(), now=NOW, problems=["索引：读不出"]))
        self.assertEqual(a["label"]["text"], "跑挂了")
        self.assertEqual((a["rank"], a["status"]["center"]), ("anomaly", "broken"))
        self.assertIn("tool-broken", [e["type"] for e in a["events"]])

    def test_passive_things_stay_off_the_wings(self):
        s = with_change()
        s["ledger_status"] = {"found": 88, "no_source": 3}
        a = only(L.build(s, now=NOW, notices=["拦下写入：2 次"]))
        wings = json.dumps([a["label"], a["ears"], a["popup"], a["body"]], ensure_ascii=False)
        self.assertNotIn("拦下", wings)
        self.assertNotIn("缺依据", wings)
        stats = {c["label"]: c["value"] for c in a["detail"]["stats"]}
        self.assertEqual((stats["拦下"], stats["缺依据"]), ("1", "3"))
        self.assertEqual(sorted(e["type"] for e in a["events"]), ["changed", "evidence-missing", "guard"])

    def test_no_change_yet_is_idle_with_the_draft_on_the_popup(self):
        a = only(L.build(summary(), now=NOW))
        self.assertEqual((a["label"]["text"], a["status"]["center"], a["rank"]), ("还没有改动", "idle", "none"))
        self.assertNotIn("pill", a)
        self.assertEqual(a["body"], [])

    def test_expanded_card_shows_your_words_the_reading_and_the_rows(self):
        # 分镜 ㊱（作者 09-21）：第一页 = 理由 · 原因 · 三行逐词；整句留面板。「你说」「Claude 读成」归许愿柳（#28）
        a = only(L.build(with_change(n=15, label="betaVal 说反"), now=NOW))
        self.assertEqual([b["title"] for b in a["body"]], ["改了"])
        items = a["body"][0]["items"]
        self.assertEqual((items[0]["text"], items[0]["tone"]), ("betaVal 说反", "white"))
        self.assertEqual(items[1]["text"], "追到你的话")
        self.assertEqual([i["kind"] for i in items[2:2 + 15]], ["diff"] * 15)   # 15 句全给：展开卡里滚动看（作者 09-21）
        self.assertEqual({k: items[2][k] for k in ("label", "old", "new")}, {"label": "X0", "old": "old 0", "new": "new 0"})   # 改写不写「改写」
        self.assertEqual(items[-1]["kind"], "diff")                                # 没超过上限就没有「还有 N 句」
        big = only(L.build(with_change(n=L.DIFF_ROWS + 5), now=NOW))["body"][0]["items"]
        self.assertEqual(sum(1 for i in big if i["kind"] == "diff"), L.DIFF_ROWS)
        self.assertIn("还有 5 句", big[-1]["text"])
        self.assertNotIn("badge", a["body"][0])
        # 没有 Claude 标签时理由行是「改了」；有几页画几页（分镜 ㉙）
        # 没有 Claude 标签：不画理由行（会和页标题「改了」重），第一条就是原因行
        self.assertEqual(only(L.build(with_change(label=None), now=NOW))["body"][0]["items"][0]["text"], "追到你的话")
        self.assertEqual([b["title"] for b in only(L.build(with_change(traced=False), now=NOW))["body"]], ["改了"])
        self.assertEqual([b["title"] for b in only(L.build(with_change(reading=None), now=NOW))["body"]], ["改了"])
        s = with_change(n=2, label="改"); s["latest_changeset"]["rows"][1]["kind"] = "added"; s["latest_changeset"]["rows"][1]["old"] = ""
        added = only(L.build(s, now=NOW))["body"][0]["items"][3]     # 理由行 + 原因行 + 两条 diff
        self.assertEqual((added["label"], added["new"]), ("X1 新增", "new 1")); self.assertNotIn("old", added)
        # 无出处两种的理由行
        e = only(L.build(with_change(traced=False), now=NOW))["body"][0]["items"]
        self.assertEqual((e[0]["text"], e[0]["tone"], e[1]["text"]), ("别处改了", "white55", "窗口里没有你的消息"))
        s = with_change(traced=False); s["latest_changeset"]["messages_in_window"] = 2
        u = only(L.build(s, now=NOW))["body"][0]["items"]
        self.assertEqual((u[0]["text"], u[0]["tone"], u[1]["text"]), ("改动无出处", "orange", "窗口里 2 条消息都对不上"))

    def test_rows_are_shown_as_the_reader_sees_them_not_as_latex(self):
        self.assertEqual(L.detex("from $12.5\\times$ baseline to $2.0\\times$, $3{,}210$ items, $41.7\\%$"),
                         "from 12.5× baseline to 2.0×, 3,210 items, 41.7%")
        s = with_change(n=1, label="改")
        s["latest_changeset"]["rows"][0]["new"] = "Score is $7$ of $9$"
        self.assertEqual(L.build(s, now=NOW)[0]["body"][0]["items"][2]["new"], "Score is 7 of 9")

    def test_the_flip_row_names_the_activity_not_a_missing_tag(self):
        # 耳朵与翻页行的第二格是改到的节（短名来自登记表 draft.sections[].short），不是提交号（作者 09-21）
        s = with_change(label="betaVal 说反"); s["section_names"] = {"X": "§3.2"}
        a = only(L.build(s, now=NOW))
        self.assertEqual(a["flip"], {"title": "betaVal 说反", "subtitle": "ws", "phase": "§3.2"})
        self.assertEqual((a["ears"]["phase"], a["ears"]["tag"]["text"]), ("§3.2", "15 句"))
        self.assertEqual(only(L.build(with_change(), now=NOW))["ears"]["phase"], "X")    # 没有短名就用前缀

    def test_panel_lists_every_changeset_newest_first_with_the_passive_note(self):
        s = with_change()
        s["history"] = [{"id": "b", "time": NOW, "n": 2, "traced": False, "verbatim": None, "status": "none"},
                        {"id": "a", "time": NOW - 9, "n": 15, "traced": True, "verbatim": "改 §3.2", "status": "one"}]
        a = only(L.build(s, now=NOW, notices=["拦下写入：2 次"]))
        d = a["detail"]
        # 分镜 ㉚：无出处折成一行（点开才摊），追到的一行 = 你说 + 句数徽章 + 行尾提交号
        self.assertEqual([h["id"] for h in d["history"]], ["fold-b", "a"])
        fold, one = d["history"]
        self.assertEqual((fold["tag"], fold["badge"], fold["lines"]), ("别处 ×1", "2 句", []))
        self.assertEqual([(r["label"], r["copy"]) for r in fold["rows"]], [("b", "b")])
        self.assertTrue(fold["rows"][0]["where"].startswith("2 句 · "))
        # 行头 = 为什么（Claude 标签）或改到的节，没有就「改了」；原话不再在面板里重复（作者 09-21）
        self.assertEqual((one["tag"], one["badge"], one["duration"], one["lines"]), ("改了", "15 句", "a", []))
        s["history"][1]["label"] = "betaVal 说反"
        s["history"][1]["rows"] = [{"label": "X6.2", "section": "X", "new": "a"}, {"label": "A03", "section": "A", "new": "b"}]
        s["section_names"] = {"X": "§3.2", "A": "摘要"}
        one = only(L.build(s, now=NOW))["detail"]["history"][1]
        self.assertEqual((one["tag"], one["lines"][0]["label"], one["lines"][0]["text"]), ("betaVal 说反", "改到", "§3.2 · 摘要"))
        s["history"][1]["label"] = None
        self.assertEqual(only(L.build(s, now=NOW))["detail"]["history"][1]["tag"], "§3.2 · 摘要")
        self.assertIn("拦下 1 次", d["historyNote"])
        # 进度按改动集（作者 09-21）：一格一个，旧 → 新；图表卡没有了；数据条只剩三格
        self.assertNotIn("chart", d)
        self.assertEqual(d["strip"]["cells"], [L.IDENTITY, L.UNTRACED])
        self.assertEqual([(k["name"], k["count"]) for k in d["strip"]["legend"]], [("追到", 1), ("对不上", 0), ("别处", 1)])
        self.assertEqual([c["label"] for c in d["stats"]], ["追到", "缺依据", "拦下"])   # 分镜 ⑥③ 的顺序
        self.assertEqual(d["listTitle"], "ws · 15 句 · 已追到")

    def test_consecutive_untraced_changesets_fold_in_groups_of_sixteen(self):
        s = with_change()
        s["history"] = [{"id": f"u{i:02d}", "time": NOW - i, "n": 1, "traced": False, "verbatim": None, "status": "none", "subject": f"s {i}"}
                        for i in range(20)]
        d = only(L.build(s, now=NOW))["detail"]
        self.assertEqual([(h["tag"], len(h["rows"])) for h in d["history"]], [("别处 ×16", 16), ("别处 ×4", 4)])
        self.assertEqual(d["history"][0]["rows"][0]["new"], "s 0")
        self.assertEqual(d["strip"]["cells"], [L.UNTRACED] * 20)

    def test_unmatched_and_elsewhere_fold_separately_and_colour_the_strip_differently(self):
        s = with_change()
        mk = lambda i, k: {"id": f"c{i}", "time": NOW - i, "n": 1, "traced": False, "verbatim": None, "status": "none", "subject": "x", "messages_in_window": k}
        s["history"] = [mk(0, 2), mk(1, 1), mk(2, 0), mk(3, 0), mk(4, 0), mk(5, 3)]   # newest first
        d = only(L.build(s, now=NOW))["detail"]
        self.assertEqual([(h["tag"], h["badge"]) for h in d["history"]], [("△ 对不上 ×2", "2 句"), ("别处 ×3", "3 句"), ("△ 对不上 ×1", "1 句")])
        self.assertEqual(d["strip"]["cells"], [L.UNMATCHED, L.UNTRACED, L.UNTRACED, L.UNTRACED, L.UNMATCHED, L.UNMATCHED])   # 旧 → 新
        self.assertEqual([(k["name"], k["count"]) for k in d["strip"]["legend"]], [("追到", 0), ("对不上", 3), ("别处", 3)])
        self.assertEqual(d["listTitle"], "ws · 15 句 · 已追到")

    def test_identity_is_the_registry_indigo(self):
        self.assertEqual(L.IDENTITY, "indigo")
        self.assertEqual(only(L.build(with_change(), now=NOW))["detail"]["dot"], "indigo")

    def test_labels_tags_and_pills_fit_the_notch(self):
        for s, problems in ((summary(), ()), (with_change(), ()), (with_change(traced=False), ()),
                            (with_change(label="betaVal 说反"), ()), (with_change(), ["x"])):
            a = only(L.build(s, now=NOW, problems=problems))
            self.assertLessEqual(L.width(a["label"]["text"]), 6, a["label"])
            self.assertLessEqual(L.width(a["ears"]["tag"]["text"]), 6, a["ears"])
            if "pill" in a:
                self.assertLessEqual(L.width(a["pill"]["title"]), 6, a["pill"])
            self.assertLessEqual(len(a["popup"]), 4)
            self.assertLessEqual(len(a["body"]), 8)

    def test_no_none_reaches_the_host(self):
        a = only(L.build(with_change(traced=False), now=NOW, notices=["x"]))
        self.assertNotIn("null", json.dumps(a))

    def test_revision_ignores_the_clock(self):
        a = only(L.build(with_change(), now=NOW))
        b = only(L.build(with_change(), now=NOW + 5000))
        self.assertNotEqual(a["updatedAt"], b["updatedAt"])
        self.assertEqual(a["revision"], b["revision"])

    def test_revision_changes_with_a_new_changeset(self):
        a = only(L.build(with_change(cid="c0ffee1"), now=NOW))
        b = only(L.build(with_change(cid="b123456"), now=NOW))
        self.assertNotEqual(a["revision"], b["revision"])
        self.assertNotEqual(a["events"][0]["id"], b["events"][0]["id"])


def turn(start, touches=(), ended=None, key="p1", chars=12, error=False):
    return {"start": start, "session": "s1", "key": key, "chars": chars, "touches": list(touches), "ended": ended,
            "error": error}


COV = {"rows": [{"id": "a", "name": "检查甲", "status": V.OK, "verdict": "findings", "result": "r"},
                {"id": "b", "name": "检查乙", "status": V.OK, "verdict": "ok", "result": "r"}]}


def risk(rid, gate, kind="风险"):
    return {"kind": kind, "id": rid, "title": f"合成标题 {rid}", "gate": gate, "source": "合成", "status": "未决"}


# NOW is 2026-09-18T02:53Z: the round starts the day before; the reader panel ran an hour before the change set (NOW - 60).
RING_COV = {"rows": [{"id": "readers", "name": "读者组", "status": V.OK, "last_at": L._iso(NOW - 3600)},
                     {"id": "a", "name": "检查甲", "status": V.OK, "verdict": "ok", "result": "r"}],
            "risks": {"open": [risk("A2", "作者写完意图卡；核对页"), risk("A1", "改稿核对页"), risk("A5", "G2")],
                      "decided": [dict(risk("B1", "改稿核对页"), decided_on="2026-09-17", decision="合成", uuid="bbbb2222" + "0" * 28)],
                      "below": [], "problems": []}}


class RingExportTest(unittest.TestCase):
    """The manuscript ring goes to the notch (plan step 4a): the words and states lintel draws, the pill says the draft
    and how many things wait on the author, and the ring stays after it is seen (spec V2)."""

    def build(self, s=None, **kw):
        return only(L.build(s or with_change(), now=NOW, coverage=RING_COV, turn=turn(NOW - 7200, ended=NOW - 7000), **kw))

    def test_seven_stages_with_states_sight_and_the_words_in_each_box(self):
        r = self.build()["ring"]
        self.assertEqual([x["key"] for x in r["segments"]], ["comment", "design", "rewrite", "check", "readers", "review", "land"])
        seg = {x["key"]: x for x in r["segments"]}
        self.assertEqual((seg["design"]["state"], seg["design"]["note"], seg["design"]["sight"]), ("waiting", "等你 1", "inferred"))
        self.assertEqual((seg["review"]["state"], seg["review"]["note"]), ("waiting", "等你 1"))
        self.assertEqual((seg["readers"]["state"], seg["readers"]["note"]), ("stale", "过期"), "the panel ran before the change")
        self.assertEqual((seg["land"]["state"], seg["land"]["sight"], seg["land"]["sightNote"]), ("unseen", "commits", "只有提交"))
        self.assertEqual(seg["design"]["items"][0], {"id": "A2", "text": "风险 A2 合成标题 A2", "you": True})
        self.assertEqual(seg["readers"]["items"][0]["you"], False)
        self.assertEqual(r["current"], "design")
        self.assertEqual([x["id"] for x in r["unhung"]], ["A5"])
        self.assertEqual((r["waiting"], r["closed"]), (3, [{"date": "2026-09-17", "items": ["B1（bbbb2222）"]}]))
        self.assertIn("2026-09-17", r["since"])
        self.assertEqual(set(r["labels"]), {"title", "current", "latest", "unhung", "closed", "waiting"})

    def test_the_latest_move_is_the_change_or_the_message_whichever_came_last(self):
        r = self.build()["ring"]
        self.assertEqual(r["latest"], "rewrite", "the change set (NOW - 60) is after the message (NOW - 7200)")
        self.assertEqual(r["latestAt"], L._iso(NOW - 60))

    def test_the_pill_says_the_draft_and_what_waits_on_you_and_stays_after_seen(self):
        a = self.build()
        self.assertEqual(a["pill"]["title"], "ws · 等你 3")
        self.assertFalse(a["pillUntilSeen"])
        self.assertNotIn("pillSeen", a)
        self.assertLessEqual(L.width(a["pill"]["title"]), L.RING_PILL_MAX)
        long = only(L.build(summary(name="a-rather-long-draft-name"), now=NOW, coverage=RING_COV))
        self.assertLessEqual(L.width(long["pill"]["title"]), L.RING_PILL_MAX, long["pill"])
        self.assertTrue(long["pill"]["title"].endswith("· 等你 3"), "the name is cut, the count never is")

    def test_alerts_keep_their_own_pill(self):
        s = with_change(traced=False); s["latest_changeset"]["messages_in_window"] = 3
        self.assertEqual(self.build(s)["pill"]["title"], "15 △")
        self.assertEqual(self.build(problems=["索引：读不出"])["pill"]["title"], "1 ⚠")
        running = only(L.build(with_change(), now=NOW, coverage=RING_COV, turn=turn(NOW - 100, touches=[(NOW - 80, "draft")])))
        self.assertIn("clockSince", running["pill"])

    def test_no_coverage_no_ring_and_a_ring_that_cannot_be_computed_says_so(self):
        self.assertNotIn("ring", only(L.build(with_change(), now=NOW)))
        self.assertNotIn("ring", only(L.build(with_change(), now=NOW, coverage=None)))
        bad = only(L.build(with_change(), now=NOW, coverage={"rows": 5}))["ring"]
        self.assertEqual(bad["segments"], [])
        self.assertIn("算不出", bad["error"])


class NestedInConversationTest(unittest.TestCase):
    """The draft is nested in the conversations editing it (the author 09-24: the loop and wishing-willow looked like two
    parallel apps): the activity names the wishing-willow sessions from the note the hook keeps for willow, the primary
    ones first. lintel draws the draft inside an open one and alone when none is open."""

    NOTE = {"sessions": {"s-old": {"role": "history", "since": "p0"}, "s-main": {"role": "primary", "since": "p1"},
                         "s-main2": {"role": "primary", "since": "p2"}}}

    def test_the_sessions_of_the_note_primary_first(self):
        a = only(L.build(with_change(), now=NOW, note=self.NOTE))
        self.assertEqual(a["within"], [{"producer": "willow", "id": "s-main", "role": "primary"},
                                       {"producer": "willow", "id": "s-main2", "role": "primary"},
                                       {"producer": "willow", "id": "s-old", "role": "history"}])

    def test_no_note_or_a_bad_one_names_no_conversation(self):
        # a role lintel does not know would get the whole activity rejected (the draft gone from the notch): dropped here
        for note in (None, {}, {"sessions": []}, {"sessions": {"s": "primary"}}, "x",
                     {"sessions": {"s": {"role": "owner"}}}, {"sessions": {"s": {"since": "p1"}}}):
            self.assertNotIn("within", only(L.build(with_change(), now=NOW, note=note)), note)

    def test_at_most_sixteen_the_primary_ones_kept(self):
        many = {"sessions": {**{f"h{i}": {"role": "history"} for i in range(20)}, "p": {"role": "primary"}}}
        w = only(L.build(with_change(), now=NOW, note=many))["within"]
        self.assertEqual(len(w), 16)
        self.assertEqual(w[0]["id"], "p")


class TurnStateTest(unittest.TestCase):
    """设计 B3 与作者 09-22 的裁定：开工每条都弹、在跑按 ② 口径、落地弹两行、看过后胶囊留括号加几时前。"""

    def test_every_message_starts_with_a_two_line_card(self):
        a = only(L.build(with_change(), now=NOW, turn=turn(NOW - 3, chars=44), coverage=COV))
        self.assertEqual(a["label"]["text"], "开工")
        self.assertEqual([e["type"] for e in a["events"]], ["started"])
        self.assertEqual([p["label"] for p in a["popup"]], ["收到", "稿子"])
        self.assertIn("44 字", a["popup"][0]["text"])
        self.assertEqual(a["popup"][1]["text"], "82 句 · 缺依据 0 · 有发现 1")
        self.assertEqual(a["status"]["clock"]["style"], "live")
        self.assertEqual(a["rank"], "event")
        # 另一条消息是另一件事；过了 START_FRESH 就回到改动集
        other = only(L.build(with_change(), now=NOW, turn=turn(NOW - 3, key="p2")))
        self.assertNotEqual(a["revision"], other["revision"])
        later = only(L.build(with_change(), now=NOW + L.START_FRESH, turn=turn(NOW - 3)))
        self.assertEqual([e["type"] for e in later["events"]], ["changed"])

    def test_a_start_beats_an_old_drift_so_every_message_pops(self):
        s = with_change(traced=False); s["latest_changeset"]["messages_in_window"] = 3
        a = only(L.build(s, now=NOW, turn=turn(NOW - 2)))
        self.assertEqual(a["label"]["text"], "开工")

    def test_running_names_the_action_ticks_from_the_first_touch_and_does_not_pop(self):
        tr = turn(NOW - 100, touches=[(NOW - 80, "draft"), (NOW - 10, "head")])
        a = only(L.build(with_change(), now=NOW, turn=tr))
        self.assertEqual(a["label"]["text"], "提交")
        self.assertTrue(a["running"] and a["inProgress"])
        self.assertEqual(a["status"]["clock"], {"style": "live", "since": L._iso(NOW - 80)})
        self.assertEqual(a["pill"]["clockSince"], L._iso(NOW - 80))
        self.assertFalse(a["labelUntilSeen"] or a["pillUntilSeen"])
        self.assertNotIn("pillSeen", a)
        self.assertEqual([e["type"] for e in a["events"]], [])
        # 动作变了不是另一件事：看过之后不重亮
        b = only(L.build(with_change(), now=NOW, turn=turn(NOW - 100, touches=[(NOW - 80, "draft")])))
        self.assertEqual(a["revision"], b["revision"])
        self.assertEqual(b["label"]["text"], "改正文")

    def test_an_old_drift_does_not_beat_running_but_a_drift_in_this_turn_does(self):
        s = with_change(traced=False); s["latest_changeset"]["messages_in_window"] = 3
        old = turn(NOW - 50, touches=[(NOW - 20, "draft")])            # the drift (NOW - 60) is before this turn
        self.assertEqual(only(L.build(s, now=NOW, turn=old))["label"]["text"], "改正文")
        this = turn(NOW - 90, touches=[(NOW - 80, "draft")])           # the drift is inside this turn
        self.assertEqual(only(L.build(s, now=NOW, turn=this))["label"]["text"], "改动无出处")

    def test_landing_pops_two_lines_once_the_index_has_caught_up(self):
        s = with_change(); s["latest_changeset"]["strength"] = "session"
        tr = turn(NOW - 120, touches=[(NOW - 90, "draft"), (NOW - 60, "head")], ended=NOW - 30)
        a = only(L.build(s, now=NOW, turn=tr, built_at=NOW - 20, coverage=COV))
        self.assertEqual([e["type"] for e in a["events"]], ["changed", "landed"])
        self.assertEqual([p["label"] for p in a["popup"]], ["改了", "检查"])
        self.assertEqual(a["popup"][0]["text"], "X0、X1、X2 等 15 句 · ○ 按会话")   # the count once, not twice
        self.assertEqual(a["popup"][1]["text"], "有发现 1：检查甲")
        landed_at = next(e["at"] for e in a["events"] if e["type"] == "landed")
        self.assertEqual(landed_at, L._iso(NOW - 30))
        # 索引还是这一轮结束之前建的：不弹
        b = only(L.build(s, now=NOW, turn=tr, built_at=NOW - 40))
        self.assertEqual([e["type"] for e in b["events"]], ["changed"])
        # 改动集不在这一轮里：不弹
        c = only(L.build(s, now=NOW, turn=turn(NOW - 50, ended=NOW - 30), built_at=NOW - 20))
        self.assertEqual([e["type"] for e in c["events"]], ["changed"])

    def test_a_turn_an_api_error_ended_is_over_but_does_not_land(self):
        s = with_change()
        tr = turn(NOW - 120, touches=[(NOW - 90, "draft")], ended=NOW - 30, error=True)
        a = only(L.build(s, now=NOW, turn=tr, built_at=NOW - 20, coverage=COV))
        self.assertFalse(a["running"])
        self.assertEqual([e["type"] for e in a["events"]], ["changed"])
        rd = {"t": NOW - 35, "summary": "M1.recall 7/9", "verdict": "findings"}
        self.assertEqual(only(L.build(s, now=NOW, turn=turn(NOW - 50, ended=NOW - 30, error=True), readers=rd,
                                      built_at=NOW - 20))["label"]["text"], "改了")

    def test_a_turn_that_only_ran_the_readers_lands_with_the_weakest_item(self):
        tr = turn(NOW - 50, ended=NOW - 30)
        rd = {"t": NOW - 35, "summary": "M1.recall 7/9，M2.recall 4/9", "verdict": "findings"}
        a = only(L.build(with_change(), now=NOW, turn=tr, readers=rd, built_at=NOW - 20))
        self.assertEqual(a["label"]["text"], "读者组")
        self.assertEqual([(p["label"], p["text"]) for p in a["popup"]], [("读者", "最弱 M2 4/9"), ("改了", "无")])
        self.assertEqual([e["type"] for e in a["events"]], ["landed"])
        self.assertEqual(only(L.build(with_change(), now=NOW + L.LANDED_HOLD, turn=tr, readers=rd,
                                      built_at=NOW - 20))["label"]["text"], "改了")

    def test_after_it_is_seen_the_capsule_keeps_the_bracket_and_how_long_ago(self):
        a = only(L.build(with_change(), now=NOW))
        self.assertTrue(a["pillUntilSeen"])
        self.assertEqual(a["pillSeen"], {"pulse": False, "agoSince": L._iso(NOW - 60)})
        self.assertNotIn("pillSeen", only(L.build(summary(), now=NOW)))           # no capsule, nothing to keep
        self.assertNotIn("pillSeen", only(L.build(with_change(), now=NOW, problems=["x"])))


class PanelGapsTest(unittest.TestCase):
    """功能对照表的缺口 1–8（lintel docs/design/2026-09-22-awt-backend-frontend-map.md，分镜 ⑥③–⑥⑤）。"""

    def cells(self, **kw):
        return {c["label"]: c for c in only(L.build(with_change(), now=NOW, **kw))["detail"]["stats"]}

    def test_refused_writes_are_counted_as_writes_not_notice_lines(self):
        # 缺口 4：提醒只有一行，但被拦下了 6 次
        denials = [{"at": f"2026-01-02T03:0{i}:00Z", "detail": f"Write → human/x{i}"} for i in range(6)]
        c = self.cells(notices=["拦下写入：共 6 次"], denials=denials)["拦下"]
        self.assertEqual((c["value"], c["tone"]), ("6", "orange"))
        self.assertIn("human/x5", c["hint"])
        self.assertEqual(self.cells()["拦下"], {"label": "拦下", "value": "0"})

    def test_checks_that_found_something_are_on_the_strip_with_their_names_in_the_hint(self):
        c = self.cells(coverage=COV)["有发现"]
        self.assertEqual((c["value"], c["tone"]), ("1", "orange"))
        self.assertIn("检查甲", c["hint"])

    def test_the_weakest_reader_item_has_a_cell_and_every_item_in_the_hint(self):
        rd = {"t": NOW, "summary": "M1.recall 7/9，M2.recall 4/9", "verdict": "findings"}
        c = self.cells(readers=rd)["读者·最弱"]
        self.assertEqual(c["value"], "4/9")
        self.assertIn("M1 7/9 · M2 4/9", c["hint"])

    def test_a_gate_override_shows_and_nothing_shows_when_there_is_none(self):
        self.assertNotIn("门放行", self.cells())
        c = self.cells(overrides=[{"at": "2026-01-02T03:04:05Z", "detail": "2 句标出未处理"}])["门放行"]
        self.assertEqual((c["value"], c["tone"]), ("1", "orange"))

    def test_undecided_risks_get_their_own_cell_once_coverage_can_list_them(self):
        # 风险台账（spec 2026-09-22-risk-register，coverage.pending 由它提供）：还没有这个函数时不画这一格
        from unittest import mock
        with mock.patch.object(V, "pending", lambda s: [{"name": "风险甲"}, {"name": "门乙"}], create=True):
            c = self.cells(coverage=COV)["未决"]
        self.assertEqual((c["value"], c["tone"], c["hint"]), ("2", "orange", "风险甲；门乙"))
        if not hasattr(V, "pending"):
            self.assertNotIn("未决", self.cells(coverage=COV))

    def test_more_than_eight_cells_move_the_least_needed_into_the_first_hint(self):
        ov = {"stats": [{"label": "句", "value": "82"}, {"label": "版", "value": "15"}, {"label": "改动集 · 这一段", "value": "3"},
                        {"label": "缺依据", "value": "2", "tone": "orange"}, {"label": "标题页待填", "value": "4", "tone": "orange"},
                        {"label": "构建落后", "value": "10", "tone": "orange"}]}
        cells = only(L.build(with_change(), now=NOW, overview=ov, coverage=COV, denials=[{"at": "t", "detail": "d"}],
                             overrides=[{"at": "t", "detail": "d"}],
                             readers={"t": NOW, "summary": "M1.recall 7/9"}))["detail"]["stats"]
        labels = [c["label"] for c in cells]
        self.assertEqual(len(cells), 8)
        self.assertEqual(labels, ["句", "缺依据", "有发现", "门放行", "拦下", "读者·最弱", "构建落后", "标题页待填"])
        self.assertIn("另有 版 15", cells[0]["hint"])

    def test_the_stage_count_is_in_the_hint_of_versions(self):
        ov = {"stats": [{"label": "句", "value": "82"}, {"label": "版", "value": "15"}, {"label": "改动集 · 这一段", "value": "3"}]}
        cells = {c["label"]: c for c in only(L.build(with_change(), now=NOW, overview=ov))["detail"]["stats"]}
        self.assertNotIn("改动集 · 这一段", cells)
        self.assertEqual(cells["版"]["hint"], "改动集 · 这一段 3")

    def test_a_folded_unmatched_group_opens_to_its_sentences(self):
        # 缺口 2：先前每个改动集只有一行（提交号、句数与时刻、提交说明）
        s = with_change(traced=False)
        h = dict(s["history"][0], rows=[{"label": "A1", "old": "o", "new": "n"}], subject="s")
        s["history"] = [h, dict(h, id="d00d1e2")]
        fold = only(L.build(s, now=NOW))["detail"]["history"][0]
        self.assertEqual([r["label"] for r in fold["rows"]], ["A1", "A1"])
        self.assertTrue(fold["rows"][0]["where"].startswith("c0ffee1"))
        self.assertEqual(fold["rows"][0]["new"], "n")

    def test_more_than_sixteen_sentences_says_how_many_are_not_listed(self):
        # 缺口 7
        s = with_change(n=20)
        s["history"][0]["rows"] = [{"label": f"X{i}", "old": "o", "new": "n"} for i in range(16)]
        row = only(L.build(s, now=NOW))["detail"]["history"][0]
        self.assertIn({"label": "还有", "text": "4 句没列出", "tone": "white55"}, row["lines"])

    def test_the_basis_claude_wrote_and_how_firmly_it_was_traced_reach_the_card(self):
        # 缺口 5、3
        s = with_change(); s["latest_changeset"]["basis"] = "作者那条 · 台账第 3 行"; s["latest_changeset"]["strength"] = "session"
        a = only(L.build(s, now=NOW))
        pages = {p["title"]: p for p in a["body"]}
        self.assertEqual(pages["依据"]["items"][0]["text"], "作者那条 · 台账第 3 行")
        self.assertIn("追到你的话 · ○ 按会话", [i.get("text") for i in pages["改了"]["items"]])


class IdentityTest(unittest.TestCase):
    """revision 是刘海上这件事的身份（设计 2026-09-22-awt-live M2）：宿主按它记看过，所以面板、标签、提交号都不进来。
    09-22 同一个改动集因为面板里的检查数变了，一天重新亮了四次。"""

    def test_the_panel_and_a_late_label_do_not_make_it_new(self):
        a = only(L.build(with_change(label="换例子"), now=NOW))
        b = only(L.build(with_change(label="拆长句"), now=NOW + 30, notices=["拦下写入：2 次"]))
        self.assertNotEqual(L.content_hash(a), L.content_hash(b))
        self.assertEqual(a["revision"], b["revision"])

    def test_a_new_changeset_or_a_new_kind_is_new(self):
        a = only(L.build(with_change(cid="c0ffee1"), now=NOW))
        self.assertNotEqual(a["revision"], only(L.build(with_change(cid="b123456"), now=NOW))["revision"])
        self.assertNotEqual(a["revision"], only(L.build(with_change(traced=False), now=NOW))["revision"])

    def test_no_change_yet_stays_the_same_thing_across_commits(self):
        a = only(L.build(summary(head="aaaaaaa"), now=NOW))
        b = only(L.build(summary(head="bbbbbbb"), now=NOW))
        self.assertEqual(a["revision"], b["revision"])

    def test_the_time_is_when_it_happened(self):
        a = only(L.build(with_change(), now=NOW + 5000))
        self.assertEqual(a["activityAt"], L._iso(NOW - 60))
        self.assertEqual(a["status"]["clock"], {"style": "ago", "since": L._iso(NOW - 60)})
        self.assertEqual(a["events"][0]["at"], L._iso(NOW - 60))
        idle = only(L.build(summary(), now=NOW))
        self.assertNotIn("activityAt", idle)
        self.assertNotIn("clock", idle["status"])
        broken = only(L.build(with_change(), now=NOW, problems=["索引：读不出"]))
        self.assertNotIn("clock", broken["status"])


class LocateRowsTest(unittest.TestCase):
    """候选 A（作者 09-21 定甲+乙）：面板里点开一条改动集，看到改的是哪句、在哪、拿去贴的定位、改前改后。"""

    def history_with_rows(self, rows, names=None):
        lc = change()
        return summary(latest_changeset=lc, section_names=names or {},
                       history=[{"id": lc["id"], "time": lc["time"], "n": lc["n"], "traced": True,
                                 "verbatim": lc["verbatim"], "status": "one", "rows": rows}])

    def test_rows_carry_where_copy_and_both_texts(self):
        s = self.history_with_rows([{"label": "X6.2", "section": "X", "par": 6, "path": "sections/results.tex", "line": 42,
                                     "old": "Three $x$ models", "new": "Three newer models were added to the same pool"}],
                                   names={"X": "Controls"})
        row = only(L.build(s, now=NOW))["detail"]["history"][0]["rows"][0]
        self.assertEqual(row["where"], "Controls · 第 6 段 · sections/results.tex:42")
        self.assertEqual(row["copy"], "sections/results.tex:42 · X6.2 · “Three newer models were added to…”")
        self.assertEqual(row["old"], "Three x models")
        self.assertEqual(row["new"], "Three newer models were added to the same pool")

    def test_missing_location_leaves_where_short_and_copy_without_a_line(self):
        s = self.history_with_rows([{"label": "A03", "section": "A", "par": None, "path": None, "line": None, "old": None, "new": "New abstract sentence."}])
        row = only(L.build(s, now=NOW))["detail"]["history"][0]["rows"][0]
        self.assertEqual(row["where"], "A")
        self.assertEqual(row["copy"], "A03 · “New abstract sentence.…”")
        self.assertNotIn("old", row)

    def test_a_history_entry_without_rows_has_no_rows_key(self):
        a = only(L.build(with_change(), now=NOW))
        self.assertNotIn("rows", a["detail"]["history"][0])

    def test_at_most_sixteen_rows_reach_the_host(self):
        rows = [{"label": f"X{i}", "new": f"s {i}"} for i in range(30)]
        self.assertEqual(len(only(L.build(self.history_with_rows(rows), now=NOW))["detail"]["history"][0]["rows"]), 16)


class SummaryViewTest(unittest.TestCase):
    """index.changeset_view: the notch's data is read from the index, never guessed."""

    def test_traced_changeset_carries_the_message_and_the_explanation(self):
        cs = {"id": "c1", "subject": "s", "time": 1, "status": "one", "triggers": ["h-1"],
              "rows": [{"kind": "edited", "old": {"label": "A1", "text": "o"}, "new": {"label": "A1", "text": "n"}},
                       {"kind": "merge", "old": [{"label": "A2", "text": "x"}, {"label": "A3", "text": "y"}], "new": {"label": "A2", "text": "xy"}}]}
        threads = [{"mid": "h-1", "text": "改 A1"}]
        expl = [{"mid": "h-1", "reading": "只改 A1", "changed": "A1", "basis": "你说", "label": "只改A1"}]
        v = X.changeset_view(cs, threads, expl)
        self.assertEqual((v["traced"], v["verbatim"], v["reading"], v["label"], v["n"]), (True, "改 A1", "只改 A1", "只改A1", 2))
        self.assertEqual(v["rows"][1], {"kind": "merge", "label": "A2", "old": "x / y", "new": "xy"})

    def test_untraced_changeset_guesses_nothing(self):
        cs = {"id": "c2", "subject": "s", "time": 1, "status": "none", "triggers": [], "rows": []}
        v = X.changeset_view(cs, [{"mid": "h-1", "text": "改 A1"}], [{"mid": "h-1", "reading": "r", "changed": None, "basis": None}])
        self.assertEqual((v["traced"], v["mid"], v["verbatim"], v["reading"]), (False, None, None, None))

    def test_how_firmly_it_was_traced_is_carried_to_the_notch(self):
        # 缺口 3（分镜 ⑥①）：只靠「提交时的会话」追到的是空心，句子一级的来源是实心
        def cs(*sources):
            return {"id": "c1", "subject": "s", "time": 1, "status": "one", "triggers": ["h-1"],
                    "rows": [{"kind": "edited", "old": {"label": "A1", "text": "o"}, "new": {"label": "A1", "text": "n"},
                              "trigger": {"source": s, "mid": "h-1"}} for s in sources]}
        view = lambda c: X.changeset_view(c, [{"mid": "h-1", "text": "t"}], [])["strength"]
        self.assertEqual(view(cs("提交时的会话")), "session")
        self.assertEqual(view(cs("提交时的会话", "脚本推断")), "sentence")
        self.assertEqual(view(cs("提交信息")), "sentence")
        self.assertIsNone(view(cs()))

    def test_old_explanations_without_a_label_field_still_load(self):
        cs = {"id": "c1", "subject": "s", "time": 1, "status": "one", "triggers": ["h-1"], "rows": []}
        v = X.changeset_view(cs, [{"mid": "h-1", "text": "t"}], [{"mid": "h-1", "reading": "r", "changed": None, "basis": None}])
        self.assertIsNone(v["label"])


def register(home, producer=L.PRODUCER):
    """What `lintel register` leaves behind, reduced to the part the producer reads."""
    Path(home).mkdir(parents=True, exist_ok=True)
    (Path(home) / "registry.json").write_text(json.dumps({"schema": 1, "producers": {producer: {"name": "t"}}}), encoding="utf-8")


class SyncTest(unittest.TestCase):
    def dir(self, home):
        return Path(home) / "producers" / L.PRODUCER / "activities"

    def setUp(self):
        self._t = TempDir()
        self.root = self._t.__enter__()
        register(self.root)

    def tearDown(self):
        self._t.__exit__(None, None, None)

    def test_unchanged_content_is_not_rewritten(self):
        root = self.root
        acts = L.build(summary(), now=NOW)
        self.assertEqual(L.sync(acts, home=root, now=NOW)["written"], 1)
        # 修改时间按测试的钟来设，否则「旧到该续心跳了」取决于真实墙上时间。
        os.utime(self.dir(root) / "loop-ws.json", (NOW, NOW))
        again = L.build(summary(), now=NOW + 5)
        self.assertEqual(L.sync(again, home=root, now=NOW + 5),
                         {"written": 0, "touched": 0, "unchanged": 1, "removed": 0})

    def test_a_panel_change_is_written_though_the_thing_is_the_same(self):
        root = self.root
        L.sync(L.build(with_change(), now=NOW), home=root, now=NOW)
        os.utime(self.dir(root) / "loop-ws.json", (NOW, NOW))
        again = L.build(with_change(), now=NOW + 5, coverage=None)   # 只有面板的数字条变了，事件一样
        self.assertEqual([e["id"] for e in again[0]["events"]],
                         [e["id"] for e in L.build(with_change(), now=NOW)[0]["events"]])
        self.assertEqual(L.sync(again, home=root, now=NOW + 5)["written"], 1)
        on_disk = json.loads((self.dir(root) / "loop-ws.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["detail"], again[0]["detail"])

    def test_an_event_alone_is_written(self):
        root = self.root
        acts = L.build(summary(), now=NOW)
        L.sync(acts, home=root, now=NOW)
        os.utime(self.dir(root) / "loop-ws.json", (NOW, NOW))
        acts[0]["events"] = acts[0].get("events", []) + [{"id": "guard:x", "type": "guard", "at": L._iso(NOW)}]
        self.assertEqual(L.sync(acts, home=root, now=NOW + 5)["written"], 1)

    def test_heartbeat_rewrites_the_same_bytes_so_seen_is_not_reset(self):
        root = self.root
        L.sync(L.build(summary(), now=NOW), home=root, now=NOW)
        p = self.dir(root) / "loop-ws.json"
        before = p.read_bytes()
        os.utime(p, (NOW - 600, NOW - 600))
        counts = L.sync(L.build(summary(), now=NOW + 600), home=root, now=NOW + 600)
        self.assertEqual(counts["touched"], 1)
        self.assertEqual(p.read_bytes(), before)

    def test_a_card_from_the_old_six_card_producer_is_removed_but_another_manuscript_is_not(self):
        root = self.root
        L.sync(L.build(summary(), now=NOW), home=root, now=NOW)
        L.sync(L.build(summary(name="other"), now=NOW), home=root, now=NOW)
        stray = self.dir(root) / "triggers.json"
        stray.write_text("{}", encoding="utf-8")
        counts = L.sync(L.build(summary(), now=NOW + 1), home=root, now=NOW + 1)
        self.assertEqual(counts["removed"], 1)
        self.assertFalse(stray.exists())
        self.assertEqual(sorted(p.name for p in self.dir(root).glob("*.json")), ["loop-other.json", "loop-ws.json"])

    def test_written_file_is_valid_json_with_the_protocol_keys(self):
        root = self.root
        L.sync(L.build(with_change(), now=NOW), home=root, now=NOW)
        a = json.loads((self.dir(root) / "loop-ws.json").read_text(encoding="utf-8"))
        for k in ("schema", "id", "open", "running", "inProgress", "stale", "flagged",
                  "rank", "labelUntilSeen", "pillUntilSeen", "popup", "body", "events", "detail"):
            self.assertIn(k, a)
        self.assertEqual(a["id"], "loop-ws")


class OffByDefaultTest(unittest.TestCase):
    """Spec v2 D5: the producer stays off until lintel has registered it, and then creates nothing."""

    def test_unregistered_producer_writes_nothing_and_creates_no_directory(self):
        with TempDir() as root:
            home = root / "lintel-home"
            with self.assertRaises(L.NotRegistered):
                L.sync(L.build(summary(), now=NOW), home=home, now=NOW)
            self.assertFalse(home.exists())

    def test_another_producer_being_registered_is_not_enough(self):
        with TempDir() as root:
            register(root, producer="someone-else")
            with self.assertRaises(L.NotRegistered):
                L.sync(L.build(summary(), now=NOW), home=root, now=NOW)
            self.assertFalse((root / "producers").exists())

    def test_malformed_registry_counts_as_unregistered(self):
        for raw in ("{not json", json.dumps({"producers": [L.PRODUCER]}), json.dumps([L.PRODUCER]), ""):
            with self.subTest(raw=raw), TempDir() as root:
                (root / "registry.json").write_text(raw, encoding="utf-8")
                with self.assertRaises(L.NotRegistered):
                    L.sync(L.build(summary(), now=NOW), home=root, now=NOW)
                self.assertFalse((root / "producers").exists())


class CliOffByDefaultTest(unittest.TestCase):
    def test_cli_refuses_with_exit_2_and_creates_nothing(self):
        from loop.cli import main
        from test_doctor import DoctorTest
        with TempDir() as root:
            ws = DoctorTest.setup_ws(None, root)
            home = root / "lintel-home"
            self.assertEqual(main(["update", str(ws)]), 0)
            self.assertEqual(main(["lintel", str(ws), "--once", "--home", str(home)]), 2)
            self.assertFalse(home.exists())
            register(home)
            self.assertEqual(main(["lintel", str(ws), "--once", "--home", str(home)]), 0)
            self.assertEqual(len(list((home / "producers" / L.PRODUCER / "activities").glob("loop-*.json"))), 1)


class ResidentTest(unittest.TestCase):
    def test_the_resident_producer_reads_the_index_and_does_not_rebuild_it(self):
        from loop.cli import main
        from test_doctor import DoctorTest
        with TempDir() as root:
            ws = DoctorTest.setup_ws(None, root)
            home = root / "lintel-home"
            register(home)
            self.assertEqual(main(["update", str(ws)]), 0)
            before = {p.name: p.stat().st_mtime_ns for p in (ws / "index").glob("*.json")}
            self.assertEqual(main(["lintel", str(ws), "--once", "--home", str(home)]), 0)
            self.assertEqual({p.name: p.stat().st_mtime_ns for p in (ws / "index").glob("*.json")}, before)

    def test_a_pid_that_is_not_a_producer_does_not_count_as_one(self):
        from loop.cli import _producer_alive
        with TempDir() as root:
            pf = root / "lintel.pid"
            self.assertFalse(_producer_alive(pf))
            pf.write_text(str(os.getpid()))
            self.assertFalse(_producer_alive(pf))
            pf.write_text("not a pid")
            self.assertFalse(_producer_alive(pf))


if __name__ == "__main__":
    unittest.main()


class NoPagingTest(unittest.TestCase):
    def test_the_loop_activity_is_not_paged_any_more(self):
        # 09-21 晚：悬停点点翻页奇怪 → 不分页，三节竖排，靠滚动
        self.assertNotIn("paged", only(L.build(with_change(), now=NOW)))

