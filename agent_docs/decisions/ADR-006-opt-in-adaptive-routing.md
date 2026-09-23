# ADR-006: Opt-in adaptive intelligence routing

**Date:** 2026-09-23
**Owner:** Repository owner and Codex
**Status:** Accepted
**Evidence:** `agent_docs/plans/2026-09-23-adaptive-intelligence-routing-plan.md`; `SPEC.md` amendment 2026-09-23; `python scripts/codexicon.py spec-check`; official Codex subagent and configuration documentation accessed 2026-09-23
**Supersedes:** None

## Context

Codexicon has a validated capability layer, sequential shared-checkout writer
policy, bounded task loop, selective review, and evidence receipts. The
recommendation package identifies an opportunity to route semantically suitable
work to lower-cost or specialist roles, but the effective model and tool
topology remain client/runtime concerns. A durable policy that assumes those
runtime values would overclaim portability and could weaken the existing
authority boundary.

## Decision or assumption

Implement adaptive intelligence routing as an additive, opt-in policy and
evidence layer. Routing may classify work by semantic role and risk tier, but it
must keep the primary agent as the sole checkout writer and integration owner.
Delegation is limited to one worker depth, uses the existing iteration, review,
and failure budgets, requires a minimum-sufficient dispatch envelope, and
escalates to the primary on ineligibility, review failure, unavailable runtime
evidence, or a human-owned boundary. Durable policy files do not pin model or
provider names. Routing is disabled by default until paired evaluation evidence
supports any future change.

## Rationale

This preserves the repository's strongest existing controls while making the
recommendation executable and inspectable. It separates requested/configured
intent from observed runtime behavior, works when a client cannot expose
effective routing metadata, and avoids introducing a daemon, scheduler, second
task engine, recursive swarm, or new authority surface.

## Alternatives considered

- Prompt-only routing was rejected because it has no structured eligibility or
  evidence boundary.
- A new orchestration daemon or recursive multi-agent runtime was rejected as
  disproportionate, non-portable, and contrary to the no-daemon/no-second-engine
  anti-goals.
- Durable model-name pinning was rejected because Codex resolves effective
  configuration through runtime and client layers that a portable repository
  cannot guarantee.
- Default-on routing was rejected until the direct-versus-routed evaluation has
  comparable acceptance, intervention, regression, latency, and available cost
  evidence.

## Impact

The contract, capability validator, task evidence schema, Build/reviewer
guidance, evaluation scripts, and public documentation gain additive routing
fields and checks. Existing routing-absent policies and receipts remain valid.
The implementation adds no Git, deployment, credential, publication, or
external-write authority. A later ADR is required for any change to default
behavior, topology, budget semantics, model/provider policy, or authority.
