"""Scan coverage: a heading no rule matches is said, by name, instead of leaving the index in silence; and the overreach
scan reads the files submitted with the draft and the text inside figure sources. Synthetic wording throughout."""
import json
import unittest
from pathlib import Path

from loop import config as C
from loop import coverage as V
from loop import history as H
from loop import state as S
from loop import text as T

from fixtures import TempDir, git, make_repo, workspace

MAIN = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We audit a bridge survey with gauges on two bridges.
\end{abstract}
\input{sections/01_intro}
\input{sections/02_method}
\end{document}
"""
INTRO = r"""\section{Introduction}\label{sec:intro}
Gauges on two bridges read 12 points. We do not test whether drivers notice.
"""
# A section renamed after the config was written: its rule no longer matches.
METHOD = r"""\section{How the Gauges Were Read}\label{sec:method}
Each gauge was read at dawn by two surveyors who wrote the value on a card, and the cards were checked against
the logger before anyone saw the totals, so a copying slip would show as a mismatch between card and logger~\cite{k1}.
Only the span length differs between the two bridges.
"""
FIG = r"""\begin{tikzpicture}[font=\sffamily]
\node[lab] at (0,0) {\textbf{Span}\;\; two bridges\\ \textit{only the span length differs between them}};
\end{tikzpicture}
"""
SUPP = r"""\section{Extra Readings}
The night readings agree. Only the span length differs, as in the main text.
"""
RULES = [{"match": r"^Abstract$", "prefix": "A", "kind": "prose", "flat": True},
         {"match": r"^Introduction$", "prefix": "I", "kind": "prose"}]

LEDGER = """# 主张清单
阶段：分析

## 主张 C1 两座桥的读数是 12
- 证据：表 1
- 强度：强
- 允许的说法：两座桥
- 越界：only the span length differs
- 必须出现：do not test whether drivers
"""


def setup(root, files=None, rules=RULES, ignore=None, also_scanned=None, also_checked=None):
    files = files or {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD,
                      "figures/fig_span.tex": FIG, "supplement.tex": SUPP}
    repo = make_repo(root, [(files, "v1", 1_700_000_000)])
    ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex", "sections/02_method.tex"])
    cfg = C.load(ws)
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = rules
    if ignore is not None:
        cfg["draft"]["ignore_headings"] = ignore
    cfg.setdefault("inputs", {})
    if also_scanned is not None:
        cfg["inputs"]["also_scanned"] = also_scanned
    if also_checked is not None:
        cfg["inputs"]["also_checked"] = also_checked
    p = Path(root) / "claims.md"
    p.write_text(LEDGER, encoding="utf-8")
    cfg["claims"] = str(p)
    C.save(ws, cfg)
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    head = git(cfg["repo"], "rev-parse", "HEAD")
    (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
    return ws, C.load(ws)


def scan_row(summary):
    return next((r for r in summary["rows"] if r["id"] == "_scan"), None)


class SectionCoverageTest(unittest.TestCase):
    def test_a_heading_no_rule_matches_is_named_with_its_words(self):
        cov = T.section_coverage(MAIN.replace(r"\input{sections/01_intro}", INTRO).replace(r"\input{sections/02_method}", METHOD),
                                 RULES, "latex")
        self.assertEqual([m["heading"] for m in cov["missing"]], ["How the Gauges Were Read"])
        self.assertGreaterEqual(cov["missing"][0]["words"], 20)
        self.assertGreater(cov["kept"], 0)

    def test_citation_keys_and_command_names_are_not_words(self):
        self.assertEqual(T.prose_words(r"\section{X} two words~\cite{zzz2020abc}\label{sec:q}"), 2 + 1)  # "X" is text
        self.assertEqual(T.prose_words(r"\textbf{bold} plain"), 2)

    def test_an_ignored_heading_is_counted_apart_not_as_missing(self):
        text = INTRO + METHOD
        cov = T.section_coverage(text, RULES, "latex", ignore=[r"^How the Gauges"])
        self.assertEqual(cov["missing"], [])
        self.assertGreater(cov["ignored"], 0)


class ScanRowTest(unittest.TestCase):
    def test_a_renamed_section_fails_the_row_and_names_the_heading(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            row = scan_row(V.compute(cfg, ws))
            self.assertIsNotNone(row)
            self.assertEqual(row["status"], V.FAILED)
            self.assertIn("How the Gauges Were Read", row["detail"])
            self.assertIn("扫描覆盖", V.live_line(ws, cfg))

    def test_a_matching_rule_or_an_ignore_rule_makes_the_row_current(self):
        with TempDir() as root:
            ws, cfg = setup(root, rules=RULES + [{"match": r"^How the Gauges", "prefix": "M", "kind": "prose"}])
            self.assertEqual(scan_row(V.compute(cfg, ws))["status"], V.OK)
        with TempDir() as root:
            ws, cfg = setup(root, ignore=[r"^How the Gauges"])
            row = scan_row(V.compute(cfg, ws))
            self.assertEqual(row["status"], V.OK)
            self.assertIn("不扫", row["detail"])

    def test_a_short_unmatched_heading_is_shown_but_does_not_fail(self):
        tiny = METHOD.split("\n")[0] + "\nA short note.\n"
        with TempDir() as root:
            ws, cfg = setup(root, files={"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": tiny})
            row = scan_row(V.compute(cfg, ws))
            self.assertEqual(row["status"], V.OK)
            self.assertIn("How the Gauges Were Read", row["detail"])


class ExtraScanTest(unittest.TestCase):
    RULES_ALL = RULES + [{"match": r"^How the Gauges", "prefix": "M", "kind": "prose"}]

    def test_a_forbidden_wording_in_a_figure_source_is_found_with_its_file(self):
        body = METHOD.replace("Only the span length differs between the two bridges.\n", "")
        files = {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": body,
                 "figures/fig_span.tex": FIG}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL)
            self.assertEqual(S.compute(cfg, ws)["over"], [])  # red without the list
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, also_scanned=["figures/*.tex"])
            [o] = S.compute(cfg, ws)["over"]
            self.assertEqual(o["claim"], "C1")
            self.assertTrue(all(l.startswith("figures/fig_span.tex:") for l in o["labels"]), o)

    def test_the_supplement_already_listed_as_also_checked_is_scanned(self):
        body = METHOD.replace("Only the span length differs between the two bridges.\n", "")
        files = {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": body, "supplement.tex": SUPP}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, also_checked=["supplement.tex"])
            [o] = S.compute(cfg, ws)["over"]
            self.assertTrue(all(l.startswith("supplement.tex:") for l in o["labels"]), o)

    def test_a_required_wording_found_only_in_an_extra_file_is_still_absent(self):
        body = INTRO.replace("We do not test whether drivers notice.", "")
        fig = FIG.replace("only the span length differs between them", "we do not test whether drivers notice")
        files = {"main.tex": MAIN, "sections/01_intro.tex": body, "sections/02_method.tex": METHOD,
                 "figures/fig_span.tex": fig}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, also_scanned=["figures/*.tex"])
            self.assertEqual([a["claim"] for a in S.compute(cfg, ws)["absent"]], ["C1"])

    def test_a_listed_file_that_is_not_there_is_said(self):
        with TempDir() as root:
            ws, cfg = setup(root, rules=self.RULES_ALL, also_scanned=["figures/missing.tex"])
            st = S.compute(cfg, ws)
            self.assertTrue(any("figures/missing.tex" in p for p in st["problems"]), st["problems"])


if __name__ == "__main__":
    unittest.main()
