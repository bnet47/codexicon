#!/usr/bin/env bash
set -euo pipefail

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "[git-hooks] Initialize Git before installing repository hooks." >&2
  exit 1
fi

root="$(git rev-parse --show-toplevel)"
cd "$root"
chmod +x .githooks/pre-commit .githooks/pre-push
git config --local core.hooksPath .githooks
echo "[git-hooks] Installed repository pre-commit and pre-push gates."

