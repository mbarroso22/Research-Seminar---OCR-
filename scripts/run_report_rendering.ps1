[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RendererPath,
    [Parameter(Mandatory=$true)][string]$RunDir,
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [int]$Dpi = 200,
    [switch]$Sample,
    [switch]$Resume
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$documents = Join-Path $DataRoot "audits\financebench_phase0_sector_fixed\manifests\pilot_documents.jsonl"
$pdfs = Join-Path $DataRoot "raw\financebench\pdfs"
$native = Join-Path $DataRoot "derived\native\native-bm25-20261008T051510Z-7fcc394d"
$nativeManifestPath = Join-Path $native "run_manifest.json"
$nativeManifest = Get-Content -LiteralPath $nativeManifestPath -Raw | ConvertFrom-Json
$nativeManifestSha = (Get-FileHash -LiteralPath $nativeManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($nativeManifest.run_id -ne "20261008T051510Z-7b1970c7f4e8" -or $nativeManifest.status -ne "complete" -or
    $nativeManifestSha -ne "5e4213b5e7e65a53e01e78352abeb039c6c79eac7a55c9c0999f304d4d114497") {
    throw "Select the verified original native run."
}
$arguments = @("-m", "finocr.cli", "render-reports", "--documents", $documents, "--pdf-dir", $pdfs,
    "--native-dir", $native, "--renderer", $RendererPath, "--output-dir", $RunDir,
    "--repository-root", $repositoryRoot, "--dpi", "$Dpi", "--expected-documents", "12", "--expected-pages", "2620")
if ($Sample) { $arguments += "--sample" }
if ($Resume) { $arguments += "--resume" }
& $pythonPath @arguments
$renderExitCode = $LASTEXITCODE
$renderManifestPath = Join-Path $RunDir "run_manifest.json"
if ($renderExitCode -ne 0) {
    if (Test-Path -LiteralPath $renderManifestPath -PathType Leaf) {
        throw "Rendering failed (exit code $renderExitCode). Inspect $renderManifestPath and the preceding Python diagnostic."
    }
    throw "Rendering failed (exit code $renderExitCode); no run manifest exists at $renderManifestPath. Inspect the preceding Python diagnostic. Retry without -Resume only when the run directory does not exist; otherwise choose a new directory."
}
if (-not (Test-Path -LiteralPath $renderManifestPath -PathType Leaf)) {
    throw "Renderer returned exit code 0 but no run manifest exists at $renderManifestPath. Inspect the preceding Python diagnostic before retrying."
}
Write-Host "Render directory: $RunDir"
