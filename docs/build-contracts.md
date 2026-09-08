# Build contracts

`SPEC.md` is the active repository contract created by `$discover`. It is intentionally kept at the root so a resumed task can find the same product boundary without transcript history.

Use stable IDs for requirements, interfaces, acceptance conditions, and anti-goals:

```markdown
# Specification: [Project or feature]

**Status:** ACTIVE

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
- None.
```

For work spanning multiple coherent changes, create `TASKS.md`:

```markdown
# Task Register

**Contract:** SPEC.md

| ID | State | Requirement | Interface | Scope | Verification |
|---|---|---|---|---|---|
| T-001 | TODO | R-001 | I-001 | `src/...`, `tests/...` | `pytest tests/...` |
```

Validate and advance the register locally:

```text
python scripts/codexicon.py spec-check
python scripts/codexicon.py tasks-next
python scripts/codexicon.py tasks-start T-001
python scripts/codexicon.py tasks-done T-001
python scripts/codexicon.py tasks-blocked T-001
```

Every Build edit must state a trace such as `T-001 -> R-001 -> I-001`. Tasks without a trace are blocked rather than expanded by assumption. Build stays in the current checkout and active branch; Git operations are reserved for `$ship`.
