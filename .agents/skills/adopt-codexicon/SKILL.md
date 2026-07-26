---
name: adopt-codexicon
description: Inspect, adopt, diagnose, or update Codexicon in an established repository without overwriting local content.
---

# Adopt or update Codexicon

Use the repository-local manager from a trusted Codexicon source. Keep inspection read-only until the user explicitly authorizes apply.

## 1. Inspect

Confirm the intended source and target repository roots, then run:

```text
python scripts/codexicon.py inspect TARGET
```

Report every `create`, `identical`, `preserve`, `required-missing`, and `conflict` result. Inspect existing project commands, `AGENTS.md`, `.codex/`, skills, CI, Git hooks, and project facts before recommending adoption. Do not treat a missing project-owned file as safe to synthesize automatically.

## 2. Adopt

Only after the user authorizes repository writes, run:

```text
python scripts/codexicon.py adopt TARGET --apply
```

The manager copies only absent managed/merge files, preserves conflicts, records baseline hashes in `.codexicon.lock.json`, and returns nonzero while integration work remains. Resolve conflicts deliberately; never replace real project commands with template stubs.

After the user deliberately stages the adopted files, run `python TARGET/scripts/codexicon.py sync-git-modes --root TARGET`. It changes only manifest-declared executable bits on already-tracked index entries and refuses untracked paths; this is required for Windows-origin adoptions that will be cloned on POSIX.

Run `python TARGET/scripts/codexicon.py doctor --root TARGET`, then the target's canonical lint, test, and security commands.

## 3. Update

From an adopted target, inspect a trusted local release source before apply:

```text
python scripts/codexicon.py update --root TARGET --source SOURCE
python scripts/codexicon.py update --root TARGET --source SOURCE --apply
```

Apply is explicit and offline. Unchanged baseline files may update or retire; locally modified files remain conflicts. Review changed hooks with `/hooks` because their trust hash changes.

Do not download releases, commit, push, publish, deploy, or modify external systems unless separately authorized.
