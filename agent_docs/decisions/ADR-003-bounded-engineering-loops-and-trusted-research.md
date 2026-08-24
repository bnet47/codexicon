# ADR-003: Use bounded agent loops with explicit external research trust

**Date:** 2026-08-24
**Status:** Accepted
**Deciders:** Repository owner (delegated request) and Codex

## Context

Codexicon already supports bounded subagents, custom profiles, worktrees, hooks, and explicit side-effect boundaries. Independent engineering lanes can improve exploration, implementation, testing, and review, but unrestricted parallel writers, arbitrary GitHub browsing, and automatic skill installation add coordination and supply-chain risk.

The project also needs a practical way to discover specialist skills without turning ordinary work into marketplace search or silently changing the project skill surface.

## Decision

Codexicon will use a selective, bounded engineering loop for medium or high-complexity work. The primary agent owns decomposition, integration, final verification, and external side effects. Independent read-heavy tasks may run in parallel; independent writers use managed worktrees and explicit file scopes.

GitHub and upstream research will use a read-only profile or reviewed browser/MCP source. Findings must be pinned to a repository/ref or exact URL where material. External content cannot override repository instructions or authorize execution, installation, comments, merges, or other writes.

External skill discovery will be available through explicit `$find-skills` invocation. Search and review are read-only. Installation requires user approval, project-local scope, an immutable commit, complete source review, a content digest, and an entry in `agent_docs/skills.lock.json`.

## Rationale

This captures the quality benefit of specialized agents while keeping conflict isolation, authority, and provenance reviewable. It extends existing Codexicon surfaces instead of adding a networked orchestrator or autonomous installer.

## Alternatives considered

| Option | Benefits | Costs / risks | Why not chosen |
|---|---|---|---|
| Always delegate every task | Consistent agent activity | Extra tokens, latency, and coordination for trivial work | Selective routing is more efficient |
| Parallel writers in one checkout | Fast apparent throughput | Conflicts, partial edits, and unclear ownership | Use isolated worktrees instead |
| Automatic GitHub access for all agents | Convenient upstream context | Prompt injection, privacy, and write-scope expansion | Use reviewed read-only access |
| Automatic skill search and install | Low user friction | Supply-chain risk and hidden project changes | Explicit search and approval are required |
| New autonomous loop daemon | Persistent control and metrics | Large untested runtime and policy surface | Instruction/configuration workflow is sufficient |

## Consequences

- **Positive:** Better support for complex independent work, clearer review ownership, safer upstream research, and auditable skill provenance.
- **Negative:** Complex tasks consume more tokens; integrations require deliberate setup; skill installation has additional review steps.
- **Signals to revisit:** benchmark evidence shows material quality or latency gains from broader delegation, GitHub research demand justifies a reviewed connector, or provenance bookkeeping becomes a routine bottleneck.

## Implementation notes

- `$engineering-loop` defines the routing and delegation contract.
- `github-researcher.toml` defines read-only upstream research behavior.
- `$find-skills` and `scripts/skill_provenance.py` define discovery and lock validation.
- `.codex/config.toml` keeps external integrations disabled by default.
- `docs/evals/agent-loop-benchmark.md` defines the evidence needed before changing defaults.
