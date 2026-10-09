"""reconcile-cites.py: an author named in the sentence and printed again by the citation, in a style that prints
author names (spec 2026-10-05-probe-growth, batch 2). "Smith et al. report ... \\citep{smith}" reads "Smith et al.
report ... (Smith et al., 2020)". Synthetic LaTeX only."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K

from fixtures import TempDir

# AWT_VERIFY-REFS_DIR: the mutated copy a red check is testing; otherwise the skill in this checkout.
SCRIPTS = Path(os.environ.get("AWT_VERIFY-REFS_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "verify-refs" / "scripts")

BIB = """@article{smith2020,
  author = {Smith, Ann and Jones, Ben and Lee, Cal},
  title = {Gauge drift before floods},
  journal = {Hydrology Letters},
  year = {2020}
}
@article{muller2019,
  author = {M{\\"u}ller, Dora},
  title = {Tidal gauges},
  journal = {Coastal Notes},
  year = {2019}
}
@article{long2018,
  author = {Long, Eve},
  title = {Records of drift},
  journal = {Hydrology Letters},
  year = {2018}
}
@misc{agency2021,
  author = {{River Agency}},
  title = {Gauge records},
  year = {2021}
}
"""
NATBIB = "\\usepackage{natbib}\n"
TWICE = "Smith et al. report that drift rose before most floods~\\citep{smith2020}."


def check(root, body, preamble=NATBIB, style="plainnat", extra=(), cls="article"):
    root = Path(root)
    (root / "references.bib").write_text(BIB, encoding="utf-8")
    cites = "\\nocite{muller2019,agency2021,smith2020,long2018}\n"
    (root / "main.tex").write_text(f"\\documentclass{{{cls}}}\n{preamble}\\begin{{document}}\n{body}\n{cites}"
                                   f"\\bibliographystyle{{{style}}}\n\\bibliography{{references}}\n\\end{{document}}\n",
                                   encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "reconcile-cites.py"), "--bib", str(root / "references.bib"),
                        "--root", str(root), "--json", *extra, str(root / "main.tex")], capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr[-400:]
    d = json.loads(r.stdout)
    assert (r.returncode == 1) == bool(d["issues"]), (r.returncode, d["issues"])
    return d


def twice(d):
    return [(i["key"], i["name"]) for i in d["issues"] if i["kind"] == "author-named-twice"]


class AuthorNamedTwiceTest(unittest.TestCase):
    def test_a_name_in_the_sentence_and_in_an_author_year_citation_is_reported(self):
        with TempDir() as root:
            d = check(root, TWICE)
            self.assertEqual(twice(d), [("smith2020", "Smith")])
            self.assertEqual(d["citation_style"], "author-year")
            [i] = [i for i in d["issues"] if i["kind"] == "author-named-twice"]
            self.assertTrue(i["location"].endswith("main.tex:4"), i["location"])

    def test_a_numeric_style_prints_no_name_and_is_not_checked(self):
        for preamble, style in ((NATBIB, "plain"), ("\\usepackage[numbers]{natbib}\n", "plainnat"),
                                ("\\usepackage{natbib}\n\\setcitestyle{numbers}\n", "plainnat")):
            with self.subTest(preamble=preamble, style=style), TempDir() as root:
                d = check(root, TWICE, preamble=preamble, style=style)
                self.assertEqual((d["citation_style"], twice(d)), ("numeric", []))

    def test_acmart_is_numeric_unless_set_to_author_year(self):
        with TempDir() as root:
            d = check(root, TWICE, preamble="", style="ACM-Reference-Format", cls="acmart")
            self.assertEqual((d["citation_style"], twice(d)), ("numeric", []))
            d = check(root, TWICE, preamble="\\citestyle{acmauthoryear}\n", style="ACM-Reference-Format", cls="acmart")
            self.assertEqual((d["citation_style"], twice(d)), ("author-year", [("smith2020", "Smith")]))

    def test_a_style_it_cannot_tell_is_said_and_not_checked(self):
        with TempDir() as root:
            d = check(root, TWICE, preamble="", style="custom-house")
            self.assertEqual((d["citation_style"], twice(d)), ("unknown", []))

    def test_the_style_the_class_and_packages_set_is_read(self):
        cases = (("\\usepackage[natbibapa]{apacite}\n", "apacite", "author-year"),
                 ("\\usepackage[style=authoryear]{biblatex}\n", "plain", "author-year"),
                 ("\\usepackage[style=numeric]{biblatex}\n", "plain", "numeric"),
                 ("\\usepackage[authoryear]{natbib}\n", "plain", "author-year"))
        for preamble, style, want in cases:
            with self.subTest(preamble=preamble), TempDir() as root:
                self.assertEqual(check(root, TWICE, preamble=preamble, style=style)["citation_style"], want)

    def test_the_workspace_can_name_the_style_the_submission_prints(self):
        with TempDir() as root:
            d = check(root, TWICE, style="plain", extra=("--style", "author-year"))
            self.assertEqual((d["citation_style"], d["citation_style_from"], twice(d)),
                             ("author-year", "--style", [("smith2020", "Smith")]))

    def test_the_name_said_once_is_not_reported(self):
        for body in ("\\citet{smith2020} report that drift rose before most floods.",
                     "Smith et al.~\\citeyearpar{smith2020} report that drift rose before most floods.",
                     "Drift rose before most floods~\\citep{smith2020}.",
                     "Unlike \\citet{smith2020}, we find drift rose late~\\citep{muller2019}."):
            with self.subTest(body=body), TempDir() as root:
                self.assertEqual(twice(check(root, body)), [])

    def test_two_name_printing_citations_of_one_key_in_a_sentence_are_reported(self):
        with TempDir() as root:
            body = "\\citeauthor{smith2020} report that drift rose before most floods~\\citep{smith2020}."
            self.assertEqual(twice(check(root, body)), [("smith2020", "Smith")])

    def test_an_accented_or_corporate_author_is_matched(self):
        for body, want in (("As M\\\"uller shows, the tides lag~\\citep{muller2019}.", ("muller2019", "Muller")),
                           ("As Müller shows, the tides lag~\\citep{muller2019}.", ("muller2019", "Muller")),
                           ("The River Agency keeps the records~\\citep{agency2021}.", ("agency2021", "River Agency"))):
            with self.subTest(body=body), TempDir() as root:
                self.assertEqual(twice(check(root, body)), [want])

    def test_a_capitalised_word_that_opens_the_sentence_is_not_read_as_the_name(self):
        for body, want in (("Long records show drift before floods~\\citep{long2018}.", []),
                           ("As Long shows, records drift before floods~\\citep{long2018}.", [("long2018", "Long")]),
                           ("Long and colleagues show drift before floods~\\citep{long2018}.", [("long2018", "Long")])):
            with self.subTest(body=body), TempDir() as root:
                self.assertEqual(twice(check(root, body)), want)

    def test_a_name_that_names_a_method_is_not_read_as_the_authors(self):
        for body, want in (("Hits are compared with Smith's exact test~\\citep{smith2020}.", []),
                           ("Ranks use the Smith signed-rank test~\\citep{smith2020}.", []),
                           ("Bounds in the sense of Smith~\\citep{smith2020} are reported.", [("smith2020", "Smith")]),
                           ("As Smith's study shows, drift rose~\\citep{smith2020}.", [("smith2020", "Smith")])):
            with self.subTest(body=body), TempDir() as root:
                self.assertEqual(twice(check(root, body)), want)

    def test_sentences_are_read_one_at_a_time(self):
        with TempDir() as root:
            body = "Smith et al.\\ report drift. Later work confirms it~\\citep{smith2020}."
            self.assertEqual(twice(check(root, body)), [])


class MacroDefinitionTest(unittest.TestCase):
    """A citation inside a macro definition is the macro's body, not a citation: \\newcommand{\\mycite}[1]{\\citep{#1}}
    reported "#1" as cited and not in the bibliography. Definitions and their bodies are skipped, and a token that
    starts with a backslash or # is never a key. A key the text really cites and the bibliography lacks is still
    reported, also when it is cited through such a macro."""

    PREAMBLE = (NATBIB +
                "\\newcommand{\\mycite}[1]{\\citep{#1}}\n"
                "\\renewcommand\\citeA[2][]{\\citeauthor[#1]{#2}}\n"
                "\\providecommand*{\\pcite}{\\citet{\\thekey}}\n"
                "\\DeclareRobustCommand{\\rcite}[1]{\\cite{#1, \\extra}}\n"
                "\\def\\dcite#1#2{\\citep[#1]{#2}}\n"
                "\\gdef\\gcite{\\cite{\\gkey}}\n"
                "\\let\\oldcite\\cite\n"
                "\\let\\olderp = \\citep\n"
                "\\newcommand{\\wrapped}{\\}\\citep{example-key}}\n"
                "\\newcommand{\\ours}{\\citet{long2018}}\n"
                "\\let\\olderp\\citep\n{gauge readings}\n"
                "{\\catcode`\\@=11 \\def\\nest{{\\cite{#9}}\n and {\\citet{#8}}}}\n")

    def issues(self, d, kind):
        return sorted(i["key"] for i in d["issues"] if i["kind"] == kind)

    def test_definitions_are_skipped_and_a_real_missing_key_is_still_reported(self):
        with TempDir() as root:
            body = "Gauges drift~\\mycite{smith2020}. Records agree~\\citep{nosuch2022}. Tides too~\\mycite{absent2017}."
            d = check(root, body, preamble=self.PREAMBLE)
            self.assertEqual(self.issues(d, "cited-not-in-bib"), ["absent2017", "nosuch2022"], d["issues"])
            self.assertEqual(self.issues(d, "bib-not-cited"), [])
            self.assertEqual(d["definition_keys"], ["example-key", "long2018"])

    def test_a_key_written_in_a_definition_counts_as_cited(self):
        """\\newcommand{\\ours}{\\citet{long2018}} used in the text cites long2018: blanking the definition must not
        turn it into an entry nothing reads."""
        with TempDir() as root:
            root = Path(root)
            (root / "references.bib").write_text(BIB, encoding="utf-8")
            (root / "main.tex").write_text(
                "\\documentclass{article}\n\\newcommand{\\ours}{\\citet{long2018}}\n\\begin{document}\n"
                "As \\ours\\ shows, drift rose~\\citep{smith2020,muller2019,agency2021}.\n\\end{document}\n", encoding="utf-8")
            r = subprocess.run([sys.executable, str(SCRIPTS / "reconcile-cites.py"), "--bib", str(root / "references.bib"),
                                "--json", str(root / "main.tex")], capture_output=True, text=True)
            d = json.loads(r.stdout)
            self.assertEqual(d["issues"], [])
            self.assertEqual(r.returncode, 0)

    def test_a_backslash_or_hash_token_is_never_a_key(self):
        with TempDir() as root:
            body = "Drift rose~\\citep{smith2020, \\somekey, #3}. Floods followed~\\citep{#1}."
            d = check(root, body)
            self.assertEqual(self.issues(d, "cited-not-in-bib"), [], d["issues"])

    def test_line_numbers_after_a_definition_are_unchanged(self):
        with TempDir() as root:
            d = check(root, "Records agree~\\citep{nosuch2022}.", preamble=self.PREAMBLE)
            [i] = [i for i in d["issues"] if i["kind"] == "cited-not-in-bib"]
            want = 1 + self.PREAMBLE.count("\n") + 2  # \\documentclass, the preamble, \\begin{document}, the body
            self.assertTrue(i["location"].endswith(f"main.tex:{want}"), (i["location"], want))


class CitationStyleSettingTest(unittest.TestCase):
    def test_the_workspace_setting_reaches_the_script(self):
        [c] = [c for c in K.CHECKS if c["id"] == "cite-bib"]
        self.assertIn("target.citation_style", c["config_keys"])
        self.assertEqual(K._citation_style({"target": {"citation_style": "author-year"}}), ["--style", "author-year"])
        self.assertEqual(K._citation_style({}), [])


if __name__ == "__main__":
    unittest.main()
