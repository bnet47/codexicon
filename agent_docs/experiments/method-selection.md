# Method-selection candidate

**Status:** Candidate insertions are staged for evaluation only; active defaults
remain unchanged. The maintainer-facing method note in `docs/agent-patterns.md` is a
reviewable protocol, not proof that a live client selected or used a method.

## Candidate insertion block A · autonomous Build

> ## Select a method from acceptance
>
> Before a substantial or uncertain task, derive the intended outcome, first
> useful observation, preferred available method, safe fallback, and verifier
> from the task rubric. Keep a known, low-risk fix on the direct path. For an
> ambiguous defect, start with the smallest diagnostic that distinguishes
> plausible causes. For conflicting sources, establish source precedence and
> independently reconcile selected values. For a web UI outcome, use a
> rendered interaction and read back the resulting DOM or persisted state. For
> native desktop acceptance, use a fresh app snapshot and verify with a new
> snapshot or saved artifact. Prefer an approved API or connector when it
> supports the same outcome and verifier; use interaction when the interaction
> itself is part of acceptance.

## Candidate insertion block B · investigation

> ## Choose the next observation
>
> Select the smallest observation that distinguishes the remaining hypotheses
> and can be checked by the task's independent acceptance evidence. Keep source
> inspection separate from rendered UI claims and keep configuration or
> availability claims separate from observed client behavior. If the preferred
> method is unavailable, use a fallback only when it is authorized and produces
> the same acceptance evidence. Otherwise record the precise missing
> capability. Do not add a retry budget or broaden authority.

## Fixed local scenarios

| Case | First observation | Method | Verifier |
|---|---|---|---|
| Known, low-risk change | Read the scoped interface and current state | Direct edit | Focused acceptance check |
| Ambiguous defect | Run the smallest failing reproduction | Diagnostic probe | Reproduction plus adjacent regression check |
| Conflicting source records | Identify authoritative sources and their dates | Source reconciliation | Independent totals and selected evidence IDs |
| Web UI outcome | Inspect the running page and current rendered state | Rendered browser interaction | Fresh DOM and persisted-state readback |
| Native desktop action | Take a fresh accessibility snapshot of the target app | Native desktop interaction | Fresh app snapshot or saved-artifact readback |
| Preferred method unavailable | Check for an authorized fallback with equivalent proof | Same-evidence fallback, or blocked | Existing acceptance verifier or precise blocker |

The comparison should use intended triggers, near misses, and held-out tasks.
The tests exercise this decision table as deterministic policy examples. They
do not establish that a live client invoked a tool, observed a rendered page,
or chose the preferred method. No trial can promote the candidate
automatically.

## Staging evidence

The baseline and candidate are prepared in isolated temporary copies using the
scaffold's declared `STARTER_FILES` plus `TEMPLATE_VERSION`. The frozen source
was reconstructed from the T-039 session copy and checked against the T-038
identity before applying this candidate.

| Source | Identity |
|---|---|
| Frozen T-038 baseline | `sha256:0f5db1e6c0ae8e5aec408c5633d71b53f50b2354f693e827e367e12c3ed34c2a` |
| Method-selection candidate | `sha256:c86d9a351e523dbc8bdfeaf14500ae3054389fd2c5ba1fa283eee05c766ae4fa` |

Only these paths differ:

| Changed path | Baseline SHA-256 | Candidate SHA-256 |
|---|---|---|
| `.agents/skills/autonomous-build/SKILL.md` | `531c32fc25b3cded1c1bcb1b5082885b8665775da55089f0616e641991db8aa8` | `3d98aea5eae8e3da2dcec11885e3b9fbe1c939b43c08417b8f343ddb19bb209e` |
| `.agents/skills/investigate/SKILL.md` | `090c520c755c3465363886a74a659bd25d64549ef51097df86f6485b06863e8a` | `601ce88a30f157c51c6701e0d04fcd47d1e50cf0f6d8d54529f233985aa6bbbd` |

The temporary directories are session-local and intentionally omitted. To
reconstruct them, copy `scaffold.STARTER_FILES` and `TEMPLATE_VERSION` from the
frozen T-038 source into a clean temp baseline, verify the baseline identity,
clone it, then insert blocks A and B at `## Loop` in the autonomous Build skill
and `## 3. Form hypotheses` in the investigation skill. The active skill files
remain unchanged.
