# Native PDF text and within-report BM25 baseline

Status: implemented against Git commit `5cf284233702edf82ed8f2bb496600eae76107a4`.
Local fixture tests verify behavior. The fixed FinanceBench pilot has **not** been
extracted or benchmarked here. Experimental results require the researcher's real
execution outputs. The supplied review bundle contains metadata and annotations,
not the 12 source PDFs. The existing Windows setup and pilot validation remain valid.

## Apply the patch and verify

Download `native-bm25-baseline.patch` to Downloads. In PowerShell:

```powershell
Set-Location "$env:USERPROFILE\Downloads\Research-Seminar-OCR-current"
git status --short
git rev-parse HEAD
# Expected base: 5cf284233702edf82ed8f2bb496600eae76107a4

$patchFile = "$env:USERPROFILE\Downloads\native-bm25-baseline.patch"
git apply --check $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch check failed; retain local edits and share this output." }
git apply $patchFile
if ($LASTEXITCODE -ne 0) { throw "Patch application failed." }

$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --no-deps --no-build-isolation -e .
if ($LASTEXITCODE -ne 0) { throw "Editable installation failed." }
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw "Tests failed; resolve them before running the corpus." }
```

The patch adds the baseline and preserves the existing audit code. Do not reapply
`experiment-handoff.patch`: its documents are already present at this commit.
Do not reset, clean, or overwrite local changes to force patch application.
The editable install uses the existing dependency versions; no new BM25 package,
GPU framework, OCR checkpoint, WSL, or environment activation is needed.
The implementation uses the already-required `pypdf` and standard library.
AES-encrypted documents still need the existing `cryptography` dependency.

## Run the fixed development pilot

The shortest command uses the supplied PowerShell runner:

```powershell
& .\scripts\run_native_pilot.ps1
```

If your shell blocks local scripts, use the direct Python command below; no
execution-policy changes are necessary. With the paths from the handoff:

```powershell
$python = ".\.venv\Scripts\python.exe"
$dataRoot = "$env:USERPROFILE\financial-ocr-data"
$auditDir = Join-Path $dataRoot "audits\financebench_phase0_sector_fixed"
$stamp = [DateTime]::UtcNow.ToString("yyyyMMddTHHmmssZ")
$suffix = [Guid]::NewGuid().ToString("N").Substring(0, 8)
$runDir = Join-Path $dataRoot "derived\native\native-bm25-$stamp-$suffix"

& $python -m finocr.cli native-baseline `
  --documents "$auditDir\manifests\pilot_documents.jsonl" `
  --tasks "$auditDir\manifests\pilot_tasks.jsonl" `
  --pdf-dir "$dataRoot\raw\financebench\pdfs" `
  --output-dir $runDir `
  --repository-root . `
  --expected-documents 12 `
  --expected-pages 2620 `
  --expected-questions 24 `
  --k1 1.2 --b 0.75 --k 1 3 5
$runExit = $LASTEXITCODE
Write-Host "Exit code: $runExit"
Write-Host "Run directory: $runDir"
```

Use the validated pilot manifests, even though the full-corpus audit remains blocked
by unrelated source issues. The expected-count flags prevent accidentally running a
different cohort. `--pdf-dir` changes only the lookup location for each original PDF
basename; report IDs, expected checksums, page counts, and zero-based indices remain
unchanged. Leave the original manifests untouched.

An existing output directory is rejected. Each invocation creates a new immutable
run identity. Completed report JSONL files and an incremental extraction summary
survive later failures/interruption. **Automatic resume/cache reuse is not implemented**;
rerun into a new directory after fixing a problem. This avoids silently mixing parser
versions, source PDFs, and configurations. Never put derived outputs in the Git repo.

Exit 0 means all reports passed source checks, all page extraction attempts completed
without extraction errors, and requested scoring completed. It does not establish
text quality or high recall. Exit 1 means the run finished with recorded extraction
failures. Exit 2 means configuration/input/artifact/scoring failure. A run manifest
records failures after the directory has been created. Ctrl+C is recorded as an
interruption; completed reports remain available. Progress prints to stderr so stdout
contains the final JSON run summary.

## Retrieval and evaluation boundary

Extraction reads only the document manifest and source PDFs. The task loader copies
only `task_id`, `doc_id`, and `question` into `retrieval_queries.jsonl`. The retriever
reloads that minimal file and accepts a `RetrievalQuery`, never `TaskRecord.metadata`.
Answers, justifications, evidence text, evidence labels, categories, and target fields
are not retrieval inputs. Only the specified report is searched for each question.

After predictions are atomically written, the evaluator reads only task IDs, report
IDs, and evidence-page labels from the original task file. Frozen task/document
manifest hashes are checked for changes. You may add `--skip-evaluation` to run just
extraction/retrieval, then score those predictions separately:

```powershell
& $python -m finocr.cli evaluate-retrieval `
  --predictions "$runDir\retrieval_predictions.jsonl" `
  --tasks "$auditDir\manifests\pilot_tasks.jsonl" `
  --output "$runDir\retrieval_metrics_offline.json" `
  --k 1 3 5
```

Standalone scoring refuses an existing metrics path. It validates report identity,
nonempty in-range evidence, complete ranking coverage, duplicate predictions and
candidates, and zero-based page indices. It does not change rankings. It scores the
labels supplied at that invocation; use the original frozen task file and retain its
checksum if producing a separate annotation-revision comparison.

## Frozen baseline choices

- pypdf `extract_text(extraction_mode="plain")`, `PdfReader(strict=False)`, reports
  processed sequentially in manifest order. No native/OCR/parser fallback.
- Verify manifest SHA-256 before extraction and again after it; compare actual PDF
  page count before extracting. Try only an empty password for encrypted reports.
- One record per zero-based PDF index. Failed pages keep their index and empty text.
  A rejected/missing/unreadable report produces expected-index failure placeholders;
  these are explicitly unattempted and do not prove physical-page coverage. If a
  source changes after extraction, discard its text and mark report failure while
  preserving the actual attempt counts/timings and post-extraction checksum.
- Preserve raw text, including financial signs, decimals, parentheses, symbols, years,
  and table reading order as supplied. Search normalization uses Unicode NFKC, converts
  Unicode minus to ASCII minus, and collapses whitespace. Raw text is never overwritten.
- Tokenization uses casefolded Unicode words and signed numbers, retaining decimal/
  thousands separators and an attached percent sign. The version and exact regex are
  saved. No stemming, stopword list, query expansion, or answer-derived keywords.
- BM25: `k1=1.2`, `b=0.75`, positive `log(1 + (N-df+0.5)/(df+0.5))` IDF, binary
  query-term frequency. All report pages contribute to N and average token length,
  including zero-length empty/failed pages. Reports without questions are extracted
  for processing coverage but need no query index.
- Save full rankings. Order by descending score, then ascending page index. Include
  zero-score ties; set `no_match=true` when every candidate scores zero. Such ties may
  hit annotated evidence by chance and remain disclosed in evaluation.
- A report-level source failure yields an empty ranking and zero retrieval success.
  Individual page errors yield `partial_extraction` predictions, retaining every
  physical candidate index. Errors remain in extraction and query denominators.

The metrics distinguish macro evidence Recall@k, any-evidence Hit@k, and all-evidence
coverage at k=1,3,5. Macro recall averages each question's fraction of distinct gold
pages retrieved. Any-hit needs one gold page; all-evidence needs every gold page.
MRR uses the first gold page in the full ranking. All questions, including failures
and no-match queries, remain in denominators. No answer generation or answer scoring
is included. An unannotated retrieved page is not automatically irrelevant.

## Saved outputs and what to return

| File | Purpose |
|---|---|
| `native_pages.jsonl` | All page records in manifest/physical order; raw/search text, IDs, statuses, page timing |
| `pages/<hash>.jsonl` | Atomic per-report checkpoints with Windows-safe names |
| `extraction_summary.json` | Expected/observed counts, hashes, attempted/failed pages, empty-text/failed indices, characters, report timings |
| `retrieval_queries.jsonl` | Auditable label-free query projection |
| `retrieval_predictions.jsonl` | All question statuses, full page rankings/scores, no-match flags, query timing |
| `retrieval_metrics.json` | Offline aggregate and per-question evidence scores; absent when scoring is skipped/fails |
| `run_manifest.json` | Run/config/input/artifact hashes, tool/Python/platform versions, code revision/dirty state/source digest, stage timing/status |

Code provenance includes a digest of all package Python source files, so new untracked
source is covered even before a commit. Tool versions are recorded, not silently
updated. Index construction and query timings are separate; total run wall time
includes ingestion and artifact writes. Page timing excludes report open/hash work,
which is included in report timing. Hardware energy/GPU memory are not measured.

Return the final command summary, test output, and these real-run files:
`run_manifest.json`, `extraction_summary.json`, `retrieval_predictions.jsonl`, and
`retrieval_metrics.json` (if present). Full `native_pages.jsonl` can stay local unless
specific failure/text diagnosis needs it. For a compact handoff:

```powershell
$handoffFiles = @(
  "$runDir\run_manifest.json",
  "$runDir\extraction_summary.json",
  "$runDir\retrieval_predictions.jsonl",
  "$runDir\retrieval_metrics.json"
) | Where-Object { Test-Path -LiteralPath $_ }
Compress-Archive -LiteralPath $handoffFiles -DestinationPath "$runDir-handoff.zip"
```

Review `blank_native_text_indices`, `failed_page_indices`, and character counts for
the long PepsiCo reports. Empty native text may indicate image-only pages; it does
not prove a visually blank page. Native text is an approximate comparison
representation, not verified full-page transcription ground truth. Layout quality
and the reports' structural contents still require source inspection after the run.

## Validation performed here

54 tests passed locally using Python 3.12.14 and pypdf 6.10.0. This is software
validation on Linux; the user's Python 3.13.7/Windows run remains to be verified.

The standard-library unittest suite uses embedded-text PDFs created with pypdf.
Behavior checks include BM25 scores against an independent arithmetic calculation,
length/frequency effects, deterministic ties, Unicode financial tokens, failure
indices, unreadable/missing/changed/encrypted sources, Windows path rebasing, atomic
UTF-8/LF writes, CLI artifacts/exit codes, offline metrics, and adversarial task-label
changes that must leave retrieval unchanged. No synthetic test score is a FinanceBench
experimental result. Windows PowerShell commands are supplied for the user's machine;
the actual pilot run and Windows execution remain pending.

Paper context: [Han et al., arXiv:2604.26462v1](https://arxiv.org/html/2604.26462v1)
uses OCR, hybrid lexical/embedding localization, and a VLM extractor. This command is
a deliberately simpler native-text/BM25 representation control. It is not a replication
of that full pipeline and does not imply its private-corpus performance will transfer.
