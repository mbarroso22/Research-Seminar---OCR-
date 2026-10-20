# Staged Windows guide: offline contract repairs only

Use the existing `.venv-answer`, baseline `.venv`, tokenizer assets and pinned
llama.cpp source. **No installs, downloads, conversions, resealing, model/backend
launches, new budgets, OCR/retrieval runs or FinanceBench generation.**

Apply over the existing preparation, validation-v2 and applied
`synthetic-v2-review-docs.patch` edits. Preserve local work when check fails; do not
reset or reapply the earlier cumulative patches. Read
[the implementation/validation status](ANSWER_CONTRACT_REPAIR_STATUS.md).

## A. Snapshot originals and apply the increment

Start a fresh PowerShell window. Paths follow the recorded Review checkout.

```powershell
$ErrorActionPreference = 'Stop'
$Repo = Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-review'
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$AnswerRoot = Join-Path $DataRoot 'answer-generation\qwen3-4b-instruct-2507-v1'
$Assets = Join-Path $AnswerRoot 'assets'
$V1Setup = Join-Path $Assets 'setup_manifest.json'
$V1Ledger = Join-Path $Assets 'synthetic_campaign.json'
$V1Run = Join-Path $AnswerRoot 'runs\synthetic-20261018T220936Z'
$V2Root = Join-Path $AnswerRoot 'followups\synthetic-contract-v2'
$V2Setup = Join-Path $V2Root 'setup_manifest.json'
$V2Ledger = Join-Path $V2Root 'synthetic_campaign.json'
$V2Run = Join-Path $V2Root 'run'
$AnswerPython = Join-Path $Repo '.venv-answer\Scripts\python.exe'
$LlamaSource = Join-Path $AnswerRoot 'tooling\llama.cpp'
$TokenizerRoot = Join-Path $Assets 'official'
$Patch = Join-Path $env:USERPROFILE 'Downloads\answer-contract-offline-repairs.patch'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$ReviewRoot = Join-Path $AnswerRoot "reviews\contract-repair-offline-$Stamp"
$GrammarCheck = Join-Path $ReviewRoot 'grammar-only'
$TokenizerCheck = Join-Path $ReviewRoot 'tokenizer-and-grammar'
$Preserve = @($V1Setup,$V1Ledger,$V1Run,$V2Setup,$V2Ledger,$V2Run)
Set-Location -LiteralPath $Repo
$env:PYTHONPATH = Join-Path $Repo 'src'
$RequiredInputs = @($Patch,$AnswerPython,(Join-Path $LlamaSource 'examples\json_schema_to_grammar.py')) + $Preserve
foreach ($Required in $RequiredInputs) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "Required existing input missing: $Required" }
}
$OriginalV1Campaign = Get-Content -Raw -LiteralPath $V1Ledger | ConvertFrom-Json
$OriginalV2Campaign = Get-Content -Raw -LiteralPath $V2Ledger | ConvertFrom-Json
$Spent = [int]$OriginalV1Campaign.attempted + [int]$OriginalV2Campaign.attempted
if ($Spent -ne 12) { throw 'Unexpected historical ledger total. Preserve both and inspect.' }
"Historical requests spent: $Spent; currently authorized additional requests: 0"
if (Test-Path -LiteralPath $ReviewRoot) { throw 'Review path exists; preserve it.' }
New-Item -ItemType Directory -Path $ReviewRoot | Out-Null

$CodeRoots = @($Repo,(Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-current'),(Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-gpu')) | Select-Object -Unique
function Save-ContractPreservation([string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { throw "Snapshot already exists: $Destination" }
    New-Item -ItemType Directory -Path $Destination | Out-Null
    foreach ($CodeRoot in $CodeRoots) {
        foreach ($EnvName in @('.venv','.venv-ocr','.venv-ocr-gpu','.venv-answer')) {
            $Exe = Join-Path $CodeRoot "$EnvName\Scripts\python.exe"
            if (Test-Path -LiteralPath $Exe) {
                $Label = (Split-Path -Leaf $CodeRoot) + '-' + $EnvName + '.txt'
                $Inventory = & $Exe -m pip freeze --all
                if ($LASTEXITCODE -ne 0) { throw "Cannot inventory existing environment: $Exe" }
                $Inventory | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination $Label)
            }
        }
    }
    $Files = @($V1Setup,$V1Ledger,$V2Setup,$V2Ledger)
    foreach ($RunPath in @($V1Run,$V2Run)) {
        $Files += @(Get-ChildItem -LiteralPath $RunPath -Recurse -File | ForEach-Object { $_.FullName })
    }
    foreach ($Relative in @('docs\EXPANSION_V1_CONTROL.json','docs\ANSWER_SETUP_LOCK.json','docs\ANSWER_WINDOWS_WHEELS.json','requirements\answer-windows-py312.lock.txt','pyproject.toml','docs\SYNTHETIC_V2_REVIEW.md','docs\SYNTHETIC_V2_RESULTS.json')) {
        $Files += (Join-Path $Repo $Relative)
    }
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
Save-ContractPreservation $Before
& git status --short
& git -c core.autocrlf=input apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw 'Increment does not match preparation + v2 + review-docs. Preserve edits; do not reset.' }
& git -c core.autocrlf=input apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
& git diff --exit-code 828ba06 -- src/finocr docs/EXPANSION_V1_CONTROL.json pyproject.toml
if ($LASTEXITCODE -ne 0) { throw 'Protected baseline source/control differs; inspect before proceeding.' }
```

The `core.autocrlf=input` setting is command-scoped. It preserves exact fixture
bytes without changing Git configuration or touching baseline OCR source endings.
Keep every original archive/recovery patch too. New answer-package code changes
its own fingerprint; the historical setup manifests must not be resealed.

## B. Revised-contract tests, then complete suite

This helper captures unittest output without relying on PowerShell stderr
redirection. Each log is new and cannot overwrite a previous log.

```powershell
$TestRunner = @'
import pathlib, subprocess, sys
with pathlib.Path(sys.argv[1]).open('xb') as log:
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', sys.argv[2], '-v'], stdout=log, stderr=subprocess.STDOUT)
print('Test exit code:', result.returncode)
raise SystemExit(result.returncode)
'@
$RepairLog = Join-Path $ReviewRoot 'revised-contract-tests.txt'
& $AnswerPython -c $TestRunner $RepairLog 'test_answer_contract_repair.py'
$RepairExit = $LASTEXITCODE
Get-Content -Tail 8 -LiteralPath $RepairLog
if ($RepairExit -ne 0) { throw 'Revised-contract tests failed. Retain the log; do not alter the environments.' }

$BaselineCandidates = @($CodeRoots | ForEach-Object { Join-Path $_ '.venv\Scripts\python.exe' } | Where-Object { Test-Path -LiteralPath $_ })
if ($BaselineCandidates.Count -eq 0) { throw 'Locate the existing baseline .venv for full tests. Do not install pypdf into the answer environment.' }
$BaselinePython = $BaselineCandidates[0]
$PopplerRoot = Join-Path $DataRoot 'tools\poppler-v26.09.0-0'
$Poppler = @(Get-ChildItem -LiteralPath $PopplerRoot -Recurse -File -Filter 'pdftoppm.exe')
if ($Poppler.Count -ne 1) { throw 'Locate the one existing reviewed Poppler executable; no new install is required.' }
$ContractSavedPath = $env:PATH
$FullLog = Join-Path $ReviewRoot 'complete-tests.txt'
try {
    $env:PATH = $Poppler[0].DirectoryName + ';' + $ContractSavedPath
    & $BaselinePython -c $TestRunner $FullLog 'test*.py'
    $FullExit = $LASTEXITCODE
} finally {
    $env:PATH = $ContractSavedPath
}
Get-Content -Tail 10 -LiteralPath $FullLog
if ($FullExit -ne 0) { throw 'Complete test suite failed; preserve the full log.' }
if (Select-String -LiteralPath $FullLog -Pattern 'skipped=' -Quiet) { throw 'Some checks were skipped; record them as pending rather than a complete validation.' }
```

Development-host checks pass **31 new tests / 250 total**. The new test module is
standard-library-only; complete baseline tests also need the already installed
baseline PDF dependencies and renderer. Legacy mocked lifecycle tests do not make
real requests or grant a budget. The genuine pause tests leave the guard intact.

## C. Pinned schema conversion and fixture gate — zero inference

```powershell
& $AnswerPython .\scripts\check_answer_contract.py --llama-source $LlamaSource --output $GrammarCheck --preserve $Preserve
$GrammarExit = $LASTEXITCODE
if (Test-Path -LiteralPath (Join-Path $GrammarCheck 'offline_conformance.json')) {
    Get-Content -Raw -LiteralPath (Join-Path $GrammarCheck 'offline_conformance.json')
} else {
    'Preflight stopped before a report existed. Retain the console error; no campaign manifest should be created.'
}
if ($GrammarExit -ne 0) { throw 'Offline grammar/fixture gate failed. Do not relax or bypass checks.' }
```

Expected status is `grammar_and_fixture_checks_pass_tokenizer_pending`, explicitly
not a complete packing check. The gate runs the checksum-verified local b6500
Python converter with UTF-8 file/stdout handling. A portable character recognizer
then checks handwritten/adversarial response fixtures. No weights, vocabulary,
backend, GPU, server or inference endpoint is used by this stage. Unknown converter
source, warnings, unsupported grammar or unexpected acceptance stop the gate.

## D. Complete local tokenizer/packing gate — still zero inference

Use only the original local tokenizer files from the existing asset bundle.
The loader checks their pinned hashes and existing tokenizer dependency versions.
It opens tokenizer/config files, never the model weight files. It first verifies
all six historical v2 prompt bytes/token IDs, then checks the revised instruction
and prospective capacity calculation question against the unchanged packing caps.

```powershell
& $AnswerPython .\scripts\check_answer_contract.py --llama-source $LlamaSource --output $TokenizerCheck --tokenizer-root $TokenizerRoot --historical-v2-run $V2Run --preserve $Preserve
$TokenizerExit = $LASTEXITCODE
if (Test-Path -LiteralPath (Join-Path $TokenizerCheck 'offline_conformance.json')) {
    $Offline = Get-Content -Raw -LiteralPath (Join-Path $TokenizerCheck 'offline_conformance.json') | ConvertFrom-Json
    $Offline | Select-Object kind,status,contract_version,inference_executed,additional_inference_authorized,remaining_authorized_requests,protected_artifacts_unchanged,baseline_source_and_control_unchanged
    $Offline.tokenizer_check.cases | Select-Object case_id,input_tokens,evidence_tokens,overhead_tokens
} else {
    'Tokenizer/preflight failed before a report existed. Preserve the console error and original tokenizer/environment.'
}
if ($TokenizerExit -ne 0) { throw 'Offline tokenizer/packing gate failed; preserve evidence and stop.' }
if ($Offline.status -ne 'offline_checks_pass') { throw 'The complete offline gate did not pass.' }
```

Expected revised input counts from host tokenization: **620, 613, 644, 636, 623,
5120**. Capacity remains 4096 evidence + 1024 overhead and five body prefixes of
800 tokens. These are tokenization/setup checks, not model outputs or a new
experimental result. No inference allowance is created even when all checks pass.
If tokenizer identity/parity or budgets differ, retain the report and stop; do not
change prompts, padding, environments or assets to hide the mismatch.

## E. Preservation comparison and export

```powershell
Save-ContractPreservation $After
$BeforeNames = @(Get-ChildItem -LiteralPath $Before -File | Select-Object -ExpandProperty Name | Sort-Object)
$AfterNames = @(Get-ChildItem -LiteralPath $After -File | Select-Object -ExpandProperty Name | Sort-Object)
if (Compare-Object $BeforeNames $AfterNames) { throw 'Preservation file inventory changed.' }
foreach ($Name in $BeforeNames) {
    $Delta = Compare-Object (Get-Content -LiteralPath (Join-Path $Before $Name)) (Get-Content -LiteralPath (Join-Path $After $Name))
    if ($Delta) { $Delta; throw "Preservation difference: $Name" }
}
$Export = Join-Path $ReviewRoot 'offline-contract-repair-review.zip'
Compress-Archive -LiteralPath @($Before,$After,$GrammarCheck,$TokenizerCheck,$RepairLog,$FullLog) -DestinationPath $Export
Get-FileHash -Algorithm SHA256 -LiteralPath $Export
$Export
```

The export contains offline checks, identities and preservation evidence, not
model weights or OCR cache pages. The v2 result and the previously saved common-v2
audit of v1 each remain 1/6 mechanical passes; neither is a revised-contract model
result. All original failures are retained. The cumulative real request count
stays **12**, currently authorized remaining **0**. Do not execute the historical
run/prepare/seal commands; they now explicitly refuse to proceed. No new setup,
ticket, campaign ledger or backend cache should appear. FinanceBench generation
and private-rubric adjudication remain separate pending work.
