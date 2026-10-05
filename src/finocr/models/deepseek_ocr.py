from __future__ import annotations

from finocr.models.base import AdapterNotConfigured, OCRAdapter
from finocr.schemas import OCRRequest, OCRResult


class DeepSeekOCRAdapter(OCRAdapter):
    model_id = "deepseek_ocr"
    supported_strategies = frozenset({"page_by_page"})

    def transcribe(self, request: OCRRequest) -> OCRResult:
        self.validate_request(request)
        raise AdapterNotConfigured(
            "Connect this adapter to the official deepseek-ai/DeepSeek-OCR inference code. "
            "Process the exact rendered pages independently and preserve page boundaries."
        )

