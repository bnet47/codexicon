# First-party skill comparison

**Pilot skill:** `$autonomous-build`
**Candidate source:** T-041 method-selection insertion
**Date:** 2026-11-14
**Decision:** retain current skill; candidate remains inactive

## Pinned sources and cases

The frozen current skill is
`.agents/skills/autonomous-build/SKILL.md`, SHA-256
`531c32fc25b3cded1c1bcb1b5082885b8665775da55089f0616e641991db8aa8`.
The candidate skill SHA-256 is
`3d98aea5eae8e3da2dcec11885e3b9fbe1c939b43c08417b8f343ddb19bb209e`;
its complete staged starter identity is
`sha256:c86d9a351e523dbc8bdfeaf14500ae3054389fd2c5ba1fa283eee05c766ae4fa`.
Candidate text and file-level provenance are in
[`agent_docs/experiments/method-selection.md`](../../agent_docs/experiments/method-selection.md).

The fixed case set is:

| Case | Trigger class | Expected activation | Independent outcome |
|---|---|---:|---|
| `positive-debug` | Positive | Yes | Repair the synthetic viewport defect and preserve neighboring behavior |
| `conceptual-near-miss` | Near miss | No | Give the requested definition without inventing or changing a defect |
| `held-out-diagnosis` | Held out | Yes | Diagnose the synthetic calculator mismatch without changing source |

Each case runs in plain/no-skill, pinned-current, and candidate arms. Inputs,
fixture, task text, model settings, permissions, timeout, and independent
verifier are matched within each case. Artifact outcome and elapsed time are
separate from activation. Skill presence is recorded from the staged arm;
`skill_invocation` remains `unmeasured` unless a trusted client event explicitly
confirms it. A model-written claim that it used a skill is not a trusted signal.
Cost, tokens, tool calls, and interventions remain unmeasured when the client
does not expose them.

## Current evidence

The local integration test exercises 3 cases × 3 arms = 9 mock invocations.
All nine independently checked artifacts pass. This proves the paired staging,
oracle, and report paths work; it does not measure live agent behavior.

No live skill comparison was run. The T-038 Codex CLI pilot timed out in 7 of 8
attempted invocations, and the client does not expose a trustworthy skill
invocation event. The report therefore has no observed false-trigger or
missed-trigger count. Those fields stay `null`/`unmeasured`; skill presence is
not used to fill them. No quality, latency, or cost superiority is claimed.

## Reproduce

First reconstruct the frozen T-038 source and the T-041 method candidate using
the recipes and identities in
[`agent_docs/experiments/method-selection.md`](../../agent_docs/experiments/method-selection.md).
The two staged source roots are session-local; if they are unavailable, rebuild
them from the saved source and verify both identities before running. Then use:

```text
python scripts/live_agent_eval.py --skill-comparison --baseline-source <frozen-T-038-source> --candidate-source <T-041-candidate-source> --runs 1 --timeout-seconds 30 --json
```

The comparison is capped at two repeats per case and arm. An invocation status
of `unmeasured` makes the overall report `unmeasured` even when all artifact
oracles pass. Preserve sanitized metadata only; the runner does not save raw
transcripts.

## Promotion gate

Do not promote from a single pilot or from skill presence. A maintainer needs
repeated observed activation on positive and held-out cases, no observed
activation on the near miss, independent outcome quality without a held-out
regression, and available time/cost trade-offs. Record any promotion as a new
append-only decision. The current evidence does not meet that bar.
