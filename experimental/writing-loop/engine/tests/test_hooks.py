"""Hooks (plan 2.1-2.3), replayed with the field names the runtime actually sends (read from the binary).

Every test builds its own registry, workspace and manuscript repository in a temporary directory.
"""
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from loop import config as C
from loop import health as HL
from loop import lintel as LN

from fixtures import TempDir, draft_md, git, make_repo, make_transcripts, workspace

HOOKS = Path(__file__).resolve().parents[2] / "hooks"
sys.path.insert(0, str(HOOKS))
import loop_hook as LH  # noqa: E402

MD = draft_md("A title", "One sentence. Two sentence.", ["Intro one. Intro two."])


def setup(root):
    repo = make_repo(root, [({"drafts/DRAFT-v1.md": MD, "ev/claims.json": "[]", "ev/check.py": "KEYMAP = {}\n"}, "v1", 1_700_000_000)])
    projects = make_transcripts(root, repo, "main", [{"type": "user", "timestamp": "2026-01-01T00:00:00Z",
                                                      "origin": {"kind": "human"}, "message": {"role": "user", "content": "hi"}}])
    ws = workspace(root, repo, "main", projects=projects,
                   ledger={"path": "ev/claims.json", "evidence_dir": "ev", "keymap_from": "ev/check.py"})
    reg = Path(root) / "registry"
    reg.write_text(f"# comment\n{ws}\n\n", encoding="utf-8")
    regs, bad = LH.registry(str(reg))
    return repo, ws, regs


def prompt_payload(cwd, **extra):
    base = {"session_id": "s1", "transcript_path": "/dev/null", "cwd": str(cwd), "prompt_id": "p1",
            "permission_mode": "default", "hook_event_name": "UserPromptSubmit", "prompt": "可以 但是 A03 先别动"}
    base.update(extra)
    return base


def tool_payload(event, cwd, tool, tool_input):
    return {"session_id": "s1", "transcript_path": "/dev/null", "cwd": str(cwd), "hook_event_name": event,
            "tool_name": tool, "tool_input": tool_input, "tool_use_id": "t1"}


class Spy:
    def __init__(self):
        self.calls = []

    def __call__(self, ws, reason):
        self.calls.append(reason)


class PromptTest(unittest.TestCase):
    def test_prompt_is_kept_verbatim_and_the_block_is_asked_for(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            out = LH.handle(prompt_payload(repo), regs)
            rec = json.loads((ws / "human" / "comments.jsonl").read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(rec["prompt"], "可以 但是 A03 先别动")
            self.assertEqual(rec["origin"], "hook:UserPromptSubmit")
            ctx = out["hookSpecificOutput"]["additionalContext"]
            self.assertIn("〔循环〕", ctx)
            self.assertEqual(out["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")

    def test_the_reminder_carries_the_coverage_line_and_only_when_something_is_not_current(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("覆盖：还没有算过", ctx, "no summary yet must be said, not left silent")
            cov = Path(ws) / "cache" / "coverage"
            from loop import catalogue as K
            from loop import coverage as V
            saved = list(K.CHECKS)
            K.CHECKS[:] = [dict(K.by_id("claim-positioning"), name="读者组")]
            self.addCleanup(lambda s=saved: K.CHECKS.__setitem__(slice(None), s))
            cfg = C.load(ws)
            cfg["genre"] = "note"
            C.save(ws, cfg)
            summary = V.compute(C.load(ws), ws)
            summary["rows"][0].update(status="过期", detail="句子改 3")
            (cov / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
            ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("过期 读者组", ctx)
            summary["rows"][0].update(status="最新", detail="")
            summary["experiments"] = None
            (cov / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
            ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            self.assertNotIn("覆盖", ctx)
            (cov / "summary.json").write_text("{not json", encoding="utf-8")
            ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("覆盖", ctx, "a broken summary must not read as all checked")
            (cov / "summary.json").write_text(json.dumps({"rows": 5}), encoding="utf-8")
            ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("覆盖：还没有算过", ctx, "a summary of the wrong shape is not trusted")
            summary["head"] = "0" * 40
            (cov / "summary.json").write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
            ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("覆盖摘要", ctx, "a summary computed for another HEAD is not current")
            from loop import coverage as V
            saved = V.reminder_line
            V.reminder_line = lambda *a, **k: (_ for _ in ()).throw(KeyError("rows"))
            try:
                ctx = LH.handle(prompt_payload(repo), regs)["hookSpecificOutput"]["additionalContext"]
            finally:
                V.reminder_line = saved
            self.assertIn("不能当作都查过了", ctx, "a failure computing the line must still reach the agent as text")

    def test_a_history_source_session_sees_coverage_and_nothing_is_recorded(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            other = Path(root) / "other"
            other.mkdir()
            git(other, "init", "-q", "-b", "old-branch")
            git(other, "commit", "-q", "--allow-empty", "-m", "x")
            cfg = C.load(ws)
            cfg["transcripts"]["also"] = [{"git_branch": "old-branch", "cwd_prefix": str(other)}]
            C.save(ws, cfg)
            regs, _ = LH.registry(str(Path(root) / "registry"))
            out = LH.handle(prompt_payload(other), regs)
            self.assertIn("历史来源", out["hookSpecificOutput"]["additionalContext"])
            self.assertIn("覆盖", out["hookSpecificOutput"]["additionalContext"])
            self.assertFalse((ws / "human" / "comments.jsonl").exists(), "a history source is never written for")
            cfg["transcripts"]["also"] = [{"cwd_prefix": str(Path(root) / "plain")}]
            C.save(ws, cfg)
            (Path(root) / "plain").mkdir()
            regs, _ = LH.registry(str(Path(root) / "registry"))
            self.assertIsNone(LH.handle(prompt_payload(Path(root) / "plain"), regs),
                              "a history source with no branch matches nothing, not every folder that is not a repository")

    def test_the_documentations_field_name_is_a_visible_error_not_silence(self):
        """The docs once said user_prompt; the runtime sends prompt. A hook reading the wrong one must be seen."""
        with TempDir() as root:
            repo, ws, regs = setup(root)
            p = prompt_payload(repo)
            p["user_prompt"] = p.pop("prompt")
            self.assertIsNone(LH.handle(p, regs))
            self.assertFalse((ws / "human" / "comments.jsonl").exists())
            self.assertIn("钩子异常", [item for item, _ in HL.file_problems(ws)])

    def test_another_branch_or_directory_is_not_recorded(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            git(repo, "checkout", "-q", "-b", "other")
            self.assertIsNone(LH.handle(prompt_payload(repo), regs))
            self.assertIsNone(LH.handle(prompt_payload(root), regs))
            self.assertFalse((ws / "human" / "comments.jsonl").exists())

    def test_a_shell_command_run_with_bang_is_not_recorded_as_the_authors_words(self):
        """`!cmd` reaches UserPromptSubmit as <bash-input>…</bash-input><bash-stdout>…. The author typed it, but it is
        a shell command and its output, not a comment on the draft, so it stays out of human/ (seen 2026-09-21)."""
        with TempDir() as root:
            repo, ws, regs = setup(root)
            out = LH.handle(prompt_payload(repo, prompt="<bash-input>chmod 600 f</bash-input><bash-stdout></bash-stdout>"), regs)
            self.assertIn("〔循环〕", out["hookSpecificOutput"]["additionalContext"])
            self.assertFalse((ws / "human" / "comments.jsonl").exists())

    def test_system_envelopes_are_not_recorded_as_the_authors_words(self):
        """Background-task notices and messages from another Claude session reach UserPromptSubmit too
        (checked against real transcripts, 2026-09-17). They are said to the model, not by the author, so they
        stay out of human/; the reminder still goes out, since the turn they start can still edit the draft.
        A quoted reply starts with markup as well, and it is the author's."""
        envelopes = [
            "<task-notification>\n<task-id>t1</task-id>\n<status>completed</status>\n</task-notification>",
            '<cross-session-message from="uds:/tmp/fake/1.sock" from-name="other" from-mode="prompting">\n'
            "Status from session B: the nightly build finished.\n</cross-session-message>",
            "  <system-reminder>\nsynthetic\n</system-reminder>",
            "[SYSTEM NOTIFICATION] synthetic",
        ]
        with TempDir() as root:
            repo, ws, regs = setup(root)
            for text in envelopes:
                out = LH.handle(prompt_payload(repo, prompt=text), regs)
                self.assertIn("〔循环〕", out["hookSpecificOutput"]["additionalContext"], text[:24])
            self.assertFalse((ws / "human" / "comments.jsonl").exists())
            quoted = "<!-- reply -->\n> 〔循环〕\n> 改了：无\n> 〔/循环〕\n\n这一块是什么意思？"
            LH.handle(prompt_payload(repo, prompt=quoted), regs)
            recs = [json.loads(line) for line in (ws / "human" / "comments.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["prompt"] for r in recs], [quoted])


    def test_the_envelope_rule_is_read_from_the_willow_plugin(self):
        """Which records are not the author's words is decided by one rule file, kept by the wishing-willow plugin;
        two copies had drifted. A record is an envelope only when nothing is left once the listed blocks are removed:
        text after them is the author's, and is recorded."""
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            rule = Path(root) / "envelopes.json"
            rule.write_text(json.dumps({"tags": ["fake-envelope"], "prefixes": ["[FAKE"]}), encoding="utf-8")
            with mock.patch.dict(os.environ, {"WILLOW_ENVELOPES": str(rule)}):
                for text in ("<fake-envelope>x</fake-envelope>", "[FAKE] y"):
                    LH.handle(prompt_payload(repo, prompt=text), regs)
                self.assertFalse((ws / "human" / "comments.jsonl").exists(), "the rule file's envelopes stay out")
                said = "<fake-envelope>x</fake-envelope> 这一句是作者自己说的"
                out = LH.handle(prompt_payload(repo, prompt=said), regs)
                self.assertNotIn("内置", out["hookSpecificOutput"]["additionalContext"])
            recs = [json.loads(line) for line in (ws / "human" / "comments.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([r["prompt"] for r in recs], [said])

    def test_without_the_willow_rule_file_the_built_in_rule_is_used_and_said(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            with mock.patch.dict(os.environ, {"WILLOW_ENVELOPES": str(Path(root) / "missing.json")}):
                out = LH.handle(prompt_payload(repo, prompt="<bash-input>ls</bash-input><bash-stdout>a</bash-stdout>"), regs)
            self.assertIn("内置", out["hookSpecificOutput"]["additionalContext"], "a missing rule file is said, not silent")
            self.assertFalse((ws / "human" / "comments.jsonl").exists(), "the built-in rule still knows shell input")


class GuardTest(unittest.TestCase):
    def denied(self, out):
        return out is not None and out["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_absolute_and_relative_writes_into_human_are_refused_and_recorded(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            problems_before = HL.file_problems(ws)
            self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", repo, "Write",
                                                               {"file_path": str(ws / "human" / "comments.jsonl"), "content": "x"}), regs)))
            self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", ws, "Edit",
                                                               {"file_path": "human/reactions.jsonl", "old_string": "a", "new_string": "b"}), regs)))
            events = [e for e in HL.load(ws)["events"] if e["kind"] == "guard_denied"]
            self.assertEqual(len(events), 2)
            self.assertIn("拦下写入", [item for item, _ in HL.file_notices(ws)])
            self.assertEqual(HL.file_problems(ws), problems_before)  # the guard worked; a refusal is not a fault

    def test_shell_writes_naming_human_are_refused_including_the_home_form(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", repo, "Bash",
                                                               {"command": f"echo x >> {ws}/human/comments.jsonl"}), regs)))
            old = os.environ.get("HOME")
            os.environ["HOME"] = str(Path(root).resolve())
            try:
                tilde = "~/" + os.path.relpath(os.path.realpath(ws / "human"), os.path.realpath(root))
                self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", repo, "Bash",
                                                                   {"command": f"cp a {tilde}/x"}), regs)))
            finally:
                os.environ["HOME"] = old
            # A path through a symlink names the same directory. Built here rather than left to the platform:
            # macOS's temporary directory sits behind /var -> /private/var, Linux's /tmp does not.
            alias = Path(root) / "alias"
            alias.symlink_to(ws, target_is_directory=True)
            self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", repo, "Bash",
                                                               {"command": f"echo x >> {alias}/human/comments.jsonl"}), regs)))

    def test_reading_human_is_allowed_but_redirecting_into_it_is_not(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            h = ws / "human"
            self.assertIsNone(LH.handle(tool_payload("PreToolUse", repo, "Bash", {"command": f"cat {h}/comments.jsonl | wc -l"}), regs))
            # found in live use: a compound command that only reads human/ but does other things elsewhere
            for cmd in (f"ls -la {h}/; cd /tmp && python3 -c 'print(1)'", f"cat {h}/c 2>&1 | head -3", f"cat {h}/c > /tmp/out"):
                self.assertIsNone(LH.handle(tool_payload("PreToolUse", repo, "Bash", {"command": cmd}), regs), cmd)
            for cmd in (f"cat x > {h}/y", f"grep a {h}/c | tee {h}/d", f"sed -i s/a/b/ {h}/c", f"cat {h}/c; rm {h}/c",
                        f"cd {h} && rm c", f"cat a >> {h}/c 2>&1"):
                self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", repo, "Bash", {"command": cmd}), regs)), cmd)

    def test_a_read_is_split_and_named_the_way_the_shell_does_it(self):
        """Found in live use (2026-09-19): a jq program with | inside single quotes, a grep pattern with | in it,
        and /usr/bin/grep were all refused although they only read. A quoted | does not end a command, and a
        reading command named by its full path from a system directory is still that command."""
        with TempDir() as root:
            repo, ws, regs = setup(root)
            h = ws / "human"
            for cmd in (f"jq -r 'select(.prompt|startswith(\"<\")) | .at' {h}/comments.jsonl",
                        f"grep -E 'a|b' {h}/c",
                        f'grep -o -E "(at|prompt)" {h}/c; echo done',
                        f"/usr/bin/grep -c x {h}/c",
                        f"grep '>' {h}/c"):
                self.assertIsNone(LH.handle(tool_payload("PreToolUse", repo, "Bash", {"command": cmd}), regs), cmd)

    def test_quotes_do_not_hide_a_write(self):
        """Reading quotes the shell's way must not open a door: a quoted redirect target, a command substitution
        inside quotes, a background & and a reading command's name borrowed by a file elsewhere are all writes
        or unknowns. The first four were let through before quotes were read at all."""
        with TempDir() as root:
            repo, ws, regs = setup(root)
            h = ws / "human"
            for cmd in (f'cat a > "{h}/b"',
                        f"cat a >'{h}/b'",
                        f'cat "$(tee {h}/b < a)"',
                        f"cat {h}/c & rm {h}/c",
                        f"cat `cp a {h}/b`",
                        f"grep x <(cat a) > {h}/b",
                        f"/tmp/fake/bin/grep x {h}/c",
                        f"sh -c 'rm {h}/c'",
                        f"grep 'x' {h}/c | sh -c 'cat > {h}/d'"):
                self.assertTrue(self.denied(LH.handle(tool_payload("PreToolUse", repo, "Bash", {"command": cmd}), regs)), cmd)

    def test_other_writes_pass_and_malformed_payloads_do_not_crash(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            self.assertIsNone(LH.handle(tool_payload("PreToolUse", repo, "Write", {"file_path": str(repo / "drafts" / "x.md")}), regs))
            self.assertIsNone(LH.handle(tool_payload("PreToolUse", repo, "Bash", {"command": "ls human"}), regs))
            for bad in (None, "Write", [], {"file_path": 3}):
                self.assertIsNone(LH.handle(tool_payload("PreToolUse", repo, "Write", bad), regs))
            self.assertIsNone(LH.handle({"hook_event_name": "PreToolUse"}, regs))


class TriggerTest(unittest.TestCase):
    def test_draft_and_ledger_writes_and_git_commands_ask_for_an_update(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            spy = Spy()
            for tool, ti in [("Write", {"file_path": str(repo / "drafts" / "DRAFT-v2.md")}),
                             ("Edit", {"file_path": "ev/claims.json"}),
                             ("Write", {"file_path": str(repo / "notes.md")}),
                             ("Bash", {"command": "git commit -qm 'v2'"}),
                             ("Bash", {"command": "ls -la"})]:
                LH.handle(tool_payload("PostToolUse", repo, tool, ti), regs, spawn=spy)
            self.assertEqual(spy.calls, ["write:drafts/DRAFT-v2.md", "write:ev/claims.json", "git"])

    def test_a_draft_write_or_git_command_in_a_long_turn_brings_the_card_producer_back(self):
        """2026-10-04: a producer exited after 30 idle minutes (as designed) while its working session was in
        one long turn; the turn then kept editing and committing, `loop update` ran, but nothing rewrote the card until
        the next human prompt. The same writes that ask for an update now also make sure a producer is alive."""
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            ensured = []
            with mock.patch.object(LH, "ensure_producer", ensured.append):
                for tool, ti in [("Write", {"file_path": str(repo / "drafts" / "DRAFT-v2.md")}),
                                 ("Write", {"file_path": str(repo / "notes.md")}),
                                 ("Bash", {"command": "git commit -qm 'v2'"}),
                                 ("Bash", {"command": "ls -la"})]:
                    LH.handle(tool_payload("PostToolUse", repo, tool, ti), regs, spawn=Spy())
            self.assertEqual([Path(w).name for w in ensured], [ws.name, ws.name])

    def test_a_draft_made_of_several_files_is_matched_file_by_file(self):
        """draft.glob may be a list: the files that together are the draft (a LaTeX main file and its sections),
        as history.py reads it. A write to one of them asks for an update; a sibling file does not; nothing raises."""
        with TempDir() as root:
            repo, ws, regs = setup(root)
            cfg = C.load(ws)
            cfg["draft"]["glob"] = ["main.tex", "sections/intro.tex"]
            C.save(ws, cfg)
            regs, _bad = LH.registry(str(Path(root) / "registry"))
            spy = Spy()
            for tool, ti in [("Edit", {"file_path": str(repo / "sections" / "intro.tex")}),
                             ("Write", {"file_path": str(repo / "sections" / "notes.tex")}),
                             ("Edit", {"file_path": "main.tex"})]:
                LH.handle(tool_payload("PostToolUse", repo, tool, ti), regs, spawn=spy)
            self.assertEqual(spy.calls, ["write:sections/intro.tex", "write:main.tex"])

    def test_stop_asks_for_an_update_only_in_a_registered_session(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            spy = Spy()
            LH.handle({"hook_event_name": "Stop", "cwd": str(repo), "stop_hook_active": False, "last_assistant_message": ""}, regs, spawn=spy)
            LH.handle({"hook_event_name": "Stop", "cwd": str(root)}, regs, spawn=spy)
            self.assertEqual(spy.calls, ["stop"])

    def test_a_submitted_paper_does_not_rebuild_its_index_after_each_turn(self):
        # K11 功耗（2026-10-01）：一次 update 连同顺带的检查要将近一分钟单核；稿子投出去以后，答完、写稿、git 都不再触发。
        from loop import config as C
        with TempDir() as root:
            repo, ws, regs = setup(root)
            ledger = Path(root) / "claims.md"
            ledger.write_text("阶段：已投稿，冻结\n", encoding="utf-8")
            cfg = C.load(ws)
            cfg["claims"] = str(ledger)
            C.save(ws, cfg)
            regs = [(w, C.load(w)) for w, _ in regs]
            spy = Spy()
            LH.handle({"hook_event_name": "Stop", "cwd": str(repo), "stop_hook_active": False, "last_assistant_message": ""}, regs, spawn=spy)
            self.assertEqual(spy.calls, [])
            ledger.write_text("阶段：返修\n", encoding="utf-8")
            LH.handle({"hook_event_name": "Stop", "cwd": str(repo), "stop_hook_active": False, "last_assistant_message": ""}, regs, spawn=spy)
            self.assertEqual(spy.calls, ["stop"])

    def test_an_api_error_ends_the_turn_as_unfinished(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            spy = Spy()
            out = LH.handle({"hook_event_name": "StopFailure", "cwd": str(repo), "error": "overloaded"}, regs, spawn=spy)
            LH.handle({"hook_event_name": "StopFailure", "cwd": str(root), "error": "overloaded"}, regs, spawn=spy)
            self.assertIsNone(out)
            self.assertEqual(spy.calls, ["stop:error"])

    def test_missing_tool_input_is_recorded(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            LH.handle({"hook_event_name": "PostToolUse", "cwd": str(repo), "tool_name": "Write"}, regs, spawn=Spy())
            self.assertIn("钩子异常", [item for item, _ in HL.file_problems(ws)])


class ProducerTest(unittest.TestCase):
    def test_a_submitted_paper_does_not_start_the_resident_producer(self):
        # K10 功耗（2026-10-01）：稿子投出去以后，钩子不再把常驻来源进程拉起来；阶段改回别的就照常拉起。
        from loop import config as C
        with TempDir() as root:
            repo, ws, regs = setup(root)
            ledger = Path(root) / "claims.md"
            ledger.write_text("阶段：已投稿，冻结\n", encoding="utf-8")
            cfg = C.load(ws)
            cfg["claims"] = str(ledger)
            C.save(ws, cfg)
            started = []
            home = Path(root) / "lintel-home"
            home.mkdir()
            (home / "registry.json").write_text(json.dumps({"producers": {LN.PRODUCER: {}}}), encoding="utf-8")
            old = os.environ.get("LOOP_LINTEL_HOME")
            os.environ["LOOP_LINTEL_HOME"] = str(home)
            try:
                self.assertFalse(LH.ensure_producer(ws, start=started.append))
                ledger.write_text("阶段：返修\n", encoding="utf-8")
                self.assertTrue(LH.ensure_producer(ws, start=started.append))
                self.assertEqual(started, [ws])
            finally:
                if old is None:
                    os.environ.pop("LOOP_LINTEL_HOME", None)
                else:
                    os.environ["LOOP_LINTEL_HOME"] = old

    def test_the_resident_producer_is_started_only_when_lintel_registered_it(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            started = []
            home = Path(root) / "lintel-home"
            old = os.environ.get("LOOP_LINTEL_HOME")
            os.environ["LOOP_LINTEL_HOME"] = str(home)
            try:
                self.assertFalse(LH.ensure_producer(ws, start=started.append))
                self.assertFalse(home.exists())
                home.mkdir()
                (home / "registry.json").write_text(json.dumps({"producers": {LN.PRODUCER: {}}}), encoding="utf-8")
                self.assertTrue(LH.ensure_producer(ws, start=started.append))
                self.assertEqual(started, [ws])
            finally:
                os.environ["LOOP_LINTEL_HOME"] = old


class AlsoSourceTest(unittest.TestCase):
    def test_an_also_source_is_read_but_the_hooks_do_not_act_on_it(self):
        """A session that once worked on the manuscript stays readable (its messages still trace commits),
        but after rebinding it no longer gets the hooks' reminder or records."""
        from loop import config as C
        from loop import transcripts as T
        with TempDir() as root:
            repo, ws, _ = setup(root)
            make_transcripts(root, repo, "other", [{"_file": "s9", "type": "user", "timestamp": "2026-01-03T00:00:00Z",
                                                    "origin": {"kind": "human"}, "message": {"role": "user", "content": "旧会话里的话"}}])
            cfg = json.loads((ws / "config.json").read_text())
            cfg["transcripts"]["also"] = [{"git_branch": "other", "cwd_prefix": str(repo)}]
            (ws / "config.json").write_text(json.dumps(cfg))
            self.assertIn("旧会话里的话", [h["text"] for h in T.read(C.load(ws))["human"]])
            reg = Path(root) / "registry"
            regs, _ = LH.registry(str(reg))
            git(repo, "checkout", "-q", "-b", "other")
            self.assertEqual(LH.session_ws(prompt_payload(repo), regs), (None, None))


class PrimaryByIdTest(unittest.TestCase):
    """A session that edits the draft from another directory, by absolute path, was not a manuscript session: the hooks
    matched only a cwd under the configured prefix on the configured branch. transcripts.sessions names it by id, and
    it then counts as the manuscript's own session wherever it runs; a neighbour in the same directory does not."""

    def setup_named(self, root):
        repo, ws, regs = setup(root)
        elsewhere = Path(root) / "elsewhere"
        elsewhere.mkdir()
        git(elsewhere, "init", "-q", "-b", "spike")
        git(elsewhere, "commit", "-q", "--allow-empty", "-m", "x")
        cfg = C.load(ws)
        cfg["transcripts"]["sessions"] = [{"id": "s7", "note": "edits the draft from another checkout"}]
        C.save(ws, cfg)
        regs, _ = LH.registry(str(Path(root) / "registry"))
        return repo, ws, regs, elsewhere

    def test_its_prompts_are_recorded_and_it_gets_the_reminder(self):
        with TempDir() as root:
            repo, ws, regs, elsewhere = self.setup_named(root)
            self.assertEqual(LH.session_ws(prompt_payload(elsewhere, session_id="s7"), regs)[0], ws.resolve())
            self.assertEqual(LH.session_ws(prompt_payload(elsewhere, session_id="s8"), regs), (None, None),
                             "a neighbour in the same directory is not taken in")
            out = LH.handle(prompt_payload(elsewhere, session_id="s7", prompt="a synthetic remark"), regs)
            self.assertIn("〔循环〕", ctx_of(out))
            self.assertIsNone(LH.handle(prompt_payload(elsewhere, session_id="s8", prompt="not about it"), regs))
            recs = [json.loads(x) for x in (ws / "human" / "comments.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([(r["session_id"], r["prompt"]) for r in recs], [("s7", "a synthetic remark")])

    def test_its_draft_writes_by_absolute_path_and_its_stops_ask_for_an_update(self):
        with TempDir() as root:
            repo, ws, regs, elsewhere = self.setup_named(root)
            (elsewhere / "drafts").mkdir()
            spy = Spy()
            # each write is judged on its own: the same relative path in the repository the session runs in is not the draft
            for sid, target, calls in [("s7", repo / "drafts" / "DRAFT-v2.md", ["write:drafts/DRAFT-v2.md"]),
                                       ("s7", elsewhere / "drafts" / "DRAFT-v3.md", []),
                                       ("s8", repo / "drafts" / "DRAFT-v2.md", [])]:
                with self.subTest(sid=sid, target=target.parent.parent.name):
                    spy.calls = []
                    payload = tool_payload("PostToolUse", elsewhere, "Write", {"file_path": str(target)})
                    payload["session_id"] = sid
                    LH.handle(payload, regs, spawn=spy)
                    self.assertEqual(spy.calls, calls)
            spy.calls = ["write:drafts/DRAFT-v2.md"]
            for sid in ("s7", "s8"):
                LH.handle({"hook_event_name": "Stop", "session_id": sid, "cwd": str(elsewhere),
                           "stop_hook_active": False, "last_assistant_message": ""}, regs, spawn=spy)
            self.assertEqual(spy.calls, ["write:drafts/DRAFT-v2.md", "stop"])


class RegistryAndProcessTest(unittest.TestCase):
    def test_a_line_that_does_not_load_is_skipped_and_reported(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            reg = Path(root) / "registry2"
            reg.write_text(f"{root}/nowhere\n{ws}\n", encoding="utf-8")
            good, bad = LH.registry(str(reg))
            self.assertEqual(([str(w) for w, _ in good], bad), ([str(ws.resolve())], [f"{root}/nowhere"]))
            self.assertEqual(LH.registry(str(Path(root) / "absent")), ([], []))

    def test_the_script_reads_stdin_and_prints_the_decision(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            env = dict(os.environ, AWT_LOOP_REGISTRY=str(Path(root) / "registry"))
            r = subprocess.run([sys.executable, str(HOOKS / "loop_hook.py")], input=json.dumps(prompt_payload(repo)),
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("〔循环〕", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])
            r = subprocess.run([sys.executable, str(HOOKS / "loop_hook.py")], input="not json", capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout), (0, ""))


class BrokenNotchModuleTest(unittest.TestCase):
    """The notch module is optional. When it cannot even be imported, the hook still guards human/ and still asks for
    the explanation block, and `loop` still starts; the failure is recorded. The hook command ends in `|| true`, so a
    hook that crashed on import would look exactly like a hook that allowed the write."""

    def copy_with_broken_notch(self, root):
        import shutil
        wl = Path(root) / "wl"
        skip = shutil.ignore_patterns("__pycache__")
        shutil.copytree(HOOKS, wl / "hooks", ignore=skip)
        shutil.copytree(HOOKS.parent / "engine" / "loop", wl / "engine" / "loop", ignore=skip)
        (wl / "engine" / "loop" / "lintel.py").write_text("raise ImportError('broken on purpose')\n", encoding="utf-8")
        return wl

    def run_hook(self, wl, root, payload):
        env = dict(os.environ, AWT_LOOP_REGISTRY=str(Path(root) / "registry"))
        return subprocess.run([sys.executable, str(wl / "hooks" / "loop_hook.py")], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_the_guard_still_refuses_a_write_into_human(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            wl = self.copy_with_broken_notch(root)
            r = self.run_hook(wl, root, tool_payload("PreToolUse", repo, "Write",
                                                     {"file_path": str(ws / "human" / "comments.jsonl"), "content": "x"}))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout or "{}").get("hookSpecificOutput", {}).get("permissionDecision"), "deny",
                             r.stderr)

    def test_a_prompt_still_gets_the_reminder_and_the_failure_is_recorded(self):
        with TempDir() as root:
            repo, ws, _ = setup(root)
            wl = self.copy_with_broken_notch(root)
            r = self.run_hook(wl, root, prompt_payload(repo))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("〔循环〕", json.loads(r.stdout or "{}").get("hookSpecificOutput", {}).get("additionalContext", ""),
                          r.stderr)
            errors = [e["detail"] for e in HL.load(ws).get("events", []) if e["kind"] == "hook_error"]
            self.assertTrue(any("broken on purpose" in d for d in errors), errors)

    def test_the_command_line_still_starts(self):
        with TempDir() as root:
            wl = self.copy_with_broken_notch(root)
            r = subprocess.run([sys.executable, "-m", "loop", "update", "--help"], cwd=str(wl / "engine"),
                               capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=str(wl / "engine")))
            self.assertEqual(r.returncode, 0, r.stderr)


class LogCapTest(unittest.TestCase):
    """2026-10-08：cache/ 下的日志没有上限（一份稿子的刘海日志 4.9 MB）。过了上限，下一次启动前挪成 <名>.1。"""

    def test_a_log_past_the_cap_moves_aside_before_the_next_run_appends(self):
        with TempDir() as root:
            ws = Path(root) / "ws"
            (ws / "cache").mkdir(parents=True)
            log = ws / "cache" / "lintel.log"
            log.write_bytes(b"x" * (LH.LOG_CAP + 1))
            with LH.open_log(ws, "lintel.log") as fh:
                fh.write("new\n")
            self.assertEqual(log.read_text(), "new\n")
            self.assertEqual((ws / "cache" / "lintel.log.1").stat().st_size, LH.LOG_CAP + 1)
            with LH.open_log(ws, "lintel.log") as fh:
                fh.write("more\n")
            self.assertEqual(log.read_text(), "new\nmore\n", "under the cap it appends")

    def test_every_detached_run_opens_its_log_through_the_cap(self):
        from unittest import mock
        with TempDir() as root:
            ws = Path(root) / "ws"
            (ws / "cache").mkdir(parents=True)
            for name, spawn in (("lintel.log", lambda: LH.spawn_card(ws)), ("lintel.log", lambda: LH.spawn_producer(ws)),
                                ("update.log", lambda: LH.spawn_update(ws, "test"))):
                (ws / "cache" / name).write_bytes(b"x" * (LH.LOG_CAP + 1))
                with mock.patch.object(LH.subprocess, "Popen"):
                    spawn()
                self.assertEqual((ws / "cache" / name).stat().st_size, 0, f"{name} moved aside before the run")


if __name__ == "__main__":
    unittest.main()


SURVEY = "The survey counted the bridges that had cracked piers in the northern district."
BAD = "The survey, which the county still funds, counted bridges with cracked piers: all in the north."


def stop_payload(cwd, **extra):
    base = {"session_id": "s1", "transcript_path": "/dev/null", "cwd": str(cwd), "hook_event_name": "Stop",
            "stop_hook_active": False, "last_assistant_message": "done"}
    base.update(extra)
    return base


def setup_gated(root, on=True):
    """A draft with a sentence long enough to rewrite, committed, and the rewrite gates switched on (or not)."""
    repo, ws, _ = setup(root)
    draft = Path(repo) / "drafts/DRAFT-v1.md"
    draft.write_text(draft_md("A title", "One sentence. Two sentence.", [SURVEY + " Intro two."]), encoding="utf-8")
    git(repo, "add", "drafts/DRAFT-v1.md")
    git(repo, "commit", "-q", "-m", "v2")
    cfg = C.load(ws)
    cfg["gates"] = {"rewrites": on}
    C.save(ws, cfg)
    regs, _bad = LH.registry(str(Path(root) / "registry"))
    return repo, ws, regs, draft


class RewriteGateTest(unittest.TestCase):
    """A rewrite written by a script in a shell never passes an editor-tool gate; the working tree is read instead,
    after the tool, and the turn does not end while a flagged rewrite is unhandled."""

    def test_a_script_write_is_read_after_the_tool_and_only_once(self):
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root)
            draft.write_text(draft.read_text(encoding="utf-8").replace(SURVEY, BAD), encoding="utf-8")
            out = LH.handle(tool_payload("PostToolUse", repo, "Bash", {"command": "python3 edit.py"}), regs, spawn=Spy())
            ctx = (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")
            self.assertIn("标出", ctx)
            self.assertIn("colon", ctx)
            self.assertIsNone(LH.handle(tool_payload("PostToolUse", repo, "Bash", {"command": "ls"}), regs, spawn=Spy()),
                              "an unchanged draft is not read again")

    def test_the_stop_is_blocked_once_then_the_override_is_recorded(self):
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root)
            draft.write_text(draft.read_text(encoding="utf-8").replace(SURVEY, BAD), encoding="utf-8")
            out = LH.handle(stop_payload(repo), regs, spawn=Spy())
            self.assertEqual((out or {}).get("decision"), "block", out)
            self.assertIn("colon", out["reason"])
            self.assertIsNone(LH.handle(stop_payload(repo, stop_hook_active=True), regs, spawn=Spy()))
            kinds = [e["kind"] for e in HL.load(ws).get("events", [])]
            self.assertIn("stop_gate_overridden", kinds)

    def test_a_missing_reply_field_is_recorded_and_the_working_tree_still_counts(self):
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root)
            draft.write_text(draft.read_text(encoding="utf-8").replace(SURVEY, BAD), encoding="utf-8")
            payload = stop_payload(repo)
            del payload["last_assistant_message"]
            out = LH.handle(payload, regs, spawn=Spy())
            self.assertEqual((out or {}).get("decision"), "block", out)
            errors = [e["detail"] for e in HL.load(ws).get("events", []) if e["kind"] == "hook_error"]
            self.assertTrue(any("last_assistant_message" in d for d in errors), errors)

    def test_a_rewrite_in_the_reply_blocks_and_a_clean_turn_ends(self):
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root)
            out = LH.handle(stop_payload(repo, last_assistant_message="改成：\n```\n" + BAD + "\n```"), regs, spawn=Spy())
            self.assertEqual((out or {}).get("decision"), "block", out)
            self.assertIsNone(LH.handle(stop_payload(repo, last_assistant_message="说明，没有改句。"), regs, spawn=Spy()))

    def test_a_blocked_stop_is_recorded_as_blocked_and_the_override_as_a_stop(self):
        # grill 09-22 #2: the stop used to be recorded before the gate, so the notch ended a turn the gate kept going
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root)
            draft.write_text(draft.read_text(encoding="utf-8").replace(SURVEY, BAD), encoding="utf-8")
            spy = Spy()
            LH.handle(stop_payload(repo), regs, spawn=spy)
            LH.handle(stop_payload(repo, stop_hook_active=True), regs, spawn=spy)
            self.assertEqual(spy.calls, ["stop:blocked", "stop"])

    def test_with_the_gates_off_nothing_is_blocked(self):
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root, on=False)
            draft.write_text(draft.read_text(encoding="utf-8").replace(SURVEY, BAD), encoding="utf-8")
            self.assertIsNone(LH.handle(stop_payload(repo), regs, spawn=Spy()))
            self.assertIsNone(LH.handle(tool_payload("PostToolUse", repo, "Bash", {"command": "x"}), regs, spawn=Spy()))


class BrokenCoverageModuleTest(unittest.TestCase):
    """The rewrite gate imports coverage inside the call. When coverage cannot be imported, the human/ guard still
    refuses, and the Stop gate says it is down rather than letting the turn end as if checked."""

    def copy_with_broken_coverage(self, root):
        import shutil
        wl = Path(root) / "wl"
        skip = shutil.ignore_patterns("__pycache__")
        shutil.copytree(HOOKS, wl / "hooks", ignore=skip)
        shutil.copytree(HOOKS.parent / "engine" / "loop", wl / "engine" / "loop", ignore=skip)
        (wl / "engine" / "loop" / "coverage.py").write_text("raise ImportError('broken on purpose')\n", encoding="utf-8")
        # A Stop starts `loop update` detached; in this copy it exits at once, or it would still be writing into the
        # temporary directory while the test removes it (seen as an intermittent failure under load).
        (wl / "engine" / "loop" / "__main__.py").write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        return wl

    def run_hook(self, wl, root, payload):
        env = dict(os.environ, AWT_LOOP_REGISTRY=str(Path(root) / "registry"), PYTHONDONTWRITEBYTECODE="1")
        return subprocess.run([sys.executable, str(wl / "hooks" / "loop_hook.py")], input=json.dumps(payload),
                              capture_output=True, text=True, env=env)

    def test_the_guard_still_refuses_and_the_stop_gate_says_it_is_down(self):
        with TempDir() as root:
            repo, ws, regs, draft = setup_gated(root)
            wl = self.copy_with_broken_coverage(root)
            r = self.run_hook(wl, root, tool_payload("PreToolUse", repo, "Write",
                                                     {"file_path": str(ws / "human" / "comments.jsonl"), "content": "x"}))
            self.assertEqual(json.loads(r.stdout or "{}").get("hookSpecificOutput", {}).get("permissionDecision"), "deny",
                             r.stderr)
            r = self.run_hook(wl, root, stop_payload(repo))
            out = json.loads(r.stdout or "{}")
            self.assertEqual(out.get("decision"), "block", r.stderr)
            self.assertIn("改句门自己坏了", out.get("reason", ""))


def willow_outlet(root, inbox=True):
    """A wishing-willow rule file and state directory under root, as the env vars that name them."""
    rule = Path(root) / "willow-envelopes.json"
    r = {"tags": ["task-notification"], "prefixes": []}
    if inbox:
        r["inbox"] = 1
    rule.write_text(json.dumps(r), encoding="utf-8")
    state = Path(root) / "willow-state"
    return {"WILLOW_ENVELOPES": str(rule), "WILLOW_STATE_DIR": str(state)}, state


def notes(state):
    d = Path(state) / "inbox"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(d.glob("awt-loop.*.json"))] if d.is_dir() else []


def ctx_of(out):
    return (out or {}).get("hookSpecificOutput", {}).get("additionalContext", "")


class OutletTest(unittest.TestCase):
    """One outlet (spec C2). A wishing-willow that speaks for other sources ("inbox": 1) says what this loop would
    say; the hook leaves it a note and stays quiet. The two UserPromptSubmit hooks run in parallel, so a note written
    during a prompt is not read for it: the first prompt of a session is said here, and `since` tells willow so."""

    def test_a_session_already_noted_is_said_by_willow_not_here(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                first = LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                self.assertIn("〔循环〕", ctx_of(first), "willow cannot have read a note written during this prompt")
                [n] = notes(state)
                self.assertEqual(n["sessions"]["s1"], {"role": "primary", "since": "p1"})
                self.assertIn("〔循环〕", n["full"])
                self.assertEqual(n["always"], LH.coverage_line(ws, C.load(ws)))
                self.assertIsNone(LH.handle(prompt_payload(repo, prompt_id="p2"), regs), "noted: willow says it")
                self.assertIsNone(LH.handle(prompt_payload(repo, prompt_id="p3", prompt="<task-notification>x</task-notification>"), regs))
                self.assertEqual(notes(state)[0]["sessions"]["s1"]["since"], "p1")
            recs = (ws / "human" / "comments.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(recs), 2, "the author's words are still recorded here; the envelope is not")

    def test_without_the_outlet_key_this_hook_speaks_for_itself(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root, inbox=False)
            with mock.patch.dict(os.environ, env):
                for pid in ("p1", "p2"):
                    self.assertIn("〔循环〕", ctx_of(LH.handle(prompt_payload(repo, prompt_id=pid), regs)))
            self.assertEqual(notes(state), [], "no note is left for a willow that would not say it")

    def test_a_history_session_is_noted_as_history(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            other = Path(root) / "other"
            other.mkdir()
            git(other, "init", "-q", "-b", "old-branch")
            git(other, "commit", "-q", "--allow-empty", "-m", "x")
            cfg = C.load(ws)
            cfg["transcripts"]["also"] = [{"git_branch": "old-branch", "cwd_prefix": str(other)}]
            C.save(ws, cfg)
            regs, _ = LH.registry(str(Path(root) / "registry"))
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                self.assertIn("历史来源", ctx_of(LH.handle(prompt_payload(other, prompt_id="p1"), regs)))
                [n] = notes(state)
                self.assertEqual(n["sessions"]["s1"]["role"], "history")
                self.assertIn("历史来源", n["history"])
                self.assertIsNone(LH.handle(prompt_payload(other, prompt_id="p2"), regs))
            self.assertFalse((ws / "human" / "comments.jsonl").exists())

    def test_a_session_that_is_history_for_two_manuscripts_is_noted_in_both_and_each_card_is_rewritten_once(self):
        """2026-10-04: one conversation works on two papers. Each is bound to it as a history source (display only);
        lintel nests a draft in a conversation only when the draft's card lists it (`within`, read from the note). The
        hook stopped at the first matching workspace, so the second never listed the conversation; and a draft with no
        primary session has no resident producer, so nothing rewrote its card after the note changed."""
        import shutil
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            other = Path(root) / "other"
            other.mkdir()
            git(other, "init", "-q", "-b", "old-branch")
            git(other, "commit", "-q", "--allow-empty", "-m", "x")
            cfg = C.load(ws)
            cfg["transcripts"]["also"] = [{"git_branch": "old-branch", "cwd_prefix": str(other)}]
            C.save(ws, cfg)
            ws2 = Path(root) / "ws2"
            shutil.copytree(ws, ws2)
            cfg2 = C.load(ws2)
            cfg2["name"] = "t2"
            C.save(ws2, cfg2)
            reg = Path(root) / "registry"
            reg.write_text(f"{ws}\n{ws2}\n", encoding="utf-8")
            regs, _ = LH.registry(str(reg))
            env, state = willow_outlet(root)
            home = Path(root) / "lintel-home"
            home.mkdir()
            (home / "registry.json").write_text(json.dumps({"producers": {LN.PRODUCER: {}}}), encoding="utf-8")
            cards = []
            with mock.patch.dict(os.environ, {**env, "LOOP_LINTEL_HOME": str(home)}), \
                    mock.patch.object(LH, "spawn_card", cards.append):
                said = ctx_of(LH.handle(prompt_payload(other, prompt_id="p1"), regs))
                self.assertEqual(sorted(n["workspace"] for n in notes(state)), ["t", "t2"])
                self.assertTrue(all(n["sessions"]["s1"]["role"] == "history" for n in notes(state)))
                self.assertIn("「t」", said)
                self.assertIn("「t2」", said)
                self.assertEqual(sorted(Path(c).name for c in cards), ["ws", "ws2"])
                LH.handle(prompt_payload(other, prompt_id="p2"), regs)
                self.assertEqual(len(cards), 2, "the card is rewritten when the session is first noted, not every prompt")

    def test_a_session_named_by_its_id_is_a_history_source_and_its_neighbours_are_not(self):
        """2026-10-04: one conversation works in a checkout and on a branch that other lines share, so a
        directory + branch rule would take those conversations in too. transcripts.history_sessions names the session
        itself; another session in the same directory stays out."""
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            shared = Path(root) / "shared"
            shared.mkdir()
            git(shared, "init", "-q", "-b", "spike")
            git(shared, "commit", "-q", "--allow-empty", "-m", "x")
            cfg = C.load(ws)
            cfg["transcripts"]["history_sessions"] = [{"id": "s1", "note": "shared-checkout conversation"}]
            C.save(ws, cfg)
            reg = Path(root) / "registry"
            reg.write_text(f"{ws}\n", encoding="utf-8")
            regs, _ = LH.registry(str(reg))
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env), mock.patch.object(LH, "spawn_card", lambda ws: None):
                LH.handle(prompt_payload(shared, session_id="s2", prompt_id="p0"), regs)
                self.assertEqual(notes(state), [], "a neighbour in the same checkout is not taken in")
                said = ctx_of(LH.handle(prompt_payload(shared, prompt_id="p1"), regs))
                self.assertEqual([n["sessions"]["s1"]["role"] for n in notes(state)], ["history"])
                self.assertIn("「t」", said)
            self.assertFalse((ws / "human" / "comments.jsonl").exists(), "display only: the author's words are not recorded")

    def test_a_note_whose_line_is_out_of_date_is_corrected_here(self):
        """The coverage line is judged current when it is read (fingerprint and HEAD). If what willow is about to
        say is not what the line reads now (the author edited outside Claude, an update is still running), the hook
        says the line itself, as a correction, and rewrites the note: at worst one extra line, never a stale one."""
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                p = next((state / "inbox").glob("awt-loop.*.json"))
                n = json.loads(p.read_text(encoding="utf-8"))
                n["always"] = "覆盖：都查过了（旧的一行）"
                p.write_text(json.dumps(n, ensure_ascii=False), encoding="utf-8")
                out = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p2"), regs))
                live = LH.coverage_line(ws, C.load(ws))
                self.assertIn("更正", out)
                self.assertIn(live, out)
                self.assertNotIn("〔循环〕", out, "only the line, the block is willow's to say")
                self.assertEqual(notes(state)[0]["always"], live)

    def test_a_commit_refreshes_the_line_before_the_next_prompt(self):
        from unittest import mock
        from loop import coverage as V
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                cfg = C.load(ws)
                V.compute(cfg, ws)
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                before = notes(state)[0]["always"]
                (Path(repo) / "drafts" / "DRAFT-v1.md").write_text(MD + "\nThree sentence.\n", encoding="utf-8")
                git(repo, "commit", "-qam", "v2")
                LH.handle(tool_payload("PostToolUse", repo, "Bash", {"command": "git commit -am v2"}), regs, spawn=Spy())
                after = notes(state)[0]["always"]
                self.assertNotEqual(after, before, "HEAD moved: the line says the summary is not current")
                self.assertEqual(after, LH.coverage_line(ws, cfg))
                self.assertIsNone(LH.handle(prompt_payload(repo, prompt_id="p2"), regs), "no correction needed")

    def test_compute_refreshes_a_note_and_never_starts_one(self):
        from unittest import mock
        from loop import coverage as V
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                cfg = C.load(ws)
                V.compute(cfg, ws)
                self.assertEqual(notes(state), [], "compute does not start a note: only a session does")
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                n = json.loads(next((state / "inbox").glob("awt-loop.*.json")).read_text(encoding="utf-8"))
                n["always"] = "覆盖：旧"
                next((state / "inbox").glob("awt-loop.*.json")).write_text(json.dumps(n, ensure_ascii=False), encoding="utf-8")
                V.compute(cfg, ws)
                self.assertEqual(notes(state)[0]["always"], LH.coverage_line(ws, cfg))
                # `loop coverage` run by hand may name the workspace another way than the registry does. Built here
                # rather than left to the platform: macOS's temporary directory sits behind /var -> /private/var.
                alias = Path(root) / "alias"
                alias.symlink_to(ws, target_is_directory=True)
                V.compute(cfg, alias)
                self.assertIsNone(LH.handle(prompt_payload(repo, prompt_id="p2"), regs),
                                  "the note written through another spelling of the path reads as the hook's line")

    def test_when_the_outlet_breaks_this_hook_speaks_and_says_why(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            from loop import outlet as O
            with mock.patch.dict(os.environ, env), mock.patch.object(O, "enrol", side_effect=RuntimeError("boom")):
                for pid in ("p1", "p2"):
                    self.assertIn("〔循环〕", ctx_of(LH.handle(prompt_payload(repo, prompt_id=pid), regs)))
            events = [e for e in HL.load(ws).get("events", []) if e["kind"] == "hook_error"]
            self.assertTrue(any("许愿柳" in e["detail"] for e in events), events)

    def test_an_update_that_removes_the_summary_also_rewrites_the_note(self):
        from unittest import mock
        from loop import cli as CL
        from loop import coverage as V
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                cfg = C.load(ws)
                V.compute(cfg, ws)
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                with mock.patch.object(V, "compute", side_effect=RuntimeError("boom")):
                    CL._coverage_after_update(ws, cfg)
                self.assertIn("还没有算过", notes(state)[0]["always"], "the note does not outlive the summary it quoted")


HOOKUP_LEDGER = """# 主张清单
阶段：分析

## 主张 C1 合成读数是 12
- 证据：表 1
- 强度：强
- 允许的说法：合成读数

## 待做 N2 合成待做乙
- 类型：分析
- 改变：C1
- 状态：未做

## 待做 N1 合成待做甲
- 类型：出处
- 改变：C1
- 状态：等作者（合成理由）

## 待做 N3 合成待做丙
- 类型：分析
- 改变：C1
- 状态：已做 2026-01-02 合成记录
"""


class OutletTodoTest(unittest.TestCase):
    """The note carries the manuscript's to-do items and a per-workspace switch, for wishing-willow to match its list
    against (spec 2026-10-04 manuscript-todo-hookup, D1 and D4)."""

    def _ledger(self, root, ws, text=HOOKUP_LEDGER, **extra):
        p = Path(root) / "claims.md"
        p.write_text(text, encoding="utf-8")
        cfg = C.load(ws)
        cfg["claims"] = str(p)
        cfg.update(extra)
        C.save(ws, cfg)
        regs, _bad = LH.registry(str(Path(root) / "registry"))  # the registry holds each workspace's config as read
        return p, regs

    def test_the_note_carries_open_and_closed_items_in_ledger_order(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            _p, regs = self._ledger(root, ws)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
            [n] = notes(state)
            self.assertEqual(n["todo"], [
                {"id": "N2", "title": "合成待做乙", "state": "未做", "closed": False},
                {"id": "N1", "title": "合成待做甲", "state": "等作者", "closed": False},
                {"id": "N3", "title": "合成待做丙", "state": "已做", "closed": True}],
                "closed items too: willow must tell closed from not there")
            self.assertNotIn("todo_why", n)
            self.assertIs(n["hookup"], False, "off unless the workspace config turns it on")

    def test_without_a_ledger_todo_is_null_with_a_reason_never_an_empty_list(self):
        from unittest import mock
        with TempDir() as root:
            repo, ws, regs = setup(root)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
            [n] = notes(state)
            self.assertIsNone(n["todo"], "[] would read as every item closed")
            self.assertIn("没登记主张清单", n["todo_why"])

    def test_an_unreadable_ledger_or_a_state_that_cannot_be_computed_is_null_with_a_reason(self):
        from unittest import mock
        from loop import state as S
        with TempDir() as root:
            repo, ws, regs = setup(root)
            p, regs = self._ledger(root, ws)
            p.unlink()
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                [n] = notes(state)
                self.assertIsNone(n["todo"])
                self.assertIn("读不到", n["todo_why"])
                _p, regs = self._ledger(root, ws)
                with mock.patch.object(S, "compute", side_effect=RuntimeError("boom")):
                    LH.handle(prompt_payload(repo, prompt_id="p2"), regs)
                [n] = notes(state)
                self.assertIsNone(n["todo"])
                self.assertIn("算不出", n["todo_why"])

    def test_the_switch_follows_the_config_and_a_refresh_keeps_it_but_rereads_the_items(self):
        from unittest import mock
        from loop import coverage as V
        with TempDir() as root:
            repo, ws, regs = setup(root)
            p, regs = self._ledger(root, ws, hookup=True)
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                self.assertIs(notes(state)[0]["hookup"], True)
                p.write_text(HOOKUP_LEDGER.replace("状态：未做", "状态：已做 2026-01-03 合成记录"), encoding="utf-8")
                V.refresh_outlet(ws, C.load(ws))
                [n] = notes(state)
                self.assertIs(n["hookup"], True, "a refresh keeps the switch the last prompt read")
                self.assertTrue(next(t for t in n["todo"] if t["id"] == "N2")["closed"], "and rereads the items")
                cfg = C.load(ws)
                cfg.pop("hookup")
                C.save(ws, cfg)
                regs, _bad = LH.registry(str(Path(root) / "registry"))
                LH.handle(prompt_payload(repo, prompt_id="p2"), regs)
                self.assertIs(notes(state)[0]["hookup"], False, "taking it out of the config turns it off next prompt")


READY_LEDGER = (HOOKUP_LEDGER.replace("状态：未做", "状态：已做 2026-01-03 合成记录")
                .replace("状态：等作者（合成理由）", "状态：不做 2026-01-03 合成理由"))


class OutletVerdictTest(unittest.TestCase):
    """The note carries the paper's verdict as {"ready": <bool>, "text": <one line>}, for wishing-willow to hold a
    reply that says the paper is done against it. ready is true only where `loop state` exits 0; text is the first part
    of the state line (verdict and stage), not the whole line. Any other shape is reported by willow every turn as
    unreadable, so the shape is asserted exactly. A state that cannot be computed is not ready: no key would read as
    nothing to check."""

    def _ledger(self, root, ws, text=HOOKUP_LEDGER, **extra):
        """The ledger, and the sentence index built as `loop update` would: without it the state says the whole-draft
        scan was not done, which stands in the way of 待作者终审."""
        from loop import history as H
        p, regs = OutletTodoTest._ledger(self, root, ws, text, **extra)
        cfg = C.load(ws)
        vs = H.load_versions(cfg)
        H.assign_ids(vs)
        (Path(ws) / "index" / "sentences.json").write_text(
            json.dumps({"head": git(cfg["repo"], "rev-parse", "HEAD"), "versions": vs}), encoding="utf-8")
        return p, regs

    def assertShape(self, v):
        self.assertIsInstance(v, dict)
        self.assertEqual(set(v), {"ready", "text"}, v)
        self.assertIs(type(v["ready"]), bool, "a real boolean: not null, not the string \"false\"")
        self.assertIsInstance(v["text"], str)
        self.assertTrue(v["text"].strip(), "a non-empty line")
        self.assertNotIn("\n", v["text"])

    def note(self, root, repo, regs, pid="p1"):
        from unittest import mock
        env, state = willow_outlet(root)
        with mock.patch.dict(os.environ, env):
            LH.handle(prompt_payload(repo, prompt_id=pid), regs)
        [n] = notes(state)
        return n, env

    def test_open_items_are_not_ready_and_the_text_is_the_head_of_the_line(self):
        with TempDir() as root:
            repo, ws, regs = setup(root)
            _p, regs = self._ledger(root, ws)
            n, _env = self.note(root, repo, regs)
            self.assertShape(n["verdict"])
            self.assertEqual(n["verdict"], {"ready": False, "text": "论文状态：未就绪（阶段：分析）"})
            self.assertTrue(n["always"].startswith(n["verdict"]["text"] + "——"), "the line's first part, not all of it")
            self.assertEqual(n["label"], "写作循环 · t", "willow names the source by the label")

    def test_ready_only_at_the_author_verdict_and_a_refresh_rereads_it(self):
        from unittest import mock
        from loop import coverage as V
        with TempDir() as root:
            repo, ws, regs = setup(root)
            p, regs = self._ledger(root, ws, text=READY_LEDGER)
            n, env = self.note(root, repo, regs)
            self.assertShape(n["verdict"])
            self.assertEqual(n["verdict"], {"ready": True, "text": "论文状态：待作者终审（阶段：分析）"})
            p.write_text(HOOKUP_LEDGER, encoding="utf-8")
            with mock.patch.dict(os.environ, env):
                V.refresh_outlet(ws, C.load(ws))
                [n] = notes(env["WILLOW_STATE_DIR"])
            self.assertEqual(n["verdict"], {"ready": False, "text": "论文状态：未就绪（阶段：分析）"})

    def test_submitted_is_ready_only_with_nothing_in_the_way(self):
        for text, ready in ((READY_LEDGER, True), (HOOKUP_LEDGER, False)):
            with self.subTest(ready=ready), TempDir() as root:
                repo, ws, regs = setup(root)
                _p, regs = self._ledger(root, ws, text=text.replace("阶段：分析", "阶段：已投稿"))
                n, _env = self.note(root, repo, regs)
                self.assertShape(n["verdict"])
                self.assertEqual(n["verdict"], {"ready": ready, "text": "论文状态：已投稿（阶段：已投稿）"})

    def test_no_ledger_and_a_state_that_cannot_be_computed_are_not_ready(self):
        from unittest import mock
        from loop import state as S
        with TempDir() as root:
            repo, ws, regs = setup(root)
            n, _env = self.note(root, repo, regs)
            self.assertShape(n["verdict"])
            self.assertEqual(n["verdict"], {"ready": False, "text": "论文状态：没登记主张清单"})
            _p, regs = self._ledger(root, ws, text=READY_LEDGER)
            with mock.patch.object(S, "compute", side_effect=RuntimeError("boom")):
                n, _env = self.note(root, repo, regs, pid="p2")
            self.assertShape(n["verdict"])
            self.assertEqual(n["verdict"], {"ready": False, "text": "论文状态：算不出"})

    def test_a_line_that_fails_before_the_state_does_not_leave_the_last_ready_standing(self):
        """The hook reads the state live_line left behind. When the coverage summary fails to load first, the state of
        an earlier call in the same process must not be taken for this one's."""
        from unittest import mock
        from loop import coverage as V
        with TempDir() as root:
            repo, ws, regs = setup(root)
            _p, regs = self._ledger(root, ws, text=READY_LEDGER)
            n, _env = self.note(root, repo, regs)
            self.assertIs(n["verdict"]["ready"], True)
            with mock.patch.object(V, "load_summary", side_effect=RuntimeError("boom")):
                n, _env = self.note(root, repo, regs, pid="p2")
            self.assertShape(n["verdict"])
            self.assertIs(n["verdict"]["ready"], False)


class StateChangeTest(unittest.TestCase):
    """A change in the paper's state is said once, apart from the per-turn line. The line reads the same every turn,
    so a blocker that appeared in it was repeated for a day and never read (09-28: the state had said since one
    commit that a required wording was missing; the agent answered the author only after being asked why). The hook
    says the change itself, not through willow's note: its own output always reaches the model, the note may not be
    read for this prompt."""

    def ws(self, root):
        from test_state import setup as state_setup
        ws, cfg = state_setup(root)
        reg = Path(root) / "registry"
        reg.write_text(f"{ws}\n", encoding="utf-8")
        regs, _ = LH.registry(str(reg))
        return ws, cfg, regs

    def test_a_new_blocker_is_said_once_at_the_next_prompt(self):
        with TempDir() as root:
            ws, cfg, regs = self.ws(root)
            repo = cfg["repo"]
            first = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p1"), regs))
            self.assertIn("论文状态：未就绪", first)
            self.assertNotIn("上一条消息以来", first, "nothing was said before, so nothing changed since")
            ledger = Path(cfg["claims"])
            ledger.write_text(ledger.read_text(encoding="utf-8").replace("do not test whether drivers",
                                                                          "we measured the drivers"), encoding="utf-8")
            second = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p2"), regs))
            self.assertIn("写作循环 · t：上一条消息以来，论文状态有变化——新：缺该有的说法 C1。", second)
            self.assertLess(second.index("上一条消息以来"), second.index("论文状态：未就绪"), "the change comes first")
            third = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p3"), regs))
            self.assertNotIn("上一条消息以来", third, "said once")
            ledger.write_text(ledger.read_text(encoding="utf-8").replace("we measured the drivers",
                                                                          "do not test whether drivers"), encoding="utf-8")
            fourth = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p4"), regs))
            self.assertIn("已解：缺该有的说法 C1", fourth)
            from test_state import CLEAN
            ledger.write_text(CLEAN, encoding="utf-8")
            fifth = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p5"), regs))
            self.assertIn("上一条消息以来，论文状态有变化——论文状态 未就绪 → 待作者终审；已解：没立住 C2、越界 1 句、全称量词没对集合 1 处。", fifth)

    def test_through_willow_the_change_is_still_said_by_this_hook(self):
        from unittest import mock
        with TempDir() as root:
            ws, cfg, regs = self.ws(root)
            repo = cfg["repo"]
            env, state = willow_outlet(root)
            with mock.patch.dict(os.environ, env):
                LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
                self.assertIsNone(LH.handle(prompt_payload(repo, prompt_id="p2"), regs), "noted, unchanged: willow says it")
                ledger = Path(cfg["claims"])
                ledger.write_text(ledger.read_text(encoding="utf-8").replace("- 强度：弱", "- 强度：强"), encoding="utf-8")
                LH.refresh_note(ws, C.load(ws), None)
                out = ctx_of(LH.handle(prompt_payload(repo, prompt_id="p3"), regs))
                self.assertIn("上一条消息以来，论文状态有变化", out)
                self.assertIn("已解：没立住 C2", out)
                self.assertNotIn("更正", out, "the note already reads as the line does; only the change is added")
                self.assertIsNone(LH.handle(prompt_payload(repo, prompt_id="p4"), regs), "said once")

    def test_a_prompt_of_a_session_reading_this_manuscript_as_history_does_not_use_up_the_change(self):
        with TempDir() as root:
            ws, cfg, regs = self.ws(root)
            repo = cfg["repo"]
            LH.handle(prompt_payload(repo, prompt_id="p1"), regs)
            other = Path(root) / "other"
            other.mkdir()
            git(other, "init", "-q", "-b", "old-branch")
            git(other, "commit", "-q", "--allow-empty", "-m", "x")
            c = C.load(ws)
            c["transcripts"]["also"] = [{"git_branch": "old-branch", "cwd_prefix": str(other)}]
            C.save(ws, c)
            regs, _ = LH.registry(str(Path(root) / "registry"))
            ledger = Path(cfg["claims"])
            ledger.write_text(ledger.read_text(encoding="utf-8").replace("do not test whether drivers",
                                                                          "we measured the drivers"), encoding="utf-8")
            hist = ctx_of(LH.handle(prompt_payload(other, session_id="s2", prompt_id="h1"), regs))
            self.assertIn("历史来源", hist)
            self.assertNotIn("上一条消息以来", hist)
            self.assertIn("新：缺该有的说法 C1", ctx_of(LH.handle(prompt_payload(repo, prompt_id="p2"), regs)))
