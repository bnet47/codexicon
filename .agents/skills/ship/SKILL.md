---
name: ship
description: Verify changes and perform only explicitly requested Git steps: commit, push, or draft PR. Never infer publication authority.
---

# Ship

Determine the authorization ceiling from the request before acting:

- **Commit only:** verify and create the commit, then stop.
- **Push:** verify, commit when needed, and push the current non-protected branch; do not open a PR.
- **Open a PR / ship:** verify, commit, push, and open a draft PR.

None of these requests authorizes deployment or unrelated cleanup.

## Verification tiers and ownership

Focused checks belong to the current Build writer, and Build completion belongs
to the primary Build writer. Those receipts may be reviewed during Ship, but
they do not satisfy Ship. Ship is human-owned and begins only after explicit
authorization; it is the only tier that may perform user-checkout Git,
tracked/history, release, publication, deployment, or external-write work.

Ship evidence must be fresh within the selected profile's Ship window and must
follow the latest relevant write. Safe read-only inspection preserves valid
evidence, but protected credential paths are never opened. A mutation, unsafe
or unknown command, malformed state, or failed tracked/history enumeration
invalidates the affected evidence and requires the relevant check again.

## Acceptance by authorization ceiling

The requested Ship ceiling determines the completion gate:

- **Commit-only:** require the full lint, test, filesystem-security, and
  tracked/history checks plus the change-set audit and review. A commit-only
  request is accepted after the authorized commit; it does not require release
  identity, publication evidence, a remote push, merge, or deployment, and the
  workflow must not pressure the user to perform any of them.
- **Publish, merge, or deploy:** require explicit authority for that action in
  addition to the full lint/test/security and tracked/history checks. Release
  identity and publication evidence are required before the authorized action;
  merge or deployment must not be inferred from a commit or push request.

Tier-aware Ship evidence records `verification_tier: "ship"`, the selected
profile, source/contract/check identities, and the configured freshness window,
`expires_at`, and responsible owner. The human Ship owner reruns the affected
checks after expiry or invalidation; these fields document responsibility and do
not create a runtime.

## 1. Verify

For commit-only, run the narrowest feature checks plus:

```bash
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
python scripts/security_scan.py --mode ship
```

For publish, merge, or deploy, also run:

```bash
python scripts/release.py check --tag vX.Y.Z
```

Then verify the intended publication artifact and destination against the
passed release identity before the authorized action. The release check
validates the canonical version, optional exact tag, public references, and
reproducible starter artifact; `security_scan.py --mode ship` is the
tracked-file/history gate and fails closed when Git enumeration is unavailable.
Run the canonical scripts directly so lint/test one-use hook receipts reflect
the real result; do not mark verification manually. If a check fails, diagnose
and fix only in-scope problems, rerun it, and stop with the exact blocker if
safe completion needs a product decision or unrelated change.

Ship Stop is outcome-based: commit-only `ACCEPTED` requires its listed local,
tracked/history, audit, and review checks but not release/publication evidence;
publish/merge/deploy `ACCEPTED` additionally requires release/publication
evidence and the explicit action authority. `PLATEAU` or `REPEATED_FAILURE`
reports why another pass cannot safely improve the requested ceiling, and
`HUMAN_BOUNDARY` stops before any unauthorized action. Never treat a focused or
Build pass as Ship completion.

For a first production launch or material production change, run `$production-readiness` before publication. A NOT READY verdict blocks shipping; only the accountable human can accept a named residual risk.

## 2. Audit the change set

Inspect unstaged, staged, and untracked files. Confirm the diff matches the request, the security gate passed, and there is no accidental generated output or unresolved conflict marker.

Determine the current branch and protected-branch policy. Do not create a branch automatically. If publication requires a different branch, stop and report the exact branch decision unless the user explicitly authorized branch creation. Never force-push.

## 3. Review

Run the `$review` workflow or perform the same acceptance-focused review. Resolve actionable findings and rerun affected verification before committing.

## 4. Commit intentionally

Stage only files that belong to this request. Use the `$conventional-commit` format:

```text
type(scope): imperative summary
```

Keep the subject concise and add a body when motivation or compatibility impact is not obvious. Confirm the resulting commit contains only the intended files.

## 5. Publish only to the authorized ceiling

If push was requested, push the current branch without force. If a PR or shipping was requested, open a draft pull request with:

- what changed;
- why;
- exact verification results;
- risks, migrations, or follow-up required;
- a concise review checklist.

If the user requested only a commit, skip this step. If a required remote, authentication, or PR tool is unavailable, stop at the last authorized successful step and report the exact blocker. Do not invent a URL or mark the PR ready for review unless the user asked.

## 6. Report

Return the commit SHA, branch, PR URL when created, verification evidence, and any residual concern. Shipping code does not authorize deployment.
