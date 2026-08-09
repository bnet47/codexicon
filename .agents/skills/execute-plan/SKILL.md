---
name: execute-plan
description: Execute an approved plan with bounded delegation. Use after write-plan for independent tasks; not for exploratory or tightly coupled work.
---

# Execute an approved plan

Announce: "I'm using execute-plan to implement the approved plan with bounded task delegation where it helps."

## 1. Load and validate the plan

Read the selected plan and linked spec. A plan produced for the current implementation request is approved by that request; do not create an extra approval gate unless the plan exposes a consequential product or architecture choice. Inspect `git status` and preserve existing user changes. Confirm task paths still exist and dependencies remain accurate; update the plan only when reality invalidates it, and explain material changes.

If resuming, run `python scripts/codexicon.py resume`, then verify the selected checkpoint against the plan and current diff. `.codex-state/` is local verification state, not project memory.

## 2. Choose execution shape

- Delegate a task to the `implementer` profile when it is concrete, independent, and has a clear file scope and verification target.
- Run independent read-heavy or non-overlapping tasks in parallel when merge risk is low.
- Execute tightly coupled tasks sequentially; keep integration work with the primary agent.
- Do not delegate merely because a task reads many files or exceeds an arbitrary token estimate.

Each subagent brief must include the exact task text, global constraints, allowed files, dependency state, verification command, and side-effect authorization. Do not rely on hidden parent context.

## 3. Integrate each result

For every task:

1. Inspect the actual diff and verification evidence.
2. Check acceptance coverage, scope, regressions, and conflicts with user changes.
3. Resolve small integration gaps directly or return one specific correction brief to the implementer.

Statuses are `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, and `NEEDS_CONTEXT`. Repeatedly blocked work should return to the primary agent for a changed approach or user decision, not loop through fresh agents.

## 4. Verify the whole result

After task-level checks, run the full plan verification plus:

```bash
./scripts/lint.sh
./scripts/test.sh
```

Then inspect the combined diff against the spec. Use `$review` for a separate read-only review when risk warrants it.

## 5. Report

Summarize completed tasks, changed behavior, exact verification, concerns, and any blocked criteria. Do not commit, push, open a PR, or deploy unless the user explicitly asked to ship.
