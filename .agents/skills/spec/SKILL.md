---
name: spec
description: Turn a precise request into an executable spec before implementation. Use when documentation is wanted and exploration is unnecessary.
argument-hint: "[request to specify]"
---

# Spec

Announce: "I'm using spec to make the requirement executable before implementation."

1. Read only the relevant project guidance and existing decisions.
2. Ask up to three questions only for missing behavior, constraints, or acceptance evidence. Skip questions when local context resolves them.
3. Save `agent_docs/briefs/[YYYY-MM-DD]-[slug].md`, adding `-v2`, `-v3`, and so on rather than overwriting:

```markdown
# Spec: [Name]

**Date:** [YYYY-MM-DD]
**Status:** Approved

## Request
[Precise restatement of the requested outcome.]

## Behavior
[What changes, for whom, and the important interaction or data flow.]

## Acceptance criteria
- [ ] [Observable and testable result.]

## Out of scope
- [Explicit exclusion.]

## Constraints
- [Compatibility, security, performance, or platform requirement.]

## Verification
- `[exact command or inspection]` — [what it proves]
```

Before saving, remove placeholders, subjective criteria, and implementation detail that is not required by the request or an accepted ADR.

Offer `$write-plan` for multi-step implementation. Do not commit or push unless separately asked.
