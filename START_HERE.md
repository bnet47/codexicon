# Starting a project with Codexicon

Codexicon begins deliberately unconfigured. The best results come from defining the project before selecting a stack, then asking Codex to build one small verified slice at a time.

For a visual overview of the lifecycle, workflow routing, token model, and safety boundaries, open [the interactive template playbook](docs/repo-template-playbook.html).

## What you need

- Codex opened at the repository root.
- Python 3.10 or newer for the template validation and hooks.
- Git when you want branches, worktrees, commits, CI, or pull requests.
- A short description of the problem, intended user, outcome, and real constraints.

Do not add provider accounts, API keys, databases, or deployment services before the project actually needs them.

## 1. Create a clean project copy

Use your normal template or repository creation flow. For a new local project, start with a fresh Git repository rather than retaining template history. Git initialization, remotes, commits, and pushes are explicit actions: ask Codex for them when wanted.

Open the resulting directory in Codex from its root. Review and trust `.codex/config.toml` and `.codex/hooks.json`; project configuration and hooks do not run until the project is trusted.

Before changing the template, confirm its baseline:

```bash
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
```

On native Windows:

```powershell
./scripts/lint.ps1
./scripts/test.ps1
./scripts/security.ps1
```

All three commands should pass. At this stage they validate the template and its Codex safeguards, not an application stack.

## 2. Define the project before the technology

Invoke:

```text
$discover
```

Codex will clarify only what is unresolved and save an approved charter under `agent_docs/briefs/`. Be ready to describe:

- the problem or cost today;
- the specific person or role affected;
- the observable outcome the project should create;
- constraints such as platform, deadline, existing systems, compliance, or budget;
- explicit non-goals;
- evidence that would show the project is useful.

A strong starting prompt is:

```text
$discover

We need to solve [problem] for [user]. Success means [observable outcome].
Known constraints: [constraints]. Out of scope: [non-goals].
```

Avoid choosing a framework or database in this step unless an existing organizational constraint has already chosen it.

## 3. Configure the real development environment

After approving the charter, invoke:

```text
$init
```

Initialization should:

1. select the smallest suitable stack;
2. fill the project identity in `AGENTS.md`, `README.md`, and `agent_docs/`;
3. create the real source and test structure;
4. replace the template command stubs with working setup, development, lint, and test commands;
5. replace template CI with stack-specific CI;
6. create `.env.example` only if real environment variables are required, using names and non-secret examples only;
7. update `.gitignore` for actual generated output;
8. complete the applicable security and operations baseline in `agent_docs/`;
9. preserve the credential scan while adding stack-specific dependency or image audits;
10. verify setup on the supported developer platforms.

When Git is enabled, inspect any existing hooks path before asking Codex to run `scripts/install-git-hooks.sh` (or `.ps1`). The tracked hooks scan before commit and run full lint, tests, and security before push.

Tell Codex about fixed technology, hosting, runtime, or compatibility constraints before `$init`. If you have no stack preference, let it recommend the smallest reversible option. Use `$architecture-review` before accepting a database, framework, ownership boundary, or deployment choice that would be expensive to reverse.

Initialization does not authorize a commit, remote, push, or deployment. State those requests explicitly if wanted.

## 4. Build the first useful slice

Start with the smallest complete behavior that proves value. Describe the outcome and done conditions rather than prescribing every edit.

Choose only the workflow the change needs:

| Situation | Workflow |
|---|---|
| Clear change affecting a few files | `$quick` |
| Feature behavior or approach is genuinely uncertain | `$brainstorm` |
| Precise requirement needs a durable contract | `$spec` |
| Approved multi-step spec needs task decomposition | `$write-plan` |
| Approved plan contains independent implementation tasks | `$execute-plan` |
| Reproducible failure has an unknown cause | `$investigate` |
| Expensive-to-reverse technical choice | `$architecture-review` |
| App or website experience needs intentional visual execution | `$design-experience` |
| Positioning, messaging, campaign, or launch work | `$create-marketing` |
| Customer-facing work needs an anti-slop quality gate | `$review-creative` |
| Current changes need an independent check | `$review` |
| First launch or material production change needs an evidence gate | `$production-readiness` |
| Direction is drifting or repeatedly blocked | `$retro` |

Example:

```text
$quick Add the first health endpoint.

Done when it returns the documented response, has a focused test, and the
repository lint and test commands pass. Do not add deployment yet.
```

Codex can select these workflows automatically. Name a skill when you want to force that exact workflow.

### Customer-facing execution

For an app or website, establish real users, tasks, content, brand constraints, and success evidence before asking for visual polish. Use:

```text
$design-experience Build the agreed customer flow. Inspect the existing product,
shape the information and states before styling, then verify rendered mobile and
desktop output. Use real evidence and do not invent customer proof.
```

For positioning, copy, a launch, or a campaign, provide the audience, offer, objective, approved proof, channel, action, and measurement constraints. Use:

```text
$create-marketing Create the agreed assets. Separate sourced facts, assumptions,
and unknowns; adapt the central argument to each channel; do not publish or send.
```

Before release, run `$review-creative` independently. It checks rendered behavior and accessibility, claim integrity, brand and channel fit, and generic generated patterns. It reports findings but does not edit, publish, send, activate spend, or replace the engineering-focused `$review`.

## 5. Give Codex efficient task prompts

For most development work, a useful prompt contains four things:

```text
Outcome: [observable result]
Done when: [acceptance evidence]
Constraints: [compatibility, security, scope, or platform limits]
Authority: [whether Git, deployment, or external writes are allowed]
```

You normally do not need to paste repository files or repeat the rules in `AGENTS.md`. Codex should inspect only the relevant paths and follow the existing context map.

When correcting work, provide the failing behavior, exact error, or changed requirement. Avoid pasting entire logs when the decisive excerpt is enough.

## 6. Keep token use low without weakening development

- Invoke `$concise` when you want shorter progress updates and final responses.
- Keep technical reasoning, code, commands, errors, tests, security evidence, and review findings exact.
- Ask for targeted inspection instead of repository-wide summaries.
- Do not require a spec, plan, ADR, checkpoint, or subagent for a small clear change.
- Use subagents only for concrete independent work where parallelism or context isolation offsets their extra tokens.
- Keep durable repository rules in `AGENTS.md`; put details in skills or `agent_docs/` so they load only when relevant.
- Do not lower reasoning effort, verification depth, tool-output limits, or compaction thresholds merely to reduce tokens.

## 7. Work with project documentation

Use each location for one kind of truth:

| Information | Location |
|---|---|
| Durable commands, boundaries, and workflow routing | `AGENTS.md` |
| Current system shape and integrations | `agent_docs/architecture.md` |
| Entities, ownership, and persistence | `agent_docs/data-model.md` |
| Project-specific conventions | `agent_docs/conventions.md` |
| Security boundaries, threats, privacy, and assurance | `agent_docs/security.md` |
| Operations, recovery, observability, and release safety | `agent_docs/operations.md` |
| Accepted technical decisions | `agent_docs/decisions/` |
| Approved charters and feature specs | `agent_docs/briefs/` |
| Implementation plans | `agent_docs/plans/` |
| Requested handoff checkpoints and retrospectives | `agent_docs/sessions/` |
| Codex configuration and extension details | `docs/codex.md` |

Do not put temporary task state or long explanations in `AGENTS.md`; it is loaded into every task. Do not treat `.codex-state/` as project memory—it is ephemeral verification state.

## 8. Verify and ship deliberately

During development, run the narrowest focused check first. Before shipping code or configuration, run the canonical full checks:

```bash
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
```

Then use `$review` for an acceptance-focused review when risk warrants it.

Before a first production launch or a material production change, invoke:

```text
$production-readiness
```

It returns READY, READY WITH ACCEPTED RISK, or NOT READY from current evidence. Unknown recovery, authorization, rollback, or ownership is a gap; only the accountable human can accept a named residual risk.

Git authority is intentionally granular:

- “commit” authorizes a local commit only;
- “push” authorizes a commit when needed and a push from a non-protected branch;
- “open a PR” or “ship” authorizes verification, commit, push, and a draft pull request;
- none of these authorizes deployment.

Use `$ship` only after stating the action you want. Production deployment and writes to external systems always require separate explicit authorization.

## Project-start checklist

- [ ] Repository opened at its root in Codex.
- [ ] Project configuration and hooks reviewed and trusted.
- [ ] Template lint and tests pass.
- [ ] Fresh Git repository or intended existing repository confirmed.
- [ ] `$discover` charter approved.
- [ ] `$init` replaced all template command stubs.
- [ ] Project identity and ownership placeholders removed.
- [ ] Real CI runs the same lint and test contract as local development.
- [ ] Canonical security scan passes locally and in CI.
- [ ] Repository Git hooks are installed or an existing equivalent is documented.
- [ ] Environment variables documented only when required; no credentials tracked.
- [ ] Security and operations owners/boundaries are documented for the actual project.
- [ ] First slice has observable acceptance criteria.
- [ ] Git, external-write, and deployment authority stated explicitly.
- [ ] `$production-readiness` passes before launch.

After this checklist, use ordinary outcome-based prompts and let the repository route Codex to the smallest workflow that fits the work.
