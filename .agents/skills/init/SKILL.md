---
name: init
description: Configure an uninitialized project from an approved charter: stack, scripts, identity, optional Git, and verification.
---

# Initialize the project

Announce: "I'm using init to turn the approved project context into a working development environment."

## 1. Establish context

Read the approved charter in `agent_docs/briefs/` and inspect the repository for existing code, package manifests, and Git state. Do not overwrite an existing stack or working command without explaining the conflict.

If neither a charter nor equivalent explicit project context exists, stop and recommend `$discover`.

## 2. Resolve only missing choices

Ask only for decisions that cannot be inferred safely:

- language, framework, data store, and deploy target;
- whether an existing remote/repository must be preserved;
- whether the project needs external documentation or system context through MCP;
- any version or platform constraints.

When the user has no preference, recommend the smallest stack that fits the charter and explain the tradeoff briefly. Use `$architecture-review` if the choice is expensive to reverse.

## 3. Configure the repository

- Fill project identity in `AGENTS.md`, `README.md`, and relevant `agent_docs/` files.
- Confirm the project's actual licensing policy and replace the generic template copyright holder in `LICENSE` with the chosen owner when appropriate.
- Replace the template reporting guidance in `SECURITY.md` with the project's real private vulnerability route and accountable response owner before public or production use.
- Complete the applicable boundaries and owners in `agent_docs/security.md` and `agent_docs/operations.md`; remove irrelevant template prompts rather than claiming they pass.
- Create the actual stack skeleton and package metadata; remove template-only code that conflicts with it.
- Replace `scripts/setup.sh`, `dev.sh`, `lint.sh`, and `test.sh` with real commands. Replace `deploy.sh` only when deployment is in scope.
- Preserve `scripts/security.sh` and `scripts/security.ps1` as equivalent gates. Add ecosystem dependency, image, or infrastructure audits when applicable; do not remove the built-in credential scan without an equal or stronger local replacement.
- Make an explicit static-analysis decision for the configured source languages and platform. Prefer repository-level GitHub CodeQL default setup when the repository is eligible and the stack is supported; otherwise select an appropriate SAST alternative or document why static analysis is not applicable. Record the scanner, language scope, triggers, alert owner, and query/rule policy in `agent_docs/security.md`. Do not enable an external service or commit a reusable provider workflow without explicit authority and confirmed repository eligibility.
- Support the developer platforms named in the charter. For native Windows projects, add equivalent `.ps1` wrappers or document platform-neutral commands; each path must run the same underlying checks.
- Preserve the lint/test verification receipt contract: call `.codex/hooks/codex_hook.py emit-success lint|test` only after the underlying check succeeds. If the project removes that contract, update the hooks, tests, and `docs/codex.md` together.
- Replace the template validation workflow in `.github/workflows/ci.yml` with CI that installs the selected stack and runs the same canonical lint, test, and security scripts.
- Create `.env.example` with names and comments only when environment variables are needed. Never create or read a real credential file.
- Leave MCP absent unless the project needs external context. When needed, start from the commented project pattern, review the server and tool schemas, keep it disabled until the user trusts it, prefer read-only tools and scoped credentials, and record the trust boundary in `agent_docs/security.md`.
- Update `.gitignore` for generated outputs and local state.
- Initialize Git only when no repository exists and the user chose a fresh local repository. Do not commit, add a remote, push, or open a PR unless separately requested.
- When Git is enabled, inspect any existing hooks configuration before running `scripts/install-git-hooks.sh` or `.ps1`. Preserve or deliberately integrate existing hooks; never silently overwrite a different hooks path.

Commands must fail when unconfigured or when their underlying check fails. Never leave success-printing stubs.

## 4. Verify

Run the configured commands, in order, through the platform path used by the project:

```bash
./scripts/setup.sh
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
```

Use the equivalent `.ps1` commands on native Windows when those are the configured platform path.

Start the development command long enough to confirm it launches when practical, then stop it cleanly.

After the project is trusted in Codex, use `/hooks` and the live smoke checklist in `docs/codex.md`. Report hook enforcement as unverified until that surface-specific check succeeds.

## 5. Report

Summarize the selected stack, security/operations baseline, files created or replaced, exact verification results, Git/hook status, and any remaining manual setup. Offer `$brainstorm`, `$spec`, or `$quick` for the first slice.
