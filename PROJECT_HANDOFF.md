# Financial OCR research handoff

## Current continuation (2026-10-05)

The project direction has moved toward compact extraction with section context,
retrieval, and bounded source-linked memory. Read `docs/MEMORY_EXPERIMENT_PROTOCOL.md`
for the proposed comparison, limits, split rules, scoring, and execution stages.
It supersedes the earlier continuation prompt below. It is a proposed protocol,
not an implemented OCR/memory experiment.

The FinanceBench audit now reconciles input/output question counts, rejects malformed
evidence, includes ingestion issues in readiness, and saves diagnostic outputs even
when pilot selection fails. The suite has 26 passing tests, including 12 new tests
using temporary PDFs and malformed supervision. This does not validate the real
downloaded corpus, whose audit outputs have not been supplied here.

Next: run the corrected audit on the processing machine, inspect real annotation
coverage and release totals, choose development/held-out companies, verify evidence
content, and implement native-text extraction plus BM25. Model selection, token
budgets, and memory policy must be frozen after development checks. No OCR models,
retrieval benchmark, or fine-tuning runs have been executed.

## Status as of 2026-09-18

Phase 0 code, manifests, and audits are complete. The project must **not** install or run an OCR model yet.

### Completed

- Downloaded and checksum-verified the official FinLongDocQA v1.1 annotations and report archive.
- Confirmed the upstream schema: `id`, `company`, `year`, `question`, `type`, `thoughts`, `page_numbers`, `python_code`, and numeric `answer`.
- Audited all 7,527 annotations and all 1,456 released reports.
- Confirmed 1,329 reports have QA tasks and 127 released reports have none.
- Confirmed every report uses contiguous one-based `# Page N` markers.
- Confirmed zero missing task/report mappings and zero out-of-range evidence references.
- Implemented a strict adapter for either `reports.zip` or an extracted report directory.
- Created a fixed ten-report pilot spanning 44–802 pages, fiscal years 2022–2024, and text/table/mixed questions.
- Generated 10 unified document records and 59 unified task records.
- Converted evidence pages once from one-based source pages to zero-based internal indices.
- Preserved raw answers, reasoning traces, programs, and original page values in metadata without executing the programs.
- Added manifest validation, release audit, PDF-only rendering gate, and evidence-packet generation.
- Added nine passing unit tests.
- Included the upstream non-commercial license required for redistribution.

### Critical findings

1. The official `reports.zip` contains page-delimited Markdown, not PDFs. It cannot directly support an OCR experiment or 200-DPI rendering.
2. The paper states that PDFs were collected from SEC EDGAR and converted with MinerU, but the public release does not include PDF files, accession identifiers, URLs, or a PDF-to-Markdown mapping.
3. A purposeful ten-task content review produced 3 passes, 2 concerns, and 5 failures. The failures include unsupported extra evidence pages, direct lookups mislabeled as multi-page reasoning, and ratios with incompatible units.
4. The manifests are structurally valid but correctly report zero OCR-ready documents.

### Important artifacts

- `data/audits/finlongdocqa_phase0/AUDIT_REPORT.md` — readable audit.
- `data/audits/finlongdocqa_phase0/audit.json` — machine-readable audit.
- `data/audits/finlongdocqa_phase0/manual_checks.jsonl` — ten content reviews awaiting researcher signoff.
- `data/audits/finlongdocqa_phase0/evidence_packets/` — released page text for each reviewed task; these are not PDF renders.
- `data/manifests/finlongdocqa_pilot/documents.jsonl` and `tasks.jsonl` — unified pilot.
- `configs/finlongdocqa_pilot.json` — deterministic selection.
- `data/raw/finlongdocqa/SOURCE.md` — provenance, checksums, format finding, and page convention.

## September 25 scope revision

FinanceBench is now the primary corpus. Local acquisition has been verified at 368 PDFs,
269 10-K filings, 40 companies, nine annual-report years, and 150 open QA annotations.
The repository now includes `finocr audit-financebench`, which inventories every PDF,
validates zero-indexed evidence pages, writes unified manifests, and selects a
deterministic four-company/three-year pilot. MMLongBench-Doc and InduOCRBench are
optional later robustness datasets rather than central corpora.

## Next task

Run the FinanceBench Phase 0 command documented in README.md. If its status is
`ready_for_native_text_baseline`, freeze the generated pilot and implement page-level
native PDF text extraction before installing an OCR model.

## Earlier FinLongDocQA task (retained for provenance)

Treat source-PDF recovery and ground-truth curation as the remainder of Phase 0:

1. Ask the FinLongDocQA authors for the exact 1,456 source PDFs or, at minimum, a mapping containing ticker, fiscal year, CIK, accession, source URL/checksum, PDF page count, and Markdown page offset.
2. Do not substitute browser-generated or Markdown-generated PDFs unless that becomes an explicitly separate synthetic condition.
3. For each pilot report, verify exact identity, page count, and at least the manually reviewed evidence pages.
4. Decide whether each `fail`/`concern` task is corrected, excluded, or retained with a documented exception. Keep raw v1.1 records immutable and store changes as a curation overlay.
5. Change `human_signoff` to `true` only after the researcher inspects each evidence packet.
6. Populate `pdf_path`, rerun validation, and render verified evidence pages at 200 DPI.
7. Only when the audit says `ready_for_ocr_dry_run`, install Unlimited-OCR and run one-page and two-page dry runs.

## Suggested continuation prompt

> Continue the Financial OCR project from the Phase 0 package. Read `PROJECT_HANDOFF.md` and `data/audits/finlongdocqa_phase0/AUDIT_REPORT.md`. Help me recover or request the exact source PDFs, design an immutable QA-correction overlay for the five failed and two concerning manual checks, and rerun the Phase 0 gate. Do not install any OCR model until the audit is ready.
