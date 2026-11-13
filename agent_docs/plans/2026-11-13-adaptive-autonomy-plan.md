# Implementation plan for adaptive autonomy

**Date:** 2026-11-13
**Baseline:** [SPEC.md](../../SPEC.md), revision `2026-09-23`, and [TASKS.md](../../TASKS.md), complete through T-035
**Status:** Proposed implementation handoff
**First milestone:** T-036 through T-040
**Follow-on milestone:** T-041 through T-044

Codexicon should improve the odds of finishing an authorized task without intervention when the first approach fails. The first milestone establishes a live comparison against plain Codex and the current starter, then tries one improvement to recovery. The follow-on work extends that same comparison to method selection, verification against a running project, and skill revisions.

## Handoff to Luna

Use Luna 6 with extra high reasoning in the invoking client. Treat that as a session setting. Read `AGENTS.md`, this plan, `SPEC.md`, and `TASKS.md`. Use `$execute-plan` and `$autonomous-build` after activation. Run `python scripts/codexicon.py tasks-next --json` at each handoff, resume an `ACTIVE` task first, and work one task at a time in the shared checkout. Record the files touched, check results, and next action before handing off a partial task. The primary agent owns integration and acceptance. Read-only review can run independently when the capability policy calls for it.

Copyable first handoff:

> Use this session's Luna 6 extra high setting. Implement milestone 1 from `agent_docs/plans/2026-11-13-adaptive-autonomy-plan.md`. Reconcile and activate its proposed contract and queue, then complete T-036 as the first part. Record fresh task evidence and leave the next runnable task ready for the next session. Use the plan's activation and completion procedure, preserve earlier evidence, and report any client or historical completion blocker precisely.

### Activate the work before the first implementation task

1. Run `python scripts/codexicon.py spec-check` and `python scripts/codexicon.py tasks-next --json`. Expect the September baseline and `COMPLETE` if the workspace has not moved. If it has moved, reconcile proposed IDs, scopes, and dependencies against current files before applying them.
2. Once authorized to implement, append the first milestone's requirements, interfaces, acceptance conditions, and a dated amendment to `SPEC.md`. Update the register header with the revision and digest printed by `spec-check`. Append the applicable rows to the existing nine-column table with `TODO`, `None` for blocker and evidence, and the listed dependencies. Keep all prior rows and receipts intact. Link this plan in the register and rerun both checks. Expect `READY` for T-036.
3. A new contract digest invalidates earlier receipts for current completion, and changes to shared source files can also stale them. The existing `tasks-next` completion check validates every `DONE` row once the queue drains. Treat earlier receipts as historical evidence and surface any stale entries. Obtain fresh evidence for affected milestone tasks via the existing controlled reopen flow, and retain the earlier receipts in the handoff record when reopening replaces them. If a check needs separate Ship authority or the project needs a migration for historical receipts, record that as a distinct completion dependency. Preserve the evidence gate, existing digests, and actual dates. Report milestone delivery separately from repository-wide `COMPLETE`, which requires the manager's full evidence gate.
4. Activate T-041 through T-044 only after the first milestone decision and an explicit choice to proceed with that milestone. Use the same append-only contract and register procedure. Keep historical reports available for comparison.

## Constraints

- Follow ADR-004, ADR-005, and ADR-006. Build is local and Git-free, with one writer, existing review and retry budgets, and explicit Ship authority. Continue through independent runnable work if a live observation is blocked.
- Use disposable synthetic fixtures and a single reviewed client path for the first benchmark. Give the fixture the minimum capability it needs. Keep normal credentials, protected paths, real accounts, production data, and external mutations outside the fixture. Any live model invocation uses the invoking user's existing authorized client and a bounded run count.
- Use the existing task register and checkpoint mechanism. Keep the evaluation runner maintainer-only. Keep `--smoke`, old receipts, and the starter's existing public commands compatible. Keep the baseline starter snapshot immutable throughout a comparison.
- Compare an actual installed workflow. Distinguish starter staged, client pickup observed, check passed, trial completed, and method observed. Missing telemetry is `unmeasured` and a requested route is only a request until observed. Use metadata and synthetic outputs for evidence, with no raw transcripts, environment dumps, or clipboard captures.
- Decide acceptance from independently checked artifacts or environment state. On current source, report stale evidence honestly. On benchmark fixtures, keep the verifier and expected answers outside the agent-writable workspace. Use hard limits for the runner and verify cancellation before interpreting recovery results.

## Proposed contract and acceptance mapping

Append these entries to their matching sections of `SPEC.md` on activation. Keep the IDs paired as shown in the register.

| Requirement | Interface | Acceptance condition | Task and evidence |
| --- | --- | --- | --- |
| **R-033** Distinguish completed, accepted live outcomes from partial checks and invalid comparisons. | **I-026** Versioned task fixture and trial-result records with an independent verifier and explicit outcome, scope and cleanup fields. | **A-034** A verifier pass cannot make an interrupted run, scope violation, cleanup failure or invalid trial acceptable. Synthetic positive and negative controls prove it. | T-036, unit tests |
| **R-034** Compare a plain client run with an actual Codexicon starter and track activation evidence. | **I-027** A paired-run mode in `scripts/live_agent_eval.py` that stages isolated copies of the same project task and accepts an optional pinned candidate source. | **A-035** Arms share the task text, fixture data, model settings, permitted tools, budgets and grader. Starter and candidate identity are recorded and client pickup and delegation are marked unmeasured when unobserved. | T-037, runner and scaffold integration tests |
| **R-035** Exercise multiple task types with independently verifiable outcomes. | **I-028** A versioned fixture catalog and a bounded pilot report recording scope, denominator, verified outcomes, interventions and available timing and cost. | **A-036** Debugging, rendered workflow and source reconciliation each have a known-good submission and a plausible wrong one. Pilot reports distinguish complete, failed, unavailable and unmeasured arms. | T-038, fixture controls and pilot record |
| **R-036** Change approach within the existing Build budget when a failure reveals a better route. | **I-029** Recovery guidance and a compact recovery section in the existing project checkpoint. | **A-037** A disproved approach, an unavailable tool and uncertain prior action each lead to an evidence-seeking next step. Resume rechecks the relevant state and avoids repeating a possible mutation. Existing stops and authority still apply. | T-039, deterministic scenarios |
| **R-037** Evaluate recovery before changing default behavior. | **I-030** A controlled pilot report and a decision to promote, revise or retain current behavior. | **A-038** A frozen starter and candidate face the same tool loss and interruption cases under matched budgets, with a plain-client comparison. Reports include observed recovery, duplicate actions, intervention and verified completion or explicitly identify missing live evidence. | T-040, pilot results and decision |
| **R-038** Select a method from the task outcome, available tools, and quality of the evidence. | **I-031** A short method-selection step in existing Build guidance for substantial or uncertain tasks. | **A-039** Known fixes take the direct path. Ambiguous defects select a diagnostic. UI claims select a rendered interaction and meaningful readback. An unavailable preferred tool yields an authorized fallback or a precise blocker. | T-041, scenario tests |
| **R-039** Give initialized projects a usable route to verify actual behavior. | **I-032** `$init` and `agent_docs/operations.md` describe the project's launch, fixture, observation and outcome-check paths. | **A-040** Web, CLI and desktop examples identify an applicable outcome check and handle unavailable prerequisites. Starter generation and existing native verification remain valid. | T-042, starter and template checks |
| **R-040** Evaluate proposed skill changes against measured behavior and activation. | **I-033** A maintainer-only skill evaluation mode or helper sharing the benchmark runner and report format. | **A-041** The current and candidate skill are compared on intended triggers, near misses and held-out tasks. Evidence includes outcome, observed activation and cost when exposed. No trial promotes a skill automatically. | T-043, comparison and promotion-gate tests |
| **R-041** Integrate only behavior that meets the evaluation bar and report unsupported capabilities. | **I-034** Maintainer guidance and a decision record linking evaluated versions, outcomes and retained defaults. | **A-042** A maintainer can repeat the comparisons, identify the active behavior and understand what was unmeasured. Canonical local verification succeeds, and any distinct queue completion blocker remains visible. | T-044, final checks and decision record |

## Proposed register rows

Use the command in the table as the task-specific receipt check. Additional commands and live observations below supplement that check. Use exact file paths from each task's scope in the active register. All new rows start `TODO` with no blocker or evidence. Implementation stays sequential even when two tasks have independent dependencies.

| Task | Trace | Dependencies | Task-specific verification command |
| --- | --- | --- | --- |
| T-036 | R-033, I-026 | None | `python -m unittest tests.test_autonomy_eval.TrialOutcomeTests` |
| T-037 | R-034, I-027 | T-036 | `python -m unittest tests.test_autonomy_eval.PairedRunnerTests tests.test_live_agent_eval` |
| T-038 | R-035, I-028 | T-037 | `python -m unittest tests.test_autonomy_eval.FixtureCatalogTests` |
| T-039 | R-036, I-029 | T-038 | `python -m unittest tests.test_autonomy_recovery.RecoveryScenarioTests` |
| T-040 | R-037, I-030 | T-038,T-039 | `python -m unittest tests.test_autonomy_recovery.RecoveryPilotTests` |
| T-041 | R-038, I-031 | T-040 | `python -m unittest tests.test_autonomy_recovery.MethodSelectionTests` |
| T-042 | R-039, I-032 | T-041 | `python -m unittest tests.test_scaffold tests.test_template` |
| T-043 | R-040, I-033 | T-038,T-040 | `python -m unittest tests.test_autonomy_eval.SkillComparisonTests` |
| T-044 | R-041, I-034 | T-041,T-042,T-043 | `python scripts/validate_template.py` |

## Milestone 1

### T-036 · Make trial acceptance reflect the actual outcome

**Files:** Create `scripts/autonomy_eval.py` and `tests/test_autonomy_eval.py`.

Build the smallest standard-library fixture and result types. Separate `trial_status` (`completed`, `interrupted`, `timed_out`, `unavailable`, `invalid`) from `verification_status` (`passed`, `failed`, `unmeasured`). `accepted` is true only for a valid completed trial with verified outcome, approved change scope, and successful cleanup. A planned interruption followed by a successful resume may count as a completed trial and must still record the interruption. Record unauthorized action attempts separately from changed paths. Metrics and scope checks that cannot be observed carry an explicit status. Use an independent parent-owned verifier over allowlisted synthetic outputs. Avoid running arbitrary code copied from fixtures or Markdown. Unit-test a passing outcome, false success despite a passing oracle, partial results, blocked capabilities, changed scope, and failed cleanup.

**Done when** the negative controls cannot contribute to accepted totals, and trial outcomes are distinguishable from tool and oracle availability.

### T-037 · Run the same task against real starter variants

**Files:** Modify `scripts/autonomy_eval.py`, `scripts/live_agent_eval.py`, `tests/test_autonomy_eval.py`, and `tests/test_live_agent_eval.py`.

Keep legacy `--smoke` available and describe it as a prompt comparison. Add `--paired --fixture ID --runs N --baseline-source PATH` with optional `--candidate-source PATH`, `--timeout-seconds N`, and `--json`. Allow only declared fixture IDs and local reviewed source roots. Generate starter arms through `scripts/scaffold.py`, then overlay the same synthetic project content and fixture contract without copying this repository's `SPEC.md`, `TASKS.md`, `.codex-state`, or sessions. The plain arm receives the same user task, project facts, tools and permissions. Each arm gets a fresh temporary directory and clean client session. Reuse the existing bounded subprocess support and injectable runner. Alternate or deterministically rotate arm order. Capture observed client version, starter digest, pickup evidence and metrics where exposed. Label client pickup as unmeasured if the runtime exposes no trustworthy signal, even when staging passed. Use offline tests to demonstrate same inputs, real scaffold content, candidate differences, clean isolation, unsupported client and timeout handling. T-037 may use the legacy calculator as a single wiring fixture until T-038 adds the real tasks.

**Done when** a single local entry point prepares the real arms and mock transport tests prove what it passes to the client. A mock test cannot be cited as live pickup.

### T-038 · Add three realistic pilot fixtures

**Files:** Modify `scripts/autonomy_eval.py`, `tests/test_autonomy_eval.py`, `docs/evals/agent-loop-benchmark.md`, and `docs/evals/capability-matrix.md`. Create `tests/fixtures/autonomy_debug.py`, `tests/fixtures/autonomy_web.html`, and `tests/fixtures/autonomy_sources.json` as synthetic inputs.

- `debug` gives a local defect a misleading symptom. The verifier checks multiple inputs and a neighboring behavior, so a hard-coded example fails.
- `browser-flow` has a local static fixture with a state transition whose implementation-level check passes. A browser interaction and resulting DOM or saved state establish the outcome. Report `unmeasured` when the chosen client and verifier cannot observe the rendered path. An HTML source inspection can supplement the evidence.
- `source-report` uses conflicting synthetic records with a dated correction and a defined precedence rule. Verify computed totals and evidence IDs, with at least one plausible stale-source answer rejected.

Each fixture declares allowed paths, initial state, expected observable outcome, required capabilities, a known-good result and a near miss. Put checks in the evaluation suite and keep trusted expectations outside the trial workspace. Document a live pilot with two paired repeats per available fixture and report counts by arm and fixture, separating a product failure from infrastructure unavailability. Use `python scripts/live_agent_eval.py --paired --fixture debug --runs 2 --baseline-source . --json` as the first live command when authorized and runnable. For the remaining fixtures substitute `browser-flow` and `source-report`. Capture sanitized results in the capability matrix or its linked evaluation record. Report unavailable cost, activation or client telemetry as `unmeasured`.

At handoff, save the baseline scaffold's identity and a recipe to reconstruct it from the reviewed source. Keep the baseline path in the local handoff if it survives the session. If a later run reconstructs it, check that its digest matches the saved identity before comparing results.

**Done when** offline controls demonstrate the fixtures can discriminate correct and plausible wrong outcomes, and the pilot status is recorded with its actual denominator.

### T-039 · Add one bounded recovery improvement

**Files:** Create `agent_docs/experiments/adaptive-recovery.md` and `tests/test_autonomy_recovery.py`. Read `.agents/skills/autonomous-build/SKILL.md` and `.agents/skills/context-dump/SKILL.md` for the insertion points.

Write the candidate text as two labeled insertion blocks for the existing Build loop and checkpoint skill. Prepare the pilot source by copying the frozen scaffold to a separate temporary source root and inserting the blocks at those named headings there. Save the changed paths and the baseline and candidate digests. Use one small block in the existing checkpoint for the verified fact, unsuccessful approach, failure category, and next useful observation. For an ambiguous or possibly delivered action, observe current state before repeating it. For a contradicted hypothesis, select a probe that distinguishes the remaining causes. For an unavailable tool, use an authorized equivalent that still supports the needed outcome check, or record what is missing. Retry transient failures within the existing budget when the action is known safe to repeat. Re-read the authoritative register and check relevant state at resume. Reuse the current checkpoint workflow. Keep stale checkpoints supplemental, and keep sensitive data and executable command text outside recovery notes. Add deterministic scenarios that exercise these branches with predeclared results. State explicitly that the scenarios validate the behavior contract and that live behavior will be measured in T-040.

**Done when** each injected failure has a bounded next step, including safe behavior when the original action may already have taken effect, and the candidate can be staged without changing default instructions for normal sessions.

### T-040 · Compare recovery against the frozen baseline

**Files:** Modify `scripts/autonomy_eval.py`, `scripts/live_agent_eval.py`, `tests/test_autonomy_recovery.py`, and `docs/evals/capability-matrix.md`. Create `docs/evals/adaptive-autonomy-pilot.md`.

Use the frozen T-038 starter as the baseline. Run the same two recovery cases in plain, baseline starter, and recovery candidate arms: preferred method unavailable and client interruption after observable partial progress. Require the known fallback and final result to be independently checkable. For the interruption case, resume against the existing state and verify there was no duplicate mutation. Record the checkpoint and client pickup signals actually observed. Add `--scenario tool-unavailable` for `debug` and `--scenario interrupted` for `browser-flow`. Invoke the T-037 paired command with both `--baseline-source` and `--candidate-source` and the scenario flag. For the interruption arm, use the client's supported resume or restart interface, preserving the fixture workspace and recording which kind of continuation was actually observed. If that interface cannot observe the prescribed interruption or continuation, report the arm unavailable. Add deterministic offline tests for injected failures, denominator accounting, and duplicate effects. Compare against a plain client given equivalent retry budget. Cap the first recovery pilot at two repeats per case and arm, with at most one extra client invocation for each deliberately interrupted trial. Run `debug` without a scenario flag as the normal control under the same repeat limit.

Use the small pilot to decide whether to expand evaluation, revise the candidate, or retain current behavior. Expand when the observed candidate runs preserve scope and outcome quality and show a recovery or intervention improvement on the failure cases, with no meaningful regression on the normal control. Report time and cost trade-offs and retain current behavior when results are unavailable, inconclusive, or tied. Save reproducible counts and reasons. A later promotion decision requires repeated evidence on held-out tasks and an append-only ADR under ADR-006. Run `python scripts/codexicon.py verify --mode build` at the first milestone boundary and record the actual queue outcome.

**Done when** the pilot has a defensible result, including a specific unmeasured reason when the client cannot run it, and the next milestone has an explicit decision.

## Milestone 2

### T-041 · Select methods from the task and the available evidence

**Files:** Create `agent_docs/experiments/method-selection.md`. Modify `docs/agent-patterns.md` and `tests/test_autonomy_recovery.py`. Read `.agents/skills/autonomous-build/SKILL.md` and `.agents/skills/investigate/SKILL.md` for the insertion points.

For substantial work, derive an outcome, first discriminating observation, preferred available method, fallback, and verifier from the existing task rubric. Prepare the candidate using the same two-source staging procedure as T-039. Examples cover direct edits, diagnosis, source comparison, browser interaction and native desktop readback. Prefer an approved API or connector when it provides the required result. Use interaction tools when the interaction itself is part of acceptance. Apply current permissions and existing budgets. Preserve the direct path for trivial work and measure the method choice only when an actual trace supports it.

**Done when** the scenario set checks the direct, diagnostic, rendered, fallback and blocked paths, and the pilot can compare selection with the current workflow.

### T-042 · Give initialized projects a practical verification path

**Files:** Modify `.agents/skills/init/SKILL.md`, `agent_docs/operations.md`, `docs/build-contracts.md`, and `tests/test_template.py`.

Teach initialization to record the project-owned launch or entry point, safe seeded inputs, the observable state or artifact, and a reproducible outcome check for relevant surfaces. Use the running UI and logs for web work where available, documented input/output for CLI work, and a fresh app state or saved artifact for native desktop work. Record missing infrastructure and partial coverage explicitly. Keep platform-native check parity and existing receipt behavior. Exercise the fresh starter as well as the existing template validator.

**Done when** the generated guidance can be followed for representative web, CLI and desktop cases and the starter still scaffolds cleanly.

### T-043 · Evaluate proposed skill changes before promotion

**Files:** Modify `scripts/autonomy_eval.py`, `scripts/live_agent_eval.py`, and `tests/test_autonomy_eval.py`. Create `docs/evals/skill-comparison.md`.

Add a small local comparison over the existing runner and outcome format. Compare a pinned current skill, a candidate skill, and a no-skill control where informative. Use the same task and input fixtures with positive activation cases, near misses, and held-out cases. Distinguish an observed invocation from skill presence. Report false triggers, missed triggers, outcome quality, time and available cost. Keep proposed edits in a reviewable candidate source, and describe promotion as a maintainer decision backed by evidence. Use an existing first-party skill as the pilot. Follow the existing provenance workflow for any approved external skill.

**Done when** maintainers can repeat the comparison and detect an apparently helpful skill that misroutes or regresses a held-out case.

### T-044 · Integrate the measured changes and document the boundaries

**Files:** Modify `docs/evals/agent-loop-benchmark.md`, `docs/evals/capability-matrix.md`, `docs/maintainers.md`, and `docs/upgrading.md`. Create `agent_docs/decisions/ADR-007-adaptive-autonomy-rollout.md` if a consequential rollout decision is made. A default change also requires an explicit rollout task with the exact affected skill and documentation paths after the decision is recorded.

Record what the live client measured, what the deterministic tests established, and what remains unmeasured. Document repeated comparison commands and compatibility with earlier versions. Keep model selection, increased delegation, and any specialist defensive security or desktop integrations as separate rollout decisions supported by the applicable capability evidence. Complete the canonical checks with `python scripts/codexicon.py verify --mode build`, `python scripts/render_playbook.py --check`, `python scripts/codexicon.py spec-check`, and `python scripts/codexicon.py tasks-next --json`. Record the actual queue outcome and any separate historical receipt or client blocker. Where a starter-facing file changes, verify the existing scaffold and release-identity checks without performing Ship actions.

**Done when** the evaluation can be repeated from the checked-in protocol and the result clearly supports the behavior and defaults reported to the user.

## References for implementation

- Outcome-based evaluation and runtime observation. [Anthropic agent evals](https://www.anthropic.com/research/demystifying-evals-for-ai-agents), [OpenAI harness engineering](https://openai.com/index/harness-engineering/)
- Mixed verification surfaces and safe re-observation. [gstack QA](https://github.com/garrytan/gstack/blob/main/docs/skills.md#qa), [agent-desktop](https://github.com/vercel-labs/agent-desktop/blob/main/skills/agent-desktop/SKILL.md)
- Paired skill comparisons and evaluation controls. [Agent Skills evaluation](https://agentskills.io/skill-creation/evaluating-skills), [Rethinking the Evaluation of Harness Evolution](https://arxiv.org/abs/2607.12227)
