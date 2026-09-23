---
name: review
description: Review a diff against its request or spec and report actionable correctness, security, regression, scope, and test gaps. Does not edit.
---

# Review

Review evidence, not intent. Do not modify files.

During Explore or Build, do not invoke Git. Review the changed paths recorded in `TASKS.md` against `SPEC.md`, acceptance criteria, and verification output. Git status, diffs, staging, and branch comparisons are reserved for `$ship`.

## Selective independent review

Independent review is a configured Build decision, not a default panel or
runtime. The canonical `$autonomous-build` route delegates review when any
configured trigger matches; it must not narrow routing to risk alone. Before
deciding, validate and read the selected profile from
`.codex/capabilities.toml` with `python scripts/codexicon.py capabilities
--json`; do not invent thresholds or substitute values from another profile.
Delegate the read-only `reviewer` profile when any configured trigger matches:

- the assessed task or change risk is in `required_risk_levels`;
- the changed-file count is greater than or equal to `changed_files_threshold`;
- the change has a public API, security, architecture, or test-complexity
  signal and the corresponding `review_on_public_api`, `review_on_security`,
  `review_on_architecture`, or `review_on_test_complexity` flag is true.

The trigger is selective: trivial low-risk work is exempt when it is below the
configured file threshold and none of the enabled signals is present. The
primary agent remains the one sequential Build writer and still performs the
normal self-review and focused checks. This is not a background runtime or an
automatic publication mechanism.
An independent review is exactly one read-only reviewer pass and one correction
round;
the reviewer may inspect files and evidence but must not edit, run publication,
or expand Git, deployment, credential, external-write, or other Ship authority.

For a triggered review, completion evidence must carry a stable finding ID and
one disposition for every finding: `accepted`, `fixed`, `rejected`, or
`not_applicable`. Each finding gets exactly one of those dispositions. A
reviewer PASS has no actionable findings; it does not grant publication
authority or replace the task's required verification.

## Establish the comparison

During Build, inspect the changed paths recorded in `TASKS.md`. During Ship, inspect `git status`, staged and unstaged diffs, and—when available—the branch diff from its merge base. Read the request or linked contract/plan plus relevant conventions.

For a triggered diff, delegate the independent read-only pass to the
`reviewer` profile, then deduplicate and verify the findings yourself.

When the result came from an engineering loop, review the combined changed paths after integration. Do not treat a passing subagent report as final evidence; inspect the files and canonical checks.

For delegated implementation, first check the minimum-sufficient dispatch
envelope: task/spec trace, acceptance rubric, exact paths, dependencies,
verification, side-effect authority, escalation, and `max_depth = 1`. A worker
must not broaden paths or authority, spawn a child, self-accept, or claim that
requested/configured routing proves observed runtime behavior. The primary owns
any correction and integration.

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
