"""The manuscript ring (the conversation-layer spec W1-W4, plus the design stage the author approved):
seven stages of one revision round, what hangs on each, and which ones the engine only infers."""
import unittest

import isolation  # noqa: F401 -- a throwaway HOME before anything reads the real one

from loop import coverage as V
from loop import ring as R


def risk(kind, rid, gate, decided_on=None, uuid=None):
    x = {"kind": kind, "id": rid, "title": f"合成标题 {rid}", "gate": gate, "source": "合成", "status": "未决"}
    if decided_on:
        x.update(decided_on=decided_on, decision="合成决定", uuid=uuid or "0" * 36)
    return x


def summary(open_=(), decided=(), rows=()):
    return {"risks": {"open": list(open_), "decided": list(decided), "below": [], "problems": []}, "rows": list(rows)}


def row(cid, status, last_at=None, name=None):
    return {"id": cid, "name": name or cid, "status": status, "detail": "", "last_at": last_at}


def seg(r, key):
    return next(s for s in r["segments"] if s["key"] == key)


class RingTest(unittest.TestCase):
    def test_the_gate_text_hangs_an_open_item_on_its_stage(self):
        """The shapes a real register uses to name a gate (synthetic wording): the first part decides, and a gate
        that names both a review page and a rewrite belongs to the review."""
        s = summary(open_=[risk("风险", "A1", "改稿核对页；再跑一轮读者组"), risk("风险", "A2", "作者写完意图卡；核对页"),
                           risk("风险", "A3", "这一轮改稿结束"), risk("风险", "A4", "作者核完之后决定怎么改稿"),
                           risk("风险", "A5", "G2"), risk("风险", "A6", "D2")])
        r = R.ring(s)
        self.assertEqual([i["id"] for i in seg(r, "review")["items"]], ["A1", "A4"])
        self.assertEqual([i["id"] for i in seg(r, "design")["items"]], ["A2"])
        self.assertEqual([i["id"] for i in seg(r, "rewrite")["items"]], ["A3"])
        self.assertEqual([i["id"] for i in r["unhung"]], ["A5", "A6"], "a gate id is not a stage: listed apart, not guessed")
        self.assertEqual(r["waiting"], 6, "every open register item waits on the author")

    def test_a_round_starts_at_the_last_review_decision_and_says_its_precision(self):
        s = summary(decided=[risk("风险", "B1", "改稿核对页", "2026-09-23"), risk("风险", "B2", "对照经作者在核对页裁定", "2026-09-24"),
                             risk("门", "G4", "G4", "2026-09-25")])
        r = R.ring(s)
        self.assertEqual(r["since"], "2026-09-24", "only a review decision starts a round, not a later gate")
        self.assertIn("日", r["sinceNote"], "the register keeps dates, not times: the ring says so")
        self.assertIsNone(R.ring(summary())["since"], "no review decided yet: the round runs from the start")

    def test_the_current_stage_is_the_first_with_something_hanging(self):
        s = summary(open_=[risk("风险", "C1", "作者写完意图卡"), risk("风险", "C2", "改稿核对页")])
        r = R.ring(s, last_comment_at="2026-09-24T10:00:00Z")
        self.assertEqual(r["current"], "design")
        self.assertEqual(seg(r, "comment")["state"], "done")

    def test_with_nothing_hanging_the_current_stage_is_the_first_not_yet_reached(self):
        r = R.ring(summary(), last_comment_at="2026-09-24T10:00:00Z")
        self.assertEqual(r["current"], "rewrite", "the author spoke; nothing rewritten since")

    def test_the_latest_activity_is_said_beside_the_current_stage(self):
        """A real manuscript waited at 设计 (an item hung there) while the day's work was rewriting. Both are true, so
        both are said: where the round waits, and where it last moved."""
        s = summary(open_=[risk("风险", "C1", "作者写完意图卡")],
                    rows=[row("readers", V.OK, last_at="2026-09-24T09:00:00Z"), row("x", V.OK, last_at="2026-09-24T09:30:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual(r["current"], "design")
        self.assertEqual(r["latest"], "rewrite")
        self.assertIsNone(R.ring(summary())["latest"])

    def test_checks_that_are_not_current_hang_on_the_check_stage(self):
        s = summary(rows=[row("fingerprint", V.FAILED, name="文风"), row("claims", V.STALE, name="主张台账"), row("x", V.OK)])
        r = R.ring(s, last_comment_at="2026-09-24T10:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual([i["id"] for i in seg(r, "check")["items"]], ["fingerprint", "claims"])
        self.assertEqual(r["current"], "check")

    def test_a_reader_panel_older_than_the_last_rewrite_hangs_on_readers_as_stale(self):
        s = summary(rows=[row("readers", V.OK, last_at="2026-09-24T09:00:00Z", name="读者组")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        items = seg(r, "readers")["items"]
        self.assertEqual(len(items), 1)
        self.assertIn("过期", items[0]["text"])
        fresh = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T08:30:00Z")
        self.assertEqual(seg(fresh, "readers")["items"], [])

    def test_times_in_different_offsets_are_compared_as_times(self):
        """The hooks write …Z, git writes …+01:00: as strings 12:30Z sorts before 13:20+01:00 (12:20Z)."""
        s = summary(rows=[row("readers", V.OK, last_at="2026-09-24T12:30:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T13:20:00+01:00")
        self.assertEqual(seg(r, "readers")["items"], [], "the panel ran after the rewrite")
        self.assertEqual(r["latest"], "readers")

    def test_register_items_are_the_authors_to_decide_and_stale_checks_are_not(self):
        """The host paints what waits on the author apart from what is only out of date: each hung item says which."""
        s = summary(open_=[risk("风险", "C1", "作者写完意图卡")], rows=[row("fingerprint", V.STALE, name="文风")])
        r = R.ring(s, last_comment_at="2026-09-24T10:00:00Z", last_change_at="2026-09-24T11:00:00Z")
        self.assertEqual([i["you"] for i in seg(r, "design")["items"]], [True])
        self.assertEqual([i["you"] for i in seg(r, "check")["items"]], [False])

    def test_the_latest_activity_carries_its_time(self):
        s = summary(rows=[row("readers", V.OK, last_at="2026-09-24T12:30:00Z")])
        r = R.ring(s, last_comment_at="2026-09-24T08:00:00Z", last_change_at="2026-09-24T13:20:00+01:00")
        self.assertEqual(r["latest_at"], "2026-09-24T12:30:00Z")
        self.assertIsNone(R.ring(summary())["latest_at"])

    def test_what_the_engine_cannot_see_is_said_not_guessed(self):
        r = R.ring(summary())
        self.assertEqual([s["key"] for s in r["segments"]], ["comment", "design", "rewrite", "check", "readers", "review", "land"])
        self.assertEqual(seg(r, "review")["seen"], R.INFERRED)
        self.assertEqual(seg(r, "land")["seen"], R.COMMITS_ONLY)
        self.assertEqual(seg(r, "design")["seen"], R.INFERRED)
        self.assertEqual(seg(r, "check")["seen"], R.SEEN)

    def test_closed_gates_are_listed_by_date_with_the_authors_message(self):
        s = summary(decided=[risk("门", "G0", "G0", "2026-09-22", "aaaa1111" + "0" * 28),
                             risk("风险", "B1", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28),
                             risk("风险", "B2", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28)])
        closed = R.ring(s)["closed"]
        self.assertEqual([c["date"] for c in closed], ["2026-09-23", "2026-09-22"], "newest first")
        self.assertEqual(closed[0]["items"], ["B1、B2（bbbb2222）"], "one message closed both: said once")
        mixed = R.ring(summary(decided=[risk("风险", "B1", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28),
                                        risk("门", "G3", "G3", "2026-09-23", "cccc3333" + "0" * 28),
                                        risk("风险", "B2", "改稿核对页", "2026-09-23", "bbbb2222" + "0" * 28),
                                        {k: v for k, v in risk("风险", "B3", "改稿核对页", "2026-09-23").items() if k != "uuid"}]))["closed"]
        self.assertEqual(mixed[0]["items"], ["B1、B2（bbbb2222）", "G3（cccc3333）", "B3"], "in the order first seen; no uuid, no bracket")


if __name__ == "__main__":
    unittest.main()
