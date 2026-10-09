"""Probes: drafts that reproduce a failure the checks once missed, each beside a corrected twin. The check a probe
names must flag the bad draft and must not flag the twin; a probe whose bad draft passes means that check cannot see
the failure it was added for (spec 2026-09-25 §4.1). Every probe is synthetic: no manuscript text, names or results.

A probe is a directory under probes/ holding probe.json, a bad/ draft, a good/ draft (the twin) and, for a check that
compares two versions, a base/ draft. probe.json names the check, its arguments ({draft} becomes bad or good) and the
flag the bad draft must raise: a sentence's flag, or the kind of an issue for a check that reports issues."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K

PROBES = Path(__file__).resolve().parent / "probes"
# AWT_AUDIT_DIR: the mutated copy a red check is testing; otherwise the skill in this checkout.
AUDIT = Path(os.environ.get("AWT_AUDIT_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "audit" / "scripts")
VERIFY_REFS = Path(os.environ.get("AWT_VERIFY-REFS_DIR")
                   or K.ENGINE_ROOT / ".claude" / "skills" / "verify-refs" / "scripts")
CHECKS = {"sentence-changes": AUDIT / "audit-sentence-changes.py", "cross-refs": AUDIT / "audit-cross-refs.py",
          "front-matter": AUDIT / "audit-front-matter.py", "cite-bib": VERIFY_REFS / "reconcile-cites.py"}


def run(probe, draft):
    spec = json.loads((probe / "probe.json").read_text(encoding="utf-8"))
    argv = [a.replace("{draft}", draft) for a in spec["argv"]]
    r = subprocess.run([sys.executable, str(CHECKS[spec["check"]]), *argv], cwd=probe, capture_output=True, text=True)
    if r.returncode not in (0, 1):
        raise AssertionError(f"{probe.name}/{draft}: the check did not run (exit {r.returncode}): {r.stderr[-400:]}")
    data = json.loads(r.stdout)
    flags = [f for s in data.get("sentences") or [] for f in s.get("flags") or []]
    flags += [i["kind"] for i in data.get("issues") or [] if isinstance(i, dict) and "kind" in i]
    carried = [c for s in data.get("sentences") or [] for c in s.get("carried") or []]
    return spec, flags, carried


def probes():
    return sorted(p for p in PROBES.iterdir() if (p / "probe.json").is_file())


class ProbeTest(unittest.TestCase):
    def test_there_are_probes(self):
        self.assertTrue(probes(), f"no probe under {PROBES}")

    def test_each_probe_is_flagged_on_the_bad_draft_and_not_on_its_twin(self):
        for probe in probes():
            with self.subTest(probe=probe.name):
                spec, bad, carried = run(probe, "bad")
                self.assertTrue(any(spec["expect_flag"] in f for f in bad),
                                f"{probe.name}: {spec['check']} did not flag the failure it was added for "
                                f"({spec['failure']}); flags raised: {bad}")
                if spec.get("expect_carried"):
                    # the rule the probe was made for, not another one that happens to catch the same sentence
                    self.assertTrue(any(c.startswith(spec["expect_carried"]) for c in carried),
                                    f"{probe.name}: flagged, but not for {spec['expect_carried']}: {carried}")
                _, good, _ = run(probe, "good")
                self.assertFalse(any(spec["expect_flag"] in f for f in good),
                                 f"{probe.name}: the corrected twin is flagged too: {good}")

    def test_no_twin_raises_the_flag_of_any_probe(self):
        # spec 2026-10-05-probe-growth D4: a rule added for one probe must not flag the corrected twins of the others
        wanted = {json.loads((p / "probe.json").read_text(encoding="utf-8"))["expect_flag"] for p in probes()}
        for probe in probes():
            with self.subTest(probe=probe.name):
                _, good, _ = run(probe, "good")
                self.assertEqual([f for f in good if any(w in f for w in wanted)], [],
                                 f"{probe.name}: its corrected twin raises another probe's flag")

    def test_the_deleted_research_question_is_caught(self):
        spec, bad, _ = run(PROBES / "deleted-question", "bad")
        self.assertIn("removed_carrier", bad)


if __name__ == "__main__":
    unittest.main()
