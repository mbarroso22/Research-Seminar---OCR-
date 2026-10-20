# Qualification runner: staged Windows guide, offline validation only

Historical runner-v1 guide. For the authorization-binding increment, preservation
closeout and new preparation arguments, use [QUALIFICATION_BINDING_WINDOWS.md](QUALIFICATION_BINDING_WINDOWS.md).

Apply this **increment** over preparation + validation-v2 + review-docs + the
offline contract-repair patch. Do not apply it to bare `828ba06`. README and all
existing source/config/result files are omitted. Read the unchanged
[qualification plan](ANSWER_CONTRACT_QUALIFICATION_PLAN.md).

**Current authorization is implementation/offline tests only.** Stages A–E below
perform no inference and create no execution ticket, setup seal, campaign ledger
or allowance. Do not install/update packages, models, compiler or drivers. The
existing and new public inference entry points remain unconditionally paused.
Mocks create disposable test fixtures, not research execution campaigns.

## A. Preserve originals, then apply

Start a fresh PowerShell window. Keep the prior review ZIP, patches and recovery
patch. The existing full grammar/tokenizer review must remain available locally.

```powershell
$ErrorActionPreference = 'Stop'
$Repo = Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-review'
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$AnswerRoot = Join-Path $DataRoot 'answer-generation\qwen3-4b-instruct-2507-v1'
$Assets = Join-Path $AnswerRoot 'assets'
$V2Root = Join-Path $AnswerRoot 'followups\synthetic-contract-v2'
$V2Setup = Join-Path $V2Root 'setup_manifest.json'
$LlamaSource = Join-Path $AnswerRoot 'tooling\llama.cpp'
$AnswerPython = Join-Path $Repo '.venv-answer\Scripts\python.exe'
$Patch = Join-Path $env:USERPROFILE 'Downloads\answer-qualification-runner-incremental.patch'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$ReviewRoot = Join-Path $AnswerRoot "reviews\qualification-implementation-$Stamp"
$CampaignAnchor = Join-Path $AnswerRoot 'followups\synthetic-contract-v3-qualification'
$env:PYTHONPATH = Join-Path $Repo 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location -LiteralPath $Repo
foreach ($Required in @($Patch,$AnswerPython,$V2Setup,$LlamaSource)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "Required existing input missing: $Required" }
}
if (Test-Path -LiteralPath $CampaignAnchor) { throw 'An existing qualification anchor must be preserved. Do not delete/restart it.' }
if (Test-Path -LiteralPath $ReviewRoot) { throw 'Offline review directory already exists.' }
New-Item -ItemType Directory -Path $ReviewRoot | Out-Null
$V2 = Get-Content -Raw -LiteralPath $V2Setup | ConvertFrom-Json
$V1Setup = $V2.lineage.setup_path
$V1Ledger = $V2.lineage.campaign_path
$V1Run = $V2.lineage.run_path
$V2Ledger = Join-Path $V2Root 'synthetic_campaign.json'
$V2Run = Join-Path $V2Root 'run'
$History = @($V1Setup,$V1Ledger,$V1Run,$V2Setup,$V2Ledger,$V2Run)
$CodeRoots = @($Repo,(Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-current'),(Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-gpu')) | Select-Object -Unique
function Save-QualificationPreservation([string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { throw "Snapshot already exists: $Destination" }
    New-Item -ItemType Directory -Path $Destination | Out-Null
    foreach ($CodeRoot in $CodeRoots) {
        foreach ($EnvName in @('.venv','.venv-ocr','.venv-ocr-gpu','.venv-answer')) {
            $Exe = Join-Path $CodeRoot "$EnvName\Scripts\python.exe"
            if (Test-Path -LiteralPath $Exe) {
                $Inventory = & $Exe -m pip freeze --all
                if ($LASTEXITCODE -ne 0) { throw "Cannot inventory existing environment: $Exe" }
                $Label = (Split-Path -Leaf $CodeRoot) + '-' + $EnvName + '.txt'
                $Inventory | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination $Label)
            }
        }
    }
    $Files = @($V1Setup,$V1Ledger,$V2Setup,$V2Ledger)
    foreach ($Run in @($V1Run,$V2Run)) {
        $Files += @(Get-ChildItem -LiteralPath $Run -Recurse -File | ForEach-Object { $_.FullName })
    }
    foreach ($Relative in @('docs\EXPANSION_V1_CONTROL.json','docs\ANSWER_SETUP_LOCK.json','docs\ANSWER_WINDOWS_WHEELS.json','requirements\answer-windows-py312.lock.txt','pyproject.toml','README.md','docs\SYNTHETIC_V2_REVIEW.md','docs\SYNTHETIC_V2_RESULTS.json')) {
        $Files += (Join-Path $Repo $Relative)
    }
    foreach ($Relative in @('src\finocr','src\finocr_answer')) {
        $Files += @(Get-ChildItem -LiteralPath (Join-Path $Repo $Relative) -Recurse -File -Filter '*.py' | ForEach-Object { $_.FullName })
    }
    $Files += @(Get-ChildItem -LiteralPath (Join-Path $Repo 'scripts') -File -Filter '*answer*.py' | ForEach-Object { $_.FullName })
    foreach ($Root in @((Join-Path $DataRoot 'derived'),(Join-Path $DataRoot 'models'))) {
        if (Test-Path -LiteralPath $Root) {
            $Files += @(Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object { $_.Name -in @('run_manifest.json','model_manifest.json') } | ForEach-Object { $_.FullName })
        }
    }
    $Files | Sort-Object -Unique | ForEach-Object {
        $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $_
        "$($Hash.Path)`t$($Hash.Hash)"
    } | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination 'preserved-hashes.txt')
}
$Before = Join-Path $ReviewRoot 'before'
$After = Join-Path $ReviewRoot 'after'
Save-QualificationPreservation $Before
& git status --short
$ExistingPlan = Join-Path $Repo 'docs\ANSWER_CONTRACT_QUALIFICATION_PLAN.md'
$PlanExclude = @()
if (Test-Path -LiteralPath $ExistingPlan) {
    $CheckPlan = @'
import hashlib, pathlib, sys
actual = hashlib.sha256(pathlib.Path(sys.argv[1]).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
if actual != 'd730ca069e7a28fccc73e3c9e6c29df1983d7df16f7a39b612fbcb207ef94ecc':
    raise SystemExit('Different local plan: preserve it and resolve before applying')
'@
    & $AnswerPython -c $CheckPlan $ExistingPlan
    if ($LASTEXITCODE -ne 0) { throw 'Existing plan differs; it has not been moved or overwritten.' }
    Copy-Item -LiteralPath $ExistingPlan -Destination (Join-Path $ReviewRoot 'original-identical-plan.md')
    $PlanExclude = @('--exclude=docs/ANSWER_CONTRACT_QUALIFICATION_PLAN.md')
}
& git -c core.autocrlf=input apply --check @PlanExclude $Patch
if ($LASTEXITCODE -ne 0) { throw 'Increment does not match the offline-repair checkout. Preserve all edits and inspect; do not reset.' }
& git -c core.autocrlf=input apply @PlanExclude $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
```

The optional existing plan is checksum-checked and copied into the review evidence,
then excluded from patch application so its original bytes remain in place. A
different local plan stops the commands. No earlier patch is reapplied.
If you commit the new implementation, do so **before stage D**; later code/HEAD/
dirty-state changes invalidate the offline preparation binding.

## B. Mocked qualification tests and complete suite

No server, model or GPU inference is used by the tests. Actual metadata/stream
helpers are tested only with mocked HTTP/processes; all accounting fixtures live
inside temporary test directories. The unchanged pause is tested without mocking it.

```powershell
$TestRunner = @'
import pathlib, subprocess, sys
with pathlib.Path(sys.argv[1]).open('xb') as log:
    result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-p', sys.argv[2], '-v'], stdout=log, stderr=subprocess.STDOUT)
print('Test exit code:', result.returncode)
raise SystemExit(result.returncode)
'@
$RunnerLog = Join-Path $ReviewRoot 'qualification-tests.txt'
& $AnswerPython -c $TestRunner $RunnerLog 'test_qualification_runner.py'
$RunnerExit = $LASTEXITCODE
Get-Content -Tail 8 -LiteralPath $RunnerLog
if ($RunnerExit -ne 0) { throw 'Qualification tests failed; preserve the log.' }
$BaselineCandidates = @($CodeRoots | ForEach-Object { Join-Path $_ '.venv\Scripts\python.exe' } | Where-Object { Test-Path -LiteralPath $_ })
if ($BaselineCandidates.Count -eq 0) { throw 'Locate the existing baseline .venv. Do not install PDF dependencies into the answer environment.' }
$BaselinePython = $BaselineCandidates[0]
$PopplerRoot = Join-Path $DataRoot 'tools\poppler-v26.09.0-0'
$Poppler = @(Get-ChildItem -LiteralPath $PopplerRoot -Recurse -File -Filter 'pdftoppm.exe')
if ($Poppler.Count -ne 1) { throw 'Locate the one existing reviewed Poppler executable; do not install another.' }
$QualificationSavedPath = $env:PATH
$FullLog = Join-Path $ReviewRoot 'complete-tests.txt'
try {
    $env:PATH = $Poppler[0].DirectoryName + ';' + $QualificationSavedPath
    & $BaselinePython -c $TestRunner $FullLog 'test*.py'
    $FullExit = $LASTEXITCODE
} finally {
    $env:PATH = $QualificationSavedPath
}
Get-Content -Tail 10 -LiteralPath $FullLog
if ($FullExit -ne 0) { throw 'Complete test suite failed.' }
if (Select-String -LiteralPath $FullLog -Pattern 'skipped=' -Quiet) { throw 'Skipped checks remain pending.' }
```

## C. Standalone native schema-converter probe — no model/server

This compiles a small wrapper against unchanged b6500 converter source. It links
no model, sampler or server. The existing pinned source must be clean. The native
and Python converters must agree on the frozen 18,525-byte grammar.

Use an **already installed** compiler: clang++, g++, or `cl.exe` from an existing
Visual Studio Developer PowerShell session. No compiler/package installation is
authorized. If none is available, stop after B, export the offline evidence from
E, and report native/Windows preflight as pending. Do not bypass the native gate.

```powershell
$Compiler = $null
foreach ($Name in @('clang++.exe','g++.exe','cl.exe')) {
    $Found = Get-Command $Name -ErrorAction SilentlyContinue
    if ($Found) { $Compiler = $Found.Source; break }
}
if (-not $Compiler) { throw 'No existing supported compiler. Keep inference paused; native preflight is pending.' }
$ProbeRoot = Join-Path $ReviewRoot 'native-probe'
& $AnswerPython .\scripts\build_qualification_probe.py --llama-source $LlamaSource --output $ProbeRoot --compiler $Compiler
if ($LASTEXITCODE -ne 0) { throw 'Offline native converter build failed; retain its log if created.' }
$NativeBuild = Join-Path $ProbeRoot 'build.json'
```

The build records compiler/helper/converter/executable hashes. It does not alter
the existing backend or model. It is an offline build check, not a GPU feasibility
result. A native-probe build directory may be retained after a failed build; use
a new offline review path for a later offline check, never erase original evidence.

## D. Offline preparation and real pause check — zero allowance

Select the existing reviewed full conformance directory. This selects only a
report whose status is `offline_checks_pass`, not the grammar-only directory.
The checker revalidates exact contract/core/evaluator/baseline identities, both
complete historical trees/ledgers, existing model/backend/official bytes, full
Python runtime, device/driver, disk/RAM limits, native grammar conversion and
local historical/revised tokenizer parity. It reads weight files to hash them;
it never initializes a model or launches the server.

```powershell
$Reports = @(Get-ChildItem -LiteralPath (Join-Path $AnswerRoot 'reviews') -Recurse -File -Filter 'offline_conformance.json' | Where-Object {
    $Value = Get-Content -Raw -LiteralPath $_.FullName | ConvertFrom-Json
    $Value.status -eq 'offline_checks_pass' -and $Value.contract_version -eq 'typed-response-v3-offline'
} | Sort-Object LastWriteTimeUtc -Descending)
if ($Reports.Count -eq 0) { throw 'Locate the original successful full contract-repair review; do not fabricate a report.' }
$ContractReview = $Reports[0].DirectoryName
"Using preserved full contract review: $ContractReview"
$Hardware = Join-Path $ReviewRoot 'hardware.json'
if (Test-Path -LiteralPath $Hardware) { throw 'Preserve the existing hardware snapshot; use a new offline review directory.' }
@{
    os = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber
    cpu = Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors
    system = Get-CimInstance Win32_ComputerSystem | Select-Object TotalPhysicalMemory
} | ConvertTo-Json -Depth 5 | Set-Content -Encoding UTF8 -LiteralPath $Hardware
$Preparation = Join-Path $ReviewRoot 'preparation'
$Preserve = @($Before,$Hardware)
& $AnswerPython .\scripts\check_qualification.py --v2-setup $V2Setup --contract-review $ContractReview --llama-source $LlamaSource --native-build $NativeBuild --output $Preparation --preserve $Preserve
$PreparationExit = $LASTEXITCODE
$PreparationReport = Join-Path $Preparation 'offline_preparation.json'
if (Test-Path -LiteralPath $PreparationReport) {
    $Offline = Get-Content -Raw -LiteralPath $PreparationReport | ConvertFrom-Json
    $Offline | Select-Object kind,status,inference_executed,additional_inference_authorized,remaining_authorized_requests,execution_enabled,preservation_pass
} else {
    'Preflight failed before a report existed. Preserve the console error; no execution manifest/ledger should exist.'
}
if ($PreparationExit -ne 0) { throw 'Offline preparation failed. Do not relax identities/resource limits.' }
if ($Offline.status -ne 'offline_ready_for_separate_review_not_authorization') { throw 'Offline preparation did not pass.' }

# This verifies refusal, not execution. The supplied path is deliberately absent.
$PauseLog = Join-Path $ReviewRoot 'pause-check.json'
& $AnswerPython .\scripts\run_qualification.py --preparation (Join-Path $ReviewRoot 'deliberately-absent.json') | Set-Content -Encoding UTF8 -LiteralPath $PauseLog
$PauseExit = $LASTEXITCODE
$Pause = Get-Content -Raw -LiteralPath $PauseLog | ConvertFrom-Json
if ($PauseExit -ne 2 -or $Pause.status -ne 'inference_paused') { throw 'Unexpected pause behavior.' }
if (Test-Path -LiteralPath $CampaignAnchor) { throw 'An execution anchor unexpectedly appeared. Preserve it and stop.' }
```

The old frozen source fingerprint remains an identity for the offline repair.
The new runner gets a **separate implementation manifest/fingerprint** including
code, tests, scripts, plan, frozen references, HEAD and dirty status. It does not
reseal either old setup. Offline preparation is not accepted as an authorization.

## E. Compare preservation and export offline evidence

This stage is also usable after B/C when later checks are pending. It exports
whatever offline evidence exists, including failures; it performs no inference.

```powershell
Save-QualificationPreservation $After
$BeforeNames = @(Get-ChildItem -LiteralPath $Before -File | Select-Object -ExpandProperty Name | Sort-Object)
$AfterNames = @(Get-ChildItem -LiteralPath $After -File | Select-Object -ExpandProperty Name | Sort-Object)
if (Compare-Object $BeforeNames $AfterNames) { throw 'Preservation inventory changed.' }
foreach ($Name in $BeforeNames) {
    $Delta = Compare-Object (Get-Content -LiteralPath (Join-Path $Before $Name)) (Get-Content -LiteralPath (Join-Path $After $Name))
    if ($Delta) { $Delta; throw "Preservation mismatch: $Name" }
}
if (Test-Path -LiteralPath $CampaignAnchor) { throw 'A real campaign must not have been created by offline validation.' }
$Archive = Join-Path (Split-Path -Parent $ReviewRoot) ("qualification-implementation-$Stamp-review.zip")
& $AnswerPython .\scripts\export_qualification.py --root $ReviewRoot --archive $Archive
if ($LASTEXITCODE -ne 0) { throw 'Evidence export failed; preserve the partial archive and evidence.' }
Get-FileHash -Algorithm SHA256 -LiteralPath $Archive
$Archive
```

The exporter includes every file plus a SHA-256 inventory; it rechecks source
preservation, ZIP integrity and each archived file, then writes a checksum sidecar
outside the source evidence tree. It refuses existing/nested export paths. Model
weights and OCR pages are not copied into this review archive; their identities
and available cache manifests remain in the evidence. No remote machine is touched.

## F. Later authorization and execution — not authorized here

Stop after E and review the exact implementation and offline evidence. A future
authorization must identify one campaign of at most six attempts and the final
implementation/report hashes. This revision issues no ticket and has **no enable
flag or environment override**. Its public runner refuses before reading even a
valid preparation report. Removing only the pause guard would still leave the
internal runner without an authorization reference; it is not an execution recipe.

A later narrowly reviewed change must bind that explicit authorization while
retaining the tested lifecycle and identities. No runnable generation command is
provided now. Once separately authorized, the lifecycle would claim the fixed
single-use anchor, preflight all six backend controls before charging, sample and
enforce resources, charge durable events before transport, retain every raw or
partial response, apply terminal stop rules, compare preservation and export all
evidence. One closed/interrupted anchor cannot resume or restart.

Even all mechanical passes remain pending two independent human source/formula/
interpretation reviews and adjudication. Human ratings are separate new files;
do not edit raw outputs or historical scores. A later offline export can include
those ratings using a new archive name. The numerical denominator is four;
abstentions are N/A numerically. Historical v2 remains 1/6. Current cumulative
spending is **12**, currently authorized remaining **0**. No FinanceBench answers,
OCR/retrieval changes or expansion-v1 tuning are included.
