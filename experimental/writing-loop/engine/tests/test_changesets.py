import unittest
from pathlib import Path

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


def build_in_session(root, pars2, messages, command=None, output="", at=(3590, 3600)):
    """Like build(), but the session committed the second version the way the working sessions do: from its own
    worktree, `cd <repo> && git commit -q …`, which prints nothing. The transcript holds the Bash call (made at T0+at[0])
    and its result (back at T0+at[1]); the commit's own time is T0+3600."""
    repo = make_repo(root, [({"drafts/DRAFT-v1.md": draft_md("T", "Abs.", BASE)}, "v1", T0),
                            ({"drafts/DRAFT-v1.md": draft_md("T", "Abs.", pars2)}, "v2", T0 + 3600)])
    wt = Path(root) / "wt"
    wt.mkdir()
    command = (command if command is not None else "cd {repo} && git add -A && git commit -q -m v2").format(repo=repo)
    recs = [{"type": "user", "timestamp": iso(T0 + 600 + 300 * k), "origin": {"kind": "human"},
             "message": {"role": "user", "content": m}} for k, m in enumerate(messages)]
    recs += [{"type": "assistant", "timestamp": iso(T0 + at[0]),
              "message": {"id": "a1", "role": "assistant",
                          "content": [{"type": "tool_use", "id": "tu1", "name": "Bash", "input": {"command": command}}]}},
             {"type": "user", "timestamp": iso(T0 + at[1]), "toolUseResult": {"stdout": output},
              "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "tu1", "content": output}]}}]
    projects = make_transcripts(root, wt, "main", recs)
    ws = workspace(root, repo, "main", projects=projects)
    cfg = C.load(ws)
    cfg["transcripts"]["cwd_prefix"] = str(wt)
    C.save(ws, cfg)
    cfg = C.load(ws)
    vs = H.load_versions(cfg)
    conv = T.read(cfg)
    return CS.build(vs, H.assign_ids(vs), conv)[0], conv


class SessionCommitTest(unittest.TestCase):
    """The author approves proposals by number ("1. 可以 2. 按你的办"): no sentence label, no quotation, no rare word.
    The session then commits the change with `git commit -q`. The commit was traced to nothing and shown as 改动无出处
    (09-22, twice). A commit the session itself made is traced to the author's latest message in that session."""

    APPROVAL = ["1. 可以\n2. 按你的办", "好的，继续"]

    def edited(self):
        pars = list(BASE)
        pars[1] = BASE[1].replace("is missing", "is unlisted")
        return pars

    def sources(self, cs):
        return {r["trigger"]["source"] for r in cs["rows"]}

    def test_a_quiet_commit_the_session_made_is_traced_to_the_authors_latest_message_there(self):
        with TempDir() as root:
            cs, conv = build_in_session(root, self.edited(), self.APPROVAL)
            latest = [h for h in conv["human"] if h["text"] == "好的，继续"][0]["mid"]
            self.assertEqual(self.sources(cs), {"提交时的会话"})
            self.assertEqual({r["trigger"]["mid"] for r in cs["rows"]}, {latest})
            self.assertEqual((cs["status"], cs["triggers"]), ("one", [latest]))

    def test_without_the_sessions_commit_the_same_message_is_still_no_trigger(self):
        with TempDir() as root:
            cs, _ = build(root, self.edited(), self.APPROVAL)
            self.assertEqual(self.sources(cs), {"△"})

    def test_a_commit_line_in_git_log_output_is_not_the_session_committing(self):
        with TempDir() as root:
            cs, _ = build_in_session(root, self.edited(), self.APPROVAL, command="cd {repo} && git log --oneline -3",
                                     output="abc1234 v2")
            self.assertEqual(self.sources(cs), {"△"})

    def test_a_commit_call_at_another_time_is_not_this_commit(self):
        with TempDir() as root:
            cs, _ = build_in_session(root, self.edited(), self.APPROVAL, at=(100, 110))
            self.assertEqual(self.sources(cs), {"△"})

    def test_a_commit_call_that_does_not_name_the_manuscripts_repository_is_not_this_commit(self):
        with TempDir() as root:
            cs, _ = build_in_session(root, self.edited(), self.APPROVAL, command="git commit -q -m other")
            self.assertEqual(self.sources(cs), {"△"})


if __name__ == "__main__":
    unittest.main()
