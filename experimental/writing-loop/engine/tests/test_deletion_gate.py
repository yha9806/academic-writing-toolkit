"""The changed-sentence gate on what a deletion takes with it and on a share that disagrees (spec
2026-09-29-deletion-side-effects D1–D3). Synthetic text throughout: a bridge survey, no manuscript text."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import coverage as V

from fixtures import TempDir

# AWT_AUDIT_DIR: the mutated copy a red check is testing; otherwise the skill in this checkout.
AUDIT = Path(os.environ.get("AWT_AUDIT_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "audit" / "scripts")
GATE = AUDIT / "audit-sentence-changes.py"

INTRO = "The survey logged readings from brass gauges on the north bridge."
FILLER = ["Weather varied across the season.", "Crews worked in pairs on each span.",
          "Traffic was stopped for an hour each morning.", "Rain delayed two of the visits.",
          "Each visit lasted about three hours.", "A second crew checked the railings.",
          "Photographs were taken of every joint."]
LAST = "We do not test whether inspectors trust the gauge readings."


def para(*sentences):
    return " ".join(sentences)


def gate(root, base, target, *extra):
    b, t = Path(root) / "base", Path(root) / "target"
    for d, text in ((b, base), (t, target)):
        d.mkdir(parents=True, exist_ok=True)
        (d / "s.tex").write_text("\\section{Setup}\n" + text + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(GATE), "--base", str(b), "--target", str(t), "--json", *extra],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr[-400:]
    return json.loads(r.stdout)


def flags(data, name):
    return [s for s in data["sentences"] if name in s["flags"]]


class LostAntecedentTest(unittest.TestCase):
    def test_a_removal_that_took_an_antecedent_is_flagged_far_down_the_paragraph(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, *FILLER, LAST), para(*FILLER, LAST))
            [s] = flags(d, "took_antecedent")
            self.assertEqual(s["old"], INTRO)
            self.assertEqual([(h["phrase"], h["sentence"]) for h in s["antecedent"]], [("the gauge", LAST)],
                             "eight sentences on, in the same paragraph; a plural folded onto its singular, one "
                             "entry for the noun phrase")
            self.assertEqual(d["compared"]["took_antecedent"], 1)

    def test_a_noun_still_named_earlier_is_not_lost(self):
        with TempDir() as root:
            named = "Brass gauges on the north bridge gave daily readings."
            d = gate(root, para(named, INTRO, *FILLER[:2], LAST), para(named, *FILLER[:2], LAST))
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_the_next_paragraph_is_not_read(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, *FILLER[:2]) + "\n\n" + LAST, para(*FILLER[:2]) + "\n\n" + LAST)
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_ordinals_modals_and_verbs_are_not_nouns(self):
        with TempDir() as root:
            gone = "Inspectors could address the second span only at night."
            later = ["The second was closed in winter.", "Those readings could vary by an hour.",
                     "This report addresses a gap in the record."]
            d = gate(root, para(FILLER[0], gone, *later), para(FILLER[0], *later))
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_a_participle_after_a_noun_is_not_a_noun(self):
        # "the sensors added later" was taken to point back to a removed "was added afterwards"
        with TempDir() as root:
            gone = "The comparison was added afterwards."
            d = gate(root, para(FILLER[0], gone, "Only the sensors added later read the deck."),
                     para(FILLER[0], "Only the sensors added later read the deck."))
            self.assertEqual(flags(d, "took_antecedent"), [])

    def test_a_revised_later_sentence_is_read_too(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, FILLER[0], LAST),
                     para(FILLER[0], "We do not test whether bridge inspectors trust the gauge readings."))
            [s] = flags(d, "took_antecedent")
            self.assertEqual(s["antecedent"][0]["phrase"], "the gauge")


OTHER = "Two of the three later sensors read the deck temperature directly."


class ShareElsewhereTest(unittest.TestCase):
    def test_a_share_that_disagrees_is_flagged_with_the_other_sentences(self):
        with TempDir() as root:
            d = gate(root, para("One sensor reads the deck temperature directly.", OTHER),
                     para("For one of three later sensors, the deck temperature is read directly.", OTHER))
            [s] = flags(d, "count_elsewhere")
            self.assertEqual(s["shares_elsewhere"], [{"share": "one of three later sensors", "sentences": [OTHER]}])
            self.assertEqual(d["compared"]["count_elsewhere"], 1)

    def test_no_other_share_of_that_total_says_nothing(self):
        with TempDir() as root:
            four = "Two of the four later sensors read the deck temperature directly."
            same = "One of the three later sensors failed in May."
            for other in ("", four, same):
                d = gate(root, para("One sensor reads the deck temperature directly.", other),
                         para("For one of three later sensors, the deck temperature is read directly.", other))
                self.assertEqual(flags(d, "count_elsewhere"), [], other or "no other sentence")

    def test_a_share_the_sentence_already_had_is_not_flagged_again(self):
        with TempDir() as root:
            d = gate(root, para("For one of three later sensors, the deck temperature is read.", OTHER),
                     para("For one of three later sensors, the deck temperature is read directly.", OTHER))
            self.assertEqual(flags(d, "count_elsewhere"), [])

    def test_a_pairs_file_has_no_draft_to_compare_with(self):
        with TempDir() as root:
            pairs = Path(root) / "pairs.tsv"
            pairs.write_text("id\told\tnew\nx1\tOne sensor reads the deck.\tFor one of three later sensors, the "
                             "deck is read.\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(GATE), "--pairs", str(pairs), "--json"], capture_output=True,
                               text=True)
            self.assertEqual(flags(json.loads(r.stdout), "count_elsewhere"), [])


def gate_files(root, base, target):
    b, t = Path(root) / "base", Path(root) / "target"
    for d, files in ((b, base), (t, target)):
        for name, text in files.items():
            (d / name).parent.mkdir(parents=True, exist_ok=True)
            (d / name).write_text("\\section{" + name[:-4] + "}\n" + text + "\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(GATE), "--base", str(b), "--target", str(t), "--json"],
                       capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr[-400:]
    return json.loads(r.stdout)


SAME = "Ten of the eighteen gauges differ from their drawings beyond rounding."


class DuplicateTest(unittest.TestCase):
    """FOR-AWT 46: a round that removed repeated statements wrote a sentence that matched another letter for letter."""

    def test_a_rewrite_that_matches_another_sentence_but_for_a_reference_is_flagged(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], "Some gauges were replaced in May.")},
                           {"a.tex": para(FILLER[0], SAME),
                            "b.tex": para(FILLER[1], SAME[:-1] + " (Section~\\ref{sec:a}).")})
            [s] = flags(d, "duplicates_elsewhere")
            self.assertEqual(s["duplicates"], [{"where": "a.tex", "sentence": SAME}])
            self.assertEqual(d["compared"]["duplicates_elsewhere"], 1)

    def test_a_verbatim_copy_is_found_by_count(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], SAME)})
            [s] = flags(d, "duplicates_elsewhere")
            self.assertEqual((s["kind"], s["where"], s["duplicates"]), ("copied", "b.tex", [{"where": "a.tex", "sentence": SAME}]),
                             "reported where the copy landed, beside where it already stood")

    def test_a_move_is_not_a_copy(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": FILLER[1]},
                           {"a.tex": FILLER[0], "b.tex": para(FILLER[1], SAME)})
            self.assertEqual(flags(d, "duplicates_elsewhere"), [])

    def test_a_repeat_the_base_already_had_is_not_flagged(self):
        with TempDir() as root:
            both = {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], SAME)}
            d = gate_files(root, both, {**both, "a.tex": para(FILLER[2], SAME)})
            self.assertEqual(flags(d, "duplicates_elsewhere"), [])

    def test_a_short_sentence_is_not_compared(self):
        with TempDir() as root:
            short = "Results are shown below."
            d = gate_files(root, {"a.tex": para(FILLER[0], short), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], short), "b.tex": para(FILLER[1], short)})
            self.assertEqual(flags(d, "duplicates_elsewhere"), [])


NEAR = "Ten of the eighteen gauges on the north bridge differ from their drawings beyond rounding."


class NearRepeatTest(unittest.TestCase):
    """Spec 2026-10-05-probe-growth, batch 1: an introduction sentence rewritten into the abstract's with one word
    changed passed the letter-for-letter check."""

    def test_a_rewrite_worded_like_another_sentence_but_for_a_word_is_flagged(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], NEAR), "b.tex": para(FILLER[1], "Some gauges were replaced in May.")},
                           {"a.tex": para(FILLER[0], NEAR),
                            "b.tex": para(FILLER[1], NEAR.replace("north", "south"))})
            [s] = flags(d, "repeats_elsewhere")
            self.assertEqual(s["repeats"], [{"where": "a.tex", "sentence": NEAR, "ratio": 0.93}])
            self.assertEqual(d["compared"]["repeats_elsewhere"], 1)
            self.assertEqual([i.get("repeats") for i in d["issues"] if "repeats_elsewhere" in i["flags"]], [s["repeats"]])

    def test_a_letter_for_letter_copy_is_a_duplicate_and_not_also_a_repeat(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], NEAR), "b.tex": para(FILLER[1], "Some gauges were replaced in May.")},
                           {"a.tex": para(FILLER[0], NEAR), "b.tex": para(FILLER[1], NEAR[:-1] + " (Section~\\ref{sec:a}).")})
            self.assertEqual(len(flags(d, "duplicates_elsewhere")), 1)
            self.assertEqual(flags(d, "repeats_elsewhere"), [])

    def test_a_sentence_that_says_the_same_in_other_words_is_not_flagged(self):
        with TempDir() as root:
            other = "Ten of the eighteen gauges on the north bridge no longer match what their drawings show."   # 0.71
            d = gate_files(root, {"a.tex": para(FILLER[0], NEAR), "b.tex": para(FILLER[1], "Some gauges were replaced in May.")},
                           {"a.tex": para(FILLER[0], NEAR), "b.tex": para(FILLER[1], other)})
            self.assertEqual(flags(d, "repeats_elsewhere"), [])

    def test_a_short_sentence_is_not_compared(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], "Results differ by bridge here."), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], "Results differ by bridge here."),
                            "b.tex": para(FILLER[1], "Results differ by bridge there.")})
            self.assertEqual(flags(d, "repeats_elsewhere"), [])


class MultipleWithoutCountTest(unittest.TestCase):
    """Spec 2026-10-05-probe-growth, batch 1: a multiple of chance written with no count beside it."""

    def run_on(self, *sentences):
        with TempDir() as root:
            return gate(root, para(INTRO, FILLER[0], FILLER[1]), para(INTRO, *sentences))

    def test_a_multiple_of_chance_alone_is_flagged(self):
        d = self.run_on("Gauges on the north bridge were read wrong about 30 times more often than chance.", FILLER[1])
        [s] = flags(d, "multiple_without_count")
        self.assertEqual(s["multiple"], ["30 times more often than chance"])
        self.assertEqual(d["compared"]["multiple_without_count"], 1)
        self.assertEqual([i.get("multiple") for i in d["issues"] if "multiple_without_count" in i["flags"]],
                         [s["multiple"]])

    def test_a_multiple_written_in_math_is_read_as_one(self):
        d = self.run_on("The mean rose from $3.1\\times$ chance on the south span.", FILLER[1])
        self.assertEqual(len(flags(d, "multiple_without_count")), 1)

    def test_a_count_in_the_sentence_or_beside_it_is_enough(self):
        self.assertEqual(flags(self.run_on("Gauges were read wrong 9 of 12 times, 30 times more often than chance.",
                                           FILLER[1]), "multiple_without_count"), [])
        self.assertEqual(flags(self.run_on("Gauges were read wrong 30 times more often than chance.",
                                           "That is 9 wrong readings in 12."), "multiple_without_count"), [])

    def test_a_chance_level_is_not_a_multiple(self):
        d = self.run_on("All three spans sit near the $1/48$ chance level of that pool.", FILLER[1])
        self.assertEqual(flags(d, "multiple_without_count"), [])


class LoopSummaryTest(unittest.TestCase):
    def test_the_loop_names_the_new_flags_apart(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, FILLER[0], LAST), para(FILLER[0], LAST))
            _, summary = V.interpret("sentence-changes", 1, json.dumps(d), "")
            self.assertIn("删句后指代可能落空 1", summary)

    def test_the_loop_names_a_duplicate(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], SAME), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], SAME), "b.tex": para(FILLER[1], SAME)})
            _, summary = V.interpret("sentence-changes", 1, json.dumps(d), "")
            self.assertIn("与别处一字不差 1", summary)

    def test_the_loop_names_a_near_repeat(self):
        with TempDir() as root:
            d = gate_files(root, {"a.tex": para(FILLER[0], NEAR), "b.tex": FILLER[1]},
                           {"a.tex": para(FILLER[0], NEAR), "b.tex": para(FILLER[1], NEAR.replace("north", "south"))})
            _, summary = V.interpret("sentence-changes", 1, json.dumps(d), "")
            self.assertIn("与别处几乎一样 1", summary)

    def test_the_loop_names_a_multiple_without_a_count(self):
        with TempDir() as root:
            d = gate(root, para(INTRO, FILLER[0]),
                     para(INTRO, "Gauges were read wrong about 30 times more often than chance."))
            _, summary = V.interpret("sentence-changes", 1, json.dumps(d), "")
            self.assertIn("倍数旁没有命中数 1", summary)


if __name__ == "__main__":
    unittest.main()
