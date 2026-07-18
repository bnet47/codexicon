# Operations — [PROJECT_NAME]

> Record how the system is operated, observed, recovered, and changed. Link to live dashboards or runbooks; do not copy credentials or sensitive production data.

**Service owner:** [role or team]  
**Incident owner / escalation:** [documented private channel or rotation]  
**Last recovery exercise:** [YYYY-MM-DD or not yet run]

## Environments and ownership

| Environment / component | Runtime and region | Deploy trigger | Owner | Access boundary |
|---|---|---|---|---|
| | | | | |

## Service objectives and observability

| User-critical behavior | SLI / target | Dashboard or query | Alert threshold | Responder |
|---|---|---|---|---|
| | | | | |

- **Logs and traces:** [correlation, redaction, sampling, retention]
- **Health signals:** [startup, readiness, liveness, dependency health]
- **Synthetic or smoke checks:** [scope, frequency, owner]

## Dependency and failure behavior

| Dependency | Timeout | Retry / idempotency | Degraded behavior | Alert / owner |
|---|---|---|---|---|
| | | | | |

## Capacity, abuse, and cost controls

- **Measured capacity / load evidence:** [current result and workload shape]
- **Rate limits and quotas:** [per identity/tenant/resource]
- **Load shedding and backpressure:** [trigger and user-visible behavior]
- **Cost ceilings:** [budget/usage alerts and shutdown authority]

## Release, migration, and rollback

1. **Pre-deploy:** [compatibility, backup, migration, feature-control, approvals]
2. **Rollout:** [stages, smoke evidence, decision window]
3. **Rollback:** [command/runbook, data compatibility, owner, time target]
4. **Post-deploy:** [metrics, audit, cleanup, follow-up]

| Change type | Forward compatibility | Rollback / roll-forward | Tested evidence |
|---|---|---|---|
| Schema / data | | | |
| Application / API | | | |
| Configuration / infrastructure | | | |

## Backup and recovery

| Data / service | Backup method and retention | RPO | RTO | Restore test and date | Owner |
|---|---|---|---|---|---|
| | | | | | |

## Incident response

- **Detection and declaration:** [signals and decision owner]
- **Containment:** [safe-mode, disable, revoke, isolate, or rate-limit steps]
- **Communication:** [approved internal/customer/legal paths]
- **Evidence preservation:** [audit/log retention and privacy boundary]
- **Review:** [post-incident owner, deadline, action tracking]

## Known operational risks

| Risk / manual step | Impact | Current mitigation | Owner | Exit condition |
|---|---|---|---|---|
| | | | | |
