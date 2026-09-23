# Exploration and Implementation Proposal: Adaptive Intelligence Routing

**Spec:** [SPEC.md](../../SPEC.md)
**Date:** 2026-09-23
**Status:** Accepted for implementation; owner authorization is recorded in the 2026-09-23 task request

## Decision summary

Codexicon should not become a general multi-agent runtime. Most of the proposed
lead → worker → reviewer shape already exists as bounded guidance, project-scoped
agent profiles, a validated capability policy, a sequential writer rule, selective
read-only review, and an evidence-bearing task queue.

The smallest justified evolution is an **opt-in routing policy extension** to the
existing capability layer, paired with a structured dispatch contract and honest
routing evidence. It should be advisory and fail closed when the client cannot
prove the requested model or reasoning setting. It should not add a daemon, a
second task engine, recursive orchestration, concurrent writers, or durable model
names.

The proposed default remains direct primary-agent implementation. A worker is
eligible only when the task contract explicitly proves that it is bounded and
independently verifiable. A worker write adds a review trigger for non-trivial or
risky work, but trivial deterministic work may use the existing selective-review
exemption. Escalation stays inside the existing `max_iterations`,
`max_failed_attempts`, and `max_review_cycles` budgets.

The recommendation is experimental until paired evaluations show a material
improvement in accepted-task quality or cost per accepted task. Current Codex
documentation supports custom agents and model/effort configuration, but the
repository has no reliable live-client evidence that effective subagent model and
reasoning settings are always observable or honored across clients.

## 1. Current-state architecture

`agent_docs/architecture.md` is still a placeholder, so this map is derived from
the active contract, skills, profiles, scripts, tests, and ADRs.

```text
Human request
    |
    v
SPEC.md ------------------------ durable requirement contract
    |
    v
TASKS.md ----------------------- authoritative queue, dependencies, evidence
    |
    v
Primary Build agent ------------ decomposition, scope, writing, integration,
    |                             final verification and acceptance
    +--> .codex/agents/researcher.toml      read-only external research
    +--> .codex/agents/github-researcher.toml read-only upstream research
    +--> .codex/agents/implementer.toml      one bounded sequential writer
    +--> .codex/agents/reviewer.toml         read-only independent review
    |
    v
.codex/capabilities.toml ------- validated profiles, budgets, review triggers,
                                  verification tiers, human-owned escalation
    |
    v
scripts/codexicon.py ------------ spec/task/capability/evidence validation
scripts/agent_loop_eval.py ------ deterministic scenarios and paired-trial shell
```

### Existing mechanisms that overlap

| Proposed capability | Already present | Remaining distinction |
|---|---|---|
| Lead owns intent, decomposition, integration, acceptance | `AGENTS.md`, `$autonomous-build`, `$execute-plan`, ADR-003/004 | No semantic routing policy names this ownership as a tier contract. |
| Bounded worker | `implementer.toml`; one sequential writer in the current checkout | Worker eligibility is described in prose, not represented as an explicit policy decision. |
| Independent reviewer | `reviewer.toml`; selective triggers from risk, changed files, public API, security, architecture, and test complexity | A delegated lower-tier write is not itself a routing/review evidence field. |
| Structured handoff | `$execute-plan` requires exact task text, global constraints, allowed files, dependency state, verification, and side-effect authorization | No single named dispatch contract includes risk signals, eligibility, escalation, and routing evidence. |
| Bounded refinement and retry control | Capability profiles define `max_iterations`, `max_review_cycles`, `max_failed_attempts`, and `max_minutes`; the skills define stop conditions | No capability-aware model escalation semantics; retry and escalation are currently judgment-only. |
| Authority boundaries | Capability policy denies Git, deployment, credentials, external writes, publication, and runtime authority; Build is Git-free | Routing must not imply authority or turn a worker into a new owner. |
| Evidence-first completion | Task receipts validate acceptance IDs, commands, source/contract digests, timestamps, and review dispositions | The receipt normalizer currently drops unknown fields, so routing provenance cannot yet be retained as a validated object. |
| No recursive swarm | Project guidance prohibits a second runtime and concurrent writers | Codex itself can expose subagent spawning; Codexicon currently has no explicit no-recursion policy field. |

### Current decision history

- ADR-003 established selective bounded loops and trusted read-only research.
- ADR-004 superseded its worktree-writer sentence and made the supported Build
  policy one sequential writer in the shared checkout.
- ADR-005 established `.codex/capabilities.toml` as validated guidance, not a
  runtime, daemon, scheduler, or authority grant.
- The active SPEC already requires selective review, bounded refinement, honest
  capability evidence, and direct-versus-Codexicon evaluation. It also explicitly
  forbids concurrent writers, forced model identity, and a second task engine.

## 2. External research

Research was performed 2026-09-23. Sources below are separated into official
documentation, repository source, vendor claims, and community reports.

### Current Codex behavior

| Fact | Classification | Evidence and implication |
|---|---|---|
| Local Codex supports project-scoped custom agents in `.codex/agents/`; each role requires `name`, `description`, and `developer_instructions`, and may set `model`, `model_reasoning_effort`, `sandbox_mode`, MCP servers, and skills configuration. | Documented | [Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents), accessed 2026-09-23. This is enough to bind user-selected roles, but not a reason to duplicate role files in a new routing subsystem. |
| Resolution is layered: explicit spawn values, then `[agents]` defaults, then the parent; a custom agent file can take precedence for model/effort. Omitted settings inherit, including parent runtime sandbox/approval overrides. | Documented | [Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents), accessed 2026-09-23. A routing policy can request a role, but must treat effective settings as runtime evidence rather than assume the role file won. |
| `[agents]` exposes enabled state, concurrent-thread cap, default subagent model, and default subagent reasoning effort. | Documented | [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), accessed 2026-09-23. Project policy should not overwrite user-controlled model bindings. |
| Project-local config cannot override several machine-local provider, auth, host-owned metadata, notification, profile-selection, and telemetry keys; untrusted projects skip project-scoped `.codex/` layers. | Documented | [Codex configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference), accessed 2026-09-23. Portability and trust level must be part of the routing risk model. |
| Subagent workflows have separate agent threads/contexts and are intended for independent, bounded work; official guidance warns that they consume more tokens and are less suitable for ordered steps or shared mutable state. | Documented | [Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents) and [OpenAI Responses multi-agent guidance](https://developers.openai.com/api/docs/guides/responses-multi-agent), accessed 2026-09-23. This supports shallow selective delegation, not mandatory delegation. |
| The OpenAI Responses multi-agent API limits concurrent subagents but imposes no fixed tree-depth or total-subagent limit; subagents share the request’s model/tools in that API. | Documented, API-specific | [Responses multi-agent limitations](https://developers.openai.com/api/docs/guides/responses-multi-agent), accessed 2026-09-23. It validates Codexicon’s no-recursion default because a client-side concurrency cap is not a topology bound. |
| Agents API observability includes best-effort usage and `subagent_id`, but usage may be null or change; command attribution requires retrieving the turn. | Documented, API-specific | [Agents API observability](https://developers.openai.com/api/docs/guides/agents-api/observability), accessed 2026-09-23. Codexicon must not fabricate token savings or model identity when the active client does not expose them. |
| The current Codex source schema includes `default_subagent_model`, `default_subagent_reasoning_effort`, custom roles, and a V1 `max_depth` field described as ignored by V2. | Repository source | [OpenAI Codex config source](https://github.com/openai/codex/blob/main/codex-rs/config/src/config_toml.rs), observed 2026-09-23. This is useful for compatibility analysis, not a stable promise that every client exposes the same controls. |
| Current Codex docs say custom-agent authoring/configuration may evolve as it matures. | Documented limitation | [Codex subagents documentation](https://learn.chatgpt.com/docs/agent-configuration/subagents), accessed 2026-09-23. Durable Codexicon templates should bind semantic roles, not assume a permanent custom-agent schema. |

### Observed or community-reported behavior

The repository’s own live evaluation record is explicit: the 2026-09-11 CLI
smoke attempt timed out, the guided arm was not started, and model, token, cost,
tool-call, intervention, and client compatibility fields remain unmeasured. See
`docs/evals/live-agent-results-2026-09-11.md` and
`docs/evals/capability-matrix.md`. This is the only local live-client evidence
available here, and it does not establish routing behavior.

The following are useful warnings, not reliable product contracts:

- [Open Codex issue #34370](https://github.com/openai/codex/issues/34370), opened
  2026-07-20, reports requested medium effort being observed as high in a desktop
  subagent. It demonstrates why a requested value and an effective value must be
  separate fields; it does not prove the bug is universal or current.
- [Open Codex issue #32504](https://github.com/openai/codex/issues/32504), opened
  2026-07-12, reports missing effective model/effort fields in a MultiAgentV2
  canonical activity surface. It suggests telemetry can be incomplete even when
  a runtime knows the values; it is community evidence, not an API guarantee.
- [Open Codex issue #30966](https://github.com/openai/codex/issues/30966), opened
  2026-07-03, reports context rediscovery and weak handoffs when a child receives
  too little parent context. This supports a minimum-sufficient dispatch brief,
  not full-history inheritance.
- [Open Codex issue #46023](https://github.com/openai/codex/issues/46023), opened
  in September 2026, describes an unbounded reviewer/implementer loop with large
  repeated cached context and no task-wide circuit breaker. The report is not an
  independent benchmark, but it is a concrete failure mode aligned with
  Codexicon’s existing bounded budgets.

### Comparable architectures

| System/pattern | Demonstrated mechanism | Failure mode or boundary | Reusable lesson |
|---|---|---|---|
| Devin Fusion | [Devin CLI](https://devin.ai/cli), accessed 2026-09-23, describes a frontier lead making decisions while a cheaper sidekick handles exploration, file reads, and tests; [Cognition’s 2026-08-31 post](https://devin.ai/blog/fable-5-1) reports vendor benchmark/cost claims. | Claims are vendor-specific, benchmark-dependent, and not evidence for Codexicon’s local clients. A compound harness also carries context, provider, and accounting complexity. | The useful primitive is role separation plus cost-per-accepted-task measurement, not copying the product. |
| OpenAI hosted/Responses multi-agent | Official APIs provide root coordination, independent subagent contexts, bounded concurrency, and consolidated results. | The documented API has no fixed tree-depth/total-agent limit and warns that parallelism increases tokens or hurts ordered/shared-state work. | Keep the topology shallow, use only independent work, and bound review/attempts in Codexicon policy. |
| Relay | [Relay](https://www.relaydev.ai/), accessed 2026-09-23, positions a vendor-neutral control plane around inline policy, interdiction, halt/reroute, recovery, and audit trails. | This is an operational control plane, not a lightweight local template; adopting it would add a runtime and authority surface Codexicon explicitly rejects. | Preserve the policy/audit insight in local evidence, but do not add a daemon or third-party control plane. |
| Agent Orchestrator | [Augani/agent-orchestrator](https://github.com/Augani/agent-orchestrator), observed 2026-09-23, advocates compact context capsules, one writer per workspace, 2–4 useful roles, and denying nested workers. | Community project; its claims and traces are not an independent Codexicon evaluation. A separate durable control plane would duplicate TASKS/evidence ownership. | Compact handoffs, one writer, shallow roles, and no recursion are strong design signals already compatible with Codexicon. |

## 3. Gap analysis

### Orchestration gaps

1. Codexicon has roles but no explicit semantic contract for which role owns
   intent, decomposition, implementation, review, and acceptance.
2. The handoff requirements are distributed across skills and the implementer
   profile instead of named as one minimum-sufficient dispatch contract.
3. Recursion is not a Codexicon policy decision. Current client capabilities can
   allow a child to spawn children, so instructions alone need an explicit
   `max_depth = 1` policy intent and a fail-closed/unverified outcome.

### Routing gaps

1. There is no worker-eligibility gate. Changed-file count is a review trigger,
   not a complexity classifier, and must not become one.
2. The capability policy has human-boundary escalation flags but no
   evidence-based capability escalation semantics.
3. The template intentionally leaves model choice user-controlled and does not
   map semantic tiers to concrete models. That is correct, but the policy needs a
   place to express role/tier intent without pinning names.

### Observability gaps

1. `validate_task_evidence` normalizes a fixed receipt and discards unknown
   fields. A routing envelope cannot be retained honestly without an additive
   schema change.
2. The local live evaluation does not expose reliable model, effort, token, cost,
   or client completion telemetry.
3. Current Codex docs establish requested/configured model and effort controls,
   but not a universal Codexicon-readable effective-runtime receipt across CLI,
   desktop, and IDE surfaces.

### Evaluation gaps

1. Existing deterministic fixtures measure policy and repository behavior, not
   model routing quality.
2. Existing live evaluation planned a direct/guided pair but did not complete;
   there is no direct/worker/reviewer comparison.
3. No current benchmark measures whether review findings change acceptance,
   whether cheaper workers require more retries, or whether routing reduces cost
   per accepted task.

## 4. Options considered

| Option | Complexity | Reliability | Token efficiency | Maintainability / portability | Observability | Main failure mode |
|---|---|---|---|---|---|---|
| A. Prompt/documentation-only routing | Low | Low-to-medium; depends on model following prose | Potentially good, but unmeasured | Excellent and portable | Low; no structured receipt | Silent policy drift, worker overreach, unsupported model claims, repeated retries |
| B. Additive capability-policy routing plus structured handoff/evidence | Medium | Medium-to-high for boundaries; still client-dependent for execution | Good when eligibility is strict and review is selective | Good; reuses current policy, skills, profiles, TASKS, and tests | Medium; can honestly distinguish configured from observed | Guidance may be ignored or client routing may be unavailable; no runtime enforcement |
| C. Programmatic runtime orchestrator/daemon | High | Potentially high if fully built, but large untested surface | Potentially good, with orchestration overhead | Poor fit; duplicates queue, budgets, recovery, and authority logic | Potentially high, but only after building a new telemetry/control plane | Second task engine, authority drift, recovery bugs, recursive loops, new persistence/runtime failures |

Option B is recommended, but as an opt-in experiment. Option A is too weak to
make routing evidence-first. Option C violates the current no-daemon/no-second-
engine boundary and is not justified by existing measurements.

## 5. Recommended architecture

```text
Human request
     |
     v
Primary / lead
  understands intent, resolves decisions, writes SPEC/TASKS,
  decomposes, owns authority and final acceptance
     |
     v
Explicit task contract + policy gate
  all eligibility predicates must pass; otherwise primary implements
     |
     +-- ineligible/risky/ambiguous --> primary implementation
     |
     +-- eligible --> one worker dispatch with minimum-sufficient context
                         |
                         v
                  focused checks + changed-path inspection
                         |
                         +-- trivial deterministic exemption --> lead accepts
                         |
                         +-- configured trigger --> read-only reviewer
                                                        |
                              PASS ---------------------+
                                |
                                v
                       primary integrates and accepts

  failed check/reviewer finding
          |
          v
  one targeted correction within current budgets
          |
          +-- pass --> reviewer/final acceptance as configured
          +-- fail, ambiguity, scope drift, or authority boundary
                     --> primary takes over / replans
          +-- optional stronger-tier request only when binding is available;
              otherwise record configured_unverified and do not claim escalation
```

The runtime topology remains shallow:

```text
Primary
├── researcher/explorer (read-only, optional)
├── implementer (one sequential writer, optional)
└── reviewer (read-only, optional)
```

No worker or reviewer should spawn another subagent. The primary may request a
separate read-only lane only when the existing engineering-loop rules justify it.
This is an instruction-level policy until a client offers a reliable enforcement
hook; an inability to enforce it must be visible as a limitation.

## 6. Routing policy

### Primary-owned responsibilities

The primary owns by default and should not delegate without an explicit,
reviewable task contract:

- requirement interpretation and acceptance meaning;
- architecture, schema, data-model, security, and material product decisions;
- decomposition, dependency ordering, and scope changes;
- authority decisions, credentials, external writes, Git, deployment,
  publication, migrations, and destructive actions;
- final integration, evidence interpretation, review disposition, and acceptance;
- deciding whether a failed worker should be corrected, escalated, replanned, or
  blocked.

These responsibilities are hard to delegate because an incorrect decision can
make every downstream worker produce a locally coherent but globally wrong patch.

### Smallest practical worker-eligibility gate

Eligibility is an all-of predicate, not a score and not a file-count heuristic.
`worker_eligible` is false unless the dispatch contract explicitly proves every
condition below:

1. The task has a stable ID, one objective, requirement/acceptance trace, known
   allowed files, forbidden scope, dependencies, and runnable verification.
2. Acceptance criteria are explicit and independently checkable.
3. No unresolved product, architecture, schema/data, security, or dependency
   decision is required.
4. The task does not expand authority and does not involve credentials,
   destructive actions, Git/publication/deployment, production, migrations, or
   external writes.
5. The task is understandable from the contract, declared files, and referenced
   repository sources without the lead conversation.
6. The task has one sequential writer and no overlapping active writer.
7. A failed check has a bounded recovery path and a clear escalation condition.
8. The selected worker role is compatible with the required sandbox and tools,
   subject to runtime verification.

If any predicate is unknown, the primary implements or asks for context. A task
may be small and still ineligible; a multi-file task may be eligible if every
predicate is explicit and verification is deterministic.

### Semantic roles and tiers

Roles and tiers are separate:

| Semantic role | Responsibility | Minimum tier intent | Concrete binding |
|---|---|---|---|
| `lead` | intent, planning, decomposition, integration, acceptance | `frontier` or user-selected equivalent | primary session; user/runtime controlled |
| `implementer` | one bounded patch and focused verification | `efficient` when eligible | `.codex/agents/implementer.toml` or user/runtime override |
| `reviewer` | independent read-only judgment against requirement, contract, diff, and evidence | `frontier` or stronger than the worker | `.codex/agents/reviewer.toml` or user/runtime override |

The policy records semantic tier intent only. It must not put current commercial
model names in durable templates. Concrete model and effort bindings remain the
user/runtime responsibility in Codex configuration and role files. If a stronger
reviewer or escalation target cannot be proved, the lead retains acceptance.

### Review triggers

Add delegated implementation as a configurable trigger, but preserve the
existing low-risk exemption. Recommended decision order:

1. Always run the worker’s declared focused verification.
2. Require independent read-only review when the worker write is non-trivial,
   any existing risk/signal trigger matches, or the configured policy says every
   delegated write must be reviewed.
3. Permit exemption only when the change is low-risk, below the configured
   changed-file threshold, fully covered by deterministic acceptance checks, and
   no public API/security/architecture/test-complexity signal exists.
4. If the worker’s lower tier is only configured but not observed, do not silently
   treat the task as safely reviewed; use the configured policy and record the
   routing status.

The reviewer receives the original requirement, task contract, actual changed
paths/diff, and verification evidence. The worker’s explanation is context only,
never the acceptance source. The reviewer remains read-only and returns stable
finding IDs with the existing dispositions.

### Escalation and budgets

Escalation is a bounded decision within the existing task, not a new queue:

- A failed focused check gets one targeted worker correction when the failure is
  local, understood, and within scope.
- A reviewer finding gets one correction round under the existing
  `max_review_cycles` budget.
- Repeated focused failure, unresolved ambiguity, scope expansion, an authority
  boundary, or a reviewer finding that needs a design decision returns control to
  the primary.
- An optional stronger-tier implementation request is allowed only after the
  primary classifies the failure and the requested binding is available. If the
  effective model/effort cannot be observed, record `configured_unverified`; do
  not claim that a stronger model ran.
- No extra `max_escalations` or retry engine is introduced. Existing
  `max_iterations`, `max_failed_attempts`, `max_review_cycles`, and `max_minutes`
  remain the hard guidance ceiling for the whole task.
- Exhaustion, plateau, repeated failure, or a human boundary leaves the task
  incomplete or blocked; it never converts an unverified worker result into
  acceptance.

### Recursion policy

Default `max_depth = 1` means the primary may delegate a leaf worker/reviewer,
but a worker/reviewer may not delegate. Because the client may expose recursion
without a project-enforceable hard stop, the policy and role instructions must
say `do not spawn subagents`, and the evidence model must record when the client
cannot verify the topology. Any observed child-of-child activity is a routing
failure and should return control to the primary.

## 7. Evidence model

Add an optional, validated routing envelope to task completion evidence rather
than creating a second receipt store. The envelope should be small and should not
persist raw conversations or secrets:

```json
{
  "routing": {
    "schema_version": 1,
    "requested_role": "implementer",
    "requested_tier": "efficient",
    "requested_model": null,
    "requested_effort": null,
    "observed_role": "implementer",
    "observed_tier": null,
    "observed_model": null,
    "observed_effort": null,
    "status": "configured_unverified",
    "evidence_source": "project_config_only",
    "max_depth": 1
  }
}
```

Allowed status values:

- `observed`: the client/runtime exposed the effective values used;
- `configured_unverified`: the role/config/request was known, but the effective
  runtime was not independently exposed;
- `unavailable`: the requested role/tier/model/effort could not be dispatched;
- `mismatched`: observed runtime values differ from the requested policy.

`requested_*` fields describe intent. `observed_*` fields require direct runtime
evidence. A model name in a TOML file is not an observed model. A worker’s claim
about its own model is not sufficient. Token, cost, latency, and cache fields are
recorded only when the client exposes reliable values; otherwise they remain
`unmeasured` in evaluation records.

The normalizer should preserve the routing envelope only after validating its
shape, status, task association, and no-authority semantics. Existing receipts
without `routing` remain valid and normalize exactly as before.

## 8. Compatibility and migration

- Existing `.codex/config.toml`, `.codex/agents/*.toml`, `SPEC.md`, and `TASKS.md`
  remain valid when routing is absent or disabled.
- Add routing under `.codex/capabilities.toml`, because it is workflow policy
  alongside review, budgets, verification, and escalation. Do not add a second
  policy file or put semantic policy in Codex’s runtime config.
- Model names and provider settings remain user-controlled. The template should
  not set `default_subagent_model` or `default_subagent_reasoning_effort`.
- Use an additive capability schema revision or an explicitly optional routing
  section with a compatibility parser. Old policy files must continue to load;
  malformed routing must fail closed rather than silently disabling boundaries.
- Existing task rows need not gain new columns in the first implementation. The
  dispatch contract can be derived from the existing row plus a bounded brief,
  while the optional routing envelope rides in existing task evidence.
- Existing `max_iterations`, `max_failed_attempts`, and `max_review_cycles` keep
  their meanings. Routing consumes those budgets; it does not redefine them.
- If a client lacks role selection, effective model/effort metadata, or recursion
  control, the routed mode remains experimental and records the limitation rather
  than pretending compatibility.

## 9. Exact implementation surface

The first implementation slice should be additive and opt-in. Likely paths are:

| Path | Likely change | Required? |
|---|---|---|
| `.codex/capabilities.toml` | Optional routing policy examples or selected-profile routing defaults, with no concrete model names | Yes for policy slice |
| `scripts/codexicon.py` | Parse/validate routing keys; preserve/validate optional evidence envelope; report JSON | Yes for executable policy/evidence |
| `tests/test_codexicon.py` | Schema, backward compatibility, invalid-policy, evidence, and status tests | Yes |
| `.agents/skills/autonomous-build/SKILL.md` | Eligibility gate, routing/escalation semantics, no-recursion and budget reuse | Yes |
| `.agents/skills/execute-plan/SKILL.md` | Minimum-sufficient dispatch contract and explicit handoff contents | Likely |
| `.codex/agents/implementer.toml` | Worker contract and no-recursion instruction; retain user model control | Likely |
| `.codex/agents/reviewer.toml` | Reviewer input order and delegated-write trigger; remain read-only | Likely |
| `docs/capabilities.md` | Public policy and evidence semantics | Yes |
| `docs/agent-patterns.md` | Shallow routing diagram, handoff and failure patterns | Likely |
| `docs/build-contracts.md` | Receipt/routing compatibility and authority wording | If evidence changes |
| `tests/test_template.py` | Cross-file guidance consistency and template allowlist checks | Yes if template guidance changes |
| `scripts/agent_loop_eval.py` | Optional routed arm, routing fields, and paired metrics | Evaluation slice |
| `tests/test_agent_loop_eval.py`, `tests/test_live_agent_eval.py` | Deterministic routed scenarios and honest unavailable telemetry | Evaluation slice |
| `docs/evals/agent-loop-benchmark.md`, `docs/evals/capability-matrix.md` | Protocol, denominators, client/version/evidence status | Evaluation slice |
| `SPEC.md` and `TASKS.md` | Amend contract and append proposed implementation tasks when implementation is authorized | First implementation task, not this exploration |
| `.codex/config.toml` | No functional change recommended; preserve user-controlled model/provider behavior | No |

No daemon, background service, runtime scheduler, new task database, worktree
writer, or external orchestration dependency is in scope.

## 10. Test and evaluation plan

### Deterministic tests

1. Routing absent: current capability policy, task receipts, scaffold, and all
   existing tests remain green.
2. Valid routing: semantic roles, tiers, review trigger, depth, and bounded
   escalation values parse and appear in stable human/JSON output.
3. Invalid routing: unknown keys, model names in the durable policy, zero/negative
   limits, depth greater than one, unknown statuses, and authority-expanding
   fields fail with line-aware diagnostics.
4. Eligibility: each of the eight negative predicates routes to primary; a fully
   specified deterministic task is worker-eligible; file count alone never changes
   eligibility.
5. Evidence: all four routing statuses round-trip; requested and observed values
   cannot be conflated; old evidence remains compatible; mismatched evidence does
   not satisfy an observed-routing assertion.
6. Review: delegated non-trivial work triggers the existing read-only reviewer;
   trivial deterministic work can use the explicit exemption; reviewer findings
   retain stable dispositions.
7. Escalation: one correction consumes the existing budget; repeated failure,
   ambiguity, scope drift, and authority expansion return to the primary without
   creating a new task engine.
8. Recursion: role guidance and policy validation reject configured recursive
   workers; observed-unavailable enforcement is recorded as a limitation.
9. Template synchronization: `validate_template.py`, playbook rendering, and
   capability references remain aligned.

### Paired live-agent experiment

Run only after deterministic checks and an explicit opt-in. Compare:

- **Baseline:** one strong primary performs planning, implementation,
  verification, and review.
- **Routed:** the same strong lead creates the same task contract, an eligible
  worker implements, focused checks run, and a strong read-only reviewer or lead
  accepts/escalates.

Hold constant repository revision, task text, acceptance criteria, authority,
environment, verification commands, and time budget. Start with at least 20
paired tasks across documentation correction, small behavior fix, multi-file
feature, research-heavy task, and high-risk task classes; repeat pairs before
changing defaults. Store sanitized raw evidence outside the repository.

Measure per arm and per task:

- acceptance and regression result;
- acceptance criteria passed/missed;
- reviewer findings, severity, and dispositions;
- failed attempts, corrections, escalations, and blocked outcomes;
- unnecessary files changed and scope violations;
- elapsed time and tool-call count when reliable;
- lead/worker/reviewer usage and model identity when directly exposed;
- token/cost/cache usage only when the client reports reliable values;
- user corrections, approval interruptions, and task-trace/integration errors.

Report unavailable values as `unmeasured`, not zero. The decision rule is to
enable routed defaults only if repeated paired runs show no material regression,
bounded coordination, and a meaningful improvement in quality or cost per
accepted task. A single successful worker run is insufficient evidence.

## 11. Risks and unresolved questions

- **Effective model uncertainty:** current Codex docs describe configuration and
  precedence, but not a universal cross-client effective-routing receipt. Until
  observed, model/effort status is `configured_unverified`.
- **Client drift:** custom-agent file format and multi-agent surfaces may evolve;
  keep the project policy semantic and validate only the local contract Codexicon
  owns.
- **Recursion enforcement:** current clients may permit child delegation and may
  not expose a project-local hard stop. No-recursion guidance is necessary but is
  not equivalent to runtime enforcement.
- **Reviewer anchoring:** passing the worker explanation can bias review. Always
  send requirement, contract, diff, and verification first; treat prose as a
  claim.
- **Context overhead:** a worker can cost more than direct execution when it
  re-reads repository guidance or receives oversized history. Use fresh,
  minimum-sufficient briefs and measure total task cost, including the lead.
- **Silent cheap-worker failure:** deterministic checks and selective independent
  review must gate acceptance; a worker report alone is never completion evidence.
- **Retry loops:** a reviewer/implementer loop can burn unbounded tokens even
  with good intentions. Reuse current budgets and require consolidated findings.
- **Authority confusion:** semantic tier must never imply a broader sandbox,
  external-write, Git, deployment, credential, or publication permission.
- **Evaluation availability:** current local live trials timed out and did not
  expose reliable telemetry. No token-savings claim should be made until a
  completed paired run produces trustworthy counts.
- **Open decision:** whether a future Codex client exposes enough effective model,
  effort, and topology metadata to change `configured_unverified` into `observed`
  for default routing. This should be decided from capability-matrix evidence,
  not assumptions.

## 12. Proposed task register

The following is a draft for a later, explicitly authorized implementation. It is
not appended to the active `TASKS.md` by this exploration. The IDs below reserve
the next logical slice; the contract amendment should assign final acceptance IDs
before any implementation task becomes runnable.

### T-029 — Amend the durable contract for opt-in routing

**Depends on:** none
**Parallel-safe with:** none
**Requirements/interfaces:** proposed R-028–R-032; existing R-021, R-023, R-026, R-027
**Files:** `SPEC.md`, `agent_docs/decisions/` only if the recommendation is accepted, `agent_docs/plans/2026-09-23-adaptive-intelligence-routing-plan.md`
**Behavior:** Add explicit requirements for opt-in semantic routing, worker eligibility, shallow topology, routing evidence, and paired evaluation without pinning model names or changing authority.
**Verification:** `python scripts/codexicon.py spec-check`
**Done when:** the active contract traces the approved routing scope and anti-goals, and no existing acceptance/evidence history is discarded.

### T-030 — Add a validated, backwards-compatible routing policy

**Depends on:** T-029
**Parallel-safe with:** none
**Requirements/interfaces:** proposed R-028; existing I-017
**Files:** `.codex/capabilities.toml`, `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/capabilities.md`
**Behavior:** Add optional routing policy with semantic roles/tiers, eligibility mode, delegated-review trigger, `max_depth = 1`, and bounded escalation semantics. Reject model/provider literals in durable policy and preserve all old profiles/files.
**Verification:** `python -m unittest tests.test_codexicon; python scripts/codexicon.py capabilities --json`
**Done when:** valid old and new policies have stable output, malformed/unsafe routing fails closed, and no policy setting grants authority.

### T-031 — Define and enforce the minimum-sufficient dispatch contract

**Depends on:** T-030
**Parallel-safe with:** none
**Requirements/interfaces:** proposed R-029; existing I-018
**Files:** `.agents/skills/autonomous-build/SKILL.md`, `.agents/skills/execute-plan/SKILL.md`, `.codex/agents/implementer.toml`, `.codex/agents/reviewer.toml`, `docs/agent-patterns.md`, `tests/test_template.py`
**Behavior:** Name task ID, trace, objective, allowed/forbidden scope, dependencies, acceptance, verification, risk signals, worker eligibility, escalation conditions, and side-effect ceiling. Require worker/reviewer no-recursion behavior and keep the primary as sole integration owner.
**Verification:** `python -m unittest tests.test_template; python scripts/validate_template.py`
**Done when:** the template contains one consistent handoff contract and no guidance permits concurrent writers or hidden task engines.

### T-032 — Add bounded delegated-review and escalation semantics

**Depends on:** T-030,T-031
**Parallel-safe with:** none
**Requirements/interfaces:** proposed R-030; existing I-018, I-019
**Files:** `.agents/skills/autonomous-build/SKILL.md`, `.agents/skills/review/SKILL.md`, `.codex/agents/reviewer.toml`, `docs/capabilities.md`, tests for template/policy behavior
**Behavior:** Make delegated non-trivial implementation a review trigger, preserve the deterministic trivial exemption, require reviewer input ordering, and reuse existing iteration/review/failure/time budgets for one correction and escalation to the primary.
**Verification:** `python -m unittest tests.test_template tests.test_codexicon`
**Done when:** no route can silently accept a failed worker, create a recursive worker tree, or add a second retry budget.

### T-033 — Preserve honest routing evidence in task receipts

**Depends on:** T-030,T-032
**Parallel-safe with:** none
**Requirements/interfaces:** proposed R-031; existing I-004, I-017
**Files:** `scripts/codexicon.py`, `tests/test_codexicon.py`, `docs/build-contracts.md`, `docs/capabilities.md`
**Behavior:** Validate and retain the optional routing envelope and four statuses; distinguish requested/configured values from observed runtime values; keep old receipts valid and do not record raw prompts or secrets.
**Verification:** `python -m unittest tests.test_codexicon; python scripts/codexicon.py spec-check`
**Done when:** `observed`, `configured_unverified`, `unavailable`, and `mismatched` are unambiguous and completion cannot be upgraded by an unobserved claim.

### T-034 — Extend the evaluation protocol with a routed arm

**Depends on:** T-029,T-033
**Parallel-safe with:** none
**Requirements/interfaces:** proposed R-032; existing I-016, I-020
**Files:** `scripts/agent_loop_eval.py`, `tests/test_agent_loop_eval.py`, `tests/test_live_agent_eval.py`, `docs/evals/agent-loop-benchmark.md`, `docs/evals/capability-matrix.md`
**Behavior:** Add deterministic routed scenarios and an optional paired live arm with the same repository/task/authority inputs. Record acceptance, regressions, findings, retries, escalation, changed-file scope, elapsed time, and reliable telemetry only; mark the rest unmeasured.
**Verification:** `python -m unittest tests.test_agent_loop_eval tests.test_live_agent_eval; python scripts/agent_loop_eval.py --json`
**Done when:** the evaluator can compare baseline and routed evidence without claiming live-client or token savings that were not observed.

### T-035 — Synchronize public guidance and migration notes

**Depends on:** T-030,T-031,T-032,T-033,T-034
**Parallel-safe with:** none; follows final policy semantics
**Requirements/interfaces:** existing I-021; proposed R-028–R-032
**Files:** `README.md`, `START_HERE.md`, `docs/index.md`, `docs/upgrading.md`, `docs/repo-template-playbook.source.html`, generated playbook, `tests/test_template.py`
**Behavior:** Explain opt-in status, semantic tiers, eligibility, evidence limitations, no-recursion policy, and evaluation gates without naming a permanent commercial model or promising runtime enforcement.
**Verification:** `python scripts/render_playbook.py --check; python scripts/validate_template.py; python -m unittest tests.test_template`
**Done when:** selector, skills, roles, docs, and generated playbook agree and fresh starters preserve routing-off compatibility.

## Recommendation

Proceed with T-029 through T-035 as an opt-in experiment. Do not enable adaptive
routing by default, do not pin current model names, and do not add a runtime
orchestrator. The measured decision gate is cost/quality per accepted task with
honest telemetry, not cheaper token price or the number of spawned agents.
