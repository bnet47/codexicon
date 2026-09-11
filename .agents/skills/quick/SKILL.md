---
name: quick
description: Implement a clear, tightly scoped change with no design, dependency, or schema decision. Route uncertainty elsewhere.
argument-hint: "[small change]"
---

# Quick change

Use this path only when the desired behavior and implementation approach are clear.

## Gate

Inspect the target and confirm:

- the change is coherent and tightly coupled;
- no new dependency, migration, or expensive-to-reverse choice is required;
- acceptance can be verified with existing commands or a small focused test.

Before editing, trace the requested code/configuration/document change to an existing `SPEC.md` requirement and interface, and to an existing `TASKS.md` task when a register already covers the work. If no register is needed, a current authorized request may make one minimal append-only amendment to root `SPEC.md`; do not invent a task ID. If the work needs a new queued task or multiple steps, route to `$write-plan` and `$autonomous-build` instead. Pure explanations and read-only reviews are exempt from this gate and from code-generation ceremonies.

If not, route to `$brainstorm`, `$investigate`, `$spec`, or `$write-plan` as appropriate.

## Execute

1. State the trace (`T-* -> R-* -> I-*`, or `R-* -> I-*` when no register is needed) and intended file scope in one sentence.
2. Preserve unrelated edits and implement the smallest complete solution.
3. Add or update focused tests for changed behavior when applicable.
4. Run the narrowest relevant check. For code, configuration, generated artifacts, or shipping readiness, also run:

```bash
./scripts/lint.sh
./scripts/test.sh
```

For documentation-only changes, run the applicable documentation or structural check and explicitly report why the broader test suite was not needed.

5. Review the diff for scope, acceptance coverage, and accidental generated files.
6. Report the outcome and verification evidence.

Use the shared task states `TODO`, `ACTIVE`, `BLOCKED`, and `DONE` and queue outcomes `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID` when a register is involved. Build has one writer in the shared checkout: the primary agent by default. An explicitly chosen `implementer` may write one bounded task sequentially; the primary agent re-reads the changed paths and owns integration and final verification. Never run concurrent writers.

Do not create branches or worktrees, commit, push, open a PR, release, deploy, publish, or modify an external system during Build; those actions belong to the explicitly authorized `$ship` workflow.
