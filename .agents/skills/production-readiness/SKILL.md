---
name: production-readiness
description: Audit a project or release for security, data, recovery, observability, capacity, and release safety. Use before launch or a major production change.
---

# Production readiness

Announce: "I'm using production-readiness to test whether this project can fail safely in production."

## 1. Set the boundary

Identify the release, environments, users, sensitive data, external systems, irreversible actions, and explicit launch criteria. Treat the workflow as read-only unless the user also asks for fixes. Never deploy, rotate credentials, change production, or accept risk on the user's behalf.

Read `AGENTS.md`, the approved charter/spec, relevant architecture and data model, deployment/CI configuration, manifests and lockfiles, then `agent_docs/security.md` and `agent_docs/operations.md` when present. Unknown evidence is a gap, not a pass. Never open credential-bearing files.

## 2. Build the evidence matrix

Assess only applicable surfaces and cite the file, command, test, dashboard, runbook, or owner that proves each conclusion:

- **Security:** trust boundaries, authentication, authorization, tenancy isolation, input validation, secret handling, outbound access, auditability, threat and abuse cases.
- **Data and privacy:** classification, minimization, retention/deletion, encryption, migrations, compatibility, backups, restore evidence, rollback, and regulatory obligations.
- **Supply chain:** locked dependencies, vulnerability audit, CI permissions, immutable actions, artifact integrity, update ownership, and third-party failure exposure.
- **Reliability:** health behavior, timeouts, retries, idempotency, degradation, observability, SLOs, alert ownership, incident response, and dependency failure modes.
- **Scale and cost:** capacity evidence, concurrency, rate limits, quotas, load shedding, abuse controls, and cost ceilings.
- **Release safety:** staging parity, migration order, rollout and rollback, feature controls, smoke tests, ownership, and decision points.

Do not demand controls that do not fit the system. Explain why an item is not applicable.

## 3. Verify

Run the project-specific checks plus the canonical gates when available:

```bash
./scripts/security.sh
./scripts/lint.sh
./scripts/test.sh
```

Use the supported native wrappers on Windows. Run ecosystem-native dependency or container audits when the project provides them. Do not install tools, mutate lockfiles, contact production, or perform load tests against shared systems without authority. Prefer restore, migration, rollback, authorization, and failure-path tests over policy claims.

## 4. Decide

Return one verdict:

- **READY** — launch criteria have current evidence and no release-blocking gaps.
- **READY WITH ACCEPTED RISK** — only when the accountable human has explicitly accepted named, bounded risks with an owner and review date.
- **NOT READY** — any unresolved critical/high risk, missing rollback or recovery proof, unknown authorization boundary, exposed credential, or unowned launch-critical failure.

Report findings as P0–P3 with impact, evidence, required action, owner, and verification. Separate blockers, accepted risks, and later improvements. If fixes were requested, update the relevant project docs and controls, rerun affected evidence, then reassess; otherwise stop after the audit.
