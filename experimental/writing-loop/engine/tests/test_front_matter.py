"""audit-front-matter.py: what the title and the abstract leave a reader to guess (spec 2026-10-05-probe-growth,
batch 2): a title word the abstract no longer has, and a name the draft coins that the abstract uses before saying
what it is. Synthetic LaTeX only."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import coverage as V

from fixtures import TempDir

# AWT_AUDIT_DIR: the mutated copy a red check is testing; otherwise the audit skill in this checkout.
SCRIPTS = Path(os.environ.get("AWT_AUDIT_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "audit" / "scripts")

TITLE = "\\title[Gauge drift]{When the gauge drifts before the flood: Sensor drift as an early warning}"
DEFINED = ("We built GaugeBench, a record of 14 river gauges, and asked whether sensor drift gives an early warning "
           "of floods. Drift rose before 12 of 14 floods.")
METHOD = "\\section{Method}\nWe built GaugeBench, a record of 14 river gauges kept for ten years.\n"


def check(root, abstract=DEFINED, title=TITLE, body=METHOD, files=None, corpus=None, env=None):
    root = Path(root)
    for name, text in (files or {}).items():
        (root / name).write_text(text, encoding="utf-8")
    parts = [title] if title else []
    if abstract is not None:
        parts.append(f"\\begin{{abstract}}\n{abstract}\n\\end{{abstract}}")
    (root / "main.tex").write_text("\\documentclass{article}\n" + "\n".join(parts) + "\n\\begin{document}\n"
                                   + body + "\n\\end{document}\n", encoding="utf-8")
    extra = ["--venue-corpus", str(corpus)] if corpus else []
    r = subprocess.run([sys.executable, str(SCRIPTS / "audit-front-matter.py"), "--root", str(root), "--json", *extra,
                        str(root / "main.tex")], capture_output=True, text=True, env=env)
    assert r.returncode in (0, 1), r.stderr[-400:]
    d = json.loads(r.stdout)
    assert (r.returncode == 1) == bool(d["issues"]), (r.returncode, d["issues"])
    return d


def kinds(d, kind):
    return [i.get("word") or i.get("name") for i in d["issues"] if i["kind"] == kind]


class TitleWordsTest(unittest.TestCase):
    def test_a_title_word_the_abstract_lost_is_reported(self):
        with TempDir() as root:
            d = check(root, abstract=DEFINED.replace("sensor drift gives an early warning of", "drift comes before"))
            self.assertEqual(kinds(d, "title-word-missing-from-abstract"), ["Sensor", "early", "warning"])
            self.assertEqual(d["title_words"], ["gauge", "drifts", "flood", "Sensor", "early", "warning"])

    def test_an_abstract_with_every_title_word_has_no_issue(self):
        with TempDir() as root:
            self.assertEqual(check(root)["issues"], [])

    def test_a_plural_or_another_form_of_the_word_counts(self):
        with TempDir() as root:
            title = "\\title{Retrieval of flood warnings}"
            d = check(root, title=title, abstract="We built GaugeBench, a record that retrieved a flood warning.")
            self.assertEqual(kinds(d, "title-word-missing-from-abstract"), [])

    def test_a_word_that_only_starts_like_it_does_not(self):
        with TempDir() as root:
            title = "\\title{Shortcuts in flood gauges}"
            d = check(root, title=title, abstract="We built GaugeBench, a record of short flood gauges.")
            self.assertEqual(kinds(d, "title-word-missing-from-abstract"), ["Shortcuts"])

    def test_the_short_title_is_not_read(self):
        with TempDir() as root:
            d = check(root, title=TITLE.replace("[Gauge drift]", "[Rainfall and gauge drift]"))
            self.assertEqual(kinds(d, "title-word-missing-from-abstract"), [])

    def test_a_title_in_an_input_file_is_found(self):
        with TempDir() as root:
            d = check(root, title="\\input{front}", files={"front.tex": "\\title{Tidal gauges}\n"})
            self.assertEqual(kinds(d, "title-word-missing-from-abstract"), ["Tidal"])

    def test_no_abstract_is_said_and_not_checked(self):
        with TempDir() as root:
            d = check(root, abstract=None)
            self.assertEqual((d["title_found"], d["abstract_found"], d["issues"]), (True, False, []))


ODD = ("The first run of our record, GaugeBench, read drift against chance. Drift rose before 12 of 14 floods, "
       "a sensor drift that gives an early warning.")


class CoinedNameTest(unittest.TestCase):
    def test_a_coined_name_used_before_the_abstract_says_what_it_is_is_reported(self):
        with TempDir() as root:
            d = check(root, abstract=ODD)
            self.assertEqual(kinds(d, "coined-name-undefined-in-abstract"), ["GaugeBench"])
            self.assertEqual(d["coined_names"], ["GaugeBench"])

    def test_the_draft_saying_we_built_it_elsewhere_makes_the_name_ours(self):
        with TempDir() as root:
            odd = ODD.replace("our record, GaugeBench,", "GaugeBench")
            self.assertEqual(kinds(check(root, abstract=odd), "coined-name-undefined-in-abstract"), ["GaugeBench"])
            self.assertEqual(kinds(check(root, abstract=odd, body="\\section{Method}\nThe gauges are old.\n"),
                                   "coined-name-undefined-in-abstract"), [])

    def test_a_name_said_to_be_ours_where_it_first_appears_is_described(self):
        for first in ("We built GaugeBench, a record of 14 river gauges, and read drift against chance.",
                      "GaugeBench, a record of 14 river gauges, reads drift against chance.",
                      "A record of 14 river gauges, GaugeBench, reads drift against chance.",
                      "GaugeBench is a record of 14 river gauges read against chance.",
                      "We built a record of 14 river gauges. GaugeBench reads drift against chance.",
                      "GaugeBench is our river record and reads drift against chance.",
                      "GaugeBench, our record of 14 river gauges, reads drift against chance.",
                      "We audit our record of river gauges, GaugeBench, against chance.",
                      "We audit GaugeBench, whose readings span ten years, against chance."):
            with self.subTest(first=first), TempDir() as root:
                d = check(root, abstract=first + " Drift gives a sensor flood warning early.")
                self.assertEqual(kinds(d, "coined-name-undefined-in-abstract"), [])

    def test_an_indefinite_phrase_that_ends_on_our_noun_does_not_describe_it(self):
        with TempDir() as root:
            odd = "An early run of our record, GaugeBench, read sensor drift against chance before each flood warning."
            self.assertEqual(kinds(check(root, abstract=odd), "coined-name-undefined-in-abstract"), ["GaugeBench"])

    def test_our_and_one_noun_says_whose_not_what(self):
        for odd in ("GaugeBench, our record, read sensor drift against chance before each flood warning early.",
                    "GaugeBench is our record. It read sensor drift against chance before each flood warning early."):
            with self.subTest(odd=odd), TempDir() as root:
                # the abstract alone says the name is ours
                d = check(root, abstract=odd, body="\\section{Method}\nThe gauges are old.\n")
                self.assertEqual(kinds(d, "coined-name-undefined-in-abstract"), ["GaugeBench"])

    def test_we_presenting_a_run_of_it_does_not_say_what_it_is(self):
        with TempDir() as root:
            odd = ("We present the first run of our record, GaugeBench, against chance. Sensor drift rose before each "
                   "flood, an early warning.")
            self.assertEqual(kinds(check(root, abstract=odd), "coined-name-undefined-in-abstract"), ["GaugeBench"])

    def test_a_name_the_draft_does_not_coin_is_not_checked(self):
        for body in ("\\section{Method}\nWe compare with RiverNet~\\cite{rivernet}.\n",
                     "\\section{Method}\nWe build on RiverNet, which others released.\n",
                     "\\section{Method}\nWe collected RiverNet scores for each gauge.\n"):
            with self.subTest(body=body), TempDir() as root:
                odd = "RiverNet reads sensor drift as an early warning before each flood at every gauge."
                d = check(root, abstract=odd, body=body)
                self.assertEqual((kinds(d, "coined-name-undefined-in-abstract"), d["coined_names"]), ([], []))

    def test_an_acronym_is_not_read_as_a_coined_name(self):
        with TempDir() as root:
            odd = "GDB reads sensor drift as an early warning before each flood at every gauge."
            d = check(root, abstract=odd, body="\\section{Method}\nWe built GDB from the gauges.\n")
            self.assertEqual(d["coined_names"], [])


def words(n):
    """n synthetic words of running text."""
    vocab = "river gauges record drift before floods and the readings rise slowly over many seasons".split()
    return " ".join(vocab[i % len(vocab)] for i in range(n))


def paper(head, n, end, between=""):
    """A synthetic venue paper as extracted text: a title, an abstract heading, n words, then a section heading."""
    return f"A synthetic paper on gauges\nAuthor One, Author Two\n{head}\n{words(n)}\n{between}{end}\n{words(300)}\n"


def corpus(root, sizes, extra=None):
    """A venue corpus of .txt papers whose abstracts have the given lengths, written in the heading forms the
    script must read, plus any extra files given."""
    forms = [("Abstract", "1 Introduction", ""), ("ABSTRACT", "1. INTRODUCTION", ""),
             ("Abstract", "I. INTRODUCTION", "Keywords: gauges, floods, drift\n"),
             ("Abstract.", "1\nIntroduction", "CCS Concepts: none here\n"), ("# Abstract", "## 1 Introduction", "")]
    d = Path(root) / "venue"
    d.mkdir()
    for i, n in enumerate(sizes):
        head, end, between = forms[i % len(forms)]
        (d / f"paper{i:02d}.txt").write_text(paper(head, n, end, between), encoding="utf-8")
    for name, text in (extra or {}).items():
        (d / name).write_text(text, encoding="utf-8")
    return d


class AbstractLengthTest(unittest.TestCase):
    """The abstract's length against the venue's: the draft's count of words, and where it falls among the abstracts
    of the venue corpus (text between an Abstract heading and the first numbered section heading). Files whose
    abstract cannot be read are counted and skipped, never guessed at."""

    SKIPPED = {"no-heading.txt": "A paper with no such heading\n" + words(200) + "\n1 Introduction\n" + words(50),
               "no-section.txt": "Abstract\n" + words(80) + "\nIntroduction without a number\n" + words(50)}

    def test_with_no_corpus_the_count_alone_is_reported(self):
        with TempDir() as root:
            d = check(root)
            self.assertEqual(d["abstract_words"], 27)
            self.assertIsNone(d["venue_abstracts"])
            self.assertIn("摘要 27 词", d["summary_zh"])

    def test_the_percentile_among_venue_abstracts_and_what_was_skipped(self):
        with TempDir() as root:
            venue = corpus(root, [10 * k + 30 for k in range(6)], self.SKIPPED)  # 30, 40, ... 80 words
            d = check(root, abstract=DEFINED + " " + words(48), corpus=venue)  # 75 words
            v = d["venue_abstracts"]
            self.assertEqual(sorted(v["parsed_files"].values()), [30, 40, 50, 60, 70, 80])
            self.assertEqual(v["parsed"], 6)
            self.assertEqual(sorted(x["file"] for x in v["skipped"]), ["no-heading.txt", "no-section.txt"])
            self.assertEqual((d["abstract_words"], v["percentile"], v["median"]), (75, 83, 55))
            self.assertEqual(kinds(d, "abstract-longer-than-venue"), [None])
            [i] = [i for i in d["issues"] if i["kind"] == "abstract-longer-than-venue"]
            self.assertEqual(i["severity"], "low")
            self.assertIn("第 83 百分位", d["summary_zh"])

    def test_at_or_below_the_75th_percentile_there_is_no_finding(self):
        with TempDir() as root:
            venue = corpus(root, [10 * k + 30 for k in range(6)])
            d = check(root, abstract=DEFINED + " " + words(23), corpus=venue)  # 50 words
            self.assertEqual((d["abstract_words"], d["venue_abstracts"]["percentile"]), (50, 42))
            self.assertEqual(d["issues"], [])

    def test_too_few_venue_abstracts_give_no_percentile(self):
        with TempDir() as root:
            venue = corpus(root, [30, 40, 50, 60], self.SKIPPED)
            d = check(root, abstract=DEFINED + " " + words(100), corpus=venue)
            v = d["venue_abstracts"]
            self.assertEqual((v["parsed"], v["percentile"]), (4, None))
            self.assertEqual(d["issues"], [])
            self.assertIn("不给百分位", d["summary_zh"])

    def test_the_loop_passes_the_venue_corpus_when_it_is_set(self):
        [c] = [c for c in K.CHECKS if c["id"] == "front-matter"]
        ctx = {"cfg": {"target": {"venue_corpus": {"dir": "/synthetic/venue"}}}, "drafts": ["main.tex"]}
        argv = c["argv"](dict(ctx, root=K.ENGINE_ROOT))
        self.assertEqual(argv[argv.index("--venue-corpus") + 1], "/synthetic/venue")
        self.assertEqual(c["outside"](ctx["cfg"]), ["/synthetic/venue"])
        self.assertIn("target.venue_corpus.dir", c.get("config_keys") or [])
        self.assertNotIn("--venue-corpus", c["argv"]({"cfg": {}, "drafts": ["main.tex"], "root": K.ENGINE_ROOT}))


PDFTOTEXT = """import json, sys
a = sys.argv[1:]
page = json.load(open(a[-2], encoding="utf-8"))
w = page["size"][0]
if "-x" in a:
    x0, width = float(a[a.index("-x") + 1]), float(a[a.index("-W") + 1])
    half = abs(width - w / 2) <= 1
    sys.stdout.write(page["cols"][0] if x0 == 0 and half else page["cols"][1] if half and abs(x0 - w / 2) <= 1 else "")
else:
    sys.stdout.write(page["full"])
"""
PDFINFO = """import json, sys
w, h = json.load(open(sys.argv[-1], encoding="utf-8"))["size"]
print("Pages:          1")
print("Page size:      %s x %s pts" % (w, h))
"""


def pdf_tools(root):
    """An environment whose pdftotext and pdfinfo read a synthetic page: a .pdf file here is JSON with the page's
    size, the text pdftotext gives for the whole page, and the text of each half when the page is cropped at its
    middle (any other crop gives nothing)."""
    bin_dir = Path(root) / "bin"
    bin_dir.mkdir()
    for name, body in (("pdftotext", PDFTOTEXT), ("pdfinfo", PDFINFO)):
        (bin_dir / name).write_text(f"#!{sys.executable}\n" + body, encoding="utf-8")
        (bin_dir / name).chmod(0o755)
    return dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))


def page(root, name, full, cols, size=(612, 792)):
    d = Path(root) / "venue"
    d.mkdir(exist_ok=True)
    (d / name).write_text(json.dumps({"size": list(size), "full": full, "cols": list(cols)}), encoding="utf-8")
    return d


class ColumnTest(unittest.TestCase):
    """10-07: of the papers of a two-column venue, the abstract of almost none was read. Cropped down the middle, each column
    reads on its own; between the "1" and the "Introduction" of the first heading the crop leaves stray glyphs."""

    TITLE_LINES = "A synthetic paper on gauges\nAuthor One, Author Two\n"

    def test_a_two_column_page_is_read_from_the_column_that_holds_the_abstract(self):
        # Read whole, the right column's figure caption falls between the abstract and the first heading.
        abstract, caption = words(120), "Figure 1: " + words(40)
        full = self.TITLE_LINES + f"Abstract\n{abstract}\n{caption}\n1 Introduction\n{words(200)}\n"
        left = f"A synthetic pa\nAuthor One\nAbstract\n{abstract}\n1\n\nw\n\nIntroduction\n{words(60)}\n"
        right = f"per on gauges\n, Author Two\n{caption}\n{words(140)}\n"
        with TempDir() as root:
            env = pdf_tools(root)
            venue = page(root, "two.pdf", full, (left, right))
            d = check(root, corpus=venue, env=env)
            self.assertEqual(d["venue_abstracts"]["parsed_files"], {"two.pdf": 120})

    def test_a_caption_the_whole_page_puts_inside_the_abstract_does_not_send_it_back_to_the_whole_page(self):
        # Read whole, the caption breaks the abstract in two; the column still holds it whole.
        first, last, caption = words(60), words(61).split(" ", 1)[1], "Figure 1: " + words(40)
        full = self.TITLE_LINES + f"Abstract\n{first}\n{caption}\n{last}\n1 Introduction\n{words(200)}\n"
        left = f"A synthetic pa\nAuthor One\nAbstract\n{first}\n{last}\n1\n\nIntroduction\n{words(60)}\n"
        with TempDir() as root:
            env = pdf_tools(root)
            venue = page(root, "split.pdf", full, (left, f"per on gauges\n{caption}\n"))
            d = check(root, corpus=venue, env=env)
            self.assertEqual(d["venue_abstracts"]["parsed_files"], {"split.pdf": 120})

    def test_a_one_column_page_cut_down_the_middle_is_read_whole_instead(self):
        # Each line of a one-column page is cut in two by the crop; its halves do not run through the page's text.
        lines = [words(16).split()[i % 3:] + [f"w{i}"] for i in range(10)]
        whole = "\n".join(" ".join(x) for x in lines)
        halves = "\n".join(" ".join(x[:len(x) // 2]) for x in lines)
        n = sum(len(x) for x in lines)
        full = self.TITLE_LINES + f"Abstract\n{whole}\n1 Introduction\n{words(200)}\n"
        left = f"A synthetic\nAuthor One\nAbstract\n{halves}\n1 Introd\n{words(60)}\n"
        with TempDir() as root:
            env = pdf_tools(root)
            venue = page(root, "one.pdf", full, (left, ""))
            d = check(root, corpus=venue, env=env)
            self.assertEqual(d["venue_abstracts"]["parsed_files"], {"one.pdf": n})

    def test_stray_glyphs_between_the_section_number_and_introduction_still_end_the_abstract(self):
        with TempDir() as root:
            d = Path(root) / "venue"
            d.mkdir()
            (d / "glyphs.txt").write_text(self.TITLE_LINES + f"Abstract\n{words(90)}\n1\n\nT\n\nIntroduction\n"
                                          + words(300) + "\n", encoding="utf-8")
            (d / "footnote.txt").write_text(self.TITLE_LINES + f"Abstract\n{words(90)}\n1\nhttps://example.org/code\n"
                                            + words(300) + "\n", encoding="utf-8")
            v = check(root, corpus=d)["venue_abstracts"]
            self.assertEqual(v["parsed_files"], {"glyphs.txt": 90})
            self.assertEqual([x["file"] for x in v["skipped"]], ["footnote.txt"])


class FrontMatterLoopTest(unittest.TestCase):
    def test_the_check_is_in_the_catalogue_for_latex(self):
        [c] = [c for c in K.CHECKS if c["id"] == "front-matter"]
        self.assertEqual((c["formats"], c["needs"], c.get("tree")), (["latex"], [], True))

    def test_the_loop_says_when_there_was_no_abstract_to_check(self):
        with TempDir() as root:
            check(root, abstract=None)
            self.assertEqual(V.interpret("front-matter", 0, run_json(root), ""), ("ok", "没找到摘要，没查"))

    def test_the_loop_names_both_kinds(self):
        with TempDir() as root:
            check(root, abstract=ODD.replace("an early warning", "a warning"))
            self.assertEqual(V.interpret("front-matter", 1, run_json(root), ""),
                             ("findings", "标题词摘要里没有 1（early）；自造名首现没说是什么 1（GaugeBench）；摘要 25 词"))

    def test_the_loop_says_what_a_clean_abstract_was_checked_for(self):
        with TempDir() as root:
            check(root)
            self.assertEqual(V.interpret("front-matter", 0, run_json(root), ""),
                             ("ok", "标题词都在摘要里；自造名 1 个首现都说了是什么；摘要 27 词"))


def run_json(root):
    root = Path(root)
    return subprocess.run([sys.executable, str(SCRIPTS / "audit-front-matter.py"), "--root", str(root), "--json",
                           str(root / "main.tex")], capture_output=True, text=True).stdout


if __name__ == "__main__":
    unittest.main()
