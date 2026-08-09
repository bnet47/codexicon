---
name: brainstorm
description: Resolve unclear feature behavior or approach and produce an approved spec. Use for genuine uncertainty; not small or precise changes.
---

# Brainstorm

Announce: "I'm using brainstorm to resolve the feature choices before implementation."

## 1. Load relevant project context

Read the project identity and only the architecture, conventions, decisions, or prior specs relevant to the feature. If the repository is still an unconfigured template, route to `$discover`.

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

After the direction is clear, save `agent_docs/briefs/[YYYY-MM-DD]-[feature-slug].md` without overwriting an existing file:

```markdown
# Spec: [Feature]

**Date:** [YYYY-MM-DD]
**Status:** Approved

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

Self-check that every criterion is testable, no placeholder remains, and the first slice is complete rather than merely scaffolding.

Offer `$write-plan` when implementation is multi-step. If the original request already authorizes implementation, continue through the smallest coherent implementation; otherwise stop after the requested brainstorming/spec artifact. Do not commit or push unless separately asked.
