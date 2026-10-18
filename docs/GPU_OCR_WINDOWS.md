# Isolated GPU diagnostic on the second Windows machine

**Status update 2026-10-18:** the diagnostic, full GPU extension and matched
retrieval have completed. See [NATIVE_OCR_PILOT_RESULTS.md](NATIVE_OCR_PILOT_RESULTS.md)
for verified findings and limitations. Pending/stop instructions below describe
the original staged setup; they do not indicate that a new GPU run is needed.

This is an **incremental** patch over `61a696d` plus the delivered
`full-report-ocr-final.patch` (SHA-256
`1ca6be76855466ca0dde634ea2b3d437b3edb68c447653c3b8aaaced2f6587a7`).
Apply it only to `C:\Users\mbarroso\Downloads\Research-Seminar-OCR-gpu`.
Leave the first machine's continuing CPU run, source checkout, environment,
models and cache unchanged. Do not apply this patch or update packages there
while it runs: resume includes the source-code fingerprint.

## Compatibility decision, verified against official sources on 2026-10-17

The researcher reports Windows 11 Education 10.0.22000, Ryzen 5 PRO 5645,
16 GB RAM, RTX 3070 Ti 8 GB, NVIDIA driver **537.70**, Python 3.13 only,
563 GiB free disk and Git. These are the supplied second-machine observations;
the commands below save fresh runtime observations before OCR.

| Component | Choice and reason |
|---|---|
| Python | Add official **3.12.10 x64** alongside 3.13 to match the CPU diagnostic interpreter |
| Paddle framework | **paddlepaddle-gpu 3.3.0**, official **cu118** Windows CPython 3.12 wheel |
| PaddleOCR / PaddleX | **3.3.2 / 3.3.10**, unchanged |
| Driver | Retain **537.70**; it exceeds CUDA 11.8's Windows toolkit driver **522.06** |
| Models | Existing `PP-OCRv5_mobile_det` and `en_PP-OCRv5_mobile_rec`, exact same file hashes |
| OCR settings | Change only `device: cpu` to `gpu:0`; FP32, thresholds, resizing, orientation switches, HPI/TensorRT/MKLDNN settings and CPU threads stay fixed |
| Environments/caches | New `.venv-ocr-gpu` and `gpu-diagnostic-200dpi-...`; never resume a CPU cache as GPU |

Official sources:

- [Paddle's cu118 wheel index](https://www.paddlepaddle.org.cn/packages/stable/cu118/paddlepaddle-gpu/) lists `paddlepaddle_gpu-3.3.0-cp312-cp312-win_amd64.whl`. The prose [Windows installation page](https://www.paddlepaddle.org.cn/documentation/docs/en/install/pip/windows-pip_en.html) still shows 3.2.2 GPU examples; wheel availability was checked directly rather than inferring it from that example.
- [NVIDIA CUDA 11.8 release notes, Tables 2 and 3](https://docs.nvidia.com/cuda/archive/11.8.0/cuda-toolkit-release-notes/) give 452.39 for Windows minor-version compatibility and 522.06 for the CUDA 11.8 toolkit driver. 537.70 exceeds both.
- [PaddleOCR framework installation](https://www.paddleocr.ai/main/en/version3.x/paddlepaddle_installation.html) documents the cu118 channel and driver requirement; its cu126 route has a higher stated driver requirement. Use **cu118**, not an unreviewed default CUDA wheel.
- [Python 3.12.10 release and Windows installers](https://www.python.org/downloads/release/python-31210/) provide the matching interpreter.
- [Paddle device synchronization API](https://www.paddlepaddle.org.cn/documentation/docs/en/api/paddle/device/synchronize_en.html) waits for device work; GPU page timings explicitly synchronize around prediction.

This establishes a compatible installation choice, not successful local CUDA
execution. Do not install a new system CUDA toolkit, TensorRT, GPU driver or
global Python packages for this stage. The official wheel supplies its runtime
dependencies; the setup check must actually pass on this Windows installation.

## 1. Apply the incremental patch on the second machine

```powershell
Set-Location 'C:\Users\mbarroso\Downloads\Research-Seminar-OCR-gpu'
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Repo = (Get-Location).Path
if ((git rev-parse HEAD).Trim() -ne '61a696d9ca7dd0c505b1de662ca3eaea57ed3e9d') { throw 'Use the specified 61a696d checkout with the full-report final patch applied.' }
$Patch = Join-Path $env:USERPROFILE 'Downloads\gpu-support-incremental.patch'
git apply --check -- $Patch
if ($LASTEXITCODE -ne 0) { throw 'Incremental patch does not match; preserve existing files and inspect the conflict.' }
git apply -- $Patch
if ($LASTEXITCODE -ne 0) { throw 'GPU patch application failed.' }
git diff --check
if ($LASTEXITCODE -ne 0) { throw 'Whitespace check failed.' }
git status --short
```

The CPU wrappers, old full-report guide, frozen BM25/expansion modules, configs
and historical results are unchanged. CPU remains the default device. The
incremental patch must not be applied twice or substituted for the earlier
cumulative patch. Keep both delivered patches and the recovery patch.

## 2. Copy immutable source inputs and the CPU diagnostic snapshot

Before continuing, copy these **existing** inputs from the first machine or a
retained backup to the same data-root layout on the second machine:

1. The **complete** finalized rendering directory
   `derived\rendered\poppler-200dpi-20261013T043945Z-f407621a`, including all
   2,620 PNGs and both metadata files. Even the eight-page diagnostic verifies
   all source image checksums before/after; an eight-image ZIP alone is insufficient.
2. The complete model directory `models\paddleocr-3.3.2-mobile-en`, including
   `model_manifest.json` and all listed detector/recognizer files. Do not redownload
   or overwrite weights.
3. The retained `financial-table-diagnostic.zip`, saved in Downloads. Use the
   **diagnostic snapshot**, not a copy of the currently changing full CPU cache.
   It includes the selection, source-render snapshot, raw attempts and worker logs.

No questions, answers, evidence labels or native text are supplied to OCR. The
diagnostic selection from the archived source-only process is reused directly.
Original PDFs need not be copied for this diagnostic; source-PDF hashes and
physical-page IDs stay bound through the retained rendering contract.

```powershell
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$RenderDir = Join-Path $DataRoot 'derived\rendered\poppler-200dpi-20261013T043945Z-f407621a'
$ModelsDir = Join-Path $DataRoot 'models\paddleocr-3.3.2-mobile-en'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$AuditDir = Join-Path $DataRoot "audits\gpu-diagnostic-$Stamp"
$GpuDir = Join-Path $DataRoot "derived\ocr\gpu-diagnostic-200dpi-$Stamp"
$DeviceComparisonDir = Join-Path $AuditDir 'cpu-gpu-comparison'
$ReferenceRoot = Join-Path $AuditDir 'cpu-reference'
$Wheelhouse = Join-Path $AuditDir 'wheelhouse'
$Requirements = Join-Path $AuditDir 'cpu-nonframework-requirements.txt'
$null = New-Item -ItemType Directory -Path $AuditDir
$null = New-Item -ItemType Directory -Path $Wheelhouse
Expand-Archive -LiteralPath (Join-Path $env:USERPROFILE 'Downloads\financial-table-diagnostic.zip') -DestinationPath $ReferenceRoot
$CpuReference = Join-Path $ReferenceRoot 'cpu-full-200dpi-20261017T204901Z-f3f8357f'
$Selection = Join-Path $ReferenceRoot 'financial-table-selection.json'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$Checks = @(
    @{ Path=(Join-Path $CpuReference 'run_manifest.json'); SHA='cd0fa0c899c9298dcc75194318114b6b947840fd663a4847ced4cf6452412d7e' },
    @{ Path=$Selection; SHA='7f3b4c5a8e7b9fedafb79b3623c780e30fcf7f26b427d4322b10c681e30fc5d2' },
    @{ Path=(Join-Path $RenderDir 'run_manifest.json'); SHA='1ff37ad01d37e3d961b3ae0d27805a1dde244023f7cd830c3bbab876c8c5ebce' },
    @{ Path=(Join-Path $ModelsDir 'model_manifest.json'); SHA='d0a91a2378b843c0fcc3ea007e4505072277b55f3b6aa07ffab15c3af8a07cf4' }
)
foreach ($Check in $Checks) {
    if ((Get-FileHash -LiteralPath $Check.Path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $Check.SHA) { throw "Immutable input mismatch: $($Check.Path)" }
}
```

Expected zero-based source pages:

| Report | Pages |
|---|---|
| AMD 2015 | 55, 57 |
| Best Buy 2015 | 58, 60 |
| Boeing 2015 | 50, 52 |
| PepsiCo 2015 | 73, 76 |

## 3. Inventory existing environments without modifying them

This works even if the second checkout has no `.venv` or `.venv-ocr`. Keep these
functions in the current PowerShell session for the final preservation check.

```powershell
function Get-ProtectedEnvironments {
    $Inventory = [ordered]@{}
    foreach ($Name in @('.venv','.venv-ocr')) {
        $Python = Join-Path $Repo "$Name\Scripts\python.exe"
        if (Test-Path -LiteralPath $Python -PathType Leaf) {
            $Version = @(& $Python --version)
            if ($LASTEXITCODE -ne 0) { throw "Interpreter inventory failed: $Name" }
            $Packages = @(& $Python -m pip freeze --all)
            if ($LASTEXITCODE -ne 0) { throw "Package inventory failed: $Name" }
            $Inventory[$Name] = [ordered]@{ exists=$true; python=$Python; version=$Version; packages=$Packages }
        } else { $Inventory[$Name] = [ordered]@{ exists=$false } }
    }
    return ($Inventory | ConvertTo-Json -Depth 8)
}
$ProtectedBefore = Get-ProtectedEnvironments
[IO.File]::WriteAllText((Join-Path $AuditDir 'protected-environments-before.json'), $ProtectedBefore, $Utf8)
$NvidiaBefore = @(& nvidia-smi.exe --query-gpu=index,name,driver_version,memory.total,memory.free --format=csv,noheader)
if ($LASTEXITCODE -ne 0) { throw 'NVIDIA inventory failed.' }
[IO.File]::WriteAllText((Join-Path $AuditDir 'nvidia-before.txt'), ($NvidiaBefore -join "`n") + "`n", $Utf8)
$NvidiaBefore
```

## 4. Add Python 3.12.10 per user, retaining Python 3.13

This uses the signed official installer with no PATH or launcher replacement.
It does not request administrator installation. If this dedicated target already
exists, use its verified interpreter; do not install over an unrelated Python.

```powershell
$PythonHome = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312OCR'
$Python312 = Join-Path $PythonHome 'python.exe'
if (-not (Test-Path -LiteralPath $Python312 -PathType Leaf)) {
    if (Test-Path -LiteralPath $PythonHome) { throw 'Dedicated interpreter directory exists but is incomplete; inspect it first.' }
    $Installer = Join-Path $AuditDir 'python-3.12.10-amd64.exe'
    Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $Installer
    $Signature = Get-AuthenticodeSignature -LiteralPath $Installer
    if ($Signature.Status -ne 'Valid' -or $Signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') { throw 'Official Python installer signature did not verify.' }
    $Install = Start-Process -FilePath $Installer -Wait -PassThru -ArgumentList @('/quiet','InstallAllUsers=0',('TargetDir="' + $PythonHome + '"'),'PrependPath=0','Include_launcher=0','Include_test=0','Include_pip=1')
    if ($Install.ExitCode -ne 0) { throw "Python installer failed: $($Install.ExitCode)" }
    Get-FileHash -LiteralPath $Installer -Algorithm SHA256 | Format-List
}
$PythonCheck = @'
import sys, struct
assert sys.version_info[:3] == (3, 12, 10) and struct.calcsize("P") == 8
print(sys.executable)
print(sys.version)
'@
$PythonCheck | & $Python312 -
if ($LASTEXITCODE -ne 0) { throw 'Expected Python 3.12.10 x64.' }
```

## 5. Prepare an isolated, pinned GPU environment and wheel snapshot

The helper uses only the standard library and verifies the immutable CPU
reference before exporting its exact non-framework pins, including pip and
setuptools. CPU Paddle is excluded; GPU Paddle 3.3.0 is obtained specifically
from the official CUDA 11.8 index. The project is installed editable without
dependency changes after the package snapshot has been installed.

```powershell
$GpuEnvironment = Join-Path $Repo '.venv-ocr-gpu'
if (Test-Path -LiteralPath $GpuEnvironment) { throw 'GPU environment already exists; preserve it and inspect its saved setup rather than overwriting it.' }
& $Python312 .\scripts\prepare_gpu_requirements.py --cpu-dir $CpuReference --output $Requirements
if ($LASTEXITCODE -ne 0) { throw 'CPU reference/requirements verification failed.' }
& $Python312 -m venv $GpuEnvironment
if ($LASTEXITCODE -ne 0) { throw 'GPU environment creation failed.' }
$GpuPython = Join-Path $GpuEnvironment 'Scripts\python.exe'
& $GpuPython -m pip download --only-binary=:all: --no-deps --index-url 'https://www.paddlepaddle.org.cn/packages/stable/cu118/' --dest $Wheelhouse 'paddlepaddle-gpu==3.3.0'
if ($LASTEXITCODE -ne 0) { throw 'Official CUDA 11.8 Windows GPU wheel download failed.' }
$GpuWheels = @(Get-ChildItem -LiteralPath $Wheelhouse -File -Filter 'paddlepaddle_gpu-3.3.0-cp312-cp312-win_amd64.whl')
if ($GpuWheels.Count -ne 1) { throw 'Expected exactly the reviewed Windows CPython 3.12 GPU wheel.' }
$GpuWheel = $GpuWheels[0].FullName
& $GpuPython -m pip download --only-binary=:all: --index-url 'https://pypi.org/simple' --dest $Wheelhouse --requirement $Requirements $GpuWheel
if ($LASTEXITCODE -ne 0) { throw 'Pinned dependency wheel resolution failed; retain the error and do not loosen the CPU pins.' }
Get-ChildItem -LiteralPath $Wheelhouse -File | Get-FileHash -Algorithm SHA256 | Export-Csv -LiteralPath (Join-Path $AuditDir 'wheel-sha256.csv') -NoTypeInformation
& $GpuPython -m pip install --no-index --find-links $Wheelhouse --report (Join-Path $AuditDir 'gpu-install-report.json') --requirement $Requirements $GpuWheel
if ($LASTEXITCODE -ne 0) { throw 'Offline pinned GPU installation failed.' }
& $GpuPython -m pip install --no-build-isolation --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw 'Editable GPU project installation failed.' }
& $GpuPython -m pip check
if ($LASTEXITCODE -ne 0) { throw 'GPU dependency consistency check failed.' }
$GpuFreeze = @(& $GpuPython -m pip freeze --all)
if ($LASTEXITCODE -ne 0) { throw 'GPU package inventory failed.' }
[IO.File]::WriteAllText((Join-Path $AuditDir 'gpu-packages.txt'), ($GpuFreeze -join "`n") + "`n", $Utf8)
```

If wheel resolution fails, stop at setup and supply the exact error. No source
build, package upgrade, CPU fallback, cu126/cu129 substitution or driver update
is part of this condition. Preserve the downloaded wheels and install report.

## 6. Verify the actual CUDA runtime and run the test suite

```powershell
& $GpuPython .\scripts\check_gpu_environment.py --cpu-dir $CpuReference --output (Join-Path $AuditDir 'gpu-runtime.json')
if ($LASTEXITCODE -ne 0) { throw 'GPU runtime check failed; retain gpu-runtime.json and console output before OCR.' }
Get-Content -LiteralPath (Join-Path $AuditDir 'gpu-runtime.json') -Raw
```

This checks the actual driver, compiled CUDA **11.8**, GPU device 0, GPU
properties and a real Paddle installation check. It rejects a CPU framework,
mixed CPU/GPU distributions and changed shared dependency pins. This is setup
validation, not an OCR result. If DLL loading or Paddle's check fails, provide
the saved error; do not alter the CPU condition to resolve GPU setup.

The renderer is not run by GPU OCR. For all rendering fixture tests, copy the
existing portable Poppler directory to `tools\poppler-v26.09.0-0` if it is not
already on this machine. No renderer installation into either Python environment
is needed. A temporary PATH is restored after this test block:

```powershell
$Poppler = @(Get-ChildItem -LiteralPath (Join-Path $DataRoot 'tools\poppler-v26.09.0-0') -Recurse -File -Filter 'pdftoppm.exe')
if ($Poppler.Count -ne 1) { throw 'Locate the one existing portable Poppler executable for the fixture tests.' }
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
    $TestRunner | & $GpuPython - (Join-Path $AuditDir 'tests-windows-gpu.txt')
    $TestExit = $LASTEXITCODE
} finally { $env:PATH = $SavedPath }
if ($TestExit -ne 0) { throw 'Tests failed; retain the log before continuing.' }
```

Expected suite: **171 tests, OK, no skips**. The test suite uses simulated OCR
workers; the separate runtime check above is what exercises installed Paddle.

## 7. Run only the same eight diagnostic pages

Save paths before launching the diagnostic. Do not precreate `$GpuDir`.

```powershell
$Paths = [ordered]@{ Repo=$Repo; DataRoot=$DataRoot; Stamp=$Stamp; AuditDir=$AuditDir; RenderDir=$RenderDir; ModelsDir=$ModelsDir; CpuReference=$CpuReference; Selection=$Selection; GpuDir=$GpuDir; DeviceComparisonDir=$DeviceComparisonDir; GpuPython=$GpuPython }
$PathsFile = Join-Path $AuditDir 'gpu-run-paths.json'
[IO.File]::WriteAllText($PathsFile, ($Paths | ConvertTo-Json) + "`n", $Utf8)
Write-Host "Retain: $PathsFile"
& .\scripts\run_gpu_diagnostic.ps1 -DataRoot $DataRoot -RenderDir $RenderDir -RunDir $GpuDir -Selection $Selection
$GpuManifest = Get-Content -LiteralPath (Join-Path $GpuDir 'run_manifest.json') -Raw | ConvertFrom-Json
$GpuManifest.coverage | ConvertTo-Json -Depth 8
if ($GpuManifest.status -ne 'diagnostic_complete' -or $GpuManifest.coverage.completed_engine_pages -ne 8 -or $GpuManifest.coverage.pending_pages -ne 2612) { throw 'GPU diagnostic incomplete; inspect failures and logs.' }
```

All 12 reports and 2,620 zero-based source records remain in the plan; only
these eight source pages are attempted. Model initialization is reused within
each report, matching the CPU orchestration. Successful blank responses remain
explicit; inspect them rather than treating completion as quality.

On interruption, wait for the process to exit and rerun the wrapper with the
same arguments plus `-Resume`. Verified successful/blank results are reused;
failed/timed-out/interrupted attempts are preserved and retried. Never point
the GPU wrapper at a CPU cache, delete a cache lock to force a second writer,
or modify code/packages within a resumable condition.

## 8. Compare outputs and timing, then inspect every financial table

```powershell
& $GpuPython -m finocr.cli compare-ocr-devices --cpu-dir $CpuReference --gpu-dir $GpuDir --selection $Selection --output-dir $DeviceComparisonDir
if ($LASTEXITCODE -ne 0) { throw 'Device comparison failed or retained diagnostic failures; inspect saved records.' }
Get-Content -LiteralPath (Join-Path $DeviceComparisonDir 'device_comparison.md') -Raw
```

The comparator is read-only on both caches. It validates manifest artifact
hashes, full rendering/source identity, exact eight-page selection, model hashes,
fixed settings, actual worker device/CUDA and immutable raw/normalized attempts.
It rejects changed shared dependencies; any GPU-only additions are listed.
It writes:

| Output | What to inspect |
|---|---|
| `device_comparison.json` | Every page's status, exact text/line/number equality, confidence/geometry differences, CPU/GPU timing, runtime/package/code identities |
| `device_comparison.md` | Eight-page summary; full GPU recommendation remains pending review |
| `page-01-text.diff` through `page-08-text.diff` | Literal text changes, including signs and years |
| `page-01-lines.json` through `page-08-lines.json` | Both conditions' complete normalized lines, polygons, ordering and confidences |

Open the PNGs and both raw line/box outputs. Check currency/scale, year columns,
minus signs/parentheses, decimals, and each row/column association. Equal numeric
multisets do not prove correct table structure. GPU kernels may produce small
confidence or coordinate differences without text changes; retain these rather
than requiring bit-identical raw JSON or correcting text manually. Review every
text/number difference and failed/blank page before deciding whether GPU can be
carried forward.

GPU page time synchronizes before/after prediction and includes serialization.
Compare page totals separately from model startup and whole-invocation wall
time. Cumulative histories include diagnostic/retry work; latest selected-page
times are reported separately. Different machines, CPU hardware, code adapter,
startup and load can confound the timing. This is a descriptive eight-page
comparison, not a pure device speedup, repeated latency benchmark, full-corpus
throughput prediction, CER/WER or financial-accuracy evaluation.

**Stop here for review.** Supply real GPU setup and diagnostic outputs before a
full GPU execution is recommended. No full-run command is proposed at this stage.
If later approved, extend only the separate GPU cache; the CPU run remains a
separate condition. Matched retrieval support is ready for the same frozen
expansion v1 at k=5, full-report candidates and label exclusion, after a complete
GPU cache exists and its lineage/coverage has been verified.

## 9. Preservation check and output bundle

```powershell
$ProtectedAfter = Get-ProtectedEnvironments
[IO.File]::WriteAllText((Join-Path $AuditDir 'protected-environments-after.json'), $ProtectedAfter, $Utf8)
if ($ProtectedAfter -cne $ProtectedBefore) { throw 'Existing baseline/CPU environment inventory changed; inspect both records.' }
$ExportDir = Join-Path $DataRoot "exports\gpu-diagnostic-$Stamp"
$null = New-Item -ItemType Directory -Path $ExportDir
Compress-Archive -LiteralPath $GpuDir -DestinationPath (Join-Path $ExportDir 'gpu-diagnostic-cache.zip')
Compress-Archive -LiteralPath $DeviceComparisonDir -DestinationPath (Join-Path $ExportDir 'cpu-gpu-comparison.zip')
$SmallAudit = Join-Path $ExportDir 'setup-audit'
$null = New-Item -ItemType Directory -Path $SmallAudit
Get-ChildItem -LiteralPath $AuditDir -File | Copy-Item -Destination $SmallAudit
Compress-Archive -LiteralPath $SmallAudit -DestinationPath (Join-Path $ExportDir 'gpu-setup-audit.zip')
Get-ChildItem -LiteralPath $ExportDir -File | Get-FileHash -Algorithm SHA256
```

Retain the complete wheelhouse locally; the setup audit ZIP contains wheel
hashes and the install report without uploading large dependency wheels. Keep
all GPU attempts, worker logs and the unchanged CPU reference snapshot. Neither
the rendered image tree nor model weights are duplicated in the GPU cache.
Include a short manual table-inspection note with the uploaded outputs.

To reopen a session, set `$PathsFile` to the printed full path, then restore:

```powershell
$Saved = Get-Content -LiteralPath $PathsFile -Raw | ConvertFrom-Json
foreach ($Entry in $Saved.PSObject.Properties) { Set-Variable -Name $Entry.Name -Value $Entry.Value }
Set-Location $Repo
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$ProtectedBefore = [IO.File]::ReadAllText((Join-Path $AuditDir 'protected-environments-before.json'))
```

Reenter `Get-ProtectedEnvironments` from section 3 before the after check.
Do not rerun setup or create another environment to resume a cache.

## Validation status

Completed in development: the supplied CPU snapshot/raw attempts and eight PNG
checksums verify; official wheel/driver compatibility is checked; the prior 157
tests plus 14 new device/comparison tests pass with no skips on Linux. No GPU
dependencies or models were installed/run on the development host.

Pending on Windows: interpreter/GPU environment installation, real driver/CUDA
check, Windows test execution, eight-page GPU OCR, output/timing comparison and
manual table inspection. Full GPU execution and new experimental findings remain
pending real outputs and review. The first machine's CPU run continues separately.
