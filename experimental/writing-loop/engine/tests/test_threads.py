import unittest

from loop import config as C
from loop import history as H
from loop import threads as TH

from fixtures import TempDir, draft_md, make_repo, workspace

T0 = 1_760_000_000
PARS = ["Gauges draw the bridge in tidy ink. Counties state what the bridge carries and what it bears.",
        "Inspectors mark each sentence by tier. A pillar is unlisted when the plan gives no drawing."]


def versions(root):
    repo = make_repo(root, [({"drafts/DRAFT-v1.md": draft_md("T", "Abs.", PARS)}, "v1", T0)])
    vs = H.load_versions(C.load(workspace(root, repo, "main")))
    H.assign_ids(vs)
    return vs


def msg(text, t=T0 + 60):
    return {"mid": "h-x", "t": t, "text": text}


class AttachTest(unittest.TestCase):
    def test_label_attaches(self):
        with TempDir() as root:
            _, hits = TH.attach(msg("I2.2 这句我看不懂"), versions(root))
            self.assertEqual([(h["label"], h["method"]) for h in hits], [("I2.2", "句子编号")])

    def test_quoted_fragment_attaches(self):
        with TempDir() as root:
            vs = versions(root)
            _, hits = TH.attach(msg("“state what the bridge carries” 这里是不是太满了"), vs)
            self.assertEqual([(h["label"], h["method"]) for h in hits], [("I1.2", "引号原文")])
            _, hits = TH.attach(msg("<!-- reply -->\n> A pillar is unlisted when the plan gives no drawing.\n为什么这么写"), vs)
            self.assertEqual([h["label"] for h in hits], ["I2.2"])

    def test_paraphrase_does_not_attach(self):
        with TempDir() as root:
            _, hits = TH.attach(msg("前提没写出来那句的定义还是不清楚"), versions(root))
            self.assertEqual(hits, [])

    def test_message_before_first_version_has_no_version(self):
        with TempDir() as root:
            sha, hits = TH.attach(msg("I2.2", t=T0 - 60), versions(root))
            self.assertEqual((sha, hits), (None, []))

    def test_label_that_does_not_exist_is_not_attached(self):
        with TempDir() as root:
            _, hits = TH.attach(msg("I9.9 和 A01.2 都看看"), versions(root))
            self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
