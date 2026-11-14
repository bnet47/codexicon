# Repository accuracy and security audit

**Status:** Complete
**Scope:** T-045 through T-047

## Outcome

The GitHub summary and public playbook describe the default-branch behavior and
make current evaluation evidence easy to find. The canonical verification
commands work as documented, and local security checks do not execute
model-edited code or silently miss supported credential-bearing text. Hook
recovery cannot erase dirty verification state after malformed state is observed.

The full repository audit confirmed and fixed one low-severity Stop-gate bypass.
Four source-grounded leads remain needs-validation because Codex runtime,
process-containment, or shared-checkout ACL facts are outside repository source;
they are not reported as confirmed vulnerabilities. An independent final
coverage review found the corrected 14-unit ledger complete, including the
explicit local Git hook installer boundary. The audit report is stored outside
the repository under the security-audit run artifacts to keep retained audit
evidence separate from target-controlled files.

## T-045 — Close source-verified security findings

- Review and fix bounded findings in the repository secret scanner, skill
  provenance digest, and legacy live evaluator.
- Keep verification local and use synthetic fixtures only. Never invoke a live
  model/provider or access credential-bearing files.
- Acceptance: `A-010`.
- Verification: focused security scanner, skill provenance, and live evaluator
  unit tests; full canonical test and security checks at completion.

## T-046 — Reconcile commands and published guidance

- Make the no-argument `verify` command run all canonical checks and reject
  unsupported names through the existing validation path.
- Make the secret scanner distinguish BOM-less UTF-16 text from binary control
  data and fail closed on oversized text files.
- Link recovery, method-selection, and skill-comparison evidence from the
  README, docs index, and visual playbook. Keep unmeasured outcomes and inactive
  candidates explicit.
- Re-render the generated playbook from its source.
- Close final-review findings in the live evaluator: avoid following fixture
  symlinks, cap captured process output, and terminate evaluator process trees
  on timeout and completion.
- At Ship, set the GitHub summary to wording supported on the default branch
  and push only the current authorized feature branch.
- Acceptance: `A-042`.
- Verification: command, template, scanner, and evaluator unit tests, playbook
  render check, full canonical lint/test/security suite, and tracked/history
  security scan.

## T-047 — Preserve the Stop gate during untrusted-state recovery

- Treat malformed, missing, and incomplete schema-4 hook state as untrusted and
  recover it into a conservative dirty state that requires fresh lint and tests,
  including when recovery occurs during a PostToolUse check event.
- Add regressions covering corruption after a write and before a check receipt
  is consumed; keep the Stop hook blocked until fresh checks are recorded.
- Clarify the lifecycle recovery guarantee in `docs/codex.md`.
- Acceptance: `A-005`.
- Verification: focused malformed-state lifecycle regression and full canonical
  lint/test/security verification.

## Existing queue condition

Before these tasks were added, `tasks-next --json` returned `BLOCKED` because
prior DONE receipts had stale source digests. The final-review fixes touch files
also named in T-045, so that historical receipt is now stale as well; T-046
revalidates those fixes. Preserve receipts and report the queue condition
separately; do not rewrite historical evidence.
