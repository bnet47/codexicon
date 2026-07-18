# Architecture — [PROJECT_NAME]

> Keep this as the current map of the system, normally no more than two pages. Record why choices were made in ADRs, not here.

**Last updated:** [YYYY-MM-DD]

## System context

```text
[Users and external systems]
              |
              v
        [System boundary]
```

## Components

| Component | Responsibility | Entry point | Depends on | Exposes |
|---|---|---|---|---|
| | | | | |

## Critical flows

### [Flow name]

1. [Trigger and input.]
2. [Important processing or boundary.]
3. [Output and observable result.]

**Failure behavior:** [How errors are contained, retried, surfaced, or recovered.]

## Data ownership

| Data | Owner / source of truth | Readers | Retention / consistency |
|---|---|---|---|
| | | | |

## External dependencies

| Service | Purpose | Authentication | Timeout / failure behavior |
|---|---|---|---|
| | | | |

## Runtime and deployment

| Environment | Runtime / location | Trigger | Observability |
|---|---|---|---|
| Local | | `./scripts/dev.sh` | |
| Staging | | | |
| Production | | | |

## Constraints and known risks

- [Constraint or accepted tradeoff with a link to an ADR when applicable.]

Schemas belong in `agent_docs/data-model.md`; rationale belongs in `agent_docs/decisions/`; implementation conventions belong in `agent_docs/conventions.md`.
