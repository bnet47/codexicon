---
name: brainstorm
description: Resolve unclear feature behavior or approach and update SPEC.md. Use for genuine uncertainty; not small or precise changes.
---

# Brainstorm

Announce: "I'm using brainstorm to resolve the feature choices before implementation."

## 1. Load relevant project context

Read root `SPEC.md` when present plus only the architecture, conventions, decisions, or prior specs relevant to the feature. If the repository is still unconfigured, route to `$discover`.

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

After the direction is clear, append the requirements, interfaces, acceptance, anti-goals, assumptions, and any amendment to root `SPEC.md`:

```markdown
# Specification amendment: [Feature]

**Date:** [YYYY-MM-DD]
**Status:** ACTIVE

## Problem
[Who is affected and what fails today.]

## Chosen solution
[User-visible behavior and the selected approach.]

## Acceptance criteria
- [ ] [Specific observable result.]

## Non-goals
- [Explicit exclusion.]

## Constraints and risks
- [Constraint, risk, or dependency.]

## First shippable slice
[Smallest complete proof of value.]

## Open questions
- [Unresolved question, or "None".]
```

Run `python scripts/codexicon.py spec-check`. Self-check that every criterion is testable, no placeholder remains, anti-goals are explicit, and the first slice is complete rather than scaffolding.

For multi-step work, write `TASKS.md` and continue to `$autonomous-build` when implementation is authorized. Do not invoke Git.
