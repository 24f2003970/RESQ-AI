param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'

try { $Python = (Get-Command py -ErrorAction Stop).Source } catch { throw 'Python Launcher (py) is required. Install Python 3.12, then rerun this setup.' }
$pythonVersion = & $Python -3.12 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $pythonVersion.Trim() -ne '3.12') { throw 'Python 3.12 is required. Install Python 3.12, then rerun this setup.' }
try { $Node = (Get-Command node -ErrorAction Stop).Source } catch { throw 'Node.js 22.12 or newer is required. Install Node.js, then rerun this setup.' }
$nodeMajor = [int]((& $Node --version).Trim().TrimStart('v').Split('.')[0])
$nodeParts = (& $Node --version).Trim().TrimStart('v').Split('.')
$nodeOk = $nodeMajor -gt 22 -or ($nodeMajor -eq 22 -and [int]$nodeParts[1] -ge 12)
if (-not $nodeOk) { throw 'Node.js 22.12 or newer is required.' }

$VenvPython = Join-Path $Backend '.venv\Scripts\python.exe'
if (-not (Test-Path $VenvPython)) {
    & $Python -3.12 -m venv (Join-Path $Backend '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'Could not create backend/.venv.' }
}
if (-not $SkipInstall) {
    & $VenvPython -m pip install -r (Join-Path $Backend 'requirements.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
    Push-Location $Frontend
    try { npm ci; if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' } }
    finally { Pop-Location }
}
Write-Host 'Setup is ready. Run scripts\start-resq-ai.ps1 for the local development demo.' -ForegroundColor Green
