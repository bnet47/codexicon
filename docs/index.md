---
layout: null
title: Codexicon — Codex Agent Harness
description: A production-minded, inspectable harness for agent-driven development with Codex.
---

# Codexicon

## A production-minded Codex agent harness

Codexicon turns agent-driven development into an inspectable path from project context to verified, explicitly authorized delivery.

<p>
  <a href="https://github.com/new?template_name=codexicon&amp;template_owner=bnet47"><strong>Use this template</strong></a>
  ·
  <a href="https://github.com/bnet47/codexicon"><strong>View the repository</strong></a>
  ·
  <a href="repo-template-playbook.html"><strong>Open the visual playbook</strong></a>
</p>

## Choose a starting point

- **New repository:** [create from the GitHub template](https://github.com/new?template_name=codexicon&amp;template_owner=bnet47).
- **Existing repository:** read the [adoption and diagnostics guide](codex.md).
- **Operating model:** review the [build contracts](build-contracts.md), [agent patterns](agent-patterns.md), and [security model](codex.md#credential-and-git-gates).
- **Maintainers:** use the [maintainer and release guide](maintainers.md).

## What the harness provides

- Durable project context with small always-loaded rules and focused supporting documentation.
- Progressive workflows for discovery, implementation, review, production readiness, and release.
- Canonical lint, test, security, doctor, and verification commands across local and CI environments.
- Explicit authority boundaries for Git, deployments, external messages, spend, and production changes.
- Safe starter scaffolding and reproducible release validation for template consumers.

## Capability policy and evidence

Inspect the validated [capability policy](../.codex/capabilities.toml) and
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
consequential decisions in the append-only [decision journal](../agent_docs/decisions/)
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
