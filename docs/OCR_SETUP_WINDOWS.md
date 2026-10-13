# OCR phase: inventory, full-report rendering, one-page smoke

Starting checkpoint: `bb274db5436473984456c1e95e30b1407337c1c4`.
Expansion v1 is now frozen for matched native/OCR retrieval at k=5. Preserve
all earlier controls and heading-format results. No more heading-format tuning
is planned. This patch implements setup tools, not new experimental results.
The suite has 138 passing tests, including 15 new rendering/OCR-contract checks
with actual small Poppler-rendered PDF fixtures and a simulated OCR worker. No
Paddle inference, Windows PowerShell or Windows Poppler execution was performed
in the development environment; those steps require the local commands below.

**Run the no-install inventory first and return its output before installing
OCR dependencies.** The assistant cannot read the Windows machine from this
workspace. Previously reported i5-12600K/16-GB/RTX-3060 and baseline Python
3.13.7 are historical information; current RAM, available disk, GPU model/VRAM,
driver and available interpreters require local measurement. Missing nvidia-smi
means NVIDIA inventory is unavailable, not proof that there is no GPU.

## 1. Apply and collect current machine information (no installs)

Download `ocr-setup.patch` to Downloads, then use the existing repository:

```powershell
Set-Location "C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current"
git rev-parse --short HEAD
git status --short
$patchPath = Join-Path $env:USERPROFILE "Downloads\ocr-setup.patch"
git apply --check $patchPath
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; preserve local changes and inspect the diagnostic." }
git apply $patchPath
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }
& .\.venv\Scripts\python.exe -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed." }
& .\scripts\check_ocr_machine.ps1
```

This script only queries hardware/Python and writes a new audit directory. It
collects GPU name, dedicated total/free VRAM and driver via nvidia-smi when
available; OS/CPU, physical/available RAM, free/total disk per local drive,
Python launcher installations and the baseline interpreter's path/version/bits.
It saves `machine_inventory.json` and `baseline-packages.txt` outside Git, with
a package-inventory SHA. Win32 AdapterRAM is supplementary and can truncate
large VRAM values; use successful nvidia-smi memory readings. The nvidia-smi
CUDA banner describes driver capability, not an installed toolkit or a tested
Paddle GPU configuration.

**Stop here for the first handoff.** Send the JSON (and any missing-tool/error
output). The remaining blocks are the concrete proposed setup, to execute after
reviewing this information. No automatic install is embedded in the inventory,
renderer or smoke command. No CUDA toolkit, GPU wheel, WSL or driver change is
proposed before current hardware/driver compatibility is checked.

## 2. Portable Poppler renderer, outside the Python environments

The renderer uses the existing baseline `.venv`; its Python dependencies do
not change. Use a fixed portable Windows Poppler build from its build publisher:
[v26.09.0-0 release](https://github.com/oschwartz10612/poppler-windows/releases/tag/v26.09.0-0).
The following downloads the named release asset, records its SHA and validates
the published asset digest when provided. It never changes global PATH.

```powershell
$dataRoot = "C:\Users\mbarroso\financial-ocr-data"
$toolRoot = Join-Path $dataRoot "tools\poppler-v26.09.0-0"
if (Test-Path -LiteralPath $toolRoot) { throw "Poppler setup directory exists; retain it and use its existing executable." }
$null = New-Item -ItemType Directory -Path $toolRoot
$release = Invoke-RestMethod "https://api.github.com/repos/oschwartz10612/poppler-windows/releases/tags/v26.09.0-0"
$assets = @($release.assets | Where-Object { $_.name -eq "Release-26.09.0-0.zip" })
if ($assets.Count -ne 1) { throw "Pinned release asset was not found; do not substitute latest." }
$archive = Join-Path $toolRoot $assets[0].name
Invoke-WebRequest -Uri $assets[0].browser_download_url -OutFile $archive
$archiveSha = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
$digestProperty = $assets[0].PSObject.Properties["digest"]
if ($digestProperty -and $digestProperty.Value -and $digestProperty.Value -ne "sha256:$archiveSha") {
    throw "Downloaded Poppler asset differs from its published digest."
}
$release | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath (Join-Path $toolRoot "release-metadata.json") -Encoding UTF8
$archiveSha | Set-Content -LiteralPath (Join-Path $toolRoot "archive-sha256.txt") -Encoding ASCII
Expand-Archive -LiteralPath $archive -DestinationPath (Join-Path $toolRoot "bundle")
$rendererFiles = @(Get-ChildItem -LiteralPath (Join-Path $toolRoot "bundle") -Recurse -File -Filter "pdftoppm.exe")
if ($rendererFiles.Count -ne 1) { throw "Expected exactly one pdftoppm executable." }
$rendererPath = $rendererFiles[0].FullName
& $rendererPath -v
if ($LASTEXITCODE -ne 0) { throw "Poppler startup failed; retain the error output." }
```

The run records exact executable/DLL byte identities and version output. Retain
the archive/build metadata with the cache. The Linux Poppler used in fixture
tests is not a validation of the Windows binary or your real report fonts.

## 3. Render source-only samples, inspect, then complete the full cache

Use a new cache outside Git. Three physical pages per report (first, middle,
last) provide an initial **36-page setup sample**, including long reports and
attachments, without loading QA/evidence annotations. Every one of the 2,620
planned page records remains visible, with unrendered pages marked pending.

```powershell
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$renderDir = Join-Path $dataRoot "derived\rendered\poppler-200dpi-$stamp"
& .\scripts\run_report_rendering.ps1 -RendererPath $rendererPath -RunDir $renderDir -DataRoot $dataRoot -Dpi 200 -Sample
Get-Content -LiteralPath (Join-Path $renderDir "run_manifest.json") -Raw
```

Inspect actual images at display zoom: small figures, footnotes, rotation and
the apparent end/attachment pages. If needed, create a separate 300-DPI setup
sample; it must not overwrite/change the 200-DPI cache:

```powershell
$render300Dir = Join-Path $dataRoot "derived\rendered\poppler-300dpi-$stamp"
& .\scripts\run_report_rendering.ps1 -RendererPath $rendererPath -RunDir $render300Dir -DataRoot $dataRoot -Dpi 300 -Sample
```

Record the resolution choice before matched retrieval evaluation. Rendering is
8-bit RGB PNG with default MediaBox/PDF rotation, no crop, deskew or denoising.
Raw physical PDF IDs stay zero-based. Only the pdftoppm invocation translates
an ID to one-based `-f/-l`; printed page numbers never replace source IDs.
Store source PDF hash, box/rotation, DPI, actual pixel dimensions and image hash.

The manifests' `rendered_image_bytes` and `observed_bytes_per_rendered_page` let
you estimate storage from actual samples. Multiplying the sample average by
2,620 is a planning estimate, not a guaranteed disk requirement; attachments,
colour and page sizes can differ. Reserve space for images, model archives,
environments/wheels and output caches on the actual data drive.

After visual/disk checks, resume the **chosen** cache without `-Sample`:

```powershell
& .\scripts\run_report_rendering.ps1 -RendererPath $rendererPath -RunDir $renderDir -DataRoot $dataRoot -Dpi 200 -Resume
```

For a chosen 300-DPI cache, use `$render300Dir` and `-Dpi 300` in that command.
Do not change DPI in an existing cache. Completed image hashes/settings are
verified before reuse; failed/pending pages retry. Use one renderer process per
cache. Source PDFs are verified against the **original native run** and the
unchanged pilot document manifest before and after rendering. All 12 reports,
including those without questions, and all blank/exhibit pages are included.

`sample_complete` means only the setup sample is complete.
`full_report_rendering_complete: true` with 12 reports / 2,620 successful pages
is the full-rendering gate. A partial/failing cache does not silently shrink the
cohort. Per-page records survive interruption; resume the same settings. A new
input PDF/manifest/renderer requires a new cache. The command writes progress
for every attempted page and uses a 120-second page deadline.

## 4. Proposed first OCR environment: pinned CPU smoke, isolated Python 3.12

Use a **separate 64-bit Python 3.12** environment at `.venv-ocr`. The existing
`.venv` remains the baseline/audit/retrieval environment; do not install model
frameworks into it. The official Windows Paddle installation page supports
Python 3.12/x64 and lists the CPU 3.3.0 package. PaddleOCR 3.3.2 supplies the
standard detection/recognition API used here. This is a practical pretrained
PP-OCRv5 smoke proposal, not replication of the paper's historical OCRv3 setup,
PP-Structure, PaddleOCR-VL, or Unlimited OCR.

Check that `py -0p` from the inventory lists Python 3.12. If absent, stop and
resolve a side-by-side interpreter install after reviewing the inventory; do
not replace the baseline Python or improvise with 3.13. The local installation
and real API/runtime compatibility are pending, despite published support.

The following are the **exact proposed dependency commands**, provided before
any installation. Execute only after the inventory review:

```powershell
py -3.12 -c "import sys,struct; print(sys.version); print(struct.calcsize('P')*8)"
if ($LASTEXITCODE -ne 0) { throw "64-bit Python 3.12 must be available first." }
if (Test-Path -LiteralPath ".\.venv-ocr") { throw "OCR environment exists; retain and inspect it before reusing." }
py -3.12 -m venv .venv-ocr
if ($LASTEXITCODE -ne 0) { throw "OCR venv creation failed." }
$ocrPython = (Resolve-Path ".\.venv-ocr\Scripts\python.exe").Path
& $ocrPython -m pip --version
& $ocrPython -m pip install "paddlepaddle==3.3.0" -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
if ($LASTEXITCODE -ne 0) { throw "CPU framework installation failed." }
& $ocrPython -m pip install -r .\requirements\ocr-smoke.txt
if ($LASTEXITCODE -ne 0) { throw "Pinned OCR dependencies failed to resolve/install; do not loosen pins silently." }
& $ocrPython -m pip check
if ($LASTEXITCODE -ne 0) { throw "OCR dependency conflicts remain." }
& $ocrPython -c "import paddle; print(paddle.__version__); paddle.utils.run_check()"
if ($LASTEXITCODE -ne 0) { throw "Framework setup check failed." }
```

Direct OCR pins are PaddleOCR 3.3.2 and PaddleX 3.3.10; pypdf 6.19.0 allows the
same lightweight project package contract in this separate environment. Other
dependencies are resolved by pip, **not already fully locked by this patch**.
Capture the actual successful Windows resolution before adding the editable
project and retain wheel bytes/hashes for faithful reconstruction:

```powershell
$ocrSetupDir = Join-Path $dataRoot "audits\ocr-cpu-setup-$stamp"
$null = New-Item -ItemType Directory -Path $ocrSetupDir
$dependencyLock = Join-Path $ocrSetupDir "dependencies.freeze.txt"
& $ocrPython -m pip freeze | Set-Content -LiteralPath $dependencyLock -Encoding ASCII
if ($LASTEXITCODE -ne 0) { throw "Could not capture the OCR dependency lock." }
$wheelDir = Join-Path $ocrSetupDir "wheels"
& $ocrPython -m pip download --only-binary=:all: -r $dependencyLock --dest $wheelDir `
    --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cpu/
if ($LASTEXITCODE -ne 0) { throw "Wheel snapshot incomplete; retain logs and resolve before claiming reproducible setup." }
Get-ChildItem -LiteralPath $wheelDir -File | Get-FileHash -Algorithm SHA256 | Format-List | Out-File (Join-Path $ocrSetupDir "wheel-sha256.txt")
& $ocrPython -m pip install --no-deps -e .
if ($LASTEXITCODE -ne 0) { throw "Project installation in OCR environment failed." }
```

For reconstruction on the same OS/architecture/Python family, install the saved
lock with `--no-index --find-links $wheelDir`, then install the same project
commit with `--no-deps -e .`. Python patch version, pip version, wheel hashes and
the executed source revision are also part of the setup identity. GPU wheels
and their runtime/driver requirements are a later device setup decision; this
smoke deliberately declares CPU rather than relying on automatic GPU selection.

## 5. Acquire explicit model weights and run exactly one OCR smoke

The model names are fixed: `PP-OCRv5_mobile_det` and `en_PP-OCRv5_mobile_rec`.
The acquisition helper downloads their official inference archives separately
from inference, safely extracts them and records archive/config/weight hashes.
Initial hashes are **observed acquisition identities**, not publisher-published
expected digests; retain this exact bundle and manifest. Subsequent smoke
runs reject any missing/changed model file and pass explicit local model paths.

```powershell
$modelDir = Join-Path $dataRoot "models\paddleocr-3.3.2-mobile-en"
& $ocrPython .\scripts\acquire_ocr_models.py --output-dir $modelDir
if ($LASTEXITCODE -ne 0) { throw "Model acquisition failed; inspect its manifest." }
$smokeStamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$smokeDir = Join-Path $dataRoot "derived\ocr\cpu-smoke-$smokeStamp"
& $ocrPython -m finocr.cli ocr-smoke --render-dir $renderDir --models-dir $modelDir `
    --output-dir $smokeDir --doc-id "financebench:AMD_2015_10K" --page-index 0 `
    --repository-root (Get-Location).Path --timeout-seconds 600
if ($LASTEXITCODE -ne 0) { throw "OCR smoke failed, timed out, or returned blank text requiring review." }
Get-Content -LiteralPath (Join-Path $smokeDir "run_manifest.json") -Raw
Get-Content -LiteralPath (Join-Path $smokeDir "ocr_pages.jsonl")
```

Page 0 of the first pilot report is a **source-selected setup page**, not a
gold-selected diagnostic or financial accuracy benchmark. It is included in the
rendering sample, so the one-page smoke can run before full rendering finishes.
Use `$render300Dir` if 300 DPI was chosen. No native-text snippets, questions,
answers, justifications or evidence labels are passed to the OCR engine.

The adapter saves immutable raw model JSON, recognized lines, confidence,
quadrilateral boxes, engine order, literal raw text and the existing NFKC search
normalization. No table reconstruction, heading modification or answer-based
correction is applied. Fixed CPU FP32 settings disable document rotation,
unwarping, text-line orientation, high-performance inference/TensorRT and MKL-DNN;
two CPU threads and the exact detector thresholds/resize policy are recorded.
The 1024-pixel maximum detector side length is **internal model resizing**,
separate from the stored rendered DPI. It is provisional until real source/numeric
smoke inspection, not a claimed financial-quality optimum.

Initialization/inference run in a separate process with a 600-second total
deadline, 30-second progress heartbeat and `worker.log`. Failure/timeout writes
a source-mapped failed page record. Empty recognition is explicitly
`blank_requires_review`, not an accepted successful transcription. A successful
`smoke_complete` means nonempty structurally valid output on **one page**;
`full_ocr_coverage` stays false. It establishes no CER/WER, QA accuracy, retrieval
recall, full-pilot throughput, GPU feasibility or energy result.

After installation/smoke, verify that baseline packages and interpreter match
the first inventory (paste the exact initial inventory path):

```powershell
$initialInventory = "C:\Users\mbarroso\financial-ocr-data\audits\machine-check-PASTE-SUFFIX\machine_inventory.json"
& .\scripts\check_ocr_machine.ps1 -CompareWith $initialInventory
```

Return the hardware JSON, render manifest and smoke directory ZIP (including
raw output and worker log) for review. Report success/failure and the observed
versions/device first; experimental OCR/retrieval claims await real execution
and inspection. The next stage extends OCR to representative statement/numeric
pages and the 25 distinct evidence pages as an explicit oracle diagnostic, then
all report pages for matched frozen-expansion retrieval. A one-page smoke or
gold-only OCR cache cannot supply full-report Recall@5.

## Sources checked on 2026-10-13 UTC

- [Paddle Windows pip installation](https://www.paddlepaddle.org.cn/documentation/docs/install/pip/windows-pip_en.html): Windows/x64/Python and CPU framework command.
- [PaddleOCR 3.3.2 release](https://github.com/PaddlePaddle/PaddleOCR/releases/tag/v3.3.2) and [installation](https://www.paddleocr.ai/v3.3.2/en/version3.x/installation.html): pinned standard OCR package, separate from optional parsers.
- [PaddleOCR 3.3.2 OCR API](https://www.paddleocr.ai/v3.3.2/en/version3.x/pipeline_usage/OCR.html): explicit model names/paths, device/transform settings and JSON line/box output.
- [PaddleX 3.3.10 package](https://pypi.org/project/paddlex/3.3.10/): pinned underlying inference package.
- [Windows Poppler build publisher](https://github.com/oschwartz10612/poppler-windows/releases/tag/v26.09.0-0): pinned portable renderer build.

Published support and fixture tests do not prove this Windows environment/model
combination has executed. Current hardware measurements, installation success,
real rendering and OCR smoke outputs remain pending the user's local commands.
