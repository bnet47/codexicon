---
name: context-dump
description: Save a human-readable checkpoint when requested or needed for session handoff. Primary agent only; not routine completion.
---

# Context checkpoint

Create a concise checkpoint that lets a fresh Codex task continue without transcript archaeology.

## 1. Gather current evidence

Inspect the active request/spec/plan, current diff or changed files, latest verification, and blockers. Do not copy secrets, large logs, or code that already exists in tracked files.

## 2. Write the checkpoint

Save `agent_docs/sessions/[YYYY-MM-DD]-[slug].md`:

```markdown
# Checkpoint: [Short title]

**Date:** [YYYY-MM-DD]
**Related spec/plan:** [relative links or none]

## Completed
- [Outcome with file or task reference.]

## Current state
- Working: [verified behavior]
- Partial: [specific incomplete work]
- Broken: [known failure, or none]

## Verification
- `[command]` — [result and when run]

## Next actions
1. [Immediate concrete action.]

## Blockers and decisions needed
- [Blocker, owner, and needed input, or none]

## Decisions and assumptions
- [Decision plus rationale.]

## Dead ends
- [Attempt] — [evidence it failed] — [better next approach]

## Resume note
[One paragraph with the minimum critical context.]
```

## 3. Keep durable and ephemeral guidance separate

Do not place session state in `AGENTS.md`; it is always-loaded repository guidance. Do not require an MCP memory service. If a connected memory tool is available and the user wants cross-project memory, store only the compact resume note.

Do not commit or push the checkpoint unless the user asks to ship or explicitly requests a checkpoint commit.
