#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python
fi

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

if "$PYTHON_BIN" -m unittest discover -s tests >"$output_file" 2>&1; then
  "$PYTHON_BIN" .codex/hooks/codex_hook.py emit-success test
  cat "$output_file"
else
  status=$?
  cat "$output_file" >&2
  exit "$status"
fi
