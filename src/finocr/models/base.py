from __future__ import annotations

from abc import ABC, abstractmethod

from finocr.schemas import OCRRequest, OCRResult


class AdapterNotConfigured(RuntimeError):
    """Raised when a heavyweight model environment has not been connected yet."""


class OCRAdapter(ABC):
    model_id: str
    supported_strategies: frozenset[str]

    def validate_request(self, request: OCRRequest) -> None:
        if request.strategy not in self.supported_strategies:
            raise ValueError(
                f"{self.model_id} does not support strategy {request.strategy}; "
                f"supported={sorted(self.supported_strategies)}"
            )
        if not request.page_image_paths and request.strategy != "native_text":
            raise ValueError("OCR requests require at least one rendered page image")

    @abstractmethod
    def transcribe(self, request: OCRRequest) -> OCRResult:
        """Run OCR and return normalized output plus timing and memory metadata."""

