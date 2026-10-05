from __future__ import annotations

from finocr.models.base import AdapterNotConfigured, OCRAdapter
from finocr.schemas import OCRRequest, OCRResult


class UnlimitedOCRAdapter(OCRAdapter):
    """Adapter boundary for Baidu Unlimited-OCR.

    The official model exposes `model.infer` for one image and `model.infer_multi`
    for a list of page images. Keep model loading in a dedicated environment because
    the official release pins CUDA/PyTorch/Transformers versions.
    """

    model_id = "unlimited_ocr"
    supported_strategies = frozenset({"one_shot", "page_by_page"})

    def transcribe(self, request: OCRRequest) -> OCRResult:
        self.validate_request(request)
        raise AdapterNotConfigured(
            "Connect this adapter to the official baidu/Unlimited-OCR environment. "
            "For one_shot call infer_multi once; for page_by_page call infer once per page. "
            "Capture raw output, wall time, and peak allocated GPU memory before normalization."
        )

