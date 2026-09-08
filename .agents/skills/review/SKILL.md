---
name: review
description: Review a diff against its request or spec and report actionable correctness, security, regression, scope, and test gaps. Does not edit.
---

# Review

Review evidence, not intent. Do not modify files.

During Explore or Build, do not invoke Git. Review the changed paths recorded in `TASKS.md` against `SPEC.md`, acceptance criteria, and verification output. Git status, diffs, staging, and branch comparisons are reserved for `$ship`.

## Establish the comparison

During Build, inspect the changed paths recorded in `TASKS.md`. During Ship, inspect `git status`, staged and unstaged diffs, and—when available—the branch diff from its merge base. Read the request or linked contract/plan plus relevant conventions.

For a broad or high-risk diff, delegate independent read-only passes to the `reviewer` profile (for example correctness, security, and test coverage), then deduplicate and verify the findings yourself.

When the result came from an engineering loop, review the combined changed paths after integration. Do not treat a passing subagent report as final evidence; inspect the files and canonical checks.

## Findings threshold

Report only issues that can cause:

- unmet acceptance criteria;
- incorrect behavior or a regression;
- security, privacy, authorization, or data-integrity exposure;
- unsafe migration or compatibility behavior;
- meaningful missing verification;
- accidental scope drift that raises risk.

Do not report style preferences, speculative future improvements, or items already enforced by a passing formatter unless they affect behavior.

## Output

Order findings by severity:

```markdown
## Findings

### [P1] [Short title]
`path/to/file:line` — [Concrete impact, triggering condition, and violated requirement.]

## Verification gaps
- [Missing or untrustworthy evidence.]

## Verdict
READY | NEEDS WORK — [one sentence]
```

Severity: P0 blocks all use; P1 high-impact and likely; P2 material but limited; P3 low-impact and concrete. Use the tightest line reference possible. If no actionable issue exists, return `READY — no actionable gaps found.`
