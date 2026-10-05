"""audit-abstract-numbers.py: quantities in the abstract against the venue's abstracts
(spec 2026-10-05-abstract-numbers). Synthetic prose only."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K

from fixtures import TempDir

# AWT_AUDIT_DIR: the mutated copy a red check is testing; otherwise the audit skill in this checkout.
SCRIPTS = Path(os.environ.get("AWT_AUDIT_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "audit" / "scripts")

# Five quantities (2,417 / 0.85 / 23% / 12.5x / 40), one year, three names with digits, three list markers, one
# numbered citation and one date.
PLANTED = ("We ran BM25, GPT-4o and Recall@10 on 2,417 pages scanned in 2019. The method (1) reads each page, (2) "
           "ranks the candidates and (3) reports 0.85 precision, 23% fewer errors and 12.5x the speed of the "
           "40 baselines [12], as of March 28, 2021.")
WORDS = ("The survey describes how libraries catalogue their maps and what readers ask of them. It reports one "
         "finding in plain words and leaves the detail to the body of the paper, where each table is explained "
         "and every source is named for the reader who wants to check it.")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "audit-abstract-numbers.py"), *map(str, args)],
                          capture_output=True, text=True)


def corpus(root, n=20, numbers=1):
    d = Path(root) / "venue"
    d.mkdir()
    for i in range(n):
        figures = " ".join(f"It found {10 + j} cases." for j in range(numbers))
        (d / f"paper{i:02d}.txt").write_text(
            f"A Paper Title {i}\nSomeone, Somewhere\n\nAbstract\n{WORDS} {figures}\n\nKeywords: maps\n\n"
            f"1 Introduction\nBody text.\n", encoding="utf-8")
    return d


def tex(root, abstract, name="main.tex"):
    p = Path(root) / name
    p.write_text("\\documentclass{article}\n\\begin{document}\n\\begin{abstract}\n" + abstract.replace("%", "\\%") +
                 "\n\\end{abstract}\n\\section{Introduction}\nBody.\n\\end{document}\n", encoding="utf-8")
    return p


class AbstractNumbersTest(unittest.TestCase):
    def test_quantities_are_counted_apart_from_years_names_markers_citations_and_dates(self):
        with TempDir() as root:
            r = run("--baseline", corpus(root), "--json", tex(root, PLANTED))
            self.assertIn(r.returncode, (0, 1), r.stderr)
            a = json.loads(r.stdout)["abstract"]
            self.assertEqual([q["text"] for q in a["quantities"]], ["2,417", "0.85", "23%", "12.5x", "40"])
            self.assertEqual(a["years"], 1)
            self.assertEqual(a["names_with_digits"], 3)
            self.assertIn("[0.85]", a["quantities"][1]["context"], "each quantity is shown in its context")

    def test_an_abstract_above_the_venues_90th_percentile_is_a_prompt_and_one_inside_is_not(self):
        with TempDir() as root:
            base = corpus(root)
            r = run("--baseline", base, "--json", tex(root, PLANTED))
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            got = json.loads(r.stdout)
            self.assertEqual(got["findings"][0]["kind"], "abstract-numbers-above-venue")
            self.assertIn("超过 P90", got["summary_zh"])
            r = run("--baseline", base, "--json", tex(root, WORDS + " It found 12 cases.", "same.tex"))
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["findings"], [])

    def test_a_venue_abstract_the_extractor_cannot_find_is_missed_not_zero(self):
        with TempDir() as root:
            base = corpus(root, numbers=3)
            (base / "noheading.txt").write_text("A Paper\n\n" + WORDS + "\n\n1 Introduction\nBody.\n", encoding="utf-8")
            got = json.loads(run("--baseline", base, "--json", tex(root, PLANTED)).stdout)
            self.assertEqual(got["corpus"]["n"], 20)
            self.assertEqual(got["corpus"]["missed"], ["noheading.txt"])
            self.assertEqual(got["corpus"]["qty"]["min"], 3, "a missed abstract is not a zero in the baseline")

    def test_a_letter_spaced_heading_is_found(self):
        with TempDir() as root:
            base = corpus(root)
            (base / "smallcaps.txt").write_text("A Paper\n\nA BSTRACT\n" + WORDS + "\n\nKeywords: maps\n",
                                                encoding="utf-8")
            got = json.loads(run("--baseline", base, "--json", tex(root, PLANTED)).stdout)
            self.assertEqual(got["corpus"]["n"], 21)
            self.assertEqual(got["corpus"]["missed"], [])

    def test_a_markdown_draft_is_read_under_its_abstract_heading(self):
        with TempDir() as root:
            p = Path(root) / "draft.md"
            p.write_text("# Title\n\n## Abstract\n\n" + PLANTED + "\n\n## 1 Introduction\n\nIt found 99 cases.\n",
                         encoding="utf-8")
            got = json.loads(run("--baseline", corpus(root), "--json", p).stdout)
            self.assertEqual(got["abstract"]["qty"], 5, "the introduction's number is not the abstract's")

    def test_nothing_to_measure_and_a_thin_baseline_exit_2(self):
        with TempDir() as root:
            p = Path(root) / "noabstract.tex"
            p.write_text("\\section{Introduction}\nIt found 12 cases.\n", encoding="utf-8")
            r = run("--baseline", corpus(root), p)
            self.assertEqual(r.returncode, 2)
            self.assertIn("nothing measured is not a pass", r.stderr)
        with TempDir() as root:
            r = run("--baseline", corpus(root, n=5), tex(root, PLANTED))
            self.assertEqual(r.returncode, 2)
            self.assertIn("no percentile below 20", r.stderr)

    def test_the_catalogue_runs_it_on_the_abstract_against_the_venue_corpus(self):
        c = K.by_id("abstract-numbers")
        self.assertEqual(c["scripts"], ["audit/audit-abstract-numbers.py"])
        self.assertIn("target.venue_corpus.dir", c["needs"])
        self.assertEqual(c["scope"]["kind"], "sections")
        self.assertEqual(c["scope"]["default"], ["A"])
        cfg = {"target": {"venue_corpus": {"dir": "/corpus"}}}
        argv = c["argv"]({"cfg": cfg, "drafts": ["main.tex", "sections/intro.tex"], "inputs": {}})
        self.assertEqual(argv[-2:], ["main.tex", "sections/intro.tex"])
        self.assertIn("/corpus", argv)


if __name__ == "__main__":
    unittest.main()
