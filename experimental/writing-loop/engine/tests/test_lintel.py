import json
import os
import unittest
from pathlib import Path

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


def change(n=15, traced=True, label=None, reading="改正 §5.5 那几句", verbatim="改 §5.5 那句 colSmol", cid="a066846"):
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
        self.assertEqual(only(L.build(summary(name="IPM"), now=NOW))["id"], "loop-IPM")
        self.assertEqual(L.activity_id("framework v9 / 2026"), "loop-framework-v9-2026")

    def test_the_wing_is_the_reason_claude_wrote_else_the_count(self):
        # channel-separation §5（作者 09-21）：字里不再有数，数在 label.count
        a = only(L.build(with_change(label="colSmol 说反"), now=NOW))
        self.assertEqual((a["label"]["text"], a["label"]["count"]), ("colSmol 说反", 15))
        b = only(L.build(with_change(label=None), now=NOW))
        self.assertEqual((b["label"]["text"], b["label"]["count"]), ("改了", 15))
        self.assertNotIn("15", b["label"]["text"])
        # a reason longer than the wing is cut, not dropped
        long = only(L.build(with_change(label="这一句说反了要改回来"), now=NOW))["label"]["text"]
        self.assertLessEqual(L.width(long), L.LABEL_MAX)
        self.assertTrue(long.endswith("…"))
        # width, not code points: seven Latin letters and two characters fit; ten characters do not
        self.assertEqual(L.width("colSmol 说反"), 6)

    def test_a_traced_change_is_active_not_attention(self):
        a = only(L.build(with_change(), now=NOW))
        self.assertFalse(a["flagged"])
        self.assertEqual(a["rank"], "event")
        self.assertEqual([e["type"] for e in a["events"]], ["changed"])
        self.assertEqual([p["label"] for p in a["popup"]], ["你说", "改了", "读成"])
        self.assertEqual(a["popup"][0]["text"], "改 §5.5 那句 colSmol")
        self.assertEqual(a["pill"]["title"], "15")

    def test_an_untraced_change_is_time_sensitive(self):
        a = only(L.build(with_change(traced=False), now=NOW))
        self.assertEqual(a["label"]["text"], "改动无出处")
        self.assertTrue(a["flagged"])
        self.assertEqual(a["status"]["center"], "flagged")
        self.assertEqual([e["type"] for e in a["events"]], ["drift"])
        # 弹出两行：改了哪几句、为什么追不到；没有「追不到你哪句话」「没有写读成」这种否定句（分镜 ㉗）
        self.assertEqual([p["label"] for p in a["popup"]], ["改了", "无出处"])
        self.assertEqual(a["popup"][1]["text"], "窗口里没有你的消息")
        self.assertEqual((a["label"]["count"], a["pill"]["title"]), (15, "15 △"))   # 胶囊保留 △（作者 09-21）
        s = with_change(traced=False); s["latest_changeset"]["messages_in_window"] = 3
        self.assertEqual(only(L.build(s, now=NOW))["popup"][1]["text"], "窗口里 3 条消息都对不上")

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
        a = only(L.build(with_change(n=15), now=NOW))
        self.assertEqual([b["title"] for b in a["body"]], ["你说", "Claude 读成", "改了"])   # 页标题不带数（数在耳朵）
        rows = a["body"][2]["items"]
        self.assertEqual(len(rows), L.ROWS_SHOWN + 1)
        self.assertIn(f"还有 {15 - L.ROWS_SHOWN} 句", rows[-1]["text"])
        self.assertNotIn("badge", a["body"][2])
        self.assertEqual(rows[0]["text"], "X0  new 0")                       # 改写不写「改写」
        # 有几页画几页（分镜 ㉙）：无出处只有「改了」；没有读法就没有「Claude 读成」
        self.assertEqual([b["title"] for b in only(L.build(with_change(traced=False), now=NOW))["body"]], ["改了"])
        self.assertEqual([b["title"] for b in only(L.build(with_change(reading=None), now=NOW))["body"]], ["你说", "改了"])
        s = with_change(n=2); s["latest_changeset"]["rows"][1]["kind"] = "added"
        self.assertEqual(only(L.build(s, now=NOW))["body"][2]["items"][1]["text"], "X1 新增  new 1")

    def test_rows_are_shown_as_the_reader_sees_them_not_as_latex(self):
        self.assertEqual(L.detex("from $48.4\\times$ chance to $1.6\\times$, $1{,}632$ plates, $23.5\\%$"),
                         "from 48.4× chance to 1.6×, 1,632 plates, 23.5%")
        s = with_change(n=1)
        s["latest_changeset"]["rows"][0]["new"] = "Recall@10 is $17$ of $18$"
        self.assertIn("Recall@10 is 17 of 18", L.build(s, now=NOW)[0]["body"][2]["items"][0]["text"])

    def test_the_flip_row_names_the_activity_not_a_missing_tag(self):
        # 耳朵与翻页行的第二格是改到的节（短名来自登记表 draft.sections[].short），不是提交号（作者 09-21）
        s = with_change(label="colSmol 说反"); s["section_names"] = {"X": "§5.5"}
        a = only(L.build(s, now=NOW))
        self.assertEqual(a["flip"], {"title": "colSmol 说反", "subtitle": "ws", "phase": "§5.5"})
        self.assertEqual((a["ears"]["phase"], a["ears"]["tag"]["text"]), ("§5.5", "15 句"))
        self.assertEqual(only(L.build(with_change(), now=NOW))["ears"]["phase"], "X")    # 没有短名就用前缀

    def test_panel_lists_every_changeset_newest_first_with_the_passive_note(self):
        s = with_change()
        s["history"] = [{"id": "b", "time": NOW, "n": 2, "traced": False, "verbatim": None, "status": "none"},
                        {"id": "a", "time": NOW - 9, "n": 15, "traced": True, "verbatim": "改 §5.5", "status": "one"}]
        a = only(L.build(s, now=NOW, notices=["拦下写入：2 次"]))
        d = a["detail"]
        # 分镜 ㉚：无出处折成一行（点开才摊），追到的一行 = 你说 + 句数徽章 + 行尾提交号
        self.assertEqual([h["id"] for h in d["history"]], ["fold-b", "a"])
        fold, one = d["history"]
        self.assertEqual((fold["tag"], fold["badge"], fold["lines"]), ("无出处 ×1", "2 句", []))
        self.assertEqual([(r["label"], r["copy"]) for r in fold["rows"]], [("b", "b")])
        self.assertTrue(fold["rows"][0]["where"].startswith("2 句 · "))
        self.assertEqual((one["badge"], one["duration"], one["lines"][0]["text"]), ("15 句", "a", "改 §5.5"))
        self.assertNotIn("tag", one)
        self.assertIn("拦下 1 次", d["historyNote"])
        # 进度按改动集（作者 09-21）：一格一个，旧 → 新；图表卡没有了；数据条只剩三格
        self.assertNotIn("chart", d)
        self.assertEqual(d["strip"]["cells"], [L.IDENTITY, L.UNTRACED])
        self.assertEqual([(k["name"], k["count"]) for k in d["strip"]["legend"]], [("追到", 1), ("无出处", 1)])
        self.assertEqual([c["label"] for c in d["stats"]], ["追到", "拦下", "缺依据"])
        self.assertEqual(d["listTitle"], "ws · 15 句 · 已追到")

    def test_consecutive_untraced_changesets_fold_in_groups_of_sixteen(self):
        s = with_change()
        s["history"] = [{"id": f"u{i:02d}", "time": NOW - i, "n": 1, "traced": False, "verbatim": None, "status": "none", "subject": f"s {i}"}
                        for i in range(20)]
        d = only(L.build(s, now=NOW))["detail"]
        self.assertEqual([(h["tag"], len(h["rows"])) for h in d["history"]], [("无出处 ×16", 16), ("无出处 ×4", 4)])
        self.assertEqual(d["history"][0]["rows"][0]["new"], "s 0")
        self.assertEqual(d["strip"]["cells"], [L.UNTRACED] * 20)

    def test_identity_is_the_registry_indigo(self):
        self.assertEqual(L.IDENTITY, "indigo")
        self.assertEqual(only(L.build(with_change(), now=NOW))["detail"]["dot"], "indigo")

    def test_labels_tags_and_pills_fit_the_notch(self):
        for s, problems in ((summary(), ()), (with_change(), ()), (with_change(traced=False), ()),
                            (with_change(label="colSmol 说反"), ()), (with_change(), ["x"])):
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
        a = only(L.build(with_change(cid="a066846"), now=NOW))
        b = only(L.build(with_change(cid="b123456"), now=NOW))
        self.assertNotEqual(a["revision"], b["revision"])
        self.assertNotEqual(a["events"][0]["id"], b["events"][0]["id"])


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
