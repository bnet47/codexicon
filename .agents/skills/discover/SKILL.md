---
name: discover
description: Define the project contract in root SPEC.md before technical choices.
---

# Discover

Define a durable project contract without turning ordinary discovery into an approval loop.

1. Inspect the repository identity and any existing `SPEC.md`.
2. Ask only questions whose answers would materially change the product outcome, safety boundary, or irreversible technical direction. Batch related questions.
3. Infer reversible details and record them as assumptions.
4. Create or update root `SPEC.md` with:
   - an observable outcome;
   - stable requirement IDs such as `R-001`;
   - interface contracts such as `I-001`;
   - acceptance conditions such as `A-001`;
   - explicit anti-goals covering what will not be built, mocked, or supported;
   - assumptions and unresolved blockers.
5. Keep requirements and interfaces append-only. Record changes under `Amendments`; never silently rewrite or delete an existing contract item.
6. Run `python scripts/codexicon.py spec-check` before continuing.
7. Continue directly to `$init` or `$autonomous-build` when the request authorizes implementation.

Pause only for a critical unresolved domain decision, required credentials with no safe local substitute, or an unrecoverable repository/tooling failure. Do not ask for approval of routine wording or technical defaults. Do not commit or push.
