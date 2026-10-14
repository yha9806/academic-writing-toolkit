"""Method ledger (spec 2026-09-29-method-ledger): sentences about what was done, bound to where it was done. Each
error kind fails on a synthetic draft and ledger and passes on the clean twin. Synthetic wording throughout."""
import csv
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import catalogue as K
from loop import config as C
from loop import coverage as V
from loop import history as H

from fixtures import TempDir, git, make_repo, workspace

# redcheck mutates a copy of the skill and names its directory here
SCRIPT = Path(os.environ["AWT_AUDIT_DIR"]) / "audit-method-ledger.py" if os.environ.get("AWT_AUDIT_DIR") \
    else K.script_path("audit/audit-method-ledger.py")

DATA = r"""\section{Data}\label{sec:data}
\paragraph{Gauges.}\label{par:gauges} We read two gauges at noon. Each gauge logs its load every hour.
The north bridge carries more load than the south bridge.
"""
MAIN = r"""\documentclass{article}
\begin{document}
\input{sections/data}
\end{document}
"""
RUN = "".join(f"line {i}\n" for i in range(1, 11))
STATS = {"bridges": [{"name": "north", "load": 12}, {"name": "south", "load": 9}], "meta": {"gauges": 2}}
FIELDS = ["id", "loc", "sentence", "claim_type", "pointer", "evidence", "verdict", "note", "checked"]
ROWS = [
    {"id": "L-000", "loc": "sections/data.tex:1", "sentence": r"\section{Data}\label{sec:data}", "claim_type": "none",
     "pointer": "", "verdict": "none"},
    {"id": "L-001", "loc": "sections/data.tex:2", "sentence": r"\paragraph{Gauges.}\label{par:gauges} We read two gauges at noon.",
     "claim_type": "procedure", "pointer": "e0:run.py:3-4; out/stats.json#meta.gauges", "verdict": "match"},
    {"id": "L-002", "loc": "sections/data.tex:2", "sentence": "Each gauge logs its load every hour.",
     "claim_type": "procedure", "pointer": 'notes.md@"read at noon"', "verdict": "match"},
    {"id": "L-003", "loc": "sections/data.tex:3", "sentence": "The north bridge carries more load than the south bridge.",
     "claim_type": "result", "pointer": r"out/stats.json#bridges[name=north].load,bridges[name=south].load; \label{sec:data}",
     "verdict": "match", "note": "loads from the stats file"},
]


def ledger_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, "") for k in FIELDS})
    return buf.getvalue()


def e0_repo(root):
    d = Path(root) / "e0"
    (d / "out").mkdir(parents=True)
    (d / "run.py").write_text(RUN, encoding="utf-8")
    (d / "out" / "stats.json").write_text(json.dumps(STATS), encoding="utf-8")
    (d / "notes.md").write_text("The gauges were read at noon.\n", encoding="utf-8")
    git(d, "init", "-q", "-b", "main")
    git(d, "add", ".")
    git(d, "commit", "-q", "-m", "e0")
    return d, git(d, "rev-parse", "HEAD")


def manuscript(root, rows=ROWS, data=DATA):
    return make_repo(root, [({"main.tex": MAIN, "sections/data.tex": data, "method-ledger.tsv": ledger_text(rows)},
                             "v1", 1_700_000_000)])


def run(ms, e0, commit, *extra, ledger="method-ledger.tsv"):
    argv = [sys.executable, str(SCRIPT), "--base-dir", str(ms), "--ledger", ledger, "--repo", f"e0={e0}@{commit}",
            "--full", "sections/data.tex", "--git", str(ms), "--json"] + list(extra)
    r = subprocess.run(argv, capture_output=True, text=True)
    out = json.loads(r.stdout) if r.stdout.lstrip().startswith("{") else None
    return r.returncode, out, r.stderr


def kinds(out):
    return sorted({e["kind"] for e in out["errors"]})


def edit(rows, rid, **kw):
    return [dict(r, **kw) if r["id"] == rid else r for r in rows]


class MethodLedgerTest(unittest.TestCase):
    def check(self, rows=ROWS, data=DATA, *extra):
        with TempDir() as root:
            e0, commit = e0_repo(root)
            ms = manuscript(root, rows, data)
            return run(ms, e0, commit, *extra)

    def test_the_clean_ledger_passes_and_line_numbers_into_pinned_code_are_allowed(self):
        code, out, err = self.check()
        self.assertEqual(code, 0, (out, err))
        self.assertEqual(out["errors"], [])
        self.assertEqual(out["keys_checked"], 2, "both key pointers were read, not skipped")
        self.assertIn("报错 0", out["summary_zh"])

    def test_each_error_kind_is_reported(self):
        cases = {
            "sentence-changed": (ROWS, DATA.replace("two gauges", "three gauges")),
            "pointer-by-line": (edit(ROWS, "L-002", pointer="sections/data.tex:2"), DATA),
            "no-pointer": (edit(ROWS, "L-002", pointer="see the run log"), DATA),
            "open-verdict": (edit(ROWS, "L-002", verdict="mismatch"), DATA),
            "bad-verdict": (edit(ROWS, "L-002", verdict="okay"), DATA),
            "note-contradicts-verdict": (edit(ROWS, "L-003", note="post-hoc, not marked as exploratory"), DATA),
            "unledgered": (ROWS, DATA + "A third bridge was not measured at all.\n"),
            "duplicate-id": (ROWS + [dict(ROWS[2])], DATA),
        }
        for kind, (rows, data) in cases.items():
            with self.subTest(kind=kind):
                code, out, err = self.check(rows, data)
                self.assertEqual(code, 1, (kind, out, err))
                self.assertIn(kind, kinds(out))

    def test_a_partial_verdict_needs_checked_and_counts_as_pending(self):
        code, out, _ = self.check(edit(ROWS, "L-002", verdict="partial"))
        self.assertEqual((code, kinds(out), out["pending"]), (1, ["open-verdict"], 1))
        code, out, _ = self.check(edit(ROWS, "L-002", verdict="partial", checked="2026-01-02 wording kept"))
        self.assertEqual((code, out["pending"]), (0, 1), "pending neither passes nor fails")

    def test_every_pointer_form_is_read(self):
        # G2: a key is resolved in the JSON, not only the file found.
        bad = {
            "file": "out/nothere.json",
            "lines past the end": "e0:run.py:99",
            "key": "out/stats.json#meta.cameras",
            "selector": "out/stats.json#bridges[name=west].load",
            "sibling after a comma": "out/stats.json#bridges[name=north].load,width",
            "fragment": 'notes.md@"read at dusk"',
            "label": r"\label{sec:none}",
            "commit": "commit:deadbeefdeadbeef",
        }
        for what, pointer in bad.items():
            with self.subTest(what=what):
                code, out, err = self.check(edit(ROWS, "L-002", pointer=pointer))
                self.assertEqual((code, kinds(out)), (1, ["pointer-missing"]), (what, out, err))

    def test_a_run_in_heading_is_not_part_of_the_sentence(self):
        # G5: a sentence inserted after the heading left both rows looking changed.
        data = DATA.replace(r"\label{par:gauges} We read", r"\label{par:gauges} Gauges are cheap to fit. We read")
        code, out, _ = self.check(ROWS, data)
        self.assertEqual(kinds(out), ["unledgered"], "the new sentence needs a row; the old ones still stand")
        heading_words = edit(ROWS, "L-002", sentence="Gauges.")
        code, out, _ = self.check(heading_words)
        self.assertNotIn("sentence-changed", kinds(out), "a row can hold a heading's own words")

    def test_a_retired_row_needs_its_commit_and_its_sentence_gone(self):
        with TempDir() as root:
            e0, commit = e0_repo(root)
            ms = manuscript(root)
            head = git(ms, "rev-parse", "HEAD")
            (ms / "method-ledger.tsv").write_text(ledger_text(edit(ROWS, "L-002", verdict=f"retired {head}")), encoding="utf-8")
            code, out, _ = run(ms, e0, commit)
            self.assertEqual(kinds(out), ["retired-but-present"])
            (ms / "sections" / "data.tex").write_text(DATA.replace(" Each gauge logs its load every hour.", ""), encoding="utf-8")
            code, out, _ = run(ms, e0, commit)
            self.assertEqual((code, out["errors"]), (0, []), "retired and gone: kept as history, not an error")
            (ms / "method-ledger.tsv").write_text(ledger_text(edit(ROWS, "L-002", verdict="retired 0000000")), encoding="utf-8")
            code, out, _ = run(ms, e0, commit)
            self.assertEqual(kinds(out), ["bad-verdict"])

    def test_a_retired_row_vouches_for_no_new_sentence(self):
        # A retired row's sentence was deleted. Its words used to stay in the "ledgered" list, so a new sentence that
        # happened to be part of it was never reported as unledgered.
        with TempDir() as root:
            e0, commit = e0_repo(root)
            ms = manuscript(root)
            head = git(ms, "rev-parse", "HEAD")
            gone = {"id": "L-004", "loc": "sections/data.tex:4", "claim_type": "procedure", "pointer": "",
                    "sentence": "Since the spring survey, North Gate keeps a copy of every reading.",
                    "verdict": f"retired {head}"}
            (ms / "method-ledger.tsv").write_text(ledger_text(ROWS + [gone]), encoding="utf-8")
            code, out, err = run(ms, e0, commit)
            self.assertEqual((code, out["errors"]), (0, []), ("retired and gone is history, not an error", out, err))
            (ms / "sections" / "data.tex").write_text(DATA + "North Gate keeps a copy of every reading.\n", encoding="utf-8")
            code, out, err = run(ms, e0, commit)
            self.assertEqual(code, 1, (out, err))
            self.assertEqual(kinds(out), ["unledgered"])
            self.assertIn("North Gate keeps a copy", out["errors"][0]["detail"])

    def test_a_row_that_vanishes_is_reported_until_it_is_retired(self):
        # G3: a rebuild dropped rows and the check saw nothing, since a row that is gone does not exist for it.
        with TempDir() as root:
            e0, commit = e0_repo(root)
            ms = manuscript(root)
            state = Path(root) / "ids.json"
            self.assertEqual(run(ms, e0, commit, "--state", str(state))[0], 0)
            (ms / "method-ledger.tsv").write_text(ledger_text([r for r in ROWS if r["id"] != "L-002"]), encoding="utf-8")
            for _ in range(2):
                code, out, _ = run(ms, e0, commit, "--state", str(state))
                self.assertIn("row-dropped", kinds(out), "said on every run, not once")
            head = git(ms, "rev-parse", "HEAD")
            (ms / "method-ledger.tsv").write_text(ledger_text(edit(ROWS, "L-002", verdict=f"retired {head}")), encoding="utf-8")
            (ms / "sections" / "data.tex").write_text(DATA.replace(" Each gauge logs its load every hour.", ""), encoding="utf-8")
            code, out, _ = run(ms, e0, commit, "--state", str(state))
            self.assertEqual((code, out["errors"]), (0, []))

    def test_a_file_outside_the_pin_is_said_not_passed_silently(self):
        with TempDir() as root:
            e0, commit = e0_repo(root)
            (e0 / "late.json").write_text("{}", encoding="utf-8")
            ms = manuscript(root, edit(ROWS, "L-002", pointer="late.json"))
            code, out, _ = run(ms, e0, commit)
            self.assertEqual(code, 0)
            self.assertEqual(out["outside_pin"], ["late.json"])
            self.assertIn("不在锁定的提交里", out["summary_zh"])

    def test_nothing_examined_is_exit_2(self):
        with TempDir() as root:
            e0, commit = e0_repo(root)
            ms = manuscript(root)
            (ms / "empty.tsv").write_text("", encoding="utf-8")
            (ms / "nopointer.tsv").write_text(ledger_text([edit(ROWS, "L-000")[0]]), encoding="utf-8")
            for ledger in ("missing.tsv", "empty.tsv", "nopointer.tsv"):
                with self.subTest(ledger=ledger):
                    self.assertEqual(run(ms, e0, commit, ledger=ledger)[0], 2)
            self.assertEqual(run(ms, e0, "0" * 40)[0], 2, "a pinned commit that is not there")

    def test_the_migration_prints_a_diff_and_writes_nothing(self):
        with TempDir() as root:
            e0, commit = e0_repo(root)
            ms = manuscript(root)
            before = (ms / "method-ledger.tsv").read_bytes()
            r = subprocess.run([sys.executable, str(SCRIPT), "--base-dir", str(ms), "--ledger", "method-ledger.tsv",
                                "--migrate-headings"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("+L-001\tsections/data.tex:2\tWe read two gauges at noon.", r.stdout)
            self.assertEqual((ms / "method-ledger.tsv").read_bytes(), before)


class MethodLedgerInTheLoop(unittest.TestCase):
    def setup(self, root, rows=ROWS):
        e0, commit = e0_repo(root)
        ms = manuscript(root, rows)
        ws = workspace(root, ms, "main", glob=["main.tex", "sections/data.tex"])
        cfg = C.load(ws)
        cfg["draft"]["format"] = "latex"
        cfg["draft"]["sections"] = [{"match": r"^Data$", "prefix": "D", "kind": "prose"}]
        cfg.setdefault("inputs", {})["method_ledger"] = {
            "path": "method-ledger.tsv", "repos": {"e0": {"path": str(e0), "commit": commit}},
            "full": ["sections/data.tex"]}
        C.save(ws, cfg)
        cfg = C.load(ws)
        vs = H.load_versions(cfg)
        H.assign_ids(vs)
        head = git(ms, "rev-parse", "HEAD")
        (Path(ws) / "index" / "sentences.json").write_text(json.dumps({"head": head, "versions": vs}), encoding="utf-8")
        return ms, ws, C.load(ws)

    def test_the_check_runs_from_the_config_and_says_what_it_found(self):
        with TempDir() as root:
            ms, ws, cfg = self.setup(root)
            chk = K.by_id("method-ledger")
            head = git(ms, "rev-parse", "HEAD")
            sents = V.current_sentences(ws)[0]
            rec = V.run(chk, cfg, ws, head, sents)
            self.assertEqual(rec["verdict"], "ok", rec)
            self.assertIn("报错 0", rec["summary"])
            self.assertTrue((Path(ws) / "cache" / "coverage" / "method-ledger-ids.json").is_file())
            (ms / "method-ledger.tsv").write_text(ledger_text(edit(ROWS, "L-002", verdict="mismatch")), encoding="utf-8")
            git(ms, "commit", "-qam", "open a verdict")
            head = git(ms, "rev-parse", "HEAD")
            rec = V.run(chk, cfg, ws, head, sents)
            self.assertEqual(rec["verdict"], "findings")
            self.assertIn("open-verdict 1", rec["summary"])

    def test_not_turned_on_is_not_a_rerun_or_a_gap(self):
        # 09-29: merged into the resident loop, the check hung 「缺前提」 on a manuscript that never asked for it, as a
        # rerun on the notch and a red check stage.
        from loop import ring as RG
        with TempDir() as root:
            ms, ws, cfg = self.setup(root)
            del cfg["inputs"]["method_ledger"]
            head = git(ms, "rev-parse", "HEAD")
            row = V.row(K.by_id("method-ledger"), cfg, ws, head, V.current_sentences(ws)[0])
            self.assertEqual((row["status"], row.get("optin")), (V.NOT_APPLICABLE, True), row)
            self.assertIn("没开启", row["detail"])
            self.assertNotIn(row["status"], V.ATTENTION)
            self.assertEqual(V.gaps({"rows": [row]}), [], "not turned on is no gap in the toolkit")
            r = RG.ring({"rows": [row]}, last_change_at="2026-01-02T00:00:00+00:00")
            self.assertEqual(next(s for s in r["segments"] if s["key"] == "check")["items"], [])

    def test_only_an_unpinned_repository_is_watched_outside(self):
        cfg = {"inputs": {"method_ledger": {"path": "m.tsv", "repos": {
            "e0": {"path": "/x/e0", "commit": "abc1234"}, "ws": {"path": "/x/ws"}}}}}
        self.assertEqual(K._method_outside(cfg), ["git:/x/ws"])
        self.assertEqual(K.method_ledger_cfg({"inputs": {"method_ledger": "m.tsv"}}), {"path": "m.tsv"})


if __name__ == "__main__":
    unittest.main()
