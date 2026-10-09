import json
import unittest
from pathlib import Path

from loop import config as C
from loop import transcripts as T

from fixtures import TempDir, make_repo, make_transcripts, workspace, draft_md


def human(ts, text, **kw):
    return {"type": "user", "timestamp": ts, "origin": {"kind": "human"}, "promptId": "p", "message": {"role": "user", "content": text}, **kw}


RECORDS = [
    human("2026-09-17T10:00:00.000Z", "I4.4 这句我看不懂"),
    human("2026-09-17T10:00:00.000Z", "I4.4 这句我看不懂", _file="s2"),  # continued session copies history
    {"type": "attachment", "timestamp": "2026-09-17T10:01:00.000Z",
     "attachment": {"type": "queued_command", "prompt": "这一句我还是没看明白", "commandMode": "prompt", "origin": {"kind": "human"}}},
    {"type": "user", "timestamp": "2026-09-17T10:02:00.000Z", "toolUseResult": {}, "message": {"role": "user", "content": [{"type": "tool_result", "content": "x"}]}},
    {"type": "user", "timestamp": "2026-09-17T10:03:00.000Z", "origin": {"kind": "task-notification"}, "message": {"role": "user", "content": "<task-notification>done</task-notification>"}},
    {"type": "user", "timestamp": "2026-09-17T10:04:00.000Z", "message": {"role": "user", "content": "<local-command-stdout>ok</local-command-stdout>"}},
    human("2026-09-17T10:05:00.000Z", "<system-reminder>\ninjected\n</system-reminder>\n可以 继续吧"),
    human("2026-09-17T10:05:30.000Z", "<bash-input>ls</bash-input><bash-stdout>a.tex</bash-stdout><bash-stderr></bash-stderr>"),
    human("2026-09-17T10:06:00.000Z", "a subagent prompt", isSidechain=True),
    human("2026-09-17T10:07:00.000Z", "a message on another branch", gitBranch="other"),
    {"type": "assistant", "timestamp": "2026-09-17T10:00:05.000Z", "message": {"id": "msg_1", "content": [{"type": "text", "text": "第一段"}]}},
    {"type": "assistant", "timestamp": "2026-09-17T10:00:06.000Z", "message": {"id": "msg_1", "content": [{"type": "tool_use", "name": "Read"}]}},
    {"type": "assistant", "timestamp": "2026-09-17T10:00:07.000Z", "message": {"id": "msg_1", "content": [{"type": "text", "text": "第二段"}]}},
    {"type": "assistant", "timestamp": "2026-09-17T10:00:07.000Z", "message": {"id": "msg_1", "content": [{"type": "text", "text": "第二段"}]}, "_file": "s2"},
]


class TranscriptReadTest(unittest.TestCase):
    def read(self, root):
        repo = make_repo(root, [({"drafts/DRAFT-v1.md": draft_md("T", "A.", ["B."])}, "v1", 1_700_000_000)])
        projects = make_transcripts(root, repo, "main", RECORDS)
        return T.read(C.load(workspace(root, repo, "main", projects=projects)))

    def test_prompt_and_queued_messages_are_both_read(self):
        with TempDir() as root:
            d = self.read(root)
            self.assertEqual([(h["channel"], h["text"]) for h in d["human"]],
                             [("prompt", "I4.4 这句我看不懂"), ("queued", "这一句我还是没看明白"), ("prompt", "可以 继续吧")])

    def test_copies_in_continued_sessions_count_once(self):
        with TempDir() as root:
            d = self.read(root)
            self.assertEqual(d["human"][0]["sessions"], ["s1", "s2"])
            self.assertEqual(len([h for h in d["human"] if h["text"] == "I4.4 这句我看不懂"]), 1)

    def test_injected_reminder_is_removed_and_counted(self):
        with TempDir() as root:
            h = self.read(root)["human"][2]
            self.assertEqual(h["text"], "可以 继续吧")
            self.assertGreater(h["stripped_chars"], 0)

    def test_a_shell_command_run_with_bang_is_not_an_authors_message(self):
        """`!cmd` in Claude Code is stored as a human-origin prompt that starts with <bash-input>. It is a command
        and the shell's output, not words about the draft, so it is counted with the other non-author records."""
        with TempDir() as root:
            d = self.read(root)
            self.assertFalse([h for h in d["human"] if "<bash-input>" in h["text"]])

    def test_non_author_records_are_counted_not_dropped(self):
        with TempDir() as root:
            d = self.read(root)
            self.assertEqual(d["unclassified"], {"<bash-input>": 1, "<local-command-stdout>": 1, "origin:task-notification": 1})
            self.assertNotIn("a subagent prompt", [h["text"] for h in d["human"]])
            self.assertNotIn("a message on another branch", [h["text"] for h in d["human"]])

    def test_assistant_blocks_join_by_message_id(self):
        with TempDir() as root:
            a = self.read(root)["assistant"]
            self.assertEqual([(x["aid"], x["text"]) for x in a], [("msg_1", "第一段\n\n第二段")])


class PrimaryByIdTest(unittest.TestCase):
    """transcripts.sessions names a session that works on the manuscript from another directory and branch (it edits the
    draft by absolute path). Its messages are the author's on this manuscript, as the hooks treat it; a neighbour in
    that same directory is not taken in."""

    def setup_ws(self, root):
        repo = make_repo(root, [({"drafts/DRAFT-v1.md": draft_md("T", "A.", ["B."])}, "v1", 1_700_000_000)])
        projects = make_transcripts(root, repo, "main", [human("2026-09-17T10:00:00.000Z", "a message in the repo")])
        other = Path(root) / "elsewhere"
        other.mkdir()
        make_transcripts(root, other, "spike", [
            human("2026-09-17T11:00:00.000Z", "a message from the named session", _file="s7", uuid="u-named-0001"),
            human("2026-09-17T11:05:00.000Z", "a message from its neighbour", _file="s8", uuid="u-neighbour-0002")])
        ws = workspace(root, repo, "main", projects=projects)
        cfg = C.load(ws)
        cfg["transcripts"]["sessions"] = [{"id": "s7", "note": "edits the draft from another checkout"}]
        C.save(ws, cfg)
        return C.load(ws)

    def test_a_session_named_by_its_id_is_read_wherever_it_ran(self):
        with TempDir() as root:
            texts = [h["text"] for h in T.read(self.setup_ws(root))["human"]]
            self.assertEqual(texts, ["a message in the repo", "a message from the named session"])

    def test_its_file_is_read_even_when_the_scan_cache_says_it_holds_no_branch(self):
        """The scan cache skips files that did not hold the branch: a file cached before its id was named must still
        be read once the id is named."""
        with TempDir() as root:
            cfg = self.setup_ws(root)
            ids = cfg["transcripts"].pop("sessions")
            cache = str(Path(root) / "scan.json")
            files = T.session_files(cfg) + sorted((Path(root) / "projects").glob("*/s7.jsonl"))
            T.read(cfg, files=files, scan_cache=cache)
            cfg["transcripts"]["sessions"] = ids
            texts = [h["text"] for h in T.read(cfg, files=files, scan_cache=cache)["human"]]
            self.assertIn("a message from the named session", texts)

    def test_an_author_message_in_it_is_on_record_for_approvals_and_the_ring(self):
        """A decision or an approval the author gave in that session names its uuid; the uuid must be found there,
        as it is for a session under the configured prefix."""
        from loop import ringinputs as RI
        from loop import targets as TG
        with TempDir() as root:
            cfg = self.setup_ws(root)
            cfg["_ws"] = str(Path(root) / "ws")
            self.assertTrue(TG._approval_in_transcripts(cfg, "u-named-0001"))
            self.assertFalse(TG._approval_in_transcripts(cfg, "u-neighbour-0002"))
            self.assertIn("s7.jsonl", [Path(f).name for f in RI._transcript_files(cfg)])


if __name__ == "__main__":
    unittest.main()
