from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfWriter

from finocr.cli import main
from finocr.datasets.financebench import FinanceBenchError, select_financebench_pilot
from finocr.datasets.validation import validate_manifests
from finocr.io import write_jsonl
from finocr.schemas import DocumentRecord, TaskRecord


class FinanceBenchAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.pdfs = self.root / "pdfs"
        self.pdfs.mkdir()
        self.metadata = self.root / "metadata.jsonl"
        self.questions = self.root / "questions.jsonl"
        self.rows = []
        sectors = ["Technology", "Health Care", "Industrials", "Utilities"]
        for company, sector in zip("ABCD", sectors):
            for year in range(2015, 2023):
                name = f"{company}_{year}_10K"
                writer = PdfWriter()
                writer.add_blank_page(width=100, height=100)
                with (self.pdfs / f"{name}.pdf").open("wb") as output:
                    writer.write(output)
                self.rows.append({"doc_name": name, "company": company, "doc_period": year,
                                  "doc_type": "10k", "company_sector_gics": sector})
        write_jsonl(self.metadata, self.rows)
        self.qa = [{"financebench_id": f"q{company}", "doc_name": f"{company}_2022_10K",
                    "question": "What is revenue?", "answer": "$10 million",
                    "evidence": [{"evidence_page_num": 0, "evidence_doc_name": f"{company}_2022_10K"}]}
                   for company in "ABCD"]

    def run_audit(self, questions: list[dict] | None = None, extra: list[str] | None = None) -> tuple[int, dict]:
        write_jsonl(self.questions, self.qa if questions is None else questions)
        output = self.root / "audit"
        arguments = ["audit-financebench", "--metadata", str(self.metadata), "--questions", str(self.questions),
                     "--pdf-dir", str(self.pdfs), "--output-dir", str(output), *(extra or [])]
        with contextlib.redirect_stdout(io.StringIO()):
            result = main(arguments)
        self.assertTrue((output / "document_inventory.csv").is_file())
        self.assertTrue((output / "AUDIT_REPORT.md").is_file())
        return result, json.loads((output / "audit.json").read_text(encoding="utf-8"))

    def test_valid_inputs_preserve_zero_based_pages_and_counts(self) -> None:
        result, audit = self.run_audit()
        self.assertEqual(result, 0)
        self.assertEqual(audit["status"], "ready_for_native_text_baseline")
        self.assertEqual(audit["source_questions"], audit["questions"])
        self.assertEqual(audit["pilot"]["document_count"], 12)
        self.assertEqual(len(audit["pilot"]["sectors"]), 4)
        tasks = [json.loads(line) for line in (self.root / "audit/manifests/tasks.jsonl").read_text().splitlines()]
        self.assertTrue(all(task["evidence_pages"] == [0] for task in tasks))

    def test_official_gics_sector_field_is_used(self) -> None:
        for row in self.rows:
            row["gics_sector"] = row.pop("company_sector_gics")
        write_jsonl(self.metadata, self.rows)
        result, audit = self.run_audit()
        self.assertEqual(result, 0)
        self.assertEqual(set(audit["pilot"]["sectors"]),
                         {"Technology", "Health Care", "Industrials", "Utilities"})
        self.assertNotIn("limited_sector_coverage",
                         {warning["code"] for warning in audit["pilot"]["warnings"]})

    def test_cross_document_evidence_blocks_readiness(self) -> None:
        self.qa[0]["evidence"][0]["evidence_doc_name"] = "A_2021_10K"
        result, audit = self.run_audit()
        self.assertEqual(result, 1)
        self.assertIn("cross_document_evidence", audit["issue_counts"])

    def test_unknown_document_cannot_silently_drop_question(self) -> None:
        self.qa[0]["doc_name"] = "unknown"
        result, audit = self.run_audit()
        self.assertEqual(result, 1)
        self.assertEqual(audit["source_questions"], 4)
        self.assertEqual(audit["questions"], 3)
        self.assertIn("question_count_mismatch", audit["issue_counts"])

    def test_malformed_evidence_is_reported_not_discarded(self) -> None:
        for evidence in ([{"evidence_page_num": "999"}], [{"evidence_page_num": True}], [], [None]):
            with self.subTest(evidence=evidence):
                self.qa[0]["evidence"] = evidence
                result, audit = self.run_audit()
                self.assertEqual(result, 1)
                self.assertIn("invalid_question_schema", audit["issue_counts"])

    def test_out_of_range_evidence_blocks_readiness(self) -> None:
        self.qa[0]["evidence"][0]["evidence_page_num"] = 1
        result, audit = self.run_audit()
        self.assertEqual(result, 1)
        self.assertEqual(audit["evidence_page_errors"], 1)

    def test_selection_failure_preserves_inventory_and_diagnostics(self) -> None:
        result, audit = self.run_audit(extra=["--company-count", "5"])
        self.assertEqual(result, 1)
        self.assertEqual(audit["pilot"]["errors"][0]["code"], "pilot_selection_failed")
        self.assertEqual(audit["documents"], 32)

    def test_empty_questions_blocks_readiness(self) -> None:
        result, audit = self.run_audit(questions=[])
        self.assertEqual(result, 1)
        self.assertIn("empty_questions", audit["issue_counts"])
        self.assertEqual(audit["pilot"]["errors"][0]["code"], "pilot_has_no_questions")

    def test_duplicate_ids_block_even_before_manifest_validation(self) -> None:
        self.qa[1]["financebench_id"] = self.qa[0]["financebench_id"]
        result, audit = self.run_audit()
        self.assertEqual(result, 1)
        self.assertIn("duplicate_source_question_id", audit["issue_counts"])

    def test_sector_fallback_is_disclosed(self) -> None:
        for row in self.rows:
            row["company_sector_gics"] = "Technology"
        write_jsonl(self.metadata, self.rows)
        result, audit = self.run_audit()
        self.assertEqual(result, 0)
        codes = {warning["code"] for warning in audit["pilot"]["warnings"]}
        self.assertIn("limited_sector_coverage", codes)

    def test_bad_document_metadata_is_reported(self) -> None:
        self.rows[0]["doc_period"] = None
        write_jsonl(self.metadata, self.rows)
        result, audit = self.run_audit()
        self.assertEqual(result, 1)
        self.assertIn("invalid_document_metadata", audit["issue_counts"])

    def test_selector_accepts_one_report_and_rejects_bad_counts(self) -> None:
        inventory = [dict(row, doc_id=row["doc_name"], fiscal_year=row["doc_period"], sector="Technology",
                          pdf_valid=True, qa_case_count=1) for row in self.rows]
        selected = select_financebench_pilot(inventory, reports_per_company=1)
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(row["fiscal_year"] == 2019 for row in selected))
        for kwargs in ({"reports_per_company": 0}, {"company_count": 0}, {"minimum_years": 0}):
            with self.assertRaises(FinanceBenchError):
                select_financebench_pilot(inventory, **kwargs)

    def test_generic_validation_rejects_empty_evidence_and_blank_answer(self) -> None:
        document = DocumentRecord("doc", "financebench", "example.pdf", "test", 1, source_format="pdf")
        task = TaskRecord("question", "doc", "question_answering", question="Revenue?", answers=[" "])
        audit = validate_manifests([document], [task])
        self.assertFalse(audit.valid)
        self.assertEqual({issue["code"] for issue in audit.errors}, {"empty_answers", "empty_evidence_pages"})


if __name__ == "__main__":
    unittest.main()
