---
layout: null
title: Codexicon — A repeatable, reviewable path to delivery
description: A repeatable, reviewable path to delivery for agent-driven development with Codex.
---

<p align="center">
  <picture>
    <source media="(max-width: 640px)" srcset="assets/codexicon-readme-hero-mobile.svg">
    <img src="assets/codexicon-readme-hero.svg" alt="Codexicon — a production-minded Codex agent harness for new and established repositories" width="100%">
  </picture>
</p>

# Codexicon

## A repeatable, reviewable path to delivery

Codexicon gives new and established repositories durable context, routed workflows, fresh verification, and explicit boundaries for Git and external effects.

<p>
  <a href="https://github.com/new?template_name=codexicon&amp;template_owner=bnet47"><strong>Use this template →</strong></a>
  ·
  <a href="https://github.com/bnet47/codexicon"><strong>View the repository →</strong></a>
  ·
  <a href="repo-template-playbook.html"><strong>Open the visual playbook →</strong></a>
</p>

## Choose your path

| If you want to… | Start here | You will get |
|---|---|---|
| Start a new project | [Create from the GitHub template](https://github.com/new?template_name=codexicon&amp;template_owner=bnet47) | A clean harness, baseline checks, and a product-first setup path |
| Add Codexicon to an existing repository | Read the [adoption and diagnostics guide](codex.md) | A read-only compatibility plan and conflict-preserving integration |
| Understand the operating model | Review the [build contracts](build-contracts.md), [agent patterns](agent-patterns.md), and [security model](codex.md#credential-and-git-gates) | The workflow, evidence, and authority boundaries in context |
| Maintain or release the template | Use the [maintainer and release guide](maintainers.md) | Versioning, validation, and publication checks |

> **See the whole system at a glance →** [Open the interactive visual playbook](repo-template-playbook.html) for the lifecycle, skill routing, capability tiers, and safety boundaries.

## What the harness provides

- Durable project context with small always-loaded rules and focused supporting documentation.
- Progressive workflows for discovery, implementation, review, production readiness, and release.
- Canonical lint, test, security, doctor, and verification commands across local and CI environments.
- Explicit authority boundaries for Git, deployments, external messages, spend, and production changes.
- Safe starter scaffolding and reproducible release validation for template consumers.

## Verified baseline

| Evidence | Current baseline |
|---|---|
| Release | **2.11.0**, recorded in [`TEMPLATE_VERSION`](https://github.com/bnet47/codexicon/blob/main/TEMPLATE_VERSION) |
| CI | [Ubuntu, Windows, and macOS across Python 3.10 and 3.13](https://github.com/bnet47/codexicon/actions/workflows/ci.yml) |
| Security | [CodeQL and security workflows](https://github.com/bnet47/codexicon/actions) plus canonical local security gates |
| Scope | No provider account, API key, database, hosting platform, or optional integration required to begin |

## Capability policy and evidence

Inspect the validated [capability policy](https://github.com/bnet47/codexicon/blob/main/.codex/capabilities.toml) and
selected profile with `python scripts/codexicon.py capabilities --json`.
Profiles guide bounded refinement and selective, read-only review: use a
task-specific rubric, focused check, weakest-aspect critique, and meaningful
in-scope refinement; triggers include configured risk, changed-file threshold,
and enabled public-API, security, architecture, or test-complexity signals.
Every review finding gets exactly one `accepted`, `fixed`, `rejected`, or
`not_applicable` disposition.

Focused iteration, Build completion, and Ship have separate owners and
evidence. Commit-only Ship requires full lint/test/filesystem-security and
tracked/history checks without release or publication evidence; publish, merge,
or deploy requires that exact authority plus release/publication checks. Record
consequential decisions in the append-only [decision journal](https://github.com/bnet47/codexicon/tree/main/agent_docs/decisions/)
and keep related scope small, reversible, directly related, and within the
declared system boundary.

The [capability matrix](evals/capability-matrix.md) records versions/dates,
denominators, expected/observed outcomes, and explicit unmeasured live-client
claims; raw tool names are not compatibility evidence. The policy adds no
daemon, scheduler, second task engine, Git, deployment, credential access,
external-write, or publication authority. Read the [capability guide](capabilities.md), [build
contracts](build-contracts.md), [agent patterns](agent-patterns.md),
[upgrade guidance](upgrading.md), and [visual playbook](repo-template-playbook.html)
for the synchronized workflow.

> Codexicon improves the development process; it does not make an unfinished application production-ready by itself. Each project still supplies and verifies its own architecture, security, data, operations, and release evidence.

Current template version: **2.11.0**
