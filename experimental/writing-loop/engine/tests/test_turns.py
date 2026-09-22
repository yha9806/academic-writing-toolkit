"""The turn the notch reads (lintel design 2026-09-22-awt-live §3.5, B1 ②): when the author wrote, when the manuscript was
touched, when the turn ended. All data here is synthetic."""
import json
import unittest
from pathlib import Path

from loop import turns as TN
from loop.cli import main

from fixtures import TempDir, git
from test_hooks import setup  # noqa: F401  (shared fixture)

CFG = {"draft": {"glob": "drafts/DRAFT-v*.md"}}
T0 = 1_789_700_000


def prompt(ws, at_iso, chars=12, pid="p1", session="s1"):
    (ws / "human").mkdir(parents=True, exist_ok=True)
    with open(ws / "human" / "comments.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"at": at_iso, "session_id": session, "prompt_id": pid, "prompt": "x" * chars,
                             "origin": "hook:UserPromptSubmit"}) + "\n")


def iso(t):
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


class RecordTest(unittest.TestCase):
    def test_records_round_trip_and_bad_lines_are_skipped(self):
        with TempDir() as root:
            TN.record(root, "write:drafts/DRAFT-v2.md", now=T0)
            with open(root / "cache" / TN.FILE, "a") as fh:
                fh.write("not json\n{\"t\": \"x\"}\n")
            TN.record(root, "stop", now=T0 + 1)
            self.assertEqual([r["reason"] for r in TN.read(root)], ["write:drafts/DRAFT-v2.md", "stop"])

    def test_the_file_is_kept_short(self):
        with TempDir() as root:
            for i in range(TN.KEEP + 300):
                TN.record(root, "write:" + "d" * 150, now=T0 + i)
            self.assertLessEqual(len(TN.read(root)), TN.KEEP + 300)
            self.assertLess((root / "cache" / TN.FILE).stat().st_size, TN.KEEP * 200 + 400)


class PromptTest(unittest.TestCase):
    def test_the_latest_message_gives_time_session_id_and_length_never_the_text(self):
        with TempDir() as root:
            prompt(root, iso(T0), chars=5, pid="a")
            prompt(root, iso(T0 + 30), chars=44, pid="b", session="s2")
            p = TN.last_prompt(root)
            self.assertEqual((p["t"], p["session"], p["id"], p["chars"]), (T0 + 30, "s2", "b", 44))
            self.assertNotIn("prompt", p)

    def test_no_messages_is_none(self):
        with TempDir() as root:
            self.assertIsNone(TN.last_prompt(root))
            self.assertIsNone(TN.current(root, CFG))


class TurnTest(unittest.TestCase):
    def test_touches_after_the_message_and_its_stop(self):
        with TempDir() as root:
            TN.record(root, "write:drafts/DRAFT-v2.md", now=T0 - 5)      # the previous turn
            prompt(root, iso(T0))
            TN.record(root, "stop", now=T0 + 1)                          # the previous turn's stop, same second
            TN.record(root, "write:drafts/DRAFT-v2.md", now=T0 + 20)
            TN.record(root, "git", now=T0 + 30)                          # any git command: not a touch by itself
            TN.record(root, "head:abc1234", now=T0 + 31)                 # the manuscript got a commit
            t = TN.current(root, CFG)
            self.assertEqual([k for _, k in t["touches"]], ["draft", "head"])
            self.assertIsNone(t["ended"])
            self.assertTrue(TN.running(t, T0 + 40))
            self.assertEqual(TN.action(t), "提交")
            TN.record(root, "stop", now=T0 + 50)
            t = TN.current(root, CFG)
            self.assertEqual(t["ended"], T0 + 50)
            self.assertFalse(TN.running(t, T0 + 60))

    def test_the_previous_turns_stop_in_the_same_second_does_not_end_this_one(self):
        with TempDir() as root:
            prompt(root, iso(T0))                              # the hook writes whole seconds
            TN.record(root, "stop", now=T0 + 0.6)              # the last turn's Stop, logged just after
            self.assertIsNone(TN.current(root, CFG)["ended"])
            TN.record(root, "stop", now=T0 + 9)
            self.assertEqual(TN.current(root, CFG)["ended"], T0 + 9)

    def test_a_touch_after_a_stop_means_that_stop_was_blocked(self):
        with TempDir() as root:
            prompt(root, iso(T0))
            TN.record(root, "write:drafts/DRAFT-v2.md", now=T0 + 10)
            TN.record(root, "stop", now=T0 + 20)          # blocked by the rewrite gate
            TN.record(root, "write:drafts/DRAFT-v2.md", now=T0 + 25)
            t = TN.current(root, CFG)
            self.assertIsNone(t["ended"])
            self.assertTrue(TN.running(t, T0 + 30))

    def test_a_ledger_write_is_a_touch_and_an_hour_of_silence_is_not_running(self):
        with TempDir() as root:
            prompt(root, iso(T0))
            TN.record(root, "write:ledger.tsv", now=T0 + 10)
            t = TN.current(root, CFG)
            self.assertEqual(TN.action(t), "改台账")
            self.assertTrue(TN.running(t, T0 + 10 + TN.STUCK - 1))
            self.assertFalse(TN.running(t, T0 + 10 + TN.STUCK + 1))

    def test_a_turn_that_touched_nothing_is_not_running(self):
        with TempDir() as root:
            prompt(root, iso(T0))
            TN.record(root, "git", now=T0 + 10)
            self.assertFalse(TN.running(TN.current(root, CFG), T0 + 20))


class ReadersTest(unittest.TestCase):
    def test_the_weakest_recall_item(self):
        s = "9 位读者；M1.asked 8/9，M1.recall 7/9，M2.recall 4/9，M3.recall 6/9（合成）"
        self.assertEqual(TN.weakest_reader(s), ("M2", 4, 9))
        self.assertIsNone(TN.weakest_reader("没有逐项结果"))

    def test_the_readers_run_record(self):
        with TempDir() as root:
            d = root / "cache" / "coverage" / "runs"
            d.mkdir(parents=True)
            (d / "readers.json").write_text(json.dumps({"at": "2026-01-02T03:04:05.250000+00:00", "summary": "M1.recall 1/2",
                                                        "verdict": "findings"}))
            r = TN.readers_run(root)
            self.assertEqual((r["verdict"], r["summary"]), ("findings", "M1.recall 1/2"))
            from datetime import datetime, timezone
            self.assertAlmostEqual(r["t"], datetime(2026, 1, 2, 3, 4, 5, 250000, tzinfo=timezone.utc).timestamp(), places=3)


class UpdateRecordsTest(unittest.TestCase):
    def test_update_records_its_reason_and_a_new_manuscript_head(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            self.assertEqual(main(["update", str(ws), "--reason", "write:drafts/DRAFT-v2.md"]), 0)
            first = [r["reason"] for r in TN.read(ws)]
            self.assertEqual(first[0], "write:drafts/DRAFT-v2.md")
            self.assertTrue(any(r.startswith("head:") for r in first))       # the first build sees a head
            self.assertEqual(main(["update", str(ws), "--reason", "git"]), 0)
            second = [r["reason"] for r in TN.read(ws)][len(first):]
            self.assertEqual(second, ["git"])                                 # no new commit: no head line
            (repo / "note.txt").write_text("n")
            git(repo, "add", "note.txt")
            git(repo, "commit", "-q", "-m", "n")
            self.assertEqual(main(["update", str(ws), "--reason", "git"]), 0)
            third = [r["reason"] for r in TN.read(ws)][len(first) + 1:]
            self.assertEqual(third[0], "git")
            self.assertTrue(third[1].startswith("head:"))


if __name__ == "__main__":
    unittest.main()
