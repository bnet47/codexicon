# Codex collaboration patterns

Use subagents when independent context or parallelism materially improves the task. Every subagent consumes additional tokens and introduces coordination cost, so file counts and token guesses are not sufficient reasons by themselves.

Use Codex's built-in `explorer` for read-heavy repository mapping. The project `researcher` is narrower: it verifies current external documentation and specifications from primary sources. The primary agent integrates both forms of evidence.

## Pattern 1: parallel exploration

Use for unfamiliar repositories, broad reviews, test-failure clusters, or several independent research questions.

```text
Primary agent
├── researcher/explorer: bounded question A (read-only)
├── researcher/explorer: bounded question B (read-only)
└── integrates evidence, decides, and verifies
```

Give each agent a non-overlapping question and a compact report format. The primary agent verifies important claims against the repository before acting.

## Pattern 2: plan execution

Use after an approved implementation plan when tasks have clear dependency and file boundaries.

```text
Primary agent
├── implementer: independent task A
├── implementer: independent task B
├── integrates and resolves conflicts
└── reviewer: combined diff (read-only, when risk warrants)
```

Parallelize read-heavy or non-overlapping work. Execute tasks that share interfaces or files sequentially. The primary agent owns full lint, tests, and acceptance coverage.

## Pattern 3: architecture research

```text
Primary agent defines decision drivers
└── researcher verifies current external facts
Primary agent compares options and records the ADR
```

The researcher gathers evidence; it does not make the final decision.

## Pattern 4: focused review

For a large or high-risk diff, use separate read-only review passes for correctness, security, and tests. Consolidate duplicate findings and reject speculative items before reporting.

## Worktree isolation

Codex app tasks can use managed worktrees for independent background work. Prefer that isolation over manually creating branches for every subagent. Do not run simultaneous writers in the same checkout unless their file scopes are provably disjoint and the primary agent is prepared to integrate conflicts.

Ignored files are not copied into managed worktrees by default. Add only the minimum required local files to `.worktreeinclude`, and never track secrets.

`.codex-state/` intentionally remains ignored, so a handoff may not carry hook verification state. On resume, the hook conservatively requires fresh checks whenever state is missing, including when Git cannot see ignored project changes; use `$context-dump` when semantic continuation context must persist.

## Brief template

Every delegated task should state:

- one concrete objective;
- exact allowed files or read-only scope;
- relevant constraints and dependencies;
- expected output format;
- verification command or evidence standard;
- explicit authorization for any Git or external side effect (normally none).

## Failure handling

`NEEDS_CONTEXT` means the brief omitted a resolvable dependency. `BLOCKED` means the task cannot progress with the current approach or authority. Provide targeted context once; if the same block repeats, change the approach or ask the user instead of spawning more agents.
