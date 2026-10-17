# Financial OCR Research — audit and native-text baseline

## Native-text continuation (2026-10-08)

Setup and development-pilot validation are complete on the user's machine:
12 reports, 2,620 pages, and 24 questions. `finocr native-baseline` now implements
sequential pypdf extraction and within-report BM25, with label-free query inputs,
zero-based page IDs, source verification, failure accounting, immutable run outputs,
and offline evidence scoring. `finocr evaluate-retrieval` scores saved predictions
separately. See [the Windows run guide](docs/NATIVE_BASELINE_WINDOWS.md).

The user supplied verified original and stopword-only pilot runs: evidence Recall@5
was 28.47% and 30.56%, respectively; complete evidence coverage was 6/24 for both.
Read [the verified comparison](docs/STOPWORD_COMPARISON_RESULTS.md) for its scope
and limitations. No answer-generation or matched OCR retrieval result is established.

The implemented development comparison is `finocr compare-query-expansion`:
fixed question-only financial terms on the unchanged stopword page index, with both
saved controls reproduced before new results are accepted. Read
[the experiment policy and Windows commands](docs/QUERY_EXPANSION_EXPERIMENT.md).
Its verified pilot Recall@5 is 40.97%, compared with 30.56% for stopwords; complete
evidence coverage rises from 6/24 to 8/24. Read
[the expansion results](docs/QUERY_EXPANSION_RESULTS.md) for paired changes and
development limitations. All five multi-page questions remain incomplete at k=5.

Expansion v1 is frozen as the development control. See
[the frozen policy snapshot](docs/EXPANSION_V1_CONTROL.json) and
[the five-question review and pipeline trace](docs/MULTIPAGE_REVIEW_AND_PIPELINE_TRACE.md).
The uploaded full native cache now reproduces all 72 saved rankings; read
[the exact score attribution and source-boundary review](docs/NATIVE_CACHE_DIAGNOSTIC.md).
An offline reproduction helper and Windows commands are included there. That
source/score review preceded section context; verified section-v1 results are
described below. Ledger, answer-generation, matched OCR retrieval and held-out results remain pending.
The older model adapter classes remain placeholders. The current-state document
and run guides supersede historical setup/readiness text below.

The separate `finocr compare-section-context` condition is now implemented against
frozen expansion v1. It adds a source-only heading field with local spans, one-page
continuation and exhibit resets, reproduces all earlier controls, and scores offline.
Read [the fixed policy and exact PowerShell run guide](docs/SECTION_CONTEXT_EXPERIMENT.md).
The suite has 103 passing tests. The user's section-v1 run is now verified:
Recall@5 remains 40.97%, Hit@5 remains 12/24, and complete coverage remains 8/24.
MRR rises from 0.302408 to 0.314780; all five multi-page questions remain incomplete.
Read [the verified structural results and regressions](docs/SECTION_CONTEXT_RESULTS.md).
Expansion v1 remains the development control; earlier verified results are unchanged.

The [heading-detection versus query-matching review](docs/HEADING_FAILURE_REVIEW.md)
separates missed/spurious headings from correct titles with zero, incidental, or
insufficient lexical signal. It recommends a note-format coverage ablation with
scoring held fixed. The final planned heading-format ablation is now implemented as
`finocr compare-note-formats`: en-dash Note titles and source-parent/sequentially
gated bare numbered notes, with both frozen expansion/S1 controls reproduced.
Read [the policy, exact PowerShell guide and retrieval-to-OCR transition](docs/NOTE_FORMAT_EXPERIMENT.md).
The real note-format run is now verified: Recall@1/3 increases to 14.58%/36.81%,
MRR to 0.347073, and Recall@5/complete coverage remain 40.97%/8 of 24.
Read [the results, paired gains/regressions and baseline recommendation](docs/NOTE_FORMAT_RESULTS.md).
Recommend carrying frozen expansion v1 into matched native/OCR retrieval at k=5;
retain the note-format condition as the structural comparator. All five
multi-page questions remain incomplete. This concludes the planned heading-format
ablations; full-report OCR and matched retrieval are the next milestone.

Expansion v1 is now frozen for matched native/OCR retrieval at k=5. The OCR
setup tools collect current Windows GPU/VRAM, RAM, disk and interpreter details,
render all physical pages with a resumable full-cohort plan, and provide a separate
pinned CPU environment for one standard PaddleOCR smoke page. Read
[the staged PowerShell guide](docs/OCR_SETUP_WINDOWS.md) and run the **no-install
machine inventory first**. Existing `.venv` dependencies and retrieval policies
remain fixed. The researcher's completed 200-DPI rendering cache and pinned CPU
smoke are now verified; see [the setup artifact review](docs/OCR_SETUP_REVIEW.md).

Continue from `61a696d` with [resumable full-report OCR and the matched comparison](docs/FULL_OCR_WINDOWS.md).
The new source-only financial-table diagnostic precedes the full run. Per-report
workers reuse initialization; immutable attempts preserve raw outputs, failures and
zero-based IDs. Matched retrieval reproduces expansion v1 before loading labels,
keeps every report page as a candidate, and reports paired/multi-page coverage at k=5.
Full OCR, table-diagnostic quality and native/OCR experimental outcomes remain
pending local execution; the successful cover-page smoke is a setup result.

The second machine's [isolated GPU diagnostic guide](docs/GPU_OCR_WINDOWS.md)
uses the official CUDA 11.8 Paddle 3.3.0 Windows wheel with the existing 537.70
driver, a separate environment/cache, and the same eight source financial tables.
It compares raw/normalized output differences and synchronized timing against the
retained CPU diagnostic. Full GPU execution remains pending that review; leave
the continuing first-machine CPU run and its checkout unchanged.

## Current direction and implementation status (2026-10-05)

The current proposal is a compact financial-document pipeline comparing ordinary
retrieval, section context, and bounded source-linked memory at a fixed inference
budget. Read [the proposed protocol](docs/MEMORY_EXPERIMENT_PROTOCOL.md) before
continuing the earlier experiment design. It describes a study to implement,
not completed model experiments. The existing OCR and native-text adapters remain
placeholders; no OCR benchmark has run.

The FinanceBench audit now blocks on malformed/dropped questions, conflicting
evidence-document mappings, invalid pages, and failed pilot selection. It preserves
inventory and diagnostic outputs when selection fails and reports pilot annotation
and sector coverage. It reconciles supplied/retained records; verify the expected
release totals separately so a partial download is not mistaken for the full release.

Python 3.11+ and `pypdf` are required. The current suite has 26 tests, including
12 PDF-backed audit regression tests. Run `python -m unittest discover -s tests -v`.
Windows PowerShell is sufficient for auditing; WSL is not required for this stage.
Use a separate Python environment for project dependencies when possible.

The generated longitudinal pilot is not yet a company-held-out experiment split.
Coverage and split decisions remain pending the audit of the downloaded files.
The sections below retain earlier implementation history; the new protocol governs
the revised research scope.

## Revised study center: FinanceBench

The primary corpus is now FinanceBench because it supplies 368 real financial PDFs,
269 10-K filings, long company histories, and 150 expert-annotated QA cases with
zero-indexed evidence pages. FinLongDocQA remains documented as an earlier candidate,
but its public release is Markdown-only and is not suitable as the main OCR input.

Phase 0 now produces a full document inventory plus a deterministic 12-report pilot:
four sectors, three annual reports per company, and early/middle/late time coverage.
The native PDF text baseline comes next. OCR models are installed only after every PDF,
page count, evidence page, and pilot selection passes this gate.

### Run the FinanceBench Phase 0 audit

In Windows PowerShell, from the repository root:

```powershell
python -m pip install -e .

finocr audit-financebench `
  --metadata "$env:DATA_ROOT\raw\financebench\data\financebench_document_information.jsonl" `
  --questions "$env:DATA_ROOT\raw\financebench\data\financebench_open_source.jsonl" `
  --pdf-dir "$env:DATA_ROOT\raw\financebench\pdfs" `
  --output-dir "$env:DATA_ROOT\audits\financebench_phase0"
```

Outputs include the full CSV/JSONL inventory, unified document and task manifests,
pilot-only manifests, `pilot_selection.csv`, `audit.json`, and `AUDIT_REPORT.md`.
The selector ranks companies by annotated annual-report coverage, preserves sector
diversity, requires at least eight annual-report years, and chooses each company's
earliest, middle, and latest usable report.

## Earlier FinLongDocQA design (retained for provenance)

The earlier package implemented and audited the FinLongDocQA ingestion layer for the research question:

> How do one-shot multi-page and page-by-page OCR differ in efficiency and their ability to preserve financial evidence as document length increases?

## Current outcome

Phase 0 is **implemented but intentionally blocked before OCR**.

- The adapter converts a fixed ten-report pilot into unified manifests.
- `documents.jsonl` contains 10 documents; `tasks.jsonl` contains all 59 associated v1.1 QA tasks.
- Source pages are converted from one-based to zero-based exactly once.
- The full v1.1 structural audit passes: 7,527 tasks, 1,456 Markdown reports, no missing task/report mappings, and no out-of-range evidence pages.
- Nine unit tests pass.
- No OCR model or model-specific dependency was installed.

The blocker is substantive: the official report archive contains Markdown, not the source PDFs described in the paper. The ten content-level checks also found 3 passes, 2 concerns, and 5 failures involving redundant/incorrect evidence pages or questionable ratios. See `data/audits/finlongdocqa_phase0/AUDIT_REPORT.md`.

## What this overlay contains

```text
configs/finlongdocqa_pilot.json                 Fixed ten-report pilot
data/raw/finlongdocqa/                          Pilot Markdown reports + 59 raw annotations
data/manifests/finlongdocqa_pilot/              Unified documents.jsonl and tasks.jsonl
data/audits/finlongdocqa_phase0/                Structural audit, manual checks, evidence packets
docs/EXPERIMENT_PROTOCOL.md                     Phase 0 gates and later experiment boundary
docs/FINLONGDOCQA_PHASE0_FINDINGS.md             Design implications and remediation plan
src/finocr/datasets/finlongdocqa.py              Strict adapter and release auditor
src/finocr/datasets/validation.py                Unified-manifest validator
src/finocr/phase0.py                             Audit composition and evidence packets
src/finocr/rendering.py                          PDF-only 200-DPI rendering gate
tests/                                           Nine standard-library unit tests
third_party/FinLongDocQA-LICENSE                 Required upstream license
```

The larger starter repository contained model, metric, page-window, and risk-scoring modules that were not among the attached files. This package is therefore a merge-ready Phase 0 overlay; it does not recreate or overwrite those unprovided modules.

## Setup and verification

Python 3.11 or newer is required; the FinanceBench audit depends on `pypdf`.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .

python -m unittest discover -s tests -v

finocr validate-data \
  --documents data/manifests/finlongdocqa_pilot/documents.jsonl \
  --tasks data/manifests/finlongdocqa_pilot/tasks.jsonl \
  --require-files \
  --repository-root .
```

Validation is expected to return `valid: true` plus ten `not_ocr_input_ready` warnings. Those warnings are the correct representation of the released Markdown-only state.

## Reproduce the conversion from the official release

Download FinLongDocQA v1.1 into `data/raw/finlongdocqa/` and verify the checksums in `data/raw/finlongdocqa/SOURCE.md`. Then run:

```bash
finocr convert-finlongdocqa \
  --annotations data/raw/finlongdocqa/dataset_qa.jsonl \
  --reports data/raw/finlongdocqa/reports.zip \
  --selection configs/finlongdocqa_pilot.json \
  --materialize-root data/raw/finlongdocqa/reports \
  --output-dir data/manifests/finlongdocqa_pilot \
  --raw-subset-output data/raw/finlongdocqa/dataset_qa.pilot.jsonl \
  --repository-root . \
  --source-version v1.1

finocr audit-finlongdocqa \
  --annotations data/raw/finlongdocqa/dataset_qa.jsonl \
  --reports data/raw/finlongdocqa/reports.zip \
  --documents data/manifests/finlongdocqa_pilot/documents.jsonl \
  --tasks data/manifests/finlongdocqa_pilot/tasks.jsonl \
  --manual-checks data/audits/finlongdocqa_phase0/manual_checks.jsonl \
  --repository-root . \
  --output-json data/audits/finlongdocqa_phase0/audit.json \
  --output-markdown data/audits/finlongdocqa_phase0/AUDIT_REPORT.md \
  --evidence-output-dir data/audits/finlongdocqa_phase0/evidence_packets
```

The adapter accepts either the official `reports.zip` or an extracted `reports/` directory. It never executes the dataset's `python_code`; the reference program is preserved as metadata only.

## Unified data contract

`documents.jsonl` contains one record per report. The released source is represented honestly:

```json
{
  "doc_id": "finlongdocqa:AAPL:2022",
  "pdf_path": null,
  "source_path": "data/raw/finlongdocqa/reports/AAPL/2022.md",
  "source_format": "markdown",
  "page_count": 80
}
```

`tasks.jsonl` contains one record per question. For upstream pages `[25, 41]`, the unified record stores internal pages `[24, 40]` and retains `[25, 41]` in metadata.

## PDF rendering gate

`finocr render-pages` uses Poppler and renders only documents whose `source_format` is `pdf` and whose `pdf_path` is populated. It refuses to render this pilot today. This prevents Markdown-to-PDF conversion from being mistaken for the original document images.

The correct next step is to acquire the exact PDFs used by the authors, verify their identity and pagination, resolve the flagged QA records, obtain researcher signoff on the ten evidence packets, and only then render at 200 DPI. Unlimited-OCR remains out of scope until those checks pass.

## Research scope retained from the starter design

- Main architecture: Unlimited-OCR in one-shot multi-page and repeated page-by-page conditions.
- Pagewise baselines: DeepSeek-OCR and PaddleOCR-VL.
- Control: native PDF text when embedded text exists.
- Planned page windows: 1, 2, 5, 10, 20, and 40 pages.
- Primary outcomes: OCR fidelity, evidence retrieval, numerical accuracy, runtime, peak GPU memory, and selective-review coverage.
- First study excludes chart understanding and fine-tuning.

## Data-use terms

The included FinLongDocQA subset is for non-commercial academic research and evaluation. Read `third_party/FinLongDocQA-LICENSE` before redistributing or using the data.
