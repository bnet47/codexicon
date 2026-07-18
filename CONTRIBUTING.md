# Contributing to Codexicon

Codexicon welcomes focused improvements to its documentation, workflows, safeguards, portability, and verification. Changes should make the template more reliable or easier to understand without increasing recurring context unnecessarily.

## Before opening a change

1. Search existing issues and pull requests.
2. For a small correction, open a focused pull request.
3. For a new skill, dependency, lifecycle stage, or behavior change, open an issue first so the trigger, maintenance cost, and compatibility impact can be discussed.
4. Never include credentials, private logs, customer data, or copied proprietary instructions.

Security vulnerabilities must use the private process in [SECURITY.md](SECURITY.md), not a public issue.

## Local verification

Python 3.10 or newer is required. From the repository root, run either path:

```bash
./scripts/lint.sh
./scripts/test.sh
./scripts/security.sh
```

```powershell
./scripts/lint.ps1
./scripts/test.ps1
./scripts/security.ps1
```

Both platform paths must enforce equivalent checks. If a change affects the visual playbook, update its tracked source and run:

```bash
python scripts/render_playbook.py
python scripts/render_playbook.py --check
python .agents/skills/review-creative/scripts/scan_interface.py docs/repo-template-playbook.source.html
```

## Change standards

- Preserve the stack-neutral project-start experience.
- Keep `AGENTS.md` limited to durable rules that justify always-loaded context.
- Put reusable workflows in `.agents/skills/` and project facts in `agent_docs/`.
- Keep skills concise, with precise trigger descriptions and progressive references only when needed.
- Add regression tests for hook, scanner, validator, and command-contract changes.
- Keep POSIX and native Windows behavior equivalent.
- Pin GitHub Actions to reviewed immutable revisions.
- Do not add automatic commits, pushes, deployments, external messages, or third-party writes.
- Do not weaken verification or reasoning merely to save tokens.

## Pull requests

Use a branch and pull request; do not push directly to `main`. Explain the outcome, scope, risks, and exact verification. Keep unrelated cleanup out of the change.

By contributing, you agree that your contribution is licensed under the repository's [MIT License](LICENSE) and that you will follow the [Code of Conduct](CODE_OF_CONDUCT.md).

