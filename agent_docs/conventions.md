# Conventions — [PROJECT_NAME]

> Record project-specific rules that tools cannot infer or enforce. Delete template guidance that does not apply after initialization.

## Source layout

- [Where application code, tests, generated code, and migrations live.]
- [Dependency direction or module boundary that must be preserved.]

## Naming and interfaces

- [Language-specific naming rules not already enforced by a formatter or linter.]
- [Public API compatibility or versioning policy.]

## Errors and observability

- Return actionable errors without leaking secrets or sensitive payloads.
- Define retry and timeout behavior per dependency and operation; do not retry non-idempotent work blindly.
- Preserve causal context in logs and traces using the project's correlation identifier.
- [Project-specific logging, metrics, and tracing rules.]

## Security and side effects

- Identify operations that send messages, charge money, mutate external systems, deploy, or delete data at the interface boundary.
- Make idempotency and dry-run behavior explicit when those operations may be retried.
- Validate untrusted input at the boundary that first interprets it.
- [Authorization, tenancy, privacy, or audit conventions.]

## Tests

- Test observable behavior and failure paths, not private implementation detail.
- Add a regression test for every fixed reproducible defect when practical.
- [Fixture, integration-test, snapshot, or naming conventions.]

## Generated and vendored files

- [Which paths are generated, the command that regenerates them, and whether manual edits are forbidden.]

## Prompt or agent code (when applicable)

- Treat prompts and tool schemas as versioned behavior with tests or evals.
- Keep reusable prompt text in one deliberate source of truth; do not create parallel Python and TypeScript loaders without a real multi-runtime requirement.
- Mark external side effects in tool descriptions and require confirmation at the workflow boundary.

## Dead ends

- [YYYY-MM-DD] [Approach] — [evidence it failed] — [preferred alternative]
