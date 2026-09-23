# Capability policy and bounded self-improvement

Codexicon's capability policy is the project-local `.codex/capabilities.toml`.
It is validated guidance for the existing Build loop, not an execution engine.
The policy defines `strict`, `balanced`, and `autonomous` profiles with
positive bounded budgets, review thresholds, verification tiers, and mandatory
human-owned escalation flags. Inspect it with:

```text
python scripts/codexicon.py capabilities
python scripts/codexicon.py capabilities --json
```

The selected profile is the source of truth for `max_iterations`,
`max_review_cycles`, `max_failed_attempts`, and `max_minutes`. Skills and the
bounded implementer consume those values as limits; they do not add a hidden
counter. Budget accounting is precise.
`one iteration` means one implement + focused-check + critique pass.
`one review cycle` means one independent reviewer pass and one correction round.
`one failed attempt` means one failed implementation/focused-check pass requiring recovery.
`max_minutes` starts at task activation and includes implementation, checks, review, and correction.
These counters are local guidance, not a runtime. There is no background
runtime or second task engine. The policy remains deny-by-default for authority.

## Opt-in semantic routing

The optional `[routing]` block is disabled by default and is advisory rather
than a runtime. It may classify an eligible task by semantic role and risk tier,
but delegation requires a minimum-sufficient envelope with exact paths,
dependencies, verification, review signals, escalation, and `max_depth = 1`.
Ineligible or trivial work stays with the primary. Workers cannot broaden
authority, spawn another worker, integrate, or publish. Routing evidence must
distinguish requested/configured values from observed runtime values; use
`configured_unverified`, `unavailable`, or `mismatched` when observation is not
reliable. Defaults remain unchanged until paired direct-versus-routed evidence
supports a decision.

## Selective independent review

The selected profile's `[profiles.<name>.review]` table is the only source for
independent-review thresholds. The canonical `$autonomous-build` route
delegates review when any configured trigger matches; it must not narrow the
route to risk alone. Validate the table before use with
`python scripts/codexicon.py capabilities --json`. A read-only `reviewer` pass
is required when any of these configured conditions matches:

- the assessed risk is listed in `required_risk_levels`;
- the changed-file count is at least `changed_files_threshold`;
- a public API, security, architecture, or test-complexity signal is present
  and its matching `review_on_public_api`, `review_on_security`,
  `review_on_architecture`, or `review_on_test_complexity` flag is enabled.

Trivial low-risk work is exempt when it is below the configured file threshold
and has no enabled signal. This is a selective instruction-level decision, not
a reviewer panel, background runtime, or automatic publication mechanism. The
primary agent remains the one sequential Build writer; the reviewer only
inspects the declared paths and evidence. Build stays filesystem-local and
Git-free, while Git, deployment, credentials, external writes, and publication
remain explicit `$ship`/human boundaries.

One review cycle is exactly one independent reviewer pass and one correction
round. When review runs, completion evidence must include a stable finding ID
and exactly one disposition for every finding. The allowed dispositions are
`accepted`, `fixed`, `rejected`, and `not_applicable`; a clean PASS has no
actionable findings and does not waive the task's fresh verification.

## Build refinement contract

For each task, the agent first writes an internal, task-specific acceptance rubric
from the task's acceptance IDs and `SPEC.md`. The rubric names:

- required behavior and observable acceptance signals;
- safety, regression, and security invariants;
- focused and final verification that will produce fresh evidence; and
- the declared file and behavior boundary.

The canonical Build loop has an early stop: if acceptance is met and fresh
relevant verification is present, stop before any optional refinement. Required
configured review and final verification still apply. Otherwise, critique the
weakest important aspect of the result. It may refine only when the proposed
change is meaningful, reversible, directly related to the rubric, and inside
the task's scope. Each refinement reruns the affected focused checks and must
preserve the task trace, current task state, and evidence requirements.

Plateau detection is evidence-based: refinement stops when another pass makes
no material improvement to acceptance coverage, correctness, regression or
safety risk, maintainability, or evidence quality. Refinement also stops when
the selected profile's iteration, review-cycle, failed-attempt, or time budget
is exhausted; when the same failure repeats without a safe alternative; or
when a human-owned boundary is reached. Acceptance plus fresh relevant
verification is sufficient; speculative polish is not required.

Human escalation includes destructive or production actions, destructive data work,
credentials,
Git, branches, worktrees, staging, commits, pushes, pull requests, releases,
deployments, publication, migrations, external writes, authority expansion,
and material product or architecture decisions. Build stays filesystem-local
and Git-free. These remain explicit `$ship`/human boundaries. `SPEC.md` and
`TASKS.md` remain authoritative, and this contract does not create a background
process or replace the task register.

## Decision journal and related scope

Consequential assumptions and decisions belong in the append-only journal at
`agent_docs/decisions/`. Add a new `ADR-NNN-short-title.md` record; never
rewrite or delete an accepted record. Each record includes the decision or
assumption, rationale, alternatives considered, impact, owner, date, status,
and inspectable evidence. A later record supersedes an earlier one when a
decision changes. This is durable guidance, not a runtime or a second source
of authority.

The current task may absorb a small related correction only when it is all of
the following: reversible, directly related to the selected task, and within
the declared system boundary. Keep the task trace, file scope, and verification
receipt accurate; record any consequential assumption or decision before
continuing. Correctness, safety, test, maintainability, and documentation fixes
can qualify when they meet that gate, but convenience or polish alone does not.

Stop and explicitly escalate before any related change that expands authority,
changes product behavior, changes a schema or data shape, changes the security
posture, or creates an irreversible or destructive outcome. Also escalate
credentials, production actions, migrations, external writes, publication,
deployment, legal/compliance commitments, and material architecture choices.
The journal records the escalation and rationale; it does not authorize the
action. `$ship` or the responsible human retains that authority.

## Verification tiers

Focused checks support iteration. Build completion requires fresh relevant
lint/test evidence and task-specific acceptance coverage. Commit-only Ship
requires full lint/test/filesystem-security plus tracked/history and
audit/review checks, without release/publication evidence. Publish, merge, or
deploy adds release/publication evidence only when that exact authority is
explicitly requested. A passing check does not override a missing rubric item,
stale evidence, a repeated failure, a plateau, or a human boundary.
