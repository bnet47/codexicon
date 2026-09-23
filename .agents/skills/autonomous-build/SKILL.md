---
name: autonomous-build
description: Execute a local task register with requirement tracing, verification, review, and refinement.
---

# Autonomous Build

Use Build for implementation requests. Work only in the current local checkout and active branch. Pure explanations and read-only reviews are exempt from this implementation workflow.

## Contract

Read root `SPEC.md` before editing. For multi-task work, read root `TASKS.md` and validate both:

```text
python scripts/codexicon.py spec-check
python scripts/codexicon.py tasks-next
```

If an authorized implementation has no `TASKS.md`, create the smallest validated
register from the root contract through `$write-plan` without a routine approval
stop. Use persisted states `TODO`, `ACTIVE`, `BLOCKED`, and `DONE`; queue outcomes
are `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID`.

Before every code generation or refactor, state the trace:

```text
Trace: T-001 -> R-001 -> I-001
```

Reject or mark `BLOCKED` any task that cannot be traced to `SPEC.md`.

## Decision visibility and scope gate

Record each consequential assumption or decision in the append-only journal at
`agent_docs/decisions/` as a new `ADR-NNN-short-title.md` record. The record
must include the decision or assumption, rationale, alternatives considered,
impact, owner, date, status, and inspectable evidence. Never rewrite or delete
an accepted record; supersede it with a later record. The journal is guidance
and history, not a runtime or an authority grant.

A related correction may stay in the current task only when it is small,
reversible, directly related, and within the declared system boundary. Keep the
task trace, declared file boundary, and verification scope accurate. Otherwise
stop and explicitly escalate before editing if the change affects authority,
product behavior, schema or data shape, security posture, or an irreversible or
destructive outcome. Credentials, production actions, migrations, external
writes, publication, deployment, legal/compliance commitments, and material
architecture choices also require that escalation. `$ship` or the responsible
human owns those actions; a journal entry does not authorize them.

Before editing, define a task-specific acceptance rubric from the task's
acceptance IDs and `SPEC.md`: required behavior, safety and regression
invariants, fresh verification evidence, and the declared file boundary. Read
the selected profile from `.codex/capabilities.toml` (or validate it with
`python scripts/codexicon.py capabilities --json`) and use its
`max_iterations`, `max_review_cycles`, `max_failed_attempts`, and `max_minutes`
as hard guidance limits. Do not invent a second budget or a task-local
orchestrator.

## Routing eligibility and dispatch contract

Routing is opt-in and advisory. The primary may delegate only an eligible,
non-trivial task after writing a minimum-sufficient dispatch envelope containing
the exact task ID and text, requirement/interface trace, acceptance rubric,
allowed paths, dependency state, verification command, risk/review signals,
side-effect authority (normally none), escalation rule, and `max_depth = 1`.
The worker may not add paths, spawn another worker, change authority, or publish
results. Ineligible, trivial, unsupported, or runtime-unverified work stays on
the primary path; the primary owns integration, acceptance, and the evidence
status for requested versus observed routing.

Budget accounting is precise.
`one iteration` means one implement + focused-check + critique pass.
`one review cycle` means one independent reviewer pass and one correction round.
`one failed attempt` means one failed implementation/focused-check pass requiring recovery.
`max_minutes` starts at task activation and includes implementation, checks, review, and correction.
These counters are local guidance, not a runtime. There is no background
runtime or second task engine.

## Loop

1. Select `RESUME_ACTIVE` before `READY`, then mark the selected `TODO` task `ACTIVE`.
2. Inspect the task's declared scope and relevant interfaces; apply the
   decision-journal and related-scope gate before absorbing any adjacent fix.
3. Implement the smallest complete change against the acceptance rubric.
4. Run focused verification and record whether each rubric item is covered.
5. Apply the deterministic completion gate: acceptance coverage plus fresh
   relevant evidence and no open in-scope correctness, safety, or evidence
   issue. If the gate is met, stop as `ACCEPTED` before optional refinement;
   required configured review and final verification still apply as gate checks,
   not optional refinement. An actionable finding reopens the gate. No open
   issue can be ignored. The early stop remains: if acceptance is met and fresh
   relevant verification is present, stop before any optional refinement,
   subject to the no-open-issue condition above.
6. Otherwise, critique the weakest important aspect of the result: correctness,
   safety, maintainability, usability, or evidence quality as relevant to the
   task; the completion gate is not met.
7. Refine only when the change is meaningful, reversible, within scope, and
   supported by the remaining profile budgets. Re-run the affected focused
   checks after each refinement.
8. The canonical `$autonomous-build` route delegates the read-only reviewer
   when any configured trigger matches in the selected profile: the assessed
   risk is in `required_risk_levels`; the changed-file count is greater than or
   equal to `changed_files_threshold`; or a public API, security, architecture,
   or test-complexity signal is present while its matching
   `review_on_public_api`, `review_on_security`, `review_on_architecture`, or
   `review_on_test_complexity` flag is enabled. Trivial low-risk work below
   the configured file threshold with no enabled signal is exempt. One review
   cycle is exactly one read-only reviewer pass and one correction round; the
   route must not narrow to risk alone. Fix valid findings and record a stable
   finding ID plus exactly one disposition for every finding in completion
   evidence.
9. Detect a plateau when another pass produces no material acceptance,
   regression, safety, or evidence improvement. Bounded improvement is allowed
   only before the completion gate and only when it is meaningful, reversible,
   in scope, and budgeted. Stop before the gate at a plateau, repeated failure,
   exhausted iteration/review/failure/time budget, or a human-owned boundary;
   none of these outcomes converts an open issue into `ACCEPTED`.
10. Run final lint, tests, and security when the queue is complete.
11. Mark the task `DONE` only after evidence is fresh.
12. Continue directly to the next runnable task; do not return a
    suggested-next-prompt ending while work remains.

The primary agent is the default sole writer in the shared checkout. An explicitly
chosen `implementer` may write one bounded task sequentially; the primary agent
re-reads the changed paths and owns integration and final verification. Never run
concurrent writers.

Do not return a suggested next prompt while actionable tasks remain.

This is bounded guidance inside the existing Build loop; `SPEC.md` and
`TASKS.md` remain authoritative. Build is Git-free; Git, branches, worktrees,
staging, commits, pushes, pull requests, releases, deployments, publication,
migrations, credentials, destructive data work, production actions, and
external writes remain explicit `$ship`/human boundaries. A profile cannot
expand that authority. These counters are local guidance, not a runtime. There
is no background runtime or second task engine.

## Verification tiers and Stop outcomes

The current Build writer owns focused iteration checks: run the narrowest
task-specific check after each implementation pass and use it to assess the
acceptance rubric. The primary Build writer owns Build completion: acceptance
coverage plus fresh relevant evidence from the selected profile's Build checks
and no open in-scope correctness, safety, or evidence issue are required, while
the existing task receipts and queue-level lint, test, and security requirements
remain mandatory. The explicitly authorized human/$ship workflow owns Ship.
For commit-only Ship, require commit-tier lint/test/security and
tracked-file/history verification; it may be accepted after authorized commit
verification without release or publication evidence. For publish, merge, or
deploy, add release and publication checks only when that exact authority was
explicitly requested. Never infer or pressure a broader action. Focused or
Build receipts never authorize Ship.

Evidence is fresh only when it follows the latest relevant write, remains within
the selected profile's tier freshness window, and matches the task, source,
contract, and check identity. Safe read-only inspection such as `spec-check`,
`tasks-next`, `inspect`, `doctor`, `resume`, and bounded file reading/search
preserves valid evidence. It must not open protected credential paths, execute
substitutions, use write options, or conceal a mutation. Source/configuration/
task writes, mutating manager commands, unsafe or unknown commands, malformed
state, and protected-path violations invalidate affected evidence and require
the relevant checks again.

Tier-aware completion evidence records `verification_tier`,
`selected_profile`, task/source/contract identities, check identity, and a
freshness record containing the selected profile's configured `window_minutes`,
the resulting `expires_at`, and the responsible owner. The owner of the tier
must rerun the applicable check after expiry or invalidation; the metadata is
auditable guidance and does not create a runtime.

Stop precedence is deterministic: an open in-scope correctness, safety, or
evidence issue means the acceptance-plus-fresh-evidence completion gate is not
met and cannot be ignored. Bounded improvement is allowed only before that
gate and only when it is meaningful, reversible, in scope, and budgeted. Once
the gate is met, stop as `ACCEPTED` before optional refinement. Required review
and final verification are gate checks, not optional refinement; an actionable
finding reopens the gate. Before then,
stop as `PLATEAU`, `REPEATED_FAILURE`, `BUDGET_EXHAUSTED`, or
`HUMAN_BOUNDARY` only to report why the gate cannot safely be reached. No
outcome starts a daemon, scheduler, second task engine, or Ship action.

## Local-first rule

Do not use Git, branches, worktrees, staging, commits, pushes, pull requests, releases, deployments, publication, or external writes during Build. Track scope and evidence in `TASKS.md`; these actions belong to `$ship`.

## Stop criteria

Pause only for an unrecoverable error, required credentials with no safe local
substitute, an unresolvable critical domain decision, a destructive/external/
production boundary, repeated failure with no safe alternative, plateau after
the rubric is otherwise covered, exhausted profile budget, or a complete
verified queue. Record blockers and decisions in `TASKS.md`.
