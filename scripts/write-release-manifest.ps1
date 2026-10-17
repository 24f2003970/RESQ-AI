param(
    [string]$OutputPath = "artifacts/part16-release-manifest.json",
    [string]$HostedActionsRun = "PENDING",
    [string]$RepositoryRoot = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    (Resolve-Path -LiteralPath $RepositoryRoot).Path
}
$outputAbsolute = Join-Path $repoRoot $OutputPath
$frontendDist = Join-Path $repoRoot "frontend/dist"
$artifactRoot = Join-Path $repoRoot "backend/ml_artifacts"

function Get-RequiredSha256([string]$RelativePath, [switch]$NormalizeLf) {
    $absolutePath = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        throw "Required release input is missing: $RelativePath"
    }
    if ((Get-Item -LiteralPath $absolutePath).Length -le 0) {
        throw "Required release input is empty: $RelativePath"
    }
    if ($NormalizeLf) {
        $content = [System.IO.File]::ReadAllText($absolutePath)
        $content = $content -replace "`r`n", "`n"
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
        $sha = [System.Security.Cryptography.SHA256]::Create()
        try {
            return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace("-", "").ToLowerInvariant()
        }
        finally {
            $sha.Dispose()
        }
    }
    return (Get-FileHash -LiteralPath $absolutePath -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-Sha256Match([string]$Label, [string]$Actual, [string]$Expected) {
    if ([string]::IsNullOrWhiteSpace($Expected) -or $Expected -notmatch '^[0-9a-fA-F]{64}$') {
        throw "The saved reliability report has no valid SHA-256 for $Label."
    }
    if ($Actual -ne $Expected.ToLowerInvariant()) {
        throw "SHA-256 mismatch for $Label. Expected $($Expected.ToLowerInvariant()), calculated $Actual."
    }
}

function Get-CommandVersion([string]$Executable, [string[]]$Arguments) {
    try {
        $command = Get-Command $Executable -ErrorAction Stop
        return (& $command.Source @Arguments 2>&1 | Out-String).Trim()
    }
    catch {
        return "unavailable: $Executable"
    }
}

$gitSha = (& git -C $repoRoot rev-parse HEAD).Trim()
$gitExitCode = $LASTEXITCODE
if ($gitExitCode -ne 0 -or $gitSha -notmatch '^[0-9a-fA-F]{40,64}$') {
    throw "Cannot determine the source commit for release manifest root '$repoRoot'."
}
$gitBranch = (& git -C $repoRoot branch --show-current).Trim()
$statusText = ((& git -C $repoRoot status --porcelain) -join "`n").Trim()
$dirty = -not [string]::IsNullOrEmpty($statusText)
$modelReportPath = Join-Path $artifactRoot "reliability_evaluation.json"
if (-not (Test-Path -LiteralPath $modelReportPath -PathType Leaf)) {
    throw "Required release input is missing: backend/ml_artifacts/reliability_evaluation.json"
}
try {
    $modelReport = Get-Content -LiteralPath $modelReportPath -Raw | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "Cannot parse backend/ml_artifacts/reliability_evaluation.json: $($_.Exception.Message)"
}

$requiredInputs = @(
    "backend/requirements.txt",
    "frontend/package-lock.json",
    "backend/ml_artifacts/flood_exposure_v1.joblib",
    "backend/ml_artifacts/model_metadata.json",
    "backend/ml_artifacts/flood_exposure_platt_v1.joblib",
    "backend/ml_artifacts/distribution_support_v1.json",
    "backend/ml_artifacts/reliability_evaluation.json"
)
foreach ($relativePath in $requiredInputs) {
    $null = Get-RequiredSha256 $relativePath
}

if (-not $modelReport.artifact_integrity) {
    throw "The saved reliability report is missing its artifact_integrity section."
}
$modelSha = Get-RequiredSha256 "backend/ml_artifacts/flood_exposure_v1.joblib"
$metadataSha = Get-RequiredSha256 "backend/ml_artifacts/model_metadata.json" -NormalizeLf
$calibratorSha = Get-RequiredSha256 "backend/ml_artifacts/flood_exposure_platt_v1.joblib"
$supportSha = Get-RequiredSha256 "backend/ml_artifacts/distribution_support_v1.json" -NormalizeLf
$reportSha = Get-RequiredSha256 "backend/ml_artifacts/reliability_evaluation.json" -NormalizeLf
Assert-Sha256Match "random-forest model" $modelSha ([string]$modelReport.artifact_integrity.model_artifact_sha256)
Assert-Sha256Match "model metadata" $metadataSha ([string]$modelReport.artifact_integrity.model_metadata_sha256)
Assert-Sha256Match "Platt calibrator" $calibratorSha ([string]$modelReport.artifact_integrity.calibrator_sha256)
Assert-Sha256Match "distribution-support artifact" $supportSha ([string]$modelReport.artifact_integrity.support_sha256)

$metadataPath = Join-Path $artifactRoot "model_metadata.json"
try {
    $modelMetadata = Get-Content -LiteralPath $metadataPath -Raw | ConvertFrom-Json -ErrorAction Stop
}
catch {
    throw "Cannot parse backend/ml_artifacts/model_metadata.json: $($_.Exception.Message)"
}
Assert-Sha256Match "model metadata's random-forest artifact" $modelSha ([string]$modelMetadata.artifact_sha256)
if ([string]::IsNullOrWhiteSpace([string]$modelMetadata.dataset_sha256) -or
    [string]$modelMetadata.dataset_sha256 -ne [string]$modelReport.artifact_integrity.dataset_sha256) {
    throw "Dataset SHA-256 in model_metadata.json does not match reliability_evaluation.json."
}

$pythonRequirementsSha = Get-RequiredSha256 "backend/requirements.txt"
$frontendLockSha = Get-RequiredSha256 "frontend/package-lock.json"

$frontendAssets = @()
if (Test-Path -LiteralPath $frontendDist -PathType Container) {
    $frontendAssets = @(Get-ChildItem -LiteralPath $frontendDist -File -Recurse | ForEach-Object {
        $relative = [System.IO.Path]::GetRelativePath($repoRoot, $_.FullName).Replace([string][char]92, '/')
        [ordered]@{
            path = $relative
            size_bytes = $_.Length
            sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    })
}
if ($frontendAssets.Count -eq 0) {
    throw "Frontend build output is missing. Run npm run build in frontend/ first."
}
if (@($frontendAssets | Where-Object { $_.size_bytes -le 0 }).Count -gt 0) {
    throw "Frontend production build contains a zero-byte asset. Rebuild frontend/dist before generating the release manifest."
}
$frontendAssetSizes = @($frontendAssets | ForEach-Object { [long]$_['size_bytes'] })
$frontendTotalSizeBytes = [long](($frontendAssetSizes | Measure-Object -Sum).Sum)
& git -C $repoRoot diff --quiet HEAD --
$trackedChanges = $LASTEXITCODE -ne 0

$manifest = [ordered]@{
    candidate = "RESQ-AI v1.0.0-rc-final"
    candidate_status = "review candidate; not a published release"
    generated_at_utc = [DateTime]::UtcNow.ToString("o")
    repository = "https://github.com/24f2003970/RESQ-AI"
    git = [ordered]@{
        branch = $gitBranch
        commit_sha = $gitSha
        working_tree_dirty = $dirty
        tracked_source_changes = [bool]$trackedChanges
    }
    requirements = [ordered]@{
        python = Get-CommandVersion "py" @("-3.12", "--version")
        node = Get-CommandVersion "node" @("--version")
        python_requirements = [ordered]@{ path = "backend/requirements.txt"; sha256 = $pythonRequirementsSha }
        frontend_lockfile = [ordered]@{ path = "frontend/package-lock.json"; sha256 = $frontendLockSha }
    }
    model_artifacts = [ordered]@{
        model = [ordered]@{ path = "backend/ml_artifacts/flood_exposure_v1.joblib"; sha256 = $modelSha }
        metadata = [ordered]@{ path = "backend/ml_artifacts/model_metadata.json"; normalized_lf_sha256 = $metadataSha }
        calibrator = [ordered]@{ path = "backend/ml_artifacts/flood_exposure_platt_v1.joblib"; sha256 = $calibratorSha }
        distribution_support = [ordered]@{ path = "backend/ml_artifacts/distribution_support_v1.json"; sha256 = $supportSha }
        reliability_evaluation = [ordered]@{ path = "backend/ml_artifacts/reliability_evaluation.json"; normalized_lf_sha256 = $reportSha }
        training_data_sha256 = $modelReport.dataset_sha256
        training_data_provenance = "72 generated scenario groups; synthetic simulator labels; see docs/DATASET_PROVENANCE.md"
    }
    frontend_build = [ordered]@{
        asset_count = $frontendAssets.Count
        total_size_bytes = $frontendTotalSizeBytes
        assets = $frontendAssets
    }
    demonstration = [ordered]@{
        demo_a = "seed 2026; mild; rainfall 30 mm/h; river 0.6 m; drainage 0.2; six five-minute ticks"
        demo_b = "all ten modeled road corridors closed; zero supported ground assignments expected"
        approval_boundary = "commander approval and dispatch are explicit; no automatic real-world dispatch"
    }
    verification = [ordered]@{
        record = "docs/PART_16_VERIFICATION.md"
        release_checklist = "docs/FINAL_RELEASE_CHECKLIST.md"
        hosted_actions_run = $HostedActionsRun
        browser = "See docs/PART_16_VERIFICATION.md; pending checks are not upgraded by this manifest script"
    }
    security_boundary = "loopback local prototype; no formal penetration test or OS-level network-isolation exercise claimed"
    known_limitations = "docs/FINAL_KNOWN_LIMITATIONS.md"
    distribution = "This script emits a manifest only. It does not archive environments, databases, secrets, browser data, or caches, and it does not tag, publish, deploy, or submit."
}

$directory = Split-Path -Parent $outputAbsolute
if (-not (Test-Path -LiteralPath $directory -PathType Container)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}
$json = $manifest | ConvertTo-Json -Depth 12
$null = $json | ConvertFrom-Json -ErrorAction Stop
$temporaryOutput = "$outputAbsolute.$([guid]::NewGuid().ToString('N')).tmp"
try {
    Set-Content -LiteralPath $temporaryOutput -Value $json -Encoding utf8
    Move-Item -LiteralPath $temporaryOutput -Destination $outputAbsolute -Force
}
finally {
    if (Test-Path -LiteralPath $temporaryOutput -PathType Leaf) {
        Remove-Item -LiteralPath $temporaryOutput -Force
    }
}
Write-Output "Manifest written and required artifact integrity checks passed: $outputAbsolute"
