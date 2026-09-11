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

## Loop

1. Select `RESUME_ACTIVE` before `READY`, then mark the selected `TODO` task `ACTIVE`.
2. Inspect the task's declared scope and relevant interfaces.
3. Implement the smallest complete change.
4. Run focused verification.
5. Use the read-only reviewer for medium/high-risk behavior.
6. Fix valid findings and record rejected findings in `TASKS.md`.
7. Run final lint, tests, and security when the queue is complete.
8. Mark the task `DONE` only after evidence is fresh.
9. Continue directly to the next runnable task; do not return a suggested-next-prompt ending while work remains.

The primary agent is the default sole writer in the shared checkout. An explicitly
chosen `implementer` may write one bounded task sequentially; the primary agent
re-reads the changed paths and owns integration and final verification. Never run
concurrent writers.

Do not return a suggested next prompt while actionable tasks remain.

## Local-first rule

Do not use Git, branches, worktrees, staging, commits, pushes, pull requests, releases, deployments, publication, or external writes during Build. Track scope and evidence in `TASKS.md`; these actions belong to `$ship`.

## Stop criteria

Pause only for an unrecoverable error, required credentials with no safe local substitute, an unresolvable critical domain decision, a destructive/external/production boundary, repeated failure with no safe alternative, or a complete verified queue. Record blockers and decisions in `TASKS.md`.
