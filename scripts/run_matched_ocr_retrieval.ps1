[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$OcrDir,
    [Parameter(Mandatory=$true)][string]$ExpansionDir,
    [Parameter(Mandatory=$true)][string]$RunDir,
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data")
)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$baselinePython = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$native = Join-Path $DataRoot "derived\native\native-bm25-20261008T051510Z-7fcc394d"
$tasks = Join-Path $DataRoot "audits\financebench_phase0_sector_fixed\manifests\pilot_tasks.jsonl"
$checks = @(
    @{ Path = (Join-Path $native "run_manifest.json"); SHA = "5e4213b5e7e65a53e01e78352abeb039c6c79eac7a55c9c0999f304d4d114497" },
    @{ Path = (Join-Path $ExpansionDir "run_manifest.json"); SHA = "4eb18afc2eecc460cdd7b38b50773625ed8a59dfd862ada787395223b31bba63" },
    @{ Path = $tasks; SHA = "1d1bfa444a3041b3e51be9535ff276fc89fa3d7985231a0bd7f4aa6746395356" }
)
foreach ($check in $checks) {
    if ((Get-FileHash -LiteralPath $check.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $check.SHA) {
        throw "Use the frozen original native/expansion/task artifacts: $($check.Path)"
    }
}
& $baselinePython -m finocr.cli compare-native-ocr --native-dir $native --expansion-dir $ExpansionDir --ocr-dir $OcrDir `
    --output-dir $RunDir --tasks $tasks --repository-root $repositoryRoot
$comparisonExitCode = $LASTEXITCODE
if ($comparisonExitCode -ne 0) { throw "Matched retrieval failed (exit code $comparisonExitCode); inspect the diagnostic and any saved manifest. No pending/diagnostic OCR cache can supply full-pilot scores." }
Write-Host "Matched comparison directory: $RunDir"
