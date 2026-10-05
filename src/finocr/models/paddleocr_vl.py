from __future__ import annotations

from finocr.models.base import AdapterNotConfigured, OCRAdapter
from finocr.schemas import OCRRequest, OCRResult


class PaddleOCRVLAdapter(OCRAdapter):
    model_id = "paddleocr_vl"
    supported_strategies = frozenset({"page_by_page"})

    def transcribe(self, request: OCRRequest) -> OCRResult:
        self.validate_request(request)
        raise AdapterNotConfigured(
            "Connect this adapter to the official PaddleOCR-VL pipeline. Process each page "
            "independently and map its structured output into page_text plus raw artifacts."
        )

