# Qualification authorization binding: offline work only

Apply this increment over preparation + validation-v2 + review-docs + offline
repair + the reviewed qualification-runner patch. It is not a patch for bare
828ba06. The frozen qualification plan/reference, contract, prompt/token/grammar
controls, evaluator, model, execution settings and existing environments are
unchanged. Historical v2 stays 1/6; 12 requests spent, zero currently remaining.

All stages below are offline. They do not install anything, issue/install an
authorization or approval, create an allowance or campaign, start a server, or
generate answers. The only subprocesses are existing interpreters, pip inventory,
tests with mocked transports, Git, the standalone native converter, and read-only
hardware checks. Preserve both completed review directories and original ZIPs.

## A. Close the preservation gap FIRST, before applying the patch

Download `qualification-authorization-offline-delivery.zip` to Downloads. The ZIP
has a flat layout; extract into a NEW directory with these commands. The closeout
helper is also delivered separately and can run against the predecessor checkout.

```powershell
$ErrorActionPreference = 'Stop'
$Downloads = Join-Path $env:USERPROFILE 'Downloads'
$Stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$Bundle = Join-Path $Downloads 'qualification-authorization-offline-delivery.zip'
$Delivery = Join-Path $Downloads "qualification-authorization-offline-delivery-$Stamp"
if (Test-Path -LiteralPath $Delivery) { throw 'Preserve the existing extraction; choose a fresh timestamp.' }
Expand-Archive -LiteralPath $Bundle -DestinationPath $Delivery
$Repo = Join-Path $Downloads 'Research-Seminar-OCR-review'
$DataRoot = Join-Path $env:USERPROFILE 'financial-ocr-data'
$AnswerRoot = Join-Path $DataRoot 'answer-generation\qwen3-4b-instruct-2507-v1'
$Reviews = Join-Path $AnswerRoot 'reviews'
$AnswerPython = Join-Path $Repo '.venv-answer\Scripts\python.exe'
$ImplementationReview = Join-Path $Reviews 'qualification-implementation-20261019T204936Z'
$CompilerReview = Join-Path $Reviews 'compiler-followup-20261019T210821Z'
$OriginalSet = Join-Path $ImplementationReview 'before\preserved-hashes.txt'
$ImplementationArchive = Join-Path $Reviews 'qualification-implementation-20261019T204936Z-review.zip'
$CompilerArchive = Join-Path $Reviews 'compiler-followup-20261019T210821Z-review.zip'
$CampaignAnchor = Join-Path $AnswerRoot 'followups\synthetic-contract-v3-qualification'
$Approval = Join-Path $AnswerRoot 'authorizations\synthetic-contract-v3-qualification.approval.json'
$Authorization = Join-Path $AnswerRoot 'authorizations\synthetic-contract-v3-qualification.authorization.json'
$CloseoutHelper = Join-Path $Delivery 'close_qualification_preservation.py'
$Patch = Join-Path $Delivery 'qualification-authorization-incremental.patch'
$env:PYTHONPATH = Join-Path $Repo 'src'
$env:PYTHONDONTWRITEBYTECODE = '1'
Set-Location -LiteralPath $Repo
foreach ($Required in @($AnswerPython,$OriginalSet,$CompilerReview,$ImplementationArchive,$CompilerArchive,$CloseoutHelper,$Patch)) {
    if (-not (Test-Path -LiteralPath $Required)) { throw "Existing input missing: $Required" }
}
foreach ($Forbidden in @($CampaignAnchor,$Approval,$Authorization)) {
    if (Test-Path -LiteralPath $Forbidden) { throw "Unexpected execution/approval input: preserve it and stop: $Forbidden" }
}
$Manifest = Get-Content -Raw -LiteralPath (Join-Path $Delivery 'manifest.json') | ConvertFrom-Json
foreach ($Name in @('close_qualification_preservation.py','qualification-authorization-incremental.patch')) {
    $Expected = $Manifest.delivery_files.$Name
    $Actual = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $Delivery $Name)).Hash.ToLowerInvariant()
    if ($Actual -ne $Expected) { throw "Delivered file checksum mismatch: $Name" }
}
$InitialCloseout = Join-Path $Reviews "qualification-preservation-final-$Stamp"
$InitialCloseoutZip = "$InitialCloseout-review.zip"
& $AnswerPython $CloseoutHelper --repository $Repo --original-review $ImplementationReview --compiler-review $CompilerReview --original-archive $ImplementationArchive --compiler-archive $CompilerArchive --output $InitialCloseout --archive $InitialCloseoutZip
$CloseoutExit = $LASTEXITCODE
if (Test-Path -LiteralPath (Join-Path $InitialCloseout 'comparison.json')) {
    Get-Content -Raw -LiteralPath (Join-Path $InitialCloseout 'comparison.json')
}
if ($CloseoutExit -ne 0) { throw 'Closeout failed. Preserve its evidence; do not replace the original before set or continue.' }
Get-FileHash -Algorithm SHA256 -LiteralPath $InitialCloseoutZip
```

If the two original archives are stored elsewhere, set **only** the two archive
variables to their existing paths before invoking the helper. The helper requires
the reviewed archive SHA-256 values, not a newly repacked equivalent ZIP:

| Original ZIP | SHA-256 |
|---|---|
| qualification-implementation | `36b338daed91b607024c3dd9cbd1c831e5c8bf269ecfff05b73126b2f7ef07ad` |
| compiler-followup | `44c2558b2158259eb94b0664fd6bd012eaefb4462f464fc85f47e1e99c1b1913` |

The helper checks the untouched original before-file hashes, reads exactly its
184 absolute file paths, rehashes every file, and runs `pip freeze --all` through
the existing current-checkout `.venv` and `.venv-ocr`, and review-checkout
`.venv-answer`. Inventory comparison ignores line ordering and BOM/newline
encoding; package lines must match exactly, including the CPU torch wheel URL.
Both raw inventory hashes are retained. No package operation changes an environment.

It also rechecks the compiler preparation's complete protected roots, snapshots
both completed reviews and original archives before/after, copies the original
before files into the NEW evidence directory, and exports a NEW CRC/content-hash
verified ZIP and sidecar. Detected file/package changes, missing files and failed
inventories are retained as failures, without shrinking the denominator or
rebaselining. Output/export paths must be fresh siblings under `reviews`.
An invalid input can stop before a comparison file exists; retain the error and
any partial output. Do not rerun into an existing directory.

This closes the reviewed manifest/inventory scope. Cache-manifest agreement does
not assert a fresh byte-by-byte hash of every OCR page or environment file.

## B. Apply the increment and run offline tests

```powershell
& git status --short
& git -c core.autocrlf=input apply --check $Patch
if ($LASTEXITCODE -ne 0) { throw 'Increment does not match this checkout. Preserve edits; do not reset or reapply old patches.' }
& git -c core.autocrlf=input apply $Patch
if ($LASTEXITCODE -ne 0) { throw 'Patch application failed.' }
$ReviewRoot = Join-Path $Reviews "qualification-binding-offline-$Stamp"
if (Test-Path -LiteralPath $ReviewRoot) { throw 'Preserve the existing offline review.' }
New-Item -ItemType Directory -Path $ReviewRoot | Out-Null
$TestRunner = @'
import pathlib, subprocess, sys
with pathlib.Path(sys.argv[1]).open('xb') as log:
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-p', sys.argv[2], '-v'], stdout=log, stderr=subprocess.STDOUT)
print('Test exit code:', result.returncode)
raise SystemExit(result.returncode)
'@
$QualificationLog = Join-Path $ReviewRoot 'qualification-tests.txt'
& $AnswerPython -c $TestRunner $QualificationLog 'test_qualification*.py'
$QualificationExit = $LASTEXITCODE
Get-Content -Tail 8 -LiteralPath $QualificationLog
if ($QualificationExit -ne 0) { throw 'Offline qualification tests failed; preserve the log.' }
$BaselinePython = Join-Path $Downloads 'Research-Seminar-OCR-current\.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $BaselinePython)) { throw 'Existing baseline interpreter missing. Do not install into .venv-answer.' }
$PopplerRoot = Join-Path $DataRoot 'tools\poppler-v26.09.0-0'
$Poppler = @(Get-ChildItem -LiteralPath $PopplerRoot -Recurse -File -Filter 'pdftoppm.exe')
if ($Poppler.Count -ne 1) { throw 'Locate the one existing reviewed Poppler executable; do not install another.' }
$SavedQualificationPath = $env:PATH
$CompleteLog = Join-Path $ReviewRoot 'complete-tests.txt'
try {
    $env:PATH = $Poppler[0].DirectoryName + ';' + $SavedQualificationPath
    & $BaselinePython -c $TestRunner $CompleteLog 'test*.py'
    $CompleteExit = $LASTEXITCODE
} finally {
    $env:PATH = $SavedQualificationPath
}
Get-Content -Tail 10 -LiteralPath $CompleteLog
if ($CompleteExit -ne 0) { throw 'Complete regression suite failed.' }
foreach ($Log in @($QualificationLog,$CompleteLog)) {
    if (Select-String -LiteralPath $Log -Pattern 'skipped=' -Quiet) { throw "Skipped checks remain pending: $Log" }
}
```

Tests use disposable temporary mock approval records, accounting fixtures and
mocked transports. They create no real authorization or research campaign and
do not contact a model. See the delivery validation record for measured test counts.

## C. Recapture preservation after the edits/tests

Use the same untouched 184-file list and original three inventories. All proposed
source edits are confined to qualification files; the original 184-file set is
expected to remain unchanged.

```powershell
$FinalStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$FinalCloseout = Join-Path $Reviews "qualification-preservation-post-tests-$FinalStamp"
$FinalCloseoutZip = "$FinalCloseout-review.zip"
& $AnswerPython $CloseoutHelper --repository $Repo --original-review $ImplementationReview --compiler-review $CompilerReview --original-archive $ImplementationArchive --compiler-archive $CompilerArchive --output $FinalCloseout --archive $FinalCloseoutZip
if ($LASTEXITCODE -ne 0) { throw 'Post-test preservation failed. Preserve the comparison/export and stop.' }
$BoundCloseout = Join-Path $ReviewRoot 'preservation-before-preparation'
if (Test-Path -LiteralPath $BoundCloseout) { throw 'Preserve the existing copied closeout.' }
Copy-Item -LiteralPath $FinalCloseout -Destination $BoundCloseout -Recurse
```

## D. Fix the final code/Git state, THEN regenerate preparation

Finish any local commit/staging choices **before** this stage. You may retain the
current dirty checkout; its exact HEAD and complete dirty-status text are bound.
Do not commit, stage/unstage, apply another patch, edit repository files or create
untracked files inside the repository after freezing. All following evidence goes
outside the repository. No preparation from the predecessor is reused as final.

```powershell
$FrozenImplementation = Join-Path $ReviewRoot 'implementation-frozen.json'
$FreezeImplementation = @'
from pathlib import Path
import sys
from finocr_qualification.preparation import implementation
from finocr_qualification.evidence import write_json
write_json(Path(sys.argv[2]), implementation(Path(sys.argv[1])))
'@
& $AnswerPython -c $FreezeImplementation $Repo $FrozenImplementation
if ($LASTEXITCODE -ne 0) { throw 'Implementation freeze failed.' }
$V2Setup = Join-Path $AnswerRoot 'followups\synthetic-contract-v2\setup_manifest.json'
$ContractReview = Join-Path $Reviews 'contract-repair-offline-20261019T195514Z\tokenizer-and-grammar'
$LlamaSource = Join-Path $AnswerRoot 'tooling\llama.cpp'
$NativeBuild = Join-Path $CompilerReview 'native-probe\build.json'
$Preparation = Join-Path $ReviewRoot 'preparation'
$ImmutableInputs = @($ImplementationReview,$CompilerReview,$ImplementationArchive,$CompilerArchive,$FinalCloseoutZip,$InitialCloseoutZip,$FrozenImplementation,$QualificationLog,$CompleteLog)
foreach ($Forbidden in @($CampaignAnchor,$Approval,$Authorization)) {
    if (Test-Path -LiteralPath $Forbidden) { throw "Unexpected execution/approval input: preserve it and stop: $Forbidden" }
}
& $AnswerPython .\scripts\check_qualification.py --v2-setup $V2Setup --contract-review $ContractReview --llama-source $LlamaSource --native-build $NativeBuild --output $Preparation --original-preservation-set $OriginalSet --preservation-closeout $BoundCloseout --preserve $ImmutableInputs
$PreparationExit = $LASTEXITCODE
$PreparationReport = Join-Path $Preparation 'offline_preparation.json'
if (Test-Path -LiteralPath $PreparationReport) {
    $Offline = Get-Content -Raw -LiteralPath $PreparationReport | ConvertFrom-Json
    $Offline | Select-Object kind,version,status,inference_executed,additional_inference_authorized,remaining_authorized_requests,execution_enabled,preservation_pass
} else {
    'Preflight stopped before a report existed. Preserve its error; no campaign manifest is expected.'
}
if ($PreparationExit -ne 0) { throw 'Offline preparation failed. Do not relax checks or overwrite its output.' }
if ($Offline.status -ne 'offline_ready_for_separate_review_not_authorization') { throw 'Preparation did not pass.' }
```

The existing native binary/build record is reused unchanged. Its pinned clean
source, helper/converter/executable identities and exact native/Python grammar
equality are checked again without loading a model/server. This stage also checks
the existing model/backend/official bytes, all runtime packages, device/driver,
idle RAM/disk/VRAM, historical trees, tokenizer parity and six prompt controls.
The preservation extension rehashes all 184 **underlying files**, validates the
three closeout inventories, and adds the original files and closeout tree to the
protected roots. It does not merely preserve a text file containing old hashes.

## E. Record NEW identities separately and verify both paused paths

```powershell
$Identities = Join-Path $ReviewRoot 'binding-identities.json'
$RecordIdentities = @'
import hashlib, sys
from pathlib import Path
from finocr_answer.contract import digest
from finocr_qualification.preparation import read_json, implementation
from finocr_qualification.evidence import assert_preserved, write_json
repo, preparation, frozen, output = map(Path, sys.argv[1:])
report = read_json(preparation)
if report['implementation'] != read_json(frozen) or report['implementation'] != implementation(repo):
    raise SystemExit('Final code/HEAD/dirty state changed; preserve this report and stop')
assert_preserved(report['protected'])
new = {'implementation_fingerprint':report['implementation']['fingerprint'],
       'implementation_record_canonical_sha256':digest(report['implementation']),
       'preparation_file_sha256':hashlib.sha256(preparation.read_bytes()).hexdigest(),
       'preparation_canonical_sha256':digest(report)}
predecessor = {'implementation_fingerprint':'d2181c02dc05e4a5caa628c4746203179ed769a035464ee23a0669956f2585fa',
       'implementation_record_canonical_sha256':'e38a116343dbaf335478f9f4a42474e71b8c93135a05248434140bb41c5194df',
       'preparation_file_sha256':'597cd4ffd91f4e6046703067627e4a4421d623b58c8546d632f744f2f38242c4',
       'preparation_canonical_sha256':'3b9066ef6e149c79cc3ac0f8c27a5476d7519db374864184c00f626dc2334a29'}
write_json(output, {'kind':'offline_binding_identities_not_authorization',
    'new_final_windows_bindings':new,'reviewed_predecessor_bindings':predecessor,
    'head':report['implementation']['head'],'inference_executed':0,
    'additional_inference_authorized':0,'remaining_authorized_requests':0})
print(__import__('json').dumps(new, indent=2))
'@
& $AnswerPython -c $RecordIdentities $Repo $PreparationReport $FrozenImplementation $Identities
if ($LASTEXITCODE -ne 0) { throw 'Final identity comparison failed.' }
$CheckPause = @'
import json, os, pathlib, subprocess, sys
python, script, preparation, output = sys.argv[1:5]
command = [python, '-B', script, '--preparation', preparation] + sys.argv[5:]
result = subprocess.run(command, capture_output=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'}, timeout=30)
with pathlib.Path(output).open('xb') as stream: stream.write(result.stdout)
value = json.loads(result.stdout.decode('utf-8-sig'))
if result.returncode != 2 or value['status'] != 'inference_paused' or result.stderr:
    raise SystemExit('Unexpected pause behavior; preserve the output and stop')
if any(value[k] != 0 for k in ('inference_executed','additional_inference_authorized','remaining_authorized_requests')):
    raise SystemExit('Unexpected nonzero pause counters')
print('Genuine pause verified; exit 2, zero new requests')
'@
$RunScript = Join-Path $Repo 'scripts\run_qualification.py'
$AbsentPreparation = Join-Path $ReviewRoot 'deliberately-absent.json'
if (Test-Path -LiteralPath $AbsentPreparation) { throw 'Pause input must remain absent.' }
& $AnswerPython -c $CheckPause $AnswerPython $RunScript $AbsentPreparation (Join-Path $ReviewRoot 'pause-default.json')
if ($LASTEXITCODE -ne 0) { throw 'Default genuine pause check failed.' }
& $AnswerPython -c $CheckPause $AnswerPython $RunScript $AbsentPreparation (Join-Path $ReviewRoot 'pause-unapproved.json') --authorization $Authorization
if ($LASTEXITCODE -ne 0) { throw 'Unapproved-record genuine pause check failed.' }
foreach ($Forbidden in @($CampaignAnchor,$Approval,$Authorization)) {
    if (Test-Path -LiteralPath $Forbidden) { throw "An execution/approval object appeared: preserve it and stop: $Forbidden" }
}
```

These are deliberate refusal checks, not authorized execution. The authorization
path remains absent. The report/identity files are evidence, never approvals.

## F. Final preservation comparison and export — then STOP

```powershell
$EndStamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
$EndCloseout = Join-Path $Reviews "qualification-preservation-post-preparation-$EndStamp"
$EndCloseoutZip = "$EndCloseout-review.zip"
& $AnswerPython $CloseoutHelper --repository $Repo --original-review $ImplementationReview --compiler-review $CompilerReview --original-archive $ImplementationArchive --compiler-archive $CompilerArchive --output $EndCloseout --archive $EndCloseoutZip
if ($LASTEXITCODE -ne 0) { throw 'Final preservation failed; preserve and export the available failure evidence separately.' }
$EndCopy = Join-Path $ReviewRoot 'preservation-after-preparation'
if (Test-Path -LiteralPath $EndCopy) { throw 'Preserve the existing copied end comparison.' }
Copy-Item -LiteralPath $EndCloseout -Destination $EndCopy -Recurse
$FinalCheck = @'
import sys
from pathlib import Path
from finocr_qualification.preparation import implementation, read_json
from finocr_qualification.evidence import assert_preserved
repo, report, frozen = map(Path, sys.argv[1:])
value=read_json(report)
if implementation(repo) != value['implementation'] or value['implementation'] != read_json(frozen):
    raise SystemExit('Code/Git state changed after preparation; retain all evidence and stop')
assert_preserved(value['protected'])
'@
& $AnswerPython -c $FinalCheck $Repo $PreparationReport $FrozenImplementation
if ($LASTEXITCODE -ne 0) { throw 'Final source/preservation verification failed.' }
foreach ($Forbidden in @($CampaignAnchor,$Approval,$Authorization)) {
    if (Test-Path -LiteralPath $Forbidden) { throw "Unexpected execution/approval object: $Forbidden" }
}
$ReviewArchive = "$ReviewRoot-review.zip"
& $AnswerPython .\scripts\export_qualification.py --root $ReviewRoot --archive $ReviewArchive
if ($LASTEXITCODE -ne 0) { throw 'Review export failed; preserve any partial export.' }
Get-FileHash -Algorithm SHA256 -LiteralPath $ReviewArchive
$ReviewArchive
```

The main review ZIP includes test logs, final code/Git manifest, native/tokenizer
preparation, separate predecessor/new identities, both real pause outputs and
before/after preparation closeout evidence. Keep all separate closeout directories,
their new ZIPs/sidecars, both original completed reviews and their original ZIPs.

## Verifier scope and future work — no execution instructions

The fixed operator approval location is under
`$AnswerRoot\authorizations`; no code/CLI command creates it or its parent. A future
separately authorized operator action would have to install an explicit record
and a separately reviewed approval pin for its exact byte hash. The pin also
identifies its reference/path/date. The record must bind the NEW final preparation
byte/canonical hashes, full implementation record/fingerprint, frozen plan/reference,
runtime/contract/prompt/decoder/model/server/native identities and preservation
inventory, with one fixed six-case campaign, at most six attempts, no retries or
resume and no benchmark requests. Expiry is checked before claim/start and each
new submission. Existing/partial/closed anchors cannot be reused or relocated.

The operator approval file is an external trust input controlled by the person
performing the later review; hashes do not independently prove human consent or
provide protection against a user who can deliberately rewrite both trust files
and source. No flag accepts an arbitrary reference or caller-provided expected
hash, and no issuer/template for real approval is included. External approval
data are outside the source fingerprint, allowing later explicit authorization
to bind final hashes without a circular code edit. **Do not create either file
under this offline authorization.** Missing approval keeps the real pause; changed
or mismatched evidence rejects before claim. The unchanged legacy entry points
continue to call their unconditional pause regardless of qualification approval.

The CLI exit codes are:

| Code | Meaning |
|---|---|
| 0 | All automated checks completed, verified export; two-human review still pending |
| 1 | Unexpected/inconsistent failure; inspect preserved evidence rather than assuming zero attempts |
| 2 | Genuine inference pause (also argparse usage errors, which do not emit the pause JSON) |
| 3 | Authorization rejected before claim/submission on this invocation |
| 5 | Terminal campaign stop, verified evidence export |
| 6 | Completed sequence with mechanical failures, verified export and manual review pending |
| 7 | Missing/failed evidence export or cleanup failure; never report automated execution success |

After any later generation, two humans must independently review every raw answer
against the frozen source/rubric without prior automated scores, preserve both
ratings and adjudicate differences. Qualification remains false until all applicable
contract, numerical, support, interpretation and resource facets pass. Four cases
are numerical; missing/capacity are N/A numerically. These inspected synthetic cases
are development checks, not generalization or FinanceBench accuracy.

No new Windows preparation hashes or Windows test results are asserted by this
delivery. Run A–F locally, export the evidence and review the actual new hashes
before any separate execution authorization is considered.
