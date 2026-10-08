from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from finocr.io import iter_jsonl
from finocr.schemas import DocumentRecord, TaskRecord


ANNUAL_TYPES = frozenset({"10k", "10k_annualreport"})


class FinanceBenchError(ValueError):
    """Raised when the FinanceBench release cannot be audited safely."""


@dataclass(slots=True)
class FinanceBenchConversion:
    documents: list[DocumentRecord]
    tasks: list[TaskRecord]
    inventory: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    source_document_count: int = 0
    source_question_count: int = 0


def _validate_question(row: dict[str, Any]) -> None:
    """Reject malformed supervision instead of silently deleting evidence."""
    for field in ("financebench_id", "doc_name", "question", "answer"):
        if not isinstance(row.get(field), str) or not row[field].strip():
            raise FinanceBenchError(f"{field} must be a non-empty string")
    evidence = row.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise FinanceBenchError("evidence must be a non-empty list")
    for item in evidence:
        if not isinstance(item, dict):
            raise FinanceBenchError("each evidence entry must be an object")
        page = item.get("evidence_page_num")
        if isinstance(page, bool) or not isinstance(page, int) or page < 0:
            raise FinanceBenchError("evidence_page_num must be a non-negative integer")
        for field in ("evidence_doc_name", "doc_name"):
            if field in item and (not isinstance(item[field], str) or not item[field].strip()):
                raise FinanceBenchError(f"evidence {field} must be a non-empty string")


def _sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _pdf_index(pdf_dir: Path) -> tuple[dict[str, Path], list[dict[str, Any]]]:
    by_stem: dict[str, Path] = {}
    issues: list[dict[str, Any]] = []
    for path in sorted(pdf_dir.glob("*.pdf")):
        key = path.stem.casefold()
        if key in by_stem:
            issues.append(
                {
                    "code": "duplicate_pdf_stem",
                    "doc_name": path.stem,
                    "paths": [str(by_stem[key]), str(path)],
                }
            )
        else:
            by_stem[key] = path.resolve()
    return by_stem, issues


def _inspect_pdf(path: Path) -> dict[str, Any]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - exercised by the user's environment
        raise FinanceBenchError(
            "pypdf is required for FinanceBench Phase 0; run `python -m pip install -e .`"
        ) from exc

    try:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)
        sample_indices = sorted({0, page_count // 2, page_count - 1}) if page_count else []
        sample_characters = 0
        readable_pages = 0
        for index in sample_indices:
            text = reader.pages[index].extract_text() or ""
            sample_characters += len(text.strip())
            readable_pages += bool(text.strip())
        return {
            "pdf_valid": True,
            "page_count": page_count,
            "native_text_sample_pages": len(sample_indices),
            "native_text_readable_pages": readable_pages,
            "native_text_sample_characters": sample_characters,
            "native_text_available": readable_pages > 0,
            "pdf_error": None,
        }
    except Exception as exc:  # retain bad rows in the audit instead of aborting the scan
        return {
            "pdf_valid": False,
            "page_count": 0,
            "native_text_sample_pages": 0,
            "native_text_readable_pages": 0,
            "native_text_sample_characters": 0,
            "native_text_available": False,
            "pdf_error": f"{type(exc).__name__}: {exc}",
        }


def convert_financebench(
    metadata_path: str | Path,
    questions_path: str | Path,
    pdf_dir: str | Path,
) -> FinanceBenchConversion:
    metadata = list(iter_jsonl(metadata_path))
    questions = list(iter_jsonl(questions_path))
    pdf_root = Path(pdf_dir)
    if not pdf_root.is_dir():
        raise FinanceBenchError(f"PDF directory does not exist: {pdf_root}")

    pdfs, issues = _pdf_index(pdf_root)
    if not metadata:
        issues.append({"code": "empty_metadata"})
    if not questions:
        issues.append({"code": "empty_questions"})
    source_question_count = len(questions)
    valid_questions = []
    seen_question_ids: set[str] = set()
    for position, question in enumerate(questions, start=1):
        try:
            _validate_question(question)
        except FinanceBenchError as exc:
            issues.append({"code": "invalid_question_schema", "source_row": position, "message": str(exc)})
            continue
        identifier = question["financebench_id"].strip()
        if identifier in seen_question_ids:
            issues.append({"code": "duplicate_source_question_id", "financebench_id": identifier})
        seen_question_ids.add(identifier)
        valid_questions.append(question)
    questions = valid_questions
    metadata_names = [str(row.get("doc_name", "")).strip() for row in metadata]
    for name, count in Counter(metadata_names).items():
        if not name:
            issues.append({"code": "empty_doc_name"})
        elif count > 1:
            issues.append({"code": "duplicate_metadata_doc_name", "doc_name": name, "count": count})

    qa_by_doc: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for question in questions:
        qa_by_doc[str(question.get("doc_name", "")).strip()].append(question)

    documents: list[DocumentRecord] = []
    inventory: list[dict[str, Any]] = []
    by_doc_name: dict[str, DocumentRecord] = {}
    for row in metadata:
        doc_name = str(row.get("doc_name", "")).strip()
        if not doc_name:
            continue
        year = row.get("doc_period")
        if (
            not isinstance(row.get("company"), str) or not row["company"].strip()
            or not isinstance(row.get("doc_type"), str) or not row["doc_type"].strip()
            or isinstance(year, bool) or not isinstance(year, (str, int))
            or not str(year).isdigit() or len(str(year)) != 4
        ):
            issues.append({"code": "invalid_document_metadata", "doc_name": doc_name})
            continue
        path = pdfs.get(doc_name.casefold())
        inspected = _inspect_pdf(path) if path else {
            "pdf_valid": False,
            "page_count": 0,
            "native_text_sample_pages": 0,
            "native_text_readable_pages": 0,
            "native_text_sample_characters": 0,
            "native_text_available": False,
            "pdf_error": "PDF not found",
        }
        if path is None:
            issues.append({"code": "missing_pdf", "doc_name": doc_name})
        elif not inspected["pdf_valid"]:
            issues.append(
                {"code": "invalid_pdf", "doc_name": doc_name, "message": inspected["pdf_error"]}
            )

        doc_id = f"financebench:{doc_name}"
        metadata_values = {
            "doc_name": doc_name,
            "company": row.get("company"),
            "fiscal_year": row.get("doc_period"),
            "doc_type": str(row.get("doc_type", "")).lower(),
            "sector": (row.get("gics_sector") or row.get("company_sector_gics")
                       or row.get("comany_sector_gics")),
            "source_url": row.get("doc_link"),
            "sha256": _sha256(path) if path and inspected["pdf_valid"] else None,
            "file_size_bytes": path.stat().st_size if path else None,
            "native_text_available": inspected["native_text_available"],
            "native_text_sample_characters": inspected["native_text_sample_characters"],
        }
        document = DocumentRecord(
            doc_id=doc_id,
            dataset="financebench",
            pdf_path=str(path) if path else None,
            source_path=str(path) if path else None,
            source_format="pdf" if path and inspected["pdf_valid"] else "unknown",
            split="open_source",
            page_count=int(inspected["page_count"]),
            metadata=metadata_values,
        )
        documents.append(document)
        by_doc_name[doc_name] = document
        evidence_pages = {
            int(evidence["evidence_page_num"])
            for question in qa_by_doc.get(doc_name, [])
            for evidence in question.get("evidence", [])
            if isinstance(evidence.get("evidence_page_num"), int)
            and not isinstance(evidence.get("evidence_page_num"), bool)
        }
        inventory.append(
            {
                "doc_id": doc_id,
                "doc_name": doc_name,
                "company": row.get("company"),
                "fiscal_year": row.get("doc_period"),
                "doc_type": str(row.get("doc_type", "")).lower(),
                "sector": metadata_values["sector"],
                "pdf_path": str(path) if path else None,
                "pdf_exists": path is not None,
                "pdf_valid": inspected["pdf_valid"],
                "pdf_error": inspected["pdf_error"],
                "page_count": inspected["page_count"],
                "file_size_bytes": metadata_values["file_size_bytes"],
                "sha256": metadata_values["sha256"],
                "native_text_available": inspected["native_text_available"],
                "native_text_sample_pages": inspected["native_text_sample_pages"],
                "native_text_readable_pages": inspected["native_text_readable_pages"],
                "native_text_sample_characters": inspected["native_text_sample_characters"],
                "qa_case_count": len(qa_by_doc.get(doc_name, [])),
                "unique_evidence_page_count": len(evidence_pages),
            }
        )

    tasks: list[TaskRecord] = []
    for position, row in enumerate(questions, start=1):
        doc_name = str(row.get("doc_name", "")).strip()
        document = by_doc_name.get(doc_name)
        raw_id = row.get("financebench_id", position)
        task_id = f"financebench:{raw_id}"
        if document is None:
            issues.append({"code": "question_unknown_document", "task_id": task_id, "doc_name": doc_name})
            continue
        evidence = row.get("evidence", [])
        pages = sorted(
            {
                int(item["evidence_page_num"])
                for item in evidence
                if isinstance(item.get("evidence_page_num"), int)
                and not isinstance(item.get("evidence_page_num"), bool)
            }
        )
        evidence_docs = sorted(
            {
                str(item.get("evidence_doc_name", item.get("doc_name", ""))).strip()
                for item in evidence
                if item.get("evidence_doc_name", item.get("doc_name"))
            }
        )
        if any(name != doc_name for name in evidence_docs):
            issues.append(
                {
                    "code": "cross_document_evidence",
                    "task_id": task_id,
                    "doc_name": doc_name,
                    "evidence_doc_names": evidence_docs,
                }
            )
        tasks.append(
            TaskRecord(
                task_id=task_id,
                doc_id=document.doc_id,
                task_type="question_answering",
                question=str(row.get("question", "")).strip(),
                answers=[str(row.get("answer", "")).strip()] if row.get("answer") is not None else [],
                evidence_pages=pages,
                metadata={
                    "financebench_id": raw_id,
                    "question_type": row.get("question_type"),
                    "question_reasoning": row.get("question_reasoning"),
                    "domain_question_num": row.get("domain_question_num"),
                    "justification": row.get("justification"),
                    "evidence_doc_names": evidence_docs,
                    "evidence": evidence,
                    "source_page_index_base": 0,
                },
            )
        )

    metadata_keys = set(metadata_names)
    for orphan in sorted(set(pdfs) - {name.casefold() for name in metadata_keys if name}):
        issues.append({"code": "pdf_without_metadata", "pdf_path": str(pdfs[orphan])})
    return FinanceBenchConversion(
        documents, tasks, inventory, issues,
        source_document_count=len(metadata), source_question_count=source_question_count,
    )


def select_financebench_pilot(
    inventory: list[dict[str, Any]],
    *,
    company_count: int = 4,
    reports_per_company: int = 3,
    minimum_years: int = 8,
) -> list[dict[str, Any]]:
    if company_count < 1 or reports_per_company < 1 or minimum_years < 1:
        raise FinanceBenchError("Pilot counts and minimum_years must be positive")
    annual = [
        row for row in inventory
        if row["doc_type"] in ANNUAL_TYPES and row["pdf_valid"]
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in annual:
        grouped[str(row["company"])].append(row)

    candidates: list[dict[str, Any]] = []
    for company, rows in grouped.items():
        years = {int(row["fiscal_year"]) for row in rows}
        if len(years) < max(minimum_years, reports_per_company):
            continue
        candidates.append(
            {
                "company": company,
                "sector": next((row["sector"] for row in rows if row.get("sector")), "Unknown"),
                "rows": rows,
                "years": len(years),
                "qa_cases": sum(int(row["qa_case_count"]) for row in rows),
                "annotated_documents": sum(int(row["qa_case_count"]) > 0 for row in rows),
            }
        )
    candidates.sort(
        key=lambda value: (
            -value["qa_cases"],
            -value["annotated_documents"],
            -value["years"],
            value["company"],
        )
    )

    chosen: list[dict[str, Any]] = []
    used_sectors: set[str] = set()
    for candidate in candidates:
        sector = str(candidate["sector"])
        if sector not in used_sectors:
            chosen.append(candidate)
            used_sectors.add(sector)
        if len(chosen) == company_count:
            break
    if len(chosen) < company_count:
        for candidate in candidates:
            if candidate not in chosen:
                chosen.append(candidate)
            if len(chosen) == company_count:
                break
    if len(chosen) < company_count:
        raise FinanceBenchError(
            f"Only {len(chosen)} companies satisfy the {minimum_years}-year pilot requirement"
        )

    selected: list[dict[str, Any]] = []
    for candidate in chosen:
        by_year: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for row in candidate["rows"]:
            by_year[int(row["fiscal_year"])].append(row)
        years = sorted(by_year)
        if reports_per_company == 1:
            indices = [len(years) // 2]
        elif reports_per_company == 3:
            indices = [0, len(years) // 2, len(years) - 1]
        else:
            indices = [round(i * (len(years) - 1) / (reports_per_company - 1)) for i in range(reports_per_company)]
        for index in dict.fromkeys(indices):
            rows = sorted(
                by_year[years[index]],
                key=lambda row: (
                    -int(row["qa_case_count"]),
                    row["doc_type"] != "10k",
                    row["doc_name"],
                ),
            )
            selected.append(rows[0])
    return selected


def write_inventory_csv(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    materialized = list(rows)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not materialized:
        target.write_text("", encoding="utf-8")
        return
    with target.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(materialized[0]))
        writer.writeheader()
        writer.writerows(materialized)
