# Build contracts

`SPEC.md` is the active repository contract created by `$discover`. It is intentionally kept at the root so a resumed task can find the same product boundary without transcript history.

Use stable IDs for requirements, interfaces, acceptance conditions, and anti-goals:

```markdown
# Specification: [Project or feature]

**Status:** ACTIVE
**Revision:** 1

## Outcome
[Observable result.]

## Requirements
- **R-001:** [Testable requirement.]

## Interfaces
- **I-001:** [API, file, event, CLI, or component contract.]

## Acceptance
- **A-001:** [Observable acceptance condition.]

## Anti-goals
- **AG-001:** [What will not be built, mocked, or supported.]

## Assumptions
- [Reversible assumption and rationale.]

## Amendments
- **2026-09-09:** Initial contract.
```

`read_contract()` validates only the actual root sections outside fenced Markdown
examples. It requires one exact `**Status:** ACTIVE` declaration, non-placeholder
definitions, unique IDs, and valid references to other contract IDs. `spec-check`
prints the amendment revision and a stable `sha256:` digest of that actual
contract. Fenced examples are excluded from the digest. A TASKS register may bind
itself with `**Contract revision:**` and `**Contract digest:**`; when present,
both must match or task parsing fails closed with contract drift.

Amendments are append-only: add a new dated entry in chronological order and keep
the prior entries intact. Do not edit an accepted requirement or silently replace
history. A contract with no amendments may use `- None.`; once an amendment is
added, replace that marker with the dated entry and retain all later history.

For work spanning multiple coherent changes, create `TASKS.md`. Legacy registers use
the six-column migration format:

```markdown
# Task Register

**Contract:** SPEC.md

| ID | State | Requirement | Interface | Scope | Verification |
|---|---|---|---|---|---|
| T-001 | TODO | R-001 | I-001 | `src/...`, `tests/...` | `pytest tests/...` |
```

The additive register format (format 2) appends dependency and state metadata
without changing the original six fields:

```markdown
**Register format:** 2
**Contract revision:** 1
**Contract digest:** sha256:<64 hex characters>

| ID | State | Requirement | Interface | Scope | Verification | Dependencies | Blocker | Evidence |
|---|---|---|---|---|---|---|---|---|
| T-001 | TODO | R-001 | I-001 | `src/...` | `pytest tests/...` | None | None | None |
```

`Dependencies` is a comma-separated list of task IDs or `None`. A `BLOCKED`
row must carry a persistent `Blocker` reason; `Evidence` is an additive record
for checks or interruption context and is not a substitute for the later
completion-evidence contract. Migrate a legacy register explicitly with
`python scripts/codexicon.py tasks-migrate`; migration preserves task meaning
and binds the current contract revision and digest.

Completion evidence is a JSON receipt stored in the `Evidence` cell. It must
contain `schema_version`, the matching `task_id`, one or more contract
`acceptance_ids`, `result: "passed"`, a timezone-bearing `timestamp`, the
current `source_digest` for the task scope, the current `contract_digest`, and
successful `checks`. At least one check must be a task-specific identity whose
argument-list command matches the row's declared `Verification` command; a
reviewed command string is accepted as recorded evidence but is never executed
by Codexicon. Optional `review_findings` entries contain an id and one of
`accepted`, `fixed`, `rejected`, or `not_applicable`.

Tier-aware completion evidence adds an auditable verification record without
changing those existing required fields. New receipts record
`verification_tier` (`focused`, `build`, or `ship`), `selected_profile`, and a
`freshness` object containing the configured `window_minutes`, the resulting
`expires_at`, and `responsible_owner`. The receipt's `source_digest`,
`contract_digest`, and each check's identity/argument-list command remain the
authoritative source, contract, and check identities. `window_minutes` must be
copied from the selected profile; the evidence owner records the expiry and is
responsible for rerunning the applicable tier after expiry or any invalidating
change. The current Build writer owns focused evidence, the primary Build
writer owns Build-completion evidence, and the explicitly authorized human
owns Ship evidence. Previously accepted receipts may omit this additive tier
metadata and remain subject to the existing digest and completion rules; the
metadata never bypasses a required field or a stale/failed check.

`tasks-done` refuses missing, failed, wrong-task, stale, uncovered, or malformed
receipts and stores the normalized receipt only after validation. Source or
contract digest changes invalidate the receipt. `tasks-next` reports
`COMPLETE` only when every task is `DONE`, every receipt is valid, all contract
acceptance IDs are covered, and the final configured `lint`, `test`, and
`security` checks each have successful evidence. Documentation-only task scopes
use the same structural digest and can therefore satisfy their own acceptance;
they do not authorize shell execution.

Validate and advance the register locally:

```text
python scripts/codexicon.py spec-check
python scripts/codexicon.py tasks-next
python scripts/codexicon.py tasks-start T-001
python scripts/codexicon.py tasks-done T-001
python scripts/codexicon.py tasks-blocked T-001 --reason "waiting for input"
```

`tasks-next` and the state commands validate the complete declared task table before
returning a queue result or changing state. Both the legacy six-column and additive
nine-column formats are strict; rows may use surrounding whitespace and either LF or CRLF line endings,
but each requirement is one `R-*` reference and each interface is one `I-*` reference
or the literal `None` when the task has no applicable interface. Multiple references
are rejected until a future register format defines their syntax. Pipes inside cells are unsupported: escaped pipes are rejected
explicitly, and unescaped pipes are diagnosed as extra columns. Malformed task-like
rows outside fenced Markdown examples are also rejected, with the source line
number, so unfinished work cannot be mistaken for an empty successful queue.

Every Build edit must state a trace such as `T-001 -> R-001 -> I-001`. Tasks without a trace are blocked rather than expanded by assumption. Build stays in the current checkout and active branch; Git operations are reserved for `$ship`.

## Build and Ship authority

Build is filesystem-local and must not depend on a Git executable or checkout metadata. The manager and hooks identify the local contract, task register, and declared paths with deterministic SHA-256 evidence; checkpoint callers supply changed paths explicitly. The default `doctor`, `resume`, checkpoint, task-evidence, and `verify --mode build` journeys therefore work in a non-Git directory or when Git is unavailable. A read-only Git probe is not an allowed replacement for this strict rule.

Ship is the separate authority boundary for branches, worktrees, index, commits,
pushes, pull requests, releases, deployments, publication, external writes,
tracked-file, and history checks. Its required checks follow the explicitly
requested ceiling: commit-only Ship requires commit verification and the
tracked/history gate but does not require publication evidence; publication,
merge, or deployment checks apply only when that authority was explicitly
requested. Never infer or pressure a broader action. Use `verify --mode ship`
or `python scripts/security_scan.py --mode ship` only from the explicitly
authorized `$ship` workflow. Ship mode fails closed when Git repository or
enumeration evidence is unavailable. Git commands in tests are permitted only
for isolated temporary fixtures and are not user-checkout operations.

## Verification tiers and Stop outcomes

Verification is tiered. A passing lower tier is useful evidence for the next
iteration, but it never substitutes for a higher tier or for the existing task
completion-evidence contract.

| Tier | Owner | Required evidence | Freshness and safe inspection | Stop outcome |
|---|---|---|---|---|
| Focused iteration | The current Build writer | The narrowest check that exercises the changed behavior and the task's acceptance rubric. | Run after the current implementation pass. Evidence must match the current task and relevant source/contract identity. Safe, read-only inspection preserves it; writes, unsafe composition, unknown commands, and protected-path access do not. | Continue while acceptance or evidence is missing, or while a meaningful in-scope improvement remains. |
| Build completion | The primary Build writer | Fresh task-specific acceptance evidence plus the selected profile's Build checks (normally lint and test). Queue completion still requires the existing configured lint, test, and security evidence and valid task receipts. | Evidence must be newer than the latest relevant write and within the selected profile's Build freshness window. Structural/documentation checks remain relevant to documentation-only work. Safe inspection does not refresh or weaken evidence. | Stop only with acceptance covered and fresh relevant evidence, or with an explicit non-success outcome below. Build does not enter Ship automatically. |
| Ship | The explicitly authorized human/$ship workflow | Commit-only: full platform-native lint, test, filesystem security, and tracked/history checks. Publish/merge/deploy: the same checks plus release identity and publication evidence, only when explicitly requested. | Ship evidence is fresh for the selected profile's Ship window. Tracked-file and history enumeration must succeed; unavailable Git evidence fails closed. Publication evidence is required only for an authorized publication, merge, or deployment action. Build receipts inform review but never satisfy this tier by themselves. | Commit-only may stop after authorized commit verification. Publish/merge/deploy stops only after its explicitly authorized release/publication boundary is verified, or reports the exact failure/blocker. |

The selected profile supplies the freshness windows; it is not a runtime. A
receipt is fresh only when its timestamp is within that window and its task,
source, contract, and required check identity still match. A safe inspection is
an explicitly read-only operation such as `spec-check`, `tasks-next`, `inspect`,
`doctor`, `resume`, or bounded file reading/search. It must not open protected
credential paths, execute substitutions, use write options, or hide a mutation.
Such an inspection preserves valid evidence. A source/configuration/task write,
mutating manager command, unsafe or unknown shell composition, malformed state,
or protected-path violation invalidates the affected evidence and requires the
appropriate checks again.

Stop precedence is deterministic and does not override an open issue:

1. The completion gate is acceptance coverage plus fresh relevant evidence and
   no open in-scope correctness, safety, or evidence issue. Until that gate is
   met, resolve the missing evidence or issue, or report a non-success outcome;
   no open issue can be ignored.
2. Before the completion gate, bounded improvement may continue only when the
   proposed pass is meaningful, reversible, in scope, and supported by the
   remaining budget. `PLATEAU`, `REPEATED_FAILURE`, `BUDGET_EXHAUSTED`, and
   `HUMAN_BOUNDARY` describe why work cannot safely reach the gate; they do not
   turn an unresolved issue into `ACCEPTED`.
3. Once the gate is met, stop as `ACCEPTED` before optional refinement. Do not
   perform optional polish or start Ship automatically. Required configured
   review and final verification are gate checks, not optional refinement; an
   actionable finding reopens the gate and requires correction or a non-success
   outcome.

No Stop outcome creates a daemon, scheduler, second task engine, or Ship
authority.

## Project-local capability policy

`.codex/capabilities.toml` is a validated, descriptive policy for reversible
workflow guidance. It is not an execution engine, daemon, scheduler, or second
task register. The selected profile is one of `strict`, `balanced`, or
`autonomous`; each profile declares positive bounded iteration/review/failure
budgets, a time budget, review risk/file thresholds, focused/Build/Ship
verification tiers, and mandatory human-owned escalation flags. The top-level
`authority` table is deny-by-default: Git, deployment, credentials, external
writes, publication, and runtime authority must all remain `false`.

Validate and inspect the policy locally:

```text
python scripts/codexicon.py capabilities
python scripts/codexicon.py capabilities --json
```

The validator rejects missing, malformed, unknown, unsafe, contradictory, or
unbounded values with a line-aware diagnostic. It parses data only; it never
executes strings or commands from the policy. Human/JSON output is stable and
reports the selected profile plus its budgets, review thresholds, verification
tiers, and escalation boundary. A clean scaffold carries the same policy via
the reviewed starter allowlist and manifest.

## Optional long-running and resume contract

Native Goal mode may be used when a supported client offers it and the user
explicitly requests sustained execution. It is optional and client-dependent;
Codexicon does not require it and does not provide a daemon, scheduler, or
third-party memory service. The portable contract remains the root `SPEC.md`
and `TASKS.md`, which are authoritative across clients and sessions.

The session contract distinguishes four cases:

- **Active-turn chaining** continues runnable local work only while the current
  turn is alive; it is not background execution.
- **Compaction recovery** rereads the current contract and register, using a
  compatible checkpoint only as supplemental context. Newer authoritative
  files and evidence take precedence.
- **Restart after termination** starts a fresh session and deterministically
  runs `tasks-next --json` (plus `resume` when applicable); a transcript is not
  durable progress.
- **Cancellation** is respected. A cancelled or stopped run is not silently
  relaunched; a later continuation requires explicit user intent.

Without Goal mode, plain-session resume follows the same deterministic path:
read `SPEC.md` and `TASKS.md`, validate them, resume the sole `ACTIVE` task
first, and then select the next runnable task. Goal mode changes client
continuation only; it does not expand Build's filesystem-local authority or
authorize Git, deployment, publication, or external writes. Those remain
explicit `$ship` boundaries.

The local harness/fixture results are observed evidence. Native Goal-mode
availability, hook trust, and live client delivery are unmeasured unless a
client/platform smoke test records them; raw tool names are not compatibility
evidence.

Queue selection is explicit and resumable. `tasks-next` selects the sole `ACTIVE`
task first (`RESUME_ACTIVE`), then the first runnable `TODO` whose dependencies
are `DONE` (`READY`). It reports `BLOCKED` when remaining work cannot run and
`COMPLETE` when every task is `DONE`; unknown dependencies, cycles, malformed
rows, contract drift, and multiple active owners are `INVALID`. Human output is
available by default; add `--json` for a stable object containing `outcome`,
`task`, `blockers`, and `reason`.

The CLI exits `0` for `READY`, `RESUME_ACTIVE`, and `COMPLETE`, `3` for
`BLOCKED`, and `2` for `INVALID` or other manager errors. Legal transitions are
`TODO -> ACTIVE|BLOCKED`, `ACTIVE -> DONE|BLOCKED`, and controlled
`BLOCKED -> TODO` / `DONE -> TODO` through `tasks-unblock` or `tasks-reopen`
with a reason. Only one `ACTIVE` implementation owner is permitted. State
updates take a transient register lock and compare the original bytes again
before the atomic replacement; a concurrent edit is refused without overwriting
the other writer's register.

```text
python scripts/codexicon.py tasks-next --json
python scripts/codexicon.py tasks-start T-001
python scripts/codexicon.py tasks-blocked T-001 --reason "waiting for input"
python scripts/codexicon.py tasks-unblock T-001 --reason "input received"
python scripts/codexicon.py tasks-reopen T-001 --reason "regression found"
```

## One contract and one Build vocabulary

All implementation entry points converge on the root `SPEC.md` and `TASKS.md`:

- `$discover`, `$spec`, and `$brainstorm` create or amend the root `SPEC.md` in place. Historical briefs and plans may supplement context, but they never replace the active contract.
- `$write-plan` creates or amends a validated `TASKS.md` register from `SPEC.md`. The plan is descriptive; the register is authoritative.
- `$execute-plan` validates the selected plan, contract, and register, then adapts into the same `$autonomous-build` loop. It does not define a second execution engine.
- `$autonomous-build` creates the smallest traced `TASKS.md` register automatically when an authorized implementation has no register, without a routine approval stop.
- `$quick` requires an existing `T-* -> R-* -> I-*` trace when a task register covers the change. If no register is needed, it may use an existing `R-* -> I-*` trace or a minimal authorized append-only `SPEC.md` amendment, but it does not invent task IDs. New queued or multi-step work routes through `$write-plan` and `$autonomous-build`.
- Pure explanations and read-only reviews are explicitly exempt from code-generation ceremonies and do not create or amend `SPEC.md` or `TASKS.md`.

The persisted task states are `TODO`, `ACTIVE`, `BLOCKED`, and `DONE`. Queue outcomes are
`READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID`; completion/report
statuses are separate result labels (`DONE`, `DONE_WITH_CONCERNS`, `BLOCKED`, and
`NEEDS_CONTEXT`) and must not be used as persisted task states. A Build has one writer
in the shared checkout: the primary agent by default. An explicitly chosen
`implementer` may write one bounded task sequentially; the primary agent re-reads the
changed paths and owns integration and final verification. Research and review lanes
remain read-only, and runnable work continues without a suggested-next-prompt stop.
