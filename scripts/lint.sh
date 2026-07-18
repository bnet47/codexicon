#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN=python
fi

output_file="$(mktemp)"
trap 'rm -f "$output_file"' EXIT

if {
  for script in scripts/*.sh; do
    bash -n "$script"
  done
  "$PYTHON_BIN" scripts/validate_template.py
} >"$output_file" 2>&1; then
  "$PYTHON_BIN" .codex/hooks/codex_hook.py emit-success lint
  cat "$output_file"
else
  status=$?
  cat "$output_file" >&2
  exit "$status"
fi

if [[ "${1:-}" == "--fix" ]]; then
  echo "[lint] No automatic template fixes are defined; validation passed."
else
  echo "[lint] Template validation passed."
fi
