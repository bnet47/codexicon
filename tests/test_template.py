from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".codex" / "hooks" / "codex_hook.py"
HOOKS_JSON = ROOT / ".codex" / "hooks.json"
VALIDATOR = ROOT / "scripts" / "validate_template.py"
TEST_TEMP_ROOT = ROOT / ".codex-state" / "tests"
HOOK_SPEC = importlib.util.spec_from_file_location("codex_hook_test_module", HOOK)
assert HOOK_SPEC and HOOK_SPEC.loader
HOOK_MODULE = importlib.util.module_from_spec(HOOK_SPEC)
sys.modules[HOOK_SPEC.name] = HOOK_MODULE
HOOK_SPEC.loader.exec_module(HOOK_MODULE)
CODEX_HOOK = HOOK_MODULE
VALIDATOR_SPEC = importlib.util.spec_from_file_location("template_validator_under_test", VALIDATOR)
assert VALIDATOR_SPEC and VALIDATOR_SPEC.loader
TEMPLATE_VALIDATOR = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(TEMPLATE_VALIDATOR)
AGENT_LOOP_EVAL_PATH = ROOT / "scripts" / "agent_loop_eval.py"
AGENT_LOOP_SPEC = importlib.util.spec_from_file_location(
    "agent_loop_eval_under_test", AGENT_LOOP_EVAL_PATH
)
assert AGENT_LOOP_SPEC and AGENT_LOOP_SPEC.loader
AGENT_LOOP_EVAL = importlib.util.module_from_spec(AGENT_LOOP_SPEC)
sys.modules[AGENT_LOOP_SPEC.name] = AGENT_LOOP_EVAL
AGENT_LOOP_SPEC.loader.exec_module(AGENT_LOOP_EVAL)


def make_test_directory() -> Path:
    path = TEST_TEMP_ROOT / uuid.uuid4().hex
    path.mkdir(parents=True, exist_ok=False)
    return path


def policy_completion_gate(
    *, acceptance_covered: bool, evidence_fresh: bool, open_issue: str | None
) -> bool:
    """Pure fixture for the documented acceptance/freshness completion gate."""

    return acceptance_covered and evidence_fresh and open_issue is None


def policy_evidence_is_fresh(*, now: int, expires_at: int) -> bool:
    """Model the documented exclusive expiry boundary without a runtime."""

    return now < expires_at


def policy_ship_requirements(ceiling: str) -> set[str]:
    """Return the policy-level evidence required by an authorized Ship ceiling."""

    if ceiling not in {"commit-only", "publish", "merge", "deploy"}:
        raise ValueError(f"unsupported Ship ceiling: {ceiling}")
    requirements = {"commit", "lint", "test", "security", "tracked_history"}
    if ceiling in {"publish", "merge", "deploy"}:
        requirements.update({"release", "publication_evidence", "explicit_authority"})
    return requirements


def policy_related_scope_allowed(
    *,
    small: bool,
    reversible: bool,
    directly_related: bool,
    within_boundary: bool,
    escalation_trigger: bool = False,
) -> bool:
    """Model the documented related-scope gate without adding a runtime."""

    return (
        small
        and reversible
        and directly_related
        and within_boundary
        and not escalation_trigger
    )


REQUIRED_SCOPE_ESCALATION_SIGNALS = (
    "authority",
    "product behavior",
    "schema",
    "data shape",
    "security posture",
    "irreversible",
    "destructive",
    "credentials",
    "production",
    "migration",
    "external write",
    "publication",
    "deployment",
    "legal",
    "compliance",
    "material architecture",
)


class TemplateValidationTests(unittest.TestCase):
    def test_repository_invariants(self) -> None:
        result = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_implementation_entry_points_share_contract_and_writer_policy(self) -> None:
        skill_paths = {
            name: ROOT / ".agents" / "skills" / name / "SKILL.md"
            for name in (
                "discover",
                "spec",
                "brainstorm",
                "write-plan",
                "quick",
                "execute-plan",
                "autonomous-build",
            )
        }
        skills = {name: path.read_text(encoding="utf-8") for name, path in skill_paths.items()}

        for name in skills:
            with self.subTest(skill=name):
                self.assertIn("SPEC.md", skills[name])
                self.assertIn("TASKS.md", skills[name])
                self.assertIn("RESUME_ACTIVE", skills[name])
                self.assertRegex(skills[name], r"Pure explanations.*read-only reviews")

        self.assertIn("root `SPEC.md`", skills["discover"])
        self.assertIn("root `SPEC.md`", skills["spec"])
        self.assertIn("historical brief", skills["spec"])
        self.assertIn("spec-check", skills["brainstorm"])
        self.assertIn("tasks-next --json", skills["write-plan"])
        self.assertIn("second execution engine", skills["execute-plan"])
        self.assertIn("do not invent a task ID", skills["quick"])
        self.assertIn("no `TASKS.md`", skills["autonomous-build"])

        contract = (ROOT / "docs" / "build-contracts.md").read_text(encoding="utf-8")
        self.assertIn("One contract and one Build vocabulary", contract)
        for state in ("TODO", "ACTIVE", "BLOCKED", "DONE", "READY", "RESUME_ACTIVE", "COMPLETE", "INVALID"):
            self.assertIn(f"`{state}`", contract)

        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        implementer = (ROOT / ".codex" / "agents" / "implementer.toml").read_text(encoding="utf-8")
        self.assertNotIn("[PROJECT_NAME]", agents)
        self.assertIn("default sole writer", agents)
        self.assertIn("explicitly chooses sequential implementation", implementer)

        for path in (ROOT / "README.md", ROOT / "START_HERE.md"):
            content = path.read_text(encoding="utf-8")
            with self.subTest(path=path):
                self.assertIn("SPEC.md", content)
                self.assertIn("TASKS.md", content)
                self.assertIn("suggested-next-prompt", content)

        codex_docs = (ROOT / "docs" / "codex.md").read_text(encoding="utf-8")
        self.assertIn("runnable", codex_docs.lower())

    def test_bounded_self_improvement_uses_validated_profile_guidance(self) -> None:
        skill = (ROOT / ".agents" / "skills" / "autonomous-build" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        implementer = (ROOT / ".codex" / "agents" / "implementer.toml").read_text(
            encoding="utf-8"
        )
        documentation = (ROOT / "docs" / "capabilities.md").read_text(encoding="utf-8")
        policy = (ROOT / ".codex" / "capabilities.toml").read_text(encoding="utf-8")

        budget_contract = (
            "`one iteration` means one implement + focused-check + critique pass.",
            "`one review cycle` means one independent reviewer pass and one correction round.",
            "`one failed attempt` means one failed implementation/focused-check pass requiring recovery.",
            "`max_minutes` starts at task activation and includes implementation, checks, review, and correction.",
            "These counters are local guidance, not a runtime.",
        )
        early_stop = (
            "if acceptance is met and fresh relevant verification is present, stop before any optional refinement"
        )
        ship_boundaries = (
            "Git",
            "branches",
            "worktrees",
            "staging",
            "commits",
            "pushes",
            "pull requests",
            "releases",
            "deployments",
            "publication",
            "migrations",
            "credentials",
            "destructive data work",
            "production actions",
            "external writes",
        )

        for content in (skill, implementer, documentation):
            with self.subTest(content=content[:32]):
                normalized = " ".join(content.split())
                for phrase in budget_contract:
                    self.assertIn(phrase, normalized)
                self.assertIn(early_stop, normalized.lower())
                self.assertIn("There is no background runtime or second task engine", normalized)
                self.assertIn("explicit `$ship`/human boundaries", normalized)
                for boundary in ship_boundaries:
                    self.assertIn(boundary, normalized)
                for phrase in (
                    "task-specific acceptance rubric",
                    "weakest important aspect",
                    "plateau",
                    "repeated failure",
                    "budget",
                    "human-owned boundary",
                    "SPEC.md",
                    "TASKS.md",
                ):
                    self.assertIn(phrase, normalized)

        skill_loop = " ".join(skill.split("## Loop", 1)[1].split("## Local-first rule", 1)[0].split()).lower()
        self.assertLess(skill_loop.index("run focused verification"), skill_loop.index(early_stop))
        self.assertLess(skill_loop.index(early_stop), skill_loop.index("otherwise, critique"))
        self.assertLess(skill_loop.index("otherwise, critique"), skill_loop.index("refine only"))
        for content in (documentation, implementer):
            normalized = " ".join(content.split()).lower()
            self.assertLess(normalized.index(early_stop), normalized.index("otherwise, critique"))

        for budget in ("max_iterations", "max_review_cycles", "max_failed_attempts", "max_minutes"):
            with self.subTest(budget=budget):
                self.assertIn(budget, policy)
                self.assertIn(budget, skill)
                self.assertIn(budget, implementer)
                self.assertIn(budget, documentation)

        for boundary in ("Git", "deployment", "credentials", "publication", "external writes"):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, documentation)
                self.assertIn(boundary, implementer)

        self.assertIn("There is no background runtime", " ".join(documentation.split()))
        self.assertIn("second task engine", documentation)
        self.assertIn("Build is Git-free", implementer)

    def test_selective_independent_review_uses_validated_profile_guidance(self) -> None:
        skill = (ROOT / ".agents" / "skills" / "review" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        reviewer = (ROOT / ".codex" / "agents" / "reviewer.toml").read_text(
            encoding="utf-8"
        )
        autonomous_build = (ROOT / ".agents" / "skills" / "autonomous-build" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        documentation = (ROOT / "docs" / "capabilities.md").read_text(encoding="utf-8")
        policy = (ROOT / ".codex" / "capabilities.toml").read_text(encoding="utf-8")

        capabilities = json.loads(
            subprocess.check_output(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "codexicon.py"),
                    "capabilities",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
            )
        )
        self.assertEqual(capabilities["selected_profile"], "balanced")
        balanced_review = capabilities["profiles"]["balanced"]["review"]
        self.assertEqual(balanced_review["required_risk_levels"], ["medium", "high", "critical"])
        self.assertEqual(balanced_review["changed_files_threshold"], 4)
        for signal in ("public_api", "security", "architecture", "test_complexity"):
            with self.subTest(signal=signal):
                self.assertIs(balanced_review[f"review_on_{signal}"], True)

        self.assertRegex(reviewer, r'(?m)^sandbox_mode\s*=\s*"read-only"\s*$')

        trigger_phrases = (
            "required_risk_levels",
            "changed_files_threshold",
            "review_on_public_api",
            "review_on_security",
            "review_on_architecture",
            "review_on_test_complexity",
        )
        for content in (skill, autonomous_build, reviewer, documentation):
            normalized = " ".join(content.split()).lower()
            with self.subTest(trigger_contract=content[:32]):
                self.assertIn("canonical `$autonomous-build` route", normalized)
                self.assertIn("any configured trigger matches", normalized)
                for phrase in trigger_phrases:
                    self.assertIn(phrase, normalized)
                self.assertIn("must not narrow", normalized)
                self.assertRegex(
                    normalized,
                    r"required_risk_levels.*changed_files_threshold.*public api.*security.*architecture.*test-complexity.*review_on_test_complexity",
                )
                self.assertIn(" or ", normalized)
                self.assertRegex(normalized, r"exactly one .*reviewer pass and one correction round")
                self.assertIn("stable finding id", normalized)
                self.assertIn("exactly one", normalized)
                self.assertIn("every finding", normalized)
                self.assertIn("trivial low-risk work", normalized)

        plan = (ROOT / "agent_docs" / "plans" / "2026-09-11-capability-layer-plan.md").read_text(
            encoding="utf-8"
        )
        plan_normalized = " ".join(plan.split()).lower()
        self.assertIn("when any configured trigger in the selected profile matches", plan_normalized)
        self.assertIn(
            "trivial low-risk work below the changed-file threshold with no enabled signal is exempt",
            plan_normalized,
        )
        self.assertNotIn("every bounded implementation task receives an independent", plan_normalized)

        for content in (skill, reviewer, documentation):
            normalized = " ".join(content.split()).lower()
            with self.subTest(content=content[:32]):
                for phrase in (
                    ".codex/capabilities.toml",
                    "capabilities --json",
                    "required_risk_levels",
                    "changed_files_threshold",
                    "review_on_public_api",
                    "review_on_security",
                    "review_on_architecture",
                    "review_on_test_complexity",
                    "trivial low-risk work",
                    "read-only",
                    "accepted",
                    "fixed",
                    "rejected",
                    "not_applicable",
                    "git",
                    "$ship",
                ):
                    self.assertIn(phrase, normalized)

        for policy_key in (
            "required_risk_levels =",
            "changed_files_threshold =",
            "review_on_public_api =",
            "review_on_security =",
            "review_on_architecture =",
            "review_on_test_complexity =",
        ):
            with self.subTest(policy_key=policy_key):
                self.assertIn(policy_key, policy)

        for risk_level in ("medium", "high", "critical"):
            with self.subTest(risk_level=risk_level):
                self.assertIn(risk_level, policy)

        combined = "\n".join((skill, reviewer, documentation)).lower()
        self.assertIn("one sequential build writer", combined)
        self.assertIn("background runtime", combined)
        self.assertIn("automatic publication", combined)

    def test_verification_tiers_preserve_freshness_and_ship_authority(self) -> None:
        build_contracts = (ROOT / "docs" / "build-contracts.md").read_text(encoding="utf-8")
        codex_docs = (ROOT / "docs" / "codex.md").read_text(encoding="utf-8")
        autonomous_build = (
            ROOT / ".agents" / "skills" / "autonomous-build" / "SKILL.md"
        ).read_text(encoding="utf-8")
        ship = (ROOT / ".agents" / "skills" / "ship" / "SKILL.md").read_text(
            encoding="utf-8"
        )

        tier_section = re.search(
            r"## Verification tiers and Stop outcomes\n\n(?P<body>.*?)(?=\n## Project-local capability policy)",
            build_contracts,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(tier_section)
        assert tier_section is not None
        tier_rows = re.findall(
            r"^\| (Focused iteration|Build completion|Ship) \| ([^|]+) \|",
            tier_section.group("body"),
            flags=re.MULTILINE,
        )
        self.assertEqual(
            [name for name, _owner in tier_rows],
            ["Focused iteration", "Build completion", "Ship"],
        )
        self.assertIn("current Build writer", tier_rows[0][1])
        self.assertIn("primary Build writer", tier_rows[1][1])
        self.assertIn("explicitly authorized human/$ship workflow", tier_rows[2][1])

        evidence_start = build_contracts.index("Completion evidence is a JSON receipt")
        evidence_end = build_contracts.index("`tasks-done` refuses", evidence_start)
        evidence_contract = build_contracts[evidence_start:evidence_end]
        normalized_evidence_contract = " ".join(evidence_contract.split())
        for field in (
            "verification_tier",
            "selected_profile",
            "window_minutes",
            "expires_at",
            "responsible_owner",
            "source_digest",
            "contract_digest",
        ):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", evidence_contract)
        self.assertLess(
            evidence_contract.index("window_minutes"),
            evidence_contract.index("expires_at"),
        )
        self.assertIn("must be copied from the selected profile", normalized_evidence_contract)
        self.assertIn("responsible for rerunning", normalized_evidence_contract)
        self.assertIn("metadata never bypasses", normalized_evidence_contract)

        for content in (build_contracts, autonomous_build):
            stop_start = content.index("Stop precedence is deterministic")
            stop_section = " ".join(content[stop_start:].split()).lower()
            self.assertLess(
                stop_section.index("completion gate"),
                stop_section.index("bounded improvement"),
            )
            self.assertLess(
                stop_section.index("bounded improvement"),
                stop_section.index("stop as `accepted`"),
            )
            self.assertIn("open in-scope correctness, safety, or evidence issue", stop_section)
            self.assertTrue(
                "no open issue can be ignored" in stop_section
                or "cannot be ignored" in stop_section
            )
            self.assertIn("actionable finding reopens the gate", stop_section)

        ship_start = ship.index("## Acceptance by authorization ceiling")
        ship_end = ship.index("## 1. Verify", ship_start)
        acceptance = " ".join(ship[ship_start:ship_end].split())
        commit_only = acceptance[: acceptance.index("- **Publish, merge, or deploy:**")]
        publish_actions = acceptance[acceptance.index("- **Publish, merge, or deploy:**") :]
        self.assertIn("does not require release", commit_only)
        self.assertIn("publication evidence", commit_only)
        self.assertIn("must not pressure", commit_only)
        self.assertNotIn("release identity and publication evidence are required", commit_only)
        self.assertIn("Release identity and publication evidence are required", publish_actions)
        self.assertIn("explicit authority", publish_actions)

        verify_start = ship.index("For commit-only, run the narrowest feature checks")
        publish_verify_start = ship.index("For publish, merge, or deploy, also run:", verify_start)
        commit_verify = ship[verify_start:publish_verify_start]
        publish_verify = ship[publish_verify_start:]
        self.assertIn("python scripts/security_scan.py --mode ship", commit_verify)
        self.assertNotIn("python scripts/release.py check", commit_verify)
        self.assertIn("python scripts/release.py check --tag vX.Y.Z", publish_verify)
        self.assertIn("fails closed", publish_verify)

        for content in (codex_docs, autonomous_build, ship):
            normalized = " ".join(content.split()).lower()
            with self.subTest(content=content[:32]):
                for phrase in (
                    "selected profile",
                    "source",
                    "contract",
                    "freshness",
                    "expires_at",
                    "responsible owner",
                    "protected credential paths",
                ):
                    self.assertIn(phrase, normalized)

        for content in (codex_docs, autonomous_build):
            self.assertIn("second task engine", " ".join(content.split()).lower())

    def test_policy_decisions_enforce_completion_freshness_and_ship_ceiling(self) -> None:
        build_contracts = (ROOT / "docs" / "build-contracts.md").read_text(encoding="utf-8")
        codex_docs = (ROOT / "docs" / "codex.md").read_text(encoding="utf-8")
        autonomous_build = (ROOT / ".agents" / "skills" / "autonomous-build" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(
            policy_completion_gate(
                acceptance_covered=True,
                evidence_fresh=True,
                open_issue=None,
            )
        )
        for acceptance_covered, evidence_fresh in ((False, True), (True, False)):
            with self.subTest(acceptance_covered=acceptance_covered, evidence_fresh=evidence_fresh):
                self.assertFalse(
                    policy_completion_gate(
                        acceptance_covered=acceptance_covered,
                        evidence_fresh=evidence_fresh,
                        open_issue=None,
                    )
                )
        for issue in ("correctness", "safety", "evidence"):
            with self.subTest(issue=issue):
                self.assertFalse(
                    policy_completion_gate(
                        acceptance_covered=True,
                        evidence_fresh=True,
                        open_issue=issue,
                    )
                )

        self.assertTrue(policy_evidence_is_fresh(now=99, expires_at=100))
        self.assertFalse(policy_evidence_is_fresh(now=100, expires_at=100))
        self.assertFalse(policy_evidence_is_fresh(now=101, expires_at=100))

        commit_only = policy_ship_requirements("commit-only")
        self.assertIn("commit", commit_only)
        self.assertIn("tracked_history", commit_only)
        self.assertNotIn("release", commit_only)
        self.assertNotIn("publication_evidence", commit_only)
        for ceiling in ("publish", "merge", "deploy"):
            with self.subTest(ceiling=ceiling):
                requirements = policy_ship_requirements(ceiling)
                self.assertIn("explicit_authority", requirements)
                self.assertIn("publication_evidence", requirements)
                self.assertIn("release", requirements)
        with self.assertRaises(ValueError):
            policy_ship_requirements("publish-without-authority")

        ship = (ROOT / ".agents" / "skills" / "ship" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        normalized_ship = " ".join(ship.split()).lower()
        self.assertIn("commit-only request is accepted", normalized_ship)
        self.assertIn("does not require release identity, publication evidence", normalized_ship)
        self.assertIn("release identity and publication evidence are required", normalized_ship)
        self.assertIn("require explicit authority", normalized_ship)
        self.assertIn("must not be inferred", normalized_ship)
        commit_only_section = ship[
            ship.index("- **Commit-only:**") : ship.index("- **Publish, merge, or deploy:**")
        ]
        normalized_commit_only = " ".join(commit_only_section.split()).lower()
        for requirement in (
            "full lint",
            "test",
            "filesystem-security",
            "tracked/history checks",
        ):
            with self.subTest(commit_only_requirement=requirement):
                self.assertIn(requirement, normalized_commit_only)
        self.assertIn("does not require release identity, publication evidence", normalized_commit_only)
        self.assertNotIn("release identity and publication evidence are required", normalized_commit_only)

        autonomous_tiers = autonomous_build[
            autonomous_build.index("## Verification tiers and Stop outcomes") : autonomous_build.index(
                "## Local-first rule"
            )
        ]
        normalized_autonomous = " ".join(autonomous_tiers.split()).lower()
        self.assertIn("for commit-only ship", normalized_autonomous)
        self.assertIn("without release or publication evidence", normalized_autonomous)
        self.assertIn("for publish, merge, or deploy", normalized_autonomous)
        self.assertIn("only when that exact authority was explicitly requested", normalized_autonomous)
        self.assertNotIn(
            "the explicitly authorized human/$ship workflow owns ship; it adds full lint/test/security, release/publication",
            normalized_autonomous,
        )

        for content in (build_contracts, codex_docs):
            normalized = " ".join(content.split()).lower()
            self.assertIn("commit-only", normalized)
            self.assertIn("explicitly requested", normalized)
            self.assertIn("never infer or pressure", normalized)

    def test_decision_journal_is_append_only_and_scope_is_bounded(self) -> None:
        journal = (ROOT / "agent_docs" / "decisions" / "README.md").read_text(
            encoding="utf-8"
        )
        documentation = (ROOT / "docs" / "capabilities.md").read_text(encoding="utf-8")
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        autonomous_build = (
            ROOT / ".agents" / "skills" / "autonomous-build" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn("agent_docs/decisions/", journal)
        self.assertIn("append-only", journal.lower())
        self.assertRegex(journal, r"ADR-NNN-short-title\.md")
        for section in ("## Context", "## Decision or assumption"):
            with self.subTest(section=section):
                self.assertIn(section, journal)
        for field in (
            "Rationale",
            "Alternatives considered",
            "Impact",
            "Owner",
            "Date",
            "Status",
            "Evidence",
        ):
            with self.subTest(field=field):
                self.assertIn(field, journal)
        self.assertIn("never rewrite or delete an accepted record", journal.lower())
        self.assertIn("new record", journal.lower())

        for content in (documentation, agents, autonomous_build):
            normalized = " ".join(content.split()).lower()
            with self.subTest(content=content[:24]):
                self.assertIn("agent_docs/decisions/", normalized)
                self.assertIn("rationale", normalized)
                self.assertIn("alternatives", normalized)
                self.assertIn("impact", normalized)
                self.assertIn("owner", normalized)
                self.assertIn("date", normalized)
                self.assertIn("status", normalized)
                self.assertIn("evidence", normalized)
                self.assertIn("small", normalized)
                self.assertIn("reversible", normalized)
                self.assertIn("directly related", normalized)
                self.assertIn("declared system boundary", normalized)
                for trigger in REQUIRED_SCOPE_ESCALATION_SIGNALS:
                    self.assertIn(trigger, normalized)
                self.assertIn("explicitly escalate", normalized)

        self.assertTrue(
            policy_related_scope_allowed(
                small=True,
                reversible=True,
                directly_related=True,
                within_boundary=True,
            )
        )
        for condition in (
            "small",
            "reversible",
            "directly_related",
            "within_boundary",
        ):
            kwargs = {
                "small": True,
                "reversible": True,
                "directly_related": True,
                "within_boundary": True,
            }
            kwargs[condition] = False
            with self.subTest(condition=condition):
                self.assertFalse(policy_related_scope_allowed(**kwargs))
        for trigger in REQUIRED_SCOPE_ESCALATION_SIGNALS:
            with self.subTest(escalation_trigger=trigger):
                self.assertFalse(
                    policy_related_scope_allowed(
                        small=True,
                        reversible=True,
                        directly_related=True,
                        within_boundary=True,
                        escalation_trigger=True,
                    )
                )

    def test_capability_matrix_has_reproducible_evidence_fields_and_boundaries(self) -> None:
        matrix = (ROOT / "docs" / "evals" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )
        required_fields = (
            "Observed version/date",
            "Client / platform",
            "Trust / source",
            "Denominator",
            "Expected outcome",
            "Observed outcome",
            "Hook trust",
            "Resume/compact",
            "Completion",
            "Native verification",
            "Status",
        )
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(f"| {field} |", matrix)

        self.assertIn("T-026/R-026/I-020/A-026", matrix)
        self.assertIn("Raw command or tool names", matrix)
        self.assertIn("never establish client compatibility", matrix)
        self.assertIn("Explicitly unmeasured or unsupported", matrix)

        capability_section = matrix.split("## Capability matrix", 1)[1].split(
            "The only measured support statement", 1
        )[0]
        table_lines = [
            line for line in capability_section.splitlines() if line.startswith("|")
        ]
        self.assertEqual(len(table_lines), 7)  # header, separator, and five surfaces
        header = [cell.strip() for cell in table_lines[0].strip("|").split("|")]
        expected_header = [
            "Surface",
            "Observed version/date",
            "Client / platform",
            "Trust / source",
            "Denominator",
            "Expected outcome",
            "Observed outcome",
            "Hook trust",
            "Resume/compact",
            "Completion",
            "Native verification",
            "Status",
        ]
        self.assertEqual(header, expected_header)
        for line in table_lines[2:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            with self.subTest(surface=cells[0]):
                self.assertEqual(len(cells), len(expected_header))
                self.assertTrue(all(cells), line)
                self.assertRegex(cells[1], r"\d{4}-\d{2}-\d{2}|no trial|no run")
                self.assertRegex(cells[4], r"\b(?:0|1|10|13)\b")
                self.assertIn(cells[11], {
                    "measured local evidence only",
                    "unmeasured live-client behavior",
                    "unsupported/not run",
                })

        local_row = next(line for line in table_lines if "Deterministic template harness" in line)
        self.assertIn("Python 3.13.13 / 2026-09-11", local_row)
        self.assertIn("REC 13/13", local_row)
        self.assertIn("journeys 10/10", local_row)
        self.assertIn("unified client completion unmeasured", local_row)
        self.assertIn("Windows-host checks measured", local_row)

        live_rows = [
            line for line in table_lines
            if any(surface in line for surface in ("Codex CLI live attempt", "Codex desktop/local client", "Browser/live client"))
        ]
        self.assertEqual(len(live_rows), 3)
        for row in live_rows:
            with self.subTest(row=row[:40]):
                self.assertIn("Unmeasured", row)
                self.assertNotIn("measured live-client compatibility", row.lower())

        scenario_section = matrix.split("## Deterministic scenario evidence", 1)[1].split(
            "Reproduce the scenario evidence", 1
        )[0]
        shared_context = scenario_section.split("Shared scenario observation context:", 1)[1].split(
            "| Scenario |", 1
        )[0]
        for field in (
            "Observed version/date",
            "Client / platform",
            "Trust / source",
            "Hook trust",
            "Resume/compact",
            "Completion",
            "Native verification",
            "Explicit unmeasured fields",
        ):
            with self.subTest(shared_field=field):
                self.assertIn(f"| {field} |", shared_context)
        self.assertIn("Value for all ten fixed traces", shared_context)
        scenario_rows = [
            line for line in scenario_section[scenario_section.index("| Scenario |"):].splitlines()
            if line.startswith("|") and not line.startswith("|---")
        ]
        self.assertEqual(len(scenario_rows), 11)  # header plus ten fixed traces
        scenario_ids = [
            re.match(r"\| `([^`]+)` \|", line).group(1)
            for line in scenario_rows[1:]
            if re.match(r"\| `([^`]+)` \|", line)
        ]
        self.assertEqual(tuple(scenario_ids), tuple(AGENT_LOOP_EVAL.SCENARIO_IDS))
        for line in scenario_rows[1:]:
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            self.assertEqual(cells[1], "1")
            self.assertTrue(cells[2] and cells[3] and cells[4])

    def test_eval_documents_repeat_provenance_and_unmeasured_client_semantics(self) -> None:
        matrix = (ROOT / "docs" / "evals" / "capability-matrix.md").read_text(
            encoding="utf-8"
        )
        benchmark = (ROOT / "docs" / "evals" / "agent-loop-benchmark.md").read_text(
            encoding="utf-8"
        )
        live = (ROOT / "docs" / "evals" / "live-agent-results-2026-09-11.md").read_text(
            encoding="utf-8"
        )
        report = AGENT_LOOP_EVAL.build_report(ROOT)
        scenario_results = {
            result["id"]: result for result in report["scenarios"]["results"]
        }

        scenario_block = benchmark.split("The ten journeys are the executable scenario IDs below.", 1)[1].split(
            "### Deterministic results", 1
        )[0]
        benchmark_rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in scenario_block.splitlines()
            if line.startswith("| `")
        ]
        self.assertEqual(
            tuple(row[0].strip("`") for row in benchmark_rows),
            tuple(AGENT_LOOP_EVAL.SCENARIO_IDS),
        )
        self.assertEqual(len(benchmark_rows), report["scenarios"]["denominator"])
        for row in benchmark_rows:
            result = scenario_results[row[0].strip("`")]
            self.assertEqual(int(row[1]), result["metrics"]["acceptance_denominator"])
            self.assertEqual(row[3].lower(), "pass" if result["acceptance_passed"] else "fail")
            self.assertEqual(row[4].lower(), "pass" if result["passed"] else "fail")

        matrix_scenario_block = matrix.split("| Scenario |", 1)[1].split(
            "Reproduce the scenario evidence", 1
        )[0]
        matrix_rows = [
            [cell.strip() for cell in line.strip("|").split("|")]
            for line in matrix_scenario_block.splitlines()
            if line.startswith("| `")
        ]
        self.assertEqual(
            tuple(row[0].strip("`") for row in matrix_rows),
            tuple(AGENT_LOOP_EVAL.SCENARIO_IDS),
        )
        for row in matrix_rows:
            result = scenario_results[row[0].strip("`")]
            self.assertEqual(int(row[1]), result["metrics"]["acceptance_denominator"])
            self.assertEqual(row[3].lower().startswith("passed"), result["passed"])

        measures_block = benchmark.split("| Measure |", 1)[1].split(
            "These are fixture outcomes", 1
        )[0]
        measure_rows = {
            row[0]: (int(row[1]), int(row[2].split()[0]))
            for row in (
                [cell.strip() for cell in line.strip("|").split("|")]
                for line in measures_block.splitlines()
                if line.startswith("| ") and not line.startswith("|---")
            )
            if len(row) >= 3 and row[0] not in {"Measure", "---"}
        }
        expected_measures = {
            "REC acceptance pass rate": report["regressions"],
            "Journey acceptance pass rate": report["measures"]["acceptance_pass_rate"],
            "Journey overall fixture pass rate": {
                "passed": report["scenarios"]["passed"],
                "denominator": report["scenarios"]["denominator"],
            },
        }
        for name, expected in expected_measures.items():
            with self.subTest(measure=name):
                self.assertEqual(
                    measure_rows[name], (expected["passed"], expected["denominator"])
                )

        for document in (benchmark, live):
            normalized = " ".join(document.split()).lower()
            with self.subTest(document=document[:32]):
                for phrase in (
                    "observed version/date",
                    "client/platform",
                    "trust/source",
                    "denominator",
                    "expected outcome",
                    "observed outcome",
                    "hook trust",
                    "resume/compact",
                    "completion",
                    "native verification",
                    "unmeasured",
                ):
                    self.assertIn(phrase, normalized)
                self.assertIn("raw command/tool names", normalized)
                self.assertIn("not compatibility evidence", normalized)

        benchmark_results = benchmark.split("### Deterministic results", 1)[1]
        self.assertIn("Python 3.13.13", benchmark_results)
        self.assertIn("REC 13/13", benchmark_results)
        self.assertIn("journey acceptance 10/10", benchmark_results)
        self.assertIn("Build-time Git 0/10", benchmark_results)
        self.assertIn("POSIX/native-platform run unmeasured", benchmark_results)

        self.assertIn("1 paired trial planned", live)
        self.assertIn("guided arm 0 started", live)
        self.assertIn("Direct default-provider arm timed out", live)
        self.assertIn("guided arm was not started", live)
        self.assertIn("no client-facing completion was observed", live)
        self.assertIn("does not establish codex cli, desktop, browser", " ".join(live.split()).lower())

    def test_current_writer_policy_excludes_historical_worktree_writer_guidance(self) -> None:
        current_guidance_paths = [
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "START_HERE.md",
            ROOT / "docs" / "agent-patterns.md",
            ROOT / "docs" / "build-contracts.md",
            ROOT / "docs" / "codex.md",
            *(ROOT / ".agents" / "skills").glob("*/SKILL.md"),
            ROOT / ".agents" / "skills" / "engineering-loop" / "agents" / "openai.yaml",
            *(ROOT / ".codex" / "agents").glob("*.toml"),
        ]
        current_guidance = "\n".join(
            path.read_text(encoding="utf-8") for path in current_guidance_paths
        )
        adr = (
            ROOT / "agent_docs" / "decisions" /
            "ADR-004-sequential-build-writers-and-release-boundary.md"
        ).read_text(encoding="utf-8")

        self.assertIn("Build uses one sequential writer in the current checkout", adr)
        self.assertIn("Read-only research and review may run independently", adr)
        self.assertIn("remain Ship actions", adr)
        self.assertIn("one sequential writer", current_guidance)
        self.assertIn("read-only research and review", current_guidance.lower())
        self.assertIn("parallel read-only research and review", current_guidance.lower())
        self.assertIn("Never run concurrent writers", current_guidance)
        self.assertIn("shared checkout", current_guidance)
        self.assertIn("$ship", current_guidance)
        for action in (
            "branches",
            "worktrees",
            "commits",
            "pushes",
            "pull requests",
            "releases",
            "deployments",
            "external writes",
        ):
            with self.subTest(action=action):
                self.assertIn(action, current_guidance.lower())

        self.assertNotRegex(
            current_guidance,
            r"(?is)(?:independent|parallel)\s+(?:implementation\s+)?writers?.{0,120}"
            r"(?:managed|isolated)\s+worktrees?",
        )
        self.assertNotRegex(current_guidance.lower(), r"parallel writers")

    def test_optional_goal_mode_preserves_portable_resume_contract(self) -> None:
        codex_docs = (ROOT / "docs" / "codex.md").read_text(encoding="utf-8")
        build_contracts = (ROOT / "docs" / "build-contracts.md").read_text(encoding="utf-8")
        start_here = (ROOT / "START_HERE.md").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        codex_lower = codex_docs.lower()
        for phrase in (
            "Goal mode",
            "optional",
            "client-dependent",
            "active-turn chaining",
            "compaction recovery",
            "restart after termination",
            "cancellation",
            "TASKS.md",
            "authoritative",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase.lower(), codex_lower)

        for document in (build_contracts, start_here, readme):
            with self.subTest(document=document[:24]):
                self.assertIn("Goal mode", document)
                self.assertIn("plain-session", document.lower())
                self.assertIn("Git", document)
                self.assertIn("deployment", document)

        combined = "\n".join((codex_docs, build_contracts, start_here, readme)).lower()
        self.assertIn("unmeasured", combined)
        self.assertIn("no daemon", combined)
        self.assertNotIn("third-party memory service is required", combined)

    def test_playbook_implementation_routing_is_complete_and_readable(self) -> None:
        source = (ROOT / "docs" / "repo-template-playbook.source.html").read_text(encoding="utf-8")
        skill_details_match = re.search(
            r"const skillDetails = \{(?P<body>.*?)\n      \};",
            source,
            re.DOTALL,
        )
        self.assertIsNotNone(skill_details_match)
        assert skill_details_match is not None
        skill_details = skill_details_match.group("body")

        selector_values = set(re.findall(r'<option value="([^"]+)">', source))
        detail_keys = {
            quoted or bare
            for quoted, bare in re.findall(
                r"(?m)^\s*(?:'([^']+)'|([a-z][a-z0-9-]*)): \{",
                skill_details,
            )
        }
        self.assertEqual(selector_values, detail_keys)
        self.assertIn("<option value=\"autonomous-build\">$autonomous-build</option>", source)
        self.assertRegex(
            source,
            r"command: '\$quick · \$execute-plan · \$autonomous-build'",
        )

        expected = {
            "autonomous-build": {
                "title": "$autonomous-build",
                "when": ("authorized implementation", "task register"),
                "produces": ("fresh evidence",),
                "next": ("$review", "$ship"),
                "prompt": ("$autonomous-build", "TASKS.md", "SPEC.md"),
            },
            "engineering-loop": {
                "title": "$engineering-loop",
                "when": ("read-only research", "review"),
                "produces": ("read-only findings", "primary agent"),
                "next": ("$autonomous-build",),
                "prompt": ("$engineering-loop", "do not edit"),
            },
            "execute-plan": {
                "title": "$execute-plan",
                "when": ("durable plan", "task register"),
                "produces": ("$autonomous-build", "task evidence"),
                "next": ("$autonomous-build",),
                "prompt": ("$execute-plan", "SPEC.md", "TASKS.md", "$autonomous-build"),
            },
        }
        for name, fields in expected.items():
            with self.subTest(skill=name):
                block_match = re.search(
                    rf"(?ms)^\s*(?:'{re.escape(name)}'|{re.escape(name)}): \{{(?P<block>.*?)^\s*\}},",
                    skill_details,
                )
                self.assertIsNotNone(block_match)
                assert block_match is not None
                block = block_match.group("block")
                self.assertIn(f"title: '{fields['title']}'", block)
                for field in ("when", "produces", "next", "prompt"):
                    self.assertRegex(block, rf"(?m)^\s*{field}: '[^']*'")
                    for expected_text in fields[field]:
                        self.assertIn(expected_text, block)

        engineering_block = re.search(
            r"(?ms)^\s*'engineering-loop': \{(?P<block>.*?)^\s*\},",
            skill_details,
        )
        self.assertIsNotNone(engineering_block)
        assert engineering_block is not None
        self.assertNotIn("$autonomous-build Implement", engineering_block.group("block"))

    def test_capability_policy_is_synchronized_across_public_surfaces(self) -> None:
        policy = (ROOT / ".codex" / "capabilities.toml").read_text(encoding="utf-8")
        implementer = (ROOT / ".codex" / "agents" / "implementer.toml").read_text(
            encoding="utf-8"
        )
        reviewer = (ROOT / ".codex" / "agents" / "reviewer.toml").read_text(
            encoding="utf-8"
        )
        public_paths = (
            ROOT / "README.md",
            ROOT / "START_HERE.md",
            ROOT / "docs" / "index.md",
            ROOT / "docs" / "agent-patterns.md",
            ROOT / "docs" / "upgrading.md",
            ROOT / "docs" / "repo-template-playbook.source.html",
            ROOT / "docs" / "repo-template-playbook.html",
        )
        public_documents = {
            path.name: " ".join(path.read_text(encoding="utf-8").split()).lower()
            for path in public_paths
        }
        required_public_terms = (
            ".codex/capabilities.toml",
            "capabilities --json",
            "selected profile",
            "focused",
            "build",
            "ship",
            "read-only",
            "changed-file",
            "public-api",
            "security",
            "architecture",
            "test-complexity",
            "accepted",
            "fixed",
            "rejected",
            "not_applicable",
            "agent_docs/decisions/",
            "small",
            "reversible",
            "directly related",
            "declared system boundary",
            "capability-matrix.md",
            "unmeasured",
            "daemon",
            "scheduler",
            "external-write",
            "publication",
        )
        for name, content in public_documents.items():
            with self.subTest(document=name):
                for term in required_public_terms:
                    self.assertIn(term, content)

        normalized_policy = " ".join(policy.split()).lower()
        for budget in (
            "max_iterations",
            "max_review_cycles",
            "max_failed_attempts",
            "max_minutes",
        ):
            self.assertIn(budget, normalized_policy)
        for content in (implementer, reviewer):
            normalized = " ".join(content.split()).lower()
            with self.subTest(role_or_policy=content[:32]):
                self.assertIn("capabilities.toml", normalized)
                self.assertIn("capabilities --json", normalized)
        normalized_implementer = " ".join(implementer.split()).lower()
        for budget in (
            "max_iterations",
            "max_review_cycles",
            "max_failed_attempts",
            "max_minutes",
        ):
            self.assertIn(budget, normalized_implementer)
        normalized_reviewer = " ".join(reviewer.split()).lower()
        self.assertIn("capabilities.toml", normalized_reviewer)
        self.assertIn("capabilities --json", normalized_reviewer)
        self.assertIn("read-only", normalized_reviewer)

        source = (ROOT / "docs" / "repo-template-playbook.source.html").read_text(
            encoding="utf-8"
        )
        standalone = (ROOT / "docs" / "repo-template-playbook.html").read_text(
            encoding="utf-8"
        )
        self.assertIn('href="#capability-heading"', source)
        self.assertIn('id="capability-heading"', source)
        self.assertIn("capability-heading", standalone)
        render_check = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "render_playbook.py"), "--check"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(render_check.returncode, 0, render_check.stdout + render_check.stderr)

    def test_docs_index_security_model_link_targets_existing_heading(self) -> None:
        index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        codex_docs_path = ROOT / "docs" / "codex.md"
        codex_docs = codex_docs_path.read_text(encoding="utf-8")

        match = re.search(r"\[security model\]\(([^)]+)\)", index)
        self.assertIsNotNone(match)
        assert match is not None
        raw_target = match.group(1)
        target, fragment = raw_target.split("#", 1)
        target_path = (ROOT / "docs" / target).resolve()
        self.assertEqual(target_path, codex_docs_path.resolve())
        self.assertTrue(target_path.is_file())
        self.assertIn("### Credential and Git gates", codex_docs)
        self.assertEqual(fragment, "credential-and-git-gates")

    def test_durable_guidance_policy_detects_brittle_external_assumptions(self) -> None:
        samples = {
            "Use gpt-5.4 for every review.": "named or versioned model choice",
            "Keep the report at most five lines.": "fixed workflow threshold",
            "This costs $2 per million input tokens.": "token-unit pricing",
            "Charge $2 / 1M tokens.": "token-unit pricing",
            "Offer it at half price.": "fixed pricing discount",
            "Compact at 50% of the context.": "fixed context threshold",
            "Compact when 100k tokens remain.": "fixed context threshold",
            "Handle roughly one to three files.": "fixed workflow count",
            "Use three agents.": "fixed workflow count",
        }
        for content, expected in samples.items():
            with self.subTest(content=content):
                self.assertIn(
                    expected,
                    TEMPLATE_VALIDATOR.durable_guidance_findings(content),
                )

        self.assertEqual(
            TEMPLATE_VALIDATOR.durable_guidance_findings(
                "Choose current capabilities for the task and keep the report compact."
            ),
            [],
        )

    def test_durable_guidance_scope_excludes_project_documents(self) -> None:
        root = make_test_directory()
        self.addCleanup(shutil.rmtree, root, True)
        (root / "AGENTS.md").write_text("Use gpt-5.4 for every review.\n", encoding="utf-8")
        brief = root / "agent_docs" / "briefs" / "model-comparison.md"
        brief.parent.mkdir(parents=True)
        brief.write_text("Compare gpt-5.4 with the current alternatives.\n", encoding="utf-8")
        original_root = TEMPLATE_VALIDATOR.ROOT
        TEMPLATE_VALIDATOR.ROOT = root
        try:
            guidance = TEMPLATE_VALIDATOR.guidance_files()
            guidance_names = {path.relative_to(root).as_posix() for path in guidance}
        finally:
            TEMPLATE_VALIDATOR.ROOT = original_root

        self.assertIn("AGENTS.md", guidance_names)
        self.assertNotIn("agent_docs/briefs/model-comparison.md", guidance_names)
        self.assertIn(
            "named or versioned model choice",
            TEMPLATE_VALIDATOR.durable_guidance_findings(
                (root / "AGENTS.md").read_text(encoding="utf-8")
            ),
        )

    def test_template_discovery_prunes_generated_and_protected_files_before_reads(self) -> None:
        root = make_test_directory()
        self.addCleanup(shutil.rmtree, root, True)
        safe = root / "application.md"
        protected = root / ".env.local"
        generated = root / "dist" / "generated.md"
        safe.write_text("Application notes.\n", encoding="utf-8")
        protected.write_text("protected-but-not-a-secret\n", encoding="utf-8")
        generated.parent.mkdir()
        generated.write_text("Use gpt-5.4 for generated output.\n", encoding="utf-8")

        files, findings = TEMPLATE_VALIDATOR.safe_discover_files(
            root,
            suffixes=TEMPLATE_VALIDATOR.TEXT_SUFFIXES,
        )

        self.assertEqual(files, [safe])
        self.assertEqual(findings, [])

        original_read_text = Path.read_text

        def guarded_read(path: Path, *args, **kwargs):
            if path in {protected, generated}:
                raise AssertionError(f"unsafe read: {path}")
            return original_read_text(path, *args, **kwargs)

        original_root = TEMPLATE_VALIDATOR.ROOT
        TEMPLATE_VALIDATOR.ROOT = root
        try:
            with mock.patch.object(Path, "read_text", new=guarded_read):
                self.assertEqual(TEMPLATE_VALIDATOR.read_template_text(safe), "Application notes.\n")
                with self.assertRaises(OSError):
                    TEMPLATE_VALIDATOR.read_template_text(protected)
                with self.assertRaises(OSError):
                    TEMPLATE_VALIDATOR.read_template_text(generated)
        finally:
            TEMPLATE_VALIDATOR.ROOT = original_root

    def test_toml_fallback_preserves_nested_mcp_sections(self) -> None:
        config = self.temp_config(
            '[mcp_servers.docs]\nenabled = false\n'
            'default_tools_approval_mode = "prompt"\n'
        )
        original_tomllib = TEMPLATE_VALIDATOR.tomllib
        TEMPLATE_VALIDATOR.tomllib = None
        try:
            parsed = TEMPLATE_VALIDATOR.parse_template_toml(config)
        finally:
            TEMPLATE_VALIDATOR.tomllib = original_tomllib
        self.assertIn("docs", parsed["mcp_servers"])
        self.assertTrue(TEMPLATE_VALIDATOR.has_active_mcp_servers(parsed))

    def test_workflow_actions_require_full_commit_shas(self) -> None:
        mutable = "steps:\n  - uses: owner/action@feature\n"
        mutable_flow = "steps:\n  - { name: Build, uses: owner/action@main }\n"
        mutable_inline_flow = "steps: [{ uses: owner/action@develop }]\n"
        mutable_compact_flow = "steps: [uses: owner/action@release]\n"
        mixed_inline_flow = (
            "steps: [{ uses: owner/pinned@0123456789abcdef0123456789abcdef01234567 }, "
            "{ uses: owner/mutable@main }]\n"
        )
        mutable_container = "steps:\n  - uses: docker://alpine:3.22\n"
        pinned = (
            "steps:\n"
            '  - uses: "owner/action@0123456789abcdef0123456789abcdef01234567" # v1.2.3\n'
            "  - uses: ./local-action\n"
            "  - uses: docker://alpine@sha256:"
            + "a" * 64
            + "\n"
        )
        self.assertEqual(TEMPLATE_VALIDATOR.mutable_action_references(mutable), ["owner/action@feature"])
        self.assertEqual(
            TEMPLATE_VALIDATOR.mutable_action_references(mutable_flow),
            ["owner/action@main"],
        )
        self.assertEqual(
            TEMPLATE_VALIDATOR.mutable_action_references(mutable_inline_flow),
            ["owner/action@develop"],
        )
        self.assertEqual(
            TEMPLATE_VALIDATOR.mutable_action_references(mutable_compact_flow),
            ["owner/action@release"],
        )
        self.assertEqual(
            TEMPLATE_VALIDATOR.mutable_action_references(mixed_inline_flow),
            ["owner/mutable@main"],
        )
        self.assertEqual(
            TEMPLATE_VALIDATOR.mutable_action_references(mutable_container),
            ["docker://alpine:3.22"],
        )
        self.assertEqual(TEMPLATE_VALIDATOR.mutable_action_references(pinned), [])

    def test_trufflehog_action_and_scanner_versions_must_match(self) -> None:
        workflow = (
            '- uses: "trufflesecurity/trufflehog@0123456789abcdef0123456789abcdef01234567" # v3.97.0\n'
            "  with:\n"
            "    version: 3.96.0\n"
        )
        self.assertTrue(TEMPLATE_VALIDATOR.trufflehog_version_mismatch(workflow))
        self.assertFalse(
            TEMPLATE_VALIDATOR.trufflehog_version_mismatch(workflow.replace("3.96.0", "3.97.0"))
        )
        self.assertTrue(
            TEMPLATE_VALIDATOR.trufflehog_version_mismatch(workflow.replace(" # v3.97.0", ""))
        )
        masked = workflow.replace(
            "  with:\n    version: 3.96.0\n",
            "  env:\n    version: 3.97.0\n  with:\n    version: 3.96.0\n",
        )
        self.assertTrue(TEMPLATE_VALIDATOR.trufflehog_version_mismatch(masked))
        self.assertTrue(
            TEMPLATE_VALIDATOR.trufflehog_version_mismatch(
                workflow.replace(
                    "0123456789abcdef0123456789abcdef01234567",
                    "v3.97.0",
                ).replace("3.96.0", "3.97.0")
            )
        )

    def test_simulated_trufflehog_bump_keeps_action_pin_and_versions_coupled(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        bumped = workflow.replace(
            "bcfcf73aaf4759d4dadc2783177c245a02792318 # v3.97.0",
            "0123456789abcdef0123456789abcdef01234567 # v3.98.0",
        ).replace("version: 3.97.0", "version: 3.98.0")

        self.assertNotEqual(bumped, workflow)
        self.assertEqual(TEMPLATE_VALIDATOR.mutable_action_references(bumped), [])
        self.assertFalse(TEMPLATE_VALIDATOR.trufflehog_version_mismatch(bumped))

    def temp_config(self, content: str) -> Path:
        directory = make_test_directory()
        self.addCleanup(shutil.rmtree, directory, True)
        path = directory / "config.toml"
        path.write_text(content, encoding="utf-8")
        return path

    def test_every_registered_hook_bootstraps_from_a_subdirectory_without_git(self) -> None:
        hooks = json.loads(HOOKS_JSON.read_text(encoding="utf-8"))
        expected_matchers = {
            "SessionStart": ["startup|clear", "resume|compact"],
            "PreToolUse": ["^Bash$|^apply_patch$|^Read$|^read_file$|^read_text_file$|Edit|Write"],
            "PostToolUse": ["^apply_patch$|Edit|Write", "^Bash$"],
            "PreCompact": [None],
            "Stop": [None],
            "SessionEnd": [None],
        }
        self.assertEqual(set(hooks["hooks"]), set(expected_matchers))

        for event, groups in hooks["hooks"].items():
            self.assertEqual([group.get("matcher") for group in groups], expected_matchers[event])
            for group_index, group in enumerate(groups):
                for handler_index, handler in enumerate(group["hooks"]):
                    with self.subTest(event=event, group=group_index, handler=handler_index):
                        command = handler["commandWindows"] if os.name == "nt" else handler["command"]
                        namespace = uuid.uuid4().hex
                        namespace_digest = hashlib.sha256(namespace.encode("utf-8")).hexdigest()[:20]
                        temp_dir = ROOT / ".codex-state" / "namespaces" / namespace_digest
                        try:
                            env = os.environ.copy()
                            env["CODEX_STATE_NAMESPACE"] = namespace
                            env.pop("CODEX_STATE_FILE", None)
                            env.pop("CODEX_STATE_DIR", None)
                            payload = {"session_id": "bootstrap"}
                            if event == "SessionStart":
                                payload["source"] = "startup"
                            elif event == "PreToolUse":
                                payload.update(
                                    tool_name="Bash",
                                    tool_use_id=f"bootstrap-pre-{group_index}-{handler_index}",
                                    tool_input={"command": "git status"},
                                )
                            elif event == "PostToolUse":
                                payload["tool_use_id"] = (
                                    f"bootstrap-post-{group_index}-{handler_index}"
                                )
                                if "apply_patch" in (group.get("matcher") or ""):
                                    payload.update(
                                        tool_name="apply_patch",
                                        tool_input={
                                            "command": "*** Begin Patch\n*** Update File: README.md\n*** End Patch"
                                        },
                                    )
                                else:
                                    payload.update(
                                        tool_name="Bash",
                                        tool_input={"command": "git status"},
                                        tool_response="",
                                    )
                            elif event == "PreCompact":
                                payload["trigger"] = "manual"
                            elif event == "Stop":
                                payload.update(
                                    turn_id="turn-bootstrap",
                                    stop_hook_active=False,
                                )
                                initialized = subprocess.run(
                                    [sys.executable, str(HOOK), "session-start"],
                                    cwd=ROOT,
                                    input=json.dumps({"session_id": "bootstrap"}),
                                    text=True,
                                    capture_output=True,
                                    env=env,
                                    check=False,
                                )
                                self.assertEqual(
                                    initialized.returncode,
                                    0,
                                    initialized.stdout + initialized.stderr,
                                )
                            elif event == "SessionEnd":
                                payload["reason"] = "other"
                                self.assertLessEqual(handler["timeout"], 3)

                            result = subprocess.run(
                                command,
                                cwd=ROOT / "tests",
                                input=json.dumps(payload),
                                text=True,
                                capture_output=True,
                                env=env,
                                shell=True,
                                check=False,
                            )
                        finally:
                            shutil.rmtree(temp_dir, ignore_errors=True)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CodexHookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state_namespace = uuid.uuid4().hex
        namespace_digest = hashlib.sha256(self.state_namespace.encode("utf-8")).hexdigest()[:20]
        self.temp_dir = ROOT / ".codex-state" / "namespaces" / namespace_digest
        self.temp_dir.mkdir(parents=True, exist_ok=False)
        self.addCleanup(shutil.rmtree, self.temp_dir, True)
        session_digest = hashlib.sha256(b"s1").hexdigest()[:20]
        self.state_file = self.temp_dir / f"session-{session_digest}.json"

    def run_hook(self, action: str, payload: dict | None = None, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["CODEX_STATE_NAMESPACE"] = self.state_namespace
        env.pop("CODEX_STATE_FILE", None)
        env.pop("CODEX_STATE_DIR", None)
        return subprocess.run(
            [sys.executable, str(HOOK), action, *extra],
            cwd=ROOT,
            input=json.dumps(payload or {}),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def receipt(self, check: str) -> str:
        result = self.run_hook("emit-success", None, check)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def record_success(self, check: str) -> None:
        suffix = "sh"
        command = f"./scripts/{check}.{suffix}"
        result = self.run_hook(
            "record-shell",
            {"session_id": "s1", "tool_input": {"command": command}, "tool_response": self.receipt(check)},
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manager_verify_consumes_lint_and_test_receipts(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        response = self.receipt("lint") + self.receipt("test")
        recorded = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "python scripts/codexicon.py verify"},
                "tool_response": response,
            },
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        allowed = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def session_summary(self, session_id: str = "s1") -> dict:
        digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
        path = self.temp_dir / "summaries" / f"session-{digest}.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_secret_policy_blocks_operator_bypasses_but_allows_example(self) -> None:
        blocked_commands = [
            "Get-Content .env.local",
            "cat<.env",
            "type<.env",
            "Get-Content .key",
            "Get-Content secrets/token.txt",
            "Get-Content credentials.json",
            "Get-Content $HOME/.npmrc",
            "Get-Content ~/.pypirc",
            "cat ~/.netrc",
            "cat ~/.aws/credentials",
            "cat ~/.ssh/id_ed25519",
            "cat ~/.kube/config",
            "cat ~/.docker/config.json",
            "Get-Content ~/.config/gh/hosts.yml",
            "Get-Content ~/.terraform.d/credentials.tfrc.json",
            "Get-ChildItem Env:",
            "printenv",
            "env",
            "Write-Output $env:OPENAI_API_KEY",
            "echo $AWS_SECRET_ACCESS_KEY",
            "printenv GITHUB_TOKEN",
            "export -p",
            "declare -x",
            "compgen -e",
            "python -c \"import os; print(dict(os.environ))\"",
            "node -e \"console.log(JSON.stringify(process.env))\"",
            "env > dump.txt",
            "printenv 1>>dump.txt",
            "set 1>dump.txt",
            "export -p > dump.txt",
            "declare -x 1>dump.txt",
            "compgen -e > dump.txt",
            "Get-Content *",
            "Get-Content .*",
            "cat .??*",
            "head *",
            "Select-String token *",
            "& Get-Content *",
            "command cat .??*",
        ]
        for command in blocked_commands:
            with self.subTest(command=command):
                result = self.run_hook(
                    "protect-secrets",
                    {"tool_name": "Bash", "tool_input": {"command": command}},
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("Blocked protected credential path", result.stderr)

        allowed = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": "Get-Content .env.example"}},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

        for command in ("printenv PATH", "Write-Output $env:PATH", "set -e"):
            with self.subTest(allowed_command=command):
                safe_environment_read = self.run_hook(
                    "protect-secrets",
                    {"tool_name": "Bash", "tool_input": {"command": command}},
                )
                self.assertEqual(safe_environment_read.returncode, 0, safe_environment_read.stderr)

        protected_read_tool = self.run_hook(
            "protect-secrets",
            {"tool_name": "Read", "tool_input": {"file_path": ".ssh/id_rsa"}},
        )
        self.assertEqual(protected_read_tool.returncode, 2)

        safe_search = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": r"rg -n '\.env' README.md"}},
        )
        protected_search = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": r"rg -n '\.env' .env.local"}},
        )
        broad_search = self.run_hook(
            "protect-secrets",
            {"tool_name": "Bash", "tool_input": {"command": r"rg -n '\.env' ."}},
        )
        execution_bearing_search = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "Bash",
                "tool_input": {
                    "command": 'rg --pre="cat .env" password README.md',
                },
            },
        )
        unknown_option_search = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "Bash",
                "tool_input": {"command": r"rg --unknown '\.env' README.md"},
            },
        )
        self.assertEqual(safe_search.returncode, 0, safe_search.stderr)
        self.assertEqual(protected_search.returncode, 2)
        self.assertEqual(broad_search.returncode, 2)
        self.assertEqual(execution_bearing_search.returncode, 2)
        self.assertEqual(unknown_option_search.returncode, 2)

        documentation_patch = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: README.md\n@@\n+Never read .env.local.\n*** End Patch"
                },
            },
        )
        protected_patch = self.run_hook(
            "protect-secrets",
            {
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: .env.local\n@@\n-old\n+new\n*** End Patch"
                },
            },
        )
        self.assertEqual(documentation_patch.returncode, 0, documentation_patch.stderr)
        self.assertEqual(protected_patch.returncode, 2)

    def test_expired_and_malformed_receipts_are_pruned(self) -> None:
        receipt_dir = self.temp_dir / "receipts"
        receipt_dir.mkdir(parents=True)
        expired = receipt_dir / "expired.json"
        malformed = receipt_dir / "malformed.json"
        expired.write_text(
            json.dumps({"check": "lint", "created_epoch": 1, "schema_version": 1}),
            encoding="utf-8",
        )
        malformed.write_text("not-json", encoding="utf-8")

        current = self.run_hook("emit-success", None, "lint")

        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertFalse(expired.exists())
        self.assertFalse(malformed.exists())
        self.assertEqual(len(list(receipt_dir.glob("*.json"))), 1)

    def test_state_namespace_cannot_select_a_filesystem_path(self) -> None:
        external = Path(tempfile.mkdtemp(prefix="codexicon-state-escape-"))
        self.addCleanup(shutil.rmtree, external, True)
        env = os.environ.copy()
        env["CODEX_STATE_NAMESPACE"] = str(external / "chosen-state")
        env["CODEX_STATE_FILE"] = str(external / "state.json")
        env["CODEX_STATE_DIR"] = str(external)

        result = subprocess.run(
            [sys.executable, str(HOOK), "session-start"],
            cwd=ROOT,
            input=json.dumps({"session_id": "untrusted-path", "source": "startup"}),
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

        namespace_digest = hashlib.sha256(env["CODEX_STATE_NAMESPACE"].encode("utf-8")).hexdigest()[:20]
        safe_directory = ROOT / ".codex-state" / "namespaces" / namespace_digest
        self.addCleanup(shutil.rmtree, safe_directory, True)
        session_digest = hashlib.sha256(b"untrusted-path").hexdigest()[:20]
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((safe_directory / f"session-{session_digest}.json").is_file())
        self.assertFalse((external / "state.json").exists())

    def test_state_file_symlink_escape_is_rejected(self) -> None:
        external = Path(tempfile.mkdtemp(prefix="codexicon-state-target-"))
        self.addCleanup(shutil.rmtree, external, True)
        target = external / "state.json"
        target.write_text('{"sentinel": true}\n', encoding="utf-8")
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.state_file.symlink_to(target)
        except OSError:
            self.skipTest("symbolic links are unavailable")

        with mock.patch.object(CODEX_HOOK, "STATE_FILE", self.state_file):
            with self.assertRaises(CODEX_HOOK.StateLoadError):
                CODEX_HOOK.load_state_unlocked(strict=True)

        self.assertEqual(target.read_text(encoding="utf-8"), '{"sentinel": true}\n')

    def test_session_summary_records_supported_lifecycle_fields(self) -> None:
        started = self.run_hook("session-start", {"session_id": "s1", "source": "startup"})
        self.assertEqual(started.returncode, 0, started.stderr)

        first_turn = {"session_id": "s1", "turn_id": "turn-1"}
        self.assertEqual(self.run_hook("record-stop", {**first_turn, "stop_hook_active": False}).returncode, 0)
        self.assertEqual(self.run_hook("record-stop", {**first_turn, "stop_hook_active": False}).returncode, 0)
        self.assertEqual(
            self.run_hook(
                "record-stop",
                {"session_id": "s1", "turn_id": "turn-2", "stop_hook_active": False},
            ).returncode,
            0,
        )
        self.assertEqual(
            self.run_hook("record-stop", {**first_turn, "stop_hook_active": False}).returncode,
            0,
        )
        self.assertEqual(
            self.run_hook("record-compact", {"session_id": "s1", "trigger": "manual"}).returncode,
            0,
        )
        self.assertEqual(self.session_summary()["turn_count"], 0)
        self.assertEqual(
            self.run_hook("end-session", {"session_id": "s1", "reason": "other"}).returncode,
            0,
        )

        summary = self.session_summary()
        self.assertEqual(summary["turn_count"], 2)
        self.assertEqual(summary["compact_count"], 1)
        self.assertIsNotNone(summary["session_started_at"])
        self.assertIsNotNone(summary["session_ended_at"])
        self.assertEqual(summary["usage"]["availability"], "not_exposed_by_hook_payloads")
        self.assertIsNone(summary["usage"]["input_tokens"])
        self.assertIsNone(summary["usage"]["cached_input_tokens"])
        self.assertIsNone(summary["usage"]["reasoning_output_tokens"])

    def test_session_telemetry_ignores_missing_optional_fields(self) -> None:
        self.assertEqual(self.run_hook("record-turn", {}).returncode, 0)
        self.assertEqual(self.run_hook("record-compact", {}).returncode, 0)
        self.assertEqual(self.run_hook("end-session", {}).returncode, 0)

    def test_telemetry_skips_busy_state_lock_without_blocking(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                started = time.monotonic()
                result = self.run_hook("record-turn", {"session_id": "s1", "turn_id": "busy"})
                elapsed = time.monotonic() - started
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 1.0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["turn_count"], 0)

    def test_session_start_fails_fast_when_state_lock_is_busy(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        original = json.loads(self.state_file.read_text(encoding="utf-8"))
        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                started = time.monotonic()
                result = self.run_hook("session-start", {"session_id": "s1", "source": "clear"})
                elapsed = time.monotonic() - started
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertEqual(result.returncode, 2)
        self.assertIn("initialization was not recorded", result.stderr)
        self.assertLess(elapsed, 1.0)
        current = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(current["session_started_at"], original["session_started_at"])

    def test_write_invalidation_survives_busy_state_lock(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        self.assertEqual(
            self.run_hook(
                "record-write",
                {"session_id": "s1", "tool_input": {"file_path": "src/before.py"}},
            ).returncode,
            0,
        )
        self.record_success("lint")
        self.record_success("test")
        self.assertEqual(
            self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False}).returncode,
            0,
        )

        busy_write = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "busy-write",
            "tool_input": {"file_path": "src/after.py"},
        }
        prepared = self.run_hook("prepare-tool", busy_write)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)

        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                result = self.run_hook("record-write", busy_write)
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertEqual(result.returncode, 2)
        self.assertIn("write invalidation remains pending", result.stderr)
        stale = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(stale["lint_passed"])
        self.assertTrue(stale["test_passed"])
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))

        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint, tests", blocked.stderr)
        reconciled = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertFalse(reconciled["lint_passed"])
        self.assertFalse(reconciled["test_passed"])
        self.assertFalse(list((self.temp_dir / "pending-writes").glob("*.json")))

        self.record_success("lint")
        self.record_success("test")
        allowed = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_pending_write_intent_blocks_checks_and_stop_until_completion(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "active-write",
            "tool_input": {"file_path": "src/example.py"},
        }
        prepared = self.run_hook("prepare-tool", payload)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)

        self.record_success("lint")
        self.record_success("test")
        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))

        completed = self.run_hook("record-write", payload)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.record_success("lint")
        self.record_success("test")
        allowed = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_pretool_intent_waits_for_state_snapshot_lock(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "serialized-intent",
            "tool_input": {"file_path": "src/example.py"},
        }
        results: list[subprocess.CompletedProcess[str]] = []

        original_state_file = CODEX_HOOK.STATE_FILE
        CODEX_HOOK.STATE_FILE = self.state_file
        try:
            with CODEX_HOOK.state_lock() as acquired:
                self.assertTrue(acquired)
                worker = threading.Thread(
                    target=lambda: results.append(self.run_hook("prepare-tool", payload))
                )
                worker.start()
                time.sleep(0.2)
                self.assertTrue(worker.is_alive())
                self.assertFalse(list((self.temp_dir / "pending-writes").glob("*.json")))
            worker.join(timeout=5)
        finally:
            CODEX_HOOK.STATE_FILE = original_state_file

        self.assertFalse(worker.is_alive())
        self.assertEqual(results[0].returncode, 0, results[0].stderr)
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))

    def test_unusable_pending_write_storage_fails_closed(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        pending_directory = self.temp_dir / "pending-writes"
        pending_directory.write_text("not a directory", encoding="utf-8")
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "blocked-storage",
            "tool_input": {"file_path": "src/example.py"},
        }

        prepared = self.run_hook("prepare-tool", payload)
        self.assertEqual(prepared.returncode, 2)
        stopped = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(stopped.returncode, 2)
        self.assertIn("pending write storage is not a trusted directory", stopped.stderr)

    def test_pending_write_storage_symlink_is_rejected(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        external = self.temp_dir / "external"
        external.mkdir()
        try:
            (self.temp_dir / "pending-writes").symlink_to(external, target_is_directory=True)
        except OSError:
            self.skipTest("symbolic links are unavailable")
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "symlink-storage",
            "tool_input": {"file_path": "src/example.py"},
        }

        prepared = self.run_hook("prepare-tool", payload)
        self.assertEqual(prepared.returncode, 2)
        self.assertFalse(list(external.iterdir()))
        stopped = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(stopped.returncode, 2)
        self.assertIn("pending write storage is not a trusted directory", stopped.stderr)

    def test_session_reset_preserves_pending_write_intent(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "reset-write",
            "tool_input": {"file_path": "src/example.py"},
        }
        self.assertEqual(self.run_hook("prepare-tool", payload).returncode, 0)

        reset = self.run_hook("session-start", {"session_id": "s1", "source": "clear"})
        self.assertEqual(reset.returncode, 0, reset.stderr)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["has_writes"])
        self.assertEqual(state["active_write_intents"], 1)
        self.assertTrue(list((self.temp_dir / "pending-writes").glob("*.json")))
        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)

    def test_documentation_marker_on_malformed_state_requires_tests(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        self.state_file.write_text("{", encoding="utf-8")
        payload = {
            "session_id": "s1",
            "tool_name": "apply_patch",
            "tool_use_id": "malformed-doc-write",
            "tool_input": {"file_path": "README.md"},
        }
        self.assertEqual(self.run_hook("prepare-tool", payload).returncode, 0)
        recorded = self.run_hook("record-write", payload)
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["test_required"])

        self.record_success("lint")
        blocked = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": False},
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: tests", blocked.stderr)

    def test_summary_write_is_serialized_with_authoritative_state(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        original_paths = (
            CODEX_HOOK.STATE_FILE,
            CODEX_HOOK.STATE_DIR,
            CODEX_HOOK.RECEIPT_DIR,
            CODEX_HOOK.SUMMARY_DIR,
        )
        CODEX_HOOK.STATE_FILE = self.state_file
        CODEX_HOOK.STATE_DIR = self.temp_dir
        CODEX_HOOK.RECEIPT_DIR = self.temp_dir / "receipts"
        CODEX_HOOK.SUMMARY_DIR = self.temp_dir / "summaries"
        original_summary = CODEX_HOOK.write_session_summary
        concurrent_results: list[subprocess.CompletedProcess[str]] = []

        def inspect_lock(state: dict) -> None:
            concurrent_results.append(
                self.run_hook("record-turn", {"session_id": "s1", "turn_id": "late"})
            )
            original_summary(state)

        try:
            with mock.patch.object(CODEX_HOOK, "write_session_summary", side_effect=inspect_lock):
                self.assertEqual(CODEX_HOOK.end_session({"session_id": "s1"}), 0)
        finally:
            (
                CODEX_HOOK.STATE_FILE,
                CODEX_HOOK.STATE_DIR,
                CODEX_HOOK.RECEIPT_DIR,
                CODEX_HOOK.SUMMARY_DIR,
            ) = original_paths

        self.assertEqual(concurrent_results[0].returncode, 0, concurrent_results[0].stderr)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertEqual(state["turn_count"], 0)
        self.assertEqual(self.session_summary()["turn_count"], 0)

    def test_malformed_numeric_telemetry_degrades_safely(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        state["compact_count"] = float("inf")
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        compact = self.run_hook("record-compact", {"session_id": "s1"})
        ended = self.run_hook("end-session", {"session_id": "s1"})

        self.assertEqual(compact.returncode, 0, compact.stderr)
        self.assertEqual(ended.returncode, 0, ended.stderr)
        self.assertEqual(self.session_summary()["compact_count"], 1)

    def test_malformed_verification_epochs_fail_closed(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        state.update(
            has_writes=True,
            last_write_epoch="not-a-number",
            lint_passed=True,
            lint_epoch=float("nan"),
        )
        self.state_file.write_text(json.dumps(state), encoding="utf-8")

        result = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Missing or stale: lint", result.stderr)

    def test_common_read_only_shell_commands_do_not_require_verification(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        read_only_commands = [
            "find . -maxdepth 1",
            "tree",
            "grep needle README.md",
            'sed -n "1,5p" README.md',
            "wc -l README.md",
            "Get-ChildItem | Select-Object Name",
            "python scripts/codexicon.py inspect target",
            "python scripts/codexicon.py adopt target",
            "python scripts/codexicon.py update --root target --source source",
            "python scripts/codexicon.py doctor --root .",
            "python scripts/codexicon.py resume --root .",
            "python3 ./scripts/codexicon.py doctor --root .",
            "python .\\scripts\\codexicon.py resume --root .",
        ]
        for command in read_only_commands:
            with self.subTest(command=command):
                result = self.run_hook(
                    "record-shell",
                    {"session_id": "s1", "tool_input": {"command": command}, "tool_response": ""},
                )
                self.assertEqual(result.returncode, 0, result.stderr)

        allowed = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_common_inspection_does_not_invalidate_fresh_verification(self) -> None:
        commands = [
            "find . -maxdepth 1",
            "tree",
            "grep needle README.md",
            'sed -n "1,5p" README.md',
            "wc -l README.md",
            "python scripts/codexicon.py inspect target",
            "python scripts/codexicon.py adopt target",
            "python scripts/codexicon.py update --root target --source source",
            "python scripts/codexicon.py doctor --root .",
            "python scripts/codexicon.py resume --root .",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.run_hook("session-start", {"session_id": "s1"})
                self.run_hook(
                    "record-write",
                    {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
                )
                self.record_success("lint")
                self.record_success("test")
                recorded = self.run_hook(
                    "record-shell",
                    {"session_id": "s1", "tool_input": {"command": command}, "tool_response": ""},
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                allowed = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_git_inspection_does_not_preserve_build_verification(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.record_success("lint")
        self.record_success("test")
        recorded = self.run_hook(
            "record-shell",
            {"session_id": "s1", "tool_input": {"command": "git status"}},
        )
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        blocked = self.run_hook(
            "verify-stop", {"session_id": "s1", "stop_hook_active": False}
        )
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint, tests", blocked.stderr)

    def test_read_only_commands_with_write_options_still_invalidate_verification(self) -> None:
        commands = [
            "git diff --output=owned.txt",
            "find . -delete",
            "find . -exec python generate.py {} ;",
            "sed -i s/old/new/ README.md",
            "sed -n 'w owned.txt' README.md",
            "tree -o owned.txt",
            "python scripts/codexicon.py adopt target --apply",
            "python scripts/codexicon.py adopt target --a",
            "python scripts/codexicon.py adopt target --app",
            "python scripts/codexicon.py update --root target --source source --apply",
            "python scripts/codexicon.py update --root target --source source --appl",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.run_hook("session-start", {"session_id": "s1"})
                self.run_hook(
                    "record-write",
                    {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
                )
                self.record_success("lint")
                self.record_success("test")
                recorded = self.run_hook(
                    "record-shell",
                    {"session_id": "s1", "tool_input": {"command": command}, "tool_response": ""},
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                blocked = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(blocked.returncode, 2)

    def test_execution_bearing_read_only_prefixes_invalidate_verification(self) -> None:
        commands = [
            "git status $(python generate.py)",
            "Get-Content README.md $(python generate.py)",
            "rg needle README.md `python generate.py`",
            "git status & python generate.py",
            "Get-Content README.md (python generate.py)",
            "rg --pre 'python generate.py' needle README.md",
            "cat <(python generate.py)",
            "git branch new-branch",
            "git branch -D old-branch",
            "git branch --edit-description",
            "git show --output=owned.txt HEAD",
            "git log --output owned.txt",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.run_hook("session-start", {"session_id": "s1"})
                self.run_hook(
                    "record-write",
                    {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
                )
                self.record_success("lint")
                self.record_success("test")
                recorded = self.run_hook(
                    "record-shell",
                    {"session_id": "s1", "tool_input": {"command": command}, "tool_response": ""},
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                blocked = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(blocked.returncode, 2)

    def test_security_verification_does_not_invalidate_lint_and_test(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        self.record_success("lint")
        self.record_success("test")
        for command in (
            "./scripts/security.sh",
            "python scripts/codexicon.py verify security",
        ):
            with self.subTest(command=command):
                recorded = self.run_hook(
                    "record-shell",
                    {
                        "session_id": "s1",
                        "tool_input": {"command": command},
                        "tool_response": "",
                    },
                )
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
                allowed = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_missing_malformed_and_wrong_schema_state_fail_closed(self) -> None:
        cases = [
            None,
            "{",
            json.dumps({"schema_version": 1, "has_writes": False}),
            json.dumps(
                {
                    "schema_version": 2,
                    "has_writes": "no",
                    "lint_passed": False,
                    "test_passed": False,
                    "test_required": False,
                }
            ),
        ]
        for content in cases:
            with self.subTest(content=content):
                self.state_file.unlink(missing_ok=True)
                if content is not None:
                    self.state_file.write_text(content, encoding="utf-8")
                result = self.run_hook(
                    "verify-stop",
                    {"session_id": "s1", "stop_hook_active": False},
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("cannot be trusted", result.stderr)

        active = self.run_hook(
            "verify-stop",
            {"session_id": "s1", "stop_hook_active": True},
        )
        self.assertEqual(active.returncode, 0)
        self.assertIn("systemMessage", active.stdout)

    def test_resume_recovers_missing_state_conservatively(self) -> None:
        with (
            mock.patch.object(HOOK_MODULE, "STATE_FILE", self.state_file),
            mock.patch.object(HOOK_MODULE, "STATE_DIR", self.temp_dir),
            mock.patch.object(HOOK_MODULE, "latest_compatible_checkpoint", return_value=None),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            result = HOOK_MODULE.resume_state({"session_id": "resumed", "source": "resume"})

        self.assertEqual(result, 0)
        state = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.assertTrue(state["has_writes"])
        self.assertTrue(state["test_required"])
        self.assertFalse(state["lint_passed"])
        self.assertFalse(state["test_passed"])
        self.assertIn("required again", output.getvalue())

    def test_resume_ignores_malformed_newest_checkpoint(self) -> None:
        root = self.temp_dir / "project"
        sessions = root / "agent_docs" / "sessions"
        sessions.mkdir(parents=True)
        with mock.patch.object(HOOK_MODULE, "ROOT", root):
            repository_id = HOOK_MODULE.repository_identity()
            valid = {
                "schema_version": 1,
                "checkpoint_id": "a" * 16,
                "created_at": HOOK_MODULE.utc_now()[1],
                "repository_id": repository_id,
                "branch": "none",
                "head": "none",
                "related": [],
            }
            malformed = {**valid, "checkpoint_id": "b" * 16, "created_at": "zzzz"}
            duplicate = {
                **valid,
                "checkpoint_id": "c" * 16,
                "related": ["README.md", "README.md"],
            }
            drive = {
                **valid,
                "checkpoint_id": "d" * 16,
                "related": ["C:/outside"],
            }
            (sessions / "valid.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(valid)} -->\n",
                encoding="utf-8",
            )
            (sessions / "malformed.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(malformed)} -->\n",
                encoding="utf-8",
            )
            (sessions / "duplicate.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(duplicate)} -->\n",
                encoding="utf-8",
            )
            (sessions / "drive.md").write_text(
                f"<!-- codexicon-checkpoint: {json.dumps(drive)} -->\n",
                encoding="utf-8",
            )

            selected = HOOK_MODULE.latest_compatible_checkpoint()

        self.assertEqual(selected, "agent_docs/sessions/valid.md")

    def test_code_write_requires_fresh_lint_and_test_receipts(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        self.assertEqual(
            self.run_hook(
                "record-write",
                {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
            ).returncode,
            0,
        )

        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint, tests", blocked.stderr)

        self.record_success("lint")
        self.record_success("test")
        allowed = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_documentation_only_write_requires_lint_but_not_tests(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        patch = "*** Begin Patch\n*** Update File: README.md\n@@\n-old\n+new\n*** End Patch"
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"command": patch}},
        )
        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint.", blocked.stderr)
        self.assertNotIn("tests", blocked.stderr)

        self.record_success("lint")
        allowed = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_failed_or_masked_check_is_not_recorded_as_passing(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )

        failed = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "./scripts/test.sh"},
                "tool_response": "Exit code: 0 but no authenticated receipt",
            },
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)

        masked = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "./scripts/lint.sh || true"},
                "tool_response": self.receipt("lint"),
            },
        )
        self.assertEqual(masked.returncode, 0, masked.stderr)

        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("lint", blocked.stderr)
        self.assertIn("tests", blocked.stderr)

    def test_receipt_remains_recoverable_until_state_is_persisted(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        receipt = self.receipt("lint")
        receipt_id = receipt.rsplit("receipt=", 1)[1].strip()
        payload = {
            "session_id": "s1",
            "tool_input": {"command": "./scripts/lint.sh"},
            "tool_response": receipt,
        }
        original_paths = (
            CODEX_HOOK.STATE_FILE,
            CODEX_HOOK.STATE_DIR,
            CODEX_HOOK.RECEIPT_DIR,
            CODEX_HOOK.SUMMARY_DIR,
        )
        CODEX_HOOK.STATE_FILE = self.state_file
        CODEX_HOOK.STATE_DIR = self.temp_dir
        CODEX_HOOK.RECEIPT_DIR = self.temp_dir / "receipts"
        CODEX_HOOK.SUMMARY_DIR = self.temp_dir / "summaries"
        original_save = CODEX_HOOK.save_json_atomic

        def fail_state_write(path: Path, value: dict) -> None:
            if path == self.state_file:
                raise OSError("simulated state persistence failure")
            original_save(path, value)

        try:
            with mock.patch.object(CODEX_HOOK, "save_json_atomic", side_effect=fail_state_write):
                with self.assertRaises(OSError):
                    CODEX_HOOK.record_shell(payload)
            receipt_key = hashlib.sha256(receipt_id.encode("ascii")).hexdigest()
            claims = list((self.temp_dir / "receipts").glob(f"{receipt_key}-*.claim"))
            self.assertEqual(len(claims), 1)

            self.assertEqual(CODEX_HOOK.record_shell(payload), 0)
            self.assertFalse(claims[0].exists())
            successful_state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.assertTrue(successful_state["lint_passed"])
            self.assertIn(receipt_id, successful_state["consumed_receipts"])
            self.assertEqual(CODEX_HOOK.reset_state({"session_id": "s1"}), 0)
            reset_state = json.loads(self.state_file.read_text(encoding="utf-8"))
            self.assertFalse(reset_state["lint_passed"])
            self.assertIn(receipt_id, reset_state["consumed_receipts"])
        finally:
            (
                CODEX_HOOK.STATE_FILE,
                CODEX_HOOK.STATE_DIR,
                CODEX_HOOK.RECEIPT_DIR,
                CODEX_HOOK.SUMMARY_DIR,
            ) = original_paths

    def test_receipt_created_before_session_reset_cannot_verify_new_writes(self) -> None:
        self.assertEqual(self.run_hook("session-start", {"session_id": "s1"}).returncode, 0)
        stale_receipt = self.receipt("lint")
        self.assertEqual(
            self.run_hook("session-start", {"session_id": "s1", "source": "clear"}).returncode,
            0,
        )
        self.assertEqual(
            self.run_hook(
                "record-write",
                {"session_id": "s1", "tool_input": {"file_path": "README.md"}},
            ).returncode,
            0,
        )

        replay = self.run_hook(
            "record-shell",
            {
                "session_id": "s1",
                "tool_input": {"command": "./scripts/lint.sh"},
                "tool_response": stale_receipt,
            },
        )
        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})

        self.assertEqual(replay.returncode, 0, replay.stderr)
        self.assertEqual(blocked.returncode, 2)
        self.assertIn("Missing or stale: lint", blocked.stderr)

    def test_mutating_shell_command_invalidates_prior_verification(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        self.record_success("lint")
        self.record_success("test")
        self.run_hook(
            "record-shell",
            {"session_id": "s1", "tool_input": {"command": "python generate.py"}, "tool_response": "done"},
        )

        blocked = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": False})
        self.assertEqual(blocked.returncode, 2)

    def test_active_stop_hook_does_not_loop_forever(self) -> None:
        self.run_hook("session-start", {"session_id": "s1"})
        self.run_hook(
            "record-write",
            {"session_id": "s1", "tool_input": {"file_path": "src/example.py"}},
        )
        result = self.run_hook("verify-stop", {"session_id": "s1", "stop_hook_active": True})
        self.assertEqual(result.returncode, 0)
        self.assertIn("systemMessage", result.stdout)


if __name__ == "__main__":
    unittest.main()
