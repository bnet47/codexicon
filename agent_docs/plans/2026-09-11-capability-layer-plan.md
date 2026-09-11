# Implementation Plan: Bounded Codexicon capability layer

**Spec:** [SPEC.md](../../SPEC.md)
**Date:** 2026-09-11

## Global constraints

- Preserve the existing REC-01 through REC-20 behavior and unrelated local files.
- Keep exactly one implementation writer in the shared checkout at a time; a bounded implementation task receives an independent read-only subagent review when any configured trigger in the selected profile matches. Trivial low-risk work below the changed-file threshold with no enabled signal is exempt.
- Keep Build filesystem-local and Git-free. Publication remains a later explicit Ship phase.
- Do not add a daemon, scheduler, arbitrary shell executor, third-party memory service, or authority expansion.
- Keep Python 3.10 compatibility, native Windows/POSIX verification, protected-path rules, and historical documents intact.

## Acceptance mapping

| Criterion | Task(s) | Evidence |
|---|---|---|
| A-021 | T-021 | Capability parser/validator tests and CLI output |
| A-022 | T-022 | Profile budget and bounded-loop contract tests/docs |
| A-023 | T-023 | Selective reviewer policy tests/docs |
| A-024 | T-024 | Verification-tier and stop-contract tests/docs |
| A-025 | T-025 | Decision-journal and scope-boundary checks |
| A-026 | T-026 | Capability matrix and deterministic scenario evidence |
| A-027 | T-027 | Template/playbook structural and render checks |

### Task 1: Validate the capability policy

**Depends on:** none
**Parallel-safe with:** none; establishes the shared policy schema
**Files:** `.codex/capabilities.toml`, `scripts/codexicon.py`, `scripts/scaffold.py`, `.codexicon.json`, `tests/test_codexicon.py`, `docs/build-contracts.md`
**Behavior:** Add strict, balanced, and autonomous profiles with explicit budgets, review thresholds, verification tiers, and mandatory escalation flags. Validate structure, values, unknown keys, and unsafe attempts; expose stable human/JSON CLI output without executing policy text.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** malformed or authority-expanding policies fail closed and a clean scaffold includes the validated capability policy.

### Task 2: Make bounded refinement explicit

**Depends on:** T-021
**Parallel-safe with:** none; consumes the selected profile
**Files:** `.agents/skills/autonomous-build/SKILL.md`, `.codex/agents/implementer.toml`, `docs/capabilities.md`, `tests/test_template.py`
**Behavior:** Define task-specific acceptance rubrics, iteration/review/failure budgets, plateau detection, and human-boundary stops. Require the agent to improve the weakest important aspect only while meaningful improvement remains; do not create a runtime loop.
**Verification:** `python -m unittest tests.test_template`
**Done when:** the skill and implementer profile reference the policy and describe observable stop behavior without conflicting with the task register.

### Task 3: Add selective independent review policy

**Depends on:** T-021,T-022
**Parallel-safe with:** none; review thresholds depend on policy semantics
**Files:** `.agents/skills/review/SKILL.md`, `.codex/agents/reviewer.toml`, `docs/capabilities.md`, `tests/test_template.py`
**Behavior:** Define review triggers from risk, changed-file count, public API/security/architecture reach, and test complexity. Keep reviewers read-only, require finding dispositions, and exempt trivial low-risk work.
**Verification:** `python -m unittest tests.test_template`
**Done when:** review routing and evidence dispositions are unambiguous and the reviewer cannot become a writer or publication authority.

### Task 4: Separate verification tiers and stop rules

**Depends on:** T-021,T-022,T-023
**Parallel-safe with:** none
**Files:** `docs/build-contracts.md`, `docs/codex.md`, `.agents/skills/autonomous-build/SKILL.md`, `.agents/skills/ship/SKILL.md`, `tests/test_template.py`
**Behavior:** Document focused iteration, Build completion, and Ship verification tiers, freshness rules, safe-inspection behavior, and outcome-based Stop conditions.
**Verification:** `python scripts/validate_template.py`
**Done when:** each tier has an owner, required evidence, and no premature shipping ceremony or weakened final gate.

### Task 5: Add decision journal and controlled scope guidance

**Depends on:** T-022,T-023
**Parallel-safe with:** none
**Files:** `agent_docs/decisions/README.md`, `docs/capabilities.md`, `AGENTS.md`, `.agents/skills/autonomous-build/SKILL.md`, `tests/test_template.py`
**Behavior:** Establish an append-only journal format for consequential assumptions/decisions and a bounded rule for small directly related correctness, safety, test, maintainability, and documentation expansion. Escalate product, architecture, destructive, external, credential, legal, and production changes.
**Verification:** `python -m unittest tests.test_template`
**Done when:** the guidance gives visibility without routine approval stops and preserves ADR history and Ship authority.

### Task 6: Publish capability matrix and scenario evidence

**Depends on:** T-021,T-024,T-025
**Parallel-safe with:** none
**Files:** `docs/evals/capability-matrix.md`, `docs/evals/agent-loop-benchmark.md`, `docs/evals/live-agent-results-2026-09-11.md`, `tests/test_template.py`
**Behavior:** Record supported client/platform evidence with versions/dates, hook trust, resume/compact, completion, native verification, denominators, and explicit unmeasured fields. Keep deterministic fixtures separate from live-client claims.
**Verification:** `python -m unittest tests.test_template tests.test_live_agent_eval`
**Done when:** the matrix is honest, reproducible, and does not infer compatibility from raw tool names or a green deterministic suite.

### Task 7: Synchronize public documentation and playbook

**Depends on:** T-021,T-022,T-023,T-024,T-025,T-026
**Parallel-safe with:** none; generated output follows the final source
**Files:** `README.md`, `START_HERE.md`, `docs/agent-patterns.md`, `docs/upgrading.md`, `docs/repo-template-playbook.source.html`, `docs/repo-template-playbook.html`, `tests/test_template.py`
**Behavior:** Expose the capability profile, refinement, review, verification, decision, and matrix behavior consistently in public docs and selector cards.
**Verification:** `python scripts/render_playbook.py --check; python scripts/validate_template.py`
**Done when:** source/generated equality and routing invariants pass, and no public document promises a capability the policy/skills do not support.

## Final verification

`python scripts/codexicon.py spec-check`, `python scripts/codexicon.py tasks-next --json`, native and POSIX lint/test/security, `python scripts/security_scan.py --mode ship`, template validation, playbook render check, deterministic evaluation, and—when any selected-profile review trigger matches—a read-only independent review of the complete change set.
