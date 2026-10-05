# FinLongDocQA Phase 0 data-quality audit

**Status:** `blocked_before_ocr`

## Outcome

The unified pilot manifests are structurally valid, but the pilot is not ready for OCR. The official release supplies page-delimited Markdown rather than the source PDFs, and the content-level review found ground-truth issues that structural checks cannot detect.

## Official v1.1 release audit

| Check | Result |
|---|---:|
| QA records | 7,527 |
| Markdown reports | 1,456 |
| Companies | 489 |
| Reports referenced by QA | 1,329 |
| Reports without QA | 127 |
| Missing report mappings | 0 |
| Out-of-range evidence references | 0 |
| Released PDFs | 0 |

All report page markers are contiguous and one-based. The adapter converts evidence pages once to zero-based internal indices and retains the source values in task metadata. Reference Python programs were preserved but never executed by the adapter.

## Ten-report pilot

| Check | Result |
|---|---:|
| Documents | 10 |
| Tasks | 59 |
| Page-count range | 44–802 |
| Manifest errors | 0 |
| OCR-ready PDFs | 0 |

Question types: `mixed` 42, `table` 10, `text` 7.

## Manual content review

The ten checks were purposefully stratified, so these counts diagnose the pilot and are not a random estimate of the full dataset's error rate.

| Source task | Company/year | Status | Main finding |
|---:|---|---|---|
| 20 | AAPL/2022 | `concern` | The math and both citations are supported, but the pages duplicate the same evidence and do not form a genuine multi-page task. |
| 59 | ABNB/2023 | `fail` | The stored arithmetic is reproducible, but one gold page is wrong and the employee operand is narrower than the question states. |
| 358 | ALB/2023 | `concern` | Both pages and the calculation are supported, but the technically distinct terms resource and reserve are conflated. |
| 1688 | CMS/2024 | `pass` | Both operands appear on the cited pages and independently reproduce the gold answer. |
| 1703 | CNC/2024 | `fail` | The code yields 15, but a gold page is incorrect and the compared quantities have incompatible units. |
| 2765 | EQR/2023 | `fail` | Both values are on the cited pages and the arithmetic matches, but the requested ratio is not semantically meaningful. |
| 4446 | KIM/2024 | `fail` | The arithmetic matches, but one evidence page is unsupported and the ratio mixes percent and years. |
| 4715 | LMT/2023 | `pass` | The cited pages supply the segment margin and consolidated operands, and the recomputation matches the gold answer. |
| 6423 | PSX/2022 | `pass` | The two cited pages contain the required operands and reproduce the gold percentage. |
| 7583 | TYL/2022 | `fail` | The answer is correct as a direct lookup, but the second evidence page is unsupported and the task is not multi-page reasoning. |

## OCR and rendering gate

Rendering at 200 DPI was not performed because there are no verified source PDFs in the official release. Rendering Markdown into synthetic PDFs would change the input distribution and would not test OCR on the documents used to create the benchmark.

Blocking items:

- `source_pdfs_unavailable` — The official FinLongDocQA report archive contains Markdown, not the source PDFs used to create it.
- `pilot_not_ocr_ready` — Only 0 of 10 pilot documents point to verified PDF inputs.
- `manual_ground_truth_failures` — 5 of 10 manually inspected tasks have blocking evidence or semantic issues.
- `researcher_signoff_pending` — 10 content checks were prepared by assistant inspection and still require researcher signoff.

## Next action

1. Acquire the exact source PDFs used by the dataset authors or obtain an author-supplied PDF-to-report mapping.
2. Verify PDF page counts and page labels against every selected Markdown '# Page N' marker.
3. Resolve, correct, or exclude tasks marked fail or concern in the manual-review file.
4. Have the researcher inspect the evidence packets and record human signoff.
5. Populate pdf_path only after identity and pagination checks pass.
6. Render verified evidence pages at 200 DPI, then rerun the audit.
7. Install no OCR model until all Phase 0 blockers are cleared.
