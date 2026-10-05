# Experiment protocol

## Research question

How do one-shot multi-page and page-by-page OCR differ in efficiency and their ability to preserve financial evidence as document length increases?

## Phase 0 — data provenance, conversion, and audit

Phase 0 is a hard gate. Model installation is prohibited until every required item passes.

### 0A. Freeze authoritative inputs

1. Record the dataset version, download URL, revision, byte size, checksum, and license.
2. Keep upstream files immutable.
3. Store any corrections in a separate curation overlay with reviewer, reason, old value, and new value.
4. Do not execute dataset-supplied reference programs during ingestion.

### 0B. Audit the full release structurally

Check:

- required annotation fields and types;
- unique task IDs;
- exact `(company, year)` report mapping;
- report filename pattern;
- contiguous one-based page markers;
- finite numeric answers;
- non-empty questions and evidence pages;
- evidence pages within each document;
- reports with and without tasks.

Structural validity is necessary but does not establish content correctness.

### 0C. Select a deterministic pilot

Use 5–10 reports. Record the selection rule before model work. The included pilot intentionally covers:

- fiscal years 2022, 2023, and 2024;
- `text`, `table`, and `mixed` question labels;
- report lengths from 44 to 802 pages;
- short and wide evidence-page spans.

This pilot is for pipeline and annotation auditing, not performance estimation.

### 0D. Convert to unified manifests

- `documents.jsonl`: one record per report.
- `tasks.jsonl`: one record per QA pair.
- Stable document ID: `finlongdocqa:<company>:<year>`.
- Stable task ID: `finlongdocqa:<source-id>`.
- Source `page_numbers` are one-based.
- Internal `evidence_pages` are zero-based.
- Preserve source pages and the conversion rule in metadata.
- Never store a Markdown path in `pdf_path`.

### 0E. Perform content-level checks

Inspect at least one task from each pilot document. For every check:

1. Open every cited source page.
2. Locate each operand or textual fact.
3. Recompute the answer independently.
4. Evaluate whether the question and units are coherent.
5. Determine whether every cited page is required and supported.
6. Assign `pass`, `concern`, or `fail`.
7. Require researcher signoff.

Do not infer full-dataset error rates from a purposeful sample.

### 0F. Verify source PDFs

Before setting `pdf_path`, record:

- company and fiscal year;
- CIK and SEC accession or equivalent stable source identifier;
- authoritative URL;
- local SHA-256;
- PDF page count;
- whether PDF page `n` corresponds to released Markdown `# Page n`;
- any offset, inserted cover pages, or missing pages.

The public FinLongDocQA v1.1 archive does not provide this information. Markdown-generated PDFs are not acceptable substitutes for the primary OCR condition.

### 0G. Render verified pages

Render each source PDF once at 200 DPI and reuse the same page images across models. The rendering command must:

- use internal zero-based pages but convert to the renderer's one-based page interface;
- avoid overwriting previous outputs silently;
- record the source PDF checksum and renderer version;
- fail if any PDF is missing or pagination is unresolved.

### Phase 0 pass criteria

All must be true:

- full-release structural audit has zero errors;
- pilot manifests have zero structural errors;
- all pilot documents point to verified PDFs;
- every manual check has researcher signoff;
- failed/concern annotations are corrected or excluded through a documented overlay;
- the 200-DPI evidence-page render is visually verified;
- the machine-readable audit reports `ready_for_ocr_dry_run`.

## Phase 1 boundary

Only after Phase 0 passes:

1. Install Unlimited-OCR in an isolated environment.
2. Run one verified page with `infer`.
3. Run the matching two-page window with `infer_multi`.
4. Save raw and normalized output, runtime, peak GPU memory, environment, and errors.
5. Compare against native PDF text before adding another OCR system.

Page counts of 1, 2, 5, 10, 20, and 40 and additional model baselines remain later phases.

