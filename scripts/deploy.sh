#!/usr/bin/env bash
set -euo pipefail

target="${1:-}"
if [[ "$target" != "staging" && "$target" != "prod" ]]; then
  echo "usage: ./scripts/deploy.sh [staging|prod]" >&2
  exit 2
fi

if [[ "$target" == "prod" && "${DEPLOY_APPROVED:-false}" != "true" ]]; then
  echo "[deploy] Production deployment requires DEPLOY_APPROVED=true." >&2
  exit 2
fi

echo "[deploy] No deployment target is configured; refusing to report success." >&2
echo "[deploy] Configure this script from current provider documentation before deployment." >&2
exit 2
