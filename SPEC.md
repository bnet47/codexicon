# Specification: Trustworthy Codexicon autonomous Build workflow

**Status:** ACTIVE

## Outcome

Codexicon provides a portable, local-first template and manager whose contract, task queue, evidence, hooks, adoption tools, and documentation describe and enforce one resumable implementation workflow. A valid build cannot silently lose work, claim completion without current acceptance evidence, or cross the documented Git/publication boundary.

## Requirements

- **R-001:** Parse the documented task register without silently dropping malformed or unfinished task-like rows, while remaining compatible with the existing six-column format during migration.
- **R-002:** Provide explicit queue outcomes, legal task transitions, dependency-aware runnable selection, blocker persistence, and single-owner protection for the default checkout.
- **R-003:** Bind task completion and milestone completion to fresh, task-specific verification evidence and acceptance coverage without treating writable receipts as a tamper-proof security boundary.
- **R-004:** Validate the real root specification outside fenced examples, enforce unique and non-placeholder contract structure, and detect contract/task drift with append-only amendments.
- **R-005:** Classify manager inspections and task bookkeeping correctly in hooks so valid verification evidence survives safe metadata operations while source or contract changes invalidate the right evidence.
- **R-006:** Route discovery, specification, planning, quick changes, existing-plan execution, and autonomous Build through one coherent contract and state vocabulary with no routine suggested-next-prompt stop while runnable work remains.
- **R-007:** Restore bounded, model-visible contract/task/evidence context on resume and compaction, with checkpoints supplemental to newer authoritative state.
- **R-008:** Repair and synchronize the interactive playbook, catalog, examples, and routing documentation so each implementation entry point selects the correct workflow.
- **R-009:** Keep Build filesystem-local and Git-free, move tracked/history checks and Git publication to the explicit Ship phase, and make message-only formatting work from supplied evidence.
- **R-010:** Detect quoted-key secret assignments and both tracked-file enumeration failures without opening protected credential files or exposing secret values.
- **R-011:** Make adoption source baselines, transaction journals, rollback, cleanup, and recovery robust to source drift, interrupted cleanup, concurrent edits, and backward-compatible existing journals.
- **R-012:** Treat executable intent and mode-only drift as adoption state, with journaled correction or explicit conflict and preservation of project-owned modes.
- **R-013:** Scope template lint to safe, relevant template-owned surfaces, prune generated trees before descent, reject protected paths before reading, and leave application-document lint meaningful.
- **R-014:** Add deterministic regression/scenario evaluations and a client/platform capability matrix with denominators, reproducible inputs, and explicit unmeasured fields.
- **R-015:** Repair the coupled dependency-update workflow and validator so immutable action pins and scanner/action version checks remain synchronized without privileged execution of untrusted code.
- **R-016:** Document and test optional supported long-running Goal-mode execution while keeping portable SPEC/TASKS resume authoritative and avoiding a scheduler or third-party persistence service.
- **R-017:** Generate a clean project starter that carries Codexicon's reusable harness surface without its development contract, task ledger, briefs, checkpoints, or internal evaluation records.
- **R-018:** Keep the documented writer and delegation policy internally consistent, with an append-only decision superseding the obsolete worktree-writer guidance.
- **R-019:** Make template version, manifest, documentation, release tag, and published starter artifact agree through one reproducible release check.
- **R-020:** Measure Codexicon on real Codex runs against a direct baseline with isolated fixtures, independent acceptance checks, repeatable inputs, and explicit cost, latency, and unmeasured fields.

## Interfaces

- **I-001:** `python scripts/codexicon.py spec-check`, `tasks-next`, `tasks-start`, `tasks-done`, and `tasks-blocked` expose validated contract/task outcomes with documented exit behavior and optional machine-readable output.
- **I-002:** Root `SPEC.md` and `TASKS.md` use stable IDs, append-only amendments, dependency metadata, acceptance mappings, blocker reasons, evidence records, and a contract digest/revision.
- **I-003:** The task manager exposes a legal-transition and runnable-selection model with `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID` outcomes and conflict-safe atomic persistence.
- **I-004:** Task evidence records acceptance IDs, check identity, result, timestamp, relevant source/contract digest, and review finding dispositions; final completion requires configured checks and coverage.
- **I-005:** Codex hooks distinguish read-only manager commands, state/evidence bookkeeping, source/configuration writes, and unsafe command composition across Bash and native Windows spellings.
- **I-006:** SessionStart resume/compact output uses `hookSpecificOutput.additionalContext` for bounded authoritative context, including contract identity, active/runnable task, blockers, and evidence freshness.
- **I-007:** Adoption transactions carry planned source identity, terminal phases, idempotent cleanup, and executable mode state through plan/apply/recover.
- **I-008:** Security and template validators share safe discovery/protected-path rules while separating filesystem Build checks from tracked/history Ship checks.
- **I-009:** The playbook source/generated pair, selector/catalog, skills, roles, README, START_HERE, upgrade guidance, and build-contract docs express the same workflow routing.
- **I-010:** Scenario fixtures and capability records report reproducible behavior across supported clients and operating systems without claiming live-agent evidence that was not measured.
- **I-011:** Dependency validation keeps action references pinned to immutable SHAs and verifies the coupled TruffleHog action/scanner version pair.
- **I-012:** Optional long-running guidance distinguishes active-turn chaining, compaction recovery, and restart after termination and preserves cancellation and authority boundaries.
- **I-013:** `python scripts/codexicon.py scaffold` creates a release-ready starter from an explicit safe allowlist and leaves project discovery as the first product step.
- **I-014:** A dated ADR and validation checks define one sequential shared-checkout writer policy for Build and one explicit publication boundary for Ship.
- **I-015:** `python scripts/release.py check` validates the canonical template version, manifest, public version references, release tag, and starter artifact identity.
- **I-016:** `python scripts/live_agent_eval.py` runs isolated direct and Codexicon trials, records machine-readable per-run evidence, and produces an honest aggregate report.

## Acceptance

- **A-001:** Malformed rows, unsupported delimiters, duplicate/unknown IDs, fenced examples, CRLF, and unfinished work are diagnosed with line-aware errors; invalid input never yields successful empty-queue or completion output.
- **A-002:** Interrupted ACTIVE work resumes first; all-BLOCKED differs from COMPLETE; missing/cyclic dependencies fail; blocked consumers do not start; independent ready work remains runnable; invalid transitions leave the register unchanged.
- **A-003:** Missing, failed, stale, wrong-task, or uncovered acceptance evidence prevents DONE/COMPLETE; relevant source or contract changes stale evidence; documentation-only checks can satisfy their own acceptance.
- **A-004:** Fenced-only, duplicate-ID, conflicting-status, missing-outcome, placeholder, drifted, and unamended contracts fail validation; authorized amendments preserve history and produce a valid task baseline.
- **A-005:** Fresh canonical lint/test/security evidence remains valid after safe inspections and valid state-only bookkeeping, while source edits, amendments, unsafe commands, and mutating manager commands invalidate the appropriate evidence.
- **A-006:** Fresh-template, precise-feature, existing-plan, quick-fix, and interrupted-resume journeys all trace code changes to real contract items and use the same persisted task states without routine approval/prompt handoffs.
- **A-007:** Resume/compact tests with and without checkpoints, stale contracts, malformed state, ACTIVE work, and blockers produce bounded model-visible additional context; a client smoke result is recorded or explicitly marked unmeasured.
- **A-008:** Every selectable playbook skill has a matching card and prompt; implementation selects autonomous-build; engineering-loop remains read-only research/review; source/render equality and browser selection/copy checks pass.
- **A-009:** Normal Build/checkpoint/resume/local verification works when Git subprocesses are unavailable; Ship retains tracked protected-path/history verification; supplied commit details suffice for message drafting without staging.
- **A-010:** Quoted JSON/YAML/dictionary secret assignments and both Git enumeration failures are detected, placeholders pass, protected files are not opened, and output contains no secret values.
- **A-011:** Source drift between plan/apply is refused; interrupted and partial cleanup/recovery is idempotent; terminal-state persistence is safe; concurrent target edits are preserved; legacy journals remain understandable.
- **A-012:** Identical non-executable managed/merge files surface or correct mode drift transactionally, rollback restores modes, and project-owned modes are preserved on POSIX with separate native Windows evidence.
- **A-013:** Project briefs may mention versioned models without failing durable harness guidance, forbidden model literals in AGENTS fail, protected files are never read, and ignored generated trees are not traversed.
- **A-014:** REC-01 through REC-13 scenario/regression coverage has reproducible inputs, expected outcomes, denominators, and measured results; unsupported client fields are explicitly unmeasured.
- **A-015:** A simulated dependency bump passes the coupled validator with immutable pins; the local workflow is ready for later authorized CI/CodeQL/security verification without weakening version checks.
- **A-016:** Optional Goal-mode guidance and plain-session resume are tested/documented, cancellation remains respected, and persistence adds no Git/deployment authority or default scheduler.
- **A-017:** A fresh scaffold contains no Codexicon development SPEC/TASKS, internal briefs, plans, checkpoints, or evidence receipts; a new project can start with `$discover` and passes the documented starter smoke test.
- **A-018:** The current ADR, AGENTS guidance, skills, and tests contain no contradictory writer policy; Build remains local and sequential, while worktree/Git publication is confined to explicit Ship behavior.
- **A-019:** A release check fails on version drift and passes for the exact tag and starter artifact used by the published release; release notes and README identify the same version.
- **A-020:** Repeated direct-versus-Codexicon Codex trials report acceptance, interventions, regressions, elapsed time, token/cost fields when available, and explicit unmeasured values without credentials or external writes.

## Anti-goals

- **AG-001:** Do not add a daemon, cron substitute, scheduler service, paid service, or third-party memory dependency to the default template.
- **AG-002:** Do not execute arbitrary shell text copied from Markdown or broaden command allowlists to every manager/Markdown operation.
- **AG-003:** Do not silently rewrite accepted requirements, discard historical evaluations/ADRs, or claim hashes, green parser tests, or zero findings prove product correctness.
- **AG-004:** Do not open credential-bearing files, print secret values, ingest transcripts/secrets into resume context, or weaken security scanning to accommodate documentation.
- **AG-005:** Do not create concurrent writers in one checkout, branches/worktrees during Build, or commits, pushes, releases, deployments, and external writes without explicit Ship authority.
- **AG-006:** Do not introduce unrelated product features, force a model identity in reusable instructions, or infer client compatibility from raw tool names alone.

## Assumptions

- This repository is the Codexicon template/harness itself; Python standard-library tooling, native shell wrappers, and GitHub Pages documentation remain the supported baseline.
- The recommendation document is an authorized implementation brief for local changes but does not authorize publication, deployment, or Git operations.
- Existing six-column task registers and current journal schemas remain readable through migration; new metadata may be additive and explicitly versioned.
- The primary checkout is the only implementation writer; each bounded task is delegated to one sequential implementation subagent and reviewed by the primary agent.
- Live client smoke tests, current upstream CI, and native Windows/POSIX differences are recorded as measured or unmeasured rather than inferred.

## Amendments

- **2026-09-09:** Created from `docs/codexicon-recommendations-2026-09-09.md`; preserves the recommendation package as historical input and authorizes local implementation only.
- **2026-09-11:** Authorized clean starter generation, writer-policy reconciliation, reproducible release identity, and live Codex comparison work; publication remains confined to the later Ship phase.
