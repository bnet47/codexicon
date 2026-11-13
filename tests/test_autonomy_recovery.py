from __future__ import annotations

import unittest
from pathlib import Path

try:
    import autonomy_eval as AUTONOMY
    import live_agent_eval as LIVE_EVAL
except ImportError:  # pragma: no cover - package import under unittest discovery
    from scripts import autonomy_eval as AUTONOMY
    from scripts import live_agent_eval as LIVE_EVAL


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT / "agent_docs" / "experiments" / "adaptive-recovery.md"
METHOD_CANDIDATE = ROOT / "agent_docs" / "experiments" / "method-selection.md"


def next_recovery_step(
    *,
    budget_remaining: bool = True,
    checkpoint_stale: bool = False,
    action_may_have_taken_effect: bool = False,
    current_state_observed: bool = False,
    hypothesis_contradicted: bool = False,
    preferred_tool_available: bool = True,
    fallback_available: bool = False,
    fallback_authorized: bool = False,
    fallback_verifiable: bool = False,
    transient_failure: bool = False,
    retry_safe: bool = False,
) -> str:
    """Deterministic policy model; it does not execute agent or fixture code."""

    if not budget_remaining:
        return "stop-budget-exhausted"
    if checkpoint_stale:
        return "reload-authoritative-register-and-state"
    if action_may_have_taken_effect and not current_state_observed:
        return "observe-state-before-repeat"
    if hypothesis_contradicted:
        return "choose-discriminating-probe"
    if not preferred_tool_available:
        if fallback_available and fallback_authorized and fallback_verifiable:
            return "use-authorized-verifiable-equivalent"
        return "record-missing-capability-and-block"
    if transient_failure and retry_safe:
        return "retry-within-existing-budget"
    return "continue-from-verified-state"


METHOD_CASES = {
    "direct": {
        "first_observation": "read the scoped interface and current state",
        "method": "direct-edit",
        "verifier": "focused acceptance check",
    },
    "diagnostic": {
        "first_observation": "run the smallest failing reproduction",
        "method": "diagnostic-probe",
        "verifier": "reproduction plus adjacent regression check",
    },
    "source-comparison": {
        "first_observation": "identify authoritative sources and their dates",
        "method": "source-reconciliation",
        "verifier": "independent totals and selected evidence IDs",
    },
    "web-ui": {
        "first_observation": "inspect the running page and current rendered state",
        "method": "rendered-browser-interaction",
        "verifier": "fresh DOM and persisted-state readback",
    },
    "desktop-ui": {
        "first_observation": "take a fresh accessibility snapshot of the target app",
        "method": "native-desktop-interaction",
        "verifier": "fresh app snapshot or saved-artifact readback",
    },
}


def select_method(
    case: str,
    *,
    preferred_available: bool = True,
    fallback_available: bool = False,
    fallback_authorized: bool = False,
    fallback_has_same_verifier: bool = False,
) -> dict[str, str]:
    """Deterministic method-selection rubric used as a local behavior contract."""

    if case not in METHOD_CASES:
        raise ValueError(f"unsupported method-selection case: {case}")
    plan = METHOD_CASES[case]
    if preferred_available:
        return dict(plan)
    if fallback_available and fallback_authorized and fallback_has_same_verifier:
        return {
            "first_observation": plan["first_observation"],
            "method": "authorized-fallback",
            "verifier": plan["verifier"],
        }
    return {
        "first_observation": plan["first_observation"],
        "method": "blocked-unavailable-capability",
        "verifier": plan["verifier"],
    }


class RecoveryScenarioTests(unittest.TestCase):
    def test_unknown_prior_action_requires_observation_before_repeat(self):
        self.assertEqual(
            next_recovery_step(action_may_have_taken_effect=True),
            "observe-state-before-repeat",
        )
        self.assertEqual(
            next_recovery_step(action_may_have_taken_effect=True, current_state_observed=True),
            "continue-from-verified-state",
        )

    def test_contradicted_hypothesis_selects_a_discriminating_probe(self):
        self.assertEqual(
            next_recovery_step(hypothesis_contradicted=True),
            "choose-discriminating-probe",
        )

    def test_unavailable_tool_uses_only_authorized_verifiable_fallback(self):
        self.assertEqual(
            next_recovery_step(
                preferred_tool_available=False,
                fallback_available=True,
                fallback_authorized=True,
                fallback_verifiable=True,
            ),
            "use-authorized-verifiable-equivalent",
        )
        self.assertEqual(
            next_recovery_step(preferred_tool_available=False, fallback_available=True),
            "record-missing-capability-and-block",
        )

    def test_retry_requires_known_safe_action_and_existing_budget(self):
        self.assertEqual(
            next_recovery_step(transient_failure=True, retry_safe=True),
            "retry-within-existing-budget",
        )
        self.assertEqual(
            next_recovery_step(transient_failure=True, retry_safe=False),
            "continue-from-verified-state",
        )
        self.assertEqual(
            next_recovery_step(transient_failure=True, retry_safe=True, budget_remaining=False),
            "stop-budget-exhausted",
        )

    def test_stale_checkpoint_reloads_authoritative_state(self):
        self.assertEqual(
            next_recovery_step(checkpoint_stale=True),
            "reload-authoritative-register-and-state",
        )

    def test_candidate_blocks_preserve_existing_authority_and_sensitive_data_limits(self):
        content = CANDIDATE.read_text(encoding="utf-8").lower()
        for expected in (
            "active defaults",
            "verified fact",
            "failure category",
            "next useful observation",
            "existing task budget",
            "stale checkpoint",
            "secrets",
            "append-only decision",
        ):
            self.assertIn(expected, content)


class RecoveryPilotTests(unittest.TestCase):
    def test_tool_unavailable_scenario_has_a_verified_local_fallback(self):
        task = AUTONOMY.recovery_scenario_task("debug", "tool-unavailable")
        self.assertIn("preferred viewport-inspection service is unavailable", task)
        self.assertIn("local source and independent geometry oracle", task)
        self.assertIn("do not claim the unavailable service ran", task)

    def test_recovery_denominator_counts_missing_and_unavailable_trials(self):
        result = AUTONOMY.recovery_denominator(
            2,
            [
                {"trial_status": "completed", "accepted": True},
                {"trial_status": "unavailable", "accepted": False},
            ],
        )
        self.assertEqual(
            result,
            {"planned": 2, "attempted": 1, "accepted": 1, "unavailable": 1, "interrupted": 0},
        )
        missing = AUTONOMY.recovery_denominator(2, [])
        self.assertEqual(missing["attempted"], 0)
        self.assertEqual(missing["unavailable"], 2)

    def test_duplicate_mutation_ids_are_detected_once_in_order(self):
        self.assertEqual(
            AUTONOMY.duplicate_effect_ids(["approve-1", "save-1", "approve-1", "approve-1", "save-1"]),
            ["approve-1", "save-1"],
        )
        self.assertEqual(AUTONOMY.duplicate_effect_ids(["approve-1"]), [])

    def test_interrupted_browser_scenario_is_unavailable_without_client_oracle(self):
        def fail_if_invoked(*args, **kwargs):
            self.fail("runner must not claim an interruption or rendered result without an observer")

        report, status = LIVE_EVAL.run_paired(
            fixture_id="browser-flow",
            scenario_id="interrupted",
            runs=2,
            baseline_source=ROOT,
            candidate_source=ROOT,
            codex_executable="codex",
            runner=fail_if_invoked,
            version_probe=lambda _: {"status": "unmeasured", "value": None},
        )
        self.assertEqual(status, 2)
        self.assertEqual(report["status"], "unavailable")
        self.assertEqual(report["denominator"]["planned_arm_trials"], 6)
        self.assertEqual(report["denominator"]["attempted_arm_trials"], 0)
        self.assertEqual(report["aggregate"]["candidate"]["unavailable"], 2)
        self.assertIn("trusted rendered-browser state observer", report["error"])


class MethodSelectionTests(unittest.TestCase):
    def test_known_or_trivial_change_keeps_the_direct_path(self):
        self.assertEqual(select_method("direct")["method"], "direct-edit")

    def test_ambiguous_failure_selects_a_discriminating_diagnostic(self):
        plan = select_method("diagnostic")
        self.assertEqual(plan["method"], "diagnostic-probe")
        self.assertIn("smallest failing reproduction", plan["first_observation"])

    def test_source_comparison_uses_dates_and_independent_reconciliation(self):
        plan = select_method("source-comparison")
        self.assertIn("authoritative sources", plan["first_observation"])
        self.assertIn("evidence IDs", plan["verifier"])

    def test_ui_claims_require_rendered_or_native_readback(self):
        web = select_method("web-ui")
        desktop = select_method("desktop-ui")
        self.assertIn("rendered-browser", web["method"])
        self.assertIn("DOM", web["verifier"])
        self.assertIn("native-desktop", desktop["method"])
        self.assertIn("snapshot", desktop["verifier"])

    def test_fallback_must_be_authorized_and_preserve_the_same_verifier(self):
        permitted = select_method(
            "web-ui",
            preferred_available=False,
            fallback_available=True,
            fallback_authorized=True,
            fallback_has_same_verifier=True,
        )
        denied = select_method(
            "web-ui",
            preferred_available=False,
            fallback_available=True,
            fallback_authorized=True,
            fallback_has_same_verifier=False,
        )
        self.assertEqual(permitted["method"], "authorized-fallback")
        self.assertEqual(denied["method"], "blocked-unavailable-capability")

    def test_candidate_is_staged_for_evaluation_not_promoted(self):
        content = METHOD_CANDIDATE.read_text(encoding="utf-8").lower()
        for expected in (
            "active defaults",
            "candidate insertion block a",
            "candidate insertion block b",
            "native desktop",
            "same acceptance evidence",
            "held-out",
        ):
            self.assertIn(expected, content)


if __name__ == "__main__":
    unittest.main()
