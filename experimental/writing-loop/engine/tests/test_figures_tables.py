"""Generated copies and float reviews in the loop: a data repository is read at its HEAD commit, so the check goes
stale when that repository commits, not when its files are touched; the row shows the check's own one-line summary;
floats are looked for from every draft file and every also-checked file. Synthetic files throughout."""
import json
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import config as C
from loop import coverage as V
from loop import history as H

from fixtures import TempDir, git, make_repo, workspace

MAIN = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Two gauges read twelve points.
\input{tables/t}
\end{document}
"""
GEN = """import json, os, sys
out = sys.argv[1]
v = json.load(open("values.json"))
os.makedirs(out, exist_ok=True)
open(os.path.join(out, "t.tex"), "w").write("A & " + format(v["a"], ".2f") + "\\n")
"""


def data_repo(root, a=0.634):
    d = Path(root) / "data"
    d.mkdir()
    (d / "gen.py").write_text(GEN, encoding="utf-8")
    (d / "values.json").write_text(json.dumps({"a": a}), encoding="utf-8")
    git(d, "init", "-q", "-b", "main")
    git(d, "add", "gen.py", "values.json")
    git(d, "commit", "-q", "-m", "gen")
    return d


def setup(root, copy="A & 0.63\n", manifest=None):
    data = data_repo(root)
    manifest = manifest if manifest is not None else json.dumps(
        {"covers": ["tables/*.tex"], "hand": {},
         "generators": [{"name": "gen", "repo": str(data), "export": ["gen.py", "values.json"],
                         "run": [sys.executable, "gen.py", "{out}"], "copies": {"tables/t.tex": "{out}/t.tex"}}]})
    repo = make_repo(root, [({"main.tex": MAIN, "tables/t.tex": copy, "generated.json": manifest}, "v1",
                             1_700_000_000)])
    ws = workspace(root, repo, "main", glob=["main.tex"])
    cfg = C.load(ws)
    cfg["draft"]["format"] = "latex"
    cfg["draft"]["sections"] = [{"match": r"^Introduction$", "prefix": "I", "kind": "prose"}]
    cfg.setdefault("inputs", {})["generated"] = "generated.json"
    C.save(ws, cfg)
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    head = git(cfg["repo"], "rev-parse", "HEAD")
    (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
    return data, repo, ws, C.load(ws)


class GeneratedCopiesInTheLoop(unittest.TestCase):
    def test_the_row_goes_stale_when_the_data_repository_commits(self):
        with TempDir() as root:
            data, repo, ws, cfg = setup(root)
            chk = K.by_id("generated-copies")
            head = git(repo, "rev-parse", "HEAD")
            sents = V.current_sentences(ws)[0]
            rec = V.run(chk, cfg, ws, head, sents)
            self.assertEqual(rec["verdict"], "ok", rec)
            self.assertIn("一致 1", rec["summary"])
            self.assertEqual(V.row(chk, cfg, ws, head, sents)["status"], V.OK)
            fp = V.fingerprint(cfg, ws)
            (data / "values.json").write_text(json.dumps({"a": 0.651}), encoding="utf-8")
            self.assertEqual(V.row(chk, cfg, ws, head, sents)["status"], V.OK,
                             "an uncommitted change in the data repository is not what the check reads")
            git(data, "commit", "-qam", "rerun")
            r = V.row(chk, cfg, ws, head, sents)
            self.assertEqual(r["status"], V.STALE)
            self.assertIn("数据仓 data 有新提交", r["detail"])
            self.assertNotEqual(V.fingerprint(cfg, ws), fp, "the per-turn fingerprint sees the new commit")
            rec = V.run(chk, cfg, ws, head, sents)
            self.assertEqual(rec["verdict"], "findings")
            self.assertIn("不一致 1（tables/t.tex）", rec["summary"])

    def test_outside_git_entries_are_the_head_commit(self):
        with TempDir() as root:
            data = data_repo(root)
            head = git(data, "rev-parse", "HEAD")
            self.assertEqual(V.outside_hash(f"git:{data}"), head)
            self.assertEqual(V._stat_sig(f"git:{data}"), head)
            self.assertIsNone(V.outside_hash(f"git:{Path(root) / 'nowhere'}"))

    def test_the_outside_list_comes_from_the_manifest_at_the_ref(self):
        with TempDir() as root:
            data, repo, ws, cfg = setup(root)
            self.assertEqual(K._generated_outside(cfg), [f"git:{data.resolve()}"])
        with TempDir() as root:
            data, repo, ws, cfg = setup(root, manifest="{not json")
            self.assertEqual(K._generated_outside(cfg), [])

    def test_a_one_line_summary_is_what_the_row_says(self):
        out = json.dumps({"summary_zh": "3 份副本重跑对照：一致 3", "hard_finding_count": 0})
        self.assertEqual(V.interpret("generated-copies", 0, out, ""), ("ok", "3 份副本重跑对照：一致 3"))


FMAIN = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Two gauges read twelve points.
\begin{figure}\includegraphics{photo.png}\caption{Two spans.}\label{fig:span}\end{figure}
\end{document}
"""
FSUPP = r"""\section{Extra}
\begin{table}\caption{Night readings.}\label{tab:night}\begin{tabular}{l}x\end{tabular}\end{table}
"""


class FloatReviewsInTheLoop(unittest.TestCase):
    def test_floats_in_the_draft_and_the_also_checked_files_are_listed_until_reviewed(self):
        with TempDir() as root:
            repo = make_repo(root, [({"main.tex": FMAIN, "supp.tex": FSUPP, "photo.png": "PNG1",
                                      "reviews.tsv": "label\tfingerprint\treviewer\tdate\tverdict\tnote\n"},
                                     "v1", 1_700_000_000)])
            ws = workspace(root, repo, "main", glob=["main.tex"])
            cfg = C.load(ws)
            cfg["draft"]["format"] = "latex"
            cfg["draft"]["sections"] = [{"match": r"^Introduction$", "prefix": "I", "kind": "prose"}]
            cfg.setdefault("inputs", {}).update({"float_reviews": "reviews.tsv", "also_checked": ["supp.tex"]})
            C.save(ws, cfg)
            cfg = C.load(ws)
            vs = H.load_versions(cfg)
            H.assign_ids(vs)
            head = git(repo, "rev-parse", "HEAD")
            (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}),
                                                               encoding="utf-8")
            chk = K.by_id("float-reviews")
            rec = V.run(chk, cfg, ws, head, V.current_sentences(ws)[0])
            self.assertEqual(rec["verdict"], "findings", rec)
            self.assertIn("图表 2 个：看过这一版 0", rec["summary"])
            self.assertEqual(sorted(f["id"] for f in rec["result"]["floats"]), ["fig:span", "tab:night"],
                             "the table lives only in an also-checked file")
            rows = "".join(f"{f['id']}\t{f['fingerprint']}\tA. Reader\t2026-01-01\tok\t\n" for f in rec["result"]["floats"])
            (repo / "reviews.tsv").write_text("label\tfingerprint\treviewer\tdate\tverdict\tnote\n" + rows,
                                              encoding="utf-8")
            git(repo, "commit", "-qam", "reviewed")
            head = git(repo, "rev-parse", "HEAD")
            rec = V.run(chk, cfg, ws, head, V.current_sentences(ws)[0])
            self.assertEqual(rec["verdict"], "ok", rec)
            self.assertIn("看过这一版 2", rec["summary"])


if __name__ == "__main__":
    unittest.main()
