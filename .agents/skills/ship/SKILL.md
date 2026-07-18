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

## 1. Verify

Run the narrowest feature checks plus:

```bash
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
```

If a check fails, diagnose and fix only in-scope problems, rerun it, and stop if safe completion needs a product decision or unrelated change. Run the canonical scripts directly so lint/test one-use hook receipts reflect the real result; do not mark verification manually.

For a first production launch or material production change, run `$production-readiness` before publication. A NOT READY verdict blocks shipping; only the accountable human can accept a named residual risk.

## 2. Audit the change set

Inspect unstaged, staged, and untracked files. Confirm the diff matches the request, the security gate passed, and there is no accidental generated output or unresolved conflict marker.

Determine the intended base branch and confirm the current branch is not `main` or another protected branch. Create a scoped branch when needed; never force-push.

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
