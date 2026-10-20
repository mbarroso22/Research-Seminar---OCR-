# Answer feasibility and private evaluator preparation — Windows

**Historical v1 acquisition/setup guide.** The original six-request campaign is
exhausted and reviewed in [SYNTHETIC_FEASIBILITY_REVIEW.md](SYNTHETIC_FEASIBILITY_REVIEW.md).
Its wrapper omitted the explicit Flash Attention flag, and the backend enabled
FA automatically; the disabled setting listed below was intended, not reproduced.
Preserve its setup/run/ledger. For the incremental repair and any explicitly
budgeted follow-up use [ANSWER_VALIDATION_V2_WINDOWS.md](ANSWER_VALIDATION_V2_WINDOWS.md).
Do not reinstall, reconvert, reseal v1 or repeat its inference command.

**Base: `828ba06`, branch `native-ocr-pilot-results`. Scope: setup and six fictional
checks only. No primary or annotated-page FinanceBench generation is implemented
or authorized by this guide.** Read `BOUNDED_ANSWER_EXPERIMENT.md` and the verified
`NATIVE_OCR_PILOT_RESULTS.md` first. Expansion v1 / k=5 stays frozen. Use the second
machine; existing CPU/OCR environments, models, caches and rankings remain intact.

## What is completed and what remains unmeasured

| State | Evidence / limit |
|---|---|
| Implemented | Immutable asset acquisition, local conversion/seal, six-case synthetic-only runner, typed evaluator helpers and private source audit |
| Checked on development host | Unit/integration tests with simulated inference; exact official tokenizer packing; Windows-target wheel resolution/acquisition checks |
| Evaluator preparation | All 24 items prepared against six checksum-matching PDFs; all 25 annotated pages and one additional tax-note page visually checked. Three source/reference issues are held in the private bundle. This is source review, not generated-answer evaluation. |
| Pending on Windows | Dependency installation, converter import/execution, quantization, actual Vulkan compatibility/offload, model outputs, 180-second deadlines, sampled memory and manual synthetic review |
| Deferred | Final private-key adjudication/freeze, primary generation, annotated-page diagnostic, blinded correctness scoring and every new experimental result |

A successful test suite is not a model feasibility result. Model-card benchmark
scores are not this pilot's results. A successful six-request run is setup evidence,
not FinanceBench accuracy or permission to begin primary generation.

## Fixed setup candidate and official sources

- Model: official `Qwen/Qwen3-4B-Instruct-2507`, revision
  `cdbee75f17c01a7cc42f958dc650907174af0554`. It is a non-thinking 4B text model.
  `ANSWER_SETUP_LOCK.json` pins every original file's SHA-256, including tokenizer
  files and the three BF16 weight shards. No community GGUF is substituted.
- Conversion: official llama.cpp **b6500**, commit
  `a7a98e0fffed794396b3fbad4dcdbbc184963645`, official weights -> F16 GGUF ->
  **Q4_K_M**, six conversion threads. The resulting GGUF is a **locally converted
  derivative**, not an official Qwen quantized release. Its actual SHA is recorded
  after conversion; no guessed output hash is supplied.
- Inference: official standalone Windows x64 **Vulkan** b6500 ZIP, SHA-256
  `d485ce9cdda9967d2b27a054bb7e16b57a56a332a4b54b2f02964b95ee591548`.
  Native Windows, one RTX 3070 Ti, device `Vulkan0`, full **37/37** layer offload.
  This candidate avoids installing a new CUDA toolkit/runtime or changing driver
  537.70. It does not establish compatibility merely from that driver number.
  llama.cpp requires Vulkan >=1.2; actual enumeration, model startup and the six
  checks decide feasibility. Stop on missing features, initialization errors or
  offload failure; there is no silent CPU fallback or driver update.
- Explicit backend settings: context 6,144, one slot, F16 K/V, prompt batch 512,
  microbatch 128, six CPU threads, flash attention disabled, cooperative matrix
  paths disabled, no warmup request, no context shifting, no prompt-cache reuse.
  Greedy temperature 0/top-k 1, seed 0, penalties neutral, output cap 1,024,
  total wall deadline 180 s/request. This deliberately differs from Qwen's sampling
  recommendations and is not a promise of bitwise GPU determinism.
- `.venv-answer`: **CPython 3.12.10 x64**, exact 43 Windows/pure wheels with hashes
  in `requirements/answer-windows-py312.lock.txt`. **CPU-only** PyTorch 2.6.0 is
  for conversion; inference uses the standalone Vulkan executable. No Paddle,
  CUDA PyTorch or generation dependencies enter an existing environment.

Official references checked 2026-10-18:
[Qwen card and immutable files](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507/tree/cdbee75f17c01a7cc42f958dc650907174af0554),
[llama.cpp b6500 release](https://github.com/ggml-org/llama.cpp/releases/tag/b6500),
[pinned build guide](https://github.com/ggml-org/llama.cpp/blob/a7a98e0fffed794396b3fbad4dcdbbc184963645/docs/build.md),
[pinned server API](https://github.com/ggml-org/llama.cpp/blob/a7a98e0fffed794396b3fbad4dcdbbc184963645/tools/server/README.md),
[NVIDIA Vulkan support](https://developer.nvidia.com/vulkan-driver),
[official CPU PyTorch index](https://download.pytorch.org/whl/cpu/torch/).
`ANSWER_WINDOWS_WHEELS.json` records exact selected wheel URLs and hashes.

## Stage 0 — apply this incremental patch and save existing state

Use a fresh PowerShell window. Do not activate an OCR environment. Download the
patch and the separate evaluator-private ZIP. The ZIP must stay outside Git and
outside all generator inputs. Change only the two downloaded-file paths if needed.

```powershell
$ErrorActionPreference = 'Stop'
$Repo = Join-Path $env:USERPROFILE 'Downloads\Research-Seminar-OCR-gpu'
$Patch = Join-Path $env:USERPROFILE 'Downloads\answer-feasibility-preparation.patch'
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$AnswerRoot = Join-Path $DataRoot 'answer-generation\qwen3-4b-instruct-2507-v1'
$Assets = Join-Path $AnswerRoot 'assets'
$Py312 = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312OCR\python.exe'
$AnswerEnv = Join-Path $Repo '.venv-answer'
$AnswerPython = Join-Path $AnswerEnv 'Scripts\python.exe'
$BaselinePython = Join-Path $Repo '.venv\Scripts\python.exe'
$LlamaSource = Join-Path $AnswerRoot 'tooling\llama.cpp'
$Before = Join-Path $AnswerRoot 'audits\before'
$After = Join-Path $AnswerRoot 'audits\after'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$RunDir = Join-Path $AnswerRoot "runs\synthetic-$Stamp"
Set-Location -LiteralPath $Repo
$Head = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $Head -notlike '828ba06*') { throw 'Expected 828ba06; preserve local work and reconcile before applying.' }
& git status --short
& git apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch check failed; nothing was reset.' }
& git apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
& git diff --exit-code 828ba06 -- docs/EXPANSION_V1_CONTROL.json src/finocr pyproject.toml
if ($LASTEXITCODE -ne 0) { throw 'Frozen retrieval/OCR code differs; inspect before setup.' }

function Save-BaselineState([string]$Destination) {
    if (Test-Path -LiteralPath $Destination) { throw "Snapshot already exists: $Destination" }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    foreach ($Name in @('.venv', '.venv-ocr', '.venv-ocr-gpu')) {
        $Python = Join-Path $Repo "$Name\Scripts\python.exe"
        if (Test-Path -LiteralPath $Python) {
            $Freeze = & $Python -m pip freeze --all
            if ($LASTEXITCODE -ne 0) { throw "Cannot inventory $Name" }
            $Freeze | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination "$Name.txt")
        } else {
            'absent on this machine' | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination "$Name.txt")
        }
    }
    $Records = @()
    $Records += Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Repo 'docs\EXPANSION_V1_CONTROL.json') |
        ForEach-Object { "$($_.Path)`t$($_.Hash)" }
    foreach ($Root in @((Join-Path $DataRoot 'derived'), (Join-Path $DataRoot 'models'))) {
        if (Test-Path -LiteralPath $Root) {
            $Records += Get-ChildItem -LiteralPath $Root -Recurse -File |
                Where-Object { $_.Name -in @('run_manifest.json', 'model_manifest.json') } |
                Get-FileHash -Algorithm SHA256 | ForEach-Object { "$($_.Path)`t$($_.Hash)" }
        }
    }
    $Records | Sort-Object | Set-Content -Encoding UTF8 -LiteralPath (Join-Path $Destination 'control-and-cache-manifests.txt')
}
Save-BaselineState $Before
if (-not (Test-Path -LiteralPath $Py312)) { throw 'Existing isolated Python 3.12.10 was not found; do not replace Python 3.13.' }
& $Py312 -c "import platform,struct; print(platform.python_version(),struct.calcsize('P')*8); assert platform.python_version()=='3.12.10' and struct.calcsize('P')*8==64"
if ($LASTEXITCODE -ne 0) { throw 'Wrong Python version/architecture.' }
& nvidia-smi
if ($LASTEXITCODE -ne 0) { throw 'GPU inventory unavailable.' }
$Drive = (Get-Item -LiteralPath $DataRoot).PSDrive
if ($Drive.Free -lt 40GB) { throw 'Reserve 40 GiB free for original weights, conversion, wheels and logs.' }
$env:PYTHONPATH = Join-Path $Repo 'src'
```

Snapshots compare existing package lists and immutable control/cache manifests;
they do not rescan every large OCR/image/model payload. Acquisition and generation
never receive an OCR cache, task or label path. Save these variables if opening a
new shell; rerunning Stage 0 would deliberately refuse overwriting its snapshot.

## Stage 1 — audit the private scoring key, before any benchmark answers

The delivered private ZIP contains the prepared 24-item key, source hashes,
per-item numerical quantities/formulas/quantums, interpretation checklists,
contradictions and reviewer sheets. It preserves original answers and evidence
labels in evaluator-only fields. It contains **no generated answers**. Keep it
outside the repository; do not upload it as a model example or prompt.

```powershell
$PrivateZip = Join-Path $env:USERPROFILE 'Downloads\answer-evaluator-private-v1.zip'
$PrivateDir = Join-Path $DataRoot 'private-answer-evaluation\v1-prepared'
if (Test-Path -LiteralPath $PrivateDir) { throw 'Private directory exists; preserve it and use the saved preparation.' }
Expand-Archive -LiteralPath $PrivateZip -DestinationPath $PrivateDir
$Key = Join-Path $PrivateDir 'rubric-v1.prepared.json'
$Tasks = Join-Path $DataRoot 'audits\financebench_phase0_sector_fixed\manifests\pilot_tasks.jsonl'
$PdfRoot = Join-Path $DataRoot 'raw\financebench\pdfs'
& $BaselinePython .\scripts\check_answer_rubric.py --key $Key --pdf-root $PdfRoot --tasks $Tasks --output (Join-Path $PrivateDir 'windows-source-audit.json')
if ($LASTEXITCODE -ne 0) { throw 'Private source audit failed; do not generate benchmark answers.' }
Get-Content -Raw -LiteralPath (Join-Path $PrivateDir 'windows-source-audit.json')
```

The expected prepared state is 24 tasks, six matching sources, three held items,
`freeze_ready=false` and `generation_executed=false`. This is not a failed setup.
Read `SOURCE_REVIEW.md` privately and resolve the holds using only the questions,
original references and source PDFs. Record an overlay, its reasons, declared
accepted definitions/rounding and reviewer signoff in a **new version** before
final freeze. If an item remains ambiguous, declare it unscorable prospectively;
retain all 24 in cohort accounting and publish eligible/held denominators. Never
silently turn an unknown label into a measured wrong answer.

`--require-freeze-ready` intentionally refuses the delivered prepared key. There
is no force flag. Do not change upstream tasks. Do not supply this key to Stage 5.
The independent source review is completed; researcher adjudication/final freeze
and the later two-human blinded output review remain pending. A hash of a draft
is an immutable preparation snapshot, not proof of adjudication or agreement.

## Stage 2 — create the separate answer environment

```powershell
if (Test-Path -LiteralPath $AnswerEnv) { throw '.venv-answer already exists; preserve it and inspect its setup record.' }
& $Py312 -m venv $AnswerEnv
if ($LASTEXITCODE -ne 0) { throw 'Answer environment creation failed.' }
$env:PIP_CACHE_DIR = Join-Path $AnswerRoot 'cache\pip'
$env:HF_HOME = Join-Path $AnswerRoot 'cache\huggingface'
& $AnswerPython -m pip install --only-binary=:all: --require-hashes --index-url https://pypi.org/simple -r .\requirements\answer-windows-py312.lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Pinned install failed; preserve its log and do not substitute latest packages.' }
& $AnswerPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'Answer dependency check failed.' }
& $AnswerPython -c "import torch,platform; print(platform.python_version(),torch.__version__,torch.version.cuda); assert torch.__version__=='2.6.0+cpu' and torch.version.cuda is None"
if ($LASTEXITCODE -ne 0) { throw 'Expected CPU-only conversion PyTorch.' }
```

Answer helpers live in the sibling `finocr_answer` package, so the existing
`finocr` Python tree and its OCR-resume source fingerprint remain unchanged.

No project `pip install -e .` is needed: `PYTHONPATH` selects the checked-out code.
This keeps base dependencies unchanged. The lock is Windows x64 / CPython 3.12
specific. It was resolved and the selected wheel hashes checked on the development
host; actual Windows import/install success is still a local check.

## Stage 3 — acquire immutable official assets and converter source

The original weight shards total about 8.05 GB, before the F16 intermediate and
Q4 derivative. Downloads verify SHA-256; existing different files are preserved
and rejected. An interrupted `.partial` stays available for inspection. Only a
failed acquisition partial may be removed to repeat **that download**; do not
remove conversion or synthetic-run records to repeat successful work.

```powershell
& $AnswerPython .\scripts\prepare_answer_setup.py acquire --root $Assets
if ($LASTEXITCODE -ne 0) { throw 'Asset acquisition/checksum verification failed.' }
if (Test-Path -LiteralPath $LlamaSource) { throw 'Converter checkout exists; inspect it rather than overwrite it.' }
& git clone --depth 1 --branch b6500 https://github.com/ggml-org/llama.cpp.git $LlamaSource
if ($LASTEXITCODE -ne 0) { throw 'Converter clone failed.' }
$ConverterCommit = (& git -C $LlamaSource rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $ConverterCommit -ne 'a7a98e0fffed794396b3fbad4dcdbbc184963645') { throw 'Wrong converter commit.' }
& git -C $LlamaSource status --short
$Servers = @(Get-ChildItem -LiteralPath (Join-Path $Assets 'backend') -Recurse -File -Filter 'llama-server.exe')
if ($Servers.Count -ne 1) { throw 'Expected one pinned server executable.' }
$Server = $Servers[0].FullName
$env:GGML_VK_DISABLE_COOPMAT = '1'
$env:GGML_VK_DISABLE_COOPMAT2 = '1'
& $Server --version
if ($LASTEXITCODE -ne 0) { throw 'Backend executable check failed.' }
& $Server --list-devices
if ($LASTEXITCODE -ne 0) { throw 'Vulkan device enumeration failed.' }
```

Verify that `Vulkan0` names the RTX 3070 Ti. Do not continue with another GPU or a
CPU-only device list. No Windows CUDA DLL ZIP is used. If a Visual C++ runtime or
Vulkan feature is missing, retain the error and review it before adding system
components; none is silently installed by the patch.

## Stage 4 — convert locally, record exact hashes, seal the setup

```powershell
& $AnswerPython .\scripts\prepare_answer_setup.py convert --root $Assets --llama-source $LlamaSource
if ($LASTEXITCODE -ne 0) { throw 'Conversion failed; preserve converted\conversion.json and 1.log / 2.log.' }
& $AnswerPython .\scripts\prepare_answer_setup.py seal --root $Assets
if ($LASTEXITCODE -ne 0) { throw 'Setup sealing failed.' }
Get-Content -Raw -LiteralPath (Join-Path $Assets 'setup_manifest.json')
```

Conversion initializes no generator. Offline mode is used after acquisition. The
seal records original/tokenizer/backend files, local GGUF, conversion metadata,
exact Python/package versions, prompt/schema and code fingerprints. It is a setup
identity, not an inference pass. Do not update packages/code/backend/model after
sealing; the runner rejects changes. Keep F16/quantizer logs through setup review.

## Stage 5 — execute the six synthetic requests once, then stop

```powershell
& $AnswerPython .\scripts\run_answer_feasibility.py --setup (Join-Path $Assets 'setup_manifest.json') --output $RunDir
$FeasibilityExit = $LASTEXITCODE
"Synthetic exit code: $FeasibilityExit"
if (Test-Path -LiteralPath (Join-Path $RunDir 'run_manifest.json')) {
    Get-Content -Raw -LiteralPath (Join-Path $RunDir 'run_manifest.json')
} else {
    'Preflight failed before a run manifest existed; retain the console error and setup manifest.'
}
```

The runner starts/owns a server bound only to `127.0.0.1` on a free port. It checks
full offload from runtime logs and compares **actual backend template bytes/token
IDs** with the official tokenizer. There is no primary-task input switch, remote
endpoint, private-rubric input, benchmark query file or annotated-page mode.

| Case | Fictional check / required manual review |
|---|---|
| signed | Parenthesized negative cash flow; year and USD million association |
| scale | USD billion -> equivalent USD million; no wrong currency/scale |
| margin | Gross-margin arithmetic; percent versus percentage-point change |
| comparison | Signed net cash-flow selection; revenue growth does not imply profit improvement; stated cost driver |
| missing | Explicit missing current liabilities; no invented quick ratio |
| capacity | All five 800-token prefixes; exactly 4,096 evidence and 5,120 complete input tokens; 1,024 output cap and same schema; insufficient evidence remains appropriate |

The boundary case pads only fictional report-ID/system text. It is a capacity
fixture, not a proposed change to primary packing. An EOS before 1,024 output
tokens is valid: distinguish **configured cap/KV capacity** from actual decoded
length; never claim it generated 1,024 tokens unless the log says so. Semantic
support, the percentage-point comparison and narrative contradiction check require
manual review even if the automated checks pass. `automated_checks_pass` is not
an adjudicated semantic pass. No repair prompt or answer-driven retry is allowed.

Every request is charged before submission. `assets\synthetic_campaign.json`
exclusively records this six-request campaign; changing output directory does not
allow another campaign. Preserve it after interruptions. A timeout stops the owned
server, saves received raw SSE bytes, and ends the campaign. OOM/crash/invalid
JSON/output-limit failures are retained. Do not delete the ledger or start a new
campaign to get a better answer; review the saved failure within the protocol.

Retain setup/conversion manifests, exact prompts, token IDs, retained prefix
ranges, canonical requests/hashes, raw SSE/content, parsed outputs, terminal backend
metadata, server logs, timing and memory samples. Server/client RSS, whole-system used/available RAM and GPU memory are
sampled; VRAM is **device-wide** (display/other processes included), sampled about
once per second and a lower bound on peak. Windows server peak working set is recorded
when available; the RSS sum may double-count shared pages. Do not describe these as exact isolated process VRAM or full-system
peak RAM. Missing memory samples/errors block a positive feasibility conclusion.

## Stage 6 — preservation check and bounded handoff

```powershell
Save-BaselineState $After
foreach ($Name in @('.venv.txt', '.venv-ocr.txt', '.venv-ocr-gpu.txt', 'control-and-cache-manifests.txt')) {
    $Difference = Compare-Object (Get-Content -LiteralPath (Join-Path $Before $Name)) (Get-Content -LiteralPath (Join-Path $After $Name))
    if ($Difference) { $Difference; throw "Preservation check differs: $Name" }
}
& git diff --exit-code 828ba06 -- docs/EXPANSION_V1_CONTROL.json src/finocr pyproject.toml
if ($LASTEXITCODE -ne 0) { throw 'Frozen code/control differs.' }
& $BaselinePython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Local complete test suite failed.' }
$Export = Join-Path $AnswerRoot "exports\synthetic-$Stamp.zip"
New-Item -ItemType Directory -Path (Split-Path -Parent $Export) -Force | Out-Null
if (Test-Path -LiteralPath $Export) { throw 'Export exists; preserve it.' }
$ExportItems = @($RunDir, (Join-Path $Assets 'setup_manifest.json'), (Join-Path $Assets 'synthetic_campaign.json'), (Join-Path $Assets 'acquisition.json'), (Join-Path $Assets 'converted\conversion.json'), (Join-Path $Assets 'converted\1.log'), (Join-Path $Assets 'converted\2.log'), $Before, $After)
Compress-Archive -LiteralPath $ExportItems -DestinationPath $Export
$Export
```

Run Stage 6 after successful synthetic completion; if a failure occurred, retain
whatever exists and perform the snapshot comparisons without assuming the export
list is complete. Export runtime artifacts **without weights, PDFs, OCR caches or
the private key**. Return the private adjudication decisions separately.

Next review setup output, numerical and narrative synthetic behavior, memory,
actual device/template, raw failures and preservation evidence. Then resolve/freeze
the private rubric and declare the exact model/runtime/prompt/packer manifest.
Primary generation and its deduplicated N/OCR requests require a later explicit
step; no such command is supplied here. No OCR or retrieval tuning is introduced.
