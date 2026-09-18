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

    def test_building_the_index_reads_blobs_without_a_process_each(self):
        """Load report F3 (2026-09-18): one git process per blob read was two thirds of a warm update."""
        import subprocess
        from unittest import mock
        with TempDir() as root:
            cfg, _ = setup(root)
            with mock.patch("subprocess.run", side_effect=subprocess.run) as run:
                X.build(cfg)
            per_blob = [c[0][0] for c in run.call_args_list if c[0][0][:1] == ["git"]
                        and (c[0][0][3] == "show" or (c[0][0][3] == "rev-parse" and ":" in c[0][0][-1]))]
            self.assertEqual(per_blob, [])

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


class DiskCacheTest(unittest.TestCase):
    """The alignment cache and the transcript scan cache may only make a rebuild faster, never different."""

    def cold(self, cfg):
        import shutil
        shutil.rmtree(Path(cfg["_ws"]) / "cache", ignore_errors=True)
        return X.build(cfg)[0]

    def test_alignment_and_scan_caches_do_not_change_a_byte(self):
        with TempDir() as root:
            cfg, _ = setup(root)
            cold = self.cold(cfg)
            self.assertTrue(any((Path(cfg["_ws"]) / "cache" / "align").glob("*.json")))
            self.assertTrue((Path(cfg["_ws"]) / "cache" / "transcript-scan.json").exists())
            self.assertEqual(X.build(cfg)[0], cold)

    def test_unreadable_cache_files_are_recomputed_not_trusted(self):
        with TempDir() as root:
            cfg, _ = setup(root)
            cold = self.cold(cfg)
            for f in (Path(cfg["_ws"]) / "cache" / "align").glob("*.json"):
                f.write_text("{not json", encoding="utf-8")
            (Path(cfg["_ws"]) / "cache" / "transcript-scan.json").write_text("[1, 2", encoding="utf-8")
            self.assertEqual(X.build(cfg)[0], cold)

    def test_a_rewritten_commit_does_not_reuse_the_old_alignment(self):
        with TempDir() as root:
            cfg, repo = setup(root)
            X.build(cfg)  # the cache now holds v1 -> v2
            (repo / "drafts" / "DRAFT-v1.md").write_text(
                draft_md("T", "Abs one.", ["Inspectors work alone. Gauges lag surveyors [KK] at night, then rest."]), encoding="utf-8")
            git(repo, "commit", "-q", "--amend", "-am", "v2 rewritten")
            self.assertEqual(X.build(cfg)[0], self.cold(cfg))

    def test_a_session_file_that_gains_the_branch_is_read_again(self):
        with TempDir() as root:
            cfg, repo = setup(root)
            make_transcripts(root, repo, "dev", [{"_file": "s2", "type": "user", "timestamp": "2025-10-09T09:40:00.000Z",
                                                  "origin": {"kind": "human"}, "message": {"role": "user", "content": "another branch"}}])
            X.build(cfg)  # s2 is scanned and remembered as not holding the branch
            make_transcripts(root, repo, "main", [{"_file": "s2", "type": "user", "timestamp": "2025-10-09T10:00:00.000Z",
                                                   "origin": {"kind": "human"}, "message": {"role": "user", "content": "再补一句"}}])
            threads = json.loads(X.build(cfg)[0]["threads.json"])
            self.assertIn("再补一句", [t["text"] for t in threads["threads"]])


if __name__ == "__main__":
    unittest.main()
