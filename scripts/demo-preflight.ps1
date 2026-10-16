$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Backend environment is missing. Run scripts\setup-resq-ai.ps1 first.' }
Push-Location $Root
try {
    & $Python 'scripts\demo_preflight.py' @args
    exit $LASTEXITCODE
}
finally { Pop-Location }
