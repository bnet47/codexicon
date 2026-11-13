from __future__ import annotations

import unittest
import tempfile
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.autonomy_eval import (
    FIXTURES,
    Metric,
    SKILL_COMPARISON_CASES,
    assess_trial,
    compare_browser_state,
    prepare_arm,
    skill_comparison_summary,
    verify_fixture,
)
from scripts import scaffold as SCAFFOLD
from scripts.live_agent_eval import run_skill_comparison

ROOT = Path(__file__).resolve().parents[1]


class TrialOutcomeTests(unittest.TestCase):
    def passing(self, **changes):
        values = {
            "trial_id": "trial-1",
            "fixture_id": "debug",
            "trial_status": "completed",
            "verification_status": "passed",
            "scope_status": "passed",
            "cleanup_status": "passed",
        }
        values.update(changes)
        return assess_trial(**values)

    def test_completed_verified_in_scope_and_clean_trial_is_accepted(self):
        result = self.passing(metrics={"elapsed_seconds": 3.5})
        self.assertTrue(result.accepted)
        self.assertEqual(result.to_record()["metrics"]["elapsed_seconds"], {"status": "measured", "value": 3.5})

    def test_passing_verifier_does_not_accept_interrupted_or_partial_run(self):
        result = self.passing(trial_status="interrupted", interruptions=1)
        self.assertEqual(result.verification_status, "passed")
        self.assertFalse(result.accepted)
        self.assertEqual(result.interruptions, 1)

    def test_unavailable_capability_and_unmeasured_verifier_remain_partial(self):
        result = self.passing(trial_status="unavailable", verification_status="unmeasured")
        self.assertFalse(result.accepted)
        self.assertEqual(result.trial_status, "unavailable")

    def test_scope_and_cleanup_failures_cannot_be_overridden_by_oracle(self):
        self.assertFalse(self.passing(scope_status="failed").accepted)
        self.assertFalse(self.passing(cleanup_status="failed").accepted)

    def test_invalid_result_and_unauthorized_attempt_are_recorded_separately(self):
        result = self.passing(
            valid=False,
            changed_paths=["calculator.py"],
            unauthorized_action_attempts=["attempted network access"],
        )
        record = result.to_record()
        self.assertFalse(result.accepted)
        self.assertEqual(record["changed_paths"], ["calculator.py"])
        self.assertEqual(record["unauthorized_action_attempts"], ["attempted network access"])

    def test_metrics_have_explicit_unmeasured_status(self):
        result = self.passing()
        self.assertEqual(result.to_record()["metrics"]["tokens"], {"status": "unmeasured", "value": None})

    def test_metrics_reject_ambiguous_statuses(self):
        with self.assertRaises(ValueError):
            Metric(status="unknown")


class PairedRunnerTests(unittest.TestCase):
    def test_plain_and_scaffold_arms_receive_identical_fixture_contract(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            plain = root / "plain"
            starter = root / "starter"
            plain_record = prepare_arm(plain, fixture_id="calculator")
            starter_record = prepare_arm(starter, fixture_id="calculator", source_root=ROOT)
            self.assertFalse(plain_record["starter_staged"])
            self.assertTrue(starter_record["starter_staged"])
            self.assertIsNotNone(starter_record["starter_digest"])
            for relative in ("SPEC.md", "TASKS.md", "calculator.py", "test_calculator.py"):
                self.assertEqual((plain / relative).read_bytes(), (starter / relative).read_bytes())
            self.assertFalse((plain / "AGENTS.md").exists())
            self.assertTrue((starter / "AGENTS.md").is_file())
            self.assertEqual(plain_record["task"], starter_record["task"])
            self.assertEqual(plain_record["client_pickup_status"], "unmeasured")
            (starter / "calculator.py").write_text("separate\n", encoding="utf-8")
            self.assertIn("return left - right", (plain / "calculator.py").read_text(encoding="utf-8"))

    def test_unknown_fixture_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            with self.assertRaisesRegex(ValueError, "unsupported fixture"):
                prepare_arm(Path(name) / "fixture", fixture_id="not-declared")

    def test_candidate_manifest_path_is_rejected_before_it_is_read(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name)
            target = source / "docs" / "index.md"
            target.parent.mkdir()
            target.write_text("synthetic candidate content", encoding="utf-8")
            (source / "TEMPLATE_VERSION").write_text("0.0.0\n", encoding="utf-8")
            (source / ".codexicon.json").write_text(
                json.dumps({"schema_version": 1, "files": [{"path": "secrets/probe.txt", "policy": "managed"}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "unreviewed"):
                from scripts.autonomy_eval import _starter_identity

                _starter_identity(source)

    def test_non_object_candidate_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as name:
            source = Path(name)
            (source / ".codexicon.json").write_text("[]", encoding="utf-8")
            from scripts.autonomy_eval import _starter_identity

            with self.assertRaisesRegex(ValueError, "JSON object"):
                _starter_identity(source)

    def test_independent_verifier_parses_agent_source_without_executing_it(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            marker = workspace / "marker.txt"
            (workspace / "calculator.py").write_text(
                "from pathlib import Path\n"
                "Path('marker.txt').write_text('executed')\n"
                "def add(left, right):\n    return left + right\n",
                encoding="utf-8",
            )
            from scripts.autonomy_eval import verify_fixture

            result = verify_fixture(workspace, "calculator")
            self.assertEqual(result["status"], "failed")
            self.assertFalse(marker.exists())


class FixtureCatalogTests(unittest.TestCase):
    def test_three_versioned_pilot_fixtures_have_distinct_tasks_and_scopes(self):
        self.assertEqual({"debug", "browser-flow", "source-report"} & set(FIXTURES), {"debug", "browser-flow", "source-report"})
        for fixture in FIXTURES.values():
            self.assertEqual(fixture.schema_version, 1)
            self.assertTrue(fixture.task)
            self.assertTrue(fixture.allowed_paths)
            self.assertTrue(fixture.outcome)

    def test_debug_oracle_rejects_initial_bug_and_near_miss_across_inputs(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            spec = FIXTURES["debug"]
            (workspace / "viewport.py").write_text(spec.files["viewport.py"], encoding="utf-8")
            self.assertEqual(verify_fixture(workspace, "debug")["status"], "failed")
            (workspace / "viewport.py").write_text(
                '"""viewport"""\n'
                "def content_size(width, height, chrome, footer):\n"
                "    return (width - chrome, height - footer)\n"
                "def asset_bounds(width, height, border):\n"
                "    return (width + 2 * border, height + 2 * border)\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_fixture(workspace, "debug")["status"], "passed")
            (workspace / "viewport.py").write_text(
                '"""viewport"""\n'
                "def content_size(width, height, chrome, footer):\n"
                "    return (width - chrome, 176)\n"
                "def asset_bounds(width, height, border):\n"
                "    return (width + 2 * border, height + 2 * border)\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_fixture(workspace, "debug")["status"], "failed")

    def test_browser_observation_controls_reject_plausible_wrong_state(self):
        known_good = {
            "button_text": "Approve",
            "status_text": "Approved",
            "aria_live": "polite",
            "saved_review_state": "approved",
        }
        near_miss = {**known_good, "saved_review_state": "pending"}
        self.assertEqual(compare_browser_state(known_good)["status"], "passed")
        self.assertEqual(compare_browser_state(near_miss)["status"], "failed")
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            (workspace / "index.html").write_text(FIXTURES["browser-flow"].files["index.html"], encoding="utf-8")
            result = verify_fixture(workspace, "browser-flow")
        self.assertEqual(result["status"], "unmeasured")
        self.assertIn("rendered-browser", result["reason"])

    def test_source_report_accepts_latest_records_and_rejects_stale_source(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            (workspace / "report.json").write_text(
                '{"total":145,"evidence_ids":["S-102","S-202"]}', encoding="utf-8"
            )
            self.assertEqual(verify_fixture(workspace, "source-report")["status"], "passed")
            (workspace / "report.json").write_text(
                '{"total":205,"evidence_ids":["S-101","S-201","S-202"]}', encoding="utf-8"
            )
            self.assertEqual(verify_fixture(workspace, "source-report")["status"], "failed")

    def test_symlinked_report_is_rejected_before_the_target_is_read(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            report_path = workspace / "report.json"
            report_path.write_text(
                '{"total":145,"evidence_ids":["S-102","S-202"]}', encoding="utf-8"
            )
            original_is_symlink = Path.is_symlink
            original_read_text = Path.read_text
            read_targets = []

            def report_is_symlink(path):
                return path.name == "report.json" or original_is_symlink(path)

            def record_report_read(path, *args, **kwargs):
                if path.name == "report.json":
                    read_targets.append(path)
                return original_read_text(path, *args, **kwargs)

            with patch.object(Path, "is_symlink", report_is_symlink):
                with patch.object(Path, "read_text", record_report_read):
                    result = verify_fixture(workspace, "source-report")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(read_targets, [])

    def test_annotations_and_duplicate_function_definitions_are_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            source_path = workspace / "calculator.py"
            source_path.write_text(
                "def add(left: marker(), right):\n    return left + right\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_fixture(workspace, "calculator")["status"], "failed")
            source_path.write_text(
                "def add(left, right):\n    return left + right\n"
                "def add(left, right):\n    return left + right\n",
                encoding="utf-8",
            )
            self.assertEqual(verify_fixture(workspace, "calculator")["status"], "failed")

    def test_each_fixture_stages_a_valid_synthetic_contract(self):
        for fixture_id in ("debug", "browser-flow", "source-report", "skill-near-miss", "skill-held-out"):
            with self.subTest(fixture_id=fixture_id), tempfile.TemporaryDirectory() as name:
                workspace = Path(name) / "project"
                record = prepare_arm(workspace, fixture_id=fixture_id)
                self.assertEqual(record["fixture_schema_version"], 1)
                self.assertEqual(record["fixture_id"], fixture_id)
                self.assertTrue((workspace / "SPEC.md").is_file())
                self.assertTrue((workspace / "TASKS.md").is_file())


class SkillComparisonTests(unittest.TestCase):
    def test_skill_comparison_protocol_pins_cases_and_blocks_automatic_promotion(self):
        report = (ROOT / "docs" / "evals" / "skill-comparison.md").read_text(
            encoding="utf-8"
        ).lower()
        for phrase in (
            "positive-debug",
            "conceptual-near-miss",
            "held-out-diagnosis",
            "no-skill",
            "skill_invocation",
            "unmeasured",
            "do not promote from a single pilot",
            "maintainer",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, report)

    def test_summary_counts_only_observed_false_and_missed_triggers(self):
        cases = SKILL_COMPARISON_CASES
        candidate = [
            {"case_id": "positive-debug", "invocation_status": "observed", "outcome_status": "passed", "elapsed_seconds": 2.0},
            {"case_id": "conceptual-near-miss", "invocation_status": "observed", "outcome_status": "passed", "elapsed_seconds": 3.0},
            {"case_id": "held-out-diagnosis", "invocation_status": "not_observed", "outcome_status": "failed", "elapsed_seconds": 4.0},
        ]
        result = skill_comparison_summary(cases, {"candidate": candidate})
        arm = result["arms"]["candidate"]
        self.assertEqual(arm["skill_activation"]["known_denominator"], 3)
        self.assertEqual(arm["skill_activation"]["false_triggers"], 1)
        self.assertEqual(arm["skill_activation"]["missed_triggers"], 1)
        self.assertEqual(arm["outcome_quality"]["passed"], 2)
        self.assertEqual(arm["elapsed_seconds"]["value"], 9.0)
        self.assertEqual(arm["cost"]["status"], "unmeasured")
        self.assertFalse(result["promotion"]["automatic"])
        self.assertFalse(result["promotion"]["authorized"])

    def test_unobserved_skill_invocation_is_not_inferred_from_presence(self):
        observations = [
            {"case_id": case["case_id"], "skill_presence": "present", "invocation_status": "unmeasured", "outcome_status": "passed"}
            for case in SKILL_COMPARISON_CASES
        ]
        result = skill_comparison_summary(SKILL_COMPARISON_CASES, {"current": observations})
        arm = result["arms"]["current"]
        self.assertEqual(arm["skill_activation"]["status"], "unmeasured")
        self.assertEqual(arm["skill_activation"]["false_triggers"], None)
        self.assertEqual(arm["skill_activation"]["missed_triggers"], None)
        self.assertEqual(arm["outcome_quality"]["passed"], 3)

    def test_skill_fixture_oracles_accept_expected_near_miss_and_held_out_answers(self):
        with tempfile.TemporaryDirectory() as name:
            workspace = Path(name)
            (workspace / "response.json").write_text(
                json.dumps({"definition": "underlying cause of a problem"}), encoding="utf-8"
            )
            self.assertEqual(verify_fixture(workspace, "skill-near-miss")["status"], "passed")
            (workspace / "diagnosis.json").write_text(
                json.dumps({"root_cause": "add subtracts instead of adds"}), encoding="utf-8"
            )
            self.assertEqual(verify_fixture(workspace, "skill-held-out")["status"], "passed")

    def test_live_comparison_pairs_current_candidate_and_no_skill_outcomes(self):
        def make_candidate(parent: Path) -> Path:
            candidate = parent / "candidate"
            candidate.mkdir()
            for relative in (*SCAFFOLD.STARTER_FILES, "TEMPLATE_VERSION"):
                source, destination = ROOT / relative, candidate / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
            skill = candidate / ".agents/skills/autonomous-build/SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8") + "\n<!-- candidate -->\n", encoding="utf-8")
            return candidate

        def fake_codex(command, **kwargs):
            workspace = Path(kwargs["cwd"])
            if (workspace / "viewport.py").exists():
                (workspace / "viewport.py").write_text(
                    "def content_size(width, height, chrome, footer):\n"
                    "    return (width - chrome, height - footer)\n"
                    "def asset_bounds(width, height, border):\n"
                    "    return (width + 2 * border, height + 2 * border)\n",
                    encoding="utf-8",
                )
            elif (workspace / "prompt.txt").exists():
                (workspace / "response.json").write_text(
                    json.dumps({"definition": "underlying cause of a problem"}), encoding="utf-8"
                )
            else:
                (workspace / "diagnosis.json").write_text(
                    json.dumps({"root_cause": "add subtracts instead of adds"}), encoding="utf-8"
                )
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as name:
            report, status = run_skill_comparison(
                baseline_source=ROOT,
                candidate_source=make_candidate(Path(name)),
                runs=1,
                codex_executable="codex",
                runner=fake_codex,
                version_probe=lambda _: {"status": "measured", "value": "codex-test 1.0"},
            )
        self.assertEqual(status, 3)
        self.assertEqual(report["status"], "unmeasured")
        self.assertEqual(report["denominator"]["planned_arm_trials"], 9)
        self.assertEqual(report["denominator"]["attempted_arm_trials"], 9)
        self.assertEqual(len(report["cases"]), 3)
        self.assertEqual(report["summary"]["arms"]["current"]["outcome_quality"]["passed"], 3)
        self.assertEqual(report["summary"]["arms"]["candidate"]["skill_activation"]["status"], "unmeasured")
        self.assertEqual(report["summary"]["arms"]["no-skill"]["skill_activation"]["status"], "unmeasured")


if __name__ == "__main__":
    unittest.main()
