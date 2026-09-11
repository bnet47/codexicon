# Live agent results — 2026-09-11

This is the sanitized evidence record for T-020/R-020. It documents bounded
paired-trial attempts, not a ranking or superiority claim.

## Protocol

- Requested command: `python scripts/live_agent_eval.py --smoke`
- Verification command actually started: `python scripts/live_agent_eval.py --smoke --json`
- Date: 2026-09-11
- Denominator: 1 paired trial; 1 direct arm and 1 guided arm
- Codex invocation: `codex exec --ephemeral --sandbox workspace-write --skip-git-repo-check -C <temp> --json <prompt>`
- Fixture: fresh temporary `calculator.py` with a deliberately failing `add`
  implementation and a harness-restored unittest oracle for each arm
- Acceptance: the independent oracle passes after the invocation
- Regression: an oracle or unrelated fixture-file change is recorded; raw
  transcripts are never persisted
- Timeout: 90 seconds per Codex invocation
- Additional local-provider probe: `codex exec --oss --local-provider ollama --model qwen3.8:27b ...`

## Evidence classification

| Evidence field | Observed value |
|---|---|
| Observed version/date | CLI version not exposed / 2026-09-11 |
| Client/platform | Default Codex CLI invocation on the current Windows host; local-provider probe was also attempted |
| Trust/source | Sanitized runner metadata plus an independent calculator unittest oracle; raw transcripts and temporary paths were discarded |
| Denominator | 1 paired trial planned; direct arm 1 started; guided arm 0 started; local-provider probe 1 |
| Expected outcome | Each arm completes and the independent oracle passes without unrelated fixture changes |
| Observed outcome | Direct default-provider arm timed out with no result; guided arm was not started; local-provider probe timed out; acceptance and regression outcomes are unmeasured |
| Hook trust | Unmeasured; no client hook-delivery observation was produced |
| Resume/compact | Unmeasured; this trial did not exercise client resume/compact delivery |
| Completion | Unmeasured; no client-facing completion was observed |
| Native verification | The Windows command path was attempted; native client verification and POSIX results are unmeasured |
| Status | unmeasured live-client behavior / timeout evidence only |

Raw command/tool names describe the attempted invocation and are not
compatibility evidence.

## Results

The default-provider smoke command did not emit a result during the bounded
verification window and was stopped before a paired result could be emitted.
The local Ollama probe also timed out after 45 seconds before producing a final
message. No raw Codex transcript, credential, temporary path, or private agent
output is included. The evaluator was hardened after the first attempt to use
UTF-8 replacement decoding, disable bytecode-cache false negatives, close
stdin, and use ephemeral output files plus process-tree cleanup.

| Arm | Acceptance | Regressions | Elapsed | Exit status | Test status | Interrupted |
|---|---:|---:|---:|---:|---|---|
| Direct | unmeasured | unmeasured | unmeasured | timeout/no result | unmeasured | yes |
| Codexicon-guided | unmeasured | unmeasured | unmeasured | not started | unmeasured | no |

The live trial did not complete, so acceptance and regression results are
unmeasured. This is an explicit unavailable/timeout result, not evidence that
either arm is better. Model, token, cost, tool-call, and intervention metrics
are **unmeasured**. The fixture covers one tiny calculator behavior and cannot
establish general agent reliability; repeated paired trials and a completed CLI
run are required for any comparison.

The command spelling identifies how the evaluator attempted the run; it does
not establish Codex CLI, desktop, browser, hook, resume/compact, or platform
compatibility. Those claims remain unmeasured until the corresponding client
and platform are directly observed.
