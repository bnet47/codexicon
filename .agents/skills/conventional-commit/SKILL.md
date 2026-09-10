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

Use the supplied change details, task scope, changed-path evidence, and verification results to draft a message even when nothing is staged. During Build, staging is outside the authority boundary; do not request it or treat its absence as missing input. During Ship, inspect the staged diff when one is available and report unrelated or unverified changes instead of inventing a broad message.

This skill does not stage files, create a commit, push, or open a PR unless the user explicitly requested those operations through `$ship` or an equivalent instruction.
