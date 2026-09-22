"""The readers skill: a packet built from the loop's index, outputs checked, a panel tallied and recorded as the
readers check's run. Fixtures are synthetic: a made-up bridge survey, no real manuscript text."""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import config as C
from loop import coverage as V

from fixtures import TempDir, git
from test_coverage import INTRO, commit, reindex, setup

# AWT_READERS_DIR: the mutated copy a red check is testing; otherwise the skill in this checkout.
SCRIPTS = Path(os.environ.get("AWT_READERS_DIR") or K.ENGINE_ROOT / ".claude" / "skills" / "readers" / "scripts")


def script(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


def reader_output(packet, who="R1_small_1", **drop):
    out = {"packet": packet["packet_id"],
           "paragraphs": [{"p": p["p"], "believe": f"It audits bridges ({who}).", "expect": "Methods.", "reread": [],
                           "guessed": ["gauge"]} for p in packet["paragraphs"]],
           "remember": ["bridges fail slowly", "inspections are rare", "gauges read 12"],
           "why_accept": "A cheap audit.", "closest_prior_work": "infrastructure surveys",
           "reuse": "the gauge check", "writing_got_in_way": "nothing", "outside_knowledge": "none"}
    for q in packet.get("questions") or []:
        out[q["id"]] = "a bridge"
    for k in drop:
        if k == "last_paragraph":
            out["paragraphs"] = out["paragraphs"][:-1]
        else:
            out.pop(k, None)
    return out


def panel(root, packet, bad=()):
    """Eight readers: 2 personas x 2 models x 2 samples; `bad` names outputs to damage."""
    d = Path(root) / "outputs"
    d.mkdir(exist_ok=True)
    bad = dict(bad)
    for persona in ("R1", "R2"):
        for model in ("small", "large"):
            for n in (1, 2):
                name = f"{persona}_{model}_{n}"
                drop = {bad[name]: True} if name in bad else {}
                (d / f"{name}.json").write_text(json.dumps(reader_output(packet, name, **drop)), encoding="utf-8")
    return d


class ReadersTest(unittest.TestCase):
    def build(self, root, ws, questions=True):
        q = Path(root) / "q.tsv"
        q.write_text("span\tWhich bridges does the survey cover?\n", encoding="utf-8")
        out = Path(root) / "packet"
        args = ["--workspace", ws, "--out", out] + (["--questions", q] if questions else [])
        r = script("build-reader-packet.py", *args)
        self.assertEqual(r.returncode, 0, r.stderr)
        return out, json.loads((out / "packet.json").read_text(encoding="utf-8"))

    def test_the_packet_reads_the_named_sections_keeps_citations_and_records_the_version(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            cfg["inputs"] = {"bib": "references.bib"}
            C.save(ws, cfg)
            out, packet = self.build(root, ws)
            text = (out / "manuscript.txt").read_text(encoding="utf-8")
            self.assertIn("[P1] We audit a bridge survey.", text)
            self.assertIn("(Smith, 2020)", text, "a citation becomes author-year, never a placeholder")
            self.assertNotIn("[cite]", text)
            self.assertEqual(packet["source"]["commit"], git(repo, "rev-parse", "HEAD"))
            self.assertEqual(packet["source"]["sections"], ["A", "I"])
            self.assertTrue(packet["snapshot"]["scope"])
            prompt = (out / "prompt_R1.txt").read_text(encoding="utf-8")
            self.assertIn('"span": Which bridges does the survey cover?', prompt)
            self.assertIn("outside_knowledge", prompt)

    def test_the_packet_shows_what_the_page_shows_not_the_markup_or_the_alt_text(self):
        # Environments and a figure's alt text span several indexed sentences; cleaned one sentence at a time they
        # reached the readers as an environment's name and options, and as a second copy of the figure in alt-text prose.
        with TempDir() as root:
            repo, ws = setup(root)
            intro = INTRO + (r"""
\paragraph{Asks.} \begin{enumerate}[label=(\alph*),nosep]
\item[Q1.] Which spans crack first? \item[Q2.] How often are they read? \end{enumerate}

\begin{figure}[htbp] \input{art/gauges} \Description{Alt text. A drawing of three gauges.
Each gauge has a dial.} \caption{Gauges on the north span.} \label{fig:gauges} \end{figure}
""")
            commit(repo, {"sections/01_intro.tex": intro}, "v2", 1_700_000_100)
            reindex(ws)
            out, _ = self.build(root, ws)
            text = (out / "manuscript.txt").read_text(encoding="utf-8")
            for debris in ("enumerate", "label=", "nosep", "figure", "[htbp]", "art/gauges", "Alt text", "dial"):
                self.assertNotIn(debris, text)
            self.assertIn("Q1. Which spans crack first?", text)
            self.assertIn("Figure caption: Gauges on the north span.", text)

    def test_personas_and_questions_can_come_from_the_workspace(self):
        with TempDir() as root:
            repo, ws = setup(root)
            q = Path(root) / "q.tsv"
            q.write_text("span\tWhich bridges?\n", encoding="utf-8")
            cfg = C.load(ws)
            cfg["target"] = {"readers": {"personas": {"R1": "a bridge engineer", "R2": "a county official"},
                                         "questions": str(q)}}
            C.save(ws, cfg)
            out = Path(root) / "p"
            self.assertEqual(script("build-reader-packet.py", "--workspace", ws, "--out", out).returncode, 0)
            prompt = (out / "prompt_R2.txt").read_text(encoding="utf-8")
            self.assertIn("Persona: a county official", prompt)
            self.assertIn('"span": Which bridges?', prompt)

    def test_nothing_to_read_exits_2(self):
        with TempDir() as root:
            empty = Path(root) / "e.txt"
            empty.write_text("\n\n", encoding="utf-8")
            self.assertEqual(script("build-reader-packet.py", "--text", empty, "--out", Path(root) / "o").returncode, 2)

    def test_incomplete_outputs_are_named_and_not_counted(self):
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = panel(root, packet, bad=[("R1_small_1", "outside_knowledge"), ("R2_large_2", "last_paragraph")])
            r = script("check-reader-output.py", "--packet", out / "packet.json", "--outputs", d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("qualified 6 of 8", r.stdout)
            self.assertIn("R1_small_1.json: outside_knowledge missing", r.stdout)
            self.assertIn("R2_large_2.json: paragraphs", r.stdout)
            self.assertEqual(script("check-reader-output.py", "--packet", out / "packet.json",
                                    "--outputs", Path(root) / "none").returncode, 2)

    def test_a_full_panel_is_recorded_as_the_current_reading_until_an_in_scope_edit(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            card = Path(root) / "card.md"
            card.write_text("M1 bridges fail slowly\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            C.save(ws, cfg)
            cfg = C.load(ws)
            self.assertEqual(next(r for r in V.compute(cfg, ws)["rows"] if r["id"] == "readers")["status"], V.NEVER)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            j = Path(root) / "j.tsv"
            j.write_text("".join(f"{p}_{m}_{n}\tM1\tmain\t✓\n{p}_{m}_{n}\tM1\tsub\t{'✓' if n == 1 else '✗'}\n"
                                 for p in ("R1", "R2") for m in ("small", "large") for n in (1, 2)), encoding="utf-8")
            r = script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d, "--judgments", j, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            got = json.loads(r.stdout)
            self.assertEqual(got["carried"]["M1"], {"carried": 4, "judged": 8}, "disagreeing judges count as not carried")
            self.assertEqual(got["agreement"], 0.5)
            self.assertTrue(got["recorded"])
            row = next(x for x in V.compute(cfg, ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.OK, row)
            self.assertIn("意图卡是草稿", row["result"])
            commit(repo, {"sections/01_intro.tex": INTRO.replace("Nobody watches them.", "Few watch them.")}, "c", 1_700_000_100)
            reindex(ws)
            row = next(x for x in V.compute(cfg, ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.STALE)
            self.assertEqual(row["changed"], 1)

    def test_a_small_panel_is_recorded_as_a_failure_not_a_reading(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            card = Path(root) / "card.md"
            card.write_text("M1\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            C.save(ws, cfg)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            for f in list(d.glob("R2_*.json")):
                f.rename(f.with_suffix(".skipped"))
            r = script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("面板不全", (out / "report.md").read_text(encoding="utf-8"))
            row = next(x for x in V.compute(C.load(ws), ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.FAILED)

    def test_fewer_than_eight_readers_is_a_failure_even_with_both_personas_and_models(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            card = Path(root) / "card.md"
            card.write_text("M1\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            C.save(ws, cfg)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            for f in list(d.glob("*_2.json")):
                f.rename(f.with_suffix(".skipped"))
            self.assertEqual(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d).returncode, 0)
            row = next(x for x in V.compute(C.load(ws), ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.FAILED)
            self.assertIn("少于 8", row["detail"])

    def test_an_output_for_another_packet_or_a_copy_is_not_a_reader(self):
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            stale = reader_output({**packet, "packet_id": "0ld0ld0ld0ld"}, "R1_small_1")
            (d / "R1_small_1.json").write_text(json.dumps(stale), encoding="utf-8")
            copy = json.loads((d / "R2_large_1.json").read_text(encoding="utf-8"))
            copy["why_accept"] = "  " + copy["why_accept"].upper() + "   "
            (d / "R2_large_2.json").write_text(json.dumps(copy), encoding="utf-8")
            r = script("check-reader-output.py", "--packet", out / "packet.json", "--outputs", d)
            self.assertIn("qualified 6 of 8", r.stdout)
            self.assertIn("R1_small_1.json: written for packet", r.stdout)
            self.assertIn("R2_large_2.json: identical to R2_large_1.json", r.stdout)

    def test_the_eight_reader_floor_cannot_be_lowered_and_one_judge_is_not_a_judgment(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            card = Path(root) / "card.md"
            card.write_text("M1\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            C.save(ws, cfg)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            j = Path(root) / "j.tsv"
            j.write_text("".join(f"{p}_{m}_{n}\tM1\tmain\t✓\n" for p in ("R1", "R2") for m in ("small", "large")
                                 for n in (1, 2)), encoding="utf-8")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d,
                                    "--judgments", j, "--json").stdout)
            self.assertEqual(got["carried"]["M1"], {"carried": 0, "judged": 0}, "one judge is not a judgment")
            self.assertIn("未判", (out / "report.md").read_text(encoding="utf-8"))
            for f in list(d.glob("*_2.json")):
                f.rename(f.with_suffix(".skipped"))
            script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d, "--min-readers", "2")
            row = next(x for x in V.compute(C.load(ws), ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.FAILED, "--min-readers cannot lower the calibrated floor")

    def test_nothing_qualified_to_tally_exits_2(self):
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = Path(root) / "outputs"
            d.mkdir()
            (d / "R1_small_1.json").write_text("{}", encoding="utf-8")
            self.assertEqual(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d).returncode, 2)

    def test_fisher_is_exact(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("tally", SCRIPTS / "tally-readers.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertAlmostEqual(mod.fisher_two_sided(8, 8, 0, 8), 0.000155, places=6)
        self.assertAlmostEqual(mod.fisher_two_sided(4, 8, 4, 8), 1.0)


if __name__ == "__main__":
    unittest.main()
