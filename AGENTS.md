# AGENTS.md — [PROJECT_NAME]

> Durable repository guidance for Codex. Keep this file short; detailed workflows belong in skills and project facts belong in `agent_docs/`.

## Project

- **Name:** `[PROJECT_NAME]`
- **Purpose:** `[one sentence describing the problem and intended outcome]`
- **Stack:** `[language · framework · data store · deploy target]`
- **Phase:** `[idea | prototype | alpha | production]`
- **Owner:** `[name or GitHub handle]`

If these fields are still placeholders, treat the repository as an unconfigured template. Use `$discover` before making product or stack decisions, then `$init` to configure the repository.

## Commands

Run commands from the repository root.

```bash
./scripts/setup.sh              # install dependencies and prepare local config
./scripts/dev.sh                # start the local development environment
./scripts/lint.sh               # lint, format-check, and type-check
./scripts/lint.sh --fix         # apply safe lint/format fixes
./scripts/test.sh               # run the full test suite
./scripts/security.sh           # scan tracked/non-ignored safe files for credentials
./scripts/deploy.sh staging     # deploy to staging
./scripts/deploy.sh prod        # production; requires DEPLOY_APPROVED=true
```

Before initialization, native Windows can run `./scripts/lint.ps1` and `./scripts/test.ps1`. `$init` must create equivalent native wrappers or platform-neutral commands for every command the configured project supports; do not silently substitute weaker verification.

## Working agreements

- Start from the requested outcome and done conditions. Inspect first; preserve unrelated changes.
- Make reversible assumptions only when local evidence supports them. Ask when a choice materially changes the result.
- Prefer the smallest complete solution. Use `rg` for search and `apply_patch` for manual edits.
- Load only relevant context. Use targeted commands and bounded output; do not dump whole logs, generated files, or minified content when an excerpt proves the point.
- Communicate densely: no request restatement, filler, or repeated summary. Preserve exact code, commands, paths, identifiers, and errors. Clarity wins for risk or ambiguity.
- Verify proportionally: full lint/tests for code, config, generated artifacts, and shipping; security before Git publication; applicable structural checks for documentation-only work.
- Report commands, results, and anything not verified.

## Workflow routing

Codex sees skill metadata first and loads full instructions only when relevant.

- Project lifecycle: `$discover` → `$init`; unclear feature: `$brainstorm`; precise written requirement: `$spec` → `$write-plan` when needed.
- Implementation: `$quick` for clear small work; `$execute-plan` for an approved plan with independent tasks.
- Assurance: `$investigate` for unknown causes; `$architecture-review` for costly choices; `$review` after building; `$ship` only on an explicit Git request.
- Release safety: `$production-readiness` before a first launch or material production change.
- Communication: `$concise` when the user asks to minimize tokens without reducing engineering rigor.

Do not force ceremony onto a clear task. Plans and subagents are tools for reducing risk and latency, not mandatory stages.

## Subagents

- Delegate only concrete independent work when separate context or parallelism justifies the extra tokens.
- Prefer parallel reading over simultaneous edits. Give each agent a scope, output contract, and verification target.
- The primary agent owns integration and final verification. Never assume agents can safely edit one checkout concurrently.
- Branches, worktrees, commits, and PRs require explicit user authority. Project profiles live in `.codex/agents/`.

## Security and change boundaries

- Never read or write credential-bearing `.env` / `.env.*` files (except `.env.example`), `secrets/**`, private-key files, credential JSON, or user credential stores such as `.npmrc`, `.netrc`, `.aws/credentials`, `.ssh/id_*`, `.kube/config`, and `.docker/config.json`.
- Never enumerate the environment or print secret-like variables. Use injected values without displaying them.
- Never commit credentials. Only documented placeholder files such as `.env.example` may be tracked.
- Do not push directly to `main`; use a branch and pull request when shipping is requested.
- ADRs are append-only. Create a new ADR to supersede a prior decision.
- Destructive operations, production deploys, external messages, and writes to third-party systems require explicit authorization.
- If scope expands into more than five unrelated files, explain why before continuing.

## Context map

Load these only when the task needs them:

| Topic | Source |
|---|---|
| System shape and integrations | `agent_docs/architecture.md` |
| Entities and persistence | `agent_docs/data-model.md` |
| Project-specific conventions | `agent_docs/conventions.md` |
| Security boundaries and evidence | `agent_docs/security.md` |
| Operations, recovery, and release | `agent_docs/operations.md` |
| Accepted technical decisions | `agent_docs/decisions/` |
| Approved charters and specs | `agent_docs/briefs/` |
| Implementation plans | `agent_docs/plans/` |
| Human-readable checkpoints | `agent_docs/sessions/` |
| Codex setup and extension points | `docs/codex.md` |

Nested components may add an `AGENTS.md` or `AGENTS.override.md` for rules that apply only to that subtree.
