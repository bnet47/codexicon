---
name: conventional-commit
description: Draft a Conventional Commit message when the user requests a commit or message. Formats only; does not authorize Git operations.
---

# Conventional commit

Format:

```text
type(scope): imperative summary
```

Allowed types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `ci`, `build`, `revert`.

- Derive the scope from the behavior or module, not the ticket name.
- Use lowercase imperative wording with no trailing period.
- Keep the subject at or below 72 characters when practical.
- Add a body when motivation, migration, compatibility, or risk is not obvious from the diff.
- Add `BREAKING CHANGE:` only for an intentional incompatible change.

Inspect the staged diff before finalizing the message. If nothing is staged or unrelated changes are mixed together, report that instead of inventing a broad message.

This skill does not stage files, create a commit, push, or open a PR unless the user explicitly requested those operations through `$ship` or an equivalent instruction.
