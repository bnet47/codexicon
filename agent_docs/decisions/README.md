# Decision journal

`agent_docs/decisions/` is the canonical, durable location for consequential
assumptions and decisions. Each record is a new Markdown file named
`ADR-NNN-short-title.md`; the existing ADR files and this format guide are
project history, not a mutable scratchpad.

Existing accepted ADRs are grandfathered as historical records. They may
predate this complete format, but they are never rewritten or deleted. Every
new consequential record, including one that supersedes a legacy decision,
must use the complete canonical format below. A later record supersedes a
legacy decision by naming or linking the earlier ADR and stating what changed;
the legacy file remains unchanged as historical evidence, while the later
record is authoritative for the current decision.

## Append-only record format

Create a new record when an assumption or decision could affect workflow
behavior, authority, product behavior, architecture, security, data, or a
material verification claim. Never rewrite or delete an accepted record.
Correct or supersede it with a later record that links back to the earlier
record and explains the change.

Every consequential record must contain these fields and sections:

```markdown
# ADR-NNN: Short title

**Date:** YYYY-MM-DD
**Owner:** person or role responsible for the decision
**Status:** Proposed | Accepted | Superseded | Rejected
**Evidence:** paths, commands, task IDs, or other inspectable support
**Supersedes:** ADR-NNN or None

## Context

What assumption, problem, or decision needs to be visible?

## Decision or assumption

State the chosen policy or assumption precisely.

## Rationale

Explain why this choice is appropriate.

## Alternatives considered

Record the credible options considered and why they were not chosen.

## Impact

Record affected users, workflow, authority, data, verification, and follow-up.
```

The `Date`, `Owner`, `Status`, `Evidence`, and `Supersedes` metadata are
required for every new consequential record, even when it is a short
assumption. `Rationale`, `Alternatives considered`, and `Impact` must be
substantive enough for a later reader to reconstruct the choice. A task receipt
may point to a journal record, but it does not replace the record's durable
rationale or evidence.

## Related-scope gate

Build may include a related correction or supporting change without a routine
approval stop only when all four conditions hold: it is small, reversible,
directly related to the selected task, and within the declared system boundary.
Examples include a directly related correctness, safety, test, maintainability,
or documentation fix. Record a consequential assumption or decision before
continuing and keep the task trace, declared file boundary, and verification
scope accurate.

Stop and explicitly escalate before editing when a proposed expansion changes
authority, product behavior, schema or data shape, security posture, or an
irreversible/destructive outcome. The same escalation applies to credentials,
production actions, external writes, publication, deployment, migrations,
material architecture choices, and legal or compliance commitments. Do not
use the journal to grant that authority: `$ship` or the responsible human
still owns those actions.
