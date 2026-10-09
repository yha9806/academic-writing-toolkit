"""audit-cross-refs.py: a \\label on a heading with no number, which \\ref prints as the number of the section around
it (spec 2026-10-05-probe-growth, batch 1). Synthetic LaTeX only."""
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


def check(root, body, cls="article", preamble="", files=None):
    root = Path(root)
    for name, text in (files or {}).items():
        (root / name).write_text(text, encoding="utf-8")
    (root / "main.tex").write_text(f"\\documentclass{{{cls}}}\n{preamble}\n\\begin{{document}}\n{body}\n"
                                   "\\end{document}\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "audit-cross-refs.py"), "--root", str(root), "--json",
                        str(root / "main.tex")], capture_output=True, text=True)
    assert r.returncode in (0, 1), r.stderr[-400:]
    d = json.loads(r.stdout)
    assert (r.returncode == 1) == bool(d["issues"]), (r.returncode, d["issues"])
    return d


TIMING = "\\section{Results}\nThe lag is about six hours.\n\\paragraph{Timing.}\\label{sec:t}\nIt is stable.\n"
SEE = "\nThe spread is in Section~\\ref{sec:t}.\n"


class CrossRefsTest(unittest.TestCase):
    def test_a_label_after_a_run_in_paragraph_that_ref_prints_is_reported(self):
        with TempDir() as root:
            d = check(root, TIMING + SEE)
            [i] = d["issues"]
            self.assertEqual((i["kind"], i["label"], i["heading"]),
                             ("label-after-unnumbered-heading", "sec:t", "\\paragraph{Timing.}"))
            self.assertEqual(len(i["refs"]), 1)
            self.assertTrue(i["location"].endswith("main.tex:6"), i["location"])
            self.assertEqual((d["secnumdepth"], d["secnumdepth_from"]), (3, "default of article"))

    def test_a_label_on_a_numbered_heading_is_not(self):
        with TempDir() as root:
            self.assertEqual(check(root, TIMING.replace("\\paragraph{Timing.}", "\\subsection{Timing}") + SEE)["issues"], [])

    def test_a_label_inside_the_title_is_read_too(self):
        with TempDir() as root:
            body = TIMING.replace("\\paragraph{Timing.}\\label{sec:t}", "\\paragraph{Timing.\\label{sec:t}}")
            self.assertEqual([i["heading"] for i in check(root, body + SEE)["issues"]], ["\\paragraph{Timing.}"])

    def test_a_starred_heading_has_no_number_at_any_depth(self):
        with TempDir() as root:
            body = TIMING.replace("\\paragraph{Timing.}", "\\section*{Timing}")
            [i] = check(root, body + SEE)["issues"]
            self.assertEqual(i["why"], "starred")

    def test_secnumdepth_set_in_the_preamble_numbers_the_paragraph(self):
        with TempDir() as root:
            d = check(root, TIMING + SEE, preamble="\\setcounter{secnumdepth}{4}")
            self.assertEqual((d["secnumdepth"], d["issues"]), (4, []))

    def test_a_report_numbers_no_subsubsection(self):
        with TempDir() as root:
            body = TIMING.replace("\\paragraph{Timing.}", "\\subsubsection{Timing}")
            self.assertEqual(check(root, body + SEE)["issues"], [])
            d = check(root, body + SEE, cls="report")
            self.assertEqual((d["secnumdepth"], len(d["issues"])), (2, 1))

    def test_only_a_reference_that_prints_the_number_counts(self):
        with TempDir() as root:
            for see in ("", "\nSee \\nameref{sec:t} on page~\\pageref{sec:t}.\n"):
                self.assertEqual(check(root, TIMING + see)["issues"], [], see or "no reference")
            [i] = check(root, TIMING + "\nSee \\cref{sec:a,sec:t}.\n")["issues"]
            self.assertEqual(i["label"], "sec:t")

    def test_an_input_file_is_read(self):
        with TempDir() as root:
            d = check(root, "\\input{results}" + SEE, files={"results.tex": TIMING})
            [i] = d["issues"]
            self.assertTrue(i["location"].endswith("results.tex:3"), i["location"])

    def test_no_file_read_exits_2(self):
        with TempDir() as root:
            r = subprocess.run([sys.executable, str(SCRIPTS / "audit-cross-refs.py"), "--root", str(root),
                                str(Path(root) / "main.tex")], capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)


if __name__ == "__main__":
    unittest.main()
