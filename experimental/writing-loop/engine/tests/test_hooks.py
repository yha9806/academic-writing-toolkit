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
