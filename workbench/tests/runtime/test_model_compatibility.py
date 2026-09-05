"""Check the compatibility tool's dry-run and fixed-fixture boundaries."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from test_providers import envelope, server_fixture


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/check-model-compatibility.py"
spec = importlib.util.spec_from_file_location("model_compatibility", SCRIPT)
compatibility = importlib.util.module_from_spec(spec)
with patch.object(sys, "path", sys.path[:]):
    spec.loader.exec_module(compatibility)


class CompatibilityToolTests(unittest.TestCase):
    def invoke(self, arguments):
        output = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), *arguments]), redirect_stdout(output):
            code = compatibility.main()
        return code, json.loads(output.getvalue()) if output.getvalue() else None

    def test_default_dry_run_never_invokes_a_model(self):
        with patch.object(compatibility, "analyse_document") as analyse:
            code, report = self.invoke([])
        analyse.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(report["mode"], "dry_run")
        self.assertEqual(report["planned_requests"], len(report["results"]))
        self.assertTrue(all(row["status"] == "not_run" for row in report["results"]))
        self.assertFalse(report["writing_effect_proven"])

    def test_credentials_in_profiles_and_existing_reports_stop_before_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory) / "profiles.json"
            profile.write_text(json.dumps({"schema_version": 1, "profiles": [
                {"name": "fixture", "provider": "ollama", "model": "fixture", "api_key": "fixture-secret"}
            ]}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "credentials"):
                compatibility.read_profiles(profile)
            report = Path(directory) / "existing.json"
            report.write_text("preserve this report", encoding="utf-8")
            with patch.object(compatibility, "analyse_document") as analyse, redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    self.invoke(["--live", "--output", str(report)])
            self.assertEqual(caught.exception.code, 2)
            analyse.assert_not_called()
            self.assertEqual(report.read_text(encoding="utf-8"), "preserve this report")

    def test_live_flag_uses_only_the_fixed_fixture_and_restores_routing(self):
        with tempfile.TemporaryDirectory() as directory, server_fixture(envelope("chat-completions")) as (url, requests):
            profile = Path(directory) / "profiles.json"
            profile.write_text(json.dumps({"schema_version": 1, "profiles": [
                {"name": "local-fixture", "provider": "ollama", "model": "fixture", "base_url": url,
                 "api_key_env": "ABSENT_COMPATIBILITY_TEST_KEY"}
            ]}), encoding="utf-8")
            with patch.dict(os.environ, {"AWT_PROVIDER": "codex", "AWT_MODEL": "previous-model"}):
                code, report = self.invoke(["--profiles", str(profile), "--live", "--all-workflows"])
                self.assertEqual(os.environ["AWT_PROVIDER"], "codex")
                self.assertEqual(os.environ["AWT_MODEL"], "previous-model")
            self.assertEqual(code, 0)
            self.assertEqual(len(requests), 5)
            self.assertEqual(report["planned_requests"], 5)
            self.assertFalse(report["writing_effect_proven"])
            self.assertTrue(all(row["status"] == "output_contract_passed" for row in report["results"]))
            self.assertTrue(all(row["source_unchanged"] for row in report["results"]))
            for _, payload, headers in requests:
                self.assertIn(compatibility.FIXTURE.decode(), payload["messages"][1]["content"])
                self.assertNotIn("Authorization", headers)


if __name__ == "__main__":
    unittest.main()
