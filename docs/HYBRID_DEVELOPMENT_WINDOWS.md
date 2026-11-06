# One fixed hybrid experiment: original development pilot

Implementation and offline validation are complete; **new semantic/hybrid results
remain pending Windows execution**. This guide uses the original native cache and
completed original **GPU OCR** cache, not the six-company evaluation. No new OCR,
answer generation, authorization files, qualification runner, or parameter sweep.

Frozen policy: `HYBRID_DEVELOPMENT_POLICY.json`, canonical policy SHA-256
`6e151c7af4624e633876c4e500fd56a63444e04a6faff971f43740e82b5d3b96`.

- BAAI/bge-small-en-v1.5 revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`,
  creator FP32 `onnx/model.onnx`; its SHA-256 is
  `828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35`.
- The tokenizer and all six accompanying configuration/vocabulary files are pinned
  by byte hash. Queries use the saved expansion-v1 question with the generic
  prefix `Represent this sentence for searching relevant passages: `.
  Passage input is only saved `search_text`. Labels, answers, justifications,
  and annotation evidence text never enter query/source encoding or indexing.
- 384 content-token windows, 64-token overlap, no page/report crossing; CLS/SEP
  added once. Queries longer than 510 content tokens fail rather than truncate.
  CLS pooling, float32 L2 normalization, cosine, maximum window score per page.
  Equal window maxima choose the earliest window. Empty token pages rank last;
  all physical pages remain candidates. Semantic ties use ascending page ID.
- Equal-weight RRF: `1/(60 + BM25_rank) + 1/(60 + semantic_rank)`, using both
  **full** report rankings. Ranks start at one; physical PDF page IDs remain zero
  based. RRF ties use ascending page ID, without score rounding.
- BM25 remains frozen expansion v1, k1=1.2, b=.75, identical tokenizer/stopwords,
  binary query term frequency, full-report candidates. No source heading context.
- One fixed encoder condition: Windows x64, Python 3.12.10, ONNX Runtime 1.22.0
  **CPUExecutionProvider**, tokenizers 0.21.1, NumPy 1.26.4, batch 8, sequential
  execution, two intra-op threads and one inter-op thread. Source order is native
  then OCR, saved report/page order, windows ascending. Query vectors are shared.
  CPU encoding avoids installing Torch or changing any Paddle/CUDA environment.

Primary decision is the **hybrid** gate, requiring all of:
Recall@5 strictly above replayed BM25 in both text conditions; Complete@5 at
least 10/24 in each; at least one complete multi-page item in each. Semantic-only
is diagnostic, not an alternative chosen after seeing outcomes. A completed run
returns exit 0 even when this research gate fails. Invalid inputs/runtime return
nonzero; failed/interrupted manifests preserve the stage and partial artifacts.

## Offline checks already completed here

- 27 new tests and 219 total **core retrieval/OCR tests**, no skips. Encoder calls
  were mocked. The preserved answer/qualification tests were outside this scope.
- Both full BM25 controls replay from the real original caches. No annotation
  parsing or encoder loading occurred in that check.
- Downloaded ONNX bytes match the pinned hash; inspected graph has three int64
  inputs and float32 `last_hidden_state[batch, sequence, 384]` output. No forward
  pass was executed. The real pinned tokenizer gives 5,426 native and 5,354 OCR
  windows (10,780 total), plus 24 shared queries, each at most 102 content tokens.
  Float32 saved vectors occupy about 16.6 MB before file headers. These are
  workload/setup checks, not new retrieval or resource-performance results.
- All 30 exact dependency pins have compatible official Windows/Python 3.12
  wheels and a complete compatible dependency closure. Wheel downloads total
  approximately 47.4 MB; model assets total approximately 134 MB. Allow at least
  5 GiB free for environment, wheels, inputs, vectors, logs and export. CPU wall
  time is unmeasured; do not infer a speedup or energy use from estimates.

Sources: [creator model card and ONNX/CLS instructions](https://huggingface.co/BAAI/bge-small-en-v1.5/blob/5c38ec7c405ec4b44b94cc5a9bb96e735b38267a/README.md),
[ONNX Runtime Python API](https://onnxruntime.ai/docs/api/python/api_summary.html),
[RRF method](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf).

## Stage A — unpack, record the existing state, apply the patch

Use one ordinary PowerShell session; paste blocks interactively. No activation,
`.ps1` execution, execution-policy change, administrator shell, or modifications
of existing environments. Save the supplied ZIP to Downloads under the exact
name below. Keep your completed broader-experiment directories/archives.

```powershell
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = 'C:\Users\mbarroso\Downloads\Research-Seminar-OCR-review'
$OriginalRepo = 'C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current'
$DataRoot = 'C:\Users\mbarroso\financial-ocr-data'
$Python312 = Join-Path $DataRoot 'tools\python-3.12.10-amd64\python.exe'
$Native = Join-Path $DataRoot 'derived\native\native-bm25-20261008T051510Z-7fcc394d'
$Imports = Join-Path $DataRoot 'imports\gpu-completed'
$Package = Join-Path $env:USERPROFILE 'Downloads\hybrid-development-20261022.zip'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$AuditDir = Join-Path $DataRoot "audits\hybrid-development-$Stamp"
$PackageDir = Join-Path $AuditDir 'package'
$EncoderEnv = Join-Path $DataRoot "environments\bge-small-onnx-dev-$Stamp"
$EncoderPython = Join-Path $EncoderEnv 'Scripts\python.exe'
$Models = Join-Path $DataRoot 'models\bge-small-en-v1.5-5c38ec7-onnx'
$Output = Join-Path $DataRoot "derived\retrieval\hybrid-development-$Stamp"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
foreach ($p in @($Python312, $Package)) { if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { throw "Missing: $p" } }
foreach ($p in @($Repo, $Native, $Imports)) { if (-not (Test-Path -LiteralPath $p -PathType Container)) { throw "Missing existing directory: $p" } }
if ((Get-PSDrive C).Free -lt 5GB) { throw 'Need at least 5 GiB free; preserve existing data.' }
$null = New-Item -ItemType Directory -Path $AuditDir
Expand-Archive -LiteralPath $Package -DestinationPath $PackageDir
Get-FileHash -LiteralPath $Package -Algorithm SHA256 | Format-List
Set-Location -LiteralPath $Repo
$GitBefore = [ordered]@{ head=([string](git --no-optional-locks rev-parse HEAD)).Trim(); status=@(git --no-optional-locks status --porcelain=v1) }
if ($LASTEXITCODE -ne 0) { throw 'Cannot read processing checkout.' }
[IO.File]::WriteAllText((Join-Path $AuditDir 'git-before-patch.json'), ($GitBefore | ConvertTo-Json -Depth 5), $Utf8)
$VerifyPackage = @'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1])
for name,expected in json.loads((root/'CONTENTS_SHA256.json').read_text()).items():
 p=root/name
 assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==expected['sha256'] and p.stat().st_size==expected['size_bytes'],name
print('package_hashes_pass')
'@
& $Python312 -I -c $VerifyPackage $PackageDir
if ($LASTEXITCODE -ne 0) { throw 'Package verification failed.' }
$Patch = Join-Path $PackageDir 'hybrid-development.patch'
git apply --check $Patch
if ($LASTEXITCODE -ne 0) {
    $Patch = Join-Path $PackageDir 'hybrid-development-crlf.patch'
    git apply --check $Patch
    if ($LASTEXITCODE -ne 0) { throw 'Neither patch matches this checkout; preserve the state and share the errors.' }
}
git apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
git diff --stat
git status --short
```

Expected: `package_hashes_pass`, one CLI addition and eight new files. The patch
is incremental over the completed broader-cohort/runtime-repair checkout,
including the preserved paused answer-stage code. No previous result documents
or score files change. Do not commit the external reference/tasks bundle to Git.

Capture existing package inventories **before** creating the encoder environment.
The following function is defined interactively and only reads interpreters.

```powershell
function Get-ProtectedEnvironments {
    $Candidates = @()
    foreach ($Root in @($OriginalRepo, $Repo, (Join-Path $DataRoot 'environments'))) {
        if (-not (Test-Path -LiteralPath $Root -PathType Container)) { continue }
        $Candidates += @(Get-ChildItem -LiteralPath $Root -Directory -Force | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'pyvenv.cfg') -PathType Leaf })
    }
    $Inventory = [ordered]@{}
    foreach ($Directory in @($Candidates | Sort-Object FullName -Unique)) {
        if ($Directory.FullName -eq $EncoderEnv) { continue }
        $Interpreter = Join-Path $Directory.FullName 'Scripts\python.exe'
        $Version = @(& $Interpreter -I --version)
        if ($LASTEXITCODE -ne 0) { throw "Cannot read $Interpreter" }
        $Packages = @(& $Interpreter -I -m pip freeze --all)
        if ($LASTEXITCODE -ne 0) { throw "Cannot inventory $Interpreter" }
        $Inventory[$Directory.FullName] = [ordered]@{ version=$Version; packages=$Packages }
    }
    return ($Inventory | ConvertTo-Json -Depth 7)
}
$ProtectedBefore = Get-ProtectedEnvironments
[IO.File]::WriteAllText((Join-Path $AuditDir 'protected-environments-before.json'), $ProtectedBefore, $Utf8)
$OS = Get-CimInstance Win32_OperatingSystem
$Machine = [ordered]@{ cpu=@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors); ram_total_bytes=[long](Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory; ram_available_bytes=([long]$OS.FreePhysicalMemory * 1024); disks=@(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | Select-Object DeviceID,FreeSpace,Size); encoder_device='CPUExecutionProvider' }
[IO.File]::WriteAllText((Join-Path $AuditDir 'machine.json'), ($Machine | ConvertTo-Json -Depth 6), $Utf8)
```

## Stage B — new isolated encoder environment and exact wheels

This creates only `$EncoderEnv`, a new wheelhouse and audit logs. The existing
baseline, CPU OCR, broader GPU OCR, answer and other environments stay unchanged.
No Paddle, CUDA, Torch, Transformers, or package upgrades in an existing venv.

```powershell
# Transcript logging avoids Windows PowerShell 5.1 native-stderr redirection issues.
function Invoke-EncoderStep {
    param([string]$Name, [string[]]$CommandArguments)
    $StepLog = Join-Path $AuditDir ($Name + '.txt')
    $StepRecord = Join-Path $AuditDir ($Name + '-time.json')
    if ((Test-Path -LiteralPath $StepLog) -or (Test-Path -LiteralPath $StepRecord)) { throw "Preserve existing step evidence: $Name" }
    $StepTimer = [Diagnostics.Stopwatch]::StartNew()
    $StepExit = -1
    Start-Transcript -LiteralPath $StepLog -NoClobber | Out-Null
    try {
        & $EncoderPython @CommandArguments
        $StepExit = $LASTEXITCODE
    } finally {
        $StepTimer.Stop()
        Stop-Transcript | Out-Null
        [IO.File]::WriteAllText($StepRecord, (([ordered]@{ step=$Name; elapsed_seconds=$StepTimer.Elapsed.TotalSeconds; exit_code=$StepExit; arguments=$CommandArguments }) | ConvertTo-Json -Depth 5), $Utf8)
    }
    if ($StepExit -ne 0) { throw "Step $Name failed with exit $StepExit; retain logs and stop." }
}
& $Python312 -I -c "import sys,struct; assert sys.version_info[:3]==(3,12,10) and struct.calcsize('P')==8; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw 'Require the supplied Python 3.12.10 x64.' }
if (Test-Path -LiteralPath $EncoderEnv) { throw 'Choose a new encoder environment; never reuse or alter an old environment.' }
& $Python312 -I -m venv $EncoderEnv
if ($LASTEXITCODE -ne 0) { throw 'New encoder venv creation failed.' }
$Lock = Join-Path $Repo 'requirements\encoder-windows-cp312.lock.txt'
$Wheelhouse = Join-Path $AuditDir 'encoder-wheels'
$null = New-Item -ItemType Directory -Path $Wheelhouse
Invoke-EncoderStep -Name 'wheel-download' -CommandArguments @('-I','-m','pip','download','--index-url','https://pypi.org/simple','--only-binary=:all:','--require-hashes','--dest',$Wheelhouse,'-r',$Lock)
Invoke-EncoderStep -Name 'encoder-install' -CommandArguments @('-I','-m','pip','install','--no-index','--find-links',$Wheelhouse,'--require-hashes','--no-deps','-r',$Lock)
Invoke-EncoderStep -Name 'project-install' -CommandArguments @('-I','-m','pip','install','--no-deps','--no-build-isolation','-e',$Repo)
Invoke-EncoderStep -Name 'pip-check' -CommandArguments @('-I','-m','pip','check')
& $EncoderPython -I -m pip freeze --all | Set-Content -LiteralPath (Join-Path $AuditDir 'encoder-packages.txt') -Encoding UTF8
if ($LASTEXITCODE -ne 0) { throw 'Cannot record encoder packages.' }
& $EncoderPython -I -c "import onnxruntime,tokenizers,numpy,psutil; print('imports_pass',onnxruntime.__version__,tokenizers.__version__,numpy.__version__,psutil.__version__)"
if ($LASTEXITCODE -ne 0) { throw 'Encoder runtime import failed; retain logs before considering any further setup.' }
```

Expected: 30 pinned wheels, `No broken requirements found`, and
`imports_pass 1.22.0 0.21.1 1.26.4 7.2.2`. Imports are not encoder inference.
If Windows reports a missing runtime DLL, stop and share the precise error;
do not alter the OCR environments or silently choose another backend/version.

## Stage C — offline tests and policy check

The retained core tests use Poppler for tiny generated fixture PDFs; they never
render project reports or run real OCR/encoder/LLM inference. Temporarily expose
the **existing** pinned Poppler executable to the child tests, then restore PATH.

```powershell
$Popplers = @(Get-ChildItem -LiteralPath (Join-Path $DataRoot 'tools') -Filter pdftoppm.exe -File -Recurse | Where-Object { $_.FullName -like '*poppler-v26.09.0-0*' })
if ($Popplers.Count -ne 1) { throw 'Expected exactly one existing pinned Poppler; do not install another.' }
$SavedPath = $env:PATH
$env:PATH = $Popplers[0].DirectoryName + ';' + $SavedPath
$Tests = @'
import pathlib,sys,unittest
root=pathlib.Path(sys.argv[1]);sys.path[:0]=[str(root/'src'),str(root/'tests')]
modules='test_phase0 test_planning test_finlongdocqa test_financebench test_financebench_audit test_metrics test_bm25 test_native_baseline test_retrieval_evaluation test_stopword_comparison test_query_expansion test_section_context test_note_formats test_native_cache_diagnostic test_ocr_setup test_full_ocr test_ocr_gpu test_company_cohort_metadata test_broader_input_preparation test_broader_runtime_resolution test_hybrid_retrieval test_hybrid_inputs'.split()
r=unittest.TextTestRunner(verbosity=2,stream=sys.stdout).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
raise SystemExit(0 if r.wasSuccessful() and not r.skipped else 1)
'@
try {
    Invoke-EncoderStep -Name 'core-tests' -CommandArguments @('-I','-c',$Tests,$Repo)
} finally { $env:PATH = $SavedPath }
$PolicyCheck = @'
import json,pathlib,sys
from finocr.retrieval.semantic import policy_record
p=policy_record();assert p==json.loads((pathlib.Path(sys.argv[1])/'docs/HYBRID_DEVELOPMENT_POLICY.json').read_text())
assert p['sha256']=='6e151c7af4624e633876c4e500fd56a63444e04a6faff971f43740e82b5d3b96'
print('fixed_policy_pass',p['sha256'])
'@
Invoke-EncoderStep -Name 'policy-check' -CommandArguments @('-I','-c',$PolicyCheck,$Repo)
```

Expected: 219 core tests, no skips, `OK`, and `fixed_policy_pass`. This is offline
implementation validation, not measured retrieval improvement. Paused generation
extension tests/code/results remain intact and are not a completion requirement.

## Stage D — locate old inputs, prepare fixed model assets, replay controls

The supplied external `reference` folder contains the **unchanged** original
native/GPU comparison and exact original scoring tasks. No answers/labels are
sent to the encoder. The helper finds the original GPU cache in preserved imports
by manifest SHA-256, or extracts its ZIP into a new audit subdirectory. It never
uses the completed six-company cohort as a substitute.

```powershell
$Reference = Join-Path $PackageDir 'reference\native-gpu-ocr-20261018T200302Z'
$Tasks = Join-Path $PackageDir 'reference\pilot_tasks.jsonl'
$Location = Join-Path $AuditDir 'input-location.json'
Invoke-EncoderStep -Name 'input-location' -CommandArguments @('-I',(Join-Path $Repo 'scripts\prepare_hybrid_inputs.py'),'--imports',$Imports,'--destination',(Join-Path $AuditDir 'original-gpu-cache'),'--output',$Location)
$Ocr = [string](Get-Content -LiteralPath $Location -Raw | ConvertFrom-Json).ocr_dir
Invoke-EncoderStep -Name 'encoder-assets' -CommandArguments @('-I','-m','finocr.cli','prepare-hybrid-encoder','--models-dir',$Models)
$InputCheck = Join-Path $AuditDir 'input-check'
Invoke-EncoderStep -Name 'input-check' -CommandArguments @('-I','-m','finocr.cli','compare-hybrid-retrieval','--native-dir',$Native,'--reference-dir',$Reference,'--ocr-dir',$Ocr,'--tasks',$Tasks,'--models-dir',$Models,'--output-dir',$InputCheck,'--repository-root',$Repo,'--check-only')
```

Expected: `assets_verified_no_inference`, then `inputs_verified_no_encoder`, both
`expansion_control_reproduced` values true, totals 12 / 2,620 / 24. Every retained
OCR raw/worker/commit record is validated without loading Paddle or requiring
original PNGs/PDFs. These immutable metadata anchors bind the previously verified
PDF checksums/rendering identities; this does **not** reread absent source PDFs or
rerun OCR. No evidence labels are parsed by `--check-only`.

Before execution, record final code/Git state and historical manifest identities.
This snapshot reads files and inventories only; it is not an approval mechanism.

```powershell
$StateScript = @'
import hashlib,json,pathlib,subprocess,sys
root=pathlib.Path(sys.argv[1]);data=pathlib.Path(sys.argv[2]);out=pathlib.Path(sys.argv[3])
def identity(p):return {'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size}
def git(*args):return subprocess.check_output(['git','--no-optional-locks','-C',str(root),*args])
paths=git('ls-files','--cached','--others','--exclude-standard','-z').decode().split('\0')
record={'head':git('rev-parse','HEAD').decode().strip(),'status':git('status','--porcelain=v1').decode(),
 'code_files':{s:identity(root/s) for s in sorted(set(paths)-{''}) if (root/s).is_file()},
 'historical_manifests':{str(p):identity(p) for folder in ('derived','imports') if (data/folder).is_dir() for p in sorted((data/folder).rglob('run_manifest.json'))}}
# New hybrid output has not existed before; exclude only that exact directory.
record['historical_manifests']={p:i for p,i in record['historical_manifests'].items() if not pathlib.Path(p).is_relative_to(pathlib.Path(sys.argv[4]))}
with out.open('x',encoding='utf-8') as f:json.dump(record,f,sort_keys=True,indent=2)
print('state_recorded',len(record['code_files']),len(record['historical_manifests']))
'@
& $EncoderPython -I -c $StateScript $Repo $DataRoot (Join-Path $AuditDir 'state-before-run.json') $Output
if ($LASTEXITCODE -ne 0) { throw 'Cannot record final pre-run state.' }
```

Stop here to share Stage A–D logs if any check fails. There is no need for another
qualification or execution ticket. The current research instruction authorizes
this one fixed **development retrieval** run; it does not restart LLM work.

## Stage E — one development encoder/retrieval run

Run once with all settings already fixed. This is the first real encoder forward
pass in this guide. Do not switch model, device, query form, weights, windows,
cutoff, or source caches after inspecting outcomes. No resume block is included.

```powershell
if (Test-Path -LiteralPath $Output) { throw 'Output already exists; preserve it. Do not overwrite or resume.' }
$RunTimer = [Diagnostics.Stopwatch]::StartNew()
$RunExit = -1
Start-Transcript -LiteralPath (Join-Path $AuditDir 'development-run.txt') -NoClobber | Out-Null
try {
    & $EncoderPython -I -m finocr.cli compare-hybrid-retrieval --native-dir $Native --reference-dir $Reference --ocr-dir $Ocr --tasks $Tasks --models-dir $Models --output-dir $Output --repository-root $Repo
    $RunExit = $LASTEXITCODE
} finally {
    $RunTimer.Stop()
    Stop-Transcript | Out-Null
    [IO.File]::WriteAllText((Join-Path $AuditDir 'development-run-time.json'), (([ordered]@{ elapsed_seconds=$RunTimer.Elapsed.TotalSeconds; exit_code=$RunExit; output_dir=$Output }) | ConvertTo-Json), $Utf8)
}
if ($RunExit -ne 0) { throw 'Run failed/interrupted; preserve the whole output and transcript. Do not tune or automatically retry.' }
```

Expected progress: native then OCR report/window counts. Expected final status:
`complete`, both controls true, and a **data-dependent** gate result. 144 logical
prediction records across six files, each a complete report ranking, all at the
same primary five-page budget. A negative gate is a valid experimental outcome.
On interruption/exception retain the partial directory/manifest, code state and
logs; resolve the concrete technical failure before deciding how to proceed.

## Stage F — completion, preservation and review export

```powershell
$Completion = @'
import hashlib,json,math,pathlib,sys
root=pathlib.Path(sys.argv[1]);m=json.loads((root/'run_manifest.json').read_text())
assert m['status']=='complete' and all(m['expansion_control_reproduced'].values())
assert m['manifest_totals']=={'documents':12,'pages':2620,'questions':24}
assert json.loads((root/'input_preservation.json').read_text())['all_match']
for name,expected in m['artifacts'].items():
 p=root/name;assert p.stat().st_size==expected['size_bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==expected['sha256'],name
for c in ('native','ocr'):
 for method in ('bm25','semantic','hybrid'):
  rows=[json.loads(x) for x in (root/f'{c}_{method}_predictions.jsonl').read_text().splitlines()]
  assert len(rows)==24 and len({r['task_id'] for r in rows})==24
  for r in rows:
   assert r['page_index_base']==0 and len(r['ranked_pages'])==r['page_count']
   assert {p['page_index'] for p in r['ranked_pages']}==set(range(r['page_count']))
   assert all(math.isfinite(p['score']) for p in r['ranked_pages'])
metrics=json.loads((root/'comparison_metrics.json').read_text())
for c in ('native','ocr'):
 b=metrics[c]['bm25'];assert math.isclose(b['at_k']['5']['macro_evidence_recall'],.4097222222222222,abs_tol=1e-14)
 assert sum(r['at_k']['5']['any_evidence_hit'] for r in b['per_question'])==12
 assert sum(r['at_k']['5']['all_evidence_coverage'] for r in b['per_question'])==8
 assert metrics['paired'][c]['hybrid']['multipage']['question_count']==5
print('completion_checks_pass');print(json.dumps(metrics['development_gate'],indent=2))
'@
Invoke-EncoderStep -Name 'completion-check' -CommandArguments @('-I','-c',$Completion,$Output)
$ProtectedAfter = Get-ProtectedEnvironments
[IO.File]::WriteAllText((Join-Path $AuditDir 'protected-environments-after.json'), $ProtectedAfter, $Utf8)
if ($ProtectedAfter -cne $ProtectedBefore) { throw 'Existing environment inventory changed; preserve evidence and investigate.' }
& $EncoderPython -I -c $StateScript $Repo $DataRoot (Join-Path $AuditDir 'state-after-run.json') $Output
if ($LASTEXITCODE -ne 0) { throw 'Cannot record final state.' }
$BeforeState = Get-Content -LiteralPath (Join-Path $AuditDir 'state-before-run.json') -Raw
$AfterState = Get-Content -LiteralPath (Join-Path $AuditDir 'state-after-run.json') -Raw
if ($BeforeState -cne $AfterState) { throw 'Code/Git or historical manifest state changed; retain evidence and investigate.' }
[IO.File]::WriteAllText((Join-Path $AuditDir 'preservation-comparison.json'), '{"existing_environment_inventories_match":true,"code_git_and_historical_manifests_match":true,"pilot_input_bytes_match":true}', $Utf8)
Get-Content -LiteralPath (Join-Path $Output 'comparison_report.md')
$ExportDir = Join-Path $AuditDir 'review-export'
$null = New-Item -ItemType Directory -Path $ExportDir
Copy-Item -LiteralPath $Output -Destination (Join-Path $ExportDir 'hybrid-run') -Recurse
$EvidenceDir = Join-Path $ExportDir 'setup-and-preservation'
$null = New-Item -ItemType Directory -Path $EvidenceDir
Get-ChildItem -LiteralPath $AuditDir -File | Copy-Item -Destination $EvidenceDir
Copy-Item -LiteralPath (Join-Path $InputCheck 'run_manifest.json') -Destination (Join-Path $EvidenceDir 'input-check-manifest.json')
Copy-Item -LiteralPath (Join-Path $InputCheck 'input_preservation.json') -Destination (Join-Path $EvidenceDir 'input-check-preservation.json')
Copy-Item -LiteralPath (Join-Path $Repo 'docs\HYBRID_DEVELOPMENT_POLICY.json') -Destination $EvidenceDir
Copy-Item -LiteralPath $Lock -Destination $EvidenceDir
Copy-Item -LiteralPath (Join-Path $Models 'encoder_assets.json') -Destination $EvidenceDir
$HashExport = @'
import hashlib,json,pathlib,sys
root=pathlib.Path(sys.argv[1]);rows={}
for p in sorted(root.rglob('*')):
 if p.is_file():rows[p.relative_to(root).as_posix()]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size_bytes':p.stat().st_size}
with (root/'EXPORT_SHA256.json').open('x',encoding='utf-8') as f:json.dump(rows,f,indent=2,sort_keys=True)
print('export_files_hashed',len(rows))
'@
& $EncoderPython -I -c $HashExport $ExportDir
if ($LASTEXITCODE -ne 0) { throw 'Export hashing failed.' }
$ReviewZip = Join-Path $DataRoot "hybrid-development-$Stamp-review.zip"
Compress-Archive -Path (Join-Path $ExportDir '*') -DestinationPath $ReviewZip
Get-FileHash -LiteralPath $ReviewZip -Algorithm SHA256 | Format-List
$ReviewZip
```

Upload that ZIP and its SHA-256 for independent review. It contains predictions,
window plans/vectors, query projections, policy/code identity, all question-level
changes and five multi-page analyses, gate, costs, package/setup logs and
preservation checks. Source PDF/PNG caches and old OCR raw outputs remain in place;
their identities are recorded, not recopied into this smaller review export.
Package inventories establish package-level preservation, not a byte-for-byte
inventory of entire environments. Historical manifest matching supplements the
stronger original-pilot cache/raw-record checks; it is not a re-audit of every
historical experiment file.

Review the hybrid result against the predeclared gate before any next step.
A pass supports considering a separately selected untouched confirmation cohort;
the already-inspected six-company cohort is not an untouched test. A fail ends
this fixed development experiment without a prompt/model/weight/window sweep.
Keep expansion v1 and all historical scores, including failures, unchanged.
