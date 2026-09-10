#!/usr/bin/env python3
"""Run the deterministic REC-01..REC-13 and agent-journey evaluations.

This evaluator deliberately measures repository fixtures, not a live agent.  The
regression cases run the existing unittest probes that protect each reviewed
failure.  Journey cases are fixed event traces used to check the durable
workflow policy and its safety boundaries without requiring a client session.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
REC_IDS = tuple(f"REC-{number:02d}" for number in range(1, 14))
SCENARIO_IDS = (
    "fresh-template",
    "spec-amendment",
    "quick-fix",
    "existing-plan",
    "active-compaction",
    "blocked-dependency-independent-work",
    "failed-verification",
    "contract-drift",
    "protected-path-attempt",
    "playbook-routing",
)


@dataclass(frozen=True)
class RegressionFixture:
    id: str
    input: str
    expected: str
    test: str


@dataclass(frozen=True)
class ScenarioFixture:
    id: str
    input: tuple[Mapping[str, Any], ...]
    expected: str
    required: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RegressionResult:
    id: str
    test: str
    passed: bool
    returncode: int


@dataclass(frozen=True)
class ScenarioResult:
    id: str
    passed: bool
    expected: str
    metrics: Mapping[str, int]
    checks: Mapping[str, bool]


# One focused, deterministic test is the executable oracle for each reviewed
# regression.  Keeping the selectors here makes coverage auditable and avoids
# pretending that raw tool names constitute client compatibility evidence.
REGRESSION_FIXTURES = (
    RegressionFixture(
        "REC-01",
        "A malformed unfinished task row follows a valid DONE row.",
        "The parser rejects the row with a line-aware error.",
        "tests.test_codexicon.CodexiconManagerTests.test_task_register_rejects_malformed_unfinished_work_after_done_row",
    ),
    RegressionFixture(
        "REC-02",
        "A blocked dependency, its consumer, and an independent TODO task.",
        "The consumer stays blocked and the independent task is READY.",
        "tests.test_codexicon.CodexiconManagerTests.test_queue_blocks_dependencies_but_keeps_independent_work_runnable",
    ),
    RegressionFixture(
        "REC-03",
        "A task attempts DONE without a fresh current-task receipt.",
        "Completion is rejected until current evidence covers acceptance.",
        "tests.test_codexicon.CodexiconManagerTests.test_done_requires_current_task_receipt_and_does_not_execute_command_text",
    ),
    RegressionFixture(
        "REC-04",
        "SPEC.md changes while TASKS.md retains its old contract identity.",
        "The task queue rejects the drift and requests an authorized baseline update.",
        "tests.test_codexicon.CodexiconManagerTests.test_contract_identity_is_stable_and_task_binding_detects_drift",
    ),
    RegressionFixture(
        "REC-05",
        "A validated task bookkeeping command and a source mutation pass through the hook.",
        "Bookkeeping preserves evidence; source mutation invalidates it.",
        "tests.test_codexicon.CodexiconManagerTests.test_hook_preserves_evidence_for_bookkeeping_but_invalidates_mutations",
    ),
    RegressionFixture(
        "REC-06",
        "Implementation entry-point skills are inspected as one route.",
        "Implementation routes use the shared SPEC/TASKS and Build vocabulary.",
        "tests.test_template.TemplateValidationTests.test_implementation_entry_points_share_contract_and_writer_policy",
    ),
    RegressionFixture(
        "REC-07",
        "A resume/compact start has ACTIVE work, blockers, and a supplemental checkpoint.",
        "Bounded authoritative context is emitted and the checkpoint cannot override current state.",
        "tests.test_codexicon.CodexiconManagerTests.test_resume_context_is_bounded_authoritative_and_checkpoint_supplemental",
    ),
    RegressionFixture(
        "REC-08",
        "The playbook selector and cards are compared for every implementation route.",
        "Selector values, cards, prompts, and generated routing remain aligned.",
        "tests.test_template.TemplateValidationTests.test_playbook_implementation_routing_is_complete_and_readable",
    ),
    RegressionFixture(
        "REC-09",
        "Build checkpoint, resume, and doctor run with Git unavailable.",
        "The normal Build path remains local and Git-free.",
        "tests.test_codexicon.CodexiconManagerTests.test_build_checkpoint_resume_and_doctor_do_not_call_git",
    ),
    RegressionFixture(
        "REC-10",
        "Quoted JSON/YAML/dictionary secret keys contain literal values.",
        "The scanner detects them without exposing their values.",
        "tests.test_security_scan.SecurityScanTests.test_quoted_json_yaml_and_dictionary_keys_detect_literal_secrets",
    ),
    RegressionFixture(
        "REC-11",
        "An adoption transaction is interrupted during apply and resumed.",
        "Recovery rolls back or completes idempotently without losing user edits.",
        "tests.test_codexicon.CodexiconManagerTests.test_interrupted_transaction_rolls_back_and_recovers",
    ),
    RegressionFixture(
        "REC-12",
        "An identical executable template file has mode drift.",
        "Adoption journals and corrects the mode while preserving ownership rules.",
        "tests.test_codexicon.CodexiconManagerTests.test_adoption_journals_mode_correction_for_identical_executable_file",
    ),
    RegressionFixture(
        "REC-13",
        "Template discovery encounters generated and protected paths.",
        "Generated trees are pruned and protected files are rejected before reads.",
        "tests.test_template.TemplateValidationTests.test_template_discovery_prunes_generated_and_protected_files_before_reads",
    ),
)


def _events(*items: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(items)


SCENARIO_FIXTURES = (
    ScenarioFixture(
        "fresh-template",
        _events(
            {"kind": "route", "value": "autonomous-build"},
            {"kind": "trace", "value": "SPEC.md -> TASKS.md"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Create missing local contract/task artifacts, trace implementation, and verify without a routine handoff.",
        (("route", "autonomous-build"), ("trace", "SPEC.md -> TASKS.md")),
    ),
    ScenarioFixture(
        "spec-amendment",
        _events(
            {"kind": "route", "value": "spec"},
            {"kind": "trace", "value": "append-only amendment"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Amend the active contract append-only, then reconcile the task baseline before implementation.",
        (("route", "spec"), ("trace", "append-only amendment")),
    ),
    ScenarioFixture(
        "quick-fix",
        _events(
            {"kind": "route", "value": "quick"},
            {"kind": "trace", "value": "existing requirement"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Use the existing trace and make the smallest behavior change with focused verification.",
        (("route", "quick"),),
    ),
    ScenarioFixture(
        "existing-plan",
        _events(
            {"kind": "route", "value": "execute-plan -> autonomous-build"},
            {"kind": "queue", "value": "RESUME_ACTIVE or READY"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Consume an existing plan as context while SPEC.md and TASKS.md remain authoritative.",
        (("route", "execute-plan -> autonomous-build"),),
    ),
    ScenarioFixture(
        "active-compaction",
        _events(
            {"kind": "resume", "value": "RESUME_ACTIVE"},
            {"kind": "context", "value": "bounded authoritative context"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Resume ACTIVE work after compaction from authoritative contract/task state.",
        (("resume", "RESUME_ACTIVE"), ("context", "bounded authoritative context")),
    ),
    ScenarioFixture(
        "blocked-dependency-independent-work",
        _events(
            {"kind": "queue", "value": "READY:T-003"},
            {"kind": "queue", "value": "consumer-not-started"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Leave a blocked consumer untouched while selecting independent READY work.",
        (("queue", "READY:T-003"), ("queue", "consumer-not-started")),
    ),
    ScenarioFixture(
        "failed-verification",
        _events(
            {"kind": "verification", "value": "failed"},
            {"kind": "verification", "value": "rerun-after-fix", "rerun": True},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Treat failed checks as incomplete, fix locally, and rerun the required verification.",
        (("verification", "failed"), ("verification", "rerun-after-fix")),
    ),
    ScenarioFixture(
        "contract-drift",
        _events(
            {"kind": "contract", "value": "drift-rejected"},
            {"kind": "scope", "value": "rejected-expansion"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Stop before writing when the task baseline no longer matches the contract.",
        (("contract", "drift-rejected"), ("scope", "rejected-expansion")),
    ),
    ScenarioFixture(
        "protected-path-attempt",
        _events(
            {"kind": "protected-path", "value": "rejected-before-read"},
            {"kind": "scope", "value": "rejected-expansion"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Reject a protected-path operation before opening it and keep the task scope unchanged.",
        (("protected-path", "rejected-before-read"), ("scope", "rejected-expansion")),
    ),
    ScenarioFixture(
        "playbook-routing",
        _events(
            {"kind": "route", "value": "selector-card-prompt-aligned"},
            {"kind": "git", "phase": "build", "attempted": False},
            {"kind": "acceptance", "passed": True},
        ),
        "Select the matching playbook route and preserve the shared implementation vocabulary.",
        (("route", "selector-card-prompt-aligned"),),
    ),
)


def _validate_fixture_ids(fixtures: Iterable[Any], expected: tuple[str, ...], label: str) -> None:
    actual = tuple(fixture.id for fixture in fixtures)
    if actual != expected:
        raise ValueError(f"{label} IDs must be exactly {expected}; found {actual}")


def evaluate_scenario(fixture: ScenarioFixture) -> ScenarioResult:
    events = fixture.input
    metrics = {
        "acceptance_passed": sum(1 for event in events if event.get("kind") == "acceptance" and event.get("passed")),
        "acceptance_denominator": 1,
        "unjustified_halts": sum(
            1
            for event in events
            if event.get("kind") == "halt" and not event.get("justified", False)
        ),
        "user_corrections": sum(1 for event in events if event.get("kind") == "user-correction"),
        "replays": sum(1 for event in events if event.get("kind") == "replay"),
        "attempted_git_during_build": sum(
            1
            for event in events
            if event.get("kind") == "git"
            and event.get("phase") == "build"
            and event.get("attempted", False)
        ),
        "rejected_scope_expansion": sum(
            1 for event in events if event.get("kind") == "scope" and event.get("value") == "rejected-expansion"
        ),
        "verification_reruns": sum(
            1 for event in events if event.get("kind") == "verification" and event.get("rerun", False)
        ),
    }
    checks = {
        "acceptance": metrics["acceptance_passed"] == metrics["acceptance_denominator"],
        "required_events": all(
            any(event.get("kind") == kind and event.get("value") == value for event in events)
            for kind, value in fixture.required
        ),
        "no_unjustified_halt": metrics["unjustified_halts"] == 0,
        "no_user_correction": metrics["user_corrections"] == 0,
        "no_replay": metrics["replays"] == 0,
        "no_build_git": metrics["attempted_git_during_build"] == 0,
    }
    return ScenarioResult(
        fixture.id,
        all(checks.values()),
        fixture.expected,
        metrics,
        checks,
    )


def run_scenarios() -> tuple[ScenarioResult, ...]:
    _validate_fixture_ids(SCENARIO_FIXTURES, SCENARIO_IDS, "scenario")
    return tuple(evaluate_scenario(fixture) for fixture in SCENARIO_FIXTURES)


def run_regressions(root: Path = ROOT) -> tuple[RegressionResult, ...]:
    _validate_fixture_ids(REGRESSION_FIXTURES, REC_IDS, "regression")
    results: list[RegressionResult] = []
    for fixture in REGRESSION_FIXTURES:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", fixture.test],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        results.append(
            RegressionResult(
                fixture.id,
                fixture.test,
                completed.returncode == 0,
                completed.returncode,
            )
        )
    return tuple(results)


def build_report(root: Path = ROOT, *, include_regressions: bool = True) -> dict[str, Any]:
    scenarios = run_scenarios()
    regressions = run_regressions(root) if include_regressions else ()
    scenario_metrics: dict[str, dict[str, int]] = {}
    for name in (
        "unjustified_halts",
        "user_corrections",
        "replays",
        "attempted_git_during_build",
        "rejected_scope_expansion",
        "verification_reruns",
    ):
        scenario_metrics[name] = {
            "measured": sum(result.metrics[name] for result in scenarios),
            "denominator": len(scenarios),
        }
    measures = {
        "acceptance_pass_rate": {
            "passed": sum(result.passed for result in scenarios),
            "denominator": len(scenarios),
        },
        **scenario_metrics,
    }
    return {
        "schema_version": 1,
        "settings": {
            "fixture_inputs": "versioned constants in scripts/agent_loop_eval.py",
            "regression_command": "python -m unittest <fixture selector>",
            "scenario_command": "python scripts/agent_loop_eval.py --scenarios-only",
            "model": "unmeasured; deterministic fixtures are model-neutral",
            "permissions": "local filesystem only; no external writes",
            "platform": "host platform for the command; no cross-platform inference",
        },
        "regressions": {
            "passed": sum(result.passed for result in regressions),
            "denominator": len(REGRESSION_FIXTURES),
            "results": [asdict(result) for result in regressions],
        },
        "scenarios": {
            "passed": sum(result.passed for result in scenarios),
            "denominator": len(scenarios),
            "results": [asdict(result) for result in scenarios],
        },
        "scenario_metrics": scenario_metrics,
        "measures": measures,
        "unmeasured_live_fields": [
            "live-agent acceptance and halt behavior",
            "user corrections, replays, and token/time usage in a client",
            "Codex hook trust and resume/compact delivery",
            "unified-exec completion as observed by a client",
            "browser interaction and copy behavior",
            "model rankings or client compatibility claims",
            "POSIX/native-platform results not run on this host",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the complete report as JSON")
    parser.add_argument(
        "--scenarios-only",
        action="store_true",
        help="run only fixed scenario traces; do not spawn unittest subprocesses",
    )
    args = parser.parse_args(argv)
    report = build_report(include_regressions=not args.scenarios_only)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            "deterministic regressions: "
            f"{report['regressions']['passed']}/{report['regressions']['denominator']} passed"
        )
        print(
            "deterministic scenarios: "
            f"{report['scenarios']['passed']}/{report['scenarios']['denominator']} passed"
        )
        for name, values in report["scenario_metrics"].items():
            print(f"{name}: {values['measured']}/{values['denominator']}")
    regressions_ok = args.scenarios_only or (
        report["regressions"]["passed"] == report["regressions"]["denominator"]
    )
    return 0 if regressions_ok and report["scenarios"]["passed"] == report["scenarios"]["denominator"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
