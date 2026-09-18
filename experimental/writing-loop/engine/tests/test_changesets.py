import unittest

from loop import config as C
from loop import changesets as CS
from loop import history as H
from loop import transcripts as T

from fixtures import TempDir, draft_md, make_repo, make_transcripts, workspace

T0 = 1_760_000_000  # 2025-10-09T08:53:20Z
# "bridge" (4 sentences), "gauges" and "counties" (3 each) are spread across the draft; "pattern" is a word about writing.
BASE = ["Gauges draw the bridge in tidy ink. Counties state what the bridge carries and what it bears.",
        "Inspectors mark each sentence by tier, a pattern we keep. A pillar is missing when counties give no drawing.",
        "County plans draw the bridge more briefly than gauges. The bridge assessment weighs gauges with counties."]


def iso(t):
    import datetime
    return datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def build(root, pars2, messages, body=""):
    repo = make_repo(root, [({"drafts/DRAFT-v1.md": draft_md("T", "Abs.", BASE)}, "v1", T0),
                            ({"drafts/DRAFT-v1.md": draft_md("T", "Abs.", pars2)}, "v2\n\n" + body if body else "v2", T0 + 3600)])
    recs = [{"type": "user", "timestamp": iso(T0 + 600 + k), "origin": {"kind": "human"}, "message": {"role": "user", "content": m}}
            for k, m in enumerate(messages)]
    projects = make_transcripts(root, repo, "main", recs)
    cfg = C.load(workspace(root, repo, "main", projects=projects))
    vs = H.load_versions(cfg)
    tr = H.assign_ids(vs)
    conv = T.read(cfg)
    return CS.build(vs, tr, conv)[0], conv


class TriggerTest(unittest.TestCase):
    def test_entering_word_attributes_the_row(self):
        with TempDir() as root:
            pars = list(BASE)
            pars[1] = BASE[1].replace("is missing", "is unlisted")
            cs, conv = build(root, pars, ["选 c，漏项改称 unlisted"])
            self.assertEqual(len(cs["rows"]), 1)
            tg = cs["rows"][0]["trigger"]
            self.assertEqual((tg["source"], tg["matched"]), ("脚本推断", ["unlisted"]))
            self.assertEqual(cs["status"], "one")

    def test_unrelated_message_is_not_a_trigger(self):
        """The message shares two changed words with one row, but both are spread across the draft; it shares
        "pattern" with another row, but that is a word about writing. Both rows must stay △."""
        with TempDir() as root:
            pars = list(BASE)
            pars[1] = BASE[1].replace(", a pattern we keep.", ".")
            pars[2] = "County plans draw the bridge more briefly than gauges. Gauges and counties are weighed on the bridge assessment."
            cs, _ = build(root, pars, ["gauges 和 counties 那个 pattern 再看看"])
            self.assertGreaterEqual(len(cs["rows"]), 2)
            self.assertEqual({r["trigger"]["source"] for r in cs["rows"]}, {"△"})
            self.assertEqual(cs["status"], "none")

    def test_named_sentence_attributes_the_row(self):
        with TempDir() as root:
            pars = list(BASE)
            pars[1] = BASE[1].replace("is missing when counties give no drawing", "is absent when counties give no drawing at all")
            cs, _ = build(root, pars, ["I2.2 这句我读不懂"])
            tg = cs["rows"][0]["trigger"]
            self.assertEqual((tg["source"], tg["method"], tg["matched"]), ("脚本推断", "句子编号", ["I2.2"]))

    def test_mixed_commit_is_marked(self):
        with TempDir() as root:
            pars = list(BASE)
            pars[1] = BASE[1].replace("is missing", "is unlisted")
            pars[2] = "County tags draw the bridge more briefly than gauges. The bridge assessment weighs gauges with counties."
            cs, _ = build(root, pars, ["漏项改称 unlisted"])
            self.assertEqual(sorted(r["trigger"]["source"] for r in cs["rows"]), ["△", "脚本推断"])
            self.assertEqual((cs["status"], cs["unknown_rows"]), ("mixed", 1))

    def test_commit_trailer_must_point_to_a_real_message(self):
        pars = list(BASE)
        pars[2] = "County tags draw the bridge more briefly than gauges. The bridge assessment weighs gauges with counties."
        with TempDir() as root:
            cs, _ = build(root, pars, ["说明文字那句改一下"], body="Loop-Trigger: h-0000000000")
            self.assertEqual(cs["rows"][0]["trigger"]["source"], "△")
            self.assertIn("不在会话记录里", cs["rows"][0]["trigger"]["why"])
        with TempDir() as root:  # message ids depend only on timestamp and words, so they repeat across fixtures
            _, conv = build(root, pars, ["说明文字那句改一下"])
            mid = conv["human"][0]["mid"]
        with TempDir() as root:
            cs, _ = build(root, pars, ["说明文字那句改一下"], body=f"Loop-Trigger: {mid}")
            self.assertEqual(cs["rows"][0]["trigger"], {"source": "提交信息", "mid": mid})


if __name__ == "__main__":
    unittest.main()
