---
name: context-dump
description: Create or resume an explicit human-readable checkpoint across compaction, sessions, or handoff. Primary agent only.
---

# Context checkpoint

Create or resume a concise checkpoint without transcript archaeology. Semantic checkpoints are explicit project writes; hooks never create or commit them automatically.

## 1. Choose the branch

- For a checkpoint or handoff request, continue with **Create**.
- For a resume or continuation request, continue with **Resume**.

## 2. Create

Inspect the active request/spec/plan, current diff or changed files, latest verification, and blockers. Do not copy secrets, large logs, transcript content, or code that already exists in tracked files.

Run the repository manager from the root:

```text
python scripts/codexicon.py checkpoint --slug [short-slug] --title "[short title]" --summary "[working, partial, and broken state]" --resume-note "[minimum critical continuation context]" --next "[immediate concrete action]" --related [relative spec or plan path] --verification "[exact command — result and time]" --blocker "[blocker and required input]" --decision "[decision and rationale]"
```

Repeat `--next`, `--related`, `--verification`, `--blocker`, and `--decision` as needed. Omit optional categories that are empty. Quote values for the active shell; never interpolate command output or untrusted text into the command.

The manager validates related paths, captures only dirty path names plus Git identity, and atomically writes `agent_docs/sessions/[YYYY-MM-DD]-[slug].md`. It refuses an existing filename. Do not hand-edit the first metadata line.

## 3. Resume

Run:

```text
python scripts/codexicon.py resume
python scripts/codexicon.py doctor
```

Use the newest repository-compatible checkpoint as orientation, then verify its HEAD, related paths, current diff, and verification claims before acting. A checkpoint is evidence, not authority to discard later user changes or repeat external side effects.

If no compatible checkpoint exists, inspect the latest plan and current diff directly; do not select a checkpoint from a different clone by filename alone.

## 4. Keep durable and ephemeral guidance separate

Do not place session state in `AGENTS.md`; it is always-loaded repository guidance. `.codex-state/` remains local verification state, not project memory. Do not require an MCP memory service. If the user explicitly wants cross-project memory, store only the compact resume note.

Do not commit or push the checkpoint unless the user asks to ship or explicitly requests a checkpoint commit.
