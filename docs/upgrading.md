# Upgrading a project from a newer Codexicon release

Codexicon projects are independent repositories. Adopt template improvements deliberately instead of replacing the project with a fresh template copy.

## Compare the project and template

1. Read the newer `TEMPLATE_VERSION` release notes and select changes relevant to the project.
2. Compare the newer template against the project without including generated output, local state, or credential-bearing files.
3. Group differences into scaffolding, project-owned content, and obsolete template material.
4. Apply one coherent safeguard or workflow change at a time, then run the project’s real verification.

Use the project’s current behavior and accepted decisions as the source of truth when template defaults conflict with deliberate local changes.

## Usually safe to adopt with review

- new validation and credential-scanning logic;
- hook bug fixes that preserve the project’s verification receipt contract;
- the 2.7.0 inspection classifier and Build operating guidance, after checking local hook and workflow customizations;
- new opt-in documentation or disabled configuration examples;
- CI hardening that preserves the project’s supported platforms and canonical checks;
- new skills or references that do not replace locally modified workflows.
- the bounded `$engineering-loop`, read-only `github-researcher`, and explicit `$find-skills` workflow after reviewing local delegation and supply-chain policy;

Review each change for local path, runtime, policy, and platform assumptions before applying it.

## Merge instead of overwriting

- `AGENTS.md`, especially project identity, commands, boundaries, and routing;
- `README.md` and public project identity;
- real setup, development, lint, test, security, and deployment scripts;
- stack-specific CI and release configuration;
- `.codex/config.toml`, hooks, and custom agents when the project has local policy;
- `.agents/skills/` when workflows were customized;
- `agent_docs/`, including architecture, data, conventions, security, operations, decisions, briefs, and plans;
- `SECURITY.md`, particularly the real private reporting route and accountable owner;
- environment placeholders, ignore rules, and dependency manifests.

Never replace a project-specific command with a template stub or restore a deleted template placeholder over established project facts.

## 2.7.0 migration note

Adopt the hook classifier and operating guidance as one reviewable change. Merge the relevant `.codex/hooks/codex_hook.py` and `tests/test_template.py` changes together so read-only inspection behavior and its regression coverage stay aligned. Merge `AGENTS.md`, `docs/codex.md`, and applicable skill changes only after comparing local routing and approval policy; preserve project-specific identity, commands, security ownership, and accepted decisions. No state-file migration is required, and external skill discovery or installation remains opt-in.

## 2.8.0 migration note

Adopt the engineering-loop guidance, GitHub researcher profile, and skill provenance lock together. Keep GitHub MCP or browser integrations disabled until the server identity, tool allowlist, credential scope, and data handling are reviewed. Preserve local `.agents/skills/` customizations. If a project already has external skills, record immutable source commits, content digests, licenses, permissions, and review ownership in `agent_docs/skills.lock.json` before enabling updates.

## Adoption checklist

- Selected release changes are mapped to a real project need or safeguard.
- Project identity, commands, supported platforms, and accepted decisions are preserved.
- Credential paths and local state remain untracked and unopened.
- External integrations remain absent, commented, or disabled until explicitly reviewed and trusted.
- Hook changes preserve or deliberately migrate verification behavior.
- The project’s canonical lint, tests, and security checks pass.
- Any live hook or integration change is reviewed in the Codex surface where it will run.
- The project records which template release was reviewed and which changes were declined.
