# Adaptive-autonomy final verification

**Date:** 2026-11-14
**Contract:** SPEC revision `2026-11-14`, digest `sha256:224a34b829856bed04cc88c62d0d2fde88035789cb674350a3958dcc2d508bff`
**Scope:** Adaptive-autonomy plan T-036 through T-044

## Build evidence

| Check | Result |
|---|---|
| `python scripts/codexicon.py verify --mode build` | Passed on native Windows before the Ship review correction; lint and security passed, with 225 tests passed and 9 skipped. |
| `python scripts/render_playbook.py --check` | Passed; editable source matches standalone output. |
| `python scripts/codexicon.py spec-check` | Passed: 41 requirements, 34 interfaces, 42 acceptance conditions, 8 anti-goals. |
| `python scripts/validate_template.py` | Passed. |

The task-specific checks for T-036 through T-044 were rerun against the final
contract and source. Canonical lint/test/security evidence is included in the
T-044 receipt. First-pass receipts are preserved in
[`2026-11-14-adaptive-autonomy-receipt-history.md`](2026-11-14-adaptive-autonomy-receipt-history.md).

## Queue outcome

`python scripts/codexicon.py tasks-next --json` returns `BLOCKED` at repository
completion. All new plan tasks T-036 through T-044 have fresh passing receipts,
but T-001 through T-035 retain historical receipts that are stale after earlier
source and contract changes. Acceptance evidence A-001 through A-033 is missing
from the current evidence ledger. Those historical rows and requirements were
left intact; this plan did not reopen or rewrite them.

This is a repository-wide completion blocker, not a failure of the new plan's
focused checks or Build verification. The recovery and skill pilots remain
inconclusive where client signals were unavailable; the rollout decision keeps
the candidates inactive.

## Ship review correction

The independent Ship review found that a discovered Codex executable which
could not launch was counted as an interrupted attempt. `invoke_codex` now
records whether the child process started; launch failures are unavailable,
remain in the planned denominator, and are excluded from attempted counts and
product verification. The regression check uses a launch-time
`FileNotFoundError`. Focused coverage passed: 51 tests across the affected
evaluation suites. The independent reviewer rechecked the correction and
reported no remaining actionable findings.

## Final Ship verification

After the launch-accounting correction, native Windows `./scripts/lint.ps1`,
`./scripts/test.ps1`, `./scripts/security.ps1`, and
`python scripts/security_scan.py --mode ship` passed. The final test run passed
226 tests with 9 skipped. `validate_template.py`, `render_playbook.py --check`,
and `spec-check` also passed.
