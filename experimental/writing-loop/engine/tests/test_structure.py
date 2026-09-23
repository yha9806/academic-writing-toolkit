"""audit-prose-structure.py: the structural measure that used to live only beside one manuscript, now a catalogued
check. Synthetic prose only: a plain baseline, and a target that opens every sentence with a condition."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K

from fixtures import TempDir

# AWT_AUDIT_DIR: the mutated copy a red check is testing; otherwise the audit skill in this checkout.
SCRIPTS = Path(os.environ.get("AWT_AUDIT_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "audit" / "scripts")

PLAIN = ("The bridge carries two lanes over the river, and the deck was replaced in the spring. Engineers measured "
         "the load on each span, and they logged the readings every week. The survey covers forty bridges in the "
         "county. Each report names the inspector, the date and the gauge that was read. ")
CONDITIONAL = ("Where a span is long and the traffic is heavy, the load rises. When the deck is wet the gauge reads "
               "high. If the gauge reads high the inspector returns. Whether the reading holds depends on the season. ")


def run(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "audit-prose-structure.py"), *map(str, args)],
                          capture_output=True, text=True)


def corpus(root, n=20):
    d = Path(root) / "baseline"
    d.mkdir()
    for i in range(n):
        (d / f"paper{i:02d}.txt").write_text((PLAIN * 12).replace("forty", f"forty-{i}"), encoding="utf-8")
    return d


class StructureTest(unittest.TestCase):
    def test_sentences_that_open_with_a_condition_are_outside_a_plain_baseline(self):
        with TempDir() as root:
            base = corpus(root)
            target = Path(root) / "draft"
            target.mkdir()
            (target / "intro.tex").write_text("\\section{Intro}\n" + CONDITIONAL * 10, encoding="utf-8")
            (target / "methods.tex").write_text("\\section{Methods}\n" + PLAIN * 10, encoding="utf-8")
            r = run("--target", target, "--baseline", base, "--json")
            self.assertEqual(r.returncode, 1, r.stderr)
            got = json.loads(r.stdout)
            self.assertIn("opens_with_sub", got["outliers"])
            self.assertEqual(got["baseline_documents"], 20)
            per = got["per_file"]
            self.assertGreater(per["intro.tex"]["opens_with_sub"], per["methods.tex"]["opens_with_sub"])

    def test_a_target_like_its_baseline_passes(self):
        with TempDir() as root:
            base = corpus(root)
            target = Path(root) / "same.txt"
            target.write_text(PLAIN * 12, encoding="utf-8")
            r = run("--target", target, "--baseline", base, "--json")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["outliers"], [])

    def test_nothing_to_measure_and_a_thin_baseline_exit_2(self):
        with TempDir() as full_root:
            empty = Path(full_root) / "empty"
            empty.mkdir()
            r = run("--target", empty, "--baseline", corpus(full_root))
            self.assertEqual(r.returncode, 2, "an empty target against a full baseline measures nothing")
            self.assertIn("nothing measured is not a pass", r.stderr)
        with TempDir() as root:
            base = corpus(root, n=5)
            target = Path(root) / "t.txt"
            target.write_text(PLAIN * 12, encoding="utf-8")
            r = run("--target", target, "--baseline", base)
            self.assertEqual(r.returncode, 2)
            self.assertIn("no percentile below 20", r.stderr)

    def test_the_catalogue_runs_it_against_the_venue_corpus(self):
        c = K.by_id("structure-venue")
        self.assertEqual(c["scripts"], ["audit/audit-prose-structure.py"])
        self.assertIn("target.venue_corpus.dir", c["needs"])


if __name__ == "__main__":
    unittest.main()
