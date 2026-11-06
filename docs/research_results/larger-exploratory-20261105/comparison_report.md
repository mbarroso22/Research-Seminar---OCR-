# Larger new-company exploratory comparison

Separate fixed exploratory study; no promotion gate. Original pilot FAIL remains unchanged.

| Text | Method | Recall@5 | Hit@5 | Complete@5 | Multi-page complete@5 |
|---|---|---:|---:|---:|---:|
| native | bm25 | 25.862069% | 17/58 | 13/58 | 1/22 |
| native | semantic | 55.172414% | 36/58 | 28/58 | 9/22 |
| native | hybrid | 46.551724% | 32/58 | 22/58 | 2/22 |
| ocr | bm25 | 25.862069% | 17/58 | 13/58 | 1/22 |
| ocr | semantic | 55.172414% | 37/58 | 27/58 | 7/22 |
| ocr | hybrid | 46.551724% | 32/58 | 22/58 | 2/22 |

Primary OCR minus native BM25 Recall@5: 0.000000 percentage points; company-cluster bootstrap 95% interval [0.000000, 0.000000] points.

All question-level gains/regressions, evidence ranks, multi-page cases, equal-company sensitivity summaries and paired intervals are retained in comparison_metrics.json.
Costs are single-run descriptive measurements. No controlled speedup, energy, answer quality or population-generalization claim.
