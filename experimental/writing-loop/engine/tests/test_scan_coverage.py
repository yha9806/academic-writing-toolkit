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
            self.assertEqual(o["labels"], ["figures/fig_span.tex#1"])

    def test_the_supplement_already_listed_as_also_checked_is_scanned(self):
        body = METHOD.replace("Only the span length differs between the two bridges.\n", "")
        files = {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": body, "supplement.tex": SUPP}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, also_checked=["supplement.tex"])
            [o] = S.compute(cfg, ws)["over"]
            self.assertEqual(o["labels"], ["supplement.tex#2"])

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
            self.assertTrue(any("figures/missing.tex" in p for p in st["scan_problems"]), st["scan_problems"])
            self.assertEqual(st["problems"], [])  # a missing figure is not an unreadable ledger
            self.assertIn("额外扫描读不到 1 处", S.line(st))


class GrillFindingsTest(unittest.TestCase):
    """One test per defect the 2026-09-24 review found; each was reproduced on the first version before the fix."""
    RULES_ALL = RULES + [{"match": r"^How the Gauges", "prefix": "M", "kind": "prose"}]
    BODY = METHOD.replace("Only the span length differs between the two bridges.\n", "")

    def files(self, fig=FIG, extra=None):
        f = {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": self.BODY,
             "figures/fig_span.tex": fig}
        f.update(extra or {})
        return f

    def over(self, files, **kw):
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, **kw)
            st = S.compute(cfg, ws)
            return st["over"], st["scan_problems"], st

    def test_latex_spellings_of_the_phrase_are_still_found(self):
        for spelled in [r"only~the span length differs", r"only the span\\[2pt] length differs",
                        r"only the \textbf{span} length differs", r"only the span\\ length differs"]:
            fig = FIG.replace("only the span length differs between them", spelled)
            over, probs, _ = self.over(self.files(fig), also_scanned=["figures/*.tex"])
            self.assertEqual(len(over), 1, spelled)
        self.assertEqual(T.tex_plain(r"12\% of R\&D"), "12% of R&D")

    def test_a_comment_after_a_line_break_is_not_text(self):
        fig = FIG.replace("only the span length differs between them", r"two\\% only the span length differs")
        over, _, _ = self.over(self.files(fig), also_scanned=["figures/*.tex"])
        self.assertEqual(over, [])

    def test_a_directory_is_expanded_not_scanned_as_a_listing(self):
        for spec in ("figures", "figures/"):
            over, probs, _ = self.over(self.files(), also_scanned=[spec])
            self.assertEqual([o["labels"] for o in over], [["figures/fig_span.tex#1"]], spec)

    def test_star_stays_in_one_directory_and_double_star_spans(self):
        nested = {"figures/old/unused.tex": FIG}
        over, _, _ = self.over(self.files(extra=nested), also_scanned=["figures/*.tex"])
        self.assertEqual(over[0]["labels"], ["figures/fig_span.tex#1"])
        over, _, _ = self.over(self.files(extra=nested), also_scanned=["figures/**/*.tex"])
        self.assertEqual(sorted(over[0]["labels"]), ["figures/fig_span.tex#1", "figures/old/unused.tex#1"])

    def test_draft_files_matched_by_a_glob_are_not_scanned_twice(self):
        files = self.files()
        files["sections/02_method.tex"] = METHOD
        over, _, _ = self.over(files, also_scanned=["**/*.tex"])
        [o] = over
        self.assertEqual([l for l in o["labels"] if l.startswith("sections/")], [])

    def test_a_list_written_as_a_string_is_said_not_split_into_characters(self):
        _, probs, _ = self.over(self.files(), also_scanned="figures/fig_span.tex")
        self.assertEqual(len(probs), 1)
        self.assertIn("列表", probs[0])

    def test_extra_files_are_read_at_the_index_commit_not_at_head(self):
        with TempDir() as root:
            ws, cfg = setup(root, files=self.files(), rules=self.RULES_ALL, also_scanned=["figures/*.tex"])
            repo = cfg["repo"]
            (Path(repo) / "figures" / "fig_span.tex").write_text(FIG.replace("only the span length differs between them", "two bridges"), encoding="utf-8")
            git(repo, "commit", "-qam", "v2")
            self.assertEqual(len(S.compute(cfg, ws)["over"]), 1)  # the index is still at v1

    def test_the_word_threshold_is_twenty(self):
        for n, status in ((19, V.OK), (20, V.FAILED)):
            body = r"\section{How the Gauges Were Read}" + "\n" + " ".join(["word"] * n) + "\n"
            with TempDir() as root:
                ws, cfg = setup(root, files={"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": body})
                self.assertEqual(scan_row(V.compute(cfg, ws))["status"], status, n)

    def test_a_bad_ignore_list_fails_the_row_and_does_not_break_the_summary(self):
        for bad in ("^How", ["^How the (Gauges"]):
            with TempDir() as root:
                ws, cfg = setup(root, ignore=bad)
                row = scan_row(V.compute(cfg, ws))
                self.assertEqual(row["status"], V.FAILED, bad)
                self.assertIn("draft.ignore_headings", row["detail"])

    def test_a_markdown_draft_without_level_two_headings_is_not_read_as_empty(self):
        md = "# Survey\n\n" + " ".join(["gauge"] * 30) + "\n\n# Method\n\nMore words here.\n"
        cov = T.section_coverage(md, [{"match": "^Abstract$", "prefix": "A", "kind": "prose"}], "markdown")
        self.assertEqual(cov["kept"], 0)
        self.assertGreaterEqual(cov["before_first"], 20)
        row = V.scan_row({**cov, "min_words": V.SCAN_MIN_WORDS})
        self.assertEqual(row["status"], V.FAILED)
        self.assertIn("一个词也没保留", row["detail"])

    def test_cjk_text_counts(self):
        self.assertEqual(T.prose_words("桥梁读数两座"), 6)

    def test_an_input_file_the_config_does_not_list_fails_the_row(self):
        main = MAIN.replace(r"\input{sections/02_method}", r"\input{sections/02_method}" + "\n" + r"\input{sections/03_more}")
        files = {"main.tex": main, "sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD,
                 "sections/03_more.tex": r"\section{Introduction}" + "\nMore.\n"}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL)
            row = scan_row(V.compute(cfg, ws))
            self.assertEqual(row["status"], V.FAILED)
            self.assertIn("sections/03_more.tex", row["detail"])

    def test_an_input_listed_as_also_scanned_is_accounted_for(self):
        main = MAIN.replace(r"\input{sections/02_method}", r"\input{sections/02_method}" + "\n" + r"\input{figures/fig_span}")
        files = {"main.tex": main, "sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD, "figures/fig_span.tex": FIG}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL)
            self.assertIn("figures/fig_span.tex", scan_row(V.compute(cfg, ws))["detail"])
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, also_scanned=["figures/*.tex"])
            self.assertEqual(scan_row(V.compute(cfg, ws))["status"], V.OK)

    def test_changing_the_ignore_list_makes_the_summary_stale(self):
        with TempDir() as root:
            ws, cfg = setup(root)
            before = V.fingerprint(cfg, ws)
            cfg["draft"]["ignore_headings"] = ["^How the Gauges"]
            self.assertNotEqual(V.fingerprint(cfg, ws), before)


class GrillRoundTwoTest(unittest.TestCase):
    """Second review round: each case was reproduced on the round-one fix before this change."""
    RULES_ALL = RULES + [{"match": r"^How the Gauges", "prefix": "M", "kind": "prose"}]

    def row_for(self, files, glob=None, **kw):
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, **kw)
            if glob:
                cfg["draft"]["glob"] = glob
                C.save(ws, cfg)
                cfg = C.load(ws)
            return scan_row(V.compute(cfg, ws))

    def test_inputs_in_every_spelling_are_resolved(self):
        base = {"sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD, "figures/fig_span.tex": FIG,
                "figures/fig_span.tikz": FIG, "figures/inner.tex": FIG}
        for line in [r"\input{./figures/fig_span}", r"\input figures/fig_span.tex", r"\input{figures/fig_span.tikz}",
                     r"\subfile{figures/fig_span}", r"\import{figures/}{fig_span}"]:
            main = MAIN.replace(r"\end{document}", line + "\n" + r"\end{document}")
            row = self.row_for({**base, "main.tex": main})
            self.assertEqual(row["status"], V.FAILED, line)
            self.assertIn("不在任何扫描列表里", row["detail"], line)

    def test_an_input_is_resolved_from_the_main_files_directory(self):
        main = MAIN.replace("sections/", "../sections/").replace(r"\end{document}", r"\input{figs/fig}" + "\n" + r"\end{document}")
        files = {"paper/main.tex": main, "sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD, "paper/figs/fig.tex": FIG}
        row = self.row_for(files, glob=["paper/main.tex", "sections/01_intro.tex", "sections/02_method.tex"])
        self.assertIn("paper/figs/fig.tex", row["detail"])

    def test_a_nested_input_inside_a_scanned_file_is_followed(self):
        outer = FIG + r"\input{figures/inner}" + "\n"
        main = MAIN.replace(r"\end{document}", r"\input{figures/fig_span}" + "\n" + r"\end{document}")
        files = {"main.tex": main, "sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD,
                 "figures/fig_span.tex": outer, "tables/inner.tex": FIG, "figures/inner.tex": FIG}
        row = self.row_for(files, also_scanned=["figures/fig_span.tex"])
        self.assertIn("figures/inner.tex", row["detail"])

    def test_journal_front_matter_before_the_first_heading_does_not_fail(self):
        front = (r"\title{A Survey of Two Bridges and Their Gauges Read at Dawn}" + "\n" +
                 r"\author{A. Surveyor and B. Surveyor, Department of Bridges, Some University, Some City}" + "\n" +
                 r"\keywords{bridges, gauges, surveying, dawn readings, loggers, cards}" + "\n" + r"\maketitle" + "\n")
        main = MAIN.replace(r"\begin{abstract}", front + r"\begin{abstract}")
        row = self.row_for({"main.tex": main, "sections/01_intro.tex": INTRO, "sections/02_method.tex": METHOD})
        self.assertEqual(row["status"], V.OK, row["detail"])
        self.assertIn("第一个标题之前", row["detail"])

    def test_a_file_with_a_chinese_name_is_scanned(self):
        body = METHOD.replace("Only the span length differs between the two bridges.\n", "")
        files = {"main.tex": MAIN, "sections/01_intro.tex": INTRO, "sections/02_method.tex": body, "figures/图一.tex": FIG}
        with TempDir() as root:
            ws, cfg = setup(root, files=files, rules=self.RULES_ALL, also_scanned=["figures/*.tex"])
            [o] = S.compute(cfg, ws)["over"]
            self.assertEqual(o["labels"], ["figures/图一.tex#1"])

    def test_the_landing_line_does_not_call_unchecked_work_passed(self):
        from loop import lintel as L
        self.assertTrue(L._checks_line({"rows": [{"name": "拼写", "status": V.STALE}]}).startswith("没看全 1"))
        self.assertEqual(L._checks_line({"rows": [], "stale_head": "abc"}), "检查算于旧版本")
        self.assertTrue(L._checks_line({"rows": [{"name": "扫描覆盖", "status": V.FAILED}]}).startswith("失败 1"))

    def test_inputs_of_the_wrong_shape_fail_the_row_without_raising(self):
        for bad in (["supplement.tex"], "supplement.tex"):
            with TempDir() as root:
                ws, cfg = setup(root, rules=self.RULES_ALL)
                cfg["inputs"] = bad
                row = scan_row(V.compute(cfg, ws))
                self.assertEqual(row["status"], V.FAILED)
                self.assertIn("inputs", row["detail"])
                S.compute(cfg, ws)
                V.fingerprint(cfg, ws)

    def test_more_latex_spellings(self):
        for spelled in [r"only the span\ length differs", r"only the span\\ [2pt] length differs",
                        r"only the sp\-an length differs", r"only the\hspace{1em} span length differs"]:
            self.assertIn("only the span length differs", T.tex_plain(spelled), spelled)

    def test_globs_skip_binary_files_and_take_character_classes(self):
        files = {"figures/a.tex", "figures/a.pdf", "figures/b.png", "tables/t1.tex", "tables/t3.tex"}
        [(_, names)] = T.resolve_listed(["figures/**"], files)
        self.assertEqual(names, ["figures/a.tex"])
        [(_, names)] = T.resolve_listed(["tables/t[12].tex"], files)
        self.assertEqual(names, ["tables/t1.tex"])

    def test_an_ignore_pattern_that_matches_everything_is_refused(self):
        for bad in ([""], ["^"], [".*"]):
            with TempDir() as root:
                ws, cfg = setup(root, ignore=bad)
                row = scan_row(V.compute(cfg, ws))
                self.assertEqual(row["status"], V.FAILED, bad)

    def test_the_share_counts_ignored_words(self):
        with TempDir() as root:
            ws, cfg = setup(root, ignore=[r"^How the Gauges"])
            s = V.compute(cfg, ws)
            cov, row = s["scan_coverage"], scan_row(s)
            share = round(100 * cov["kept"] / (cov["kept"] + cov["dropped"] + cov["ignored"]))
            self.assertLess(share, 50)  # 23 kept of 74 under headings
            self.assertIn(f"{share}%", row["detail"])

    def test_a_malformed_cache_is_rebuilt(self):
        with TempDir() as root:
            ws, cfg = setup(root, rules=self.RULES_ALL, also_scanned=["figures/*.tex"])
            cache = Path(ws) / "cache" / "coverage" / "extra_scan.json"
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text("[]", encoding="utf-8")
            [o] = S.compute(cfg, ws)["over"]
            self.assertEqual(len(o["labels"]), 2)  # the method sentence and the figure


if __name__ == "__main__":
    unittest.main()
