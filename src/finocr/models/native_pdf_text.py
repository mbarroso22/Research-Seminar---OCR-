from __future__ import annotations

from finocr.models.base import AdapterNotConfigured, OCRAdapter
from finocr.schemas import OCRRequest, OCRResult


class NativePDFTextAdapter(OCRAdapter):
    model_id = "native_pdf_text"
    supported_strategies = frozenset({"native_text"})

    def transcribe(self, request: OCRRequest) -> OCRResult:
        self.validate_request(request)
        raise AdapterNotConfigured(
            "Implement with PyMuPDF page.get_text() after installing the optional `pdf` extras. "
            "Treat missing/empty embedded text as unavailable, never as an OCR score of zero."
        )

