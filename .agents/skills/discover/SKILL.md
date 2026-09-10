---
name: discover
description: Define the project contract in root SPEC.md before technical choices.
---

# Discover

Define or amend the durable project contract in the root `SPEC.md` without turning
ordinary discovery into an approval loop.

1. Inspect the repository identity and any existing root `SPEC.md` and `TASKS.md`.
2. Ask only questions whose answers would materially change the product outcome, safety boundary, or irreversible technical direction. Batch related questions.
3. Infer reversible details and record them as assumptions.
4. Create or amend root `SPEC.md` in place with:
   - an observable outcome;
   - stable requirement IDs such as `R-001`;
   - interface contracts such as `I-001`;
   - acceptance conditions such as `A-001`;
   - explicit anti-goals covering what will not be built, mocked, or supported;
   - assumptions and unresolved blockers.
5. Keep requirements and interfaces append-only. Record changes under `Amendments`; never silently rewrite or delete an existing contract item. Do not write only a brief or keep the active contract in transcript context.
6. Run `python scripts/codexicon.py spec-check` before continuing. If implementation is authorized and the change spans multiple tasks, create and validate `TASKS.md` through `$write-plan`; if a register is absent, `$autonomous-build` creates the smallest traced register without another approval turn.
7. Continue directly to `$init` or the shared `$autonomous-build` loop when the request authorizes implementation. Use the persisted states `TODO`, `ACTIVE`, `BLOCKED`, and `DONE`, with queue outcomes `READY`, `RESUME_ACTIVE`, `BLOCKED`, `COMPLETE`, and `INVALID`.

Pure explanations and read-only reviews do not create or amend `SPEC.md` or `TASKS.md` and do not enter a code-generation workflow.

Build has one writer in the shared checkout: the primary agent by default. An explicitly chosen `implementer` may write one bounded task sequentially; the primary agent then re-reads the changed paths and owns integration and final verification. Never run concurrent writers.

Pause only for a critical unresolved domain decision, required credentials with no safe local substitute, or an unrecoverable repository/tooling failure. Do not ask for approval of routine wording or technical defaults. Do not commit or push.
