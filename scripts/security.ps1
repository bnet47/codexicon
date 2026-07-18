$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$PythonCommand = (Get-Command $PythonBin -ErrorAction Stop).Source

Push-Location $Root
try {
    & $PythonCommand scripts/security_scan.py
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
finally {
    Pop-Location
}

