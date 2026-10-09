"""`loop update` and health (plan 2.4, spec T8): a stopped or broken updater, and a tampered index, must show."""
import contextlib
import io
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

from loop import health as HL
from loop.cli import main

from fixtures import TempDir, draft_md, git, make_transcripts
from test_hooks import HOOKS, setup  # noqa: F401  (shared fixture)

sys.path.insert(0, str(HOOKS))
import loop_hook as LH  # noqa: E402

from loop import config as C  # noqa: E402


def items(problems):
    return [i for i, _ in problems]


# `loop update` in a second process, stopped inside its lock until the test lets it go. Only the coverage step, the
# last thing done under the lock, is replaced by the wait, so the lock code that runs is the engine's own: the one
# this test imports (redcheck points PYTHONPATH at a mutated copy).
HOLDER = r"""
import isolation  # noqa: F401
import sys
import time
from pathlib import Path
from loop import cli
ws, entered, go = sys.argv[1:4]
def held(ws_, cfg):
    Path(entered).write_text("in", encoding="utf-8")
    end = time.time() + 60
    while not Path(go).exists() and time.time() < end:
        time.sleep(0.02)
cli._coverage_after_update = held
sys.exit(cli.main(["update", ws, "--reason", "holder"]))
"""


class Holder:
    def __init__(self, root, ws):
        import loop
        self.entered, self.go = Path(root) / "holder-entered", Path(root) / "holder-go"
        engine = Path(loop.__file__).resolve().parents[1]
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(engine), str(engine / "tests")]))
        self.proc = subprocess.Popen([sys.executable, "-c", HOLDER, str(ws), str(self.entered), str(self.go)],
                                     env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        end = time.time() + 60
        while not self.entered.exists():
            if self.proc.poll() is not None or time.time() > end:
                self._stop()
                raise AssertionError(f"the holder never got inside its lock: {self.proc.stderr.read()}")
            time.sleep(0.02)

    def release(self):
        self.go.write_text("go", encoding="utf-8")
        out, err = self.proc.communicate(timeout=60)
        return self.proc.returncode, out, err

    def _stop(self):
        if self.proc.poll() is None:
            self.go.write_text("go", encoding="utf-8")
            try:
                self.proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.communicate()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._stop()


class UpdateTest(unittest.TestCase):
    def test_update_builds_the_index_and_records_success(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            self.assertEqual(main(["update", str(ws), "--reason", "t"]), 0)
            self.assertTrue((ws / "index" / "explanations.json").exists())
            self.assertEqual(HL.load(ws)["last_ok"]["reason"], "t")
            self.assertEqual(HL.assess(C.load(ws)), [])

    def test_a_running_update_is_not_doubled_but_asked_to_go_round_again(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            (ws / "cache").mkdir(exist_ok=True)
            (ws / "cache" / "update.lock").write_text("")
            self.assertEqual(main(["update", str(ws)]), 0)
            self.assertTrue((ws / "cache" / "update.dirty").exists())
            self.assertFalse((ws / "index" / "sources.json").exists())

    def test_a_lock_left_by_a_killed_update_is_taken_over(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            (ws / "cache").mkdir(exist_ok=True)
            lock = ws / "cache" / "update.lock"
            lock.write_text("")
            old = time.time() - 3600
            os.utime(lock, (old, old))
            self.assertEqual(main(["update", str(ws)]), 0)
            self.assertTrue((ws / "index" / "sources.json").exists())
            self.assertFalse(lock.exists())

    def test_an_old_lock_whose_holder_is_still_running_is_not_taken_over(self):
        # An update that runs past STALE_LOCK is slow, not dead. Taking its lock over ran two updates of one workspace
        # side by side. The lock is aged by hand: nothing here waits STALE_LOCK out.
        with TempDir() as root:
            repo, ws, _ = setup(root)
            lock, dirty = ws / "cache" / "update.lock", ws / "cache" / "update.dirty"
            with Holder(root, ws) as holder:
                old = time.time() - 3600
                os.utime(lock, (old, old))
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(["update", str(ws), "--reason", "second"]), 0)
                self.assertIn("另一次更新正在进行", out.getvalue(), "the second update must leave, not run alongside")
                self.assertTrue(dirty.exists(), "the request is kept for the running update to go round again")
                code, _, err = holder.release()
                self.assertEqual(code, 0, err)
            self.assertFalse(lock.exists(), "the holder still removes its own lock")

    def test_a_lock_whose_holder_has_exited_is_taken_over_at_once(self):
        # The holder's pid is in the lock: once that process is gone the lock is free, however fresh its time.
        with TempDir() as root:
            repo, ws, _ = setup(root)
            (ws / "cache").mkdir(exist_ok=True)
            gone = subprocess.Popen([sys.executable, "-c", "pass"])
            gone.wait()
            lock = ws / "cache" / "update.lock"
            lock.write_text(f"{gone.pid} a-token-of-an-exited-update\n", encoding="utf-8")
            self.assertEqual(main(["update", str(ws)]), 0)
            self.assertTrue((ws / "index" / "sources.json").exists())
            self.assertFalse(lock.exists())

    def test_an_update_that_ends_removes_only_its_own_lock(self):
        # The lock passed to someone else while this update ran (the takeover rule on a platform without a pid
        # probe, or a hand-cleared lock). The update that ends must not delete the new holder's lock.
        with TempDir() as root:
            repo, ws, _ = setup(root)
            lock = ws / "cache" / "update.lock"
            with Holder(root, ws) as holder:
                lock.unlink()
                theirs = f"{os.getpid()} a-token-that-is-not-the-holders\n"
                lock.write_text(theirs, encoding="utf-8")
                code, _, err = holder.release()
                self.assertEqual(code, 0, err)
            self.assertTrue(lock.exists(), "the ending update deleted a lock it did not hold")
            self.assertEqual(lock.read_text(encoding="utf-8"), theirs)

    def test_a_failure_is_recorded_and_stays_visible_until_a_later_success(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            cfg = json.loads((ws / "config.json").read_text())
            good = cfg["ref"]
            cfg["ref"] = "no-such-branch"
            (ws / "config.json").write_text(json.dumps(cfg))
            self.assertEqual(main(["update", str(ws)]), 1)
            self.assertIn("更新失败", items(HL.file_problems(ws)))
            cfg["ref"] = good
            (ws / "config.json").write_text(json.dumps(cfg))
            self.assertEqual(main(["update", str(ws)]), 0)
            self.assertNotIn("更新失败", items(HL.file_problems(ws)))


class HealthTest(unittest.TestCase):
    def test_never_updated_is_a_problem_not_silence(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            self.assertIn("从未更新", items(HL.file_problems(ws)))

    def test_a_new_commit_without_an_update_is_lag(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            main(["update", str(ws)])
            (repo / "drafts" / "DRAFT-v2.md").write_text(draft_md("A title", "One sentence.", ["Intro one."]), encoding="utf-8")
            git(repo, "add", "drafts/DRAFT-v2.md")
            git(repo, "commit", "-qm", "v2")
            p = HL.assess(C.load(ws))
            self.assertIn(("落后", "分支比索引多 1 个提交"), p)

    def test_a_grown_transcript_is_lag(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            main(["update", str(ws)])
            make_transcripts(root, repo, "main", [{"type": "user", "timestamp": "2026-01-02T00:00:00Z",
                                                   "origin": {"kind": "human"}, "message": {"role": "user", "content": "again"}}])
            self.assertIn("落后", items(HL.assess(C.load(ws))))

    def test_a_tampered_index_is_named_as_tampered(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            main(["update", str(ws)])
            p = ws / "index" / "explanations.json"
            p.write_text(p.read_text().replace("[]", '[{"forged": true}]', 1))
            self.assertIn(("索引不一致", "真源与引擎都没变，索引却不同：索引被改动过"), HL.assess(C.load(ws)))

    def test_health_cli_exit_code(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            self.assertEqual(main(["health", str(ws), "--quick"]), 1)
            main(["update", str(ws)])
            self.assertEqual(main(["health", str(ws)]), 0)


class AckTest(unittest.TestCase):
    def test_ack_clears_what_was_shown_but_keeps_the_record(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            HL.record_event(ws, "guard_denied", "Write → x", now=100)
            HL.record_event(ws, "hook_error", "boom", now=101)
            self.assertIn("钩子异常", items(HL.file_problems(ws)))
            self.assertEqual(len(HL.file_notices(ws)), 1)
            HL.ack(ws, now=102)
            self.assertNotIn("钩子异常", items(HL.file_problems(ws)))
            self.assertEqual(HL.file_notices(ws), [])
            self.assertEqual(len(HL.load(ws)["events"]), 2)
            HL.record_event(ws, "guard_denied", "Write → y", now=103)
            self.assertEqual(len(HL.file_notices(ws)), 1)
            self.assertEqual(main(["ack", str(ws)]), 0)
            self.assertEqual(HL.file_notices(ws), [])


class DetachedTest(unittest.TestCase):
    def test_the_hook_spawned_update_finishes_on_its_own(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            LH.spawn_update(ws, "spawned")
            deadline = time.time() + 20
            while time.time() < deadline and (HL.load(ws).get("last_ok") or {}).get("reason") != "spawned":
                time.sleep(0.05)
            self.assertEqual(HL.load(ws)["last_ok"]["reason"], "spawned")
            self.assertTrue((ws / "index" / "sources.json").exists())



class NotchCountsTest(unittest.TestCase):
    """What the notch counts (lintel C7, gap 4): refused writes and gate overrides since the last ack, one per event."""

    def test_refused_writes_and_overrides_are_counted_per_event_and_an_ack_clears_them(self):
        with TempDir() as root:
            (root / "cache").mkdir()
            for i in range(3):
                HL.record_event(root, "guard_denied", f"Write → human/x{i}", now=100 + i)
            HL.record_event(root, "stop_gate_overridden", "1 句标出未处理", now=104)
            self.assertEqual(len(HL.guard_denials(root)), 3)
            self.assertEqual(len(HL.gate_overrides(root)), 1)
            self.assertEqual(len(HL.file_notices(root)), 1)          # the notice is one line whatever the count
            HL.ack(root, now=110)
            HL.record_event(root, "guard_denied", "Write → human/y", now=120)
            self.assertEqual([e["detail"] for e in HL.guard_denials(root)], ["Write → human/y"])
            self.assertEqual(HL.gate_overrides(root), [])

if __name__ == "__main__":
    unittest.main()
