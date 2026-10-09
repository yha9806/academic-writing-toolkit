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
            self.assertIn("Caption: Gauges on the north span.", text)

    def test_alt_text_with_an_escaped_brace_or_a_short_form_and_a_table_spec_do_not_leak_or_swallow(self):
        with TempDir() as root:
            repo, ws = setup(root)
            intro = INTRO + (r"""
\begin{table}[b]\centering\caption[Short]{Readings by span.} \begin{tabular}{@{}lr@{}} north & 12 \\ \end{tabular}
\end{table} After the table the survey continues.

\begin{figure}[t] \Description[Gauge dial]{Alt text with a brace \{0, 1. The dial.} \caption{Dials.} \end{figure}
The next sentence must survive.
""")
            commit(repo, {"sections/01_intro.tex": intro}, "v2", 1_700_000_100)
            reindex(ws)
            out, _ = self.build(root, ws)
            text = (out / "manuscript.txt").read_text(encoding="utf-8")
            for debris in ("@", "lr", "Short", "Gauge dial", "Alt text", "The dial"):
                self.assertNotIn(debris, text)
            for kept in ("Caption: Readings by span.", "north", "After the table the survey continues.",
                         "Caption: Dials.", "The next sentence must survive."):
                self.assertIn(kept, text)

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

    def test_a_cross_reference_shows_its_number_from_the_aux_or_says_the_packet_omits_it(self):
        # Every \\ref used to become "§x", and most readers of one panel spent "what got in the way" on a placeholder
        # the page does not show (spec 2026-09-25 §4.3). With the compiled .aux the number is the page's; a label the
        # .aux lacks is said to be omitted, and the prompt tells readers that is the packet's limit.
        with TempDir() as root:
            src = Path(root) / "d.tex"
            src.write_text("Methods are in \\S\\ref{sec:m}. Figure~\\ref{fig:a} shows the gauges.\n\n"
                           "See \\autoref{tab:t} and \\S~\\ref{sec:gone}.\n", encoding="utf-8")
            aux = Path(root) / "d.aux"
            aux.write_text("\\newlabel{sec:m}{{3.2}{4}{Methods}{section.3.2}{}}\n"
                           "\\newlabel{fig:a}{{2}{5}{Gauges}{figure.2}{}}\n"
                           "\\newlabel{tab:t}{{4}{6}}\n", encoding="utf-8")
            r = script("build-reader-packet.py", "--text", src, "--aux", aux, "--out", Path(root) / "o")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (Path(root) / "o" / "manuscript.txt").read_text(encoding="utf-8")
            self.assertNotIn("§x", text)
            for shown in ("§3.2", "Figure 2 shows", "Table 4", "§(number omitted)"):
                self.assertIn(shown, text)
            packet = json.loads((Path(root) / "o" / "packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["references"], {"resolved": 3, "omitted": 1, "aux": str(aux.resolve()),
                                                    "aux_older_than_source": None})
            head = (Path(root) / "o" / "prompt_R1.txt").read_text(encoding="utf-8").split("MANUSCRIPT")[0]
            self.assertIn("(number omitted)", head, "the readers are told the omission is the packet's")

    def test_an_aux_compiled_before_the_version_read_is_said_to_be_stale(self):
        # 09-27: an .aux compiled at 18:09 numbered a draft last committed at 18:34, and nothing said so; readers may
        # then complain about numbers the page does not show. The packet records it, the build says it, the report too.
        with TempDir() as root:
            src = Path(root) / "d.tex"
            src.write_text("Methods are in \\S\\ref{sec:m}.\n", encoding="utf-8")
            aux = Path(root) / "d.aux"
            aux.write_text("\\newlabel{sec:m}{{3.2}{4}}\n", encoding="utf-8")
            t = src.stat().st_mtime
            os.utime(aux, (t - 3600, t - 3600))
            r = script("build-reader-packet.py", "--text", src, "--aux", aux, "--out", Path(root) / "o")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("before the draft last changed", r.stdout)
            packet = json.loads((Path(root) / "o" / "packet.json").read_text(encoding="utf-8"))
            self.assertIsNotNone(packet["references"]["aux_older_than_source"])
            os.utime(aux, (t + 60, t + 60))
            r = script("build-reader-packet.py", "--text", src, "--aux", aux, "--out", Path(root) / "o2")
            self.assertNotIn("before the draft last changed", r.stdout)
            self.assertIsNone(json.loads((Path(root) / "o2" / "packet.json").read_text(encoding="utf-8"))["references"]["aux_older_than_source"])
            # Workspace mode: compared with the draft files on disk, not the commit time -- compiling and then committing
            # the same text is the usual order, and would otherwise always read as stale.
            repo, ws = setup(Path(root) / "w")
            old_aux = Path(root) / "old.aux"
            old_aux.write_text("", encoding="utf-8")
            os.utime(old_aux, (946_684_800, 946_684_800))   # 2000-01-01, before the fixture's commits
            out = Path(root) / "p"
            r = script("build-reader-packet.py", "--workspace", ws, "--out", out, "--aux", old_aux)
            self.assertEqual(r.returncode, 0, r.stderr)
            packet = json.loads((out / "packet.json").read_text(encoding="utf-8"))
            self.assertIsNotNone(packet["references"]["aux_older_than_source"])
            fresh = Path(root) / "fresh.aux"
            fresh.write_text("", encoding="utf-8")
            later = max(p.stat().st_mtime for p in Path(repo).rglob("*.tex")) + 60
            os.utime(fresh, (later, later))
            r = script("build-reader-packet.py", "--workspace", ws, "--out", Path(root) / "p2", "--aux", fresh)
            self.assertIsNone(json.loads((Path(root) / "p2" / "packet.json").read_text(encoding="utf-8"))["references"]["aux_older_than_source"],
                              "an .aux compiled after the last edit is not stale, whenever the commit came")
            d = panel(Path(root) / "w", packet)
            script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d)
            self.assertIn("交叉引用编号可能过期", (out / "report.md").read_text(encoding="utf-8"))

    def test_without_an_aux_every_reference_says_its_number_is_omitted(self):
        with TempDir() as root:
            src = Path(root) / "d.tex"
            src.write_text("Methods are in \\S\\ref{sec:m}. The table (\\ref{tab:t}) lists them.\n", encoding="utf-8")
            r = script("build-reader-packet.py", "--text", src, "--out", Path(root) / "o")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (Path(root) / "o" / "manuscript.txt").read_text(encoding="utf-8")
            self.assertNotIn("§x", text)
            self.assertIn("§(number omitted)", text)
            packet = json.loads((Path(root) / "o" / "packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["references"], {"resolved": 0, "omitted": 2, "aux": None, "aux_older_than_source": None})

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

    def test_remember_written_as_one_string_is_named_as_such_not_as_missing(self):
        # A reader that numbered its three points inside one string was reported as "remember missing or empty"; the
        # panel's own count then disagreed with the script's, and the report used its own (spec 2026-09-25 §4.3).
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = Path(root) / "one"
            d.mkdir()
            data = reader_output(packet)
            data["span"] = "the northern district"
            data["remember"] = "1. bridges fail slowly 2. inspections are rare 3. gauges read 12"
            (d / "R1_small_1.json").write_text(json.dumps(data), encoding="utf-8")
            r = script("check-reader-output.py", "--packet", out / "packet.json", "--outputs", d)
            self.assertEqual(r.returncode, 2)
            self.assertIn("remember is one string, not a list", r.stdout)
            self.assertNotIn("remember missing", r.stdout)

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

    def judgments(self, root, name, carriers, extra=""):
        """Two judges who agree: ✓ for the readers in `carriers`, ✗ for the rest, on point M1."""
        j = Path(root) / name
        rows = []
        for pr in ("R1", "R2"):
            for m in ("small", "large"):
                for n in (1, 2):
                    r = f"{pr}_{m}_{n}"
                    v = "✓" if r in carriers else "✗"
                    rows += [f"{r}\tM1\tmain\t{v}\n", f"{r}\tM1\tsub\t{v}\n"]
        j.write_text("".join(rows) + extra, encoding="utf-8")
        return j

    def test_a_repeat_panel_sets_the_noise_floor_and_a_change_inside_it_is_said_to_be_noise(self):
        # One panel run twice on one text moved a point by three readers of sixteen, the size the round's rule called
        # a clear drop (spec 2026-09-25 §4.3). A comparison is read against that spread, or says it has none.
        all8 = [f"{pr}_{m}_{n}" for pr in ("R1", "R2") for m in ("small", "large") for n in (1, 2)]
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            j = self.judgments(root, "j.tsv", all8[:6])
            rj = self.judgments(root, "rj.tsv", all8[:3])
            cj = self.judgments(root, "cj.tsv", all8[:4])
            args = ["--packet", out / "packet.json", "--outputs", d, "--judgments", j, "--compare-packet",
                    out / "packet.json", "--compare-outputs", d, "--compare-judgments", cj, "--json"]
            got = json.loads(script("tally-readers.py", *args, "--repeat-outputs", d, "--repeat-judgments", rj).stdout)
            self.assertAlmostEqual(got["noise_floor"]["M1"]["spread"], 3 / 8)
            self.assertIs(got["compare"]["M1"]["inside_noise"], True, "6/8 against 4/8 is inside a 6/8-3/8 spread")
            self.assertIn("在噪声内", (out / "report.md").read_text(encoding="utf-8"))
            got = json.loads(script("tally-readers.py", *args).stdout)
            self.assertIsNone(got["compare"]["M1"]["inside_noise"])
            self.assertIn("没有同包重跑", (out / "report.md").read_text(encoding="utf-8"))

    def test_a_misreading_is_compared_only_on_a_question_both_versions_asked(self):
        # A misreading gone in the new version could mean nobody made it or nobody mentioned it (FOR-AWT 41). A point
        # asked as a directed question in one version and not the other is not compared; a free-recall point is
        # compared with a note; the same question in both versions is the paired design.
        all8 = [f"{pr}_{m}_{n}" for pr in ("R1", "R2") for m in ("small", "large") for n in (1, 2)]
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)                      # asks "span"
            d = panel(root, packet)
            span = lambda carriers: "".join(f"{r}\tspan\t{j}\t{'✓' if r in carriers else '✗'}\n"
                                            for r in all8 for j in ("main", "sub"))
            j = self.judgments(root, "j.tsv", all8[:6], span(all8[:7]))
            b = Path(root) / "b"
            b.mkdir()
            r = script("build-reader-packet.py", "--workspace", ws, "--out", b / "packet")   # does not ask it
            self.assertEqual(r.returncode, 0, r.stderr)
            bpacket = json.loads((b / "packet" / "packet.json").read_text(encoding="utf-8"))
            bd = panel(b, bpacket, bad={"R1_small_1": "remember", "R2_small_2": "remember"})
            cj = self.judgments(b, "cj.tsv", all8[:3], span(all8[:2]))
            args = ["--packet", out / "packet.json", "--outputs", d, "--judgments", j, "--compare-packet",
                    b / "packet" / "packet.json", "--compare-outputs", bd, "--compare-judgments", cj, "--json"]
            got = json.loads(script("tally-readers.py", *args).stdout)
            self.assertEqual(got["compare"]["span"]["kind"], "mismatch")
            self.assertIsNone(got["compare"]["span"]["p"], "counts of two different things get no p")
            self.assertEqual(got["compare"]["M1"]["kind"], "recall")
            text = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("不可比", text)
            self.assertIn("配对设计", text)
            # The panels' make-up: every reader qualified here, two of eight small-model readers rejected there.
            self.assertEqual(got["models"], {"large": {"qualified": 4, "rejected": 0}, "small": {"qualified": 4, "rejected": 0}})
            self.assertEqual(got["compare_models"]["small"], {"qualified": 2, "rejected": 2})
            self.assertIn("按模型的合格读者（合格/交回）：large 4/4、small 4/4", text)
            self.assertIn("两组合格读者的模型构成不同", text)
            # The same question in both versions is compared, and said to be.
            q = Path(root) / "q.tsv"
            r = script("build-reader-packet.py", "--workspace", ws, "--out", b / "packet2", "--questions", q)
            self.assertEqual(r.returncode, 0, r.stderr)
            b2 = json.loads((b / "packet2" / "packet.json").read_text(encoding="utf-8"))
            c = Path(root) / "c"
            c.mkdir()
            cd = panel(c, b2)
            args[args.index("--compare-packet") + 1] = b / "packet2" / "packet.json"
            args[args.index("--compare-outputs") + 1] = cd
            got = json.loads(script("tally-readers.py", *args).stdout)
            self.assertEqual(got["compare"]["span"]["kind"], "directed")
            self.assertIsNotNone(got["compare"]["span"]["p"])
            text = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("两版同一道定向题", text)
            self.assertNotIn("两组合格读者的模型构成不同", text)

    def test_counts_are_given_per_model_and_what_the_blank_reader_carries_is_marked(self):
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            blank = json.loads((out / "blank_reader.json").read_text(encoding="utf-8"))
            self.assertEqual(blank["packet"], packet["packet_id"])
            self.assertEqual(blank["remember"][0], "We audit a bridge survey.", "the blank reader copies the first paragraph")
            d = panel(root, packet)
            small = [f"{pr}_small_{n}" for pr in ("R1", "R2") for n in (1, 2)]
            j = self.judgments(root, "j.tsv", small, extra="BLANK\tM1\tmain\t✓\nBLANK\tM1\tsub\t✓\n")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d,
                                    "--judgments", j, "--json").stdout)
            self.assertEqual(got["carried"]["M1"], {"carried": 4, "judged": 8}, "the blank reader is not a reader")
            self.assertEqual(got["by_model"]["small"]["M1"], {"carried": 4, "judged": 4})
            self.assertEqual(got["by_model"]["large"]["M1"], {"carried": 0, "judged": 4})
            self.assertEqual(got["blank"], {"M1": True})
            self.assertIn("空白读者也带走了", (out / "report.md").read_text(encoding="utf-8"))

    def test_the_packet_measures_how_much_the_introduction_repeats_the_abstract(self):
        with TempDir() as root:
            repo, ws = setup(root)
            commit(repo, {"sections/01_intro.tex": INTRO.replace("Bridges fail slowly",
                                                                  "We audit a bridge survey. Bridges fail slowly")},
                   "v2", 1_700_000_100)
            reindex(ws)
            out, packet = self.build(root, ws)
            rep = packet["repetition"]
            self.assertGreaterEqual(rep["longest_verbatim_words"], 5, rep)
            self.assertIn("we audit a bridge survey", rep["longest_verbatim"])
            self.assertIn("引言第一段与摘要的重复", "".join(
                [script("tally-readers.py", "--packet", out / "packet.json", "--outputs", panel(root, packet)).stdout,
                 (out / "report.md").read_text(encoding="utf-8")]))

    def test_a_point_credited_to_the_wrong_thing_is_counted_apart_and_not_carried(self):
        # Readers who told one model's result as another's were graded ✓: the judge was asked only whether the point
        # was mentioned (spec 2026-09-25 §4.3).
        all8 = [f"{pr}_{m}_{n}" for pr in ("R1", "R2") for m in ("small", "large") for n in (1, 2)]
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            j = self.judgments(root, "j.tsv", all8[:4])
            j.write_text(j.read_text(encoding="utf-8").replace(f"{all8[4]}\tM1\tmain\t✗", f"{all8[4]}\tM1\tmain\t≠")
                         .replace(f"{all8[4]}\tM1\tsub\t✗", f"{all8[4]}\tM1\tsub\t≠"), encoding="utf-8")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d,
                                    "--judgments", j, "--json").stdout)
            self.assertEqual(got["carried"]["M1"], {"carried": 4, "judged": 8})
            self.assertEqual(got["misattributed"], {"M1": 1})
            self.assertIn("归属错", (out / "report.md").read_text(encoding="utf-8"))

    def test_judges_who_miss_the_injected_set_make_the_panel_a_failure(self):
        all8 = [f"{pr}_{m}_{n}" for pr in ("R1", "R2") for m in ("small", "large") for n in (1, 2)]
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            card = Path(root) / "card.md"
            card.write_text("M1 bridges fail slowly\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            C.save(ws, cfg)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            truth = Path(root) / "injected.tsv"
            truth.write_text("Z1\tM1\t✓\nZ2\tM1\t≠\nZ3\tM1\t✗\nZ4\tM1\t✗\n", encoding="utf-8")
            good = "".join(f"{z}\tM1\t{jd}\t{v}\n" for z, v in (("Z1", "✓"), ("Z2", "≠"), ("Z3", "✗"), ("Z4", "✗"))
                           for jd in ("main", "sub"))
            bad = good.replace("Z2\tM1\tsub\t≠", "Z2\tM1\tsub\t✓").replace("Z3\tM1\tsub\t✗", "Z3\tM1\tsub\t✓") \
                      .replace("Z4\tM1\tsub\t✗", "Z4\tM1\tsub\t✓")
            args = ["--packet", out / "packet.json", "--outputs", d, "--injected", truth, "--json"]
            ok = json.loads(script("tally-readers.py", *args, "--judgments",
                                   self.judgments(root, "ok.tsv", all8[:4], extra=good)).stdout)
            self.assertEqual(ok["injected"], [0, 8])
            self.assertEqual(ok["panel_problems"], [])
            self.assertEqual(ok["carried"]["M1"], {"carried": 4, "judged": 8}, "injected answers are not readers")
            no = json.loads(script("tally-readers.py", *args, "--judgments",
                                   self.judgments(root, "no.tsv", all8[:4], extra=bad)).stdout)
            self.assertEqual(no["injected"], [3, 8])
            self.assertTrue(any("注入集" in x for x in no["panel_problems"]), no["panel_problems"])
            row = next(x for x in V.compute(C.load(ws), ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.FAILED, "a panel whose judges failed the injected set is not a reading")

    def test_a_directed_question_the_first_paragraph_answers_is_flagged_and_keys_do_not_reach_readers(self):
        # All four prompted points were answerable by copying the abstract, and they sat at ceiling (spec 2026-09-25
        # §4.3). A key phrase the first paragraph prints verbatim flags its question; keys are for judges only.
        with TempDir() as root:
            repo, ws = setup(root)
            q = Path(root) / "q.tsv"
            q.write_text("gauge\tWhat do the gauges read?\tgauges read 12\ncause\tWhy do bridges fail?\tcorrosion ‖ load\n",
                         encoding="utf-8")
            r = script("build-reader-packet.py", "--workspace", ws, "--out", Path(root) / "p", "--questions", q)
            self.assertEqual(r.returncode, 0, r.stderr)
            packet = json.loads((Path(root) / "p" / "packet.json").read_text(encoding="utf-8"))
            self.assertEqual(packet["copyable_questions"], ["gauge"])
            self.assertIn("gauge", r.stdout)
            prompt = (Path(root) / "p" / "prompt_R1.txt").read_text(encoding="utf-8")
            self.assertNotIn("corrosion", prompt, "an answer key never reaches a reader")
            q.write_text("gauge\tWhat do the gauges read?\ncause\tWhy do bridges fail?\n", encoding="utf-8")
            script("build-reader-packet.py", "--workspace", ws, "--out", Path(root) / "p2", "--questions", q)
            again = json.loads((Path(root) / "p2" / "packet.json").read_text(encoding="utf-8"))
            self.assertEqual(again["packet_id"], packet["packet_id"], "keys do not change what the readers read")

    def test_a_derived_metric_coded_only_by_the_reviser_is_not_a_count(self):
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            derived = Path(root) / "derived.tsv"
            derived.write_text("".join(f"misread\tR1_small_{n}\tmain\t1\n" for n in (1, 2)), encoding="utf-8")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d,
                                    "--derived", derived, "--json").stdout)
            self.assertEqual(got["derived"]["misread"], {"coded_by": ["main"], "blind": False, "count": None})
            self.assertIn("未盲编", (out / "report.md").read_text(encoding="utf-8"))
            derived.write_text(derived.read_text(encoding="utf-8") + "misread\tR1_small_1\tblind\t1\nmisread\tR1_small_2\tblind\t0\n",
                               encoding="utf-8")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d,
                                    "--derived", derived, "--json").stdout)
            self.assertEqual(got["derived"]["misread"], {"coded_by": ["blind", "main"], "blind": True, "count": 1})

    def test_what_got_in_the_way_is_listed_sorted_and_named_from_three_readers(self):
        # writing_got_in_way was asked and never tallied: eight readers of one round said the prose was dense and none
        # of it reached a count. It is listed verbatim, sorted by a closed keyword list (descriptive, not a coding),
        # and a kind or a paragraph three readers share is marked. "Reading flow" is not a complaint about links.
        with TempDir() as root:
            repo, ws = setup(root)
            out, packet = self.build(root, ws)
            d = panel(root, packet)
            said = {"R1_small_1": "Very dense; several qualifications stacked in one sentence.",
                    "R1_large_1": "Dense, with caveats packed into long clauses.",
                    "R2_small_1": "The paragraphs are dense.",
                    "R2_large_1": "Section placeholders (§x) broke the reading flow.",
                    "R2_large_2": "None."}
            for who in ("R1_small_1", "R1_small_2", "R1_large_1", "R2_small_1", "R2_small_2", "R2_large_1", "R2_large_2"):
                f = d / f"{who}.json"
                o = json.loads(f.read_text(encoding="utf-8"))
                o["writing_got_in_way"] = said.get(who, "nothing")
                if who in ("R1_small_1", "R1_large_1", "R2_small_2"):
                    o["paragraphs"][0]["reread"] = ["The survey covers"]
                f.write_text(json.dumps(o), encoding="utf-8")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d, "--json").stdout)
            t = got["tally"]
            self.assertEqual(sorted(r for r, _ in t["writing"]), ["R1_large_1", "R1_small_1", "R2_large_1", "R2_small_1"])
            self.assertEqual(t["writing_kinds"]["density"], {"readers": ["R1_large_1", "R1_small_1", "R2_small_1"],
                                                             "flag": True})
            self.assertEqual(t["writing_kinds"]["placeholders"]["flag"], False)
            self.assertNotIn("links", t["writing_kinds"], "reading flow is not a complaint about links")
            self.assertTrue(t["paragraphs"][0]["flag"])
            self.assertIsNone(t["relations"], "the packet did not ask")
            text = (out / "report.md").read_text(encoding="utf-8")
            self.assertIn("写法挡路（原话）：4 / 8 位读者说有", text)
            self.assertIn("density 3 位 ⚑", text)
            self.assertIn("3 位以上重读：P1", text)
            self.assertIn("--derived", text)

    def test_the_relations_question_is_asked_and_its_quotes_placed_in_paragraphs(self):
        # Readers asked only what got in their way rarely name a missing link between two sentences. --ask-relations
        # asks for the two sentences, quoted; the tally places each quote in the paragraph that holds it.
        with TempDir() as root:
            repo, ws = setup(root)
            out = Path(root) / "packet"
            r = script("build-reader-packet.py", "--workspace", ws, "--out", out, "--ask-relations")
            self.assertEqual(r.returncode, 0, r.stderr)
            packet = json.loads((out / "packet.json").read_text(encoding="utf-8"))
            self.assertIn("relation_guessed", [q["id"] for q in packet["questions"]])
            self.assertIn('"relation_guessed"', (out / "prompt_R1.txt").read_text(encoding="utf-8"))
            d = panel(root, packet)
            words = packet["paragraphs"][-1]["text"].split()
            quote = '"' + " ".join(words[:5]) + '" then "' + " ".join(words[5:10]) + '"'
            answers = {"R1_small_1": quote, "R1_large_2": quote, "R2_small_1": quote.upper(),
                       "R2_large_1": '"a sentence this survey never printed"', "R2_large_2": "none"}
            for f in d.glob("*.json"):
                o = json.loads(f.read_text(encoding="utf-8"))
                o["relation_guessed"] = answers.get(f.stem, "none")
                f.write_text(json.dumps(o), encoding="utf-8")
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d, "--json").stdout)
            rel = got["tally"]["relations"]
            last = str(packet["paragraphs"][-1]["p"])
            self.assertEqual(sorted(rel["named"]), ["R1_large_2", "R1_small_1", "R2_large_1", "R2_small_1"])
            self.assertEqual(rel["unplaced"], ["R2_large_1"])
            self.assertEqual(rel["paragraphs"][last], {"readers": ["R1_large_2", "R1_small_1", "R2_small_1"], "flag": True})
            self.assertIn(f"P{last}：3 位 ⚑", (out / "report.md").read_text(encoding="utf-8"))

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

    # 09-28, four ways a packet read something other than the text: a plain-text file cut at its first percentage, math
    # symbols reaching the readers as words, a packet of the version before the one just committed, and a packet of
    # two sections recorded as the panel of the whole text.

    def test_plain_text_keeps_a_percent_and_latex_drops_a_comment_but_says_so(self):
        with TempDir() as root:
            body = "Gauges read 37.25% of the time, and the rest never.\n\nThe second paragraph.\n"
            (Path(root) / "t.txt").write_text(body, encoding="utf-8")
            (Path(root) / "t.tex").write_text(body, encoding="utf-8")
            r = script("build-reader-packet.py", "--text", Path(root) / "t.txt", "--out", Path(root) / "plain")
            self.assertEqual(r.returncode, 0, r.stderr)
            text = (Path(root) / "plain" / "manuscript.txt").read_text(encoding="utf-8")
            self.assertIn("[P1] Gauges read 37.25% of the time, and the rest never.", text)
            self.assertEqual(json.loads((Path(root) / "plain" / "packet.json").read_text())["source"]["format"], "text")
            for args in (["--text", Path(root) / "t.tex"], ["--text", Path(root) / "t.txt", "--format", "latex"]):
                out = Path(root) / f"latex{len(args)}"
                r = script("build-reader-packet.py", *args, "--out", out)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("[P1] Gauges read 37.25\n", (out / "manuscript.txt").read_text(encoding="utf-8"),
                              "as LaTeX the rest of the line is a comment, as the typeset page would drop it")
                self.assertIn("a % after a number drops the rest of the line (lines 1)", r.stdout)

    def test_math_shows_its_symbols_and_a_command_without_one_keeps_its_backslash(self):
        with TempDir() as root:
            repo, ws = setup(root)
            intro = INTRO + (r"""
The load holds when $L \le C$ and $a \cdot b \geq 41.75$, with $\alpha = \frac{1}{2}$; each gauge reads $\widget{g}$.
""")
            commit(repo, {"sections/01_intro.tex": intro}, "v2", 1_700_000_100)
            reindex(ws)
            out, packet = self.build(root, ws)
            text = (out / "manuscript.txt").read_text(encoding="utf-8")
            self.assertIn("The load holds when L ≤ C and a · b ≥ 41.75, with α = 1/2; each gauge reads \\widget{g}.", text)
            for word in (" le ", "cdot", "geq", "alpha", "frac"):
                self.assertNotIn(word, text)
            self.assertEqual(packet["residual_commands"], {"\\widget": 1})

    def test_a_packet_is_refused_while_the_index_is_behind_the_branch(self):
        with TempDir() as root:
            repo, ws = setup(root)
            old = git(repo, "rev-parse", "HEAD")
            commit(repo, {"sections/01_intro.tex": INTRO.replace("Nobody watches them.", "Few watch them.")}, "c",
                   1_700_000_100)
            r = script("build-reader-packet.py", "--workspace", ws, "--out", Path(root) / "packet")
            self.assertEqual(r.returncode, 2)
            self.assertIn(f"the index was built at {old[:7]} but main is at {git(repo, 'rev-parse', 'HEAD')[:7]}",
                          r.stderr)
            self.assertFalse((Path(root) / "packet" / "packet.json").exists())
            reindex(ws)
            _, packet = self.build(root, ws)
            self.assertIn("Few watch them.", " ".join(p["text"] for p in packet["paragraphs"]))

    def test_other_sections_are_a_comparison_not_the_checks_run(self):
        with TempDir() as root:
            repo, ws = setup(root)
            cfg = C.load(ws)
            card = Path(root) / "card.md"
            card.write_text("M1 bridges fail slowly\n", encoding="utf-8")
            cfg["target"] = {"intent_card": str(card)}
            C.save(ws, cfg)
            out = Path(root) / "only-intro"
            r = script("build-reader-packet.py", "--workspace", ws, "--out", out, "--sections", "I")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("--sections I is not the workspace's readers scope (A,I): this packet reads", r.stdout)
            packet = json.loads((out / "packet.json").read_text(encoding="utf-8"))
            self.assertIsNone(packet["snapshot"])
            over = packet["source"]["scope_override"]
            self.assertEqual(over["configured"], ["A", "I"])
            self.assertLess(over["read_sentences"], over["configured_sentences"])
            got = json.loads(script("tally-readers.py", "--packet", out / "packet.json", "--outputs",
                                    panel(root, packet), "--judgments",
                                    self.judgments(root, "j.tsv", ["R1_small_1"]), "--json").stdout)
            self.assertFalse(got["recorded"])
            row = next(x for x in V.compute(C.load(ws), ws)["rows"] if x["id"] == "readers")
            self.assertEqual(row["status"], V.NEVER, "a comparison of two sections is not a panel of the configured scope")
            # The configured scope, named in either order, is the check's own panel.
            r = script("build-reader-packet.py", "--workspace", ws, "--out", Path(root) / "both", "--sections", "I,A")
            self.assertNotIn("not the workspace's readers scope", r.stdout)
            self.assertTrue(json.loads((Path(root) / "both" / "packet.json").read_text())["snapshot"])


ABSTRACT = ("River gauges drift before floods. We ask whether drift warns early. On ten rivers, drift rose before nine "
            "floods. A cheap fix recalibrates every gauge weekly. It hides the drift that gives the warning, e.g. Tay "
            "and Dee. Gauges should log drift, not erase it.\n")
TURN = '"On ten rivers, drift rose" and "A cheap fix recalibrates"'


class RelationTurnsTest(unittest.TestCase):
    """Where readers had to guess how one sentence follows another, placed at the turn between the two sentences they
    quoted, not only in a paragraph: an abstract is one paragraph, and "P1: 12 readers" did not say where (10-07, K12).
    Synthetic text only."""

    def run_panel(self, root, answers):
        root = Path(root)
        (root / "abstract.txt").write_text(ABSTRACT, encoding="utf-8")
        out = root / "packet"
        r = script("build-reader-packet.py", "--text", root / "abstract.txt", "--out", out, "--ask-relations")
        self.assertEqual(r.returncode, 0, r.stderr)
        packet = json.loads((out / "packet.json").read_text(encoding="utf-8"))
        d = panel(root, packet)
        for f in d.glob("*.json"):
            o = json.loads(f.read_text(encoding="utf-8"))
            o["relation_guessed"] = answers.get(f.stem, "none")
            f.write_text(json.dumps(o), encoding="utf-8")
        r = script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d, "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout), (out / "report.md").read_text(encoding="utf-8"), out, d

    def test_most_readers_guessing_at_one_turn_is_placed_there_and_said_to_be_about_order(self):
        answers = {"R1_small_1": TURN, "R1_small_2": TURN, "R1_large_1": TURN.upper(),
                   "R2_small_1": ["On ten rivers, drift rose", "A cheap fix recalibrates"],   # a list, unquoted
                   "R2_large_1": '"A cheap fix recalibrates" then "It hides the drift"'}
        with TempDir() as root:
            got, text, _, _ = self.run_panel(root, answers)
            self.assertEqual(got["rejected"], [], "a list of the two openings is an answer")
            turns = got["tally"]["relations"]["turns"]
            self.assertEqual([(t["from"], t["to"], len(t["readers"]), t["flag"], t["most"]) for t in turns],
                             [([1, 3], [1, 4], 4, True, True), ([1, 4], [1, 5], 1, False, False)])
            self.assertIn("P1 第 3 句 → 第 4 句：4 位 ⚑", text)
            self.assertIn("「On ten rivers, drift rose before…」→「A cheap fix recalibrates every gauge…」", text)
            self.assertIn("过半读者（4 / 5）卡在 P1 第 3 句 → 第 4 句：这里可能要重排", text)

    def test_readers_spread_over_several_turns_are_not_called_an_order_problem(self):
        other = '"River gauges drift before" and "We ask whether drift"'
        answers = {"R1_small_1": TURN, "R1_small_2": TURN, "R1_large_1": TURN,
                   "R2_small_1": other, "R2_small_2": other, "R2_large_1": other}
        with TempDir() as root:
            got, text, _, _ = self.run_panel(root, answers)
            turns = got["tally"]["relations"]["turns"]
            self.assertEqual(sorted((t["from"][1], t["to"][1], t["flag"], t["most"]) for t in turns),
                             [(1, 2, True, False), (3, 4, True, False)])
            self.assertNotIn("可能要重排", text)

    def test_an_abbreviation_ends_no_sentence(self):
        answers = {"R1_small_1": '"It hides the drift" and "Gauges should log drift"'}
        with TempDir() as root:
            got, _, _, _ = self.run_panel(root, answers)
            self.assertEqual([(t["from"], t["to"]) for t in got["tally"]["relations"]["turns"]], [([1, 5], [1, 6])])

    def test_a_panel_the_loop_cannot_record_says_so(self):
        # 10-07: a packet built from a file, not a loop workspace, was tallied and the last line was only the report's
        # path, which reads like the loop has it.
        with TempDir() as root:
            got, _, out, d = self.run_panel(root, {})
            self.assertFalse(got["recorded"])
            self.assertIn("--workspace", got["not_recorded"])
            r = script("tally-readers.py", "--packet", out / "packet.json", "--outputs", d)
            self.assertIn("没记进循环", r.stdout.strip().splitlines()[-1])


if __name__ == "__main__":
    unittest.main()
