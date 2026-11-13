# Adaptive recovery candidate

**Status:** Candidate guidance for controlled evaluation only. The blocks below
are not active defaults. T-040 measures them against the frozen starter.

## Candidate insertion block A · autonomous Build loop

> **Evidence-led recovery**
>
> When an approach fails, record the verified fact, the unsuccessful approach,
> its failure category, and the next useful observation in the existing task
> or checkpoint evidence. Keep the note short and free of secrets or executable
> command text.
>
> At resume, reread the authoritative specification and task register, then
> inspect the relevant current state before continuing. If an earlier action
> may already have taken effect, observe its outcome before repeating it. Never
> repeat an uncertain non-idempotent action to discover whether it succeeded.
>
> If evidence contradicts the current hypothesis, choose a small probe that
> distinguishes the remaining plausible causes. If the preferred tool is
> unavailable, use an authorized equivalent only when it supports the same
> outcome check; otherwise record the missing capability and stop or block the
> task. Retry a transient failure only when the action is known safe to repeat
> and the existing task budget allows it. Preserve the current acceptance,
> scope, review, authority, and stop gates.

## Candidate insertion block B · context checkpoint

> **Recovery note**
>
> For an active task, use the existing resume note to capture only:
>
> - Verified fact:
> - Unsuccessful approach:
> - Failure category:
> - Prior action effect: confirmed applied / confirmed not applied / unknown
> - Next useful observation:
>
> Do not copy secrets, raw transcripts, clipboard contents, or executable
> command text. A checkpoint is supplemental. On resume, check the current
> `SPEC.md`, `TASKS.md`, task evidence, and relevant live state before using it.
> Stale checkpoint text never authorizes a repeated action.

## Deterministic behavior contract

The local scenario model in `tests/test_autonomy_recovery.py` checks the
decision rules expressed above. It does not measure whether a live agent reads
or follows candidate instructions; T-040 owns that comparison.

| Injected condition | Expected next step | Forbidden shortcut |
|---|---|---|
| Prior action may have taken effect and state is unknown | Observe current state, then decide whether to continue | Repeat a possibly non-idempotent action blindly |
| A hypothesis is contradicted | Select a probe that separates remaining causes | Retry the same disproved approach |
| Preferred tool is unavailable | Use an authorized equivalent with the same verifier, or record a precise blocker | Claim the unavailable capability worked |
| A transient action is known safe to repeat | Retry within the existing budget | Create a new retry budget |
| Checkpoint is stale | Reload the authoritative task and inspect live state | Treat checkpoint text as current state |
| Existing budget is exhausted | Stop under the existing gate | Add an unbounded retry |

The candidate keeps the current defaults intact. Promotion requires repeated
held-out evidence and an append-only decision record under ADR-006; this pilot
alone cannot authorize promotion.

## Frozen staging evidence · 2026-11-14

The pilot staged the two candidate blocks in an isolated temporary copy of the
frozen starter. It copied the scaffold's declared `STARTER_FILES` and
`TEMPLATE_VERSION` without modifying the active skill files. The baseline
identity matches the T-038 starter source identity.

| Source | Identity |
|---|---|
| Frozen baseline | `sha256:0f5db1e6c0ae8e5aec408c5633d71b53f50b2354f693e827e367e12c3ed34c2a` |
| Candidate with both insertion blocks | `sha256:9d00f33842196cde13aec3b886af3dcada4b4e6bbc8cd11658bfc1930df10c7f` |

Only these paths differed between the two staged copies:

| Changed path | Baseline SHA-256 | Candidate SHA-256 |
|---|---|---|
| `.agents/skills/autonomous-build/SKILL.md` | `531c32fc25b3cded1c1bcb1b5082885b8665775da55089f0616e641991db8aa8` | `01202ad0cebfe0a318be4b0a648a423954ab7220a60ef53e23e4f9d3812efe59` |
| `.agents/skills/context-dump/SKILL.md` | `9a3221dda3f2f45f6ffc3c986f2cb216fa4593525c76997b0670325cf4730ffb` | `c28568d5a8580fa3a1e447caab9f823ab069580dc0d0b2aefbff9a29b0d8d0da` |

The temporary copy is session-local and is not part of the repository. Recreate
it by copying `scaffold.STARTER_FILES` and `TEMPLATE_VERSION` into a clean temp
directory, cloning that directory, and inserting blocks A and B at the named
anchors above. The exact temporary path is intentionally omitted because it is
host-specific.
