---
name: retro
description: Reassess direction after a milestone, repeated blockage, scope drift, or an invalid plan. Produces continue, stop, or pivot; not defect debugging.
---

# Retro

Announce: "I'm using retro to step back and assess direction."

## 1. Load evidence

Read the relevant charter/spec, plan, checkpoints, accepted decisions, current diff, and verification state. Note missing or empty evidence rather than inferring a history that is not recorded.

## 2. Assess

Answer with concrete evidence:

- **Direction:** Is the original problem and outcome still correct? Has scope moved away from it?
- **Execution:** What completed cleanly, blocked, or required rework, and why?
- **Decisions:** Which assumptions or ADRs no longer fit the evidence?
- **Debt:** What shortcut or ambiguity creates the largest future risk?
- **Workflow:** Did planning, context management, or delegation improve outcomes or add overhead?

## 3. Report

```markdown
# Retro: [Project or feature] — [YYYY-MM-DD]

## Working
- [Evidence-backed strength.]

## Not working
- [Evidence-backed problem.]

## Scope drift
- [Original intent versus current state.]

## Decisions to revisit
- [ADR or assumption.]

## Recommended changes
1. [Highest-leverage action.]

## Verdict
CONTINUE | STOP | PIVOT

[Rationale and immediate next move.]
```

Save to `agent_docs/sessions/[YYYY-MM-DD]-[slug]-retro.md` when a durable report is useful or requested.

## 4. Act only within authority

Continue ordinary in-scope implementation when the verdict is CONTINUE and the request includes it. For STOP or PIVOT, recommend the appropriate spec, ADR, or plan updates and perform them only when already authorized. Never auto-commit, push, open a PR, or rewrite accepted ADRs as a retro side effect.
