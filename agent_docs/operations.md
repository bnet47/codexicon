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

## Local behavior-verification paths

For each relevant product surface, record the project-owned launch path, safe
seed/reset procedure, observable behavior, and a reproducible check. Use only
synthetic or otherwise approved data. Mark missing launch, render, desktop, or
readback infrastructure as unmeasured; do not substitute source inspection for
an outcome that requires a live interaction.

| Surface | Project launch / entry point | Safe fixture / seed and reset | Observable state or artifact | Reproducible outcome check | Missing infrastructure / partial coverage |
|---|---|---|---|---|---|
| Web | [command, URL, readiness signal] | [synthetic input and reset] | [rendered DOM/accessibility state and persisted result] | [browser interaction and expected readback] | [browser, server, or storage observer gaps] |
| CLI | [command and required arguments] | [safe input fixture] | [exit status, stdout/stderr, output artifact] | [expected values and comparison command] | [missing runtime or unsupported platform] |
| Native desktop | [app launch path] | [safe local sample and reset] | [visible control, accessibility state, or saved artifact] | [fresh snapshot/action/fresh snapshot or artifact check] | [app, accessibility, or artifact observer gaps] |

Keep these checks separate from the canonical lint and test commands: a unit
test can prove a code path while the running UI or desktop outcome remains
unmeasured.

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
