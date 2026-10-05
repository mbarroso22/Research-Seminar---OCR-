# FinLongDocQA Phase 0 findings and design implications

## 1. FinLongDocQA has two distinct roles

The released v1.1 data is immediately useful for:

- evidence-page retrieval;
- numerical QA;
- native-text retrieval ceilings;
- selecting long reports and evidence windows;
- testing whether downstream retrieval survives controlled text corruption.

It is not, by itself, an OCR input dataset. The public archive has Markdown generated from PDFs with MinerU, while the original PDF bytes and their identifiers are absent.

The study should therefore keep two layers separate:

1. **Document-image layer:** exact source PDFs and 200-DPI page images used by OCR.
2. **Task/evaluation layer:** FinLongDocQA questions, numerical answers, and evidence-page supervision.

Joining the layers requires an explicit, audited mapping. A matching ticker and year is not enough if pagination differs.

## 2. Structural quality is strong

The complete release inspected here contains:

- 7,527 unique QA records;
- 1,456 page-delimited Markdown reports;
- 489 companies;
- 1,329 reports referenced by at least one QA task;
- 127 reports without a retained QA task;
- report lengths from 8 to 802 pages;
- evidence references from source pages 2 to 658;
- zero missing task/report mappings;
- zero out-of-range evidence pages;
- contiguous one-based page markers in every report.

This makes v1.1 straightforward to convert reproducibly.

## 3. Content quality needs a curation layer

The purposeful ten-task review found:

- 3 passes;
- 2 concerns;
- 5 failures.

Observed problem classes:

- an extra cited page contains no required evidence;
- both operands occur on one page despite a two-page gold label;
- a direct lookup is presented as multi-page reasoning;
- compared quantities have incompatible units;
- technically distinct terms such as resource and reserve are conflated.

Because the sample was intentionally stratified rather than random, these counts must not be reported as the full benchmark's error rate. They do show that page-range validation alone is insufficient.

## 4. Recommended immutable curation overlay

Do not edit `dataset_qa.jsonl`. Add a separate record keyed by `source_task_id`:

```json
{
  "source_task_id": "59",
  "decision": "exclude",
  "reason_codes": ["incorrect_evidence_page", "ambiguous_operand"],
  "source_pages_before": [19, 20],
  "source_pages_after": [19],
  "reviewer": "researcher-id",
  "reviewed_at": "ISO-8601 timestamp",
  "notes": "..."
}
```

Allowed decisions should be `keep`, `correct`, or `exclude`. Evaluation manifests should record the overlay version and never silently mix raw and curated labels.

## 5. Source-PDF recovery requirements

The paper says the authors collected PDF filings from SEC EDGAR, then used MinerU. However, ticker/year alone does not identify the exact PDF representation or pagination, and an inspected SEC filing directory may contain HTML/XBRL without the authors' PDF artifact.

The preferred resolution is an author-supplied mapping or archive. A request should ask for:

- the exact PDF files or stable download URLs;
- CIK and accession numbers;
- SHA-256 checksums;
- PDF page counts;
- conversion command/settings;
- known page offsets or extraction failures.

If exact PDFs cannot be recovered, FinLongDocQA should remain the downstream/native-text benchmark and a dataset with released page images or PDFs should provide the primary OCR-fidelity input. That would be a documented design change, not an invisible substitution.

