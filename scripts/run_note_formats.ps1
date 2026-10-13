[CmdletBinding()]
param(
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [string]$BaselineDir = "",
    [string]$ExpansionDir = "",
    [string]$SectionDir = "",
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

function Find-ReferenceRun([string]$suppliedPath, [string]$pattern, [string]$runId, [string]$label) {
    if (-not $suppliedPath) {
        $candidateRuns = @(Get-ChildItem -LiteralPath $nativeRoot -Directory -Filter $pattern | Where-Object {
            $candidatePath = Join-Path $_.FullName "run_manifest.json"
            if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
                try {
                    $candidate = Get-Content -LiteralPath $candidatePath -Raw | ConvertFrom-Json
                    $candidate.run_id -eq $runId -and $candidate.status -eq "complete"
                } catch { $false }
            } else { $false }
        })
        if ($candidateRuns.Count -ne 1) {
            throw "Expected exactly one saved $label run $runId. Supply its explicit directory parameter."
        }
        $suppliedPath = $candidateRuns[0].FullName
    }
    $reference = Get-Content -LiteralPath (Join-Path $suppliedPath "run_manifest.json") -Raw | ConvertFrom-Json
    if ($reference.status -ne "complete" -or $reference.run_id -ne $runId) {
        throw "$label directory must select the verified run $runId."
    }
    return $suppliedPath
}

$ExpansionDir = Find-ReferenceRun $ExpansionDir "query-expansion-*" "20261009T020622Z-76a16239e13d" "expansion-v1"
$SectionDir = Find-ReferenceRun $SectionDir "section-context-*" "20261013T010312Z-967cd9567b9c" "section-v1"
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$comparisonDir = Join-Path $nativeRoot "note-formats-$stamp-$suffix"
$cliArguments = @("-m", "finocr.cli", "compare-note-formats", "--baseline-dir", $BaselineDir,
                  "--expansion-dir", $ExpansionDir, "--section-dir", $SectionDir,
                  "--output-dir", $comparisonDir, "--repository-root", $repositoryRoot)
if ($TasksPath) { $cliArguments += @("--tasks", $TasksPath) }
Write-Host "Frozen expansion directory: $ExpansionDir"
Write-Host "Saved section-v1 directory: $SectionDir"
Write-Host "New run directory: $comparisonDir"
& $pythonPath @cliArguments
$comparisonExit = $LASTEXITCODE
Write-Host "Exit code: $comparisonExit"
Write-Host "Run directory: $comparisonDir"
if ($comparisonExit -ne 0) {
    throw "Note-format comparison failed. Inspect any new manifest; failed outputs are not accepted results."
}
