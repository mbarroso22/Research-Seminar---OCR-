# Financial OCR Research — Phase 0 working package

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

This package implements and audits the FinLongDocQA ingestion layer for the research question:

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

Python 3.11 or newer is sufficient; Phase 0 has no third-party Python dependency.

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
