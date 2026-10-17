param(
    [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$repositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$generator = Join-Path $PSScriptRoot "write-release-manifest.ps1"
$pwsh = (Get-Process -Id $PID).Path
$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("resqai-manifest-validation-" + [guid]::NewGuid().ToString("N"))
$baseFixture = Join-Path $tempRoot "base"
$passed = 0

function Invoke-Git([string]$WorkingDirectory, [string[]]$Arguments) {
    $output = & git -C $WorkingDirectory @Arguments 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed: $output" }
    return ($output | Out-String).Trim()
}

function New-Fixture([string]$Name) {
    $fixture = Join-Path $tempRoot $Name
    & git clone --quiet --no-hardlinks --local --branch (Invoke-Git $repositoryRoot @("branch", "--show-current")) $baseFixture $fixture
    if ($LASTEXITCODE -ne 0) { throw "Could not create disposable fixture '$Name'." }
    $distSource = Join-Path $repositoryRoot "frontend/dist"
    if (-not (Test-Path -LiteralPath $distSource -PathType Container)) {
        throw "Cannot prepare fixture: frontend/dist is missing in the source checkout."
    }
    $distTarget = Join-Path $fixture "frontend/dist"
    New-Item -ItemType Directory -Path $distTarget -Force | Out-Null
    Copy-Item -Path (Join-Path $distSource "*") -Destination $distTarget -Recurse -Force
    return $fixture
}

function Assert-ManifestRejected([string]$Name, [string]$RelativePath, [string]$ExpectedText) {
    $fixture = New-Fixture $Name
    $target = Join-Path $fixture ($RelativePath.Replace('/', [string][char]92))
    if ($Name -eq "hash-mismatch") {
        $report = Get-Content -LiteralPath $target -Raw | ConvertFrom-Json
        $report.artifact_integrity.model_artifact_sha256 = "0" * 64
        $report | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $target -Encoding utf8
    } elseif ($Name -eq "empty-build") {
        Get-ChildItem -LiteralPath $target -File -Recurse | Remove-Item -Force
    } else {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
    $outputPath = "artifacts/part16-release-manifest.json"
    $output = & $pwsh -NoProfile -File $generator -RepositoryRoot $fixture -OutputPath $outputPath 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -eq 0) { throw "FAIL ${Name}: generator accepted an invalid fixture." }
    $message = $output | Out-String
    if ($message -notmatch [regex]::Escape($ExpectedText)) {
        throw "FAIL ${Name}: expected error text '$ExpectedText'; got '$message'."
    }
    if (Test-Path -LiteralPath (Join-Path $fixture $outputPath)) { throw "FAIL ${Name}: a manifest was emitted after validation failed." }
    $script:passed++
    Write-Output "PASS $Name rejected with no manifest output"
}

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    $currentBranch = Invoke-Git $repositoryRoot @("branch", "--show-current")
    & git clone --quiet --no-hardlinks --local --branch $currentBranch $repositoryRoot $baseFixture
    if ($LASTEXITCODE -ne 0) { throw "Could not create the base disposable repository fixture." }

    $valid = New-Fixture "valid"
    $validOutput = "artifacts/part16-release-manifest.json"
    $output = & $pwsh -NoProfile -File $generator -RepositoryRoot $valid -OutputPath $validOutput 2>&1
    if ($LASTEXITCODE -ne 0) { throw "Valid fixture failed: $($output | Out-String)" }
    $manifestPath = Join-Path $valid $validOutput
    $manifestText = Get-Content -LiteralPath $manifestPath -Raw
    $manifest = $manifestText | ConvertFrom-Json -ErrorAction Stop
    $expectedCommit = Invoke-Git $valid @("rev-parse", "HEAD")
    if ($manifest.git.commit_sha -ne $expectedCommit) { throw "Valid fixture recorded the wrong source commit." }
    if ($manifest.frontend_build.asset_count -le 0 -or $manifest.frontend_build.assets.Count -ne $manifest.frontend_build.asset_count) {
        throw "Valid fixture has an invalid frontend asset count."
    }
    foreach ($asset in $manifest.frontend_build.assets) {
        if ($asset.path -match '(^|/)\.\.(?:/|$)' -or $asset.path -match '^[A-Za-z]:|^/') { throw "Unsafe frontend asset path: $($asset.path)" }
        $assetPath = Join-Path $valid ($asset.path.Replace('/', [string][char]92))
        if (-not (Test-Path -LiteralPath $assetPath -PathType Leaf)) { throw "Manifest asset is missing: $($asset.path)" }
        $actual = (Get-FileHash -LiteralPath $assetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actual -ne $asset.sha256) { throw "Manifest asset hash mismatch: $($asset.path)" }
    }
    if ($manifestText -match '(?i)(api[_-]?key|password|secret|token)\s*[:=]' -or
        $manifestText -match '(?i)[A-Z]:\\Users\\|/home/[^/]+/') {
        throw "Manifest contains a secret-like value or personal-machine path."
    }
    if ($manifest.model_artifacts.model.sha256 -notmatch '^[0-9a-f]{64}$' -or
        $manifest.model_artifacts.calibrator.sha256 -notmatch '^[0-9a-f]{64}$' -or
        $manifest.requirements.frontend_lockfile.sha256 -notmatch '^[0-9a-f]{64}$') {
        throw "Valid fixture contains an invalid recorded checksum."
    }
    $passed++
    Write-Output "PASS all-required-artifacts, JSON, source commit, asset hashes, and hygiene"

    Assert-ManifestRejected "missing-model" "backend/ml_artifacts/flood_exposure_v1.joblib" "flood_exposure_v1.joblib"
    Assert-ManifestRejected "missing-calibrator" "backend/ml_artifacts/flood_exposure_platt_v1.joblib" "flood_exposure_platt_v1.joblib"
    Assert-ManifestRejected "missing-support" "backend/ml_artifacts/distribution_support_v1.json" "distribution_support_v1.json"
    Assert-ManifestRejected "missing-metadata" "backend/ml_artifacts/model_metadata.json" "model_metadata.json"
    Assert-ManifestRejected "missing-reliability-report" "backend/ml_artifacts/reliability_evaluation.json" "reliability_evaluation.json"
    Assert-ManifestRejected "missing-requirements" "backend/requirements.txt" "backend/requirements.txt"
    Assert-ManifestRejected "missing-lockfile" "frontend/package-lock.json" "frontend/package-lock.json"
    Assert-ManifestRejected "empty-build" "frontend/dist" "Frontend build output is missing"
    Assert-ManifestRejected "hash-mismatch" "backend/ml_artifacts/reliability_evaluation.json" "SHA-256 mismatch for random-forest model"

    $passed++
    Write-Output "PASS $passed manifest validation cases"
}
finally {
    $resolvedTemp = [System.IO.Path]::GetFullPath($tempRoot)
    $resolvedSystemTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if (-not $resolvedTemp.StartsWith($resolvedSystemTemp, [System.StringComparison]::OrdinalIgnoreCase) -or
        [System.IO.Path]::GetFileName($resolvedTemp) -notmatch '^resqai-manifest-validation-[0-9a-f]{32}$') {
        throw "Refusing to clean an unexpected validation path: $resolvedTemp"
    }
    if (Test-Path -LiteralPath $resolvedTemp) { Remove-Item -LiteralPath $resolvedTemp -Recurse -Force }
}
