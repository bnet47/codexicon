# Agent-loop benchmark

This benchmark compares direct single-agent work with the bounded `$engineering-loop`. It is a measurement protocol, not a claim that live Codex telemetry is available in every client.

The fast deterministic suite is separate from live-agent and browser trials. It
is an executable regression/policy oracle, not an agent ranking or client
compatibility result.

## Live Codex paired smoke

The live comparison is intentionally narrower than this protocol's broader
direct-versus-loop journeys. `python scripts/live_agent_eval.py --smoke`
creates two fresh temporary calculator fixtures and runs exactly one direct and
one Codexicon-guided local invocation with:

```text
codex exec --ephemeral --sandbox workspace-write --skip-git-repo-check -C <temp> --json <prompt>
```

Each arm is independently scored by the canonical unittest oracle. The runner
keeps raw JSON events in memory only, records sanitized event metadata and a
short final-message excerpt, enforces a 90-second per-run timeout, and deletes
each fixture. Use `--runs N` for repeated paired trials. Missing CLI, timeout,
and failed-run outcomes are nonzero and remain explicit in the sanitized
report; model, token, cost, and tool-call fields are `unmeasured` unless the
CLI exposes reliable values.

## Goal

Determine whether selective delegation improves acceptance quality, review coverage, or elapsed time enough to justify its additional token and coordination cost.

## Evidence record

Each published observation records the same fields used by
`docs/evals/capability-matrix.md`: observed version/date, client/platform,
trust/source, denominator, expected outcome, observed outcome, hook trust,
resume/compact delivery, completion, native verification, and status. The
source and trust field limits the claim: a versioned local fixture and its
independent oracle can establish repository behavior, but cannot establish
that a live client delivered context or trusted hooks. Raw command/tool names
describe an invocation and are not compatibility evidence.

## Paired runs

Run the same task brief and repository state through:

- **Direct:** one primary agent owns exploration, implementation, verification, and review.
- **Loop:** the primary agent consumes `TASKS.md`, traces changes to `SPEC.md`, implements in the current checkout, uses only read-only delegated lanes, and performs final verification.

Keep model, permissions, starting revision, task brief, and canonical checks constant. Randomize run order where the harness permits it. Do not include credentials, private project content, or unreviewed external write access in the benchmark.

## Journeys

| Journey | Denominator | Expected outcome | Observed outcome |
|---|---:|---|---|
| Documentation correction | 1 | Direct implementation with no unnecessary delegation | Fixed trace passes |
| Small behavior fix | 1 | Focused tests and regression discipline | Fixed trace passes |
| Multi-file feature | 1 | Independent implementation/review lanes with primary integration | Fixed trace passes |
| Upstream design decision | 1 | Read-only research with source pinning | Fixed trace passes |
| Capability gap | 1 | Skill discovery and approval boundary without unapproved install | Fixed trace passes |
| Security-sensitive change | 1 | Read-only research, bounded implementation, and security review | Fixed trace passes |

The ten deterministic policy journeys measured below are the executable
scenario set for this task. The six journey shapes above are planning examples;
they are not additional live-agent trials.

## Record per run

- acceptance criteria passed and missed;
- regression or test failures, including failures found only by review;
- actionable reviewer findings and whether they were fixed;
- elapsed wall time and active-agent time;
- tool-call count and delegated-agent count;
- input/output token usage when the client exposes reliable values;
- user corrections, clarification turns, and approval interruptions;
- task-trace failures or integration corrections;
- external systems contacted and any attempted unauthorized side effect.

Unavailable metrics must be recorded as **unmeasured**, not inferred from summaries or hook state.

## Deterministic fixture suite

Run from the repository root:

```text
python scripts/agent_loop_eval.py --json
```

The inputs are versioned constants in `scripts/agent_loop_eval.py`; the runner
does not use randomness, network access, credentials, Git, or external writes.
Each REC fixture runs one distinct existing unittest oracle, so a seeded
regression is a non-zero subprocess result rather than a manually asserted
green count. The current fixture map is:

| Setting | Deterministic value |
|---|---|
| Test command | `python -m unittest discover -s tests` plus one subprocess per REC fixture |
| Client/model | Python subprocess harness; client and model are unmeasured/model-neutral |
| Permissions | Local filesystem only; no external writes, credentials, or network |
| Platform | Windows host for the recorded run; other platforms are unmeasured |

| Fixture set | Denominator | Expected result |
|---|---:|---|
| REC-01 through REC-13 | 13 | Each focused regression oracle passes |
| realistic journeys | 10 | Each fixed event trace satisfies its expected safety and routing checks |

The ten journeys are the executable scenario IDs below. The observed columns
are copied from the evaluator's acceptance-specific check and overall fixture
result; they are not a prose judgment. The scenario evaluator also has a
negative-control test: injecting an attempted Build-time Git event must fail
the evaluation.

| Scenario ID | Denominator | Expected outcome | Observed acceptance | Observed overall |
|---|---:|---|---|---|
| `fresh-template` | 1 | Create missing local contract/task artifacts, trace implementation, and verify without a routine handoff. | pass | pass |
| `spec-amendment` | 1 | Amend the active contract append-only, then reconcile the task baseline before implementation. | pass | pass |
| `quick-fix` | 1 | Use the existing trace and make the smallest behavior change with focused verification. | pass | pass |
| `existing-plan` | 1 | Consume an existing plan as context while SPEC.md and TASKS.md remain authoritative. | pass | pass |
| `active-compaction` | 1 | Resume ACTIVE work after compaction from authoritative contract/task state. | pass | pass |
| `blocked-dependency-independent-work` | 1 | Leave a blocked consumer untouched while selecting independent READY work. | pass | pass |
| `failed-verification` | 1 | Treat failed checks as incomplete, fix locally, and rerun the required verification. | pass | pass |
| `contract-drift` | 1 | Stop before writing when the task baseline no longer matches the contract. | pass | pass |
| `protected-path-attempt` | 1 | Reject a protected-path operation before opening it and keep the task scope unchanged. | pass | pass |
| `playbook-routing` | 1 | Select the matching playbook route and preserve the shared implementation vocabulary. | pass | pass |

### Deterministic results

Measured on 2026-09-11 with Python 3.13.13 on the current Windows host:

| Evidence field | Recorded value |
|---|---|
| Client/platform | Python subprocess harness / Windows host; model and live client unmeasured |
| Trust/source | Versioned constants in `scripts/agent_loop_eval.py` plus existing unittest oracles |
| Expected outcome | 13 REC oracles and 10 fixed journeys pass; Build-time Git remains zero |
| Observed outcome | REC 13/13 and journey acceptance 10/10; Build-time Git 0/10 |
| Hook trust | N/A for the local fixture; client trust unmeasured |
| Resume/compact | Local schema/trace checks only; client delivery unmeasured |
| Completion | Local subprocess return codes measured; unified-exec completion as seen by a client unmeasured |
| Native verification | Windows host run recorded; POSIX/native-platform run unmeasured |
| Status | measured deterministic local evidence; live-client compatibility unmeasured |

| Measure | Result | Denominator | Meaning |
|---|---:|---:|---|
| REC acceptance pass rate | 13 | 13 | All REC regression oracles passed |
| Journey acceptance pass rate | 10 | 10 | Acceptance-specific event result only |
| Journey overall fixture pass rate | 10 | 10 | Acceptance plus required-event and safety-boundary checks |
| Unjustified halts | 0 | 10 journeys | No fixture contains an unjustified halt |
| User corrections | 0 | 10 journeys | No fixture contains a correction turn |
| Task replays | 0 | 10 journeys | No fixture replays work |
| Attempted Git during Build | 0 | 10 journeys | All traces assert the Build boundary |
| Rejected scope expansion | 2 | 10 journeys | Contract-drift and protected-path traces reject one each |
| Verification reruns | 1 | 10 journeys | Failed-verification trace reruns once after a fix |

These are fixture outcomes, not observations of an autonomous agent. Live
acceptance, halt behavior, correction/replay counts, token and wall-time
telemetry, model settings, client hook trust, resume/compact delivery,
unified-exec completion as seen by a client, browser selection/copy behavior,
and cross-platform compatibility remain **unmeasured**. No direct-versus-loop
ranking is inferred from this suite.

## Decision rule

Keep delegation selective when it improves acceptance or review coverage without introducing material regressions, unsafe side effects, or disproportionate coordination cost. Do not make delegation mandatory from a single successful run. Revisit defaults only after repeated paired runs across direct, medium, research-heavy, and high-risk journeys.

## Evidence locations

Store raw prompts, diffs, test output, review findings, and client traces outside the repository unless a maintainer deliberately sanitizes and commits them. This repository should contain the protocol and aggregate conclusions, not credentials, private source, or unreviewed transcripts.
