import unittest

from loop import align as A
from loop import config as C
from loop import history as H
from loop.text import norm

from fixtures import TempDir, draft_md, make_repo, workspace

P1 = "Counties draw objects in plain words. Their tags state what is shown."
P2 = "Gauges write longer plans than tags do. Those plans mix drawing with loading."
P3 = "We grade each sentence by tier. Each grade surveys the pillar it rests on."


def versions_for(root, texts):
    commits = [({"drafts/DRAFT-v1.md": t}, f"c{k}", 1_700_000_000 + k * 60) for k, t in enumerate(texts)]
    repo = make_repo(root, commits)
    cfg = C.load(workspace(root, repo, "main"))
    vs = H.load_versions(cfg)
    return vs


def by_text(v):
    return {norm(s["text"]): s for s in v["sentences"]}


class StableIdTest(unittest.TestCase):
    def test_moved_paragraph_keeps_ids(self):
        with TempDir() as root:
            v1 = draft_md("T", "Abs one. Abs two.", [P1, P2, P3])
            v2 = draft_md("T", "Abs one. Abs two.", [P3, P1, P2.replace("longer", "much longer")])
            vs = versions_for(root, [v1, v2])
            H.assign_ids(vs)
            old, new = vs[0], vs[1]
            ob = by_text(old)
            for s in new["sentences"]:
                src = ob.get(norm(s["text"])) or ob.get(norm(s["text"].replace("much longer", "longer")))
                self.assertIsNotNone(src, s["text"])
                self.assertEqual(s["sid"], src["sid"], f"{s['label']} took {s['sid']}, its plan was {src['sid']}")
            # positions really did change, so this is not a no-op
            self.assertNotEqual([s["label"] for s in new["sentences"] if s["section"] == "I"][0],
                                next(s["label"] for s in old["sentences"] if norm(s["text"]) == norm(P3.split(". ")[0] + ".")))

    def test_split_and_merge_are_recognised(self):
        with TempDir() as root:
            a = "The grading rule treats a pillar as cracked when the county survey contradicts it; the same rule treats it as unlisted when the plan is blank."
            b1, b2 = "Inspectors work alone.", "They meet only after both tables are in."
            v1 = draft_md("T", "Abs.", [a + " " + b1 + " " + b2])
            a1 = "The grading rule treats a pillar as cracked when the county survey contradicts it."
            a2 = "The same rule treats it as unlisted when the plan is blank."
            merged = "Inspectors work alone, and they meet only after both tables are in."
            v2 = draft_md("T", "Abs.", [a1 + " " + a2 + " " + merged])
            vs = versions_for(root, [v1, v2])
            tr = H.assign_ids(vs)
            al = tr[0]["align"]
            self.assertEqual(len(al["splits"]), 1, al)
            self.assertEqual(len(al["merges"]), 1, al)
            new = {norm(s["text"]): s for s in vs[1]["sentences"]}
            old = {norm(s["text"]): s for s in vs[0]["sentences"]}
            heirs = [new[norm(a1)], new[norm(a2)]]
            self.assertEqual(sum(h["sid"] == old[norm(a)]["sid"] for h in heirs), 1)
            self.assertEqual(sum(h.get("split_from") == old[norm(a)]["sid"] for h in heirs), 1)
            self.assertEqual(sorted(new[norm(merged)]["merged_from"]), sorted([old[norm(b1)]["sid"], old[norm(b2)]["sid"]]))

    def test_reused_text_across_a_gap_is_not_called_new(self):
        with TempDir() as root:
            a = "A pillar is unlisted when the plan gives no drawing of a joint, and cracked when the county survey contradicts the drawing it rests on."
            v1 = draft_md("T", "Abs.", [a + " Inspectors work alone."])
            v2 = draft_md("T", "Abs.", ["A pillar is cracked when the county survey contradicts the drawing it rests on. Inspectors work alone. "
                                        "A pillar is unlisted when the plan gives no drawing of a joint."])
            vs = versions_for(root, [v1, v2])
            H.assign_ids(vs)
            olds = {norm(s["text"]): s["sid"] for s in vs[0]["sentences"]}
            reused = [s for s in vs[1]["sentences"] if s.get("derived_from") == olds[norm(a)]]
            self.assertEqual(len(reused), 1, [(s["label"], s.get("derived_from")) for s in vs[1]["sentences"]])

    def test_scattered_common_words_are_not_reuse(self):
        short = norm("We call either case a structural-pillar failure.")
        long_ = norm("Its pillar is cracked when a drawing it hangs from is overruled by the county's survey.")
        self.assertEqual(A._cover(short, long_), 0.0)


if __name__ == "__main__":
    unittest.main()
