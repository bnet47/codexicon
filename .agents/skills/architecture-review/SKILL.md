---
name: architecture-review
description: Evaluate expensive-to-reverse choices and optionally record an authorized ADR. Use for architecture, framework, database, or ownership decisions.
argument-hint: "[decision to make]"
---

# Architecture review

Announce: "I'm using architecture-review to evaluate this decision and record its consequences."

## 1. Load decision context

Read relevant accepted ADRs, `agent_docs/architecture.md`, project constraints, and the code that establishes the current system. If an ADR already settles the question, surface it and determine whether new evidence justifies superseding it.

## 2. Research only unstable facts

For current libraries, platform capabilities, pricing, limits, or deprecations, use a read-only researcher and primary sources. Do not browse merely to validate general engineering principles.

## 3. Define decision drivers

State the decision, constraints, non-negotiable qualities, and observable signals that would make the choice fail. Evaluate two or three viable options against the drivers most relevant here, normally including:

- product and constraint fit;
- operational complexity and failure isolation;
- security and data ownership;
- reversibility and migration cost;
- delivery and ongoing cost;
- testability, observability, and agent/developer navigability.

Avoid false precision. Use qualitative ratings unless reliable measurements exist.

## 4. Recommend and obtain direction

Lead with the recommended option, its decisive reason, and its largest downside. Ask the user only when the choice changes product behavior, cost, or irreversible commitments beyond the authority already granted.

## 5. Record the ADR only when authorized

If the user asked only for advice, a comparison, or a review, return the recommendation without modifying the repository. Create or update architecture documents only when the user asked to record the decision, asked for implementation that includes the decision, or explicitly delegated repository changes.

Copy `docs/adr-template.md` to the next available `agent_docs/decisions/ADR-NNN-[slug].md`.

- Use `Status: Proposed` when a required human decision is pending.
- Use `Status: Accepted` when the user chose the option or explicitly delegated the decision.
- Link any superseded ADR from the new record; do not rewrite the accepted historical decision.
- Update `agent_docs/architecture.md` when the accepted choice changes system shape.

Do not commit or push the ADR unless the user asks to ship.
