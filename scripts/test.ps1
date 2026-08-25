$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$PythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } else { "python" }
$PythonCommand = (Get-Command $PythonBin -ErrorAction Stop).Source
$StdoutFile = [System.IO.Path]::GetTempFileName()
$StderrFile = [System.IO.Path]::GetTempFileName()

Push-Location $Root
try {
    $CommandLine = "`"$PythonCommand`" -m unittest discover -s tests 1>`"$StdoutFile`" 2>`"$StderrFile`""
    & $env:ComSpec /d /s /c $CommandLine
    $Status = $LASTEXITCODE
    if ($Status -ne 0) {
        [Console]::Out.Write([System.IO.File]::ReadAllText($StdoutFile))
        [Console]::Error.Write([System.IO.File]::ReadAllText($StderrFile))
        exit $Status
    }
    & $PythonCommand .codex/hooks/codex_hook.py emit-success test
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    Get-Content -LiteralPath $StdoutFile
    Get-Content -LiteralPath $StderrFile
}
finally {
    Pop-Location
    Remove-Item -LiteralPath $StdoutFile, $StderrFile -Force -ErrorAction SilentlyContinue
}
