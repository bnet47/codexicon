# ADR-005: Bounded capability policy without a new runtime

**Status:** Accepted
**Date:** 2026-09-11
**Supersedes:** None

## Context

The evolution evaluation recommends more autonomous reversible decisions,
bounded self-improvement, selective independent review, tiered verification,
and clearer decision visibility. It also rejects a daemon, scheduler, generic
autonomous runtime, and third-party persistence dependency for the template.

## Decision

Add a small project-local `.codex/capabilities.toml` policy with explicit
strict, balanced, and autonomous profiles. `python scripts/codexicon.py
capabilities` validates and reports the policy; skills consume it as guidance.
The policy owns budgets, review thresholds, verification tiers, and escalation
invariants, but it does not execute shell text, keep a process alive, grant
Git/deployment authority, or replace `SPEC.md`/`TASKS.md`.

Use append-only decision records for consequential assumptions and decisions.
Keep deterministic evaluation evidence separate from live-client claims.

## Alternatives considered

- **No structured policy:** lowest implementation cost, but profile behavior and
  budgets remain prose-only and drift is hard to detect.
- **Persistent orchestration runtime:** more automation, but adds an untested
  authority and recovery subsystem that conflicts with the template's local-
  first, no-daemon boundary.
- **Validated policy plus skill guidance:** makes the useful boundaries
  inspectable and testable while keeping execution in Codex's existing loop.

## Consequences

Positive: downstream projects can choose a bounded profile, reviewers have
explicit triggers, and documentation can point to one validated contract.

Trade-off: the policy is not an execution engine; client behavior and live
telemetry remain measured only where a supported client exposes them.

## Verification

- `python -m unittest tests.test_codexicon tests.test_template`
- `python scripts/validate_template.py`
- `python scripts/codexicon.py capabilities --json`
