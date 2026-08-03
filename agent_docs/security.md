# Security — [PROJECT_NAME]

> Keep current security facts and evidence here. Do not store credentials, tokens, private keys, sensitive payloads, or copied scan output.

**Owner:** [role or team]  
**Last reviewed:** [YYYY-MM-DD]  
**Next review trigger:** [release, architecture change, incident, or date]

## Scope and trust boundaries

| Boundary / flow | Untrusted input or actor | Sensitive asset / action | Control | Verification |
|---|---|---|---|---|
| | | | | |

## Identity, authorization, and tenancy

- **Authentication:** [provider, credential/session lifetime, recovery, machine identity]
- **Authorization:** [policy location, default-deny behavior, server-side enforcement]
- **Tenancy:** [isolation boundary and tests, or why tenancy is not applicable]
- **Privileged access:** [roles, approval, logging, break-glass ownership]

## Threat and abuse model

| Threat or abuse case | Entry point | Prevent / detect / limit | Evidence | Owner | Residual risk |
|---|---|---|---|---|---|
| | | | | | |

Cover applicable misuse of authentication, authorization, data access, uploads/parsers, automation, messaging, payments, scraping, resource exhaustion, and administrative actions.

## Data and privacy

| Data class | Purpose and source | Storage / region | Readers | Retention / deletion | Protection |
|---|---|---|---|---|---|
| | | | | | |

- **Minimization and consent:** [what is deliberately not collected and how consent/legal basis is handled]
- **Export, correction, deletion:** [workflow and verification]
- **Logging and analytics:** [redaction, access, retention, user controls]

## Secrets and external access

- **Secret source:** [managed store or injected environment; never literal values]
- **Rotation and revocation:** [owner, trigger, test]
- **Outbound allowlist / egress:** [destinations and enforcement]
- **Third-party credentials and scopes:** [least-privilege scope and ownership]
- **External tools and MCP:** [trusted server identity, reviewed transport, read-only or approval-gated tools, and owner]
- **Untrusted tool output:** [how documentation, issue, review, browser, log, and server content is prevented from overriding durable rules or authorizing writes]

## Supply chain and assurance

- **Static analysis / SAST:** [tool and setup, languages, triggers, query or rule policy, alert owner, or reason not applicable]
- **Dependency and image audit command:** [canonical command and failure policy]
- **Locking and updates:** [lockfiles, automated updates, review owner]
- **CI and artifact integrity:** [permissions, immutable actions, signing/provenance if required]
- **Security test evidence:** [authorization, isolation, input, scan, and regression tests]

## Open and accepted risks

| Risk | Severity | Mitigation / decision | Accountable owner | Review or expiry date | Evidence |
|---|---|---|---|---|---|
| | | | | | |
