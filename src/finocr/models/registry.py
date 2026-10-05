from __future__ import annotations

from finocr.models.base import OCRAdapter
from finocr.models.deepseek_ocr import DeepSeekOCRAdapter
from finocr.models.native_pdf_text import NativePDFTextAdapter
from finocr.models.paddleocr_vl import PaddleOCRVLAdapter
from finocr.models.unlimited_ocr import UnlimitedOCRAdapter


def build_adapter(model_id: str) -> OCRAdapter:
    adapters: dict[str, type[OCRAdapter]] = {
        "unlimited_ocr": UnlimitedOCRAdapter,
        "deepseek_ocr": DeepSeekOCRAdapter,
        "paddleocr_vl": PaddleOCRVLAdapter,
        "native_pdf_text": NativePDFTextAdapter,
    }
    try:
        return adapters[model_id]()
    except KeyError as exc:
        raise KeyError(f"Unknown model ID {model_id!r}; options={sorted(adapters)}") from exc

