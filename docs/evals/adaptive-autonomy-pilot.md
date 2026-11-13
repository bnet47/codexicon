# Adaptive recovery pilot

**Date:** 2026-11-14
**Scope:** T-039 and T-040
**Decision:** retain current recovery defaults; candidate remains inactive

## Candidate and protocol

The proposed recovery text is in
[`agent_docs/experiments/adaptive-recovery.md`](../../agent_docs/experiments/adaptive-recovery.md).
The frozen baseline identity is
`sha256:0f5db1e6c0ae8e5aec408c5633d71b53f50b2354f693e827e367e12c3ed34c2a`;
the staged candidate identity is
`sha256:9d00f33842196cde13aec3b886af3dcada4b4e6bbc8cd11658bfc1930df10c7f`.
The candidate changes only the autonomous Build and context checkpoint skill
files in a separate temporary copy. It does not change active defaults.

The protocol plans two repeats in each of three arms: plain Codex, frozen
starter, and recovery candidate. `debug` without a recovery scenario is the
normal control. The failure cases are `debug` with `tool-unavailable` and
`browser-flow` with `interrupted`. Recovery runs are capped at two repeats. A
missing or unobserved arm remains in the planned denominator and counts as
unavailable; it is not counted as a failed agent result.

## Observations

| Case | Planned denominator | Attempted | Observed result |
|---|---:|---:|---|
| Normal `debug` control | 2 pairs / 4 plain and starter arms | 2 pairs / 4 arms, from the T-038 pilot | Plain accepted 0/2; starter accepted 0/2. Three invocations timed out; the remaining plain invocation completed but failed the independent oracle. Scope and cleanup passed for all four. No candidate arm was included in this earlier control. |
| `tool-unavailable` recovery | 2 pairs / 6 arms | 0 | Unmeasured. The current client runner cannot independently observe tool availability; representing the outage in task text alone would not prove the condition occurred. Repeated T-038 debug invocations also timed out. |
| `interrupted` recovery | 2 pairs / 6 arms | 0 | Unavailable. The runner has no trusted rendered-browser state observer or client continuation signal, so it cannot establish partial progress, resume behavior, or duplicate effects. |

The normal control comes from [the T-038 adaptive-autonomy paired pilot](capability-matrix.md#capability-matrix).
The runner now accepts `--scenario tool-unavailable` for `debug` and
`--scenario interrupted` for `browser-flow`. The interruption path returns an
unavailable report with zero attempted arms rather than simulating a client
resume. The tool outage prompt is explicitly labeled as an instruction-only
scenario and leaves actual client tool availability unmeasured.

The offline policy suite checks the bounded fallback, planned versus attempted
denominators, duplicate mutation IDs, and safe handling when the interruption
observer is missing. It validates the scenario/report contract, not whether a
live agent follows the candidate text. See the recovery scenarios and pilot
record in [`agent_docs/experiments/adaptive-recovery.md`](../../agent_docs/experiments/adaptive-recovery.md).

## Decision and limits

There is no live evidence that the candidate improves recovery, intervention
count, or completion quality. Keep the candidate inactive and retain the
current defaults. Continue with method selection, initialization verification,
and skill comparison as separate candidates; this pilot does not authorize
automatic promotion, model selection, or increased delegation.

Live tool recovery remains unmeasured until a client can expose the prescribed
tool-availability signal. Interrupted browser recovery remains unavailable
until a rendered-state observer and reliable continuation signal are wired to
the runner. Tokens, cost, model pickup, tool calls, interventions, and
cross-platform behavior also remain unmeasured.
