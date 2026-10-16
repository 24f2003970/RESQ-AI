param([ValidateSet('development','production')][string]$Mode = 'development')
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Backend = Join-Path $Root 'backend'
$Frontend = Join-Path $Root 'frontend'
$Python = Join-Path $Backend '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) { throw 'Backend environment is missing. Run scripts\setup-resq-ai.ps1 first.' }
if (-not (Test-Path (Join-Path $Frontend 'node_modules'))) { throw 'Frontend dependencies are missing. Run scripts\setup-resq-ai.ps1 first.' }
if (-not (Test-Path (Join-Path $Backend 'ml_artifacts\flood_exposure_v1.joblib'))) { throw 'The locally trained model artifact is missing. See docs/LOCAL_DEMO_QUICKSTART.md.' }

$pythonVersion = & $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $pythonVersion.Trim() -ne '3.12') { throw 'backend/.venv must use Python 3.12. Run setup with Python 3.12 available.' }
$node = Get-Command node -ErrorAction Stop
$nodeParts = (& $node.Source --version).Trim().TrimStart('v').Split('.')
$nodeMajor = [int]$nodeParts[0]
if (-not ($nodeMajor -gt 22 -or ($nodeMajor -eq 22 -and [int]$nodeParts[1] -ge 12))) { throw 'Node.js 22.12 or newer is required.' }

$viteCli = Join-Path $Frontend 'node_modules\vite\bin\vite.js'
$frontendArguments = @($viteCli,'--host','127.0.0.1')
$frontendUrl = 'http://127.0.0.1:5173'
if ($Mode -eq 'production') {
    Push-Location $Frontend
    try { npm run build; if ($LASTEXITCODE -ne 0) { throw 'Production build failed.' } }
    finally { Pop-Location }
    $frontendArguments = @($viteCli,'preview','--host','127.0.0.1','--port','4173')
    $frontendUrl = 'http://127.0.0.1:4173'
}

$DbPath = if ($env:RESQ_DB_PATH) { $env:RESQ_DB_PATH } else { Join-Path $Backend 'data\resq.sqlite3' }
if (Test-Path $DbPath) {
    & $Python -c "import pathlib,sqlite3,sys; p=pathlib.Path(sys.argv[1]); db=sqlite3.connect(p.resolve().as_uri()+'?mode=ro',uri=True,timeout=2); result=db.execute('PRAGMA quick_check').fetchone()[0]; db.close(); print(result); sys.exit(0 if result=='ok' else 1)" $DbPath
    if ($LASTEXITCODE -ne 0) { throw 'The existing local SQLite database failed a read-only quick check. Preserve the file and inspect it before starting.' }
} else {
    Write-Host 'No existing SQLite database; the backend will initialize it.'
}

foreach ($port in @(8000, $(if ($Mode -eq 'development') { 5173 } else { 4173 }))) {
    $occupied = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($occupied) { throw "Port $port is already in use. Close the process using it and rerun. For alternate ports, use the manual commands in README.md and update the Vite proxy and preflight URLs to match." }
}

$children = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
try {
    $backendTimer = [System.Diagnostics.Stopwatch]::StartNew()
    $backendProcess = Start-Process -FilePath $Python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $Backend -PassThru -NoNewWindow
    $children.Add($backendProcess)
    $ready = $false
    for ($i = 0; $i -lt 40; $i++) {
        if ($backendProcess.HasExited) { throw "Backend exited during startup (code $($backendProcess.ExitCode))." }
        try {
            $health = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/health' -TimeoutSec 2
            if ($health.status -eq 'ok') { $ready = $true; break }
        } catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $ready) { throw 'Backend did not become healthy within 20 seconds. Run scripts\demo-preflight.ps1 for diagnostics.' }
    $backendTimer.Stop()
    Write-Host "Backend health readiness: $([math]::Round($backendTimer.Elapsed.TotalMilliseconds,1)) ms"
    $frontendTimer = [System.Diagnostics.Stopwatch]::StartNew()
    if ($Mode -eq 'development') {
        $frontendProcess = Start-Process -FilePath $node.Source -ArgumentList $frontendArguments -WorkingDirectory $Frontend -PassThru -NoNewWindow
    } else {
        $frontendProcess = Start-Process -FilePath $node.Source -ArgumentList $frontendArguments -WorkingDirectory $Frontend -PassThru -NoNewWindow
    }
    $children.Add($frontendProcess)
    $frontendReady = $false
    for ($i = 0; $i -lt 40; $i++) {
        if ($frontendProcess.HasExited) { throw "Frontend exited during startup (code $($frontendProcess.ExitCode))." }
        try { Invoke-WebRequest -Uri $frontendUrl -TimeoutSec 2 | Out-Null; $frontendReady = $true; break }
        catch { Start-Sleep -Milliseconds 500 }
    }
    if (-not $frontendReady) { throw 'Frontend did not respond within 20 seconds. Run scripts\demo-preflight.ps1 for diagnostics.' }
    $frontendTimer.Stop()
    Write-Host "Frontend HTTP readiness: $([math]::Round($frontendTimer.Elapsed.TotalMilliseconds,1)) ms"
    Write-Host "RESQ-AI is running at $frontendUrl" -ForegroundColor Green
    Write-Host 'Backend health: http://127.0.0.1:8000/api/v1/health'
    Write-Host 'Press Ctrl+C to stop both local services.'
    while ($children | Where-Object { -not $_.HasExited }) { Start-Sleep -Milliseconds 500 }
    throw 'A RESQ-AI service stopped unexpectedly.'
}
finally {
    foreach ($process in $children) {
        if (-not $process.HasExited) {
            & taskkill.exe /PID $process.Id /T /F 2>$null | Out-Null
            $process.WaitForExit(5000) | Out-Null
        }
    }
}
