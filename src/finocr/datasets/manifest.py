from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from finocr.io import read_jsonl
from finocr.schemas import DocumentRecord, TaskRecord


@dataclass(slots=True)
class DatasetAudit:
    document_count: int
    task_count: int
    missing_pdf_count: int
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return asdict(self) | {"valid": self.valid}


def load_documents(path: str | Path) -> list[DocumentRecord]:
    return [DocumentRecord.from_dict(item) for item in read_jsonl(path)]


def load_tasks(path: str | Path) -> list[TaskRecord]:
    return [TaskRecord.from_dict(item) for item in read_jsonl(path)]


def validate_manifests(
    documents: list[DocumentRecord],
    tasks: list[TaskRecord],
    *,
    require_files: bool = False,
) -> DatasetAudit:
    errors: list[str] = []
    warnings: list[str] = []
    doc_ids = [record.doc_id for record in documents]
    task_ids = [record.task_id for record in tasks]
    duplicate_docs = sorted({value for value in doc_ids if doc_ids.count(value) > 1})
    duplicate_tasks = sorted({value for value in task_ids if task_ids.count(value) > 1})
    if duplicate_docs:
        errors.append(f"Duplicate document IDs: {duplicate_docs}")
    if duplicate_tasks:
        errors.append(f"Duplicate task IDs: {duplicate_tasks}")

    documents_by_id = {record.doc_id: record for record in documents}
    missing_pdf_count = 0
    for document in documents:
        if document.page_count <= 0:
            errors.append(f"{document.doc_id}: page_count must be positive")
        if document.page_paths and len(document.page_paths) != document.page_count:
            errors.append(
                f"{document.doc_id}: page_paths has {len(document.page_paths)} items "
                f"but page_count is {document.page_count}"
            )
        if not Path(document.pdf_path).exists():
            missing_pdf_count += 1
            message = f"{document.doc_id}: PDF not found at {document.pdf_path}"
            (errors if require_files else warnings).append(message)

    for task in tasks:
        document = documents_by_id.get(task.doc_id)
        if document is None:
            errors.append(f"{task.task_id}: unknown doc_id {task.doc_id}")
            continue
        invalid_pages = [
            page for page in task.evidence_pages if page < 0 or page >= document.page_count
        ]
        if invalid_pages:
            errors.append(
                f"{task.task_id}: evidence pages outside document range: {invalid_pages}"
            )
        if task.task_type == "question_answering" and not task.question:
            errors.append(f"{task.task_id}: question_answering task has no question")
        if not task.answers and not task.target_fields and task.task_type != "ocr_reference":
            warnings.append(f"{task.task_id}: task has no answer or target field")

    return DatasetAudit(
        document_count=len(documents),
        task_count=len(tasks),
        missing_pdf_count=missing_pdf_count,
        errors=errors,
        warnings=warnings,
    )

