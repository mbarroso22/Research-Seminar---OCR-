[CmdletBinding()]
param(
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [string]$BaselineDir = "",
    [string]$ExpansionDir = "",
    [string]$TasksPath = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    throw "Repository-local Python not found: $pythonPath"
}
$nativeRoot = Join-Path $DataRoot "derived\native"
if (-not $BaselineDir) {
    $BaselineDir = Join-Path $nativeRoot "native-bm25-20261008T051510Z-7fcc394d"
}
$nativeManifest = Get-Content -LiteralPath (Join-Path $BaselineDir "run_manifest.json") -Raw | ConvertFrom-Json
if ($nativeManifest.status -ne "complete" -or $nativeManifest.run_id -ne "20261008T051510Z-7b1970c7f4e8" -or
    $nativeManifest.manifest_totals.documents -ne 12 -or $nativeManifest.manifest_totals.pages -ne 2620 -or
    $nativeManifest.manifest_totals.questions -ne 24) {
    throw "Select the verified 12-report / 2,620-page / 24-question original native run."
}
$expansionRunId = "20261009T020622Z-76a16239e13d"
if (-not $ExpansionDir) {
    $expansionRuns = @(Get-ChildItem -LiteralPath $nativeRoot -Directory -Filter "query-expansion-*" | Where-Object {
        $candidatePath = Join-Path $_.FullName "run_manifest.json"
        if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
            try {
                $candidate = Get-Content -LiteralPath $candidatePath -Raw | ConvertFrom-Json
                $candidate.run_id -eq $expansionRunId -and $candidate.status -eq "complete"
            } catch { $false }
        } else { $false }
    })
    if ($expansionRuns.Count -ne 1) {
        throw "Expected exactly one saved expansion-v1 run. Supply -ExpansionDir with its existing full path."
    }
    $ExpansionDir = $expansionRuns[0].FullName
}
$reference = Get-Content -LiteralPath (Join-Path $ExpansionDir "run_manifest.json") -Raw | ConvertFrom-Json
if ($reference.status -ne "complete" -or $reference.run_id -ne $expansionRunId) {
    throw "ExpansionDir must select the verified frozen expansion-v1 run $expansionRunId."
}
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$comparisonDir = Join-Path $nativeRoot "section-context-$stamp-$suffix"
$cliArguments = @("-m", "finocr.cli", "compare-section-context", "--baseline-dir", $BaselineDir,
                  "--expansion-dir", $ExpansionDir, "--output-dir", $comparisonDir,
                  "--repository-root", $repositoryRoot)
if ($TasksPath) { $cliArguments += @("--tasks", $TasksPath) }
Write-Host "Frozen expansion directory: $ExpansionDir"
Write-Host "New run directory: $comparisonDir"
& $pythonPath @cliArguments
$comparisonExit = $LASTEXITCODE
Write-Host "Exit code: $comparisonExit"
Write-Host "Run directory: $comparisonDir"
if ($comparisonExit -ne 0) {
    throw "Section comparison failed. Inspect any new run manifest; failed outputs are not accepted results."
}
