[CmdletBinding()]
param(
    [string]$DataRoot = (Join-Path $env:USERPROFILE "financial-ocr-data"),
    [string]$AuditDir = "",
    [string]$RunDir = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Repository-local Python not found: $python. Use the existing project .venv."
}
if (-not $AuditDir) {
    $AuditDir = Join-Path $DataRoot "audits\financebench_phase0_sector_fixed"
}
if (-not $RunDir) {
    $stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
    $suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
    $RunDir = Join-Path $DataRoot "derived\native\native-bm25-$stamp-$suffix"
}
$documents = Join-Path $AuditDir "manifests\pilot_documents.jsonl"
$tasks = Join-Path $AuditDir "manifests\pilot_tasks.jsonl"
$pdfDir = Join-Path $DataRoot "raw\financebench\pdfs"
foreach ($file in @($documents, $tasks)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Pilot manifest not found: $file"
    }
}
if (-not (Test-Path -LiteralPath $pdfDir -PathType Container)) {
    throw "PDF directory not found: $pdfDir"
}
if (Test-Path -LiteralPath $RunDir) {
    throw "RunDir already exists. Choose a new directory to preserve prior outputs."
}

$arguments = @(
    "-m", "finocr.cli", "native-baseline",
    "--documents", $documents,
    "--tasks", $tasks,
    "--pdf-dir", $pdfDir,
    "--output-dir", $RunDir,
    "--repository-root", $repoRoot,
    "--expected-documents", "12",
    "--expected-pages", "2620",
    "--expected-questions", "24",
    "--k1", "1.2", "--b", "0.75", "--k", "1", "3", "5"
)
Write-Host "Run directory: $RunDir"
& $python @arguments
$runExit = $LASTEXITCODE
Write-Host "Exit code: $runExit"
Write-Host "Run directory: $RunDir"
if ($runExit -eq 1) {
    Write-Host "Completed with extraction failures. Inspect extraction_summary.json before interpreting metrics."
}
if ($runExit -eq 2) {
    Write-Host "Run failed. If created, run_manifest.json records the failure; use a new RunDir for a retry."
}
exit $runExit
