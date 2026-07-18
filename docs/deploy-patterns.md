# Deployment contract

`scripts/deploy.sh` must remain fail-closed until `$init` or a later deployment task configures a real target. Do not copy a provider command without validating it against the project's current provider documentation and authentication model.

## Required properties

Every configured deployment should:

1. Accept an explicit environment such as `staging` or `prod`.
2. Run the repository's real lint and test commands before mutation.
3. Refuse production unless the workflow has explicit production authorization.
4. Identify the immutable source revision or artifact being deployed.
5. Avoid placing tokens or credentials on the command line or in tracked config.
6. Surface the target, result, and observable deployment identifier.
7. Document rollback or roll-forward behavior.

## Environment policy

| Environment | Typical trigger | Required authority | Failure handling |
|---|---|---|---|
| Local | developer command | none | stop process |
| Staging | branch/PR workflow | project policy | preserve logs and prior artifact |
| Production | protected workflow | explicit user or release approval | execute documented rollback/roll-forward |

## Script skeleton

```bash
#!/usr/bin/env bash
set -euo pipefail

target="${1:-}"
[[ "$target" == "staging" || "$target" == "prod" ]] || {
  echo "usage: ./scripts/deploy.sh [staging|prod]" >&2
  exit 2
}

if [[ "$target" == "prod" && "${DEPLOY_APPROVED:-false}" != "true" ]]; then
  echo "production deployment requires DEPLOY_APPROVED=true" >&2
  exit 2
fi

./scripts/lint.sh
./scripts/test.sh

# Build one immutable artifact, deploy it with the provider's supported CLI,
# print the deployment identifier, and verify a health signal.
```

Do not use an arbitrary sleep as the production approval mechanism. Approval happens before the command; the script verifies the explicit gate.

## Documentation to add with a provider

- current provider CLI and pinned/managed version;
- authentication source and required scopes;
- environment-to-project mapping;
- build and deploy commands;
- database migration ordering;
- health verification;
- rollback/roll-forward procedure;
- owner and incident path.
