# ADR-002: Use a repository-local adoption and update protocol

**Date:** 2026-07-26
**Status:** Accepted
**Deciders:** Repository owner (delegated request) and Codex

## Context

ADR-001 made Codex-native repository surfaces authoritative and deferred plugin packaging until the workflow proved stable. Codexicon can create a fresh repository, but an established project has no deterministic way to inspect compatibility, adopt only missing harness pieces, diagnose partial or stale configuration, or apply a later Codexicon release without manually guessing which files remain template-owned.

The solution must preserve project commands, guidance, decisions, and application content; work offline on Python 3.10+ across Windows, macOS, and Linux; require explicit mutation authority; recover interrupted writes; and avoid a hosted updater, package lifecycle, generic merge engine, or universal shell parser.

## Decision

Codexicon will use one dependency-free repository entry point, `scripts/codexicon.py`, and a versioned source manifest, `.codexicon.json`.

- Inspection, doctor, update planning, verification orchestration, checkpoint selection, and resume are read-only by default.
- Adoption and update mutations require `--apply` and an explicitly selected local source and target.
- The source manifest assigns whole-file `managed`, `merge`, or `project` ownership.
- `.codexicon.lock.json` records the installed release, source-manifest digest, and baseline hashes only for adopted managed/merge files.
- The manifest and lock carry executable intent. `sync-git-modes` applies that intent only to already-tracked index entries, avoiding implicit staging while making Windows-origin adoption portable to POSIX.
- An update may replace or retire a file only when its current hash still matches the installed baseline. A locally modified file remains unchanged and becomes an explicit conflict.
- Per-file writes are atomic. Multi-file operations use a local journal, backups, rollback, and next-run recovery.
- Canonical project lint, test, and security scripts remain project-owned; the manager invokes rather than reimplements them.
- Semantic checkpoints remain explicit Markdown project artifacts. Hooks can recover conservative verification state and surface a compatible checkpoint, but do not silently author or commit one.

## Rationale

This is the smallest option that makes adoption and future changes inspectable and recoverable without moving authority to a package registry or service. Whole-file baselines are easy to audit and test. Keeping canonical checks project-owned preserves Codexicon's strongest integration boundary after `$init`.

## Alternatives considered

| Option | Benefits | Costs / risks | Why not chosen |
|---|---|---|---|
| Continue release-note-only manual porting | No new code or state | No diagnostics or repeatable conflict detection; easy to overwrite local policy accidentally | Does not satisfy adoption or safe-update outcomes |
| Region markers and automatic three-way merging | More updates could apply automatically | Permanent markers in project files, merge semantics, and recovery complexity | Whole-file conflicts are safer and more reversible |
| Packaged CLI or Codex plugin | Central distribution and version discovery | New install, trust, compatibility, and publication lifecycle before the local protocol is proven | ADR-001's plugin revisit signal is not met |
| Hosted update/control service | Central policy and status | Telemetry, credentials, network authority, service operations, and data ownership | Explicit non-goal |

## Consequences

- **Positive:** established repositories gain plan-first adoption, post-init diagnostics, local update provenance, atomic recovery, one verification entry point, and deterministic checkpoint resume.
- **Negative:** maintainers must keep a small manifest schema and explicit file list current; locally modified files require human integration; checkpoints are not synchronized automatically.
- **Signals to revisit:** the manifest requires multiple incompatible migrations, whole-file conflicts dominate routine updates, or multiple proven repositories need the same distribution lifecycle and can justify plugin packaging.

## Implementation notes

- Source contract: `.codexicon.json`, schema version 1.
- Installed contract: `.codexicon.lock.json`, schema version 1; it is safe to track and contains release/provenance metadata, paths, policies, executable intent, unresolved entries, and SHA-256 baselines, but no file contents or credentials.
- Transaction state: `.codexicon/transaction.json` and `.codexicon/backups/`; never place credentials or arbitrary project files in the manifest.
- User interfaces: `inspect`, `adopt`, `doctor`, `update`, `verify`, `checkpoint`, `resume`, and `install-git-hooks`.
- Template validation checks the manifest, documented Codex config, hook registration, POSIX modes/EOL policy, and skill budget.
- No command commits, pushes, downloads, publishes, deploys, or performs external writes.
