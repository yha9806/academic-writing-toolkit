from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import awt
from awt.mvp import (
    MAX_AGENT_INPUT_TOKENS,
    MvpApplication,
    MvpError,
    SessionStore,
    WORKFLOWS,
    _codex_binary,
    _is_allowed_host_header,
    _is_allowed_origin_header,
    _is_loopback_host,
    analyse_document,
    build_agent_prompt,
)
from awt.workflow_io import WorkflowAuthorityError, run_workflow


SOURCE = b"The conclusion proves universal effectiveness.\n"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def empty_runner(_text: str, _workflow: str, _purpose: str) -> dict:
    return {
        "status": "pass",
        "summary": "No issue in this engineering fixture.",
        "issues": [],
        "evidence_boundaries": [],
        "required_materials": [],
        "limitations": ["Engineering fixture; not writing-effect evidence."],
    }


def replacement_runner(text: str, _workflow: str, _purpose: str) -> dict:
    original = SOURCE.decode().strip()
    if original not in text:
        raise AssertionError("source missing from model context")
    return {
        "status": "warn",
        "summary": "One overclaim needs author review.",
        "issues": [
            {
                "title": "Universal claim exceeds the reported material",
                "severity": "high",
                "verification_status": "manuscript_reported_only",
                "verification_check": {
                    "claim_dimension": "manuscript_text_only",
                    "kind": "manuscript_only",
                    "result": "not_checked",
                    "note": "Only the manuscript statement was inspected.",
                },
                "evidence": original,
                "source_refs": ["manuscript"],
                "evidence_trace": [
                    {
                        "source_ref": "manuscript",
                        "locator": "Conclusion sentence",
                        "relationship": "supports",
                        "note": "The sentence makes a universal claim.",
                    }
                ],
                "explanation": "No supplied material supports universality.",
                "recommended_action": "Ask the author to narrow or add evidence.",
                "action_options": [
                    {
                        "option_id": "narrow_claim",
                        "label": "Narrow now",
                        "action": "Limit the wording to the observed setting.",
                        "tradeoff": "Safer but less general.",
                        "canonical": False,
                    }
                ],
                "replacement": {
                    "original_text": original,
                    "replacement_text": (
                        "The reported material supports effectiveness in this setting."
                    ),
                    "rationale": "Match wording to the supplied evidence.",
                },
            }
        ],
        "evidence_boundaries": ["Only manuscript text was inspected."],
        "required_materials": ["Comparative evidence for a broader claim."],
        "limitations": ["Engineering fixture; not writing-effect evidence."],
    }


class LeanRuntimeTests(unittest.TestCase):
    def test_release_versions_align_across_workbench_plugin_and_app(self):
        repository_root = Path(__file__).resolve().parents[2]
        plugin = json.loads(
            (
                repository_root
                / "plugins/academic-writing-toolkit/.codex-plugin/plugin.json"
            ).read_text(encoding="utf-8")
        )
        app = json.loads(
            (
                repository_root
                / "apps/chatgpt-academic-writing-toolkit/package.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(plugin["version"], app["version"])
        self.assertEqual(
            awt.__version__,
            app["version"].replace("-rc.", "rc"),
        )

    def test_cli_version_check_and_loopback_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            fake_codex = Path(temporary) / "codex"
            fake_codex.write_text(
                """#!/bin/sh
case "$*" in
  "--version") echo "codex 0.test" ;;
  "login status") echo "Logged in using test fixture" ;;
  "exec --help")
    echo "--ephemeral --ignore-rules --ignore-user-config"
    echo "--output-last-message --output-schema --sandbox"
    echo "--skip-git-repo-check"
    ;;
  *) exit 2 ;;
esac
""",
                encoding="utf-8",
            )
            fake_codex.chmod(0o700)
            environment = {
                **os.environ,
                "AWT_CODEX_BIN": str(fake_codex),
                "AWT_SESSION_DIR": str(Path(temporary) / "sessions"),
            }
            version = subprocess.run(
                [sys.executable, "-m", "awt.mvp", "--version"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(version.returncode, 0)
            self.assertEqual(version.stdout.strip(), "mvp.py 0.5.0")
            check = subprocess.run(
                [sys.executable, "-m", "awt.mvp", "--check"],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(check.returncode, 0)
            self.assertIn("Local preflight: ready", check.stdout)
            self.assertIn("no model request was made", check.stdout)
            self.assertIn("Codex version: codex 0.test", check.stdout)
            remote = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "awt.mvp",
                    "--host",
                    "0.0.0.0",
                    "--port",
                    "0",
                ],
                text=True,
                capture_output=True,
                check=False,
                env=environment,
            )
            self.assertEqual(remote.returncode, 2)
            self.assertIn("only accepts a local loopback host", remote.stderr)
        self.assertTrue(_is_loopback_host("127.0.0.1"))
        self.assertTrue(_is_loopback_host("localhost"))
        self.assertFalse(_is_loopback_host("0.0.0.0"))
        self.assertTrue(_is_allowed_host_header("127.0.0.1:8784", 8784))
        self.assertTrue(_is_allowed_host_header("localhost:8784", 8784))
        self.assertFalse(_is_allowed_host_header("attacker.example:8784", 8784))
        self.assertFalse(_is_allowed_host_header("127.0.0.1:9999", 8784))
        self.assertTrue(
            _is_allowed_origin_header("http://127.0.0.1:8784", 8784)
        )
        self.assertFalse(
            _is_allowed_origin_header("https://attacker.example", 8784)
        )

    def test_codex_runner_must_be_executable(self):
        with tempfile.TemporaryDirectory() as temporary:
            runner = Path(temporary) / "codex"
            runner.write_text("#!/bin/sh\n", encoding="utf-8")
            runner.chmod(0o600)
            with patch.dict(os.environ, {"AWT_CODEX_BIN": str(runner)}):
                with self.assertRaisesRegex(MvpError, "不可执行"):
                    _codex_binary()

    def test_five_workflows_use_lean_prompt_and_keep_source_read_only(self):
        for workflow_id in WORKFLOWS:
            with self.subTest(workflow_id=workflow_id):
                result = analyse_document(
                    SOURCE,
                    "paper.md",
                    workflow_id,
                    "preprint",
                    runner=empty_runner,
                )
                profile = result["runtime_instruction_profile"]
                self.assertTrue(result["source_unchanged"])
                self.assertFalse(result["write_performed"])
                self.assertEqual(profile["contract"], "lean-runtime-v1")
                self.assertFalse(profile["full_skill_injected"])
                self.assertLessEqual(
                    profile["prompt_plus_schema_estimate"]["tokens"],
                    MAX_AGENT_INPUT_TOKENS,
                )

    def test_prompt_does_not_embed_repository_skill(self):
        for workflow_id in WORKFLOWS:
            with self.subTest(workflow_id=workflow_id):
                prompt, profile = build_agent_prompt(
                    "<manuscript>Public-safe fixture.</manuscript>",
                    workflow_id,
                    "camera_ready",
                )
                self.assertIn("<workflow-card>", prompt)
                self.assertNotIn("AWT skill instructions", prompt)
                self.assertNotIn("<skill>", prompt)
                self.assertFalse(profile["full_skill_injected"])

    def test_oversized_non_bounded_request_stops_before_runner(self):
        calls = []

        def runner(*_args):
            calls.append(True)
            return empty_runner("", "", "")

        oversized = ("A bounded manuscript sentence. " * 12_000).encode()
        with self.assertRaisesRegex(MvpError, "超过 Lean Runtime"):
            analyse_document(
                oversized,
                "paper.md",
                "manuscript-reframe",
                "preprint",
                runner=runner,
            )
        self.assertEqual(calls, [])

    def test_large_argument_governance_uses_bounded_parallel_json_summary(self):
        source = (
            "# Results\n"
            "Mode A reports d=-0.157; Mode B reports d=+0.097, "
            "with 5/10 models sign-stable.\n"
            + ("Background context without a result anchor.\n" * 5_000)
        ).encode()
        evidence_value = {
            "mode_A": {
                "d_pooled": -0.157,
                "n_models_negative": 7,
                "n_models_total": 10,
                "per_model_d": {
                    "m1": 0.1,
                    "m2": -0.2,
                    "m3": -0.3,
                    "m4": 0.4,
                },
            },
            "mode_B": {
                "d_pooled": 0.097,
                "n_models_negative": 2,
                "n_models_total": 10,
                "per_model_d": {
                    "m1": 0.2,
                    "m2": 0.3,
                    "m3": -0.4,
                    "m4": 0.5,
                },
            },
        }
        evidence = json.dumps(evidence_value, indent=2).encode()
        captured = []
        with tempfile.TemporaryDirectory() as temporary:
            application = MvpApplication(
                runner=lambda text, *_args: (
                    captured.append(text) or empty_runner("", "", "")
                ),
                store=SessionStore(Path(temporary) / "sessions"),
            )
            analysed = application.analyse(
                {
                    "filename": "paper.md",
                    "content_base64": base64.b64encode(source).decode(),
                    "workflow_id": "argument-governance",
                    "manuscript_purpose": "preprint",
                    "author_goal": (
                        "Check Mode A and Mode B claim-evidence alignment."
                    ),
                    "evidence_files": [
                        {
                            "filename": "results.json",
                            "content_base64": base64.b64encode(evidence).decode(),
                        }
                    ],
                }
            )
            self.assertEqual(analysed["context_route"], "bounded_preflight")
            self.assertEqual(
                analysed["context_pack_manifest"]["workflow_scope"],
                "claim_evidence_alignment_only",
            )
            self.assertIn("complete argument hierarchy", captured[0])
            self.assertLessEqual(
                analysed["runtime_instruction_profile"]["prompt_plus_schema_estimate"][
                    "tokens"
                ],
                MAX_AGENT_INPUT_TOKENS,
            )
            inventory = {
                item["filename"]: item
                for item in analysed["deterministic_preflight"]["inventory"]
            }
            parallel = inventory["results.json"]["structure"]["parallel_object_summary"]
            self.assertEqual(parallel["branches"], ["mode_A", "mode_B"])
            scalars = {
                item["field"]: item["values"]
                for item in parallel["shared_scalar_values"]
            }
            self.assertEqual(
                scalars["d_pooled"],
                {"mode_A": -0.157, "mode_B": 0.097},
            )
            scalar_maps = {
                item["field"]: item["values"] for item in parallel["shared_scalar_maps"]
            }
            self.assertEqual(
                scalar_maps["per_model_d"]["mode_B"]["m3"],
                -0.4,
            )
            restored = MvpApplication(
                runner=lambda *_args: self.fail("restore reran the model"),
                store=SessionStore(Path(temporary) / "sessions"),
            ).restore({"session_id": analysed["session_id"]})
            self.assertEqual(
                restored["context_pack_manifest"],
                analysed["context_pack_manifest"],
            )

    def test_version_one_bounded_session_remains_restorable(self):
        source = (
            "# Findings\n"
            "The reported evaluation score was 72.4 across 18 clusters.\n"
            + ("Background context without a result anchor.\n" * 5_000)
        ).encode()
        evidence = (
            "metric,value,clusters\n"
            "evaluation_score,72.4,18\n" + ("unrelated_measure,0.1,3\n" * 5_000)
        ).encode()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sessions"
            application = MvpApplication(
                runner=empty_runner,
                store=SessionStore(root),
            )
            with patch("awt.context_pack.ALGORITHM_VERSION", 1):
                analysed = application.analyse(
                    {
                        "filename": "paper.md",
                        "content_base64": base64.b64encode(source).decode(),
                        "workflow_id": "audit",
                        "manuscript_purpose": "preprint",
                        "evidence_files": [
                            {
                                "filename": "results.csv",
                                "content_base64": base64.b64encode(evidence).decode(),
                            }
                        ],
                    }
                )
            self.assertEqual(
                analysed["context_pack_manifest"]["algorithm"]["version"], 1
            )
            restored = MvpApplication(
                runner=lambda *_args: self.fail("restore reran the model"),
                store=SessionStore(root),
            ).restore({"session_id": analysed["session_id"]})
            self.assertEqual(
                restored["context_pack_manifest"]["algorithm"]["version"], 1
            )

    def test_restart_preserves_analysis_and_explicit_apply_copy(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "sessions"
            application = MvpApplication(
                runner=replacement_runner,
                store=SessionStore(root),
            )
            analysis = application.analyse(
                {
                    "filename": "paper.md",
                    "content_base64": base64.b64encode(SOURCE).decode(),
                    "workflow_id": "self-review",
                    "manuscript_purpose": "preprint",
                }
            )
            issue = analysis["result"]["issues"][0]
            decisions = [
                {
                    "issue_id": issue["issue_id"],
                    "decision": "accept",
                    "reason": "Synthetic runtime check.",
                    "modified_text": None,
                }
            ]
            saved = application.save(
                {
                    "session_id": analysis["session_id"],
                    "issue_decisions": decisions,
                    "review_revision": 1,
                }
            )
            restarted = MvpApplication(
                runner=lambda *_args: self.fail("restore reran the model"),
                store=SessionStore(root),
            )
            restored = restarted.restore({"session_id": analysis["session_id"]})
            self.assertEqual(restored["result"], analysis["result"])
            exported = restarted.export(
                {
                    "session_id": analysis["session_id"],
                    "issue_decisions": decisions,
                    "review_revision": saved["review_revision"],
                    "apply_copy_confirmed": True,
                }
            )
            copy = base64.b64decode(exported["copy_base64"])
            self.assertEqual(
                SOURCE, b"The conclusion proves universal effectiveness.\n"
            )
            self.assertNotEqual(copy, SOURCE)
            self.assertFalse(exported["review"]["apply_source"])
            self.assertTrue(exported["review"]["source_unchanged"])

    def test_public_runtime_has_no_apply_source_mode(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "paper.md"
            source.write_bytes(SOURCE)
            request = {
                "schema_version": 1,
                "request_id": "no-source-overwrite",
                "requested_at": "2026-07-28T22:00:00Z",
                "mode": "apply-source",
                "workflow_id": "self-review",
                "source": {"path": str(source), "sha256": digest(SOURCE)},
                "target_path": str(source),
                "authorisation": None,
            }
            with self.assertRaisesRegex(
                WorkflowAuthorityError, "invalid workflow mode"
            ):
                run_workflow(request)
            self.assertEqual(source.read_bytes(), SOURCE)

    def test_packaged_assets_are_colocated_with_runtime(self):
        import awt.mvp

        root = Path(awt.mvp.__file__).resolve().parent
        self.assertTrue((root / "mvp_index.html").is_file())
        self.assertTrue((root / "demo-paper.md").is_file())


if __name__ == "__main__":
    unittest.main()
