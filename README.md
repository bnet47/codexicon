# Codexicon

[![Template CI](https://github.com/bnet47/codexicon/actions/workflows/ci.yml/badge.svg)](https://github.com/bnet47/codexicon/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)
[![Template version](https://img.shields.io/badge/template-v2.5.0-2563eb.svg)](TEMPLATE_VERSION)

**A production-minded project template for building with Codex.**

Codexicon gives a new repository an explicit path from an idea to verified delivery: durable project guidance, progressively loaded skills, canonical checks, credential safeguards, production-readiness review, and clear authority boundaries for Git, deployment, and external systems.

It is intentionally not an application starter or a framework opinion. You define the product first, then Codex configures the smallest suitable stack for that project.

> Codexicon improves the development process; it does not make an unfinished application production-ready by itself. Each project must supply and verify its own architecture, security, data, operations, and release evidence.

## Why use it

Starting from an empty repository leaves every Codex task to rediscover how the project should be understood, changed, checked, and shipped. Codexicon makes those expectations inspectable and reusable without loading every workflow into every prompt.

- **Start with the problem:** `$discover` defines the user, outcome, constraints, evidence, and non-goals before technology is selected.
- **Configure deliberately:** `$init` turns the template into a real stack with working setup, development, lint, test, security, and CI commands.
- **Use the smallest workflow:** clear changes stay lightweight; ambiguity, architecture, design, marketing, and production risk receive the additional process they need.
- **Keep context lean:** `AGENTS.md` contains durable rules while complete workflows and project facts load only when relevant.
- **Verify with evidence:** humans, Codex, Git hooks, and CI use the same canonical commands.
- **Keep side effects explicit:** commits, pushes, pull requests, deployments, messages, spend, and production changes require clear authority.

## Start in five minutes

### 1. Create a project

On GitHub, select **Use this template**, then **Create a new repository**. For local-only work, copy the directory and omit its `.git` directory.

To add Codexicon to an established repository, keep the repositories separate and inspect first:

```bash
python scripts/codexicon.py inspect /path/to/existing-repository
```

Inspection does not write. After reviewing conflicts and project-owned requirements, explicit `adopt ... --apply` copies only absent managed/merge files and records baseline hashes; it never replaces existing content. See [Adoption, diagnostics, and updates](docs/codex.md#adoption-diagnostics-and-updates).

On Windows, after deliberately staging the adopted files, run `python scripts/codexicon.py sync-git-modes` in the target. This changes only the manifest-declared executable bits already in the Git index, so later POSIX clones can run the tracked hooks and shell entry points.

### 2. Open the new project in Codex

Open Codex at the repository root. Review `AGENTS.md`, `.codex/config.toml`, and `.codex/hooks.json` before trusting the project configuration.

### 3. Verify the template baseline

POSIX:

```bash
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
```

Native Windows:

```powershell
./scripts/lint.ps1
./scripts/test.ps1
./scripts/security.ps1
```

### 4. Define the project

```text
$discover

We need to solve [problem] for [specific user].
Success means [observable outcome].
Constraints: [real constraints].
Out of scope: [non-goals].
```

### 5. Initialize the real stack

After approving the charter created by `$discover`:

```text
$init Configure this repository from the approved charter. Recommend the
smallest suitable stack, replace every template command with a real one,
configure equivalent CI checks, and explain any irreversible choice before
making it. Do not add hosting or deploy anything unless I ask.
```

From this point, use ordinary outcome-based prompts. Codexicon routes the work to the smallest relevant workflow.

## Example: build a sports app

The examples throughout the visual playbook use **Matchday**, a fictional community-football app. A realistic first sequence is:

```text
$discover

We want a mobile-first app for community football supporters to follow
fixtures, live scores, standings, and match alerts. Success means a supporter
can find today's match and understand its current state in under 10 seconds.
Constraints: accessible web app, no betting features, no data provider chosen.
```

```text
$init Configure Matchday from the approved charter. Recommend the smallest
stack for a responsive web app with live-score updates. Create real setup,
development, lint, test, security, and CI commands. Do not initialize hosting
or contact providers.
```

```text
$quick Add the upcoming-fixtures view using the existing API boundary.

Done when each fixture shows competition, teams, kickoff in the viewer's
timezone, and complete loading, empty, and error states. Add focused tests and
run the repository checks. Local code changes only.
```

Before the first real launch:

```text
$production-readiness Audit this release across authorization, tenancy, data,
privacy, dependencies, provider failure, abuse controls, observability,
capacity, backups, restore evidence, migrations, rollback, and incident
ownership. Do not deploy or accept risk on my behalf.
```

## The lifecycle

| Stage | Primary workflow | Evidence before continuing |
|---|---|---|
| Discover | `$discover` | Approved product charter |
| Initialize | `$init` | Working stack, commands, CI, and project identity |
| Build | `$quick`, `$brainstorm`, `$spec`, `$write-plan`, `$execute-plan` | Observable behavior and focused verification |
| Experience | `$design-experience`, `$create-marketing` | Rendered, accessible, evidence-backed customer work |
| Assure | `$review`, `$review-creative`, `$architecture-review` | Actionable findings resolved and canonical checks passing |
| Release | `$production-readiness`, then `$ship` | Readiness verdict plus only the authorized Git action |

The [live visual playbook](https://bnet47.github.io/codexicon/repo-template-playbook.html) explains each stage, every repository skill, example prompts, context loading, safety boundaries, and conservative model floors. Its standalone HTML source remains in `docs/repo-template-playbook.html` for local and offline use.

## Workflow map

| Situation | Use |
|---|---|
| Unconfigured project | `$discover` → `$init` |
| Clear change affecting a few files | `$quick` |
| Unclear feature behavior | `$brainstorm` |
| Precise requirement needing a durable contract | `$spec` |
| Approved multi-step requirement | `$write-plan` → `$execute-plan` when delegation helps |
| Reproducible failure with an unknown cause | `$investigate` |
| Expensive-to-reverse technical choice | `$architecture-review` |
| App or website experience | `$design-experience` |
| Positioning, copy, campaign, or launch asset | `$create-marketing` |
| Customer-facing anti-slop review | `$review-creative` |
| Engineering correctness and regression review | `$review` |
| First launch or major production change | `$production-readiness` |
| Explicit commit, push, or pull-request request | `$ship` |
| Shorter communication with full rigor | `$concise` |

Skills are optional routing tools, not mandatory ceremony. Codex may select them automatically; name one when you want that exact workflow.

## Security and release safeguards

Codexicon uses several independent layers:

1. `AGENTS.md` forbids opening credential-bearing files, dumping environment variables, and inferring external authority.
2. Trusted Codex hooks block common credential stores and require fresh verification after repository writes.
3. `scripts/security.sh` and `scripts/security.ps1` scan tracked and non-ignored safe text without printing suspected secret values.
4. Optional tracked Git hooks run security before commit and full verification before push.
5. CI repeats the canonical checks and adds a history-aware TruffleHog scan.
6. `$production-readiness` treats missing authorization, recovery, rollback, or operational ownership as a release gap.

Project hooks run only after the user reviews and trusts them. Repository code cannot grant that trust on the user's behalf.

## Token efficiency

Codexicon reduces recurring context rather than weakening engineering work:

- `AGENTS.md` stays short and durable.
- Codex sees compact skill metadata first and loads full instructions only when they apply.
- Detailed project facts live under `agent_docs/` and are read selectively.
- Tool output is targeted and delegation is used only when it offsets its additional context.
- `$concise` shortens communication without reducing reasoning, implementation, tests, review, or security evidence.

The template validator enforces budgets for always-loaded repository guidance and the initial skill catalog.

## Repository structure

```text
.
├── AGENTS.md                 # durable project rules and workflow routing
├── START_HERE.md             # complete project-start guide
├── .agents/skills/           # progressively disclosed workflows
├── .codex/
│   ├── config.toml           # conservative trusted-project defaults
│   ├── hooks.json            # lifecycle registration
│   ├── hooks/                # portable hook implementation
│   └── agents/               # bounded project agent profiles
├── .githooks/                # opt-in commit and push verification
├── agent_docs/               # project facts, decisions, specs, and operations
├── docs/                     # Codex guide, patterns, and visual playbook
├── scripts/                  # canonical cross-platform commands
└── tests/                    # template, hook, scanner, and creative checks
```

The root `.codexicon.json` is the source ownership contract used by the repository-local manager; adopted projects record their installed baselines in `.codexicon.lock.json`.

## Documentation

- [Start a project](START_HERE.md)
- [Codex configuration and hooks](docs/codex.md)
- [Agent and delegation patterns](docs/agent-patterns.md)
- [Deployment command pattern](docs/deploy-patterns.md)
- [Architecture decision template](docs/adr-template.md)
- [Maintainer and release guide](docs/maintainers.md)
- [Security policy](SECURITY.md)
- [Support](SUPPORT.md)
- [Contributing](CONTRIBUTING.md)

## Requirements

- Codex opened at the repository root.
- Python 3.10 or newer for template validation and hooks.
- Git only when branches, commits, worktrees, remotes, or pull requests are wanted.
- Bash for the POSIX scripts or PowerShell for the equivalent native Windows paths.

No provider account, API key, database, hosting platform, or optional integration is required to begin.

## What Codexicon does not do

- It does not choose a framework, database, or cloud before the project requires one.
- It does not guarantee that generated code is correct, secure, accessible, or production-ready.
- It does not read credentials, create production secrets, or preconfigure third-party integrations.
- It does not download or apply automatic harness updates.
- It does not authorize commits, pushes, deployments, messages, purchases, or production changes.
- It does not replace product judgment, security review, operational ownership, or human risk acceptance.

## Versioning and updates

Template releases are recorded in [`TEMPLATE_VERSION`](TEMPLATE_VERSION). Projects remain independent and never receive automatic or network-fetched upgrades.

Adopted repositories can compare a trusted local release source and apply only baseline-unchanged files:

```bash
python scripts/codexicon.py update --root /path/to/project --source /path/to/new-codexicon
python scripts/codexicon.py update --root /path/to/project --source /path/to/new-codexicon --apply
```

The first command is a read-only plan. Apply uses atomic writes and rollback, leaves locally modified files as conflicts, and never commits or publishes the result. Project-owned commands, guidance, architecture, and decisions still require deliberate integration.

## Community

Questions and reproducible problems belong in GitHub Issues after checking [support guidance](SUPPORT.md). Security vulnerabilities must follow [the private reporting process](SECURITY.md). Contributions are welcome under [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md).

Codexicon is maintained by [@bnet47](https://github.com/bnet47) and released under the [MIT License](LICENSE).
