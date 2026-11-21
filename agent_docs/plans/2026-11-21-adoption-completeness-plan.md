# Adoption completeness repair

Date: 2026-11-21. Contract: R-042 / I-035 / A-043. Task: T-053.

## Findings

The starter carries 23 skills; adoption carries six. Existing AGENTS.md is deliberately preserved, leaving no automatic operating-guidance integration. Doctor checks configuration and installed baselines but does not detect these gaps. Application type errors remain application defects; absent Git setup should not stop authorized local repairs.

## Implementation

One sequential task owns `.codexicon.json`, `scripts/codexicon.py`, `scripts/validate_template.py`, `AGENTS.md`, `.agents/skills/adopt-codexicon/SKILL.md`, `.agents/skills/ship/SKILL.md`, `docs/upgrading.md`, and regression tests. Extend the manifest to every allowlisted skill resource with merge policy. Validate parity to prevent recurrence. Add bounded doctor warnings for missing core skills and the documented operating-guidance reference. Supply a manual merge paragraph, preserving project identity, commands, diagnosis-only requests, and publication boundaries. Scope template release tooling to Codexicon maintenance and use consuming applications' own release checks. Record the decision in ADR-008.

## Acceptance and review

Exercise real-manifest adoption and update, preserve customized AGENTS and wrappers, delete a core skill to prove the warning, and check that an uninitialized full starter is healthy. Run focused regressions, canonical lint/test/security, and release identity before Ship. Review for protected paths, overwrite hazards, and false claims that structural checks prove application readiness. Keep historical stale task receipts visible. This task uses the next unused task ID; the November 16 plan remains an unactivated proposal whose proposed contract IDs must be reconciled before use.

## Ship

The user explicitly requested push. Inspect the change set under Ship, preserve unrelated working files, commit only this repair, and push the current non-protected branch. Do not merge or deploy by inference.
