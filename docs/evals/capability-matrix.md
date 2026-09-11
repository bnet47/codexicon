# Capability matrix and evidence boundaries

This matrix is the capability evidence for T-026/R-026/I-020/A-026. It records
what was observed, how it was observed, and what remains unavailable. A green
local fixture is evidence about the fixture and its repository checks; it is
not evidence that a live client trusts hooks, delivers resume context, or
surfaces a completed unified execution.

The observation date is the date of the run, not the date this document was
edited. `Measured` means the named local oracle observed the behavior.
`Unmeasured` means no direct observation exists. `Unsupported/not run` means
the surface was outside the executed evidence set. Raw command or tool names
are execution descriptions only and never establish client compatibility.

## Evidence field contract

Every matrix row and published scenario record carries these fields:

| Field | Meaning |
|---|---|
| Observed version/date | Version exposed by the observed runtime, or `not exposed`, plus the run date |
| Client / platform | The actual client surface and operating-system/runtime host used |
| Trust / source | Which fixture, oracle, runner, or direct client observation produced the result and what that source can be trusted to establish |
| Denominator | The number of trials, arms, fixtures, or scenarios behind a count |
| Expected outcome | The acceptance behavior defined before the observation |
| Observed outcome | The result actually emitted by the named source, including timeout or no-result states |
| Hook trust | Whether a client was observed to trust hook output; `N/A` means no client hook was involved |
| Resume/compact | Whether delivery was observed by a client, or only a local schema/fixture path was checked |
| Completion | Whether the independent oracle or client-facing execution completed |
| Native verification | The host-native checks actually run; unrun platforms remain unmeasured |
| Status | `measured local evidence only`, `unmeasured live-client behavior`, or `unsupported/not run` for the claim in this row |

## Capability matrix

| Surface | Observed version/date | Client / platform | Trust / source | Denominator | Expected outcome | Observed outcome | Hook trust | Resume/compact | Completion | Native verification | Status |
|---|---|---|---|---:|---|---|---|---|---|---|---|
| Deterministic template harness | Python 3.13.13 / 2026-09-11 | Python subprocess harness on Windows host | Trusted local source: versioned constants in `scripts/agent_loop_eval.py` and canonical unittest oracles; no live client | REC 13; journeys 10 | All REC oracles and fixed safety/routing traces pass | REC 13/13 and journeys 10/10; metric denominators are recorded below | N/A; hooks are not exercised by a client | Fixture/schema behavior only; live delivery is unmeasured | Local subprocess/oracle results measured; unified client completion unmeasured | Windows-host checks measured; POSIX checks unmeasured | measured local evidence only |
| Codex CLI live attempt | Version not exposed / 2026-09-11 | Codex CLI invocation on the current Windows host | Sanitized runner metadata and independent fixture oracle; raw transcript is discarded; this source cannot establish general client compatibility | 1 paired trial planned; direct 1 started; guided 0 started | Both arms complete and the independent calculator oracle passes without unrelated files | Direct arm timed out with no result; guided arm was not started; acceptance and regressions are unmeasured | Unmeasured | Unmeasured | Unmeasured because no client completion was observed | Windows invocation was attempted; native client verification remains unmeasured | unmeasured live-client behavior |
| Codex desktop/local client | Version/date not exposed; no trial | Client and platform not run | No direct observation; raw tool names or product labels are not evidence | 0 | A direct client trial would be required | No observation | Unmeasured | Unmeasured | Unmeasured | Unmeasured | unsupported/not run |
| Browser/live client | Version/date not exposed; no trial | Browser client and platform not run | No direct observation; browser capability is not inferred from repository or tool names | 0 | A browser trial would be required | No observation | Unmeasured | Unmeasured | Unmeasured | Unmeasured | unsupported/not run |
| POSIX host | Version/date not exposed; no run | POSIX host not run | No cross-platform inference from the Windows run | 0 | The deterministic suite would need to run natively on POSIX | No observation | N/A | Unmeasured | Unmeasured | Unmeasured | unsupported/not run |

The only measured support statement here is that the repository's deterministic
checks ran on the recorded Windows/Python host. The matrix does not rank
clients, models, or platforms and does not turn the Codex command spelling into
a compatibility claim.

## Deterministic scenario evidence

The reproducible scenario suite uses ten fixed event traces. Each scenario has
one denominator, a predeclared expected outcome, and an observed result from
the local evaluator. These are repository-policy measurements, not live-agent
measurements.

Shared scenario observation context:

| Evidence field | Value for all ten fixed traces |
|---|---|
| Observed version/date | Python 3.13.13 / 2026-09-11 |
| Client / platform | Python subprocess harness on the current Windows host; live client unmeasured |
| Trust / source | Versioned constants in `scripts/agent_loop_eval.py` and fixed event-trace checks; no client transcript |
| Hook trust | N/A for the local evaluator; client hook trust unmeasured |
| Resume/compact | Local event/schema behavior measured for `active-compaction`; client delivery unmeasured |
| Completion | Fixed evaluator result measured; unified-exec completion as seen by a client unmeasured |
| Native verification | Windows-host command run recorded; POSIX/native-platform run unmeasured |
| Explicit unmeasured fields | Live-agent behavior, client compatibility, browser behavior, and reliable client telemetry |

| Scenario | Denominator | Expected outcome | Observed outcome | Status |
|---|---:|---|---|---|
| `fresh-template` | 1 | Route through autonomous Build, trace contract/task state, and avoid Build-time Git | Passed fixed trace | measured |
| `spec-amendment` | 1 | Preserve an append-only contract amendment and reconcile the task baseline | Passed fixed trace | measured |
| `quick-fix` | 1 | Use an existing trace, make the smallest change, and run focused verification | Passed fixed trace | measured |
| `existing-plan` | 1 | Consume plan context while SPEC.md and TASKS.md remain authoritative | Passed fixed trace | measured |
| `active-compaction` | 1 | Resume ACTIVE work with bounded authoritative context after compaction | Passed fixed trace | measured locally; client delivery unmeasured |
| `blocked-dependency-independent-work` | 1 | Keep a blocked consumer untouched and select independent READY work | Passed fixed trace | measured |
| `failed-verification` | 1 | Treat a failed check as incomplete and rerun after the local fix | Passed fixed trace | measured |
| `contract-drift` | 1 | Reject drift and scope expansion before implementation | Passed fixed trace | measured |
| `protected-path-attempt` | 1 | Reject a protected-path operation before reading it | Passed fixed trace | measured |
| `playbook-routing` | 1 | Keep selector, card, prompt, and implementation vocabulary aligned | Passed fixed trace | measured |

Reproduce the scenario evidence with:

```text
python scripts/agent_loop_eval.py --scenarios-only
python scripts/agent_loop_eval.py --json
```

The evaluator reports the host platform and leaves model, live-agent,
client-hook, resume/compact-delivery, browser, unified-exec, and unrun
POSIX/native-platform fields explicitly `unmeasured`. No credential, raw
transcript, or external write is required.

## Explicitly unmeasured or unsupported

The following claims are intentionally not made by this matrix:

- live client compatibility, model identity/ranking, or tool-name equivalence;
- client hook trust and client-visible resume/compact delivery;
- unified-exec completion as surfaced by a desktop, browser, or other client;
- browser selection/copy behavior and client intervention telemetry;
- POSIX/native-platform results not run on the recorded host;
- token, cost, tool-call, latency, or cross-client comparison metrics when the
  client does not expose reliable values.
