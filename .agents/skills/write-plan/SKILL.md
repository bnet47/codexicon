---
name: write-plan
description: Turn SPEC.md into dependency-aware local tasks with traces, file scopes, acceptance mapping, and verification.
---

# Write an implementation plan

Announce: "I'm using write-plan to turn SPEC.md into verifiable local tasks."

## Inputs

Read root `SPEC.md`, relevant architecture and conventions, applicable ADRs, and the current target code. Do not require a separate approval turn when the current request authorizes implementation. Do not invoke Git.

## Task design

- Map every acceptance criterion to at least one task and verification step.
- Order tasks by real dependency. Identify tasks that are safe to run in parallel.
- Keep tightly coupled edits in one task. Do not split work to satisfy a time or file-count quota.
- Give each task the smallest coherent file scope and name existing interfaces precisely.
- Include migrations, compatibility behavior, error paths, and tests when required by the spec.
- Include requirement and interface IDs for every task. Do not include Git, deployment, or external writes in Build tasks.

## Output

Save `agent_docs/plans/[YYYY-MM-DD]-[feature-slug]-plan.md`:

```markdown
# Implementation Plan: [Feature]

**Spec:** [relative link]
**Date:** [YYYY-MM-DD]

## Global constraints
- [Constraint all tasks must preserve.]

## Acceptance mapping
| Criterion | Task(s) | Evidence |
|---|---|---|
| AC-1 | 1, 3 | [test or inspection] |

### Task 1: [Coherent outcome]

**Depends on:** none | Task N  
**Parallel-safe with:** [task numbers or none]  
**Files:** create/modify/test exact paths  
**Behavior:** [complete expected behavior and error handling]  
**Interfaces:** [signatures, schemas, events, or commands]  
**Verification:** `[exact command]`  
**Done when:** [observable completion condition]
```

Self-review for contract coverage, stale paths, undefined interfaces, unsafe parallelism, placeholders, and runnable verification. Write the corresponding `TASKS.md` register and continue into `$autonomous-build` when implementation is authorized.
