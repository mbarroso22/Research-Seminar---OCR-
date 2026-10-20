# Staged Windows commands — strict synthetic validation v2

**Completed campaign; allowance exhausted.** The six v2 requests and six v1
requests have all been spent. Do not repeat Stages B/C, recreate a ticket or reset
a ledger. Read [the verified v2 review](SYNTHETIC_V2_REVIEW.md). The commands below
are the historical execution guide, not new authorization. Further work is
offline; [the next design](ANSWER_CONTRACT_NEXT_DESIGN.md) is a proposal only.

Use the existing `.venv-answer`, original model/backend files and completed v1
artifacts. **No installs, conversions, OCR or FinanceBench generation.** The patch
is incremental over the delivered answer-feasibility implementation on `828ba06`
(original patch SHA `3a49514a0e0af185c829e07be58750773c9127b1394da396bb27c9a86e32bd1f`).
The original preparation work is not yet on the public branch; do not apply this
incremental patch to a bare clone or reset local changes.

Read [the verified synthetic review](SYNTHETIC_FEASIBILITY_REVIEW.md). Stages A/B
are offline and spend **0 requests**. Stage C explicitly permits **at most six new
synthetic requests**, once, after the original six: cumulative setup ceiling 12.
Stage C remains pending local execution. All original failures are retained.

## A. Preserve and audit the original run; apply the incremental patch

Use a fresh PowerShell window. The repository path below follows the executable
path recorded in the supplied setup manifest (`Research-Seminar-OCR-review`).
Change only `$Repo` if your actual patched checkout moved; the sealed interpreter
path/runtime must still match. Keep the existing `.venv-answer` in place.

```powershell
$ErrorActionPreference = 'Stop'
$Repo = Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-review'
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$AnswerRoot = Join-Path $DataRoot 'answer-generation\qwen3-4b-instruct-2507-v1'
$Assets = Join-Path $AnswerRoot 'assets'
$OldSetup = Join-Path $Assets 'setup_manifest.json'
$OldLedger = Join-Path $Assets 'synthetic_campaign.json'
$OldRun = Join-Path $AnswerRoot 'runs\synthetic-20261018T220936Z'
$Python = Join-Path $Repo '.venv-answer\Scripts\python.exe'
$Patch = Join-Path $env:USERPROFILE 'Downloads\answer-validation-v2-incremental.patch'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$ReviewRoot = Join-Path $AnswerRoot "reviews\strict-v2-$Stamp"
$AuditDir = Join-Path $ReviewRoot 'offline-audit'
$NextRoot = Join-Path $AnswerRoot 'followups\synthetic-contract-v2'
$NextSetup = Join-Path $NextRoot 'setup_manifest.json'
$NextRun = Join-Path $NextRoot 'run'
Set-Location -LiteralPath $Repo
$env:PYTHONPATH = Join-Path $Repo 'src'
foreach ($Required in @($OldSetup,$OldLedger,(Join-Path $OldRun 'run_manifest.json'),$Python,$Patch)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "Required existing file missing: $Required" }
}
if (Test-Path -LiteralPath $ReviewRoot) { throw 'Review directory exists; preserve it.' }
New-Item -ItemType Directory -Path $ReviewRoot -Force | Out-Null

$CodeRoots = @($Repo, (Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-gpu'), (Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-current')) | Select-Object -Unique
function Save-PreservedState([string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { throw "Snapshot exists: $Destination" }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($CodeRoot in $CodeRoots) {
        foreach ($EnvName in @('.venv','.venv-ocr','.venv-ocr-gpu','.venv-answer')) {
            $Exe = Join-Path $CodeRoot "$EnvName\Scripts\python.exe"
            if (Test-Path -LiteralPath $Exe) {
                $Label = (Split-Path -Leaf $CodeRoot) + '-' + $EnvName + '.txt'
                $Packages = & $Exe -m pip freeze --all
                if ($LASTEXITCODE -ne 0) { throw "Cannot inventory $Exe" }
                $Packages | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination $Label)
            }
        }
    }
    $Files = @($OldSetup,$OldLedger,(Join-Path $Repo 'docs\EXPANSION_V1_CONTROL.json'),(Join-Path $Repo 'requirements\answer-windows-py312.lock.txt'),(Join-Path $Repo 'docs\ANSWER_SETUP_LOCK.json'),(Join-Path $Repo 'docs\ANSWER_WINDOWS_WHEELS.json'))
    $Files += @(Get-ChildItem -LiteralPath $OldRun -Recurse -File | ForEach-Object { $_.FullName })
    $Files += @(Get-ChildItem -LiteralPath (Join-Path $Repo 'src\finocr') -Recurse -File -Filter '*.py' | ForEach-Object { $_.FullName })
    foreach ($Root in @((Join-Path $DataRoot 'derived'),(Join-Path $DataRoot 'models'))) {
        if (Test-Path -LiteralPath $Root) {
            $Files += @(Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object { $_.Name -in @('run_manifest.json','model_manifest.json') } | ForEach-Object { $_.FullName })
        }
    }
    $Hashes = $Files | Sort-Object -Unique | ForEach-Object {
        $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_
        "$($Hash.Path)`t$($Hash.Hash)"
    }
    $Hashes | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination 'preserved-hashes.txt')
}
$Before = Join-Path $ReviewRoot 'before'
$After = Join-Path $ReviewRoot 'after'
Save-PreservedState $Before
Compress-Archive -LiteralPath @($OldRun,$OldSetup,$OldLedger) -DestinationPath (Join-Path $ReviewRoot 'original-v1-preserved.zip')
& git status --short
& git -c core.autocrlf=input apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw 'Incremental patch does not match the existing v1 implementation. Preserve local edits; do not reset or apply the old cumulative patch again.' }
& git -c core.autocrlf=input apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
& git diff --exit-code 828ba06 -- src/finocr docs/EXPANSION_V1_CONTROL.json pyproject.toml
if ($LASTEXITCODE -ne 0) { throw 'An existing protected file differs; inspect before continuing.' }
```

The command-scoped `core.autocrlf=input` handles an existing CRLF checkout while
preserving exact saved-response fixture bytes. It does not change Git config.
The fixture attributes retain their bytes in future checkouts too.
The answer dependency lock and model/backend acquisition locks are included in
the before/after byte snapshots. Continue with the offline artifact review:

```powershell
& $Python .\scripts\audit_answer_feasibility.py --run-dir $OldRun --setup $OldSetup --campaign $OldLedger --output $AuditDir
if ($LASTEXITCODE -ne 0) { throw 'Original artifact/hash audit failed; no new inference is allowed.' }
Get-Content -Raw -LiteralPath (Join-Path $AuditDir 'audit.json')
& $Python -m unittest discover -s tests -p 'test_answer_validation.py' -v
if ($LASTEXITCODE -ne 0) { throw 'Strict validation regression tests failed.' }
```

Expected audit: `integrity_verified=true`, `additional_inference_requests=0`,
`strict_mechanical_pass_count=1`, `intended_flash_attention_reproduced=false`.
The audit command exits 0 when artifact integrity succeeds; that is **not** an
inference or model-correctness pass. These new validation tests use standard-library
fixtures and existing modules; do not install pypdf or anything else into the answer
environment. Model outputs in tests are saved failures or simulated fixtures.

For the complete test suite, use an **already existing** baseline environment with
pypdf. The following selects an existing `.venv` from the known code roots:

```powershell
$BaselineCandidates = @($CodeRoots | ForEach-Object { Join-Path $_ '.venv\Scripts\python.exe' } | Where-Object { Test-Path -LiteralPath $_ })
if ($BaselineCandidates.Count -gt 0) {
    $BaselinePython = $BaselineCandidates[0]
    & $BaselinePython -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw 'Complete Windows test suite failed.' }
} else {
    'Complete Windows suite remains pending: no existing baseline .venv was found. Keep the answer environment unchanged.'
}
```

## B. Prepare the separate follow-up seal — still zero inference

This re-audits the original artifacts and rehashes actual model/backend/official
model bytes against their original records. It requires the **same** answer
interpreter/package inventory and conversion record. It does not install, copy,
requantize or redownload models. The old setup is not resealed.

```powershell
if (Test-Path -LiteralPath $NextRoot) { throw 'The single v2 ticket already exists. Preserve it and its ledger; do not delete or rename it to reset a budget.' }
& $Python .\scripts\prepare_answer_followup.py --previous-setup $OldSetup --previous-campaign $OldLedger --previous-run $OldRun
if ($LASTEXITCODE -ne 0) { throw 'Follow-up preparation failed; inspect the console error. Do not change existing environments or bypass fingerprint checks.' }
Get-Content -Raw -LiteralPath $NextSetup
```

The fixed path is `followups\synthetic-contract-v2\setup_manifest.json`.
Its budget is six new requests, one campaign, no retries, cumulative synthetic
ceiling 12, primary/annotated-page budgets both zero. Model/backend/runtime and
prompt identities remain fixed. The new seal records strict schema/validator and
explicit FA-off execution. A second preparation or copied/relocated ticket is
rejected. Keep all preparation artifacts when a later preflight fails.

## C. Optional execution of the explicitly budgeted six requests

This is the only inference command in this guide. Execute it **once**. Do not run
it merely to produce better-looking answers or rerun the historical v1 command.

```powershell
& $Python .\scripts\run_answer_feasibility.py --setup $NextSetup --output $NextRun
$SyntheticExit = $LASTEXITCODE
"V2 synthetic exit code: $SyntheticExit"
if (Test-Path -LiteralPath (Join-Path $NextRun 'run_manifest.json')) {
    $NewManifest = Get-Content -Raw -LiteralPath (Join-Path $NextRun 'run_manifest.json') | ConvertFrom-Json
    $NewManifest | Select-Object status,attempted,request_budget,automated_checks_pass,resource_checks_pass,original_artifacts_unchanged,feasibility_conclusion
    $NewManifest.runtime_observed
} else {
    'Preflight failed before a new run manifest existed. Retain the console error and the separate follow-up setup; the old manifest/ledger must remain untouched.'
}
if (Test-Path -LiteralPath (Join-Path $NextRoot 'synthetic_campaign.json')) {
    Get-Content -Raw -LiteralPath (Join-Path $NextRoot 'synthetic_campaign.json')
}
```

Before any completion, the runner requires explicit FA disabled in runtime logs,
full expected GPU offload, fixed context/KV/batches and **all six original prompt
bytes/token IDs**. A mismatch, including the last capacity prompt, stops before
the first request. Metadata/tokenization calls do not generate completions.

The original six-request ledger at `assets\synthetic_campaign.json` stays unchanged.
The new ledger is `followups\synthetic-contract-v2\synthetic_campaign.json`; its
cache is also separate. Requests are charged before submission, including transport
failures. No resume/retry/reset flag exists. If a deadline or transport failure
stops the campaign after fewer than six requests, retain that state and stop;
unused allowance does not authorize a fresh campaign or resubmitting an answer.

Every raw SSE/response, malformed/invalid parsed result, diagnostic, timing and
memory sample is retained. `validation_failed` is a failure, not a completed pass.
Exit 0 means automated mechanics/resources/device controls passed; semantic support,
financial formula meaning, narrative conclusions and final-answer completeness
still need manual review. Do not infer any FinanceBench correctness from it.
The follow-up changes both strict output grammar and effective FA setting, so
response/timing differences cannot be attributed to either change alone.

## D. Compare preservation snapshots and export the new records

Run this after offline-only stages too. If Stage C was executed, do it afterward.

```powershell
Save-PreservedState $After
$OldNames = @(Get-ChildItem -LiteralPath $Before -File | Select-Object -ExpandProperty Name | Sort-Object)
$NewNames = @(Get-ChildItem -LiteralPath $After -File | Select-Object -ExpandProperty Name | Sort-Object)
if (Compare-Object $OldNames $NewNames) { throw 'Preservation snapshot file inventory differs.' }
foreach ($Name in $OldNames) {
    $Diff = Compare-Object (Get-Content -LiteralPath (Join-Path $Before $Name)) (Get-Content -LiteralPath (Join-Path $After $Name))
    if ($Diff) { $Diff; throw "Preservation difference: $Name" }
}
$Export = Join-Path $ReviewRoot 'synthetic-contract-v2-review.zip'
$ExportItems = @($AuditDir,$Before,$After)
if (Test-Path -LiteralPath $NextRoot) { $ExportItems += $NextRoot }
Compress-Archive -LiteralPath $ExportItems -DestinationPath $Export
Get-FileHash -Algorithm SHA256 -LiteralPath $Export
$Export
```

The export contains audit/control/setup/run records, not model weights or OCR
caches. Keep `original-v1-preserved.zip` too. If a preservation check differs, retain
both snapshots and the error; do not edit the original manifests to make it pass.
No `pip install`, driver update, OCR run, retrieval run, model conversion or
FinanceBench generation is part of this workflow. The three private scoring-key
holds and later benchmark generation remain separate pending work.
