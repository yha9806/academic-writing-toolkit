import json
import unittest

from loop import checks as K
from loop import config as C
from loop import gitio
from loop import history as H

from fixtures import TempDir, draft_md, make_repo, workspace

T0 = 1_760_000_000
RAW = "Abstract. We find that a substantial gap is observed between gauges and surveyors. Sensors perform worse on abstract bridges than on flat ones."
KEYMAP = 'KEYMAP = {"SpanBench": "Liu2024", "Roe1907": "Roe1907", "Other": "Other2020"}\nNARR = {}\nPLACE = {"X1%"}\n'
LEDGER = [
    {"id": "E1", "key": "Liu2024", "tier": "raw_abstract", "source": "raw/liu.txt", "draft": "Gauges lag surveyors at loading bridges", "span": "a substantial gap is observed"},
    {"id": "E2", "key": "Liu2024", "tier": "raw_abstract", "source": "raw/liu.txt", "draft": "They misjudge abstract bridges", "span": "perform worse on abstract bridges"},
    {"id": "E3", "key": "Roe1907", "tier": "unverified", "source": None, "draft": "Inspection comes first", "span": None},
]
PAR = ("Gauges lag surveyors at loading bridges [SpanBench]. They misjudge abstract bridges [SpanBench] at [X1%]. "
       "Inspection comes first [Roe1907†].")


def setup(root, pars_list, ledger=LEDGER, raw=RAW):
    commits = []
    for k, par in enumerate(pars_list):
        files = {"drafts/DRAFT-v1.md": draft_md("T", "Abs.", [par])}
        if k == 0:
            files.update({"ev/claims.json": json.dumps(ledger), "ev/check.py": KEYMAP, "ev/raw/liu.txt": raw})
        commits.append((files, f"c{k}", T0 + 60 * k))
    repo = make_repo(root, commits)
    cfg = C.load(workspace(root, repo, "main", ledger={"path": "ev/claims.json", "evidence_dir": "ev", "keymap_from": "ev/check.py"}))
    vs = H.load_versions(cfg)
    H.assign_ids(vs)
    return cfg, vs


def by_label(version, result):
    return {s["label"]: result["sentences"][s["sid"]] for s in version["sentences"] if s["section"] == "I"}


class CheckTest(unittest.TestCase):
    def test_saved_spans_are_found_and_facts_listed(self):
        with TempDir() as root:
            cfg, vs = setup(root, [PAR])
            r = by_label(vs[0], K.check_version(cfg, vs[0]))
            self.assertEqual([e["status"] for e in r["I1.1"]["ledger"]], ["found"])
            self.assertEqual(r["I1.2"]["placeholders"], ["X1%"])
            self.assertEqual([e["status"] for e in r["I1.3"]["ledger"]], ["no_source"])
            self.assertEqual([x["dagger"] for x in r.values()], [[], [], []])
            raw_norm = gitio.show(cfg["repo"], vs[0]["sha"], "ev/raw/liu.txt")
            a, b = r["I1.1"]["ledger"][0]["at"]
            self.assertEqual(raw_norm[a:b], "a substantial gap is observed")

    def test_fabricated_span_is_not_found_and_only_its_sentence_changes(self):
        with TempDir() as root:
            cfg, vs = setup(root, [PAR])
            fake = [dict(e) for e in LEDGER]
            fake[1]["span"] = "gauges flawlessly read every load"
            r = by_label(vs[0], K.check_version(cfg, vs[0], ledger=fake))
            self.assertEqual([e["status"] for e in r["I1.2"]["ledger"]], ["not_found"])
            self.assertEqual([e["status"] for e in r["I1.1"]["ledger"]], ["found"])

    def test_only_changed_sentences_are_rechecked(self):
        with TempDir() as root:
            cfg, vs = setup(root, [PAR, PAR.replace("Inspection comes first", "Inspection comes first, as a rule")])
            cache = {}
            first = K.check_version(cfg, vs[0], cache)
            second = K.check_version(cfg, vs[1], cache)
            self.assertEqual((first["evaluated"], second["evaluated"], second["reused"]), (5, 1, 4))

    def test_ledger_change_invalidates_the_cached_sentence(self):
        with TempDir() as root:
            cfg, vs = setup(root, [PAR])
            cache = {}
            K.check_version(cfg, vs[0], cache)
            fake = [dict(e) for e in LEDGER]
            fake[0]["span"] = "a gap nobody saved"
            r = K.check_version(cfg, vs[0], cache, ledger=fake)
            self.assertEqual([e["status"] for e in by_label(vs[0], r)["I1.1"]["ledger"]], ["not_found"])

    def test_dagger_and_missing_entries_are_reported(self):
        with TempDir() as root:
            par = ("Gauges lag surveyors at loading bridges [SpanBench†]. They misjudge abstract bridges [SpanBench]. "
                   "Inspection comes first [Roe1907]. Another claim [Other].")
            cfg, vs = setup(root, [par])
            r = by_label(vs[0], K.check_version(cfg, vs[0]))
            self.assertEqual([d["key"] for d in r["I1.1"]["dagger"]], ["Liu2024"])
            self.assertEqual([d["key"] for d in r["I1.3"]["dagger"]], ["Roe1907"])
            self.assertEqual(r["I1.4"]["keys_without_ledger"], ["Other2020"])

    def test_missing_source_file_and_unattached_entry(self):
        with TempDir() as root:
            led = [dict(e) for e in LEDGER] + [{"id": "E4", "key": "Liu2024", "tier": "raw_abstract", "source": "raw/liu.txt",
                                                "draft": "a sentence that is not in the draft", "span": "gap"}]
            led[0]["source"] = "raw/nope.txt"
            cfg, vs = setup(root, [PAR], ledger=led)
            res = K.check_version(cfg, vs[0])
            r = by_label(vs[0], res)
            self.assertEqual([e["status"] for e in r["I1.1"]["ledger"]], ["file_missing"])
            self.assertEqual([u["id"] for u in res["unattached"]], ["E4"])


if __name__ == "__main__":
    unittest.main()
