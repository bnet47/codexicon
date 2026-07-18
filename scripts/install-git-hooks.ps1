$ErrorActionPreference = "Stop"

& git rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "[git-hooks] Initialize Git before installing repository hooks."
    exit 1
}

$Root = (& git rev-parse --show-toplevel).Trim()
Push-Location $Root
try {
    & git config --local core.hooksPath .githooks
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Write-Output "[git-hooks] Installed repository pre-commit and pre-push gates."
}
finally {
    Pop-Location
}

