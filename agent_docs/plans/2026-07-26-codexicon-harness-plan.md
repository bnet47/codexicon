# Implementation Plan: Maintainable Codexicon Repository Harness

**Spec:** User request supplied on 2026-07-26 (conversation attachment)
**Date:** 2026-07-26

## Current state

Already implemented:

- concise root guidance, progressive repository skills, conservative project configuration, explicit side-effect authority, and a primary-agent integration model;
- portable Python hooks with trusted project registration, protected-path checks, locked atomic session state, conservative verification invalidation, and one-use lint/test receipts;
- canonical Bash and PowerShell lint, test, and security entry points;
- Linux/Windows CI, pinned actions, structural template validation, credential scanning, and focused hook tests;
- a human-readable `context-dump` checkpoint format.

Actually missing or defective:

- no inspect-first adoption flow for an established repository and no conflict-aware future update path;
- no post-initialization doctor or stable cross-platform verification orchestrator;
- checkpoints have no machine-readable identity, deterministic resume selection, compatibility check, or resume workflow;
- current Codex config uses undocumented `agents.max_depth` and a legacy concurrency key;
- the custom researcher overlaps the built-in explorer;
- resume or worktree handoff can lose ignored hook state and make the stop gate fail open;
- the read-only shell classifier accepts execution-bearing suffixes and substitutions;
- canonical POSIX files lack executable Git modes and an LF checkout policy;
- credential scanning can suppress real values containing placeholder substrings and can silently skip unreadable files;
- Git-hook installation silently replaces an existing `core.hooksPath`;
- Windows CI does not exercise the native security wrapper.

## Chosen architecture

Add one repository-local, Python-standard-library entry point, `scripts/codexicon.py`, plus one versioned source manifest, `.codexicon.json`.

- The manager provides read-only inspection and diagnostics by default.
- Adoption and updates require an explicit `--apply`.
- File-level baseline hashes distinguish unchanged infrastructure from project modifications. Locally modified files are never overwritten or deleted.
- Mutations use atomic per-file replacement plus a transaction journal and rollback.
- Canonical project scripts remain the verification source of truth; the manager only invokes them in order.
- Semantic checkpoints remain explicit Markdown under `agent_docs/sessions/`; no hook silently writes or commits project-owned checkpoint content.
- Hooks recover missing resume state conservatively and surface the latest compatible checkpoint, but remain a guardrail rather than a complete security boundary.

This extends ADR-001's repository-native decision. It does not add a package, plugin, network updater, service, telemetry, or framework.

## Expensive-to-reverse decisions

- **Ownership granularity:** use whole-file baselines. Region markers and a general merge engine are deferred because they would permanently complicate project-owned files.
- **Update authority:** use an explicitly supplied local source and plan-first apply. Network self-update and automatic replacement are out of scope.
- **Verification ownership:** keep `scripts/lint.*`, `test.*`, and `security.*` project-owned. Moving application checks into Codexicon would make initialized projects harder to maintain.
- **Checkpoint privacy:** require an explicit checkpoint command/skill. Automatic transcript summarization or hook-authored tracked files would weaken authority and privacy boundaries.
- **Distribution:** remain repository-local. ADR-001's plugin revisit signal is not met.

## Deferred

- automatic three-way or semantic merging;
- automatic downloads, release discovery, or version scoring;
- automatic creation, commit, publication, or synchronization of checkpoints;
- universal shell parsing; commands outside a narrow exact read-only allowlist are treated as mutating;
- MCP-wide credential enforcement, because specialized tools can bypass local tool hooks;
- live Codex UI trust, compaction, and worktree-handoff smoke tests that repository code cannot execute by itself;
- binding receipts to a Codex session, because canonical scripts do not receive a documented session identifier.

## Global constraints

- Preserve unrelated and project-owned content; do not commit, push, publish, deploy, or perform external writes.
- Support Python 3.10+, Windows PowerShell, Bash on macOS/Linux, and fresh checkouts with Git line-ending conversion enabled.
- Keep persistent state human-readable and minimal; never include credentials, transcript contents, or diffs in lock/checkpoint metadata.
- Resolve source and target paths safely, reject traversal and unsafe symlinks, and recover interrupted mutations.
- Keep the primary agent as integrator and final verifier; use no simultaneous writers in this checkout.

## Acceptance mapping

| Criterion | Task(s) | Evidence |
|---|---|---|
| AC-1 Inspect an existing repository without mutation and report compatibility/conflicts | 2 | read-only fixture tests; unchanged target hash/status |
| AC-2 Adopt only with explicit authority and preserve existing content | 2 | adoption success/conflict/security/interruption tests |
| AC-3 Diagnose missing, malformed, stale, partial, and unsupported harness state after initialization | 2, 4 | doctor fixtures and template validation |
| AC-4 Resume from a compatible durable human-readable checkpoint across sessions/compaction | 3 | checkpoint/resume and hook resume tests |
| AC-5 Run real project-defined verification consistently on Windows and POSIX | 2, 4 | manager verification tests; native wrapper and CI checks |
| AC-6 Apply future infrastructure updates without silently overwriting local changes | 2 | unchanged-update, conflict, removal, rollback, and traversal tests |
| AC-7 Use only current documented Codex configuration and lifecycle behavior | 1, 3, 4 | config assertions and docs references |
| AC-8 Close verified safety and portability gaps without a universal shell parser | 1, 4 | bypass, malformed-state, scanner, hook-installer, LF/mode, and CI tests |
| AC-9 Preserve compact progressive repository ergonomics and explicit authority | 2, 3, 4 | skill/catalog budgets, docs inspection, no automatic side effects |
| AC-10 Full canonical verification and independent complete-diff review pass | 5 | exact lint/test/security results and reviewer reports |

### Task 1: Harden documented config, hooks, scanner, and Git-hook installation

**Depends on:** none
**Parallel-safe with:** none (shared verification and policy files)
**Files:** modify `.codex/config.toml`, `.codex/agents/researcher.toml`, `.codex/hooks/codex_hook.py`, `scripts/security_scan.py`, `scripts/install-git-hooks.sh`, `scripts/install-git-hooks.ps1`, `tests/test_template.py`, `tests/test_security_scan.py`; create `.gitattributes`; update executable Git modes for `scripts/*.sh` and `.githooks/*`
**Behavior:** use only documented config keys; narrow researcher to external primary-source research; replace prefix-based read-only classification with a complete narrow allowlist; fail closed or recover conservatively from missing/malformed resume state; detect scanner false negatives and unreadable inputs; refuse to replace a different hooks path; preserve idempotent installation; force LF and executable POSIX entry points.
**Interfaces:** existing hook actions plus a resume-safe session action; existing scanner CLI; existing installer scripts.
**Verification:** `python -m unittest tests.test_template tests.test_security_scan -v`; `python scripts/validate_template.py`; POSIX syntax and direct-execution smoke checks.
**Done when:** every reproduced bypass has a regression test, supported behavior remains compatible, and no undocumented config key remains.

### Task 2: Add the repository-local adoption, doctor, update, and verification manager

**Depends on:** Task 1
**Parallel-safe with:** none (establishes shared manifest and verification contract)
**Files:** create `scripts/codexicon.py`, `.codexicon.json`, `tests/test_codexicon.py`; modify `scripts/validate_template.py` and canonical wrappers only where integration requires it.
**Behavior:** `inspect` and mutation plans are read-only; `adopt`/`update` require `--apply`; installed lock data records schema/version/policy/baseline hashes; unchanged files may update, locally changed files conflict, removed files delete only when unchanged and explicitly applied; traversal/symlinks are rejected; atomic writes and a transaction journal roll back interruption; `doctor` validates installed/source modes without assuming an uninitialized template; `verify` invokes platform-native canonical scripts in lint/test/security order and propagates failures.
**Interfaces:** `python scripts/codexicon.py inspect TARGET`; `adopt TARGET [--apply]`; `doctor [--root ROOT]`; `update --source SOURCE [--apply]`; `verify [checks...]`; `install-git-hooks`.
**Verification:** `python -m unittest tests.test_codexicon -v`; fixture subprocess tests for success, failure, malformed state, partial adoption, update conflicts/removals, interruption, and security path bypasses.
**Done when:** all operations are deterministic, plan-first, dependency-free, and leave project-owned conflicts untouched.

### Task 3: Make checkpoint and resume support durable and explicit

**Depends on:** Task 2
**Parallel-safe with:** none (touches manager and hook lifecycle)
**Files:** modify `scripts/codexicon.py`, `.codex/hooks/codex_hook.py`, `.codex/hooks.json`, `.agents/skills/context-dump/SKILL.md`, `.agents/skills/execute-plan/SKILL.md`, `tests/test_codexicon.py`, `tests/test_template.py`.
**Behavior:** atomically create a Markdown checkpoint with schema, timestamp, repository fingerprint, branch/HEAD, related files, dirty-path summary, verification claims, next actions, blockers, and decisions; deterministically select the newest compatible checkpoint; diagnose stale/broken references; on documented `SessionStart` resume/compact sources preserve valid state, reconstruct missing state conservatively by always requiring fresh lint and tests, and surface compatible resume context; do not auto-write a semantic checkpoint during compaction.
**Interfaces:** `checkpoint` and `resume` manager subcommands; updated `context-dump` skill branches; `session-resume` hook action.
**Verification:** focused checkpoint parsing/selection/staleness/atomic-failure tests and resume-hook state tests.
**Done when:** a fresh task can resume from explicit repository evidence without transcript archaeology, while missing local hook state cannot bypass required checks.

### Task 4: Align validation, CI, documentation, and architecture records

**Depends on:** Tasks 1-3
**Parallel-safe with:** none (documents and validates final interfaces)
**Files:** modify `AGENTS.md`, `README.md`, `START_HERE.md`, `docs/codex.md`, `docs/agent-patterns.md`, `docs/maintainers.md`, `.github/workflows/ci.yml`, `scripts/validate_template.py`; create the next ADR; update relevant skill metadata and manifest coverage.
**Behavior:** document only implemented commands and authority; correct config precedence and hook limitations from current official docs; explain built-in explorer versus narrowed researcher; document local state/worktree limitations; run Windows security in CI; directly exercise POSIX canonical scripts and Git hooks; validate manifest/config/hook schema, executable modes, LF policy, and skill budgets.
**Interfaces:** existing documentation, template validator, and CI workflow.
**Verification:** `python scripts/validate_template.py`; Markdown-link validation inside lint; workflow inspection; official-doc source comparison.
**Done when:** docs, validation, CI, and code describe one consistent lifecycle and update/checkpoint contract.

### Task 5: Integrate, review, and verify the complete result

**Depends on:** Tasks 1-4
**Parallel-safe with:** independent read-only review passes may run concurrently after implementation
**Files:** complete diff; fixes limited to verified findings; remove temporary task artifacts only if required by release policy.
**Behavior:** run focused tests, both native and POSIX canonical checks, security scanning, source/fixture integration tests, and independent correctness/security/regression/cross-platform/complexity reviews; verify reviewer findings before editing; compare every acceptance criterion to evidence.
**Interfaces:** canonical repository commands and reviewer reports.
**Verification:** `./scripts/lint.sh`; `./scripts/test.sh`; `./scripts/security.sh`; PowerShell equivalents; all focused unittest modules; `git diff --check`; clean template/adoption fixture runs.
**Done when:** material verified findings are fixed, affected checks are rerun, all acceptance criteria have evidence, and residual risks/deferred work are explicit.
