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

    def test_a_rebuild_reads_old_commits_from_the_versions_cache(self):
        """K11 power (2026-10-01): re-reading every old version was the largest cost of an update. A second build gives the same
        bytes and lists no commit's tree again."""
        from unittest import mock
        from loop import history as H
        with TempDir() as root:
            cfg, _ = setup(root)
            cold, _ = X.build(cfg)
            self.assertEqual(len(list((Path(cfg["_ws"]) / "cache" / "versions").glob("*.json"))), 1)
            with mock.patch.object(H, "_draft_at", side_effect=AssertionError("an old commit was read again")):
                warm, _ = X.build(cfg)
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


class RoundReadsTest(unittest.TestCase):
    """2026-10-08：写一张卡把 sentences.json 解析四遍（摘要、总览、主张清单的整篇扫描两遍），前后叠着，一张卡峰值
    超过 1 GB。round_reads() 里同一个文件只解析一次，几处读同一份，所以读的地方都不能改它。"""

    def _ws(self, root):
        from test_overview import DAY, T0, build_ws
        cfg, shas = build_ws(root)
        ws = Path(cfg["_ws"])
        (ws / "index" / "sources.json").write_text(json.dumps({"head": shas[2]}), encoding="utf-8")
        (ws / "index" / "threads.json").write_text(json.dumps({"threads": []}), encoding="utf-8")
        (ws / "index" / "explanations.json").write_text(json.dumps({"explanations": []}), encoding="utf-8")
        ledger = Path(root) / "claims.md"
        ledger.write_text("阶段：分析\n\n## 主张 C1 读数是 12\n- 证据：表 1\n- 强度：强\n- 允许的说法：读数\n",
                          encoding="utf-8")
        cfg = C.load(ws)
        cfg["claims"] = str(ledger)
        C.save(ws, cfg)
        return C.load(ws), T0 + 12 * DAY

    def _one_card(self, cfg, now):
        from loop import coverage as V
        from loop import overview as O
        from loop import state as S
        self.assertIsNotNone(X.load_summary(cfg))
        O.build(cfg, now)
        V.indexed_versions(cfg["_ws"])
        S.compute(cfg, cfg["_ws"])

    def test_one_card_parses_sentences_json_once(self):
        import contextlib
        from unittest import mock
        with TempDir() as root:
            cfg, now = self._ws(root)
            real, parsed = json.loads, []

            def counting(s, *a, **k):
                if isinstance(s, str) and s.startswith('{"head"') and '"versions"' in s:
                    parsed.append(len(s))
                return real(s, *a, **k)
            with mock.patch("json.loads", counting), getattr(X, "round_reads", contextlib.nullcontext)():
                self._one_card(cfg, now)
            self.assertEqual(len(parsed), 1, f"sentences.json parsed {len(parsed)} times for one card")

    def test_what_one_card_reads_is_not_changed_by_its_readers(self):
        with TempDir() as root:
            cfg, now = self._ws(root)
            with X.round_reads():
                docs = {n: X.read_doc(cfg["_ws"], n) for n in X.FILES}
                before = {n: json.dumps(d, sort_keys=True) for n, d in docs.items()}
                self._one_card(cfg, now)
                self.assertEqual({n: json.dumps(d, sort_keys=True) for n, d in docs.items()}, before)

    def test_a_file_rewritten_during_a_round_is_read_again_and_nothing_outlives_the_round(self):
        with TempDir() as root:
            cfg, _ = self._ws(root)
            p = Path(cfg["_ws"]) / "index" / "threads.json"
            with X.round_reads():
                self.assertEqual(X.read_doc(cfg["_ws"], "threads.json"), {"threads": []})
                p.write_text(json.dumps({"threads": [{"text": "新的"}]}), encoding="utf-8")
                self.assertEqual(X.read_doc(cfg["_ws"], "threads.json")["threads"][0]["text"], "新的")
            self.assertIsNone(X._ROUND, "the parsed files are dropped when the round ends")


if __name__ == "__main__":
    unittest.main()
