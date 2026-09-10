from __future__ import annotations

import dataclasses
import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVAL_PATH = ROOT / "scripts" / "agent_loop_eval.py"
SPEC = importlib.util.spec_from_file_location("agent_loop_eval", EVAL_PATH)
assert SPEC and SPEC.loader
EVAL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = EVAL
SPEC.loader.exec_module(EVAL)


class AgentLoopEvaluationTests(unittest.TestCase):
    def test_regression_fixture_set_covers_rec_01_through_rec_13(self) -> None:
        self.assertEqual(tuple(fixture.id for fixture in EVAL.REGRESSION_FIXTURES), EVAL.REC_IDS)
        self.assertEqual(len({fixture.test for fixture in EVAL.REGRESSION_FIXTURES}), 13)
        for fixture in EVAL.REGRESSION_FIXTURES:
            with self.subTest(regression=fixture.id):
                self.assertTrue(fixture.input)
                self.assertTrue(fixture.expected)
                self.assertIn("tests.", fixture.test)

    def test_deterministic_regressions_execute_the_existing_focused_oracles(self) -> None:
        results = EVAL.run_regressions(ROOT)
        self.assertEqual(len(results), 13)
        self.assertTrue(all(result.passed for result in results), results)
        self.assertTrue(all(result.returncode == 0 for result in results), results)

    def test_scenario_fixtures_have_expected_measured_boundaries(self) -> None:
        results = EVAL.run_scenarios()
        self.assertEqual(tuple(result.id for result in results), EVAL.SCENARIO_IDS)
        self.assertTrue(all(result.passed for result in results), results)

        by_id = {result.id: result for result in results}
        self.assertEqual(by_id["failed-verification"].metrics["verification_reruns"], 1)
        self.assertEqual(by_id["contract-drift"].metrics["rejected_scope_expansion"], 1)
        self.assertEqual(by_id["protected-path-attempt"].metrics["rejected_scope_expansion"], 1)
        self.assertTrue(all(result.metrics["attempted_git_during_build"] == 0 for result in results))

    def test_negative_control_catches_an_attempted_build_git_operation(self) -> None:
        fixture = next(item for item in EVAL.SCENARIO_FIXTURES if item.id == "quick-fix")
        corrupted = dataclasses.replace(
            fixture,
            input=fixture.input
            + ({"kind": "git", "phase": "build", "attempted": True},),
        )
        result = EVAL.evaluate_scenario(corrupted)
        self.assertFalse(result.passed)
        self.assertFalse(result.checks["no_build_git"])

    def test_report_uses_denominators_and_declares_live_fields_unmeasured(self) -> None:
        report = EVAL.build_report(ROOT, include_regressions=False)
        self.assertEqual(report["scenarios"]["passed"], 10)
        self.assertEqual(report["scenarios"]["denominator"], 10)
        self.assertEqual(report["scenario_metrics"]["verification_reruns"], {"measured": 1, "denominator": 10})
        self.assertEqual(report["measures"]["acceptance_pass_rate"], {"passed": 10, "denominator": 10})
        self.assertEqual(report["measures"]["attempted_git_during_build"], {"measured": 0, "denominator": 10})
        self.assertTrue(report["unmeasured_live_fields"])


if __name__ == "__main__":
    unittest.main()
