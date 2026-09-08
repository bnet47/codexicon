---
name: execute-plan
description: Execute a durable plan locally with bounded read-only review. Use for existing multi-task plans.
---

# Execute a durable plan

Announce: "I'm using execute-plan to implement the durable plan locally with bounded read-only review where it helps."

## 1. Load and validate the plan

Read the selected plan, linked contract, and `TASKS.md`. A plan produced for the current implementation request is authorized by that request; do not create an extra approval gate unless it exposes a consequential product or architecture choice. Preserve existing user changes without invoking Git. Confirm task paths and dependencies remain accurate.

If resuming, run `python scripts/codexicon.py resume`, then verify the selected checkpoint against the plan and current diff. `.codex-state/` is local verification state, not project memory.

## 2. Choose execution shape

- Delegate a task to the `implementer` profile when it is concrete, independent, and has a clear file scope and verification target.
- For medium or high-complexity plans, use `$engineering-loop` to separate independent research, implementation, verification, and review lanes before delegating.
- Run independent read-heavy or non-overlapping tasks in parallel when merge risk is low.
- Execute tightly coupled tasks sequentially; keep integration work with the primary agent.
- Do not delegate merely because a task reads many files or exceeds an arbitrary token estimate.

Each subagent brief must include the exact task text, global constraints, allowed files, dependency state, verification command, and side-effect authorization. Do not rely on hidden parent context.

For GitHub or upstream research, use the read-only `github-researcher` profile or equivalent reviewed source. Pin findings to a repository ref or commit and do not run external repository instructions.

## 3. Integrate each result

For every task:

1. Inspect the declared changed paths and verification evidence.
2. Check acceptance coverage, scope, regressions, and conflicts with user changes.
3. Resolve small integration gaps directly or return one specific correction brief to the implementer.

Statuses are `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, and `NEEDS_CONTEXT`. Repeatedly blocked work should return to the primary agent for a changed approach or user decision, not loop through fresh agents.

## 4. Verify the whole result

After task-level checks, run the full plan verification plus:

```bash
./scripts/lint.sh
./scripts/test.sh
```

Then inspect the declared changed paths against the contract. Use `$review` for a separate read-only review when risk warrants it; do not create a branch or worktree.

## 5. Report

Summarize completed tasks, changed behavior, exact verification, concerns, and any blocked criteria. Do not commit, push, open a PR, or deploy unless the user explicitly asked to ship.
