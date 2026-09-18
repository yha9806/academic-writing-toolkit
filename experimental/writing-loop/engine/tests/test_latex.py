"""LaTeX drafts made of several files: the abstract environment and chosen (sub)sections become sentences."""
import unittest

from loop import history as H
from loop.text import latex_sections, sentences_of

from fixtures import TempDir, git, make_repo, workspace

MAIN = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We audit a bridge survey. It has two sentences. % a comment that must vanish
\end{abstract}
\input{sections/05_results}
\end{document}
"""
RESULTS = r"""\section{Results}\label{sec:results}
Intro to results.

\subsection{Load as a Stress Control}\label{sec:xling}
The first gauge reads 5\% of the plan. The second gauge is small.

A new paragraph here.

\subsection{Next Part}
Not tracked.
"""
RULES = [{"match": r"^Abstract$", "prefix": "A", "kind": "prose", "flat": True},
         {"match": r"^Load as a Stress Control$", "prefix": "X", "kind": "prose"}]


class LatexTest(unittest.TestCase):
    def test_sections_and_comments(self):
        secs = dict(latex_sections(MAIN + RESULTS))
        self.assertEqual(set(secs), {"Abstract", "Results", "Load as a Stress Control", "Next Part"})
        self.assertNotIn("comment", secs["Abstract"])
        self.assertIn(r"5\% of the plan", secs["Load as a Stress Control"])

    def test_only_the_chosen_sections_become_sentences(self):
        s = sentences_of(MAIN + "\n\n" + RESULTS, RULES, "latex")
        self.assertEqual([x["label"] for x in s], ["A01", "A02", "X1.1", "X1.2", "X2.1"])
        self.assertEqual(s[2]["text"], r"The first gauge reads 5\% of the plan.")

    def test_malformed_latex_does_not_crash_and_yields_nothing_for_missing_sections(self):
        for bad in ("", r"\begin{abstract} never closed", r"\section{unbalanced", "%" * 50):
            self.assertEqual(sentences_of(bad, RULES, "latex"), [])


class MultiFileTest(unittest.TestCase):
    def test_a_commit_to_either_file_is_a_new_version_of_one_draft(self):
        with TempDir() as root:
            repo = make_repo(root, [({"main.tex": MAIN, "sections/05_results.tex": RESULTS}, "v1", 1_700_000_000),
                                    ({"notes.md": "unrelated"}, "notes", 1_700_000_100),
                                    ({"sections/05_results.tex": RESULTS.replace("is small", "is tiny")}, "v2", 1_700_000_200),
                                    ({"main.tex": MAIN.replace("two sentences", "three sentences")}, "v3", 1_700_000_300)])
            ws = workspace(root, repo, "main", glob=["main.tex", "sections/05_results.tex"])
            from loop import config as C
            cfg = C.load(ws)
            cfg["draft"]["format"] = "latex"
            cfg["draft"]["sections"] = RULES
            vs = H.load_versions(cfg)
            self.assertEqual([v["subject"] for v in vs], ["v1", "v2", "v3"])
            self.assertEqual(vs[0]["path"], "main.tex+sections/05_results.tex")
            self.assertIn("The second gauge is tiny.", [s["text"] for s in vs[1]["sentences"]])
            H.assign_ids(vs)
            self.assertEqual(vs[0]["sentences"][0]["sid"], vs[2]["sentences"][0]["sid"])


if __name__ == "__main__":
    unittest.main()
