"""Coverage: a check's status follows the draft, and nothing that did not look at the current draft is green."""
import datetime as dt
import json
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import config as C
from loop import coverage as V
from loop import history as H
from loop import targets as TG

from fixtures import TempDir, git, make_repo, workspace

MAIN = r"""\documentclass{article}
\begin{document}
\begin{abstract}
We audit a bridge survey. Its gauges read 12 points.
\end{abstract}
\input{sections/01_intro}
\end{document}
"""
INTRO = r"""\section{Introduction}\label{sec:intro}
Bridges fail slowly~\cite{smith2020}. Nobody watches them.

Inspections are rare.
"""
BIB = "@article{smith2020, title={Slow}, author={Smith, A.}, year={2020}, journal={J}}\n"
RULES = [{"match": r"^Abstract$", "prefix": "A", "kind": "prose", "flat": True},
         {"match": r"^Introduction$", "prefix": "I", "kind": "prose"}]

# A throwaway check: prints how many sentences it can see and exits with the code written in CODE, or sleeps.
PROBE = r"""
import json, pathlib, sys, time
code = pathlib.Path(sys.argv[1]).read_text().strip()
if code == "sleep":
    time.sleep(5)
tex = "".join(p.read_text() for p in pathlib.Path(".").rglob("*.tex"))
print(json.dumps({"issues": ["x"] * tex.count("~\\cite")}))
sys.exit(int(code))
"""


def probe_check(root, scope="cite", formats=("latex",), needs=(), inputs=None, instead=None):
    script = Path(root) / "probe.py"
    script.write_text(PROBE, encoding="utf-8")
    code = Path(root) / "code.txt"
    if not code.exists():
        code.write_text("0", encoding="utf-8")
    return {"id": "probe", "name": "探针", "kind": "script", "scripts": [str(script)], "formats": list(formats),
            "instead": instead or {}, "scope": {"kind": scope}, "needs": list(needs),
            "inputs": inputs or (lambda cfg: {}), "outside": lambda cfg: [],
            "argv": lambda ctx: [sys.executable, str(script), str(code)]}


def setup(root, extra_commits=()):
    commits = [({"main.tex": MAIN, "sections/01_intro.tex": INTRO, "references.bib": BIB}, "v1", 1_700_000_000)]
    commits += list(extra_commits)
    repo = make_repo(root, commits)
    ws = workspace(root, repo, "main", glob=["main.tex", "sections/01_intro.tex"])
    cfg = C.load(ws)
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = RULES
    cfg["genre"] = "note"
    C.save(ws, cfg)
    reindex(ws)
    return repo, ws


def reindex(ws):
    """What `loop update` leaves on disk, reduced to the one file coverage reads."""
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    head = git(cfg["repo"], "rev-parse", "HEAD")
    (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")


def commit(repo, files, msg, t):
    for path, txt in files.items():
        (repo / path).write_text(txt, encoding="utf-8")
        git(repo, "add", path)
    d = f"@{t} +0000"
    git(repo, "commit", "-q", "-m", msg, env={"GIT_AUTHOR_DATE": d, "GIT_COMMITTER_DATE": d})


class Probe:
    """Put a probe check in the catalogue for the duration of a test."""

    def __init__(self, check):
        self.check = check

    def __enter__(self):
        self.saved = list(K.CHECKS)
        K.CHECKS[:] = [self.check]
        return self.check

    def __exit__(self, *exc):
        K.CHECKS[:] = self.saved


def status(summary, cid="probe"):
    return next(r for r in summary["rows"] if r["id"] == cid)


class StalenessTest(unittest.TestCase):
    def test_never_run_then_run_then_up_to_date(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.NEVER)
                s = V.compute(cfg, ws, do_run=True)
                self.assertEqual(s["ran"], ["probe"])
                self.assertEqual(status(s)["status"], V.OK)
                self.assertEqual(status(s)["result"], "1 条")
                self.assertEqual(V.compute(cfg, ws, do_run=True)["ran"], [], "an up-to-date check is not re-run")

    def test_an_edited_sentence_in_scope_makes_it_stale_and_one_outside_does_not(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="cite")):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"sections/01_intro.tex": INTRO.replace("Inspections are rare.", "Inspections are very rare.")},
                       "outside scope", 1_700_000_100)
                reindex(ws)
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.OK)
                commit(repo, {"sections/01_intro.tex": INTRO.replace("fail slowly", "fail quietly")}, "in scope",
                       1_700_000_200)
                reindex(ws)
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE)
                self.assertEqual(r["changed"], 1)
                self.assertIn("句子", r["detail"])

    def test_the_sections_scope_follows_subsections_and_nothing_else(self):
        self.assertTrue(V.in_sections("Wa", ["W"]))
        self.assertTrue(V.in_sections("I", ["A", "I"]))
        self.assertFalse(V.in_sections("X", ["R"]))
        self.assertFalse(V.in_sections("Ia2", ["I"]))

    def test_a_changed_input_file_makes_it_stale(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="none", inputs=lambda c: {"bib": "references.bib"})):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"references.bib": BIB + "@misc{x, title={X}, year={2021}}\n"}, "bib", 1_700_000_100)
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE)
                self.assertIn("输入 bib", r["detail"])

    def test_a_changed_check_script_makes_it_stale(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            chk = probe_check(root)
            with Probe(chk):
                V.compute(cfg, ws, do_run=True)
                Path(chk["scripts"][0]).write_text(PROBE + "\n# a new version\n", encoding="utf-8")
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE)
                self.assertIn("检查脚本本身改过", r["detail"])


class NeverGreenTest(unittest.TestCase):
    """Every way a check can fail to look at the draft is shown as itself, never as 最新."""

    def test_a_format_the_check_cannot_read(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, formats=("markdown",), instead={"latex": None})):
                r = status(V.compute(cfg, ws, do_run=True))
                self.assertEqual(r["status"], V.NOT_APPLICABLE)
                self.assertIn("没有别的检查替它", r["detail"])
                s = V.load_summary(ws)
                self.assertEqual(V.attention(s), [], "a toolkit gap is not a task for this turn")
                self.assertEqual([r["id"] for r in V.gaps(s)], ["probe"], "but it is listed as a gap")
                self.assertIn("AWT 读不了这种稿件", V.table(s, ws))
                self.assertIsNone(V.reminder_line(s, ws), "and it stays out of the per-turn line")
            with Probe(probe_check(root, formats=("markdown",), instead={"latex": "claim-ledger"})):
                s = V.compute(cfg, ws)
                self.assertEqual(status(s)["status"], V.NOT_APPLICABLE)
                self.assertEqual(V.attention(s), [], "a format covered by another check is a decision, not a gap")
                self.assertEqual(V.gaps(s), [])

    def test_a_missing_prerequisite(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, needs=("inputs.number_ledger",))):
                r = status(V.compute(cfg, ws, do_run=True))
                self.assertEqual(r["status"], V.MISSING)
                self.assertIn("inputs.number_ledger", r["detail"])

    def test_an_input_configured_but_absent_at_head_is_a_failure_not_a_pass(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="none", inputs=lambda c: {"bib": "nope.bib"})):
                r = status(V.compute(cfg, ws, do_run=True))
                self.assertEqual(r["status"], V.FAILED)
                self.assertIn("nope.bib", r["detail"])

    def test_a_waiver_is_shown_with_its_reason(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            cfg["waive"] = {"probe": "the agent wrote this"}
            with Probe(probe_check(root)):
                s = V.compute(cfg, ws, do_run=True)
                self.assertEqual(status(s)["status"], V.OK, "a waiver in config.json is not the author's and does nothing")
                self.assertIn("config.json 里的豁免不生效", V.reminder_line(s, ws))
                (Path(ws) / "human" / "waivers.json").write_text(json.dumps({"probe": "作者：这篇不做"}), encoding="utf-8")
                s = V.compute(cfg, ws, do_run=True)
                self.assertEqual(status(s)["status"], V.WAIVED)
                self.assertIn("已豁免 探针", V.reminder_line(s, ws), "a waiver is said every turn")

    def test_exit_2_is_a_failure(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            chk = probe_check(root)
            (Path(root) / "code.txt").write_text("2", encoding="utf-8")
            with Probe(chk):
                r = status(V.compute(cfg, ws, do_run=True))
                self.assertEqual(r["status"], V.FAILED)
                self.assertIn("退出码 2", r["detail"])

    def test_exit_1_without_a_result_is_a_crash_not_a_finding(self):
        # A traceback, or an error line such as a malformed ledger's, also exits 1. Only a check that printed its
        # result has findings; one that printed none examined nothing and must not turn green.
        for out, code in (("Traceback (most recent call last):\n  boom", 1), ("LEDGER_COLUMNS: expected five", 1),
                          ("done", 0)):
            self.assertEqual(V.interpret("x", code, out, "")[0], "failed", out)
        self.assertEqual(V.interpret("x", 1, '{"issues": ["a"]}', "")[0], "findings")
        self.assertEqual(V.interpret("x", 0, '{"issues": []}', "")[0], "ok")

    def test_a_notes_lint_result_is_summarised_by_file_not_by_its_first_line(self):
        out = '{\n  "a_NOTES.md": [],\n  "b_NOTES.md": [{"severity": "warning", "code": "evidence-status-missing"}]\n}'
        self.assertEqual(V.interpret("notes-lint", 0, out, ""), ("ok", "2 份笔记，错 0、提示 1"))

    def test_a_timeout_is_a_failure(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            chk = probe_check(root)
            (Path(root) / "code.txt").write_text("sleep", encoding="utf-8")
            with Probe(chk):
                rec = V.run(chk, cfg, ws, git(repo, "rev-parse", "HEAD"), V.current_sentences(ws)[0], timeout=1)
                self.assertEqual(rec["verdict"], "failed")
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.FAILED)

    def test_no_index_means_nothing_is_up_to_date(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            (Path(ws) / "index" / "sentences.json").unlink()
            with Probe(probe_check(root)):
                s = V.compute(cfg, ws, do_run=True)
                self.assertEqual(status(s)["status"], V.NEVER)
                self.assertEqual(s["ran"], [])

    def test_a_failed_check_is_rerun_only_when_something_changed(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            (Path(root) / "code.txt").write_text("2", encoding="utf-8")
            with Probe(probe_check(root)):
                self.assertEqual(V.compute(cfg, ws, do_run=True)["ran"], ["probe"])
                self.assertEqual(V.compute(cfg, ws, do_run=True)["ran"], [])
                commit(repo, {"sections/01_intro.tex": INTRO.replace("fail slowly", "fail quietly")}, "c", 1_700_000_100)
                reindex(ws)
                self.assertEqual(V.compute(cfg, ws, do_run=True)["ran"], ["probe"])


class GrillTest(unittest.TestCase):
    """Each false green the 2026-09-21 review reproduced, kept as a test."""

    def test_a_glob_draft_is_checked_on_the_one_file_the_index_tracks(self):
        with TempDir() as root:
            repo = make_repo(root, [({"drafts/DRAFT-v1.md": "# Draft\n\n## Abstract\n\nOld one.\n",
                                      "drafts/DRAFT-v2.md": "# Draft\n\n## Abstract\n\nNew one.\n"}, "v", 1_700_000_000)])
            ws = workspace(root, repo, "main")
            cfg = C.load(ws)
            self.assertEqual(V.draft_files(cfg, git(repo, "rev-parse", "HEAD")), ["drafts/DRAFT-v2.md"])

    def test_text_the_index_does_not_see_still_makes_a_whole_text_check_stale(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="all")):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"main.tex": MAIN.replace("\\documentclass{article}", "\\documentclass{article}\n\\keywords{Gauges}")},
                       "preamble", 1_700_000_100)
                reindex(ws)
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE, r)
                self.assertIn("索引外的正文变了", r["detail"])

    def test_a_citation_in_an_unindexed_section_makes_a_citation_check_stale(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="cite")):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"sections/01_intro.tex": INTRO + "\n\\section{Methods}\nWe follow~\\cite{smith2020}.\n"},
                       "methods", 1_700_000_100)
                reindex(ws)
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.STALE)

    def test_reordering_paragraphs_makes_a_sections_check_stale(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            chk = probe_check(root, scope="sections")
            chk["scope"] = {"kind": "sections", "config": "target.readers.sections", "default": ["I"]}
            with Probe(chk):
                V.compute(cfg, ws, do_run=True)
                swapped = INTRO.replace("Bridges fail slowly~\\cite{smith2020}. Nobody watches them.\n\nInspections are rare.",
                                        "Inspections are rare.\n\nBridges fail slowly~\\cite{smith2020}. Nobody watches them.")
                self.assertNotEqual(swapped, INTRO)
                commit(repo, {"sections/01_intro.tex": swapped}, "swap", 1_700_000_100)
                reindex(ws)
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE, r)

    def test_an_index_behind_head_and_a_summary_for_an_older_head_are_never_current(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"sections/01_intro.tex": INTRO.replace("Inspections", "Checks")}, "not indexed", 1_700_000_100)
                s = V.load_summary(ws, cfg)
                self.assertTrue(s.get("stale_head"))
                self.assertEqual(V.attention(s)[0]["id"], "_summary")
                self.assertNotEqual(V.todo_cell(s)["value"], "全部最新")
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE)
                self.assertIn("索引建于", r["detail"])

    def test_a_summary_of_another_workspace_or_schema_is_not_trusted(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                s = V.compute(cfg, ws, do_run=True)
                path = Path(ws) / "cache" / "coverage" / "summary.json"
                self.assertIsNotNone(V.load_summary(ws, cfg), "the genuine summary is trusted")
                for bad in ({**s, "schema": 99}, {**s, "workspace": "someone-else"}, {**s, "rows": []},
                            {**s, "rows": [{"name": "x", "status": "fine"}]}):
                    path.write_text(json.dumps(bad, ensure_ascii=False), encoding="utf-8")
                    self.assertIsNone(V.load_summary(ws, cfg), bad.get("schema"))

    def test_a_waiver_does_not_hide_a_failure_and_the_cell_never_says_all_current_with_one(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            (Path(root) / "code.txt").write_text("2", encoding="utf-8")
            with Probe(probe_check(root)):
                V.compute(cfg, ws, do_run=True)
                (Path(ws) / "human" / "waivers.json").write_text(json.dumps({"probe": "不做"}), encoding="utf-8")
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.FAILED)
            with Probe(probe_check(root, formats=("markdown",), instead={"latex": None})):
                cell = V.todo_cell(V.compute(C.load(ws), ws))
                self.assertEqual((cell["value"], cell["text"]), ("缺口 1", "能跑的都查过当前稿"))

    def test_a_library_beside_the_script_makes_it_stale(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            fake = Path(root) / "awt"
            d = fake / ".claude" / "skills" / "probe" / "scripts"
            d.mkdir(parents=True)
            (d / "probe.py").write_text(PROBE, encoding="utf-8")
            (d / "lib.py").write_text("X = 1\n", encoding="utf-8")
            chk = probe_check(root)
            chk["scripts"] = ["probe/probe.py"]
            saved = K.ENGINE_ROOT
            K.ENGINE_ROOT = fake
            try:
                with Probe(chk):
                    V.compute(cfg, ws, do_run=True)
                    (d / "lib.py").write_text("X = 2\n", encoding="utf-8")
                    self.assertIn("检查脚本本身改过", status(V.compute(cfg, ws))["detail"])
            finally:
                K.ENGINE_ROOT = saved

    def test_a_same_size_change_in_a_corpus_is_a_different_corpus(self):
        with TempDir() as root:
            d = Path(root) / "corpus"
            d.mkdir()
            (d / "a.pdf").write_bytes(b"%PDF-aaaa")
            before = V.outside_hash(d)
            (d / "a.pdf").write_bytes(b"%PDF-bbbb")
            self.assertNotEqual(V.outside_hash(d), before)

    def test_an_unresolvable_ref_is_a_failure(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                V.compute(cfg, ws, do_run=True)
                cfg["ref"] = "no-such-branch"
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.FAILED)

    def test_a_config_key_the_check_reads_makes_it_stale_and_an_unrelated_one_does_not(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            chk = probe_check(root)
            chk["config_keys"] = ["inputs.literature_exclude"]
            with Probe(chk):
                V.compute(cfg, ws, do_run=True)
                cfg["inputs"] = {"number_ledger": "numbers.tsv"}
                self.assertEqual(status(V.compute(cfg, ws))["status"], V.OK, "an unrelated key must not cost a re-run")
                cfg["inputs"]["literature_exclude"] = ["me*"]
                self.assertIn("工作区配置改过", status(V.compute(cfg, ws))["detail"])

    def test_files_submitted_with_the_draft_are_read_and_watched(self):
        with TempDir() as root:
            repo, ws = setup(root, extra_commits=[({"supplement.tex": "Supp one.\n"}, "supp", 1_700_000_050)])
            cfg = C.load(ws)
            cfg["inputs"] = {"also_checked": ["supplement.tex"]}
            with Probe(probe_check(root, scope="all")):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"supplement.tex": "Supp two.\n"}, "supp2", 1_700_000_100)
                reindex(ws)
                self.assertIn("输入 also0 变了", status(V.compute(cfg, ws))["detail"])


class ProjectCheckTest(unittest.TestCase):
    """A manuscript's own checks: declared in the workspace, keyed on the whole tree, slow ones run only when named."""

    def ws_with_check(self, root, code="0"):
        repo, ws = setup(root, extra_commits=[({"tools/check.py": "import sys, pathlib\n"
                                                "sys.exit(int(pathlib.Path('tools/code.txt').read_text()))\n",
                                                "tools/code.txt": code}, "tools", 1_700_000_050)])
        cfg = C.load(ws)
        cfg["project_checks"] = [{"id": "build", "name": "构建", "argv": [sys.executable, "tools/check.py"]}]
        return repo, ws, cfg

    def test_a_slow_project_check_runs_only_when_named_and_any_change_in_the_tree_makes_it_stale(self):
        with TempDir() as root:
            repo, ws, cfg = self.ws_with_check(root)
            s = V.compute(cfg, ws, do_run=True)
            self.assertNotIn("build", s["ran"], "auto is false by default: update does not start a slow build")
            self.assertEqual(status(s, "build")["status"], V.NEVER)
            self.assertIn("--only build", status(s, "build")["detail"])
            s = V.compute(cfg, ws, do_run=True, only={"build"})
            self.assertEqual((s["ran"], status(s, "build")["status"]), (["build"], V.OK), "named, it runs alone")
            commit(repo, {"tools/plot.txt": "new figure data"}, "fig", 1_700_000_100)
            reindex(ws)
            self.assertEqual(status(V.compute(cfg, ws), "build")["status"], V.STALE, "a figure is part of the build")

    def test_changing_a_project_checks_command_makes_its_old_result_stale(self):
        with TempDir() as root:
            repo, ws, cfg = self.ws_with_check(root, code="1")
            V.compute(cfg, ws, do_run=True, only={"build"})
            cfg["project_checks"][0]["argv"] = [sys.executable, "-c", "pass"]
            r = status(V.compute(cfg, ws), "build")
            self.assertTrue(r.get("due"), "a failed result under an old command must be re-run")
            s = V.compute(cfg, ws, do_run=True, only={"build"})
            self.assertEqual(status(s, "build")["status"], V.OK)

    def test_a_project_check_that_exits_non_zero_is_a_failure(self):
        with TempDir() as root:
            repo, ws, cfg = self.ws_with_check(root, code="1")
            s = V.compute(cfg, ws, do_run=True, only={"build"})
            self.assertEqual(status(s, "build")["status"], V.FAILED)


class Grill2Test(unittest.TestCase):
    """Each problem the second review (2026-09-22) reproduced, kept as a test."""

    def test_a_citation_check_reads_the_notes_and_a_run_that_read_none_fails(self):
        with TempDir() as root:
            repo, ws = setup(root, extra_commits=[({"literature/reading_notes/Smith_2020_NOTES.md": "notes\n"},
                                                   "notes", 1_700_000_050)])
            cfg = C.load(ws)
            chk = probe_check(root, scope="none")
            chk["optional"] = lambda c: {"literature": "literature"}
            chk["argv"] = lambda ctx: [sys.executable, "-c", "import json,pathlib;print(json.dumps({'issues': "
                                       "[str(p) for p in pathlib.Path('literature').rglob('*.md')]}))"]
            with Probe(chk):
                self.assertEqual(status(V.compute(cfg, ws, do_run=True))["result"], "1 条", "the notes were archived")
                commit(repo, {"literature/reading_notes/Smith_2020_NOTES.md": "more notes\n"}, "n2", 1_700_000_100)
                reindex(ws)
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE, "a changed note makes it stale")
                self.assertIn("输入 ?literature 变了", r["detail"])
        self.assertEqual(V.interpret("citation-fidelity", 0, '{"citations_checked": 3, "notes_sources_indexed": 0}',
                                     "")[0], "failed")

    def test_a_markdown_citation_check_watches_the_whole_text(self):
        with TempDir() as root:
            repo = make_repo(root, [({"drafts/DRAFT-v1.md": "# D\n\n## Abstract\n\nPlain text here.\n"}, "v1", 1_700_000_000)])
            ws = workspace(root, repo, "main")
            reindex(ws)
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="cite", formats=("markdown",))):
                V.compute(cfg, ws, do_run=True)
                commit(repo, {"drafts/DRAFT-v1.md": "# D\n\n## Abstract\n\nJones (2021) reports that it is plain.\n"},
                       "v2", 1_700_000_100)
                reindex(ws)
                r = status(V.compute(cfg, ws))
                self.assertEqual(r["status"], V.STALE)
                self.assertGreaterEqual(r["changed"], 1, "the edited sentence itself is in scope")

    def test_every_check_against_the_venue_corpus_validates_it(self):
        cfg = {"repo": ".", "ref": "main", "genre": "journal", "_ws": "/nonexistent",
               "target": {"venue": "J", "venue_corpus": {"manifest": "/nonexistent.json", "dir": "/tmp"}}}
        self.assertTrue(TG.problems_for("structure-venue", cfg))
        self.assertTrue(TG.problems_for("fingerprint-venue", cfg))

    def test_a_summary_is_not_current_once_a_check_script_or_its_set_of_checks_changes(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            chk = probe_check(root)
            with Probe(chk):
                V.compute(cfg, ws, do_run=True)
                self.assertFalse(V.load_summary(ws, cfg).get("stale_inputs"))
                Path(chk["scripts"][0]).write_text(PROBE + "\n# changed\n", encoding="utf-8")
                s = V.load_summary(ws, cfg)
                self.assertTrue(s.get("stale_inputs"))
                self.assertEqual(V.attention(s)[0]["id"], "_summary")
            other = dict(probe_check(root), id="other")
            with Probe(other):
                K.CHECKS.append(chk)
                self.assertIsNone(V.load_summary(ws, cfg), "a summary without a row for every check is not trusted")

    def test_a_project_check_whose_script_lives_outside_the_repository_follows_that_script(self):
        with TempDir() as root:
            repo, ws = setup(root)
            ext = Path(root) / "outside.py"
            ext.write_text("print('ok')\n", encoding="utf-8")
            cfg = C.load(ws)
            cfg["project_checks"] = [{"id": "ext", "argv": [sys.executable, str(ext)], "auto": True}]
            V.compute(cfg, ws, do_run=True, only={"ext"})
            ext.write_text("raise SystemExit(1)\n", encoding="utf-8")
            self.assertEqual(status(V.compute(cfg, ws), "ext")["status"], V.STALE)

    def test_a_symlink_out_of_the_repository_fails_one_check_not_the_summary(self):
        with TempDir() as root:
            repo, ws = setup(root)
            (repo / "refs.bib").symlink_to(Path(root) / "zotero.bib")
            git(repo, "add", "refs.bib")
            git(repo, "commit", "-q", "-m", "link")
            cfg = C.load(ws)
            with Probe(probe_check(root, scope="none", inputs=lambda c: {"bib": "refs.bib"})):
                s = V.compute(cfg, ws, do_run=True)
                self.assertEqual(status(s)["status"], V.FAILED)
                self.assertIsNotNone(V.load_summary(ws), "the summary survives")


class ShownTest(unittest.TestCase):
    def test_the_reminder_names_what_is_not_current_and_is_silent_otherwise(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                s = V.compute(cfg, ws)
                line = V.reminder_line(s, ws)
                self.assertIn("从未运行 探针", line)
                s = V.compute(cfg, ws, do_run=True)
                self.assertIsNone(V.reminder_line(s, ws), "a check that ran clean on the current draft is not repeated")
                self.assertEqual(V.todo_cell(s)["tone"], "white")
                (Path(root) / "code.txt").write_text("1", encoding="utf-8")
                s = V.compute(cfg, ws, do_run=True, force=True)
                self.assertIn("有发现 探针（1 条）", V.reminder_line(s, ws), "a check that found something is said")
                self.assertIn("有发现 1 项", V.todo_cell(s)["sub"])
            self.assertIn("还没有算过", V.reminder_line(None, ws))

    def test_the_line_never_cuts_a_config_key_or_a_word(self):
        rows = [{"id": "n", "name": "数字台账", "status": V.MISSING, "detail": "配置里缺 inputs.number_ledger"},
                {"id": "f", "name": "文风", "status": V.OK, "verdict": "findings",
                 "result": "越界 2 项：hedge_per_1k, semicolon_per_1k"}]
        line = V.reminder_line({"head": "abc", "rows": rows, "target": {}}, "ws")
        self.assertIn("数字台账（inputs.number_ledger）", line)
        self.assertIn("文风（越界 2 项）", line)

    def test_the_todo_cell_counts_and_names(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                cell = V.todo_cell(V.compute(cfg, ws))
                self.assertEqual(cell["tone"], "orange")
                self.assertIn("从未运行 1", cell["text"])
                self.assertIn("探针", cell["sub"])
                self.assertLessEqual(len(cell["value"]), 16)

    def test_the_table_lists_the_unwired_checks_with_their_reasons(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            text = V.table(V.compute(cfg, ws), ws)
            for name, reason in K.UNWIRED.items():
                self.assertIn(name, text)
                self.assertIn(reason, text)


class UpdateTest(unittest.TestCase):
    def test_a_coverage_failure_during_update_leaves_no_old_summary_standing(self):
        from loop import cli
        from loop import health as HL
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(probe_check(root)):
                cli._coverage_after_update(ws, cfg)
                self.assertIsNotNone(V.load_summary(ws))
                saved = V.compute
                V.compute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
                try:
                    cli._coverage_after_update(ws, cfg)
                finally:
                    V.compute = saved
                self.assertIsNone(V.load_summary(ws), "an old summary must not stand in for a failed one")
                events = json.loads((Path(ws) / "health.json").read_text(encoding="utf-8"))["events"]
                self.assertTrue(any(e["kind"] == "coverage_error" for e in events))


class RealCheckTest(unittest.TestCase):
    def test_the_positioning_audit_runs_on_the_archived_draft(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            cfg["inputs"] = {"bib": "references.bib"}
            with Probe(K.by_id("claim-positioning")):
                r = status(V.compute(cfg, ws, do_run=True), "claim-positioning")
                self.assertIn(r["status"], (V.OK,), r)
                rec = V.load_run(ws, "claim-positioning")
                self.assertIn("--bib", rec["argv"])
                self.assertIn(rec["exit"], (0, 1))


    def test_the_changed_sentence_audit_reads_the_draft_against_the_version_before_it(self):
        with TempDir() as root:
            edited = INTRO.replace("Inspections are rare.", "Inspections are rare: most bridges wait a decade.")
            repo, ws = setup(root, [({"sections/01_intro.tex": edited}, "v2", 1_700_000_100)])
            cfg = C.load(ws)
            with Probe(K.by_id("sentence-changes")):
                r = status(V.compute(cfg, ws, do_run=True), "sentence-changes")
                rec = V.load_run(ws, "sentence-changes")
                self.assertEqual(rec["exit"], 1, rec)
                self.assertEqual(rec["result"]["changed"], 1, rec["result"]["compared"])
                self.assertIn("colon", rec["result"]["sentences"][0]["flags"])
                self.assertIn("改动 1 句，标出 1 句", rec["summary"])
                self.assertIn(r["status"], (V.OK,), r)

    def test_a_base_that_does_not_exist_fails_the_changed_sentence_audit_by_name(self):
        with TempDir() as root:
            repo, ws = setup(root)  # one commit: there is no version before it
            cfg = C.load(ws)
            with Probe(K.by_id("sentence-changes")):
                r = status(V.compute(cfg, ws, do_run=True), "sentence-changes")
                self.assertEqual(r["status"], V.FAILED, r)
                self.assertIn("上一版", V.load_run(ws, "sentence-changes")["summary"])
            cfg["draft"]["base_ref"] = "no-such-ref"
            C.save(ws, cfg)
            with Probe(K.by_id("sentence-changes")):
                self.assertEqual(status(V.compute(C.load(ws), ws, do_run=True), "sentence-changes")["status"], V.FAILED)


def manifest(venue, n, files=True):
    recs = [{"arxiv_id": f"2101.{i:05d}", **({"file": f"2101.{i:05d}.pdf"} if files else {})} for i in range(n)]
    return {"venue": venue, "admitted": n, "accounting_closes": True, "records": recs}


class TargetTest(unittest.TestCase):
    def cfg(self, root, **target):
        cfg = {"repo": str(root), "ref": "main", "genre": "journal", "_ws": str(Path(root) / "ws"), "target": target}
        return cfg

    def corpus(self, root, m, make=None):
        d = Path(root) / "corpus"
        d.mkdir(exist_ok=True)
        for r in m["records"][: make if make is not None else len(m["records"])]:
            if r.get("file"):
                (d / r["file"]).write_bytes(b"%PDF")
        p = Path(root) / "manifest.json"
        p.write_text(json.dumps(m), encoding="utf-8")
        return {"manifest": str(p), "dir": str(d)}

    def test_a_journal_without_a_venue_is_reported(self):
        with TempDir() as root:
            self.assertTrue(any("目标未登记" in p for p in TG.describe(self.cfg(root))["problems"]))

    def test_an_escaped_venue_name_matches_and_a_full_corpus_passes(self):
        with TempDir() as root:
            vc = self.corpus(root, manifest("Information &amp; Things", 25))
            cfg = self.cfg(root, venue="Information & Things", venue_corpus=vc)
            self.assertEqual(TG.venue_corpus_problems(cfg), [])

    def test_wrong_venue_small_corpus_and_missing_files_are_each_named(self):
        with TempDir() as root:
            vc = self.corpus(root, manifest("Other Journal", 12), make=10)
            ps = TG.venue_corpus_problems(self.cfg(root, venue="Information & Things", venue_corpus=vc))
            self.assertTrue(any("不是" in p for p in ps), ps)
            self.assertTrue(any("少于 20" in p for p in ps), ps)
            self.assertTrue(any("少了 2 个" in p for p in ps), ps)

    def test_an_intent_card_outside_human_is_a_draft(self):
        with TempDir() as root:
            (Path(root) / "ws" / "human").mkdir(parents=True)
            card = Path(root) / "card.md"
            card.write_text("M1", encoding="utf-8")
            self.assertEqual(TG.intent_card_state(self.cfg(root, intent_card=str(card)))[0], "draft")
            own = Path(root) / "ws" / "human" / "card.md"
            own.write_text("M1", encoding="utf-8")
            self.assertEqual(TG.intent_card_state(self.cfg(root, intent_card=str(own)))[0], "author")

    def test_a_card_finalised_by_claude_on_the_authors_word_is_delegated_only_if_that_word_is_on_record(self):
        from fixtures import make_transcripts
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            make_transcripts(root, cfg["transcripts"]["cwd_prefix"], cfg["transcripts"]["git_branch"],
                             [{"type": "user", "uuid": "abcdef12-0000-4000-8000-000000000001", "timestamp": "2026-09-22T00:00:00Z",
                               "message": {"role": "user", "content": "卡片交给你收尾，桥梁那段照旧"}}])
            card = Path(root) / "card.md"
            card.write_text("# card\n作者授权定稿：uuid abcdef12-0000-4000-8000-000000000001\nM1\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            self.assertEqual(TG.intent_card_state(cfg)[0], "delegated")
            card.write_text("# card\n作者授权定稿：uuid deadbeef-0000-4000-8000-000000000009\nM1\n", encoding="utf-8")
            self.assertEqual(TG.intent_card_state(cfg)[0], "draft", "a uuid that is not on record authorises nothing")

    def test_experiments_without_a_disposition_or_past_review_are_listed(self):
        with TempDir() as root:
            e = Path(root) / "experiments"
            for name, text in {"a": "# A\n\n处置：已晋升 → `.claude/skills/readers`\n",
                               "b": "# B\n\n- **处置**：退役 — 结论已写进 spec\n",
                               "c": "# C\n\n处置：进行中 — 门：作者裁定；复查 2026-09-01\n",
                               "d": "# D\n\n处置：进行中 — 门：作者裁定；复查 2026-10-30\n",
                               "e": "# E\n\n结果很好，下一步接进 AWT。\n"}.items():
                (e / name).mkdir(parents=True)
                (e / name / "README.md").write_text(text, encoding="utf-8")
            (e / "f").mkdir()
            (e / "g").mkdir()
            (e / "g" / "README.md").write_text("# G\n\n" + "".join(f"line {i}\n" for i in range(12))
                                               + "处置：退役 — buried in the body\n", encoding="utf-8")
            (e / "i").mkdir()
            (e / "i" / "README.md").write_text("# I\n\n处置：已晋升 → `.claude/skills/readers`（旁注提到 `other.py`）\n",
                                               encoding="utf-8")
            for name, text in {"dot": "处置：已晋升 → `./`", "home": "处置：已晋升 → `~/`",
                               "up": "处置：已晋升 → `experiments/..`",
                               "self": "处置：已晋升 → `experiments/self`", "bare": "处置：退役",
                               "fenced": "```\n处置：退役 — 这是一段示例\n```"}.items():
                (e / name).mkdir()
                (e / name / "README.md").write_text(f"# {name}\n\n{text}\n", encoding="utf-8")
            (e / "h").mkdir()
            (e / "h" / "README.md").write_text("# H\n\n处置：已晋升 → `no/such/place.py`\n", encoding="utf-8")
            (Path(root) / ".claude" / "skills" / "readers").mkdir(parents=True)
            saved = K.ENGINE_ROOT
            K.ENGINE_ROOT = Path(root)
            try:
                got = TG.experiments({"experiments_dir": [str(e)]}, today=dt.date(2026, 9, 21))
            finally:
                K.ENGINE_ROOT = saved
            self.assertEqual(sorted(got["promoted_missing"]), ["dot", "h", "home", "self", "up"],
                             "a promotion to nowhere, to a root or home, or to the experiment itself")
            for name in ("bare", "fenced"):
                self.assertIn(name, got["undisposed"], name)
                got["undisposed"].remove(name)
            self.assertIn("g", got["undisposed"], "a disposition buried in the body is not one")
            got["undisposed"].remove("g")
            self.assertEqual(got["promoted"], ["a", "i"], "a note after the target is not a second target")
            self.assertEqual(got["retired"], ["b"])
            self.assertEqual(got["overdue"], ["c"])
            self.assertEqual(got["in_progress"], [["d", "2026-10-30"]])
            self.assertEqual(got["undisposed"], ["e", "f"])


if __name__ == "__main__":
    unittest.main()
