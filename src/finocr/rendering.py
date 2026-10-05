from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from finocr.schemas import DocumentRecord, TaskRecord


class RenderingError(RuntimeError):
    pass


def build_render_plan(
    documents: list[DocumentRecord], tasks: list[TaskRecord]
) -> dict[str, Any]:
    by_id = {document.doc_id: document for document in documents}
    pages_by_document: dict[str, set[int]] = {}
    for task in tasks:
        pages_by_document.setdefault(task.doc_id, set()).update(task.evidence_pages)

    jobs: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for doc_id, pages in sorted(pages_by_document.items()):
        document = by_id[doc_id]
        if not document.ocr_input_ready:
            blockers.append(
                {
                    "doc_id": doc_id,
                    "code": "verified_pdf_missing",
                    "source_format": document.source_format,
                    "pdf_path": document.pdf_path,
                }
            )
            continue
        jobs.append(
            {
                "doc_id": doc_id,
                "pdf_path": document.pdf_path,
                "internal_pages": sorted(pages),
                "pdf_pages": [page + 1 for page in sorted(pages)],
            }
        )
    return {"ready": not blockers, "jobs": jobs, "blockers": blockers}


def render_evidence_pages(
    documents: list[DocumentRecord],
    tasks: list[TaskRecord],
    output_dir: str | Path,
    *,
    repository_root: str | Path = ".",
    dpi: int = 200,
) -> list[Path]:
    if dpi <= 0:
        raise RenderingError("DPI must be positive")
    if shutil.which("pdftoppm") is None:
        raise RenderingError("pdftoppm (Poppler) is required for PDF rendering")

    plan = build_render_plan(documents, tasks)
    if not plan["ready"]:
        labels = ", ".join(item["doc_id"] for item in plan["blockers"][:10])
        raise RenderingError(
            "Rendering blocked because verified PDF inputs are missing for: " + labels
        )

    root = Path(repository_root)
    output = Path(output_dir)
    written: list[Path] = []
    for job in plan["jobs"]:
        pdf = Path(str(job["pdf_path"]))
        if not pdf.is_absolute():
            pdf = root / pdf
        if not pdf.is_file():
            raise RenderingError(f"PDF does not exist: {pdf}")
        document_dir = output / str(job["doc_id"]).replace(":", "__")
        document_dir.mkdir(parents=True, exist_ok=True)
        for internal_page in job["internal_pages"]:
            pdf_page = internal_page + 1
            prefix = document_dir / f"page_{internal_page:04d}"
            command = [
                "pdftoppm",
                "-f",
                str(pdf_page),
                "-l",
                str(pdf_page),
                "-singlefile",
                "-png",
                "-r",
                str(dpi),
                str(pdf),
                str(prefix),
            ]
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode != 0:
                raise RenderingError(
                    f"pdftoppm failed for {job['doc_id']} page {pdf_page}: "
                    f"{completed.stderr.strip()}"
                )
            target = prefix.with_suffix(".png")
            if not target.is_file():
                raise RenderingError(f"Renderer did not create {target}")
            written.append(target)
    return written

