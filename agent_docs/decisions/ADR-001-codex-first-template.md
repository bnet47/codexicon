# ADR-001: Make Codex the template's native execution model

**Date:** 2026-07-15  
**Status:** Accepted  
**Deciders:** Repository owner and Codex

## Context

The original template mixed Antigravity, Gemini, Claude Code, Cursor, and an incomplete Codex compatibility layer. Instructions and skills were duplicated across tool-specific directories, Codex hooks contained an absolute path to one workstation while writing state under `.claude/`, and several workflows performed commits or pushes without making that authority explicit. Stack-agnostic claims also conflicted with shipping unused Python and TypeScript prompt loaders.

Codex natively supports root and nested `AGENTS.md` guidance, repository skills in `.agents/skills/`, project configuration and hooks in `.codex/`, project-scoped custom agents, MCP configuration, and managed worktrees. These surfaces remove the need for compatibility copies.

## Decision

The template will use Codex-native repository surfaces as its single source of truth:

- durable behavior and boundaries in a concise root `AGENTS.md`;
- reusable workflows only in `.agents/skills/`;
- custom agents, conservative configuration, and portable lifecycle hooks in `.codex/`;
- project facts and generated artifacts in `agent_docs/`;
- real canonical verification commands in `scripts/`;
- optional external integrations documented for deliberate setup, not enabled with placeholder credentials.

Commits, pushes, PRs, deployments, destructive operations, and third-party writes require explicit user authorization. Subagents are used for bounded independent work, not from arbitrary file-count or token thresholds.

## Rationale

This structure matches Codex discovery and configuration semantics, reduces always-on instruction weight, prevents duplicated workflow drift, works across Codex app/CLI/IDE surfaces, and keeps external side effects reviewable.

## Alternatives considered

| Option | Benefits | Costs / risks | Why not chosen |
|---|---|---|---|
| Keep every harness as a first-class target | Broad nominal compatibility | Duplicate skills and hooks drift; unclear authority; larger maintenance surface | Compatibility was already incorrect and weakened the Codex experience |
| Keep Antigravity primary and add Codex shims | Minimal migration | Preserves wrong invocation syntax, state paths, models, and hook assumptions | Does not satisfy the Codex-first goal |
| Codex-only plugin | Easy distribution | Adds packaging and install lifecycle before the repository workflow is proven | Repo-scoped skills and config are simpler for the template stage |

## Consequences

- **Positive:** one authoritative workflow set, smaller prompt footprint, portable hooks, accurate side-effect boundaries, and testable template invariants.
- **Negative:** users of other coding harnesses must add their own thin adapter instead of relying on bundled copies.
- **Signals to revisit:** a second harness can consume `.agents/skills/` and Codex-compatible hooks without duplication, or the workflow becomes stable enough to distribute as a Codex plugin.

## Implementation notes

Validate JSON, TOML, agent profiles, skill metadata, hook behavior, placeholder boundaries, and obsolete harness references in the template test suite. Do not pin a Codex model in project config; allow the active client and user to choose.
