# Data model — [PROJECT_NAME]

> Describe business meaning and ownership before storage syntax. Keep this synchronized with schemas and migrations when the project has persistent data.

**Last updated:** [YYYY-MM-DD]

## Domain entities

### [Entity]

**Meaning:** [What this represents in the domain.]  
**Owner:** [Component or external source of truth.]  
**Identity:** [Stable identifier and uniqueness rule.]  
**Lifecycle:** [Creation, important transitions, archival/deletion.]

| Field | Type / format | Required | Business rule |
|---|---|---:|---|
| | | | |

## Relationships

```text
[Entity A] 1 ---- N [Entity B]
```

Record cardinality, ownership, cascade behavior, and any cross-boundary reference.

## Invariants

- [Rule that must remain true across writes.]

## Access patterns

| Operation | Caller | Consistency / latency need | Index or cache implication |
|---|---|---|---|
| | | | |

## Retention, privacy, and deletion

- [Classification, retention period, deletion/export behavior, audit need.]

## Migrations

Document the real migration location and command after stack initialization.

- Prefer backward-compatible expand/migrate/contract changes for live systems.
- Include rollback or roll-forward behavior and data validation.
- Never claim a migration is reversible when it destroys or transforms data irreversibly.
