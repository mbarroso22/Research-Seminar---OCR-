# FinLongDocQA source and licensing record

This directory contains a **non-commercial academic pilot subset** of FinLongDocQA v1.1.

## Authoritative sources

- Repository: https://github.com/AI-Application-and-Integration-Lab/FinLongDocQA
- Hugging Face dataset: https://huggingface.co/datasets/Amian/FinLongDocQA
- Paper: https://arxiv.org/abs/2604.03664
- Full report archive linked by the authors: https://drive.google.com/file/d/1MySo4fFBEeht7lVasDCVrvHWki8Yvkkk/view

The v1.1 update is dated 2026-06-16 and revises `page_numbers` without changing the 7,527-example set. The Hugging Face revision inspected for this audit was `dc9f72b620022a748db9a8c5bcf123ef285512e8`.

## Verified full-download checksums

| File | Bytes | SHA-256 |
|---|---:|---|
| `dataset_qa.jsonl` | 4,361,733 | `b4b8d7d78c4bf51b9cc891eaabe0d3324b13e21bdb5edcadc8ea756e7aac96c9` |
| `reports.zip` | 226,993,533 | `61ae06db1f599fcd76ff6f77a015af4104497f8fae62b4477ecaa8694a6ba3e9` |

The full downloads are intentionally excluded from this package. `dataset_qa.pilot.jsonl` contains all 59 upstream annotations for the selected ten reports, and `reports/` contains those ten released Markdown reports.

## Critical format finding

Despite the upstream paper describing source PDF filings, the public `reports.zip` inspected here contains **1,456 page-delimited Markdown files and zero PDFs**. A report is stored as `reports/<company>/<year>.md` and uses headings such as `# Page 1`. The Markdown was produced with MinerU according to the paper.

Consequences:

1. These files are suitable for native-text retrieval and evidence-page QA.
2. They are not raw OCR inputs.
3. Generating new PDFs from the Markdown would create synthetic layouts and invalidate an OCR comparison.
4. The exact source PDFs and a verified PDF-to-Markdown page mapping must be acquired before OCR rendering.

## Page-number convention

- Upstream `page_numbers`: one-based.
- Released Markdown page labels: one-based.
- Unified manifest `evidence_pages`: zero-based.
- The adapter applies `internal_page = source_page - 1` once and retains the original values in `metadata.source_page_numbers`.

## License

The included upstream annotations and reports remain subject to the AI²Lab Source Code License (National Taiwan University), including its non-commercial-use limitation. The complete upstream license is included at `third_party/FinLongDocQA-LICENSE`.

