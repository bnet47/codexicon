---
name: brainstorm
description: Resolve unclear feature behavior or approach and update SPEC.md. Use for genuine uncertainty; not small or precise changes.
---

# Brainstorm

Announce: "I'm using brainstorm to resolve the feature choices before implementation."

## 1. Load relevant project context

Read root `SPEC.md` and `TASKS.md` when present plus only the architecture, conventions, decisions, or prior specs relevant to the feature. If the repository is still unconfigured, route to `$discover` so the root contract is created.

## 2. Resolve the problem

Ask only genuinely blocking questions, batching related questions when practical, and stop when you can state:

- the problem and affected person;
- verifiable success;
- constraints and non-goals;
- the smallest shippable slice;
- unresolved risks.

## 3. Compare approaches

Present two or three genuinely viable approaches with tradeoffs in behavior, complexity, reversibility, and verification. Recommend one and explain why. Ask for a choice only when the alternatives materially change the product or cost; otherwise proceed with the recommended reversible option and state the assumption.

## 4. Write the spec

After the direction is clear, append the requirements, interfaces, acceptance, anti-goals, assumptions, and a dated amendment to the root `SPEC.md` in place. Use the existing contract sections; do not create a separate brainstorm artifact:

```markdown
## Amendments
- **[YYYY-MM-DD]:** [Chosen direction and rationale.]
```

Put the chosen problem, solution, acceptance, non-goals, constraints, first slice,
and open questions in the matching root `SPEC.md` sections before adding the dated
amendment entry.

Run `python scripts/codexicon.py spec-check`. Self-check that every criterion is testable, no placeholder remains, anti-goals are explicit, and the first slice is complete rather than scaffolding. For authorized implementation, use `$write-plan` to create or validate `TASKS.md`, then enter the shared `$autonomous-build` loop without a routine approval turn. Use task states `TODO`, `ACTIVE`, `BLOCKED`, and `DONE`; queue outcomes are `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID`.

Pure explanations and read-only reviews are exempt from code-generation ceremonies and do not write `SPEC.md` or `TASKS.md`.

Build has one writer in the shared checkout: the primary agent by default. An explicitly chosen `implementer` may write one bounded task sequentially; the primary agent re-reads the changed paths and owns integration and final verification. Never run concurrent writers. Do not invoke Git.
