#!/usr/bin/env python3
"""Source installer regression tests. All writes use temporary directories."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

SPEC = importlib.util.spec_from_file_location("awt_installer", Path(__file__).with_name("install-codex-skills.py"))
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        installer.build_guards(installer.SOURCE)
        installer.check_runtime(sys.executable)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="awt-global-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve() / "user space 文本"
        self.root.mkdir()
        self.dest = self.root / "skills"
        self.python = Path(sys.executable).absolute()

    def install(self, replace=False, smoke=False):
        # Compilation is exercised once in setUpClass. Transaction tests
        # isolate disk behavior; separate tests run every real installed helper.
        with patch.object(installer, "build_guards"), patch.object(installer, "smoke", wraps=installer.smoke if smoke else None):
            return installer.install(installer.SOURCE, self.dest, self.python, replace)

    def test_fresh_install_runs_bundled_helpers_from_unrelated_directory(self):
        result = self.install(smoke=True)
        self.assertEqual(result["status"], "installed")
        self.assertEqual(sorted(p.name for p in self.dest.iterdir()), sorted(installer.NAMES))
        previous = os.getcwd()
        try:
            os.chdir(self.root)
            installer.verify(self.dest, installer.read_receipt(installer.state_dir(self.dest)))
        finally:
            os.chdir(previous)
        for name in installer.NAMES:
            text = (self.dest / name / "SKILL.md").read_text(encoding="utf-8")
            front = yaml.safe_load(text.split("---", 2)[1])
            self.assertEqual(front["name"], name)
            self.assertNotIn("disable-model-invocation", front)
        policy = yaml.safe_load((self.dest / "export/agents/openai.yaml").read_text(encoding="utf-8"))
        self.assertIs(policy["policy"]["allow_implicit_invocation"], False)

    def test_update_preserves_old_bytes_ui_assets_and_other_skills(self):
        installer.write_text(self.dest / "audit/SKILL.md", "Original locally installed audit")
        installer.write_text(self.dest / "audit/agents/openai.yaml", 'interface:\n  display_name: "My audit"\npolicy:\n  allow_implicit_invocation: false\n')
        installer.write_text(self.dest / "audit/assets/icon.svg", "<svg/>")
        installer.write_text(self.dest / "export/agents/openai.yaml", 'interface:\n  display_name: "Export UI"\ndependencies:\n  tools: []\npolicy:\n  allow_implicit_invocation: false\n')
        installer.write_text(self.dest / "another-skill/SKILL.md", "Unrelated personal skill")
        before = installer.snapshot(self.dest)
        result = self.install(replace=True)
        backup = Path(result["backup"])
        for name in ("audit", "export"):
            self.assertEqual(installer.manifest(backup / name), before[name])
        self.assertEqual((self.dest / "another-skill/SKILL.md").read_text(), "Unrelated personal skill")
        self.assertEqual((self.dest / "audit/assets/icon.svg").read_text(), "<svg/>")
        audit_ui = yaml.safe_load((self.dest / "audit/agents/openai.yaml").read_text())
        self.assertEqual(audit_ui["interface"]["display_name"], "My audit")
        self.assertFalse(audit_ui["policy"]["allow_implicit_invocation"])
        export_ui = yaml.safe_load((self.dest / "export/agents/openai.yaml").read_text())
        self.assertEqual(export_ui["interface"]["display_name"], "Export UI")
        self.assertEqual(export_ui["dependencies"], {"tools": []})

    def test_unmanaged_collision_is_refused_before_any_replacement(self):
        installer.write_text(self.dest / "audit/SKILL.md", "A different audit skill")
        before = installer.snapshot(self.dest)
        with self.assertRaisesRegex(installer.InstallError, "replace-existing"):
            self.install()
        self.assertEqual(installer.snapshot(self.dest), before)

    def test_repeat_install_is_unchanged_and_local_edits_need_explicit_replacement(self):
        result = self.install()
        receipt = Path(result["receipt"]).read_bytes()
        file = self.dest / "note/SKILL.md"
        original_stat = file.stat().st_mtime_ns
        again = self.install()
        self.assertEqual(again["status"], "unchanged")
        self.assertEqual(file.stat().st_mtime_ns, original_stat)
        self.assertEqual(Path(result["receipt"]).read_bytes(), receipt)
        with file.open("a", encoding="utf-8") as handle:
            handle.write("\nA personal change.\n")
        before = installer.snapshot(self.dest)
        with self.assertRaisesRegex(installer.InstallError, "replace-existing"):
            self.install()
        updated = self.install(replace=True)
        self.assertEqual(installer.manifest(Path(updated["backup"]) / "note"), before["note"])
        self.assertEqual((Path(updated["backup"]).parent / "previous-installation.json").read_bytes(), receipt)

    def test_mid_promotion_failure_rolls_back_all_nine_and_keeps_previous_receipt(self):
        result = self.install()
        installer.write_text(self.dest / "note/extra.txt", "Keep this local file")
        before = installer.snapshot(self.dest)
        old_receipt = Path(result["receipt"]).read_bytes()
        original = Path.rename

        def fail_midway(path, target):
            if path.parent.name == "staged" and path.name == "map":
                raise OSError("simulated write failure during promotion")
            return original(path, target)

        with patch.object(Path, "rename", fail_midway):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                self.install(replace=True)
        self.assertEqual(installer.snapshot(self.dest), before)
        self.assertEqual(Path(result["receipt"]).read_bytes(), old_receipt)
        self.assertFalse((installer.state_dir(self.dest) / "install.lock").exists())

    def test_late_receipt_failure_also_rolls_back(self):
        result = self.install()
        installer.write_text(self.dest / "note/extra.txt", "Preserve")
        before = installer.snapshot(self.dest)
        with patch.object(installer.os, "replace", side_effect=OSError("receipt write failed")):
            with self.assertRaisesRegex(OSError, "receipt write failed"):
                self.install(replace=True)
        self.assertEqual(installer.snapshot(self.dest), before)
        installer.read_receipt(installer.state_dir(self.dest))
        self.assertTrue(Path(result["receipt"]).is_file())

    def test_concurrent_install_is_refused_without_touching_skills(self):
        with installer.install_lock(installer.state_dir(self.dest)):
            with self.assertRaisesRegex(installer.InstallError, "Another install"):
                self.install()
        self.assertFalse(self.dest.exists())

    def test_failed_build_and_missing_runtime_leave_existing_skills_intact(self):
        installer.write_text(self.dest / "audit/SKILL.md", "Keep old content")
        before = installer.snapshot(self.dest)
        for function in ("build_guards", "check_runtime"):
            with self.subTest(function=function), patch.object(installer, function, side_effect=installer.InstallError("preflight failed")):
                with self.assertRaisesRegex(installer.InstallError, "preflight failed"):
                    installer.install(installer.SOURCE, self.dest, self.python, True)
            self.assertEqual(installer.snapshot(self.dest), before)

    def test_failed_staged_helper_check_leaves_existing_skills_intact(self):
        installer.write_text(self.dest / "audit/SKILL.md", "Keep old content")
        before = installer.snapshot(self.dest)
        with patch.object(installer, "build_guards"), patch.object(installer, "smoke", side_effect=installer.InstallError("helper failed")):
            with self.assertRaisesRegex(installer.InstallError, "helper failed"):
                installer.install(installer.SOURCE, self.dest, self.python, True)
        self.assertEqual(installer.snapshot(self.dest), before)

    def test_node_preflight_reports_missing_executable_and_build_dependencies(self):
        with patch.object(installer.shutil, "which", return_value=None):
            with self.assertRaisesRegex(installer.InstallError, "Node.js"):
                installer.build_guards(installer.SOURCE)
        with self.assertRaisesRegex(installer.InstallError, "npm ci"):
            installer.build_guards(self.root)

    def test_dry_run_writes_nothing_even_with_install_deps(self):
        before = sorted(self.root.iterdir())
        result = subprocess.run([sys.executable, str(installer.SOURCE / "scripts/install-codex-skills.py"),
                                 "--dest", str(self.dest), "--dry-run", "--install-deps"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)["skills"]), 9)
        self.assertEqual(sorted(self.root.iterdir()), before)

    def test_linked_or_junction_skill_is_refused_without_touching_target(self):
        actual = self.root / "shared-plugin"
        installer.write_text(actual / "SKILL.md", "External plugin must not change")
        self.dest.mkdir()
        link = self.dest / "audit"
        if os.name == "nt":
            # Native PowerShell creates an ordinary NTFS junction without
            # requiring Developer Mode or exposing paths to shell expansion.
            env = dict(os.environ, AWT_TEST_LINK=str(link), AWT_TEST_TARGET=str(actual))
            subprocess.run(["powershell", "-NoProfile", "-Command", "New-Item -ItemType Junction -Path $env:AWT_TEST_LINK -Target $env:AWT_TEST_TARGET | Out-Null"], env=env, check=True)
        else:
            link.symlink_to(actual, target_is_directory=True)
        self.addCleanup(lambda: os.rmdir(link) if os.name == "nt" else link.unlink())
        with self.assertRaisesRegex(installer.InstallError, "symlink/junction"):
            self.install(replace=True)
        self.assertEqual((actual / "SKILL.md").read_text(), "External plugin must not change")

    @unittest.skipIf(os.name == "nt", "symlink privileges are not required by Windows installer")
    def test_dangling_link_is_also_refused(self):
        self.dest.mkdir()
        link = self.dest / "audit"
        link.symlink_to(self.root / "absent", target_is_directory=True)
        with self.assertRaisesRegex(installer.InstallError, "symlink/junction"):
            self.install(replace=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
