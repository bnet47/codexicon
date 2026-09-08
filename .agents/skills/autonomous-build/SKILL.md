---
name: autonomous-build
description: Execute a local task register with requirement tracing, verification, review, and refinement.
---

# Autonomous Build

Use Build for implementation requests. Work only in the current local checkout and active branch.

## Contract

Read `SPEC.md` before editing. For multi-task work, read `TASKS.md` and validate both:

```text
python scripts/codexicon.py spec-check
python scripts/codexicon.py tasks-next
```

Before every code generation or refactor, state the trace:

```text
Trace: T-001 -> R-001 -> I-001
```

Reject or mark `BLOCKED` any task that cannot be traced to `SPEC.md`.

## Loop

1. Select the next `TODO` task and mark it `ACTIVE`.
2. Inspect the task's declared scope and relevant interfaces.
3. Implement the smallest complete change.
4. Run focused verification.
5. Use the read-only reviewer for medium/high-risk behavior.
6. Fix valid findings and record rejected findings in `TASKS.md`.
7. Run final lint, tests, and security when the queue is complete.
8. Mark the task `DONE` only after evidence is fresh.
9. Continue directly to the next `TODO` task.

Do not return a suggested next prompt while actionable tasks remain.

## Local-first rule

Do not use Git, branches, worktrees, staging, commits, pushes, or pull requests during Build. Track scope and evidence in `TASKS.md`; Git inspection belongs to `$ship`.

## Stop criteria

Pause only for an unrecoverable error, required credentials with no safe local substitute, an unresolvable critical domain decision, a destructive/external/production boundary, repeated failure with no safe alternative, or a complete verified queue. Record blockers and decisions in `TASKS.md`.
