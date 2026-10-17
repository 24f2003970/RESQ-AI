param(
    [string]$OutputPath = "artifacts/part16-release-manifest.json",
    [string]$HostedActionsRun = "PENDING"
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$outputAbsolute = Join-Path $repoRoot $OutputPath
$frontendDist = Join-Path $repoRoot "frontend/dist"
$artifactRoot = Join-Path $repoRoot "backend/ml_artifacts"

function Get-RelativeSha256([string]$RelativePath, [switch]$NormalizeLf) {
    $absolutePath = Join-Path $repoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $absolutePath -PathType Leaf)) {
        return $null
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
$gitBranch = (& git -C $repoRoot branch --show-current).Trim()
$dirty = [bool]((& git -C $repoRoot status --porcelain).Trim())
$modelReportPath = Join-Path $artifactRoot "reliability_evaluation.json"
$modelReport = Get-Content -LiteralPath $modelReportPath -Raw | ConvertFrom-Json

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
        python_lockfile = [ordered]@{ path = "backend/requirements.txt"; sha256 = Get-RelativeSha256 "backend/requirements.txt" }
        frontend_lockfile = [ordered]@{ path = "frontend/package-lock.json"; sha256 = Get-RelativeSha256 "frontend/package-lock.json" }
    }
    model_artifacts = [ordered]@{
        model = [ordered]@{ path = "backend/ml_artifacts/flood_exposure_v1.joblib"; sha256 = Get-RelativeSha256 "backend/ml_artifacts/flood_exposure_v1.joblib" }
        metadata = [ordered]@{ path = "backend/ml_artifacts/model_metadata.json"; normalized_lf_sha256 = Get-RelativeSha256 "backend/ml_artifacts/model_metadata.json" -NormalizeLf }
        calibrator = [ordered]@{ path = "backend/ml_artifacts/flood_exposure_platt_v1.joblib"; sha256 = Get-RelativeSha256 "backend/ml_artifacts/flood_exposure_platt_v1.joblib" }
        distribution_support = [ordered]@{ path = "backend/ml_artifacts/distribution_support_v1.json"; sha256 = Get-RelativeSha256 "backend/ml_artifacts/distribution_support_v1.json" }
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
$manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $outputAbsolute -Encoding utf8
Write-Output "Manifest written: $outputAbsolute"
