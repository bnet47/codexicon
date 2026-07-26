# Codex setup

This repository keeps Codex configuration intentionally conservative. It configures project discovery, hooks, and bounded subagent concurrency, but leaves model, reasoning effort, personality, sandbox, approvals, and optional integrations to the user or organization.

## Instruction discovery

Codex reads `AGENTS.md` from the project root toward the current working directory. Add nested `AGENTS.md` guidance only when a subtree has genuinely different commands or constraints. Use `AGENTS.override.md` for a narrower override.

Keep always-on guidance short. Put repeatable workflows in `.agents/skills/`, accepted project facts in `agent_docs/`, and one-off requirements in the task prompt.

Official reference: [Custom instructions with AGENTS.md](https://developers.openai.com/codex/guides/agents-md)

## Skills

Repository skills live in `.agents/skills/<name>/SKILL.md`. Codex initially sees only skill metadata and reads the full instructions when a request matches or the user invokes `$skill-name`.

Use `/skills` in Codex CLI or IDE surfaces to browse skills. Keep each description concise and explicit about when the skill should and should not trigger.

Official reference: [Agent skills](https://developers.openai.com/codex/skills)

## Project configuration

`.codex/config.toml` is loaded only for a trusted project. The template enables stable hooks and multi-agent support and caps direct concurrency. It deliberately does not pin a model or permission mode.

Review project configuration before trusting it. CLI/live overrides outrank project configuration; project configuration outranks profile and user defaults. Managed `requirements.toml` can constrain allowed values independently.

Official reference: [Codex configuration](https://developers.openai.com/codex/config-basic)

## Hooks

`.codex/hooks.json` registers a portable Python hook that:

- resets ephemeral verification state on a fresh or cleared session;
- preserves valid state on documented `resume` and `compact` starts, requires fresh lint and tests whenever state is missing, and points to the newest compatible explicit checkpoint;
- blocks supported shell and patch operations that target protected credential paths, while allowing protected names as `rg` search patterns when explicit non-sensitive targets are supplied;
- records successful patch/write events;
- requires lint after any write and tests after behavior-relevant writes;
- accepts verification only when an exact canonical command returns a one-use success receipt;
- recognizes only a narrow complete allowlist of read-only inspections; execution syntax and unknown options conservatively invalidate prior verification;
- conservatively invalidates verification after shell commands that are not definitely read-only;
- records compaction metadata without treating it as a project checkpoint;
- asks Codex to run any missing checks before stopping.

Codex requires review and trust for new or changed project hooks. Use `/hooks` to inspect and trust the exact definitions.

Hook launchers search the current directory and its parents, so they work before Git initialization and when Codex starts in a nested directory. Hook coverage is a safety net, not a complete security boundary—sandbox, approval policy, repository guidance, CI, and code review still matter.

Current Codex documentation does not define a reliable child-process exit-code field in `PostToolUse`. The canonical shell and PowerShell scripts therefore create a short-lived, one-use receipt only after their checks succeed. The post-tool hook consumes that receipt for the active session. Do not replace the final `emit-success` call with command-text guessing or a hand-written pass marker.

Official schema and lifecycle reference: [PostToolUse](https://developers.openai.com/codex/hooks#posttooluse).

Documentation-only changes require structural lint but not the full test suite. Once a behavior-relevant write occurs, tests remain required until a fresh canonical test receipt is recorded. Verification run outside Codex remains useful, but it does not satisfy the active task’s stop gate. Expired or malformed receipts are pruned automatically.

`.codex-state/session-<hash>.json` and short-lived receipt files are local, ephemeral, and gitignored. Session-scoped files plus file locking prevent independent Codex tasks from resetting one another while allowing subagents in one task to share conservative verification state. Missing, malformed, or wrong-schema state fails closed on the first `Stop` attempt; when Codex marks a repeated Stop hook as active, the hook returns a system message instead of blocking again so it cannot loop indefinitely. A resume/compact start rebuilds missing state conservatively and always requires fresh lint and tests. State deliberately lives outside `.codex/`, which is a protected read-only path under the normal workspace sandbox.

Official reference: [Codex hooks](https://developers.openai.com/codex/hooks)

### Credential and Git gates

The pre-tool policy blocks common repository and user credential stores, broad environment enumeration, and direct reads of secret-like environment variables. `.env.example` remains the only credential-shaped placeholder path agents may open. The dependency-free `scripts/security.sh` and `scripts/security.ps1` scan tracked and non-ignored safe text without opening protected credential paths; findings reveal only path, line, and detector.

When a project uses Git, run `scripts/install-git-hooks.sh` or `.ps1` after inspecting any existing hooks path. Installation is idempotent for `.githooks` and refuses to replace a different `core.hooksPath`. The tracked pre-commit hook runs the security gate; pre-push runs lint, tests, and security. `$ship` runs the same commands directly, so publication safety does not depend on local hooks alone.

Hook registration is structurally and behaviorally tested, but Codex trust is local to each clone and surface. After trusting the project, use `/hooks` and complete the live smoke checklist below; repository code cannot grant that trust itself.

### Durable checkpoints and resume

`$context-dump` uses `python scripts/codexicon.py checkpoint` to atomically create an explicit Markdown checkpoint under `agent_docs/sessions/`. The first line contains schema 1 metadata: checkpoint ID, creation time, repository fingerprint, branch/HEAD, and related project paths. The body remains human-readable and records current state, dirty path names, verification claims, next actions, blockers, decisions, and a compact resume note. It never includes transcript contents or diffs automatically.

`python scripts/codexicon.py resume` selects the newest checkpoint whose repository fingerprint matches the current Git common directory (or repository path outside Git), warns when HEAD changed, and prints it for verification against the current plan and diff. `doctor` reports missing related paths. Compaction does not silently write a checkpoint: `PreCompact` remains mechanical metadata, while a subsequent documented `SessionStart` source of `compact` preserves/reconstructs verification state and surfaces the compatible checkpoint.

Checkpoints are project files but are never auto-committed or synchronized. `.codex-state/` is not a checkpoint store.

## Adoption, diagnostics, and updates

`scripts/codexicon.py` is a repository-local, Python-standard-library manager; it is not a packaged CLI or network updater.

- `inspect TARGET` produces a read-only adoption plan.
- `adopt TARGET --apply` copies only absent `managed` or `merge` files and preserves every conflict/project-owned file.
- `doctor --root TARGET` diagnoses malformed config/hooks/lock data, missing canonical commands, partial adoption, local harness modifications, and broken checkpoint references without assuming the project is still a template.
- `update --root TARGET --source SOURCE` compares an installed lock with a trusted local release source. `--apply` updates or retires only files unchanged since their recorded baseline.
- `sync-git-modes --root TARGET` sets manifest-declared executable bits only on files the user has already staged or tracked. Run it after staging a Windows-origin adoption and before committing so POSIX clones retain runnable hooks and shell entry points.
- `verify` invokes the platform-native project-owned lint, test, and security scripts in canonical order and stops on the first failure.

`.codexicon.json` is the source's schema-1 whole-file ownership list, including executable intent. An adopted project receives `.codexicon.lock.json`, which stores only release/provenance metadata, paths, policies, executable intent, and SHA-256 baselines. Locally modified or deleted files become explicit conflicts. Apply uses atomic writes plus a write-ahead `.codexicon/` transaction journal, backups, rollback, and a committed cleanup phase; the next authorized mutation recovers a valid interrupted journal before planning new work. Unsafe traversal, source/target symlinks, malformed state, and source or target bytes changed during apply are refused.

The manager never downloads, commits, pushes, publishes, deploys, or writes to external systems.

## Subagents and worktrees

Project-scoped custom agents live in `.codex/agents/`. The template includes a read-only external-documentation `researcher`, a read-only `reviewer`, and a bounded `implementer`. Use Codex's built-in `explorer` for repository mapping; the custom researcher deliberately does not duplicate it.

Use subagents for independent work with clear inputs and outputs. Parallel read-heavy exploration is usually safer than parallel edits. The main agent owns integration and final verification.

Read-only custom-agent sandbox settings are defaults: a parent turn's live permission mode can override them, so agent instructions and the primary agent's review still matter.

In the Codex app, prefer Codex-managed worktrees for independent background tasks. Worktrees require Git; ignored local files are not copied unless deliberately listed in `.worktreeinclude`. Because `.codex-state/` is intentionally ignored, worktree handoff can omit local verification state; resume/compact recovery therefore treats every missing state file as requiring fresh lint and tests, including when Git cannot see changes to ignored project files.

Official references: [Subagents](https://developers.openai.com/codex/subagents), [Worktrees](https://developers.openai.com/codex/app/worktrees)

## MCP and external systems

Do not preconfigure every possible server. Add only integrations the project needs, with the narrowest tool set and approval policy.

Examples:

```bash
codex mcp add openaiDeveloperDocs --url https://developers.openai.com/mcp
codex mcp list
```

Project-scoped MCP configuration belongs in `.codex/config.toml`; personal integrations belong in `~/.codex/config.toml`. Use environment-variable names or OAuth, never literal credentials in tracked files.

Official reference: [Model Context Protocol](https://developers.openai.com/codex/mcp)

## Token efficiency

Optimize recurring context before compressing technical content:

- `AGENTS.md` is always loaded, so keep it to durable commands, boundaries, and routing.
- Codex initially loads skill names, descriptions, and paths; full `SKILL.md` bodies remain progressively disclosed. Keep descriptions short and front-load trigger conditions.
- Use targeted searches and bounded command output. Preserve full logs only when diagnosis requires them.
- Delegate only when parallelism or context isolation justifies the additional agent tokens.
- Use `$concise` for low-token communication. It never reduces reasoning, code, verification, review, security detail, exact commands, or exact errors.

The template validator budgets repository guidance and the initial skill catalog to catch context creep. It reports a rough character-based token estimate; actual tokenization and platform/global instructions vary.

The template uses `$concise` only when requested, so routine sessions do not pay recurring prompt overhead for output compression. It changes output style only; it does not compress user requirements or technical evidence.

Avoid lowering reasoning effort, tool-output limits, or compaction thresholds as a repository default merely to save tokens; those controls can hide evidence or discard useful development context.

## Verification checklist

After changing Codex configuration:

1. Start a fresh Codex task from the repository root.
2. Confirm the root `AGENTS.md` is loaded.
3. Use `/skills` to confirm repository skills are visible.
4. Use `/hooks` to review and trust hook definitions.
5. Ask Codex to list available custom agents or run a bounded read-only delegation.
6. Run `./scripts/lint.sh` and `./scripts/test.sh`, or the `.ps1` equivalents on native Windows.
7. Run `./scripts/security.sh`, then confirm a deliberately protected path request is blocked without opening the file.
8. Make a disposable documentation edit, confirm the stop gate requests lint, run the canonical lint command, and confirm the task can stop.
