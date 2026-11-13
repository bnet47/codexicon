# ADR-007: Retain adaptive-autonomy candidates pending live evidence

**Date:** 2026-11-14
**Owner:** Repository owner and Codex
**Status:** Accepted
**Evidence:** `agent_docs/plans/2026-11-13-adaptive-autonomy-plan.md`; `docs/evals/adaptive-autonomy-pilot.md`; `docs/evals/skill-comparison.md`; T-036 through T-043 focused receipts; `python scripts/codexicon.py spec-check`
**Supersedes:** None

## Context

Codexicon's current template predates recent work on paired harness evaluation,
recovery behavior, task-method selection, and skill comparisons. The new plan
adds safer verification paths and maintainer-only evaluation, while its live
results are constrained by client timeouts and missing UI, continuation, and
skill-invocation signals. Changing always-loaded skill defaults without those
signals would turn local policy examples into unsupported claims about live
agent behavior.

## Decision or assumption

Adopt the new local evaluation surfaces, the maintainer-facing method-selection
reference, and project-owned behavior-verification paths. Retain the existing
recovery and method-selection skill defaults. Keep both skill candidates
inactive. Do not auto-select models, increase delegation, or automatically
install or enable specialist desktop or security skills.

Revisit candidate promotion only after repeated paired runs cover positive,
near-miss, and held-out tasks, independently verify outcomes, and provide a
trustworthy signal of actual skill invocation. Require no material regression
and a separate append-only maintainer decision for any default change.

## Rationale

The T-038 live pilot accepted none of four debug arms and none of four source
reconciliation arms; seven of eight invocations timed out. T-040's planned live
tool-unavailability and interrupted-browser comparisons had zero attempted
arms because the runner could not observe the required capabilities. T-043's
local integration test passed nine mock arm outcomes, but live skill invocation
remained unmeasured. This evidence supports better evaluation and honest
fallback documentation, not a claim that a candidate improves autonomous
completion.

The decision preserves the current authority, retry, and delegation boundaries
while making task-level verification and candidate evidence easier to inspect.
It avoids converting fixture and mock results into claims about installed
clients.

## Alternatives considered

- Promote the recovery candidate after deterministic scenario tests: rejected
  because the live recovery cases had no observations.
- Promote the method-selection skill candidate after local runner tests:
  rejected because mock outcomes do not establish client activation or
  held-out live behavior.
- Add automatic model selection, higher delegation, or specialist desktop and
  security integrations now: deferred because these need separate
  capability-specific comparisons and explicit authority review.
- Keep the existing harness without adding evaluation or verification paths:
  rejected because maintainers need reproducible denominators, clear
  unmeasured states, and project-specific outcome checks.

## Impact

The repository gains deterministic recovery and method-selection contracts,
paired skill-comparison tooling, and initialization guidance for web, CLI, and
native desktop outcomes. The live Codexicon default skills remain unchanged.
Clients without rendered-state, continuation, or activation telemetry receive
explicit `unavailable` or `unmeasured` results. Any later change to default
behavior, delegation, model policy, or specialist capability requires a new
task trace and append-only decision.
