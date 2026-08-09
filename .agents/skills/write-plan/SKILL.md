---
name: write-plan
description: Turn an approved spec into dependency-aware tasks with file scopes, acceptance mapping, and verification. Skip obvious small changes.
---

# Write an implementation plan

Announce: "I'm using write-plan to turn the approved spec into verifiable implementation tasks."

## Inputs

Read the selected spec, relevant architecture and conventions, applicable ADRs, and the current target code. A spec created during the current implementation request is sufficient; do not require a separate approval turn when the request already authorizes the work. Do not assume the newest spec is the right one when several are present; identify it from the request or links.

## Task design

- Map every acceptance criterion to at least one task and verification step.
- Order tasks by real dependency. Identify tasks that are safe to run in parallel.
- Keep tightly coupled edits in one task. Do not split work to satisfy a time or file-count quota.
- Give each task the smallest coherent file scope and name existing interfaces precisely.
- Include migrations, compatibility behavior, error paths, and tests when required by the spec.
- Do not include commits, pushes, deployments, or external writes unless the approved scope explicitly authorizes them.

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

Self-review for spec coverage, stale paths, undefined interfaces, unsafe parallelism, placeholders, and runnable verification. Continue into implementation when the original request authorizes it; offer `$execute-plan` when delegation is useful, or stop after the plan when planning was the requested deliverable.
