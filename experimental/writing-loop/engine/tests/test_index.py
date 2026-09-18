import json
import unittest
from pathlib import Path

from loop import config as C
from loop import index as X

from fixtures import TempDir, draft_md, git, make_repo, make_transcripts, workspace

T0 = 1_760_000_000
LEDGER = [{"id": "E1", "key": "K", "tier": "raw_abstract", "source": "raw/k.txt", "draft": "Gauges lag surveyors", "span": "a gap is observed"}]


def setup(root):
    repo = make_repo(root, [
        ({"drafts/DRAFT-v1.md": draft_md("T", "Abs one.", ["Gauges lag surveyors [KK]. Inspectors work alone."]),
          "ev/claims.json": json.dumps(LEDGER), "ev/check.py": 'KEYMAP = {"KK": "K"}\nNARR = {}\nPLACE = set()\n',
          "ev/raw/k.txt": "we note that a gap is observed"}, "v1", T0),
        ({"drafts/DRAFT-v1.md": draft_md("T", "Abs one.", ["Gauges lag surveyors [KK]. Inspectors work alone, then meet."])}, "v2", T0 + 3600),
    ])
    projects = make_transcripts(root, repo, "main", [
        {"type": "user", "timestamp": "2025-10-09T09:30:00.000Z", "origin": {"kind": "human"}, "message": {"role": "user", "content": "I1.2 加上他们什么时候见面"}}])
    ws = workspace(root, repo, "main", projects=projects, ledger={"path": "ev/claims.json", "evidence_dir": "ev", "keymap_from": "ev/check.py"})
    return C.load(ws), repo


class IndexTest(unittest.TestCase):
    def test_rebuild_matches_written_index(self):
        with TempDir() as root:
            cfg, _ = setup(root)
            files, summary = X.build(cfg)
            X.write(cfg, files)
            self.assertEqual(X.check(cfg, X.build(cfg)[0]), ([], None))
            self.assertEqual((summary["versions"], summary["changesets"], summary["messages_attached"]), (2, 1, 1))

    def test_warm_and_cold_cache_give_the_same_bytes(self):
        with TempDir() as root:
            cfg, _ = setup(root)
            cache = {}
            cold, _ = X.build(cfg, cache)
            warm, _ = X.build(cfg, cache)
            self.assertEqual(cold, warm)

    def test_tampered_index_is_named_as_tampered(self):
        with TempDir() as root:
            cfg, _ = setup(root)
            X.write(cfg, X.build(cfg)[0])
            p = Path(cfg["_ws"]) / "index" / "checks.json"
            p.write_bytes(p.read_bytes().replace(b'"found"', b'"fouND"'))
            diffs, cause = X.check(cfg, X.build(cfg)[0])
            self.assertEqual(diffs, [("checks.json", "不同")])
            self.assertIn("被改动", cause)

    def test_new_commit_is_named_as_stale(self):
        with TempDir() as root:
            cfg, repo = setup(root)
            X.write(cfg, X.build(cfg)[0])
            (repo / "drafts/DRAFT-v1.md").write_text(draft_md("T", "Abs one.", ["Gauges lag surveyors [KK]. Inspectors meet at the end."]))
            git(repo, "commit", "-qam", "v3")
            diffs, cause = X.check(cfg, X.build(cfg)[0])
            self.assertTrue(diffs)
            self.assertIn("落后", cause)

    def test_missing_index_file_is_reported(self):
        with TempDir() as root:
            cfg, _ = setup(root)
            X.write(cfg, X.build(cfg)[0])
            (Path(cfg["_ws"]) / "index" / "threads.json").unlink()
            diffs, _ = X.check(cfg, X.build(cfg)[0])
            self.assertEqual(diffs, [("threads.json", "缺失")])


if __name__ == "__main__":
    unittest.main()
