from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = ROOT / "scripts" / "live_agent_eval.py"
SPEC = importlib.util.spec_from_file_location("live_agent_eval", EVAL_PATH)
assert SPEC and SPEC.loader
EVAL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EVAL
SPEC.loader.exec_module(EVAL)


class LiveAgentEvaluationTests(unittest.TestCase):
    def test_command_construction_is_the_required_ephemeral_json_invocation(self) -> None:
        command = EVAL.build_codex_command("codex", Path("C:/fixture"), "prompt")
        self.assertEqual(
            command,
            [
                "codex",
                "exec",
                "--ephemeral",
                "--sandbox",
                "workspace-write",
                "--skip-git-repo-check",
                "-C",
                os.fspath(Path("C:/fixture")),
                "--json",
                "prompt",
            ],
        )

    def test_fixture_scoring_restores_oracle_and_scores_calculator(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            fixture = Path(name)
            EVAL.create_fixture(fixture)
            score = EVAL.score_fixture(fixture)
            self.assertEqual(score["status"], "failed")
            (fixture / EVAL.CALCULATOR_FILENAME).write_text(
                "def add(left, right):\n    return left + right\n",
                encoding="utf-8",
            )
            (fixture / EVAL.ORACLE_FILENAME).write_text("broken oracle", encoding="utf-8")
            score = EVAL.score_fixture(fixture)
            self.assertEqual(score["status"], "passed")
            self.assertIn("CalculatorOracle", (fixture / EVAL.ORACLE_FILENAME).read_text(encoding="utf-8"))

    def test_unavailable_cli_is_explicit_and_nonzero(self) -> None:
        report, status = EVAL.run_evaluation(which=lambda _: None)
        self.assertEqual(status, 2)
        self.assertEqual(report["status"], "unavailable")
        self.assertIn("unavailable", report["error"])
        self.assertEqual(report["trials"], [])

    def test_timeout_is_interrupted_without_raw_output(self) -> None:
        def timeout_runner(*args, **kwargs):
            raise subprocess.TimeoutExpired(kwargs.get("args", args[0]), 90, output=b"secret")

        with tempfile.TemporaryDirectory() as name:
            result = EVAL.invoke_codex("codex", Path(name), "prompt", runner=timeout_runner)
        self.assertEqual(result["exit_status"], "timeout")
        self.assertTrue(result["interrupted"])
        self.assertTrue(result["invocation_started"])
        self.assertNotIn("secret", json.dumps(result))

    def test_report_schema_has_smoke_denominator_and_unmeasured_metrics(self) -> None:
        def fake_codex(*args, **kwargs):
            fixture = Path(kwargs["cwd"])
            (fixture / EVAL.CALCULATOR_FILENAME).write_text(
                "def add(left, right):\n    return left + right\n",
                encoding="utf-8",
            )
            return SimpleNamespace(
                returncode=0,
                stdout='{"type":"item.completed","item":{"type":"agent_message","text":"verified"}}\n',
                stderr="",
            )

        report, status = EVAL.run_evaluation(
            codex_executable="codex",
            runner=fake_codex,
        )
        self.assertEqual(status, 0)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["denominator"]["paired_trials"], 1)
        self.assertEqual(report["aggregate"]["direct"]["acceptance"], "1/1")
        self.assertEqual(report["aggregate"]["guided"]["acceptance"], "1/1")
        self.assertEqual(report["aggregate"]["routed"]["acceptance"], "1/1")
        for arm in (
            report["trials"][0]["direct"],
            report["trials"][0]["guided"],
            report["trials"][0]["routed"],
        ):
            self.assertEqual(arm["metrics"]["model"], "unmeasured")
            self.assertEqual(arm["event_metadata"]["last_message_excerpt"], "verified")
        self.assertTrue(report["limitations"])

    def test_guided_prompt_contains_required_workflow_and_scope(self) -> None:
        prompt = EVAL.PROMPTS["guided"].lower()
        for word in ("inspect", "run", "fix", "verify", "unrelated files"):
            self.assertIn(word, prompt)

    def test_routed_prompt_contains_bounded_dispatch_and_primary_ownership(self) -> None:
        prompt = EVAL.PROMPTS["routed"].lower()
        for word in ("eligible", "envelope", "authority", "spawn", "primary"):
            self.assertIn(word, prompt)


class PairedRunnerTests(unittest.TestCase):
    def test_paired_runner_uses_same_prompt_and_records_unobserved_pickup(self) -> None:
        prompts = []
        inputs = []

        def fake_codex(command, **kwargs):
            workspace = Path(kwargs["cwd"])
            prompts.append(command[-1])
            inputs.append(
                tuple(
                    (workspace / relative).read_bytes()
                    for relative in ("SPEC.md", "TASKS.md", "calculator.py", "test_calculator.py")
                )
            )
            (workspace / "calculator.py").write_text(
                "def add(left, right):\n    return left + right\n",
                encoding="utf-8",
            )
            return SimpleNamespace(
                returncode=0,
                stdout='{"type":"item.completed"}\n',
                stderr="",
            )

        report, status = EVAL.run_paired(
            fixture_id="calculator",
            runs=1,
            baseline_source=ROOT,
            codex_executable="codex",
            runner=fake_codex,
            version_probe=lambda _: {"status": "measured", "value": "codex-test 1.0"},
        )
        self.assertEqual(status, 0)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(
            report["denominator"],
            {
                "paired_trials": 1,
                "plain_runs": 1,
                "starter_runs": 1,
                "planned_arm_trials": 2,
                "attempted_arm_trials": 2,
            },
        )
        self.assertEqual(prompts[0], prompts[1])
        self.assertEqual(inputs[0], inputs[1])
        plain = report["trials"][0]["arms"]["plain"]
        starter = report["trials"][0]["arms"]["starter"]
        self.assertTrue(plain["accepted"])
        self.assertTrue(starter["accepted"])
        self.assertFalse(plain["starter_staged"])
        self.assertTrue(starter["starter_staged"])
        self.assertEqual(starter["client_pickup_status"], "unmeasured")
        self.assertEqual(starter["method_observation_status"], "unmeasured")
        self.assertEqual(starter["unauthorized_attempt_status"], "unmeasured")
        self.assertEqual(report["settings"]["client_version"], {"status": "measured", "value": "codex-test 1.0"})

    def test_unavailable_codex_does_not_start_trials(self) -> None:
        report, status = EVAL.run_paired(
            fixture_id="calculator",
            baseline_source=ROOT,
            codex_executable=None,
            which=lambda _: None,
        )
        self.assertEqual(status, 2)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["trials"], [])

    def test_codex_launch_failure_is_unavailable_and_not_an_attempted_trial(self) -> None:
        def missing_executable(*args, **kwargs):
            raise FileNotFoundError("codex executable disappeared")

        report, status = EVAL.run_paired(
            fixture_id="calculator",
            baseline_source=ROOT,
            codex_executable="codex",
            runner=missing_executable,
            version_probe=lambda _: {"status": "unmeasured", "value": None},
        )

        self.assertEqual(status, 2)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["denominator"]["planned_arm_trials"], 2)
        self.assertEqual(report["denominator"]["attempted_arm_trials"], 0)
        self.assertEqual(len(report["trials"]), 1)
        for label in ("plain", "starter"):
            arm = report["trials"][0]["arms"][label]
            self.assertEqual(arm["trial_status"], "unavailable")
            self.assertFalse(arm["invocation_started"])
            self.assertEqual(arm["verification_status"], "unmeasured")
            self.assertEqual(report["aggregate"][label]["attempted"], 0)
            self.assertEqual(report["aggregate"][label]["unavailable"], 1)

    def test_legacy_smoke_text_keeps_the_original_acceptance_format(self) -> None:
        report = {
            "status": "passed",
            "denominator": {"paired_trials": 1},
            "aggregate": {
                label: {
                    "acceptance": "1/1",
                    "denominator": 1,
                    "regressions": 0,
                    "elapsed_seconds": 0.1,
                }
                for label in ("direct", "guided", "routed")
            },
        }
        output = StringIO()
        with redirect_stdout(output):
            EVAL._print_report(report, as_json=False)
        self.assertIn("direct: accepted 1/1;", output.getvalue())
        self.assertNotIn("1/1/1", output.getvalue())


if __name__ == "__main__":
    unittest.main()
