# Maintaining Codexicon

This guide covers the public template itself, not projects created from it.

## Release principles

- Keep the default branch usable as a fresh template at every release.
- Preserve Python 3.10 compatibility until the documented minimum changes in a reviewed release.
- Test native Windows and POSIX paths.
- Keep action revisions immutable and review upstream release notes before updating them.
- Treat skill metadata and `AGENTS.md` as recurring context with explicit budgets.
- Never publish task-local specs, machine paths, credentials, local state, or generated debris.

## Release checklist

1. Update the version and dated notes in `TEMPLATE_VERSION`.
2. Confirm `README.md`, `START_HERE.md`, the visual playbook, and skill catalog describe the same lifecycle.
3. Run Windows and POSIX lint, tests, and security checks.
4. Run `python scripts/validate_template.py --release` to reject repository-local briefs, plans, and checkpoints before tagging.
5. Run the production-readiness skill validator and creative scanner when those surfaces changed.
6. Confirm the playbook source and standalone output match.
7. Search for machine-specific paths, credentials, obsolete harness files, placeholders outside intentional project templates, and internal task records.
8. Open a pull request and require CI before merging.
9. Tag the exact merge commit as `vX.Y.Z` and publish release notes from `TEMPLATE_VERSION`.
10. Confirm the repository remains public, marked as a template, and private vulnerability reporting is enabled.

## Updating the playbook

Edit `docs/repo-template-playbook.source.html`, then run:

```bash
python scripts/render_playbook.py
python scripts/render_playbook.py --check
```

The shell file supplies the standalone wrapper. Do not edit the generated standalone document directly.

## Updating skills

Keep the `SKILL.md` body procedural and concise. Put detailed variant guidance in a directly linked reference only when the main workflow does not need it. Validate new or changed skills with the current official skill-creator validator, but never commit a machine-specific validator path.

## Supporting generated projects

Projects created from Codexicon have independent histories and do not receive automatic updates. Keep `.codexicon.json` limited to real harness integration points and assign project-owned commands/guidance conservatively. Test adoption and update from the prior release: unchanged managed files update, retired unchanged files recoverably remove, local modifications conflict, malformed state fails safely, and no plan mode writes.

Release notes should identify safeguards worth porting and avoid instructions that overwrite project-specific commands, architecture, or accepted decisions. Update schema 1 only compatibly; a provenance or ownership semantic change requires a new schema and migration tests.

