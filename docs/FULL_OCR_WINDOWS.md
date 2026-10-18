# Resumable full-report OCR and matched retrieval on Windows

**Status update 2026-10-18:** both full OCR runs and matched comparisons are
complete and independently verified in [NATIVE_OCR_PILOT_RESULTS.md](NATIVE_OCR_PILOT_RESULTS.md).
The setup/pending statements below describe the original execution stage;
retain these instructions as history. Reuse the completed immutable caches.

Continue from `61a696d` using the existing `.venv`, `.venv-ocr`, model bundle and
complete 200-DPI rendering. **No installation commands are needed.** Expansion
v1 stays frozen at primary **k=5**. Read the verified setup observations in
[OCR_SETUP_REVIEW.md](OCR_SETUP_REVIEW.md).

The latest 16 feature tests and complete 157-test suite passed on Linux with no
skips. Real small PDF rendering fixtures and simulated OCR workers were used.
Execution of these new Windows wrappers, the financial-table inspection, full
OCR and matched corpus retrieval remains pending on the researcher's machine.

## 1. Apply the appropriate patch, preserving the recovery checkpoint

Keep `full-ocr-recovery.patch` unchanged as the cancellation checkpoint. Its
SHA-256 is `55f380d84dcc361ea8065e841f15dabf006ae763eb28f0e1112fbd7ab23554b4`.
The final patch is cumulative against `61a696d`; it includes all 13 required
files, including both new documentation files and the experiment-state update.
The companion `full-report-ocr-from-recovery.patch` contains only the remaining
changes after that exact recovery checkpoint. **Apply one path below**, according
to the current checkout. Do not layer the cumulative patch over recovery edits.

Open PowerShell in the existing checkout, which already has both environments:

```powershell
Set-Location 'C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current'
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = (Get-Location).Path
$Base = '61a696d9ca7dd0c505b1de662ca3eaea57ed3e9d'
if ((git rev-parse HEAD).Trim() -ne $Base) { throw 'Use the 61a696d checkout; retain other work separately.' }
git status --short
```

For a clean `61a696d` checkout, after saving the final patch in Downloads:

```powershell
$Patch = Join-Path $env:USERPROFILE 'Downloads\full-report-ocr-final.patch'
git apply --check -- $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch check failed; preserve local edits and inspect the conflict.' }
git apply -- $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
```

If the exact recovered edits are already present, use this block instead:

```powershell
$Patch = Join-Path $env:USERPROFILE 'Downloads\full-report-ocr-from-recovery.patch'
git apply --check -- $Patch
if ($LASTEXITCODE -ne 0) { throw 'Recovery delta does not match this checkout; preserve current edits.' }
git apply -- $Patch
if ($LASTEXITCODE -ne 0) { throw 'Recovery delta application failed.' }
```

Neither route resets files or deletes the recovery patch. Check the final diff:

```powershell
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace check failed.' }
git status --short
```

## 2. Resolve existing inputs and record the baseline environment

Run subsequent blocks in this same session. New output paths are outside Git.
Do not create `$OcrDir` or `$ComparisonDir` in advance; the runners create them.

```powershell
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$BaselinePython = Join-Path $Repo '.venv\Scripts\python.exe'
$OcrPython = Join-Path $Repo '.venv-ocr\Scripts\python.exe'
$NativeDir = Join-Path $DataRoot 'derived\native\native-bm25-20261008T051510Z-7fcc394d'
$RenderDir = Join-Path $DataRoot 'derived\rendered\poppler-200dpi-20261013T043945Z-f407621a'
$ModelsDir = Join-Path $DataRoot 'models\paddleocr-3.3.2-mobile-en'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$AuditDir = Join-Path $DataRoot "audits\full-ocr-$Stamp"
$OcrDir = Join-Path $DataRoot "derived\ocr\cpu-full-200dpi-$Stamp"
$ComparisonDir = Join-Path $DataRoot "derived\retrieval\native-ocr-expansion-v1-$Stamp"
$Selection = Join-Path $AuditDir 'financial-table-selection.json'
$TableReview = Join-Path $AuditDir 'financial-table-review.json'
$BeforeDir = Join-Path $AuditDir 'baseline-before'
$AfterDir = Join-Path $AuditDir 'baseline-after'
$null = New-Item -ItemType Directory -Path $AuditDir
foreach ($p in @($BaselinePython, $OcrPython, (Join-Path $RenderDir 'run_manifest.json'), (Join-Path $ModelsDir 'model_manifest.json'))) {
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Required existing input missing: $p" }
}
& $BaselinePython -c 'import pathlib,finocr; assert pathlib.Path(finocr.__file__).resolve().parents[2] == pathlib.Path.cwd().resolve(); print(finocr.__file__)'
if ($LASTEXITCODE -ne 0) { throw 'Baseline environment must import this checkout; do not reinstall dependencies.' }
$RuntimeProbe = @'
import sys, struct, pathlib, finocr, importlib.metadata as m
assert sys.version_info[:3] == (3, 12, 10) and struct.calcsize("P") * 8 == 64
assert pathlib.Path(finocr.__file__).resolve().parents[2] == pathlib.Path.cwd().resolve()
pins = {"paddlepaddle": "3.3.0", "paddleocr": "3.3.2", "paddlex": "3.3.10"}
actual = {key: m.version(key) for key in pins}
assert actual == pins, actual
print(sys.version)
print(actual)
print(finocr.__file__)
'@
$RuntimeProbe | & $OcrPython -
if ($LASTEXITCODE -ne 0) { throw 'Existing OCR runtime/source differs; inspect it before continuing.' }
& .\scripts\check_ocr_machine.ps1 -DataRoot $DataRoot -OutputDir $BeforeDir
```

This checks metadata without initializing Paddle. The worker also verifies the
actual CPU device and non-CUDA build at initialization. Both source import checks
must point into this checkout. Keep the same code/package versions throughout a
cache, including resumes; a changed condition requires a new cache.

Find the saved expansion control by its recorded run ID, without guessing a
directory suffix. Its manifest hash is pinned in the wrapper as well:

```powershell
$ExpansionMatches = @(Get-ChildItem -LiteralPath (Join-Path $DataRoot 'derived') -Recurse -File -Filter 'run_manifest.json' | ForEach-Object {
    $Candidate = Get-Content -LiteralPath $_.FullName -Raw | ConvertFrom-Json
    if ($null -ne $Candidate.PSObject.Properties['run_id'] -and $Candidate.run_id -eq '20261009T020622Z-76a16239e13d') { $_.DirectoryName }
})
if ($ExpansionMatches.Count -ne 1) { throw 'Expected exactly one saved expansion v1 reference; inspect duplicate/missing runs.' }
$ExpansionDir = $ExpansionMatches[0]
if ((Get-FileHash -LiteralPath (Join-Path $ExpansionDir 'run_manifest.json') -Algorithm SHA256).Hash.ToLowerInvariant() -ne '4eb18afc2eecc460cdd7b38b50773625ed8a59dfd862ada787395223b31bba63') { throw 'Expansion reference identity differs.' }
$Paths = [ordered]@{ Repo=$Repo; DataRoot=$DataRoot; NativeDir=$NativeDir; RenderDir=$RenderDir; ModelsDir=$ModelsDir; AuditDir=$AuditDir; OcrDir=$OcrDir; ComparisonDir=$ComparisonDir; ExpansionDir=$ExpansionDir; Selection=$Selection; TableReview=$TableReview; BeforeDir=$BeforeDir; AfterDir=$AfterDir; Stamp=$Stamp }
$PathsFile = Join-Path $AuditDir 'run-paths.json'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText($PathsFile, ($Paths | ConvertTo-Json) + "`n", $Utf8)
Write-Host "Retain this paths file: $PathsFile"
```

## 3. Run the complete suite locally without changing either environment

Make the existing portable Poppler executable visible only for this test block.
No packages or tools are downloaded. This exercises the actual Windows PDF
fixtures too; confirm **157 tests, OK, no skips** before starting the diagnostic.

```powershell
$PopplerRoot = Join-Path $DataRoot 'tools\poppler-v26.09.0-0'
$Poppler = @(Get-ChildItem -LiteralPath $PopplerRoot -Recurse -File -Filter 'pdftoppm.exe')
if ($Poppler.Count -ne 1) { throw 'Locate the one existing reviewed Poppler executable.' }
$SavedPath = $env:PATH
$TestRunner = @'
import pathlib, subprocess, sys
result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
pathlib.Path(sys.argv[1]).write_text(result.stdout, encoding="utf-8")
print(result.stdout, end="")
sys.exit(result.returncode)
'@
try {
    $env:PATH = $Poppler[0].DirectoryName + ';' + $SavedPath
    $TestRunner | & $BaselinePython - (Join-Path $AuditDir 'tests-windows.txt')
    $TestExit = $LASTEXITCODE
} finally { $env:PATH = $SavedPath }
if ($TestExit -ne 0) { throw 'Windows tests failed; retain the log.' }
```

## 4. Select and OCR eight source-only financial tables

The selector reads native source text and rendering identities only, never QA
annotations. Expected zero-based pages are AMD 2015 **55,57**, Best Buy 2015
**58,60**, Boeing 2015 **50,52**, PepsiCo 2015 **73,76**. This preview has been
checked against the supplied native cache; OCR quality remains unmeasured.

```powershell
& $BaselinePython -m finocr.cli select-ocr-tables --native-dir $NativeDir --render-dir $RenderDir --output $Selection
if ($LASTEXITCODE -ne 0) { throw 'Source table selection failed.' }
& .\scripts\run_full_report_ocr.ps1 -DataRoot $DataRoot -RenderDir $RenderDir -RunDir $OcrDir -Mode Diagnostic -Selection $Selection
$Diagnostic = Get-Content -LiteralPath (Join-Path $OcrDir 'run_manifest.json') -Raw | ConvertFrom-Json
if ($Diagnostic.status -ne 'diagnostic_complete' -or $Diagnostic.coverage.completed_engine_pages -ne 8 -or $Diagnostic.coverage.pending_pages -ne 2612 -or $Diagnostic.full_ocr_coverage) { throw 'Inspect incomplete diagnostic and explicit failures before proceeding.' }
& $BaselinePython -m finocr.cli review-ocr-tables --native-dir $NativeDir --ocr-dir $OcrDir --selection $Selection --output $TableReview
if ($LASTEXITCODE -ne 0) { throw 'Table review export failed.' }
Get-Content -LiteralPath $TableReview -Raw
```

The aggregate has all **2,620** source-page records even during this diagnostic;
unselected pages are pending. `blank_ocr_text` is a completed engine response,
reported separately from nonempty text and requiring inspection. Model startup
is reused across pages within a report, then reset at report boundaries.

Open each selected PNG and its retained raw OCR JSON/line boxes. Check years,
currency/scale, decimals, parentheses/minus signs, and row/column associations.
For a reproducible list of inspection paths:

```powershell
$Review = Get-Content -LiteralPath $TableReview -Raw | ConvertFrom-Json
$Review.pages | ForEach-Object {
    [pscustomobject]@{ Report=$_.doc_id; Page=$_.page_index; Status=$_.ocr_status; Image=(Join-Path $RenderDir $_.image_path); Record=(Join-Path $OcrDir $_.record_path); Raw=(Join-Path (Split-Path -Parent (Join-Path $OcrDir $_.record_path)) 'raw_ocr_result.json') }
} | Format-List
```

The numeric-token overlap is approximate and does not assess column placement
or financial correctness. It is not CER/WER; native extraction is not manual
gold. Do not copy native text, answers, justifications or evidence snippets into
OCR records. Retain a short manual review alongside the JSON. If settings require
a change, retain this cache and create a separately named condition; do not edit
its raw outputs or tune retrieval on the diagnostic.

Before the full run updates aggregate metadata, save an immutable diagnostic
snapshot. It includes all eight raw attempts and the complete pending-page plan:

```powershell
$DiagnosticSnapshot = Join-Path $AuditDir 'diagnostic-snapshot'
$null = New-Item -ItemType Directory -Path $DiagnosticSnapshot
Copy-Item -LiteralPath $OcrDir -Destination $DiagnosticSnapshot -Recurse
Copy-Item -LiteralPath $Selection,$TableReview -Destination $DiagnosticSnapshot
Compress-Archive -Path (Join-Path $DiagnosticSnapshot '*') -DestinationPath (Join-Path $AuditDir 'financial-table-diagnostic.zip')
```

## 5. Extend the same cache to all reports, then resume if needed

After inspecting the diagnostic, omit `-Selection` and use `-Resume` on the
**same** `$OcrDir`. The eight verified completed pages are reused:

```powershell
& .\scripts\run_full_report_ocr.ps1 -DataRoot $DataRoot -RenderDir $RenderDir -RunDir $OcrDir -Mode Full -Resume
```

Each immutable attempt retains request/source hashes, raw output if returned,
normalized lines, boxes/confidences and an atomic `record.json`. Worker sessions
retain startup results and logs. The OS-backed cache lock prevents concurrent
writers; the lock file can remain after exit and must not be deleted to force
another writer. Model initialization is reused within each report; a timeout or
exception closes that worker and later pages can start another. Deadlines remain
180 seconds for initialization and 600 seconds per page.

To interrupt, press Ctrl+C once and wait for the process to finish recording its
state. Then rerun the same full command above. Resume rechecks actual image and
model hashes, runtime, code, configuration and prior commits. Successful and blank
pages are reused; explicit failed/timed-out/interrupted pages are retried in new
attempt directories. Prior raw outputs and failure histories remain intact.
If a process was forcibly terminated before committing an attempt, its partial
files are retained as an interrupted attempt and retried.

For a deliberate short chunk, use the following **instead of** the unlimited
command. `-MaxPages` limits new attempts in that invocation, not total coverage:

```powershell
& .\scripts\run_full_report_ocr.ps1 -DataRoot $DataRoot -RenderDir $RenderDir -RunDir $OcrDir -Mode Full -Resume -MaxPages 25
```

The CLI returns **3** for a paused/partial run, and the wrapper raises an error
with the manifest path. Inspect status and resume; this is expected for a chunk
with pending pages. A preflight error before a manifest exists explicitly says
so; inspect the preceding diagnostic rather than looking for a nonexistent file.

To reopen a PowerShell session, set `$PathsFile` to the printed path, then:

```powershell
$Saved = Get-Content -LiteralPath $PathsFile -Raw | ConvertFrom-Json
foreach ($Entry in $Saved.PSObject.Properties) { Set-Variable -Name $Entry.Name -Value $Entry.Value }
Set-Location $Repo
$BaselinePython = Join-Path $Repo '.venv\Scripts\python.exe'
$OcrPython = Join-Path $Repo '.venv-ocr\Scripts\python.exe'
```

Inspect completion before retrieval:

```powershell
$FinalOcr = Get-Content -LiteralPath (Join-Path $OcrDir 'run_manifest.json') -Raw | ConvertFrom-Json
$FinalOcr.coverage | ConvertTo-Json -Depth 8
if ($FinalOcr.mode -ne 'full' -or $FinalOcr.status -notin @('complete','partial') -or $FinalOcr.coverage.pending_pages -ne 0 -or $FinalOcr.coverage.expected_pages -ne 2620 -or $FinalOcr.coverage.documents -ne 12) { throw 'Finalize all full-report page records before retrieval.' }
```

Prefer retrying transient failures before comparison. A final `partial` cache
with no pending pages can be compared explicitly as **failure-inclusive**.
Failed and blank pages remain full-report candidates with empty text; none are
dropped. `full_ocr_coverage=true` requires all pages to have completed engine
responses, including explicitly reported blanks; it does not mean nonempty or
correct transcription. Diagnostic, paused and interrupted caches cannot supply
full-pilot retrieval scores.

## 6. Run the matched expansion-v1 comparison

```powershell
& .\scripts\run_matched_ocr_retrieval.ps1 -DataRoot $DataRoot -OcrDir $OcrDir -ExpansionDir $ExpansionDir -RunDir $ComparisonDir
Get-Content -LiteralPath (Join-Path $ComparisonDir 'comparison_report.md') -Raw
& .\scripts\check_ocr_machine.ps1 -DataRoot $DataRoot -OutputDir $AfterDir -CompareWith (Join-Path $BeforeDir 'machine_inventory.json')
```

The wrapper uses baseline `.venv` for retrieval and pins the original native,
expansion-reference and 24-question file identities. No dependencies are installed.
Do not commit or change packages between the before/after inventory pair: editable
package inventories can encode the current Git commit.

Only the page representation changes. Both conditions index every page in all
12 reports with the same tokenizer, stopwords, BM25 `k1=1.2, b=0.75`, binary query
term frequency, frozen financial expansion, deterministic tie order and questions.
All IDs remain zero-based physical PDF pages. No heading context is added.
Expanded query/audit records must reproduce exactly; native full scores/ranks
must reproduce the saved expansion control. Both prediction files are saved
before parsing evidence labels. OCR receives images/source identity only, and
indexes receive page text only. Answers and justifications never enter either.

The comparison produces:

| File | Review purpose |
|---|---|
| `run_manifest.json` | Input/code identities, expansion reproduction, coverage and timings |
| `native_predictions.jsonl`, `ocr_predictions.jsonl` | Full within-report rankings, including zero-score ties |
| `retrieval_queries.jsonl`, `expanded_retrieval_queries.jsonl`, `query_expansion_audit.jsonl` | Minimal queries and unchanged expansion trace |
| `index_stats.jsonl` | Both representations of all 12 reports and build times |
| `comparison_metrics.json` | Recall/Hit/Complete at 1/3/5, MRR, deltas, per-question gained/lost evidence pages and ranks |
| `comparison_report.md` | Execution summary and five-question multi-page completeness |

Primary reporting remains **k=5**. Smaller cutoffs and MRR are diagnostics.
Review each gain/regression and every evidence-page rank in all five multi-page
questions, including OCR status. Zero-score ties can include evidence by chance;
read no-match counts and failure coverage with retrieval metrics.

OCR ingestion timing includes recorded diagnostic invocations and retries.
Page-attempt wall time excludes separately recorded worker startup wall time;
SDK initialization/inference timings overlap parent observations and must not
be added again. Unfinished invocation/attempt durations are explicitly unknown.
Original rendering wall time covers its last retained invocation only. Retrieval
uses fixed native-then-OCR order. These are descriptive logs, not repeated
latency, throughput extrapolations or energy measurements.

## 7. Preserve outputs for verification

Keep the complete local OCR cache, including every attempt and worker log.
Archive the finished comparison, diagnostic audit and OCR cache separately;
no rendered image tree, model weights or virtual environment is in `$OcrDir`.

```powershell
$ExportDir = Join-Path $DataRoot "exports\full-ocr-$Stamp"
$null = New-Item -ItemType Directory -Path $ExportDir
Compress-Archive -LiteralPath $ComparisonDir -DestinationPath (Join-Path $ExportDir 'matched-retrieval.zip')
Compress-Archive -LiteralPath $AuditDir -DestinationPath (Join-Path $ExportDir 'diagnostic-and-environment.zip')
Compress-Archive -LiteralPath $OcrDir -DestinationPath (Join-Path $ExportDir 'full-ocr-cache.zip')
Get-ChildItem -LiteralPath $ExportDir -File | Get-FileHash -Algorithm SHA256
```

The saved paths file restores `$Stamp` too. If a large archive exceeds the local archiver's limit,
retain the full tree and split archives by report without dropping failure or
retry histories. Summary files alone do not verify raw-output checksums. Retain
the original rendered images/model bundle locally; the cache preserves exact
rendering metadata snapshots rather than duplicating those large inputs.

The generated summary is execution output awaiting independent artifact review.
Supply the real outputs before recording verified new OCR/retrieval findings.
This development-pilot comparison measures retrieval sensitivity to native/OCR
text, not answer correctness, CER/WER or held-out generalization.
