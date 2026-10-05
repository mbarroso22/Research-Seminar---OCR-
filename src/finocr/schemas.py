from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


TaskType = Literal["question_answering", "field_extraction", "ocr_reference"]
Strategy = Literal["one_shot", "page_by_page", "native_text"]
SourceFormat = Literal["pdf", "markdown", "image", "unknown"]


@dataclass(slots=True)
class DocumentRecord:
    doc_id: str
    dataset: str
    pdf_path: str | None
    split: str
    page_count: int
    page_paths: list[str] = field(default_factory=list)
    source_path: str | None = None
    source_format: SourceFormat | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DocumentRecord":
        normalized = dict(value)
        normalized.setdefault("pdf_path", None)
        normalized.setdefault("page_paths", [])
        normalized.setdefault("source_path", normalized.get("pdf_path"))
        normalized.setdefault("source_format", None)
        normalized.setdefault("metadata", {})
        return cls(**normalized)

    @property
    def primary_path(self) -> str | None:
        return self.source_path or self.pdf_path

    @property
    def ocr_input_ready(self) -> bool:
        return self.source_format == "pdf" and bool(self.pdf_path)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    doc_id: str
    task_type: TaskType
    question: str | None = None
    answers: list[str] = field(default_factory=list)
    evidence_pages: list[int] = field(default_factory=list)
    target_fields: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "TaskRecord":
        normalized = dict(value)
        normalized.setdefault("question", None)
        normalized.setdefault("answers", [])
        normalized.setdefault("evidence_pages", [])
        normalized.setdefault("target_fields", {})
        normalized.setdefault("metadata", {})
        return cls(**normalized)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PageWindow:
    doc_id: str
    start_page: int
    end_page: int

    @property
    def page_count(self) -> int:
        return self.end_page - self.start_page

    def page_indices(self) -> list[int]:
        return list(range(self.start_page, self.end_page))


@dataclass(slots=True)
class OCRRequest:
    run_id: str
    document: DocumentRecord
    window: PageWindow
    strategy: Strategy
    page_image_paths: list[str]
    prompt: str = "document parsing."
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class OCRResult:
    run_id: str
    doc_id: str
    model_id: str
    strategy: Strategy
    page_indices: list[int]
    page_text: dict[int, str]
    full_text: str
    runtime_seconds: float
    peak_gpu_mb: float | None
    success: bool
    error: str | None = None
    raw_output_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

