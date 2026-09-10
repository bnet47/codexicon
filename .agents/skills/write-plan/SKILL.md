---
name: write-plan
description: Turn SPEC.md into dependency-aware local tasks with traces, file scopes, acceptance mapping, and verification.
---

# Write an implementation plan and task register

Announce: "I'm using write-plan to turn SPEC.md into verifiable local tasks."

## Inputs

Read root `SPEC.md`, relevant architecture and conventions, applicable ADRs, the current target code, and `TASKS.md` when present. `SPEC.md` is authoritative; create or amend the root `TASKS.md` register without silently discarding existing tasks or evidence. Do not require a separate approval turn when the current request authorizes implementation. Do not invoke Git.

## Task design

- Map every acceptance criterion to at least one task and verification step.
- Order tasks by real dependency. Identify tasks that are safe to run in parallel.
- Keep tightly coupled edits in one task. Do not split work to satisfy a time or file-count quota.
- Give each task the smallest coherent file scope and name existing interfaces precisely.
- Include migrations, compatibility behavior, error paths, and tests when required by the spec.
- Include requirement and interface IDs for every task. Do not include Git, deployment, or external writes in Build tasks.
- Use the shared persisted states `TODO`, `ACTIVE`, `BLOCKED`, and `DONE`, with dependencies and blocker reasons recorded in the register. The queue outcomes are `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID`. Validate the contract and register with `python scripts/codexicon.py spec-check` and `python scripts/codexicon.py tasks-next --json` before handing off.

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

Self-review for contract coverage, stale paths, undefined interfaces, unsafe parallelism, placeholders, and runnable verification. The plan is descriptive; `TASKS.md` is the authoritative queue. Continue directly into `$autonomous-build` when implementation is authorized, including when the register was just created. Do not end with a suggested next prompt while runnable work remains.

Build has one writer in the shared checkout: the primary agent by default. An explicitly chosen `implementer` may write one bounded task sequentially; the primary agent re-reads the changed paths and owns integration and final verification. Never run concurrent writers. Pure explanations and read-only reviews do not create a plan or task register.
