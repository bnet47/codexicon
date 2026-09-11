# Clean Codexicon starters

The template repository contains its own development contract, task ledger, historical briefs, checkpoints, and evaluation material. A new project should not inherit that state.

From a trusted local Codexicon checkout, create a clean starter with:

```bash
python scripts/codexicon.py scaffold /path/to/new-project
```

The command accepts an optional `--source PATH` when the command is run from a different trusted template checkout. Use `--dry-run` to print the exact output allowlist without writing anything.

The target must not already exist, and the command refuses protected targets, symlink sources, and targets inside the source template. It stages the files in a temporary sibling directory and publishes the target only after every allowlisted source has been checked.

The starter carries the reusable Codex configuration, hooks, agent profiles, skills, local manager, security scanner, project command stubs, and workflow documentation. It creates a filtered `.codexicon.json` for the files it carries. The explicit allowlist excludes:

- `SPEC.md` and `TASKS.md`;
- `agent_docs/briefs/`, `agent_docs/plans/`, `agent_docs/sessions/`, receipts, and checkpoint state;
- evaluation records and repository-internal evaluation documents;
- credentials, protected paths, generated output, and local Codex state.

## Starter smoke test

Run the manager's local structural diagnostic from the new project:

```bash
python scripts/codexicon.py doctor --root /path/to/new-project
```

The diagnostic may report informational source-manifest output, but it must report zero errors. The first product step remains `$discover`, which creates the new project's active root `SPEC.md`; `$init` then replaces the project command stubs after the contract is approved.
