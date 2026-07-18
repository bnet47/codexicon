---
name: discover
description: Define a new project's problem, user, outcome, constraints, and non-goals before technical choices. Use once for an unconfigured project.
---

# Discover

Announce: "I'm using discover to define the project before we choose how to build it."

## 1. Check the gate

Inspect `agent_docs/briefs/` and the identity section in `AGENTS.md`.

- If an approved project charter already exists, summarize it and ask whether the user wants to revise it. Do not create a duplicate.
- If this is an established repository with clear project identity, stop and route the request to the relevant feature workflow.

## 2. Build understanding

Ask one question at a time and stop as soon as the answer is clear. Prefer no more than six questions total.

Cover only unresolved parts of:

1. What is painful, missing, or expensive today?
2. Who experiences it, and what do they do now?
3. What concrete change should the project create for that person?
4. Why is this worth solving now?
5. What constraints and existing systems are real?
6. What is explicitly not part of the project?

Do not choose a language, framework, database, or deployment target in this workflow.

## 3. Reflect before writing

Return a two- or three-sentence synthesis of the problem, person, and intended outcome. Resolve material corrections before saving.

## 4. Write the charter

Save `agent_docs/briefs/charter-[project-slug].md`:

```markdown
# Project Charter: [Project name]

**Date:** [YYYY-MM-DD]
**Status:** Approved

## Problem
[Pain, affected person, and current cost.]

## Intended user
[A specific person or role and their context.]

## Outcome
[The observable change when the project succeeds.]

## Why now
[Why the work matters now.]

## Constraints
- [Real limit or dependency.]

## Non-goals
- [Explicit boundary.]

## Success signals
- [Observable evidence without prescribing a feature.]

## Open questions
- [Unresolved item, or "None".]
```

Self-check that the charter describes a problem and outcome rather than a predetermined solution, and that non-goals are meaningful.

## 5. Hand off

Offer `$init` to configure the technical environment. Do not commit, push, or open a PR unless the user separately asks.
