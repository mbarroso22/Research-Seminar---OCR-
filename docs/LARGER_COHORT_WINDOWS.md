# New larger-company exploratory retrieval study — Windows guide

This is a separately requested exploratory study after the original pilot gate
failed. It uses 20 companies, 43 reports, 7,003 pages and 58 questions, selected
from the pinned local release by company/report metadata and PDF availability.
The original pilot and six-company results remain unchanged. Lockheed Martin
is also excluded conservatively because LMT occurred in earlier FinLongDocQA
project material. No exhaustive prior-exposure certification is claimed.

Primary: question-weighted macro Recall@5, GPU OCR minus native, using frozen
expansion-v1 BM25. Secondary: semantic and equal-RRF comparisons; Hit/Complete@5;
all multi-page questions; k=1/3; equal-company sensitivity; 10,000 paired
company-cluster bootstrap resamples, seed 20261105, 95% percentile intervals.
No new pass/fail promotion gate or unchanged 10/24 threshold is applied.

Encoder and OCR settings are retained from the completed experiments. The BGE
encoder is CPU ONNX, not a GPU or larger model upgrade. This larger study needs
new native extraction/rendering/GPU OCR for its new PDFs; it does not redo the
completed cohorts. Question projections contain task_id/doc_id/question only.
Preparation validates evidence into a separate scorer-only file. Retrieval
control/check-only stages never parse scorer labels; the real comparison reads
them for evaluation only after all six ranking files are saved.

## Evidence and delivery limits

The source intake ZIP was verified as
`651a2fbfc6cf095b180e9eafdf13de5a9c106648d0294293256b6d51ff9fc76e`.
All 105 intake-listed files verified. Source official JSONL hashes and all
43 PDF identities are bound in the proposed cohort. Study membership is not
selected by answers, evidence ranks, or expected method performance.

Offline: 213 available legacy tests and 20 new tests passed, no skips. The intake
omitted scripts/diagnose_native_cache.py, so the six unchanged diagnostic tests
could not run locally. Stage 1 below runs all **239** tests on Windows, using
the existing diagnostic script. Encoder and OCR calls in the new tests are
mocked. No new-cohort extraction, rendering, OCR, real embedding or retrieval
result was produced while preparing this delivery. Windows patch application,
tests, GPU runtime verification and corpus execution remain unconfirmed until
the operator supplies their logs.

The original hybrid_comparison.py and semantic.py are unchanged. Existing
native_baseline.py and cli.py receive only the new larger_exploratory group.
Separate larger_cohort.py/larger_hybrid.py and run_larger_study.py implement
the new cohort, control preparation, comparison, and validation. The old pilot
manifest/task guard stays intact. No package installation, environment creation,
model download, branch change, commit, push or answer-generation step is needed.

Use ordinary PowerShell, no administrator shell, activation, .ps1 files or
execution-policy changes. Keep one window open. Run only the first unfinished
stage. Preserve failed or interrupted outputs and share the precise error.
The comparison has no resume. Render/OCR support explicit compatible resume,
but no generic retry block is supplied. Never apply the old pilot package again.

## 1. Extract the package; apply and validate offline

Save larger-cohort-exploratory-20261105.zip into Downloads. Extract it to a NEW
folder using File Explorer's Extract All. The folder contains
setup_larger_windows.py, patches, files, study, references, and this guide.
Run setup_larger_windows.py from that extracted folder with the existing
verified encoder Python, as shown in the delivery message. Do not run it twice.

The setup script verifies every delivery file and source preimage, inventories
all established environments, saves a source-only prepatch backup, chooses one
applicable LF/CRLF patch, applies it, runs all 239 offline tests, checks the new
policy and existing encoder assets without inference, and compares environment
inventories. It records new nonoverlapping paths and a historical-state snapshot.
It installs nothing and performs no new-cohort processing.

Expected: 239 tests, zero skips, OK; larger_policy_pass;
existing_encoder_assets_verified_no_inference 7;
larger_setup_complete_no_new_cohort_processing. Upload the printed setup-review.zip
and checksum before proceeding. Its audit_directory is the exact session path
to use below. If setup fails after applying the patch, preserve the audit and
share the error; do not rerun setup or choose another audit by default.

## 2. Load saved paths, freeze inputs, verify the existing GPU runtime

Set $LAudit to the exact audit_directory printed by setup (not the earlier
pilot audit or the intake export directory). The following Read-Host accepts
that literal path so no guessed timestamp or placeholder enters execution.

```powershell
$LAudit = Read-Host 'Paste the exact audit_directory printed by larger-study setup'
$L = Get-Content -LiteralPath (Join-Path $LAudit 'paths.json') -Raw | ConvertFrom-Json
$LRunner = Join-Path $L.Repo 'scripts\run_larger_study.py'
$LUtf8 = New-Object System.Text.UTF8Encoding($false)

function Invoke-LargerStep {
    param([string]$Name, [string]$Python, [string[]]$CommandArguments)
    $Log = Join-Path $LAudit ($Name + '.txt')
    $Record = Join-Path $LAudit ($Name + '-time.json')
    if ((Test-Path -LiteralPath $Log) -or (Test-Path -LiteralPath $Record)) {
        throw "Existing stage evidence; preserve it and stop: $Name"
    }
    $Timer = [Diagnostics.Stopwatch]::StartNew()
    $StepExit = -1
    Start-Transcript -LiteralPath $Log -NoClobber | Out-Null
    try {
        & $Python @CommandArguments
        $StepExit = $LASTEXITCODE
    } finally {
        $Timer.Stop()
        Stop-Transcript | Out-Null
        $Value = [ordered]@{
            step=$Name; executable=$Python; arguments=$CommandArguments
            exit_code=$StepExit; elapsed_seconds=$Timer.Elapsed.TotalSeconds
        }
        [IO.File]::WriteAllText($Record, ($Value | ConvertTo-Json -Depth 5), $LUtf8)
    }
    if ($StepExit -ne 0) { throw "Step $Name failed ($StepExit); preserve evidence and stop." }
}

. {
    $ErrorActionPreference = 'Stop'
    Invoke-LargerStep -Name 'freeze' -Python $L.EncoderPython -CommandArguments @(
        '-I',$LRunner,'freeze','--study-dir',(Join-Path $L.Package 'study'),
        '--data-root',$L.DataRoot,'--output-dir',$L.Freeze,'--repository-root',$L.Repo
    )
    Invoke-LargerStep -Name 'gpu-runtime' -Python $L.GpuPython -CommandArguments @(
        '-I',$LRunner,'check-runtime','--lock',(Join-Path $L.Package 'references\gpu-active-wheel-lock.txt'),
        '--reference',$L.OriginalGpuReference,'--renderer',$L.Renderer,
        '--models-dir',$L.OcrModels,'--output',(Join-Path $LAudit 'gpu-runtime.json'),
        '--repository-root',$L.Repo
    )
}
```

Expected frozen totals: 20/43/7003/58. This step checks cross-report/invalid
evidence annotations before execution; an issue stops the entire freeze and
must be reviewed rather than silently dropping a question. GPU check requires
the preserved 74-package Windows closure, original Poppler executable/DLL bytes,
OCR asset bytes, CUDA 11.8 and gpu:0. Paddle's numerical setup check is not OCR.
It does not install or repair anything. Share freeze/runtime errors before any
new report processing. Do not replace model, provider, pins or cohort to get past
a demonstrated error.

## 3. New native extraction and source-only render sample

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Invoke-LargerStep -Name 'native' -Python $L.EncoderPython -CommandArguments @(
        '-I','-m','finocr.cli','native-baseline',
        '--documents',(Join-Path $L.Freeze 'documents.jsonl'),
        '--tasks',(Join-Path $L.Freeze 'retrieval-queries.jsonl'),
        '--pdf-dir',(Join-Path $L.DataRoot 'raw\financebench\pdfs'),
        '--output-dir',$L.Native,'--repository-root',$L.Repo,
        '--expected-documents','43','--expected-pages','7003','--expected-questions','58',
        '--experimental-group','larger_exploratory','--skip-evaluation'
    )
    Invoke-LargerStep -Name 'render-sample' -Python $L.EncoderPython -CommandArguments @(
        '-I','-m','finocr.cli','render-reports',
        '--documents',(Join-Path $L.Freeze 'documents.jsonl'),
        '--native-dir',$L.Native,'--renderer',$L.Renderer,'--output-dir',$L.Render,
        '--repository-root',$L.Repo,'--dpi','200',
        '--expected-documents','43','--expected-pages','7003','--sample'
    )
    $Sample = Get-Content -LiteralPath (Join-Path $L.Render 'run_manifest.json') -Raw | ConvertFrom-Json
    if ($Sample.status -ne 'sample_complete') { throw 'Expected successful source render sample.' }
    $Images = Get-Content -LiteralPath (Join-Path $L.Render 'render_pages.jsonl') |
        ForEach-Object { $_ | ConvertFrom-Json } | Where-Object status -eq 'ok'
    $MaxBytes = ($Images | ForEach-Object { $_.image_identity.size_bytes } | Measure-Object -Maximum).Maximum
    $EstimatedBudget = [long]($MaxBytes * 7003 * 2 + 5GB)
    $Free = (Get-PSDrive -Name ([IO.Path]::GetPathRoot($L.DataRoot).Substring(0,1))).Free
    [ordered]@{sampled_images=@($Images).Count; free_bytes=$Free; conservative_sample_based_budget_bytes=$EstimatedBudget} |
        ConvertTo-Json
    if ($Free -lt $EstimatedBudget) { throw 'Insufficient sample-based storage budget; preserve sample and review capacity.' }
}
```

Expected native status complete with 43/7003/58 and evaluation skipped; sample
status sample_complete, 129 source-selected images. The size budget uses twice
the largest sampled page times total pages plus 5 GiB. It is conservative for
the observed sample, not a guarantee about every unsampled image. No evidence
labels are used for native extraction, rendering or sample selection.

## 4. Extend that same render plan and OCR the new cohort once

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Invoke-LargerStep -Name 'render-full' -Python $L.EncoderPython -CommandArguments @(
        '-I','-m','finocr.cli','render-reports',
        '--documents',(Join-Path $L.Freeze 'documents.jsonl'),
        '--native-dir',$L.Native,'--renderer',$L.Renderer,'--output-dir',$L.Render,
        '--repository-root',$L.Repo,'--dpi','200',
        '--expected-documents','43','--expected-pages','7003','--resume'
    )
    Invoke-LargerStep -Name 'gpu-ocr-full' -Python $L.GpuPython -CommandArguments @(
        '-I','-m','finocr.cli','ocr-reports',
        '--render-dir',$L.Render,'--models-dir',$L.OcrModels,'--output-dir',$L.Ocr,
        '--repository-root',$L.Repo,'--device','gpu:0',
        '--page-timeout-seconds','600','--initialization-timeout-seconds','180'
    )
}
```

The render --resume here extends only this new study's intentional sample;
verified images are reused. This is not a resume/rerun of any old cohort. Both
full manifests must be complete, with 7,003 pages and no failed/pending OCR
pages. Blank OCR responses remain completed candidates. No silent CPU fallback.

## 5. Prepare fixed BM25 controls and verify them without encoder inference

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Invoke-LargerStep -Name 'prepare-controls' -Python $L.EncoderPython -CommandArguments @(
        '-I',$LRunner,'controls','--freeze-dir',$L.Freeze,'--native-dir',$L.Native,
        '--ocr-dir',$L.Ocr,'--output-dir',$L.Controls,'--repository-root',$L.Repo
    )
    Invoke-LargerStep -Name 'input-check' -Python $L.EncoderPython -CommandArguments @(
        '-I',$LRunner,'compare','--freeze-dir',$L.Freeze,'--native-dir',$L.Native,
        '--reference-dir',$L.Controls,'--ocr-dir',$L.Ocr,'--models-dir',$L.EncoderModels,
        '--output-dir',$L.Check,'--repository-root',$L.Repo,'--check-only'
    )
}
```

Expected controls_prepared_no_encoder_no_labels, then inputs_verified_no_encoder,
both expansion_control_reproduced true, totals 43/7003/58, promotion_gate null.
All native/PDF/render/OCR raw-commit lineage and query identities are checked.
Controls are created with the fixed expansion-v1 BM25 settings, then replayed
before encoder loading. No labels are parsed and no model assets are loaded by
these stages. Keep outputs; neither stage is a measured semantic result.

## 6. One real fixed encoder/retrieval run

```powershell
. {
    $ErrorActionPreference = 'Stop'
    Invoke-LargerStep -Name 'comparison' -Python $L.EncoderPython -CommandArguments @(
        '-I',$LRunner,'compare','--freeze-dir',$L.Freeze,'--native-dir',$L.Native,
        '--reference-dir',$L.Controls,'--ocr-dir',$L.Ocr,'--models-dir',$L.EncoderModels,
        '--output-dir',$L.Output,'--repository-root',$L.Repo
    )
}
```

Expected status complete, both controls reproduced, 348 logical full rankings
(6 x 58), all questions and all physical page candidates retained. Encoding is
native then OCR, with shared queries and retained windows/vectors. Labels are
read by this retrieval run only after all six rankings exist. The new run has
no promotion gate; report its paired estimates, uncertainty and multi-page
coverage regardless of direction. There is no hybrid resume or automatic retry.
Keep partial/failed output and logs if interrupted. Do not tune after outcomes.

## 7. Validate saved artifacts and export

```powershell
. {
    $ErrorActionPreference = 'Stop'
    & $L.EncoderPython -I (Join-Path $L.Package 'finalize_larger_windows.py') --audit $LAudit
    if ($LASTEXITCODE -ne 0) { throw 'Finalization failed; preserve evidence and share the error.' }
}
```

This rescoring/validation uses saved vectors/rankings, not encoder inference.
It rechecks artifact and input hashes, metrics, semantic/RRF replay, paired
company uncertainty and sensitivity; compares environment inventories and
code/Git/historical manifests; and exports results, source, frozen scorer-only
tasks and setup/provenance records. Report PDFs/PNGs/raw OCR payloads, model
weights and environments remain in their original new-study directories; the
review ZIP records identities, not a complete backup of those payloads.

Upload the printed review ZIP and SHA-256. Review it before claiming a result.
Package inventories establish package-level preservation, not full venv byte
identity. No code commit/push or external backup verification is performed by
this workflow. Answer generation remains paused.
