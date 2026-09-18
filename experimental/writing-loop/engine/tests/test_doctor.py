import json
import unittest
from pathlib import Path

from loop import config as C
from loop import doctor

from fixtures import TempDir, draft_md, make_repo, make_transcripts, workspace

MD = draft_md("A title", "One sentence. Two sentence.", ["Intro one. Intro two."])


class DoctorTest(unittest.TestCase):
    def setup_ws(self, root):
        repo = make_repo(root, [({"drafts/DRAFT-v1.md": MD, "ev/claims.json": "[]", "ev/check.py": "KEYMAP = {}\n"}, "v1", 1_700_000_000)])
        projects = make_transcripts(root, repo, "main", [{"type": "user", "timestamp": "2026-01-01T00:00:00Z", "origin": {"kind": "human"}, "message": {"role": "user", "content": "hi"}}])
        ws = workspace(root, repo, "main", projects=projects,
                       ledger={"path": "ev/claims.json", "evidence_dir": "ev", "keymap_from": "ev/check.py"})
        return ws

    def test_good_config_has_no_problems(self):
        with TempDir() as root:
            problems, facts = doctor.run(self.setup_ws(root))
            self.assertEqual(problems, [])

    def test_each_wrong_path_is_named(self):
        cases = [
            (lambda c: c.__setitem__("ref", "no-such-branch"), "ref"),
            (lambda c: c["draft"].__setitem__("glob", "drafts/NOPE-v*.md"), "draft.glob"),
            (lambda c: c["ledger"].__setitem__("path", "ev/missing.json"), "ledger.path"),
            (lambda c: c["ledger"].__setitem__("keymap_from", "ev/nope.py"), "ledger.keymap_from"),
            (lambda c: c["transcripts"].__setitem__("git_branch", "other"), "transcripts.git_branch"),
            (lambda c: c["transcripts"].__setitem__("projects_dir", "/nonexistent/projects"), "transcripts.projects_dir"),
            (lambda c: c.__setitem__("repo", "/nonexistent/repo"), "repo"),
        ]
        for mutate, item in cases:
            with self.subTest(item=item), TempDir() as root:
                ws = self.setup_ws(root)
                cfg = C.load(ws)
                mutate(cfg)
                C.save(ws, cfg)
                problems, _ = doctor.run(ws)
                self.assertIn(item, [p[0] for p in problems], problems)

    def test_a_rebound_workspace_whose_history_is_elsewhere_is_not_a_fault(self):
        """F6 (load report 2026-09-18): a workspace rebound to a new repo before any session ran there keeps its
        history in a read-only `also` source. Calling that a fault put a false warning on the notch. With no
        history anywhere it stays a fault: then it is as likely a typo in the branch as a fresh start."""
        with TempDir() as root:
            ws = self.setup_ws(root)
            other = Path(root) / "elsewhere"
            other.mkdir()
            make_transcripts(root, other, "dev", [{"_file": "old", "type": "user", "timestamp": "2026-01-01T00:00:00Z",
                                                   "origin": {"kind": "human"}, "message": {"role": "user", "content": "hi"}}])
            cfg = C.load(ws)
            cfg["transcripts"]["git_branch"] = "fresh"
            cfg["transcripts"]["also"] = [{"git_branch": "dev", "cwd_prefix": str(other)}]
            C.save(ws, cfg)
            problems, facts = doctor.run(ws)
            self.assertNotIn("transcripts.git_branch", [p[0] for p in problems], problems)
            self.assertTrue(any("还没有" in f[1] for f in facts), facts)
            cfg["transcripts"]["also"] = [{"git_branch": "nope", "cwd_prefix": str(other)}]
            C.save(ws, cfg)
            problems, _ = doctor.run(ws)
            self.assertIn("transcripts.git_branch", [p[0] for p in problems])

    def test_cli_exit_code(self):
        from loop.cli import main
        with TempDir() as root:
            ws = self.setup_ws(root)
            self.assertEqual(main(["doctor", str(ws)]), 0)
            cfg = json.loads((ws / "config.json").read_text())
            cfg["ledger"]["path"] = "ev/missing.json"
            (ws / "config.json").write_text(json.dumps(cfg))
            self.assertEqual(main(["doctor", str(ws)]), 1)


if __name__ == "__main__":
    unittest.main()
