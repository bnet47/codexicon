$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$PythonCommand = (Get-Command $PythonBin -ErrorAction Stop).Source
$StdoutFile = [System.IO.Path]::GetTempFileName()
$StderrFile = [System.IO.Path]::GetTempFileName()

Push-Location $Root
try {
    $CommandLine = "`"$PythonCommand`" scripts/validate_template.py 1>`"$StdoutFile`" 2>`"$StderrFile`""
    & $env:ComSpec /d /s /c $CommandLine
    $Status = $LASTEXITCODE
    if ($Status -ne 0) {
        Get-Content -LiteralPath $StdoutFile
        Get-Content -LiteralPath $StderrFile | Write-Error
        exit $Status
    }
    & $PythonCommand .codex/hooks/codex_hook.py emit-success lint
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Get-Content -LiteralPath $StdoutFile
    Get-Content -LiteralPath $StderrFile
    Write-Output "[lint] Template validation passed."
}
finally {
    Pop-Location
    Remove-Item -LiteralPath $StdoutFile, $StderrFile -Force -ErrorAction SilentlyContinue
}
