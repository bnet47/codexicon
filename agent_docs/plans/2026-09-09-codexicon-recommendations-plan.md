# Implementation Plan: Codexicon recommendations 2026-09-09

**Spec:** [SPEC.md](../../SPEC.md)
**Date:** 2026-09-09

## Global constraints

- Preserve unrelated local changes and historical recommendation/evaluation documents.
- Keep one implementation writer in the current checkout at a time; the primary agent inspects and verifies every delegated change.
- Do not invoke Git, create branches/worktrees, stage, commit, push, deploy, or write externally during Build.
- Do not read protected credential-bearing files or execute untrusted shell text from Markdown.
- Maintain compatibility with documented six-column task registers and existing transaction journals during migration.

## Acceptance mapping

| Criterion | Task(s) | Evidence |
|---|---|---|
| A-001 | T-001 | Parser regression tests and line-aware CLI errors |
| A-002 | T-003 | Queue/transition/dependency tests |
| A-003 | T-004, T-005 | Evidence and hook-preservation tests |
| A-004 | T-002 | Contract parser/drift tests |
| A-005 | T-005 | Hook classification and receipt tests |
| A-006 | T-006, T-007 | Skill journey fixtures and resume tests |
| A-007 | T-007 | SessionStart schema/content tests and smoke status |
| A-008 | T-008 | Render equality and browser-routing fixture |
| A-009 | T-009 | Git-disabled Build probes and message guidance |
| A-010 | T-010 | Synthetic scanner and enumeration-failure tests |
| A-011 | T-011 | Fault-injected filesystem transaction tests |
| A-012 | T-012 | POSIX mode and Windows-path test evidence |
| A-013 | T-013 | Scoped lint/protected-read/generated-tree tests |
| A-014 | T-014 | Scenario results with denominators and unmeasured fields |
| A-016 | T-015 | Long-running/resume documentation and structural checks |
| A-015 | T-016 | Coupled workflow validator simulation |

## Tasks

### Task 1: Reject malformed task rows

**Depends on:** none
**Parallel-safe with:** none; establishes shared register parsing
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/build-contracts.md`
**Behavior:** Validate the declared table and every task-like row outside fenced examples. Support whitespace, CRLF, and the six-column migration format; support or clearly reject multiple references and escaped/unescaped pipes. Reject duplicates, unknown references, extra/missing columns, and malformed unfinished work with line numbers.
**Interfaces:** Extend `task_rows()` diagnostics and manager command outcomes without treating malformed input as an empty queue.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** REC-01 adversarial cases fail closed and the documented six-column register remains readable.

### Task 2: Validate SPEC and contract drift

**Depends on:** Task 1
**Parallel-safe with:** none; binds the next task-register contract
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/build-contracts.md`
**Behavior:** Parse actual top-level sections outside fences, enforce unique IDs, required outcome/status/anti-goal structure, non-placeholder definitions, structural references, append-only amendments, and a digest/revision used by TASKS/evidence.
**Interfaces:** Strengthen `read_contract()` and `spec-check`; expose contract identity to task parsing.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** fenced-only, duplicate, conflicting-status, missing-outcome, placeholder, and drift cases are rejected with migration-safe valid contracts accepted.

### Task 3: Make queue state and dependencies explicit

**Depends on:** Tasks 1-2
**Parallel-safe with:** none; changes the register state model
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/build-contracts.md`
**Behavior:** Add explicit READY/RESUME_ACTIVE/BLOCKED/COMPLETE/INVALID outcomes, legal transitions, optional dependencies, blocker reasons, controlled reopen/unblock, runnable selection, conflict-safe atomic updates, and one active implementation owner.
**Interfaces:** Upgrade task register metadata and `tasks-next`/`tasks-*` commands with documented exit/JSON behavior.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** interruption, dependency, concurrency, and invalid-transition acceptance cases pass without register loss.

### Task 4: Bind completion to fresh evidence

**Depends on:** Task 3
**Parallel-safe with:** none; consumes the queue model
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/build-contracts.md`
**Behavior:** Persist acceptance mappings, check identity/result/timestamp/digest, require current task evidence for DONE and covered final checks for COMPLETE, invalidate on source/contract drift, and record review dispositions without blindly executing Markdown commands.
**Interfaces:** Add structured evidence and final-completion validation to manager state.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** missing/failed/stale/wrong-task/uncovered evidence refuses completion and documentation-only structural evidence remains possible.

### Task 5: Correct hook bookkeeping

**Depends on:** Task 4
**Parallel-safe with:** none; coordinates receipt validity with task state
**Files:** `.codex/hooks/codex_hook.py`, `tests/test_codexicon.py`, `docs/codex.md`
**Behavior:** Recognize exact safe manager inspections, distinguish state/evidence bookkeeping from source/config writes, preserve valid source evidence after safe operations, and test Bash/PowerShell command spellings and unsafe composition.
**Interfaces:** Extend hook command classification and state invalidation policy.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** REC-05 cases pass and bookkeeping no longer causes verification churn.

### Task 6: Unify implementation entry points

**Depends on:** Tasks 3-5
**Parallel-safe with:** none; updates shared workflow policy
**Files:** `.agents/skills/**`, `.codex/agents/**`, `AGENTS.md`, `README.md`, `START_HERE.md`, `docs/*.md`, `tests/test_template.py`
**Behavior:** Make discover/spec/brainstorm produce/amend root SPEC, planning create validated TASKS, execute-plan adapt to autonomous-build, quick trace existing contracts or authorized amendments, and pure review/explanation routes exempt from code ceremonies. Resolve primary-writer versus explicitly chosen sequential implementer policy.
**Interfaces:** Align skill triggers, outputs, statuses, and entry-point routing.
**Verification:** `python scripts/validate_template.py`
**Done when:** fresh-template, precise-spec, existing-plan, quick-fix, and resume journeys share one persisted workflow.

### Task 7: Restore model-visible resume context

**Depends on:** Tasks 3-5
**Parallel-safe with:** Task 6 in theory, but run sequentially in this checkout
**Files:** `.codex/hooks/codex_hook.py`, `tests/test_codexicon.py`, `docs/codex.md`
**Behavior:** Emit bounded `hookSpecificOutput.additionalContext` on resume/compact with contract identity, active/runnable task, blockers, evidence freshness, and authoritative reread instructions; use checkpoints only as supplemental context.
**Interfaces:** SessionStart hook output schema and bounded context formatter.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** checkpoint/no-checkpoint, stale/malformed, ACTIVE/BLOCKED, and client-delivery cases are covered or explicitly unmeasured.

### Task 8: Repair playbook routing

**Depends on:** Task 6
**Parallel-safe with:** none; generated artifact follows source
**Files:** `docs/repo-template-playbook.source.html`, `docs/repo-template-playbook.html`, `tests/test_template.py`
**Behavior:** Add autonomous-build selector/card, repair engineering-loop and execute-plan metadata, and synchronize catalog/examples/README/START_HERE/build docs using a small shared catalog where practical.
**Interfaces:** Selector-to-card mapping and prompt copy behavior.
**Verification:** `python scripts/render_playbook.py --check`
**Done when:** source/generated equality, static routing invariants, and an actual browser selection/copy smoke check pass or are recorded unmeasured.

### Task 9: Reconcile Git phase policy

**Depends on:** Tasks 5 and 7
**Parallel-safe with:** none; security and checkpoint policy are coupled
**Files:** `scripts/codexicon.py`, `.codex/hooks/codex_hook.py`, `scripts/security_scan.py`, `.agents/skills/**`, `docs/**`, `tests/**`
**Behavior:** Remove checkout Git dependence from Build/checkpoint/resume/local verification, use local identities/changed paths, split filesystem scan from tracked/history Ship checks, and allow supplied-evidence commit-message drafting without staging.
**Interfaces:** Explicit Build/Ship policy and injectable local identity/evidence functions.
**Verification:** `python -m unittest tests.test_codexicon tests.test_security_scan`
**Done when:** mocked Git-unavailable Build works and stronger tracked/history checks remain documented for Ship.

### Task 10: Harden secret scanning

**Depends on:** Task 9
**Parallel-safe with:** none; uses the scanner split
**Files:** `scripts/security_scan.py`, `tests/test_security_scan.py`, `docs/codex.md`
**Behavior:** Detect quoted keys and dictionary-style assignments, report either Git enumeration failure in Ship mode, preserve placeholders/redaction/protected-path behavior, and support non-Git filesystem scanning.
**Interfaces:** Scanner mode and failure findings.
**Verification:** `python -m unittest tests.test_security_scan`
**Done when:** synthetic secrets, placeholders, both enumeration failures, and protected-file non-read cases pass.

### Task 11: Harden adoption transaction recovery

**Depends on:** Task 9
**Parallel-safe with:** Task 12 conceptually, but run sequentially
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/codex.md`
**Behavior:** Carry planned source digest into operations, refuse source drift before apply, persist terminal rollback before deleting backups, make committed/rolled-back cleanup idempotent, preserve concurrent edits, and read legacy journals.
**Interfaces:** Journal phases and source-baseline validation.
**Verification:** `python -m unittest tests.test_codexicon`
**Done when:** fault-injected source drift, partial cleanup/rollback, terminal persistence failure, concurrent edit, and legacy journal cases pass.

### Task 12: Handle executable mode drift

**Depends on:** Task 11
**Parallel-safe with:** none
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `scripts/validate_template.py`
**Behavior:** Detect identical-byte mode drift, correct it journaledly or report a specific conflict, roll back mode changes, preserve project-owned modes, and keep Windows index synchronization separate.
**Interfaces:** Mode-aware install actions and transaction operations.
**Verification:** `python -m unittest tests.test_codexicon tests.test_template`
**Done when:** POSIX mode cases pass and native Windows behavior is separately documented/measured.

### Task 13: Scope template lint safely

**Depends on:** Task 9
**Parallel-safe with:** none; shares safe discovery boundaries
**Files:** `scripts/validate_template.py`, `tests/test_template.py`, `scripts/security_scan.py`, `docs/codex.md`
**Behavior:** Share protected-path/symlink/pruning policy, separate template-owned durable guidance from project documents, and avoid opening protected or generated files.
**Interfaces:** Safe file discovery and validator surface selection.
**Verification:** `python -m unittest tests.test_template tests.test_security_scan`
**Done when:** model-version project briefs pass, forbidden AGENTS literals fail, protected reads are intercepted, and generated trees are pruned.

### Task 14: Measure behavior and compatibility

**Depends on:** Tasks 1-13
**Parallel-safe with:** none; integrates all prior contracts
**Files:** `docs/evals/agent-loop-benchmark.md`, `tests/**`, `scripts/**`, `docs/codex.md`
**Behavior:** Add deterministic regressions and scenario fixtures for the listed journeys, publish denominators/results/unmeasured fields, and document a client/platform capability matrix without inventing live-agent evidence.
**Interfaces:** Reproducible scenario inputs/results and capability record format.
**Verification:** `python -m unittest discover -s tests`
**Done when:** seeded known failures are caught and measured fast-suite results are recorded separately from live-agent/client smoke gaps.

### Task 15: Document optional long-running execution

**Depends on:** Tasks 6-9 and 14
**Parallel-safe with:** Task 16 in theory, but run sequentially
**Files:** `docs/codex.md`, `docs/build-contracts.md`, `START_HERE.md`, `README.md`, `tests/test_template.py`
**Behavior:** Document supported Goal mode as optional, distinguish active-turn chaining/compaction/restart, preserve cancellation and authority, and keep plain-session deterministic resume.
**Interfaces:** Long-running capability guidance and testable session contract.
**Verification:** `python scripts/validate_template.py`
**Done when:** the optional route and plain-session route are documented with observed/unmeasured client availability.

### Task 16: Repair dependency maintenance workflow

**Depends on:** Tasks 13-14
**Parallel-safe with:** none; final local workflow task before Ship
**Files:** `.github/workflows/ci.yml`, `scripts/validate_template.py`, `tests/test_template.py`, `docs/upgrading.md`
**Behavior:** Keep coupled TruffleHog action/scanner versions synchronized, immutable SHA pins, simulated bump validation, and safe workflow boundaries; do not perform remote refresh, CI, merge, or publication in Build.
**Interfaces:** Dependency validator and update guidance.
**Verification:** `python -m unittest tests.test_template`
**Done when:** simulated updates pass locally and later authorized CI/CodeQL/security verification is explicitly the only remaining release evidence.
