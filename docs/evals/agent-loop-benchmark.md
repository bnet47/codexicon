# Agent-loop benchmark

This benchmark compares direct single-agent work with the bounded `$engineering-loop`. It is a measurement protocol, not a claim that live Codex telemetry is available in every client.

## Goal

Determine whether selective delegation improves acceptance quality, review coverage, or elapsed time enough to justify its additional token and coordination cost.

## Paired runs

Run the same task brief and repository state through:

- **Direct:** one primary agent owns exploration, implementation, verification, and review.
- **Loop:** the primary agent delegates only independent lanes, uses isolated worktrees for writers, integrates the results, and performs final verification.

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
- worktree conflicts or integration corrections;
- external systems contacted and any attempted unauthorized side effect.

Unavailable metrics must be recorded as **unmeasured**, not inferred from summaries or hook state.

## Decision rule

Keep delegation selective when it improves acceptance or review coverage without introducing material regressions, unsafe side effects, or disproportionate coordination cost. Do not make delegation mandatory from a single successful run. Revisit defaults only after repeated paired runs across direct, medium, research-heavy, and high-risk journeys.

## Evidence locations

Store raw prompts, diffs, test output, review findings, and client traces outside the repository unless a maintainer deliberately sanitizes and commits them. This repository should contain the protocol and aggregate conclusions, not credentials, private source, or unreviewed transcripts.
