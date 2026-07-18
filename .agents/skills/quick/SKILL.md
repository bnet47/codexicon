---
name: quick
description: Implement a clear change of roughly one to three files with no design, dependency, or schema decision. Route uncertainty elsewhere.
argument-hint: "[small change]"
---

# Quick change

Use this path only when the desired behavior and implementation approach are clear.

## Gate

Inspect the target and confirm:

- the change is coherent and normally limited to one to three files;
- no new dependency, migration, or expensive-to-reverse choice is required;
- acceptance can be verified with existing commands or a small focused test.

If not, route to `$brainstorm`, `$investigate`, `$spec`, or `$write-plan` as appropriate.

## Execute

1. State the intended change and file scope in one sentence.
2. Preserve unrelated edits and implement the smallest complete solution.
3. Add or update focused tests for changed behavior when applicable.
4. Run the narrowest relevant check. For code, configuration, generated artifacts, or shipping readiness, also run:

```bash
./scripts/lint.sh
./scripts/test.sh
```

For documentation-only changes, run the applicable documentation or structural check and explicitly report why the broader test suite was not needed.

5. Review the diff for scope, acceptance coverage, and accidental generated files.
6. Report the outcome and verification evidence.

Do not commit, push, open a PR, deploy, or modify an external system unless the user explicitly requests that action.
