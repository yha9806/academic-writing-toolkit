#!/usr/bin/env python3
"""Exercise selected plugin export through its public CLI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

SOURCE = Path(__file__).resolve().parents[1]
EXPORT = SOURCE / 'scripts/export-codex-plugin.py'
EIGHT = ('audit', 'export', 'integrate', 'map', 'note', 'read', 'review', 'verify-refs')


class PluginExportTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='awt-plugin-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'space and 文本'
        self.root.mkdir()
        self.output = self.root / 'plugin'

    def command(self, *extra):
        return [sys.executable, str(EXPORT), '--out', str(self.output),
                *[part for name in EIGHT for part in ('--skill', name)], *extra]

    def test_selected_export_preserves_policy_and_verifies_real_helpers(self):
        policies = self.root / 'existing'
        target = policies / 'map'
        (target / 'agents').mkdir(parents=True)
        (target / 'SKILL.md').write_text('---\nname: map\ndescription: Local\nallowed-tools: Read, Glob\n---\nDo not copy this local body.\n')
        (target / 'assets').mkdir()
        (target / 'assets/custom.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        (target / 'agents/openai.yaml').write_text('interface:\n  display_name: "My map"\n  icon_small: ./assets/custom.svg\n  icon_large: ./assets/custom.svg\npolicy:\n  allow_implicit_invocation: false\n')
        result = subprocess.run(self.command('--preserve-policy-from', str(policies)), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['skills'], list(EIGHT))
        self.assertEqual(report['helperChecks'], 'passed')
        self.assertEqual(sorted(p.name for p in (self.output / 'skills').iterdir()), list(EIGHT))
        manifest = json.loads((self.output / '.codex-plugin/plugin.json').read_text())
        self.assertEqual(manifest['name'], 'academic-writing-toolkit')
        self.assertEqual(manifest['skills'], './skills/')
        skill = self.output / 'skills/map/SKILL.md'
        front = yaml.safe_load(skill.read_text().split('---', 2)[1])
        self.assertEqual(front['allowed-tools'], 'Read, Glob')
        self.assertNotIn('Do not copy this local body.', skill.read_text())
        self.assertEqual((self.output / 'skills/map/agents/openai.yaml').read_bytes(), (target / 'agents/openai.yaml').read_bytes())
        self.assertEqual((self.output / 'skills/map/assets/custom.svg').read_bytes(), (target / 'assets/custom.svg').read_bytes())
        before = skill.stat().st_mtime_ns
        repeated = subprocess.run(self.command('--preserve-policy-from', str(policies)), capture_output=True, text=True)
        self.assertEqual(repeated.returncode, 0, repeated.stderr)
        self.assertEqual(json.loads(repeated.stdout)['status'], 'unchanged')
        self.assertEqual(skill.stat().st_mtime_ns, before)
        skill.write_text(skill.read_text() + '\nKeep this edit.\n')
        refused = subprocess.run(self.command('--preserve-policy-from', str(policies)), capture_output=True, text=True)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn('Keep this edit.', skill.read_text())

    def test_invalid_selection_does_not_create_output(self):
        result = subprocess.run(self.command('--skill', 'unknown'), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('invalid choice', result.stderr)
        self.assertFalse(self.output.exists())

    def test_foreign_output_is_preserved(self):
        self.output.mkdir()
        keep = self.output / 'manuscript.md'
        keep.write_text('Keep this manuscript.')
        result = subprocess.run(self.command(), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Output exists', result.stderr)
        self.assertEqual(keep.read_text(), 'Keep this manuscript.')
        self.assertEqual(list(self.output.iterdir()), [keep])

    def test_source_directory_cannot_be_reached_through_a_linked_parent(self):
        if sys.platform == 'win32':
            self.skipTest('Creating directory symlinks may need Windows privileges')
        link = self.root / 'source-link'
        link.symlink_to(SOURCE / 'scripts', target_is_directory=True)
        result = subprocess.run([sys.executable, str(EXPORT), '--out', str(link / 'plugin')], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('must not replace source directories', result.stderr)

    def test_invalid_invocation_metadata_is_rejected(self):
        source = self.root / 'policies/map'
        (source / 'agents').mkdir(parents=True)
        (source / 'SKILL.md').write_text('---\nname: map\ndescription: Map\n---\nLocal\n')
        (source / 'agents/openai.yaml').write_text('policy:\n  allow_implicit_invocation: sometimes\n')
        result = subprocess.run(self.command('--preserve-policy-from', str(source.parent)), capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('policy must be boolean', result.stderr)
        self.assertFalse(self.output.exists())

    def test_invalid_ui_asset_does_not_create_output(self):
        source = self.root / 'policies/map'
        (source / 'agents').mkdir(parents=True)
        (source / 'SKILL.md').write_text('---\nname: map\ndescription: Map\n---\nLocal\n')
        outside = source.parent / 'outside.svg'
        outside.write_text('<svg/>')
        for icon in ('./assets/missing.svg', '../outside.svg', str(outside.resolve()), './SKILL.md'):
            with self.subTest(icon=icon):
                (source / 'agents/openai.yaml').write_text(yaml.safe_dump({'interface': {'icon_small': icon}}))
                result = subprocess.run(self.command('--preserve-policy-from', str(source.parent)), capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('UI asset', result.stderr)
                self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
