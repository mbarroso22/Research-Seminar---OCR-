[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$RenderDir,
    [Parameter(Mandatory=$true)][string]$RunDir,
    [Parameter(Mandatory=$true)][string]$Selection,
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [switch]$Resume
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repositoryRoot ".venv-ocr-gpu\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Use the separate .venv-ocr-gpu; retain .venv and .venv-ocr." }
$models = Join-Path $DataRoot "models\paddleocr-3.3.2-mobile-en"
$checks = @(
    @{ Path=(Join-Path $models "model_manifest.json"); SHA="d0a91a2378b843c0fcc3ea007e4505072277b55f3b6aa07ffab15c3af8a07cf4" },
    @{ Path=(Join-Path $RenderDir "run_manifest.json"); SHA="1ff37ad01d37e3d961b3ae0d27805a1dde244023f7cd830c3bbab876c8c5ebce" },
    @{ Path=$Selection; SHA="7f3b4c5a8e7b9fedafb79b3623c780e30fcf7f26b427d4322b10c681e30fc5d2" }
)
foreach ($check in $checks) {
    if ((Get-FileHash -LiteralPath $check.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $check.SHA) { throw "Fixed GPU diagnostic input changed: $($check.Path)" }
}
$arguments = @("-m", "finocr.cli", "ocr-reports", "--device", "gpu:0", "--render-dir", $RenderDir,
    "--models-dir", $models, "--output-dir", $RunDir, "--repository-root", $repositoryRoot,
    "--selection", $Selection, "--page-timeout-seconds", "600", "--initialization-timeout-seconds", "180")
if ($Resume) { $arguments += "--resume" }
& $python @arguments
$ocrExit = $LASTEXITCODE
if ($ocrExit -ne 0) {
    $manifest = Join-Path $RunDir "run_manifest.json"
    if (Test-Path -LiteralPath $manifest -PathType Leaf) { throw "GPU diagnostic exit $ocrExit. Inspect $manifest and worker logs; do not launch a full GPU run." }
    throw "GPU preflight failed before a manifest exists. Inspect the preceding diagnostic; retain inputs and choose a fresh output path."
}
Write-Host "GPU diagnostic cache: $RunDir. Compare with the retained CPU snapshot and inspect all eight tables before considering full execution."
