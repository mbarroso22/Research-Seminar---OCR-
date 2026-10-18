# Review of the supplied rendering and CPU-smoke artifacts

**Later milestone 2026-10-18:** full CPU/GPU OCR and matched retrieval are now
verified in [NATIVE_OCR_PILOT_RESULTS.md](NATIVE_OCR_PILOT_RESULTS.md). This file
retains the earlier setup-only review and its then-pending execution status.

Reviewed 2026-10-17, continuing from `61a696d`. This is a review of real setup
outputs supplied by the researcher, not a full-report OCR experiment. The next
commands are in [FULL_OCR_WINDOWS.md](FULL_OCR_WINDOWS.md).

## Verified setup observations

The supplied `full-rendering-records(1).zip` contains a complete rendering
manifest and page-record export. Their recorded hashes and sizes reconcile.
All 12 reports and 2,620 physical pages occur once, in report/page order, with
zero-based IDs, the expected source-PDF hashes, status `ok`, and 200-DPI RGB
metadata. The completed cache is:

```text
C:\Users\mbarroso\financial-ocr-data\derived\rendered\poppler-200dpi-20261013T043945Z-f407621a
```

| Artifact | Verified identity |
|---|---|
| Rendering run ID | `bdf1681af83144898dd05d469fbd1682` |
| Full rendering manifest SHA-256 | `1ff37ad01d37e3d961b3ae0d27805a1dde244023f7cd830c3bbab876c8c5ebce` |
| Rendering attempts | 2 |
| Recorded PNG bytes | 940,190,080 |
| Last rendering invocation wall time | 1,076.352844 seconds |

That wall time belongs to the last retained resume invocation; it is not total
rendering cost across both attempts. The uploaded records do not contain the
2,620 PNG files or original PDFs. Their recorded lineage is verified here; the
OCR runner checks actual local image bytes, checksums and geometry before and
after ingestion. It does not rewrite or decrypt a PDF on disk.

All artifacts in `cpu-smoke-20261013T045647Z-e1fc36a9(1).zip` match their manifest
hashes and sizes. Run `66c9fe60b88c4146bfa7d64eb47ff999` is `smoke_complete` on
AMD 2015 physical page **0**, using a 1,700 by 2,200 RGB image at 200 DPI.
The raw output has 61 lines and 3,828 characters. Its normalized representation
reconciles with the retained raw result.

| Runtime observation | Supplied execution value |
|---|---|
| Python | 3.12.10, 64 bit |
| Device | CPU; Paddle compiled with CUDA: false |
| PaddlePaddle / PaddleOCR / PaddleX | 3.3.0 / 3.3.2 / 3.3.10 |
| Smoke wall time | 39.476452 seconds |
| SDK imports/model initialization | 7.302680 seconds |
| Inference and serialization | 31.666357 seconds |
| Model-manifest SHA-256 | `d0a91a2378b843c0fcc3ea007e4505072277b55f3b6aa07ffab15c3af8a07cf4` |

The model bundle is the existing
`models\paddleocr-3.3.2-mobile-en` directory, containing
`PP-OCRv5_mobile_det` and `en_PP-OCRv5_mobile_rec`. Model weights were not
uploaded with these records; the local runner rechecks every listed model file.
The smoke page's image SHA-256 is
`eedc29d8abd577181611ab5206056dccb1b0e8a53b1d3cd47ce2b51941623732`
(386,690 bytes), matching that page in the completed full rendering.

The smoke references an earlier sample rendering manifest/export. Those two
snapshot hashes are expected to differ from the resumed full cache. The page
image identity provides the direct match. The setup runs record `bb274db` plus
working edits; their source fingerprint
`80ec00dfdae02ee888913f532e10c60f147a50ffe2516a7e8651ce29dbf46027`
matches the `61a696d` Python sources with Windows CRLF line endings. The new
full-report implementation will record its own source fingerprint.

Baseline preservation was reported by the researcher. These two bundles do
not supply a fresh before/after baseline package-inventory pair, so that claim
is not independently remeasured here. The next guide records a new pair without
installing packages or replacing either environment.

## Source-only table selection preview

The selector has been checked against the supplied native-text cache. It selects
the first two qualifying statement pages in each 2015 report using source titles,
units and numeric-token density, without questions or evidence labels:

| Report | Zero-based physical page IDs |
|---|---|
| AMD 2015 | 55, 57 |
| Best Buy 2015 | 58, 60 |
| Boeing 2015 | 50, 52 |
| PepsiCo 2015 | 73, 76 |

This is a selection preview, not a completed OCR table diagnostic. The eight
pages must be OCRed locally and inspected for signs, years, units and row/column
associations before the full run. Approximate native/OCR numeric overlap is
only an inspection aid; native extraction is not transcription ground truth.

## Completed development validation and pending execution

The latest reporting changes pass the 16 feature tests. The complete **157-test
suite passes with no skips** on the development Linux host, including actual
small Poppler PDF fixtures and simulated OCR workers. Tests cover immutable
attempts, worker reuse, interruption/timeouts, verified resume, source/model/raw
tampering, full candidates, label exclusion, control reproduction and paired
multi-page/report formatting. No real Paddle model was run by these tests.

PowerShell execution of the new wrappers, the eight-table inspection, full-report
OCR, and the matched native/OCR comparison remain pending local execution.
The cover-page smoke does not establish financial-table accuracy, full-report
throughput, retrieval gains, CER/WER or energy use. New experimental results
will be reported only after the real local outputs are supplied and verified.
