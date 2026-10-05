from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from finocr.datasets import (
    FinLongDocQAError,
    ReportKey,
    audit_finlongdocqa_release,
    convert_finlongdocqa,
    load_selection,
    split_markdown_pages,
    validate_manifests,
)
from finocr.io import write_jsonl
from finocr.rendering import build_render_plan


def annotation(
    task_id: str = "1", company: str = "AAA", year: str = "2022"
) -> dict[str, object]:
    return {
        "id": task_id,
        "company": company,
        "year": year,
        "question": "What is the computed value?",
        "type": "mixed",
        "thoughts": "Page 1 gives one value and Page 3 gives another.",
        "page_numbers": [1, 3],
        "python_code": "round(5 / 2, 2)",
        "answer": 2.5,
    }


REPORT = """\
---
# Page 1
First page.
---
# Page 2
Second page.
---
# Page 3
Third page.
"""


class FinLongDocQATests(unittest.TestCase):
    def test_split_markdown_pages_requires_contiguous_one_based_markers(self) -> None:
        pages = split_markdown_pages(REPORT)
        self.assertEqual(list(pages), [1, 2, 3])
        self.assertEqual(pages[2], "Second page.\n---")

        with self.assertRaises(FinLongDocQAError):
            split_markdown_pages("# Page 1\na\n# Page 3\nc")

    def test_adapter_converts_page_base_once_and_preserves_source_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "dataset_qa.jsonl"
            write_jsonl(annotations, [annotation()])
            source = root / "source" / "AAA"
            source.mkdir(parents=True)
            (source / "2022.md").write_text(REPORT, encoding="utf-8")

            conversion = convert_finlongdocqa(
                annotations,
                root / "source",
                [ReportKey("AAA", "2022")],
                root / "data" / "reports",
                root,
            )

            self.assertEqual(len(conversion.documents), 1)
            self.assertEqual(len(conversion.tasks), 1)
            document = conversion.documents[0]
            task = conversion.tasks[0]
            self.assertIsNone(document.pdf_path)
            self.assertEqual(document.source_format, "markdown")
            self.assertEqual(document.page_count, 3)
            self.assertEqual(task.evidence_pages, [0, 2])
            self.assertEqual(task.metadata["source_page_numbers"], [1, 3])
            self.assertEqual(task.answers, ["2.5"])
            self.assertFalse(task.metadata["reference_program_executed_by_adapter"])
            self.assertTrue((root / document.source_path).is_file())

    def test_adapter_reads_official_archive_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "dataset_qa.jsonl"
            write_jsonl(annotations, [annotation()])
            archive = root / "reports.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("reports/AAA/2022.md", REPORT)

            conversion = convert_finlongdocqa(
                annotations,
                archive,
                [ReportKey("AAA", "2022")],
                root / "materialized",
                root,
            )
            self.assertEqual(conversion.documents[0].page_count, 3)
            self.assertTrue((root / "materialized" / "AAA" / "2022.md").is_file())

    def test_release_audit_checks_report_and_evidence_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "dataset_qa.jsonl"
            write_jsonl(annotations, [annotation()])
            reports = root / "reports" / "AAA"
            reports.mkdir(parents=True)
            (reports / "2022.md").write_text(REPORT, encoding="utf-8")

            result = audit_finlongdocqa_release(annotations, root / "reports")
            self.assertTrue(result["structurally_valid"])
            self.assertEqual(result["annotation_count"], 1)
            self.assertEqual(result["report_count"], 1)
            self.assertEqual(result["released_pdf_count"], 0)
            self.assertEqual(result["source_evidence_page_range"], {"min": 1, "max": 3})

    def test_manifest_validation_distinguishes_structure_from_ocr_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "dataset_qa.jsonl"
            write_jsonl(annotations, [annotation()])
            reports = root / "reports" / "AAA"
            reports.mkdir(parents=True)
            (reports / "2022.md").write_text(REPORT, encoding="utf-8")
            conversion = convert_finlongdocqa(
                annotations,
                root / "reports",
                [ReportKey("AAA", "2022")],
                root / "materialized",
                root,
            )

            audit = validate_manifests(
                conversion.documents,
                conversion.tasks,
                require_files=True,
                repository_root=root,
            )
            self.assertTrue(audit.valid)
            self.assertEqual(audit.statistics["ocr_ready_documents"], 0)
            self.assertEqual(audit.warnings[0]["code"], "not_ocr_input_ready")

    def test_validation_rejects_out_of_range_internal_page(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "dataset_qa.jsonl"
            write_jsonl(annotations, [annotation()])
            reports = root / "reports" / "AAA"
            reports.mkdir(parents=True)
            (reports / "2022.md").write_text(REPORT, encoding="utf-8")
            conversion = convert_finlongdocqa(
                annotations,
                root / "reports",
                [ReportKey("AAA", "2022")],
                root / "materialized",
                root,
            )
            conversion.tasks[0].evidence_pages = [3]
            audit = validate_manifests(conversion.documents, conversion.tasks)
            self.assertFalse(audit.valid)
            self.assertEqual(audit.errors[0]["code"], "invalid_evidence_page")

    def test_render_plan_blocks_markdown_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            annotations = root / "dataset_qa.jsonl"
            write_jsonl(annotations, [annotation()])
            reports = root / "reports" / "AAA"
            reports.mkdir(parents=True)
            (reports / "2022.md").write_text(REPORT, encoding="utf-8")
            conversion = convert_finlongdocqa(
                annotations,
                root / "reports",
                [ReportKey("AAA", "2022")],
                root / "materialized",
                root,
            )
            plan = build_render_plan(conversion.documents, conversion.tasks)
            self.assertFalse(plan["ready"])
            self.assertEqual(plan["blockers"][0]["code"], "verified_pdf_missing")

    def test_selection_rejects_duplicate_document_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            selection = Path(directory) / "selection.json"
            selection.write_text(
                json.dumps(
                    {
                        "documents": [
                            {"company": "AAA", "year": "2022"},
                            {"company": "AAA", "year": "2022"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(FinLongDocQAError):
                load_selection(selection)


if __name__ == "__main__":
    unittest.main()

