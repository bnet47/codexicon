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

## Paired runs

Run the same task brief and repository state through:

- **Direct:** one primary agent owns exploration, implementation, verification, and review.
- **Loop:** the primary agent consumes `TASKS.md`, traces changes to `SPEC.md`, implements in the current checkout, uses only read-only delegated lanes, and performs final verification.

Keep model, permissions, starting revision, task brief, and canonical checks constant. Randomize run order where the harness permits it. Do not include credentials, private project content, or unreviewed external write access in the benchmark.

## Journeys

| Journey | What it tests | Expected loop shape |
|---|---|---|
| Documentation correction | Ceremony and routing overhead | Direct implementation; no delegation |
| Small behavior fix | Focused tests and regression discipline | Direct or one bounded implementer |
| Multi-file feature | Independent implementation and review lanes | Explorer, implementer, reviewer, primary integration |
| Upstream design decision | GitHub research quality and source pinning | `github-researcher` plus primary decision |
| Capability gap | Skill discovery, review, and approval boundary | `$find-skills` search and recommendation; no install unless approved |
| Security-sensitive change | Boundary preservation and review depth | Read-only research, bounded implementation, independent security review |

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

The ten journeys are `fresh-template`, `spec-amendment`, `quick-fix`,
`existing-plan`, `active-compaction`, `blocked-dependency-independent-work`,
`failed-verification`, `contract-drift`, `protected-path-attempt`, and
`playbook-routing`. The scenario evaluator also has a negative-control test:
injecting an attempted Build-time Git event must fail the evaluation.

### Deterministic results

Measured on 2026-09-11 with Python 3.13.13 on the current Windows host:

| Measure | Result | Denominator | Meaning |
|---|---:|---:|---|
| REC acceptance pass rate | 13 | 13 | All REC regression oracles passed |
| Journey acceptance pass rate | 10 | 10 | All fixed journey traces passed |
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
