import json
import unittest
from pathlib import Path

from loop import inbox as IB

from fixtures import TempDir, make_repo, make_transcripts

MAIN = r"""\documentclass{article}
\begin{document}
\begin{abstract}
First abstract sentence. Second abstract sentence.
\end{abstract}
\section{Introduction}
Intro one. Intro two.
\input{sections/method}
\end{document}
"""
METHOD = "\\section{Method}\nMethod one is here. Method two follows.\n"


def registry(root, accepts=("folder",)):
    home = Path(root) / "lintel"
    (home / "producers" / "awt-loop" / "inbox").mkdir(parents=True)
    (home / "registry.json").write_text(json.dumps({"schema": 1, "producers": {"awt-loop": {
        "name": "写作循环", "initial": "循", "accepts": list(accepts),
        "events": {"changed": {"attention": False}, "drift": {"attention": True}}}}}), encoding="utf-8")
    return home


def drop(home, path, name="d1"):
    p = home / "producers" / "awt-loop" / "inbox" / f"{name}.json"
    p.write_text(json.dumps({"schema": 1, "kind": "drop", "path": str(path), "at": "2026-09-21T12:00:00Z", "from": "lintel"}), encoding="utf-8")
    return p


class InboxTest(unittest.TestCase):
    """候选 B（作者 09-21：只收目录）：lintel 只写收件文件；这里读到就登记、建索引、写「登记好了」。"""

    def test_a_dropped_folder_becomes_a_workspace_with_its_tex_files(self):
        with TempDir() as root:
            repo = make_repo(root, [({"main.tex": MAIN, "sections/method.tex": METHOD}, "v1", 1_700_000_000)])
            projects = make_transcripts(root, repo, "main", [])
            home = registry(root)
            drop(home, repo)
            results = IB.process(home, Path(root) / "workspaces", projects_dir=projects, now=1_789_700_000)
            self.assertEqual([(n, o["ok"]) for n, o in results], [("d1.json", True)])
            cfg = json.loads((Path(root) / "workspaces" / "ms" / "config.json").read_text())
            self.assertEqual(Path(cfg["repo"]).resolve(), repo.resolve()); self.assertEqual(cfg["ref"], "main")
            self.assertEqual(cfg["draft"]["glob"], ["main.tex", "sections/method.tex"])
            self.assertEqual(cfg["draft"]["format"], "latex")
            self.assertEqual([r["prefix"] for r in cfg["draft"]["sections"]], ["A", "B", "C"])
            self.assertTrue((Path(root) / "workspaces" / "ms" / "index" / "sentences.json").exists())
            a = json.loads((home / "producers" / "awt-loop" / "activities" / "loop-ms.json").read_text())
            self.assertEqual(a["label"]["text"], "登记好了")
            self.assertEqual(a["ears"]["tag"]["text"], "6 句")
            self.assertIn("6 句 · 3 节 · main", a["popup"][1]["text"])
            done = json.loads((home / "producers" / "awt-loop" / "inbox" / "done" / "d1.json").read_text())
            self.assertEqual(done["outcome"]["sentences"], 6)
            self.assertEqual(list((home / "producers" / "awt-loop" / "inbox").glob("*.json")), [])

    def test_section_rules_follow_the_headings_with_the_abstract_flat(self):
        rules = IB.section_rules([MAIN, METHOD])
        self.assertEqual([(r["prefix"], r["match"], r.get("flat", False)) for r in rules],
                         [("A", "^Abstract$", True), ("B", "^Introduction$", False), ("C", "^Method$", False)])

    def test_a_folder_that_is_not_a_repo_or_has_no_main_tex_is_refused_and_leaves_no_workspace(self):
        with TempDir() as root:
            home = registry(root)
            plain = Path(root) / "plain"; plain.mkdir()
            drop(home, plain, "plain")
            repo = make_repo(root, [({"notes.md": "# hi\n"}, "v1", 1_700_000_000)])
            drop(home, repo, "notex")
            results = dict(IB.process(home, Path(root) / "workspaces"))
            self.assertFalse(results["plain.json"]["ok"]); self.assertIn("git", results["plain.json"]["reason"])
            self.assertFalse(results["notex.json"]["ok"]); self.assertIn("documentclass", results["notex.json"]["reason"])
            self.assertFalse((Path(root) / "workspaces").exists())
            self.assertEqual(sorted(p.name for p in (home / "producers" / "awt-loop" / "inbox" / "done").glob("*.json")), ["notex.json", "plain.json"])

    def test_a_file_that_is_not_a_drop_is_moved_aside_with_a_reason(self):
        with TempDir() as root:
            home = registry(root)
            (home / "producers" / "awt-loop" / "inbox" / "junk.json").write_text('{"kind": "other"}', encoding="utf-8")
            results = dict(IB.process(home, Path(root) / "workspaces"))
            self.assertFalse(results["junk.json"]["ok"])

    def test_nothing_pending_when_the_inbox_does_not_exist(self):
        with TempDir() as root:
            self.assertEqual(IB.pending(Path(root) / "nowhere"), [])
