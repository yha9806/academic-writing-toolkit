import unittest

from loop import explain as EX


def human(mid, t, text, session="s1", channel="prompt"):
    return {"mid": mid, "ts": f"t{t}", "t": t, "text": text, "sessions": [session], "channel": channel}


def reply(aid, t, text, session="s1"):
    return {"aid": aid, "ts": f"t{t}", "t": t, "text": text, "session": session}


class ParseTest(unittest.TestCase):
    def test_block_fields_are_read(self):
        p = EX.parse("Done.\n\n〔循环〕\n读成：只改标题\n改了：T01\n依据：你说标题太长\n〔/循环〕")
        self.assertEqual((p["reading"], p["changed"], p["basis"], p["source"]), ("只改标题", "T01", "你说标题太长", "解释块"))
        self.assertIsNone(p["label"])

    def test_the_label_line_is_the_notch_wing_and_stays_short_in_the_record(self):
        p = EX.parse("〔循环〕\n读成：改正 §3.2 那句\n改了：X6.2\n依据：你说说反了\n标签：betaVal 说反\n〔/循环〕")
        self.assertEqual((p["reading"], p["changed"], p["label"], p["source"]), ("改正 §3.2 那句", "X6.2", "betaVal 说反", "解释块"))

    def test_first_line_reading_counts_when_the_block_omits_it(self):
        p = EX.parse("我读成了：先别动 A03\n\n...\n\n〔循环〕\n改了：无\n〔/循环〕")
        self.assertEqual((p["reading"], p["changed"], p["source"]), ("先别动 A03", "无", "我读成了"))

    def test_block_reading_wins_over_first_line(self):
        p = EX.parse("我读成了：甲\n〔循环〕\n读成：乙\n〔/循环〕")
        self.assertEqual((p["reading"], p["source"]), ("乙", "解释块"))

    def test_unclosed_block_is_not_a_block(self):
        p = EX.parse("〔循环〕\n读成：甲\n改了：I1.2")
        self.assertFalse(p["block"])
        self.assertIsNone(p["changed"])

    def test_first_occurrence_of_a_field_wins_and_empty_values_do_not_count(self):
        p = EX.parse("〔循环〕\n读成：\n读成：甲\n读成：乙\n〔/循环〕")
        self.assertEqual(p["reading"], "甲")

    def test_more_than_six_lines_is_flagged_not_dropped(self):
        body = "\n".join(["读成：甲"] + [f"依据：{i}" for i in range(6)])
        p = EX.parse(f"〔循环〕\n{body}\n〔/循环〕")
        self.assertTrue(p["over_limit"])
        self.assertEqual(p["reading"], "甲")

    def test_a_reading_written_over_several_lines_is_read_to_its_end(self):
        """Found in use: a reading that went on as a list was cut at its first line."""
        p = EX.parse("我读成了：对应的几件事是：\n- 修四处\n- 改 §3.2\n我补上的：无\n标签：修四处")
        self.assertEqual(p["reading"], "对应的几件事是： 修四处 改 §3.2")
        p = EX.parse("我读成了：只改标题\n\n正文开始。")
        self.assertEqual(p["reading"], "只改标题")

    def test_nothing_said_is_none_not_empty_string(self):
        p = EX.parse("Just an answer.")
        self.assertEqual((p["reading"], p["source"], p["block"]), (None, None, False))


class BuildTest(unittest.TestCase):
    def test_ambiguous_reaction_keeps_the_words_and_shows_the_reading_beside_them(self):
        """T14: "可以但是……" is exactly where a reading can go wrong; the original stays verbatim."""
        words = "可以 但是 A03 那句先别动……"
        conv = {"human": [human("h1", 10, words), human("h2", 50, "继续")],
                "assistant": [reply("a1", 11, "我读成了：同意推进，但 A03 保持原样\n\n改好了。"),
                              reply("a2", 12, "〔循环〕\n改了：A01, A02\n依据：你的第一句\n〔/循环〕"),
                              reply("a3", 51, "好的。")]}
        e = EX.build(conv)
        self.assertEqual(e[0]["verbatim"], words)
        self.assertEqual((e[0]["reading"], e[0]["changed"], e[0]["source"]), ("同意推进，但 A03 保持原样", "A01, A02", "我读成了"))
        self.assertEqual(e[0]["replies"], ["a1", "a2"])
        self.assertIsNone(e[1]["reading"])

    def test_a_message_typed_mid_turn_does_not_take_the_turns_block(self):
        """Found in use: a question typed while Claude was working took the explanation of the turn it interrupted."""
        conv = {"human": [human("p", 10, "改 §3.2 那句"), human("q", 12, "先给我看看刘海", channel="queued"),
                          human("n", 50, "下一件事")],
                "assistant": [reply("a1", 11, "开始改。"),
                              reply("a2", 13, "我读成了：先画刘海的图\n\n做完了。\n〔循环〕\n读成：改正 §3.2 那句\n改了：X6.2\n依据：你的原话\n〔/循环〕")]}
        e = {x["mid"]: x for x in EX.build(conv)}
        self.assertEqual((e["p"]["reading"], e["p"]["changed"], e["p"]["source"]), ("改正 §3.2 那句", "X6.2", "解释块"))
        self.assertEqual((e["q"]["reading"], e["q"]["changed"], e["q"]["source"]), ("先画刘海的图", None, "我读成了"))
        self.assertIsNone(e["n"]["reading"])

    def test_replies_from_another_session_are_not_borrowed(self):
        conv = {"human": [human("h1", 10, "改一下标题", session="s1")],
                "assistant": [reply("a1", 11, "我读成了：别的会话的事", session="s2")]}
        self.assertIsNone(EX.build(conv)[0]["reading"])


if __name__ == "__main__":
    unittest.main()
