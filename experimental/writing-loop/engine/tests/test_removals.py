"""Removed sentences in the writing loop (spec 2026-09-25 §4.2): the claims ledger's required wordings go to the
changed-sentence check, a removal that carried one holds the turn, and an acceptance is given for that removal only.
Fixtures are synthetic: the bridge survey of test_coverage, no manuscript text."""
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import config as C
from loop import coverage as V

from fixtures import TempDir
from test_coverage import INTRO, Probe, setup

LEDGER = """阶段：改稿

## 主张 C1 Bridges decay unseen
- 证据：synthetic
- 强度：中
- 允许的说法：nobody watches them
- 必须出现：\\bnobody watches\\b
"""


def with_ledger(root, ws):
    ledger = Path(root) / "claims.md"
    ledger.write_text(LEDGER, encoding="utf-8")
    cfg = C.load(ws)
    cfg["claims"] = str(ledger)
    C.save(ws, cfg)
    return C.load(ws)


class RemovalTest(unittest.TestCase):
    def test_a_removed_sentence_that_carried_a_required_wording_holds_the_turn_until_accepted(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = with_ledger(root, ws)
            with Probe(K.by_id("sentence-changes")):
                V.compute(cfg, ws, do_run=True)   # v1 is the clean base
            intro = Path(repo) / "sections/01_intro.tex"
            plain = intro.read_text(encoding="utf-8")
            intro.write_text(plain.replace(" Nobody watches them.", ""), encoding="utf-8")
            r = V.worktree_check(cfg, ws)
            self.assertEqual(len(r["unresolved"]), 1, r)
            flag = r["unresolved"][0]
            self.assertEqual(flag["flags"], ["removed_carrier"])
            self.assertTrue(flag["new"].startswith("删去："), flag)
            reason = V.stop_verdict(cfg, ws)
            self.assertIn(flag["key"], reason or "")
            V.accepted_path(cfg).write_text(f"{flag['key']}\tsaid again in the conclusion\tauthor\t…\n", encoding="utf-8")
            self.assertIsNone(V.stop_verdict(cfg, ws), "an accepted removal releases the turn")

    def test_without_a_ledger_pattern_a_plain_removal_is_counted_not_flagged(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            with Probe(K.by_id("sentence-changes")):
                V.compute(cfg, ws, do_run=True)
            intro = Path(repo) / "sections/01_intro.tex"
            intro.write_text(intro.read_text(encoding="utf-8").replace(" Nobody watches them.", ""), encoding="utf-8")
            r = V.worktree_check(cfg, ws)
            self.assertEqual(r["unresolved"], [], r)
            self.assertIn("删 1 句（0 句带着东西）", r["summary"])

    def test_the_carriers_file_is_not_read_as_prose(self):
        with TempDir() as root:
            _, ws = setup(root)
            cfg = with_ledger(root, ws)
            argv = K.by_id("sentence-changes")["argv"]({"cfg": cfg, "ws": str(ws), "tmp": str(root), "inputs": {}, "head": ""})
            path = Path(argv[argv.index("--carriers") + 1])
            self.assertEqual(path.read_text(encoding="utf-8").strip(), r"\bnobody watches\b")
            self.assertTrue(any(part.startswith(".") for part in path.relative_to(root).parts[:-1]),
                            "a carriers file outside a dot directory is read as a draft file by --target .")
            self.assertNotIn("--carriers", K.by_id("sentence-changes")["argv"](
                {"cfg": cfg, "ws": str(ws), "tmp": "", "inputs": {}, "head": ""}), "no directory, no file written")


if __name__ == "__main__":
    unittest.main()
