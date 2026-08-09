# Codexicon evolution evaluation

**Date:** 2026-08-08
**Scope:** `CODEXICON_EVOLUTION_EVALUATION_BRIEF-1.md` and the repository at this revision
**Verdict:** Proceed with a small autonomy and verification improvement; defer a new orchestration subsystem.

## Executive conclusion

Codexicon is not uniformly too procedural. Clear, tightly scoped work already routes to `$quick`, and the stop hook is concerned with verification evidence rather than formal lifecycle artifacts. The friction is concentrated in two places:

- ambiguous or medium work can turn brainstorm, specification, planning, and execution into user-managed approval gates;
- the hook's conservative command classifier treated several harmless inspection commands as mutations, invalidating otherwise valid lint/test evidence.

The second issue was confirmed and fixed. The first was confirmed in skill instructions and is now reduced by allowing a request that already authorizes implementation to carry through internal planning and review. The default operating contract is now explicitly Explore, Build, or Ship, with Build owning reversible internal decisions and Ship retaining explicit authority boundaries.

The evaluation does not support adding a configurable autonomous runtime, a persistent agent loop service, an automatic external-skill installer, or a new reviewer panel. Codex already owns the task loop at the instruction level, and the repository has no runtime event or policy engine that could safely enforce those larger designs.

## Current-state findings

### Routing and human interruption

- `AGENTS.md` routes clear small work to `$quick` and explicitly says not to force ceremony onto a clear task.
- `$quick` has no approval step. It inspects, edits, verifies, reviews the diff, and reports.
- `$brainstorm` asked one question at a time and stopped before implementation. `$write-plan` expected an approved spec, and `$execute-plan` expected an approved plan. Those instructions could make the user the workflow engine for a medium task even when the original request already authorized implementation.
- `$discover` and `$init` remain intentional gates for the unconfigured template. They establish product identity and stack decisions that are expensive or materially consequential; removing them would trade visible friction for unsafe implicit choices.
- `$review` is correctly read-only and `$ship` correctly stops at the user's Git authority ceiling. These are safety boundaries, not unnecessary intermediate approvals.

Evidence: `AGENTS.md`, `START_HERE.md`, `.agents/skills/{quick,brainstorm,spec,write-plan,execute-plan,review,ship}/SKILL.md`.

### Verification and hooks

`.codex/hooks.json` runs:

- session initialization/resume hooks;
- `PreToolUse` for shell, read, edit, and write tools;
- `PostToolUse` for edits/writes and shell;
- compaction, stop, and session-end hooks.

The hook uses authenticated one-use receipts for canonical lint and test commands, durable pending write markers, session-scoped state, and fail-closed malformed-state handling. It does not use a repository content fingerprint; it uses a command classifier plus write timestamps and pending intents.

Before this change, the classifier allowed only a narrow read-only set. The following representative commands were classified as mutation-bearing and therefore invalidated verification:

| Command | Before | After | Safety treatment |
|---|---:|---:|---|
| `git diff`, `git diff --stat`, `git diff --name-only` | mutation | read-only | allowed |
| `git grep`, `git ls-tree` | mutation | read-only | allowed |
| `find`, `tree`, `grep`, `sed`, `wc` | mutation | read-only | allowed with write-option guards |
| `git branch --show-current`, `git status`, `git show` | read-only | read-only | unchanged |
| `git diff --output=...` | mutation | mutation | preserved |
| `find ... -delete` or `-exec` | mutation | mutation | preserved |
| `sed -i ...` | mutation | mutation | preserved |
| `tree -o ...` | mutation | mutation | preserved |
| arbitrary Python inspection | mutation | mutation | intentionally conservative |

The original behavior was reproducible through `definitely_read_only()` and the hook tests. The new behavior is covered by `test_common_inspection_does_not_invalidate_fresh_verification`, `test_common_read_only_shell_commands_do_not_require_verification`, and `test_read_only_commands_with_write_options_still_invalidate_verification` in `tests/test_template.py`.

### Stop behavior

The Stop hook blocks only when the repository has recorded writes and lint, or behavior-relevant tests, are missing or stale. It does not inspect whether a brainstorm, spec, plan, or reviewer artifact exists. A harmless command was indirectly able to block stopping only because it was misclassified as a write. The classifier fix removes that false positive without weakening the receipt contract.

### Existing autonomy capabilities

Codexicon already has useful pieces of the proposed model:

- local lifecycle telemetry in the hook, with unsupported token fields explicitly unavailable;
- a bounded researcher, reviewer, and implementer profile set;
- read-only review guidance;
- focused development checks plus final canonical checks;
- decision/checkpoint support through `scripts/codexicon.py`;
- explicit Git, deployment, credential, and external-write boundaries;
- commented, disabled MCP examples with trust guidance.

What is missing is an explicit default Build contract and a self-critique expectation. Those are now documented in `AGENTS.md` and `docs/codex.md`; they do not introduce a new runtime or mandatory artifact.

### External skill discovery

There is no automatic external skill discovery or installation path in the repository. MCP and external systems are documented as opt-in and disabled by default. This is the correct current baseline for a template: ordinary work should not turn into marketplace search, installation, and extra context loading.

## Severity-ranked issues

### HIGH - Harmless inspection invalidated verification

**Behavior:** command-name classification treated common diff, search, listing, and text-inspection commands as writes.
**Evidence:** direct classifier reproduction; existing hook state and Stop behavior; regression tests added in `tests/test_template.py`.
**Impact:** unnecessary lint/test reruns, repeated Stop interruptions, and loss of momentum after a final diff inspection.
**Root cause:** no repository-state fingerprint and an incomplete allowlist.
**Disposition:** fixed with an expanded, guarded read-only classifier. Dangerous flags remain mutation-bearing.

### MEDIUM - Multi-step workflow could become approval-driven

**Behavior:** brainstorm, plan, and execute instructions used language that implied separate acceptance gates.
**Evidence:** the skill bodies required an accepted direction/spec/plan even when a user request already authorized implementation.
**Impact:** extra turns, context loss, and premature decisions on medium work.
**Root cause:** workflow artifacts were described as handoffs rather than internal Build phases.
**Disposition:** fixed by allowing current-task authorization to continue through the phases; explicit artifact-only requests still stop.

### MEDIUM - No bounded quality loop is mechanically enforced

**Behavior:** the repository can review and verify work, but no runtime instruction requires the agent to critique and improve a technically passing but weak result.
**Impact:** quality may stop at first completion.
**Root cause:** Codex hook events expose verification and lifecycle state, not acceptance rubrics or quality deltas.
**Disposition:** document a bounded self-review expectation in Build. Do not create a loop daemon or numeric policy surface without runtime support and benchmark evidence.

### MEDIUM - Verification still relies on heuristics

**Behavior:** arbitrary read-only Python, shell wrappers, and commands that modify ignored/generated files remain conservatively mutation-bearing.
**Impact:** some false-positive reruns remain; broadening the classifier further could create false negatives.
**Root cause:** command payloads and repository state are separate concerns, and a general filesystem fingerprint is expensive and difficult to scope safely across Git, non-Git, Windows, generated files, and concurrent sessions.
**Disposition:** defer a fingerprint design. Revisit only with traces showing material residual false positives and a check-specific state model.

### LOW - External skill extension is documented but not discoverable by an explicit command

**Behavior:** users can read the MCP trust posture, but there is no `$find-skill` or governed external-skill lock workflow.
**Impact:** specialist capability discovery is less convenient.
**Root cause:** adding the CLI and provenance workflow would create a supply-chain subsystem.
**Disposition:** keep discovery explicit and manual for now; do not auto-trigger it. A future extension must search read-only, review complete skill contents and scripts, pin a reviewed source, install project-locally, and record provenance.

## Options considered

| Problem | Option | Assessment | Decision |
|---|---|---|---|
| Inspection invalidation | Expand guarded allowlist | Small, testable, preserves fail-closed behavior | Selected |
| Inspection invalidation | Fingerprint Git and relevant files | Stronger semantics, but higher cost and tricky ignored/generated/non-Git cases | Defer |
| Workflow friction | Replace all skills with one autonomous orchestrator | Could reduce gates, but adds a large untested subsystem and weakens explicit boundaries | Reject |
| Workflow friction | Document Explore/Build/Ship and remove accidental approval gates | Small, compatible, directly addresses the confirmed cause | Selected |
| Self-improvement | Fixed iteration/review config | Easy to describe, but no runtime owner and durable numeric defaults age poorly | Reject |
| Self-improvement | Task-specific internal rubric and plateau-aware review | Improves quality without a new subsystem | Selected as guidance |
| Independent review | Reviewer for every task | More coverage, unnecessary latency and context for trivial work | Reject |
| Independent review | Selective reviewer for medium/high-risk work | Matches existing reviewer profile and risk boundaries | Retain |
| External skills | Automatic search/install | Slower, unsafe, and not authorized by ordinary implementation requests | Reject |
| External skills | Explicit search/review/install flow | Safer future direction, but not justified as a current subsystem | Document as future option |

## Recommended operating model

### Explore

Use for investigation, comparison, diagnosis, and recommendations. It is read-only unless the request explicitly authorizes a modification.

### Build

Use by default for a clear implementation request:

```text
understand goal
-> inspect constraints
-> define acceptance evidence
-> choose reversible assumptions
-> implement
-> focused validation
-> critique the weakest important aspect
-> improve when meaningful
-> final verification
-> decision and evidence report
```

The agent owns file placement, naming, implementation approach, focused tests, small related correctness fixes, and the ordering of work. It records important assumptions and decisions instead of interrupting for routine preferences. It batches questions that genuinely block progress.

### Ship

Use for commit, push, pull request, publication, deployment, migrations, credential changes, destructive data work, and external-system writes. These remain explicit authority boundaries and continue to use `$ship` and `$production-readiness` where applicable.

The stop condition is evidence-based: acceptance is met, relevant verification is fresh, no blocking review or safety issue remains, and the agent has no known incomplete work. A self-review should stop when improvement plateaus, failures repeat, the result reaches the task-specific quality bar, or a human-owned boundary is encountered.

## Benchmark

### Repeatable method

The repository supports deterministic hook and structural checks, but it does not expose a live Codex transcript runner or stable token-usage payload. Therefore this evaluation separates measured results from expected workflow behavior:

1. Run the native lint, test, security, and doctor commands.
2. Run the hook classifier matrix before and after each classifier change.
3. For each journey below, record route, blocking questions, approval gates, verification commands, and whether the agent stops with safe next steps available.
4. In a live Codex harness, add elapsed time, tool calls, tokens, reviewer findings, and user corrections; those metrics are not claimed here.

### Journey comparison

| Journey | Current template | Recommended template | Result |
|---|---|---|---|
| Documentation typo | `$quick`; lint; no routine approval | Same | No added ceremony |
| Configuration edit | `$quick`; focused/full checks by risk | Same | No added ceremony |
| Small bug or endpoint | `$quick` when clear; tests and lint | Build loop owns internal review | Faster when the request is already clear |
| Medium feature | Brainstorm/spec/plan language can pause for acceptance | Internal phases continue under Build | Fewer context-breaking gates |
| Ambiguous product request | Ask questions, often one at a time | Batch blocking questions; recommend defaults | Lower clarification latency |
| Read-only investigation | Explore/research; no write | Explore; no write | Safety preserved |
| Failed implementation | Recovery is available but no explicit refinement loop | Re-enter Build with acceptance and evidence | Better momentum and recovery |
| Passing but weak implementation | May stop after checks pass | Critique and improve the weakest important aspect | Quality target is explicit |
| Full ship request | Explicit Git/shipping controls | Same | Safety preserved |
| External skill search | No automatic search/install | Explicit future extension only | No supply-chain detour |
| Destructive migration/external write | Escalation required | Same | Human boundary preserved |
| Reversible missing detail | Local assumptions permitted but not prominently framed | Assumption recorded and work continues | Fewer preference interruptions |

### Measured verification result

The final hook matrix confirms that the selected read-only commands no longer invalidate a passing verification state, while write-bearing options still do. The full test suite includes the new positive and negative cases. No claim is made that arbitrary scripts or ignored generated files are detected by a repository fingerprint; those remain conservative.

## External skill recommendation

Do not install or auto-discover external skills as part of normal Codexicon operation. Document the possibility only. If a future `$find-skill` or `$extend` capability is added, it should require explicit invocation, keep search read-only, avoid exposing sensitive project terms, review complete instructions and executable content, pin a reviewed source, install project-locally, record provenance, and require explicit approval for installation and updates.

## Implemented changes

- `.codex/hooks/codex_hook.py`: guarded common read-only commands and preserved mutation handling for write options.
- `tests/test_template.py`: regression coverage for inspection commands and dangerous options.
- `AGENTS.md`: compact Build autonomy and escalation contract.
- `.agents/skills/brainstorm/SKILL.md`, `.agents/skills/write-plan/SKILL.md`, `.agents/skills/execute-plan/SKILL.md`: current-task authorization can carry through internal phases without an extra approval turn.
- `docs/codex.md`: Explore/Build/Ship model, self-review, decision visibility, and external-skill trust boundary.
- `docs/upgrading.md`: migration note for downstream repositories.
- `TEMPLATE_VERSION` and `.codexicon.json`: release marker `2.7.0`.

## Rollout and rollback

Roll out the hook and its tests together, then merge the guidance and skill changes after comparing local policy. Existing repositories can adopt the changes selectively using the repository-local manager or the migration note in `docs/upgrading.md`; no state migration is required.

Rollback is file-level and reversible: restore the prior hook and matching tests, restore the prior guidance/skill files if desired, and restore the prior version marker. Do not overwrite project-owned identity, commands, security ownership, or accepted decisions during downstream adoption.

## Remaining risks and follow-up

- Run a live multi-task Codex benchmark when a transcript/tool-call harness is available; measure latency, interruptions, verification reruns, quality after first implementation, and quality after refinement.
- If false-positive invalidation remains material, design a check-specific repository fingerprint with explicit treatment for untracked, ignored, generated, non-Git, Windows, and concurrent-session state before changing the hook contract.
- If external skill demand is demonstrated, specify and review a project-local provenance lock before implementing discovery or installation.
