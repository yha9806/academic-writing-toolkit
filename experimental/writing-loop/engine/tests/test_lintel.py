import json
import os
import unittest
from pathlib import Path

from loop import lintel as L

from fixtures import TempDir

NOW = 1_789_700_000

CLEAN = {"name": "ws", "head": "abc1234", "versions": 15, "sentences": 82, "changesets": 14,
         "mixed": 0, "all_unknown": 0, "ledger": 91,
         "ledger_status": {"found": 91}, "unattached_ledger": 0,
         "messages": 64, "messages_attached": 1, "messages_before_first_version": 17}


def summary(**over):
    s = dict(CLEAN)
    s["ledger_status"] = dict(CLEAN["ledger_status"])
    s.update(over)
    return s


class BuildTest(unittest.TestCase):
    def test_no_problems_leaves_only_the_draft_card(self):
        self.assertEqual([a["id"] for a in L.build(summary(), now=NOW)], ["draft"])

    def test_each_kind_of_problem_adds_its_own_card(self):
        s = summary(ledger_status={"found": 88, "no_source": 3}, all_unknown=12, mixed=2)
        ids = [a["id"] for a in L.build(s, now=NOW, problems=["doctor: 台账路径读不到"])]
        self.assertEqual(ids, ["draft", "ledger", "triggers", "tool"])

    def test_first_popup_line_always_says_who(self):
        s = summary(ledger_status={"found": 88, "no_source": 3}, all_unknown=12)
        for a in L.build(s, now=NOW, problems=["x"]):
            self.assertEqual(a["popup"][0]["label"], "谁说的")
            self.assertIn(a["popup"][0]["text"], L.SOURCE_WORD.values())

    def test_inferred_trigger_is_assumed_not_flagged(self):
        """全 △ 是「不知道」，只有推断是「我替你定的」——两者不能画成同一个圆心。"""
        only_inferred = L.build(summary(mixed=2), now=NOW)[1]
        self.assertEqual(only_inferred["status"]["center"], "assumed")
        self.assertFalse(only_inferred["flagged"])
        unknown = L.build(summary(all_unknown=1, mixed=2), now=NOW)[1]
        self.assertEqual(unknown["status"]["center"], "flagged")
        self.assertTrue(unknown["flagged"])

    def test_revision_ignores_the_clock(self):
        a = L.build(summary(), now=NOW)[0]
        b = L.build(summary(), now=NOW + 5000)[0]
        self.assertNotEqual(a["updatedAt"], b["updatedAt"])
        self.assertEqual(a["revision"], b["revision"])

    def test_revision_changes_when_a_number_changes(self):
        a = L.build(summary(), now=NOW)[0]
        b = L.build(summary(sentences=83), now=NOW)[0]
        self.assertNotEqual(a["revision"], b["revision"])

    def test_labels_and_tags_fit_the_notch(self):
        s = summary(ledger_status={"found": 8, "no_source": 3}, all_unknown=12, mixed=2)
        for a in L.build(s, now=NOW, problems=["x"]):
            self.assertLessEqual(len(a["label"]["text"]), 6, a["id"])
            self.assertLessEqual(len(a["ears"]["tag"]["text"]), 6, a["id"])


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
        if True:
            acts = L.build(summary(), now=NOW)
            self.assertEqual(L.sync(acts, home=root, now=NOW)["written"], 1)
            # 修改时间按测试的钟来设，否则「旧到该续心跳了」取决于真实墙上时间。
            os.utime(self.dir(root) / "draft.json", (NOW, NOW))
            again = L.build(summary(), now=NOW + 5)
            self.assertEqual(L.sync(again, home=root, now=NOW + 5),
                             {"written": 0, "touched": 0, "unchanged": 1, "removed": 0})

    def test_heartbeat_rewrites_the_same_bytes_so_seen_is_not_reset(self):
        root = self.root
        if True:
            L.sync(L.build(summary(), now=NOW), home=root, now=NOW)
            p = self.dir(root) / "draft.json"
            before = p.read_bytes()
            os.utime(p, (NOW - 600, NOW - 600))
            counts = L.sync(L.build(summary(), now=NOW + 600), home=root, now=NOW + 600)
            self.assertEqual(counts["touched"], 1)
            self.assertEqual(p.read_bytes(), before)

    def test_a_problem_that_went_away_takes_its_card_with_it(self):
        root = self.root
        if True:
            L.sync(L.build(summary(all_unknown=12), now=NOW), home=root, now=NOW)
            self.assertTrue((self.dir(root) / "triggers.json").exists())
            counts = L.sync(L.build(summary(), now=NOW + 1), home=root, now=NOW + 1)
            self.assertEqual(counts["removed"], 1)
            self.assertFalse((self.dir(root) / "triggers.json").exists())

    def test_written_file_is_valid_json_with_the_protocol_keys(self):
        root = self.root
        if True:
            L.sync(L.build(summary(), now=NOW), home=root, now=NOW)
            a = json.loads((self.dir(root) / "draft.json").read_text(encoding="utf-8"))
            for k in ("schema", "id", "open", "running", "inProgress", "stale", "flagged",
                      "rank", "labelUntilSeen", "pillUntilSeen", "popup", "body", "events"):
                self.assertIn(k, a)
            self.assertEqual(a["id"], "draft")


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
            self.assertEqual(main(["lintel", str(ws), "--once", "--home", str(home)]), 2)
            self.assertFalse(home.exists())
            register(home)
            self.assertEqual(main(["lintel", str(ws), "--once", "--home", str(home)]), 0)
            self.assertTrue((home / "producers" / L.PRODUCER / "activities" / "draft.json").exists())


if __name__ == "__main__":
    unittest.main()
