from __future__ import annotations

import unittest

from finocr.datasets.validation import ManifestAudit
from finocr.phase0 import build_phase0_audit
from finocr.schemas import DocumentRecord, TaskRecord


class Phase0AuditTests(unittest.TestCase):
    def test_missing_pdfs_and_manual_failure_block_ocr(self) -> None:
        documents = [
            DocumentRecord(
                doc_id="finlongdocqa:AAA:2022",
                dataset="finlongdocqa",
                pdf_path=None,
                split="test",
                page_count=3,
                source_path="reports/AAA/2022.md",
                source_format="markdown",
                metadata={"fiscal_year": "2022"},
            )
        ]
        tasks = [
            TaskRecord(
                task_id="finlongdocqa:1",
                doc_id=documents[0].doc_id,
                task_type="question_answering",
                question="Question?",
                answers=["1"],
                evidence_pages=[0],
                metadata={"question_type": "text"},
            )
        ]
        release = {
            "released_pdf_count": 0,
            "annotation_count": 1,
            "report_count": 1,
            "company_count": 1,
            "task_document_count": 1,
            "reports_without_tasks_count": 0,
            "missing_reports": [],
            "invalid_evidence_references": [],
        }
        manifests = ManifestAudit(1, 1, True)
        checks = [
            {
                "task_id": "finlongdocqa:1",
                "source_task_id": "1",
                "company": "AAA",
                "year": "2022",
                "status": "fail",
                "findings": [{"code": "bad_page"}],
                "human_signoff": False,
            }
        ]
        audit = build_phase0_audit(release, manifests, documents, tasks, checks)
        self.assertEqual(audit["status"], "blocked_before_ocr")
        codes = {item["code"] for item in audit["ocr_readiness"]["blockers"]}
        self.assertIn("source_pdfs_unavailable", codes)
        self.assertIn("manual_ground_truth_failures", codes)
        self.assertIn("researcher_signoff_pending", codes)


if __name__ == "__main__":
    unittest.main()

