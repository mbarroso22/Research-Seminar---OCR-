# Data policy and manifest format

Keep downloaded datasets out of version control. The repository stores only manifests, checksums, transformations, and evaluation outputs.

## `documents.jsonl`

Required fields:

```json
{"doc_id":"report_001","dataset":"finlongdocqa","pdf_path":"data/raw/finlongdocqa/report_001.pdf","split":"dev","page_count":64,"page_paths":[],"metadata":{}}
```

`page_paths` may be empty before rendering. After rendering, it should contain ordered image paths.

## `tasks.jsonl`

```json
{"task_id":"q_001","doc_id":"report_001","task_type":"question_answering","question":"What was revenue in 2023?","answers":["$10.2 million"],"evidence_pages":[11],"target_fields":{},"metadata":{}}
```

All `evidence_pages` are zero-indexed internally. Preserve the source's original index in `metadata` when converting.

## Reliability audit before use

- Confirm license/research-use terms.
- Confirm the PDF version matches the annotation version.
- Check file hashes after download.
- Check that every task references an existing document.
- Check evidence pages fall inside `[0, page_count)`.
- Check duplicated IDs and missing answers.
- Manually inspect at least 10 examples per dataset.
- Record any corrections without silently editing original annotations.

