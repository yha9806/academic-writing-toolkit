import io
import json
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

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

    def test_a_new_workspace_on_a_branch_that_exists_but_has_no_session_yet_is_not_a_fault(self):
        """2026-10-04: two papers put into the loop with `init` (transcripts default to the repo and its ref) showed a red
        「跑挂了」 on the notch before anyone had worked on them. A branch that exists in the repo is a fresh start; a
        branch that does not exist stays a fault, since then it is as likely a typo."""
        import subprocess
        with TempDir() as root:
            ws = self.setup_ws(root)
            cfg = C.load(ws)
            subprocess.run(["git", "-C", cfg["transcripts"]["cwd_prefix"], "branch", "paper-two"], check=True)
            cfg["transcripts"]["git_branch"] = "paper-two"
            C.save(ws, cfg)
            problems, facts = doctor.run(ws)
            self.assertNotIn("transcripts.git_branch", [p[0] for p in problems], problems)
            self.assertTrue(any("还没有会话" in f[1] for f in facts), facts)
            cfg["transcripts"]["git_branch"] = "paper-twoo"
            C.save(ws, cfg)
            problems, _ = doctor.run(ws)
            self.assertIn("transcripts.git_branch", [p[0] for p in problems])

    def test_a_target_that_is_not_registered_is_a_fact_and_a_configured_path_that_does_not_resolve_is_a_problem(self):
        from loop import doctor
        with TempDir() as root:
            ws = self.setup_ws(root)
            problems, facts = doctor.run(ws)
            self.assertEqual(problems, [], "no target registered is a coverage gap, not a broken tool")
            self.assertTrue(any(item == "target" and "未登记" in msg for item, msg in facts), facts)
            cfg = C.load(ws)
            cfg["target"] = {"venue": "J", "venue_corpus": {"manifest": "nope.json", "dir": str(root / "nodir")},
                             "intent_card": str(root / "card.md")}
            C.save(ws, cfg)
            items = [item for item, _ in doctor.run(ws)[0]]
            self.assertEqual(sorted(items), ["target.intent_card", "target.venue_corpus.dir",
                                             "target.venue_corpus.manifest"])

    def test_cli_exit_code(self):
        from loop.cli import main
        with TempDir() as root:
            ws = self.setup_ws(root)
            reg = Path(root) / "registry"
            reg.write_text(f"{ws}\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"AWT_LOOP_REGISTRY": str(reg)}), redirect_stdout(io.StringIO()):
                self.assertEqual(main(["doctor", str(ws)]), 0)
                cfg = json.loads((ws / "config.json").read_text())
                cfg["ledger"]["path"] = "ev/missing.json"
                (ws / "config.json").write_text(json.dumps(cfg))
                self.assertEqual(main(["doctor", str(ws)]), 1)


class NamedSessionTest(unittest.TestCase):
    """transcripts.sessions names primary sessions by id. Each id must resolve to a transcript file, and a manuscript
    whose sessions are all named by id is not missing its sessions because none ran on the configured branch."""

    def setup_ws(self, root):
        ws = DoctorTest.setup_ws(self, root)
        other = Path(root) / "elsewhere"
        other.mkdir()
        make_transcripts(root, other, "spike", [{"_file": "s7", "type": "user", "timestamp": "2026-01-02T00:00:00Z",
                                                 "origin": {"kind": "human"}, "message": {"role": "user", "content": "x"}}])
        cfg = C.load(ws)
        cfg["transcripts"]["sessions"] = [{"id": "s7", "note": "synthetic"}]
        C.save(ws, cfg)
        return ws

    def test_a_named_session_is_found_and_one_that_is_not_is_a_problem(self):
        with TempDir() as root:
            ws = self.setup_ws(root)
            problems, facts = doctor.run(ws)
            self.assertEqual(problems, [])
            self.assertTrue(any(item == "transcripts.sessions" and "1/1" in msg for item, msg in facts), facts)
            cfg = C.load(ws)
            cfg["transcripts"]["sessions"].append({"id": "s-missing", "note": "typo"})
            C.save(ws, cfg)
            problems, _ = doctor.run(ws)
            self.assertIn("transcripts.sessions[1]", [p[0] for p in problems], problems)

    def test_with_named_sessions_no_session_on_the_branch_is_not_a_fault(self):
        with TempDir() as root:
            ws = self.setup_ws(root)
            cfg = C.load(ws)
            cfg["transcripts"]["git_branch"] = "no-such-branch"
            C.save(ws, cfg)
            problems, _ = doctor.run(ws)
            self.assertNotIn("transcripts.git_branch", [p[0] for p in problems], problems)


class RegistryTest(unittest.TestCase):
    """A workspace was set up and never added to the hook registry. Every configured path resolved, so doctor said
    nothing; the hooks never fired for it, the author's words were not recorded, no update ran after an edit, and no
    session was told the paper's state. Being listed is now part of what doctor checks, and `loop state` and
    `loop coverage` say it in their first line."""

    def setup_ws(self, root):
        return DoctorTest.setup_ws(self, root)

    def doctor(self, ws, reg):
        from loop.cli import main
        buf = io.StringIO()
        with mock.patch.dict(os.environ, {"AWT_LOOP_REGISTRY": str(reg)}), redirect_stdout(buf):
            rc = main(["doctor", str(ws)])
        return rc, buf.getvalue()

    def test_a_workspace_the_registry_does_not_list_is_named_and_fails_doctor(self):
        with TempDir() as root:
            ws = self.setup_ws(root)
            reg = Path(root) / "registry"
            reg.write_text(f"# synthetic\n{Path(root) / 'another-ws'}\n", encoding="utf-8")
            rc, out = self.doctor(ws, reg)
            self.assertEqual(rc, 1, out)
            self.assertIn("不在钩子登记表", out)
            self.assertIn("钩子不会触发", out)
            self.assertIn(str(reg), out)

    def test_a_listed_workspace_passes_however_the_line_spells_it(self):
        with TempDir() as root:
            ws = self.setup_ws(root)
            reg = Path(root) / "registry"
            for spelled in (str(ws), str(ws) + "/", str(ws / ".." / ws.name)):
                with self.subTest(spelled=spelled):
                    reg.write_text(f"  {spelled}  \n", encoding="utf-8")
                    rc, out = self.doctor(ws, reg)
                    self.assertEqual(rc, 0, out)
                    self.assertNotIn("不在钩子登记表", out)
                    self.assertNotIn("读不到", out)

    def test_a_registry_that_cannot_be_read_is_said_never_taken_for_listed(self):
        with TempDir() as root:
            ws = self.setup_ws(root)
            rc, out = self.doctor(ws, Path(root) / "no-registry-here")
            self.assertEqual(rc, 1, out)
            self.assertIn("读不到", out)
            self.assertIn("钩子不会触发", out)

    def test_state_and_coverage_say_it_in_their_first_line(self):
        from loop.cli import main
        with TempDir() as root:
            ws = self.setup_ws(root)
            reg = Path(root) / "registry"
            reg.write_text("", encoding="utf-8")
            for cmd in ("state", "coverage"):
                with self.subTest(cmd=cmd):
                    buf = io.StringIO()
                    with mock.patch.dict(os.environ, {"AWT_LOOP_REGISTRY": str(reg)}), redirect_stdout(buf):
                        main([cmd, str(ws)])
                    first = buf.getvalue().splitlines()[0]
                    self.assertIn("不在钩子登记表", first)
            reg.write_text(f"{ws}\n", encoding="utf-8")
            for cmd in ("state", "coverage"):
                with self.subTest(cmd=cmd, listed=True):
                    buf = io.StringIO()
                    with mock.patch.dict(os.environ, {"AWT_LOOP_REGISTRY": str(reg)}), redirect_stdout(buf):
                        main([cmd, str(ws)])
                    self.assertNotIn("登记表", buf.getvalue())


class BranchScanTest(unittest.TestCase):
    """2026-10-08：常驻来源进程每轮跑 doctor，这里把每个会话文件整份读进内存只为找分支名（一份稿子两个前缀下
    1.8 GB，最大一份 375 MB）。现在分块读、找到就停；没找到的记下读到哪，文件长了只读新增的尾部。"""

    BRANCH = "claude/the-branch"

    def setUp(self):
        doctor._SCANNED.clear()

    def _line(self, branch):
        return (json.dumps({"type": "user", "gitBranch": branch, "message": "x"}) + "\n").encode()

    def _needle_hits(self, files):
        return doctor._on_branch(files, self.BRANCH)

    def test_a_session_file_is_searched_without_reading_it_whole(self):
        with TempDir() as root:
            f = Path(root) / "s.jsonl"
            f.write_bytes(self._line("other") * 200 + self._line(self.BRANCH))
            with mock.patch.object(doctor, "_CHUNK", 256), \
                    mock.patch.object(Path, "read_bytes", side_effect=AssertionError("read whole")):
                self.assertEqual(self._needle_hits([f]), [f])

    def test_a_match_cut_by_a_chunk_boundary_is_found(self):
        with TempDir() as root:
            f = Path(root) / "s.jsonl"
            hit = self._line(self.BRANCH)
            for cut in range(1, len(hit)):
                doctor._SCANNED.clear()
                f.write_bytes(b"x" * (256 - cut) + hit)
                with mock.patch.object(doctor, "_CHUNK", 256), mock.patch.object(doctor, "_OVERLAP", 128):
                    self.assertEqual(self._needle_hits([f]), [f], f"cut {cut} bytes into the match")

    def test_a_file_that_gains_the_branch_is_found_and_only_its_new_tail_is_read(self):
        with TempDir() as root:
            f = Path(root) / "s.jsonl"
            f.write_bytes(self._line("other") * 500)
            self.assertEqual(self._needle_hits([f]), [])
            with f.open("ab") as fh:
                fh.write(self._line(self.BRANCH))
            seeks = []
            real_open = open

            def spying_open(path, mode="r", *a, **k):
                fh = real_open(path, mode, *a, **k)
                real_seek = fh.seek
                fh.seek = lambda pos, *x: (seeks.append(pos), real_seek(pos, *x))[1]
                return fh
            with mock.patch("builtins.open", spying_open):
                self.assertEqual(self._needle_hits([f]), [f])
            self.assertTrue(seeks and seeks[0] > 0, f"the second scan starts near where the first stopped: {seeks}")

    def test_a_file_rewritten_shorter_is_read_from_the_top(self):
        with TempDir() as root:
            f = Path(root) / "s.jsonl"
            f.write_bytes(self._line("other") * 500)   # longer than the overlap, so resuming would start past the end
            self.assertEqual(self._needle_hits([f]), [])
            f.write_bytes(self._line(self.BRANCH))
            self.assertEqual(self._needle_hits([f]), [f])


if __name__ == "__main__":
    unittest.main()
