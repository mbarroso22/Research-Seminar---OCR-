# Current experiment state — 2026-10-08

Read this before continuing the experiment. This records the current verified Windows setup and supersedes historical experiment descriptions where they conflict. Do not report proposed work as completed results.

## Research goal

Study whether a compact financial-document pipeline can preserve relevant evidence using OCR, retrieval, section context, and bounded source-linked memory while controlling processing cost. FinanceBench is the primary dataset. Comparing one-shot and pagewise OCR remains a possible component, not the entire research question. Fine-tuning and transfer to other business documents are later possibilities, not completed work. MMLongBench-Doc and InduOCRBench are outside the primary experiment.

## Windows setup

- Repository: https://github.com/mbarroso22/Research-Seminar---OCR-.git
- Clone: C:\Users\mbarroso\Downloads\Research-Seminar-OCR-current
- GitHub base commit: bfa5a46. Local audit and sector patches have been applied; their presence on GitHub is not confirmed.
- Python: 3.13.7; repository-local .venv. Activation is unnecessary when invoking .venv\Scripts\python.exe directly.
- Editable install succeeded. pypdf, cryptography, and fonttools installed.
- All 27 tests passed on the user's machine after the sector fix.
- DATA_ROOT: C:\Users\mbarroso\financial-ocr-data
- Metadata: DATA_ROOT\raw\financebench\data\financebench_document_information.jsonl
- Questions: DATA_ROOT\raw\financebench\data\financebench_open_source.jsonl
- PDFs: DATA_ROOT\raw\financebench\pdfs
- Current audit: DATA_ROOT\audits\financebench_phase0_sector_fixed
- Hardware previously reported: i5-12600K, 16 GB RAM, RTX 3060. Confirm current machine and GPU VRAM before model installation.

## Verified dataset findings

368 physical PDFs; 361 metadata rows representing 360 unique document names. Types: 269 10k, 6 10k_annualreport, 27 10q, 30 8k, 29 Earnings. The annual-report entries represent 274 unique reports across 40 companies.

150 questions cover 84 documents. Of those, 112 questions cover 64 annual reports. Each question includes a reference answer and evidence; supporting text and justification are evaluation material, not retrieval inputs. Evidence page numbers are zero-based PDF indices, not printed page labels.

The full audit remains blocked: FOOTLOCKER_2023_annualreport occurs twice with identical URL but reporting years 2023 and 2022; two Intel 2023 8-K PDFs fail parsing; eight PDFs lack metadata. Preserve originals. No year has been corrected and the Intel files have not been repaired. Audit readability counts are metadata-row counts, not counts of distinct physical PDFs.

Three Adobe failures were resolved by installing cryptography. The two associated evidence-page errors disappeared; they were consequences of unreadable PDFs, not demonstrated incorrect annotations. gics_sector mapping was fixed in code and tested.

## Fixed development pilot

| Company | Sector | Years |
|---|---|---|
| AMD | Information Technology | 2015, 2019, 2022 |
| Best Buy | Consumer Discretionary | 2015, 2019, 2023 |
| Boeing | Industrials | 2015, 2019, 2022 |
| PepsiCo | Consumer Staples | 2015, 2019, 2022 |

12 reports, 2,620 pages, 24 questions across six reports, and 25 distinct annotated evidence pages. Five questions have multiple evidence pages. Question types: 15 domain-relevant, 4 metrics-generated, 5 novel-generated.

Separate validate-data run on pilot_documents.jsonl and pilot_tasks.jsonl returned valid=true, 12 documents, 24 tasks, no errors or warnings, 12 OCR-ready documents. Pilot mappings were checked against original annotations and matched. Native text was sampled, not extracted from every page yet. PepsiCo reports with 667 and 503 pages require structural inspection.

Pilot manifests: current audit\manifests\pilot_documents.jsonl and pilot_tasks.jsonl. This is a DEVELOPMENT pilot, not a held-out evaluation cohort. Six unannotated reports support processing comparisons, not annotated QA scoring.

## Next phase: implement the native-text retrieval baseline

1. Extract all pages from the fixed pilot PDFs, preserving doc_id and zero-based page index. Record blank pages and extraction failures, checksums, tool version, configuration, and elapsed time. Process reports sequentially and save derived outputs outside Git.
2. Build a simple reproducible lexical page-retrieval baseline, initially BM25 within each question's specified report. Index all report pages. Retrieve with question text only; exclude answers, justifications, evidence text, and known evidence indices from retrieval and memory.
3. Save ranked pages and scores per question. Evaluate against annotations afterward: evidence recall, any-evidence hit, and all-evidence coverage at fixed k (initially 1, 3, 5). Distinguish these metrics and report question counts. No answer generation is included in this first baseline.
4. Inspect extraction and long-report structure. Native text is a comparison reference, not verified OCR transcription ground truth.
5. Later run an OCR diagnostic on the 25 evidence pages; this is oracle-selected diagnostic work, not end-to-end retrieval evaluation. Full-report OCR is needed for fair OCR retrieval comparison.
6. Then compare ordinary retrieval, section context, and bounded source-linked memory under matched budgets. Define separate company/document held-out boundaries before claims of generalization or training.

## Not completed

No full-page native-text baseline or retrieval results. No OCR model execution, answer-generation evaluation, contextual-memory implementation, fine-tuning, latency benchmark, measured energy savings, or generalization result. Do not invent these results or reuse synthetic test outcomes as experimental measurements. OCR adapter placeholders and proposed protocol text are not functioning model integrations.

## Handoff instruction

Read this file, PROJECT_HANDOFF.md, docs/MEMORY_EXPERIMENT_PROTOCOL.md, relevant source, and tests. Resolve conflicts in favor of verified current-state evidence. Inspect git status before editing; preserve applied patches and originals. Implement the native-text baseline and meaningful tests, provide a patch and Windows commands, and wait for the user's real run output before reporting experimental results. The assistant cannot access the user's Windows filesystem or PDFs directly.

## Detailed technical roadmap

Read `docs/TECHNICAL_RESEARCH_ROADMAP.md` for the paper relationship, provisional model choices, architecture, execution stages, data boundaries, budgets, scoring, cost accounting, implementation backlog, and handoff instructions. Its 35 sections distinguish verified state from proposals. Model names in the roadmap are not evidence of installation or successful inference.

## Phase 1 implementation handoff (2026-10-08)

The repository continuation is based on confirmed Git commit
`5cf284233702edf82ed8f2bb496600eae76107a4`; the earlier `bfa5a46` setup reference
above is historical. The native-text/BM25 CLI baseline is now implemented and tested
locally on small fixtures. It has **not been run on the user's FinanceBench PDFs**.
The pilot remains development-only; no empirical recall, latency, OCR, or answer
correctness result has been established by this implementation.

Read `docs/NATIVE_BASELINE_WINDOWS.md` for patch application, the existing .venv,
`scripts/run_native_pilot.ps1`, direct Windows commands, output contracts, and the
files to return. Runtime retrieval accepts only `task_id`, `doc_id`, and `question`.
Scoring reads labels after predictions are saved. Every expected page and question
is accounted for, including failed/empty native text, with zero-based IDs preserved.
Source hashes/page counts and configuration/provenance are recorded. Resume is
explicitly unsupported; use a new output directory for each run.

The next experimental action is execution on the validated 12-report pilot and
inspection of its real output artifacts. Keep the corpus results pending until those
outputs are supplied. Earlier roadmap rows naming the native baseline as a proposed
module now refer to implemented code; other OCR/context/memory stages remain proposed.
