[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RenderDir,
    [Parameter(Mandatory=$true)][string]$RunDir,
    [ValidateSet("Diagnostic", "Full")][string]$Mode = "Diagnostic",
    [string]$Selection = "",
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [switch]$Resume,
    [int]$MaxPages = 0
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$ocrPython = Join-Path $repositoryRoot ".venv-ocr\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $ocrPython -PathType Leaf)) { throw "Existing .venv-ocr is required; do not install into .venv." }
$models = Join-Path $DataRoot "models\paddleocr-3.3.2-mobile-en"
$modelManifest = Join-Path $models "model_manifest.json"
if ((Get-FileHash -LiteralPath $modelManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne "d0a91a2378b843c0fcc3ea007e4505072277b55f3b6aa07ffab15c3af8a07cf4") {
    throw "Use the existing verified CPU-smoke model bundle; retain any different bundle as a separate condition."
}
$renderManifestPath = Join-Path $RenderDir "run_manifest.json"
$renderManifest = Get-Content -LiteralPath $renderManifestPath -Raw | ConvertFrom-Json
if ((Get-FileHash -LiteralPath $renderManifestPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne "1ff37ad01d37e3d961b3ae0d27805a1dde244023f7cd830c3bbab876c8c5ebce" -or
    $renderManifest.status -ne "complete" -or $renderManifest.full_report_rendering_complete -ne $true -or
    $renderManifest.cohort_totals.documents -ne 12 -or $renderManifest.page_record_count -ne 2620 -or $renderManifest.contract.dpi -ne 200) {
    throw "Use the reviewed complete 12-report/2620-page 200-DPI rendering cache."
}
$arguments = @("-m", "finocr.cli", "ocr-reports", "--render-dir", $RenderDir, "--models-dir", $models,
    "--output-dir", $RunDir, "--repository-root", $repositoryRoot, "--page-timeout-seconds", "600",
    "--initialization-timeout-seconds", "180")
if ($Mode -eq "Diagnostic") {
    if (-not $Selection) { throw "Diagnostic mode requires the source-only table selection file." }
    $arguments += @("--selection", $Selection)
} elseif ($Selection) { throw "Full mode uses every report page; omit -Selection." }
if ($Resume) { $arguments += "--resume" }
if ($MaxPages -lt 0) { throw "MaxPages must be zero (unlimited) or positive." }
if ($MaxPages -gt 0) { $arguments += @("--max-pages", "$MaxPages") }
& $ocrPython @arguments
$ocrExitCode = $LASTEXITCODE
$manifestPath = Join-Path $RunDir "run_manifest.json"
if ($ocrExitCode -ne 0) {
    if (Test-Path -LiteralPath $manifestPath -PathType Leaf) {
        throw "OCR ended with exit code $ocrExitCode. Inspect $manifestPath and worker logs; resume with the same cache/settings. Exit code 3 means paused or explicit page failures."
    }
    throw "OCR preflight failed (exit code $ocrExitCode), before a manifest exists. Inspect the preceding diagnostic; retain inputs and use a fresh output path."
}
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "OCR returned success without its manifest." }
Write-Host "OCR directory: $RunDir"
