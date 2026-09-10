---
name: spec
description: Turn a precise request into an executable spec before implementation. Use when documentation is wanted and exploration is unnecessary.
argument-hint: "[request to specify]"
---

# Spec

Announce: "I'm using spec to make the requirement executable in the root SPEC.md before implementation."

1. Read only the relevant project guidance, existing root `SPEC.md`, `TASKS.md` when present, and existing decisions.
2. Ask targeted questions only for missing behavior, constraints, or acceptance evidence. Skip questions when local context resolves them.
3. Create or amend the root `SPEC.md` using this contract structure. Do not make a historical brief the active contract or write only under `agent_docs/briefs/`:

```markdown
# Specification: [Project or feature]

**Status:** ACTIVE
**Revision:** [revision]

## Outcome
[Observable result.]

## Requirements
- **R-001:** [Testable requirement.]

## Interfaces
- **I-001:** [API, file, event, CLI, or component contract.]

## Acceptance
- **A-001:** [Observable acceptance condition.]

## Anti-goals
- **AG-001:** [What will not be built, mocked, or supported.]

## Assumptions
- [Reversible assumption and rationale.]

## Amendments
- **[YYYY-MM-DD]:** [Append-only change.]

## Verification
- `[exact command or inspection]` — [what it proves]
```

Append new requirements, interfaces, acceptance conditions, anti-goals, assumptions, and dated amendments; preserve accepted history and remove placeholders, subjective criteria, and unnecessary implementation detail. Run `python scripts/codexicon.py spec-check`. When implementation is authorized, create/validate `TASKS.md` for multi-task work and continue through `$autonomous-build` without a routine approval turn. Use the persisted task states `TODO`, `ACTIVE`, `BLOCKED`, and `DONE` and queue outcomes `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID`.

Pure explanations and read-only reviews are exempt: answer or review from supplied context without code-generation ceremonies or contract/task writes.

Build has one writer in the shared checkout: the primary agent by default. An explicitly chosen `implementer` may write one bounded task sequentially; the primary agent re-reads the changed paths and owns integration and final verification. Never run concurrent writers.

For multi-task implementation, use `$write-plan` to create and validate `TASKS.md`; `$execute-plan` is only an adapter into the same `$autonomous-build` loop. Do not commit or push unless separately asked.
