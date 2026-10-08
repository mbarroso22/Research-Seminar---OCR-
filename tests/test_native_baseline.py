from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from finocr.io import read_json, read_jsonl, write_jsonl
from finocr.pipelines.native_baseline import (
    NativeDocument, extract_document, load_native_documents, run_native_baseline, sha256_file,
)


def text_pdf(path: Path, pages: list[str | None], *, password: str | None = None) -> None:
    """A real embedded-text PDF fixture; no reportlab/test-only dependency needed."""
    writer = PdfWriter()
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                             NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    font_ref = writer._add_object(font)
    for text in pages:
        page = writer.add_blank_page(width=612, height=792)
        if text is None:
            continue
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})})
        stream = DecodedStreamObject()
        escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream.set_data(f"BT /F1 12 Tf 30 750 Td ({escaped}) Tj ET".encode("ascii"))
        page[NameObject("/Contents")] = writer._add_object(stream)
    if password is not None:
        writer.encrypt(password)
    with path.open("wb") as handle:
        writer.write(handle)


class NativeBaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.pdfs = self.root / "pdfs"
        self.pdfs.mkdir()
        self.source = self.pdfs / "A.pdf"
        text_pdf(self.source, ["Profit (125) -12.50% in 2022.", None, "Revenue $1,234.00 in 2022."])
        self.document = NativeDocument("financebench:A:2022", self.source, 3, sha256_file(self.source))
        self.documents = self.root / "documents.jsonl"
        self.tasks = self.root / "tasks.jsonl"
        self.document_row = {
            "doc_id": self.document.doc_id, "page_count": 3, "pdf_path": str(self.source),
            "source_format": "pdf", "metadata": {"sha256": self.document.sha256},
        }
        self.task_row = {"task_id": "q", "doc_id": self.document.doc_id, "question": "revenue",
                         "answers": ["DO_NOT_LEAK_ANSWER profit"], "evidence_pages": [2],
                         "metadata": {"justification": "DO_NOT_LEAK_JUSTIFICATION profit",
                                      "evidence_text_full_page": "DO_NOT_LEAK_EVIDENCE profit"}}
        write_jsonl(self.documents, [self.document_row])
        write_jsonl(self.tasks, [self.task_row])

    def tearDown(self):
        self.temp.cleanup()

    def run_baseline(self, name="run", **options):
        return run_native_baseline(self.documents, self.tasks, self.root / name,
                                   repository_root=self.root, **options)

    def test_real_pdf_preserves_raw_financial_text_blank_and_zero_based_ids(self):
        rows, summary = extract_document(self.document, run_id="fixture")
        self.assertEqual([row["page_index"] for row in rows], [0, 1, 2])
        self.assertEqual([row["status"] for row in rows], ["ok", "blank_native_text", "ok"])
        self.assertIn("(125) -12.50%", rows[0]["raw_text"])
        self.assertIn("$1,234.00", rows[2]["search_text"])
        self.assertEqual(rows[1]["raw_text"], "")
        self.assertEqual(summary["attempted_page_count"], 3)
        self.assertEqual(summary["observed_sha256"], self.document.sha256)

    def test_page_exception_preserves_next_page_index(self):
        from pypdf._page import PageObject
        original = PageObject.extract_text
        calls = 0

        def fail_second(page, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("fixture extraction failure")
            return original(page, *args, **kwargs)

        with patch.object(PageObject, "extract_text", fail_second):
            rows, summary = extract_document(self.document, run_id="fixture")
        self.assertEqual(rows[1]["status"], "page_failed")
        self.assertIn("fixture extraction failure", rows[1]["error"])
        self.assertEqual(rows[2]["page_index"], 2)
        self.assertIn("Revenue", rows[2]["raw_text"])
        self.assertEqual(summary["status"], "partial_extraction")

    def test_checksum_count_missing_and_corrupt_pdf_get_expected_failure_rows(self):
        corrupt = self.pdfs / "corrupt.pdf"
        corrupt.write_bytes(b"not a PDF")
        cases = [
            NativeDocument("hash", self.source, 3, "0" * 64),
            NativeDocument("count", self.source, 4, self.document.sha256),
            NativeDocument("missing", self.pdfs / "missing.pdf", 2, "0" * 64),
            NativeDocument("corrupt", corrupt, 2, sha256_file(corrupt)),
        ]
        for document in cases:
            with self.subTest(document.doc_id):
                rows, summary = extract_document(document, run_id="fixture")
                self.assertEqual(len(rows), document.page_count)
                self.assertTrue(all(row["status"] == "document_failed" for row in rows))
                self.assertFalse(any(row["extraction_attempted"] for row in rows))
                self.assertEqual(summary["status"], "document_failed")
        self.assertEqual(extract_document(cases[1], run_id="fixture")[1]["observed_page_count"], 3)

    def test_empty_password_encryption_and_dependency_failure_are_explicit(self):
        encrypted = self.pdfs / "encrypted.pdf"
        text_pdf(encrypted, ["Revenue"], password="")
        document = NativeDocument("encrypted", encrypted, 1, sha256_file(encrypted))
        rows, _ = extract_document(document, run_id="fixture")
        self.assertEqual(rows[0]["status"], "ok")
        text_pdf(encrypted, ["Revenue"], password="secret")
        document = NativeDocument("locked", encrypted, 1, sha256_file(encrypted))
        rows, _ = extract_document(document, run_id="fixture")
        self.assertIn("encrypted_pdf", rows[0]["error"])
        with patch.object(PdfReader, "decrypt", side_effect=ImportError("cryptography missing")):
            rows, _ = extract_document(document, run_id="fixture")
        self.assertIn("cryptography missing", rows[0]["error"])

    def test_source_change_during_extraction_rejects_extracted_content(self):
        with patch("finocr.pipelines.native_baseline.sha256_file",
                   side_effect=[self.document.sha256, "f" * 64]):
            rows, summary = extract_document(self.document, run_id="fixture")
        self.assertIn("source_changed", summary["error"])
        self.assertTrue(all(row["raw_text"] == "" for row in rows))
        self.assertEqual(summary["attempted_page_count"], 3)
        self.assertEqual(summary["post_extraction_sha256"], "f" * 64)

    def test_windows_path_rebasing_keeps_doc_ids_and_checksums(self):
        row = copy.deepcopy(self.document_row)
        row["pdf_path"] = r"C:\Users\someone\data\A.pdf"
        write_jsonl(self.documents, [row])
        docs = load_native_documents(self.documents, repository_root=self.root, pdf_dir=self.pdfs)
        self.assertEqual(docs[0], self.document)

    def test_all_reports_extracted_but_retrieval_stays_inside_query_report(self):
        other = self.pdfs / "B.pdf"
        text_pdf(other, ["revenue revenue revenue"])
        row = {"doc_id": "B", "page_count": 1, "pdf_path": str(other), "source_format": "pdf",
               "metadata": {"sha256": sha256_file(other)}}
        write_jsonl(self.documents, [self.document_row, row])
        result = self.run_baseline(expected_documents=2, expected_pages=4, expected_questions=1)
        self.assertEqual(result["page_records"], 4)
        pages = read_jsonl(self.root / "run" / "native_pages.jsonl")
        self.assertEqual({page["doc_id"] for page in pages}, {self.document.doc_id, "B"})
        prediction = read_jsonl(self.root / "run" / "retrieval_predictions.jsonl")[0]
        self.assertEqual(prediction["doc_id"], self.document.doc_id)
        self.assertEqual(prediction["ranked_pages"][0]["page_index"], 2)
        self.assertEqual(len(prediction["ranked_pages"]), 3)

    def test_labels_cannot_change_queries_native_text_or_predictions(self):
        self.run_baseline("first")
        changed = copy.deepcopy(self.task_row)
        changed["answers"] = ["different answer"]
        changed["evidence_pages"] = [0]
        changed["metadata"] = {"justification": "revenue", "evidence_text": "revenue"}
        write_jsonl(self.tasks, [changed])
        self.run_baseline("second")
        for name in ("first", "second"):
            queries = read_jsonl(self.root / name / "retrieval_queries.jsonl")
            self.assertEqual(queries, [{"task_id": "q", "doc_id": self.document.doc_id, "question": "revenue"}])
            for file in ("native_pages.jsonl", "retrieval_queries.jsonl", "retrieval_predictions.jsonl"):
                self.assertNotIn("DO_NOT_LEAK", (self.root / name / file).read_text())
        first = read_jsonl(self.root / "first" / "retrieval_predictions.jsonl")[0]
        second = read_jsonl(self.root / "second" / "retrieval_predictions.jsonl")[0]
        self.assertEqual(first["ranked_pages"], second["ranked_pages"])
        self.assertEqual(read_json(self.root / "first" / "retrieval_metrics.json")["at_k"]["1"]["macro_evidence_recall"], 1)
        self.assertEqual(read_json(self.root / "second" / "retrieval_metrics.json")["at_k"]["1"]["macro_evidence_recall"], 0)

    def test_evaluator_is_called_after_predictions_are_saved(self):
        from finocr.evaluation.retrieval import evaluate_retrieval

        def check(predictions, labels, **kwargs):
            self.assertTrue((self.root / "run" / "retrieval_predictions.jsonl").exists())
            return evaluate_retrieval(predictions, labels, **kwargs)

        with patch("finocr.pipelines.native_baseline.evaluate_retrieval", side_effect=check):
            self.run_baseline()

    def test_failure_query_remains_and_zero_overlap_ties_are_flagged(self):
        row = copy.deepcopy(self.document_row)
        row["metadata"]["sha256"] = "0" * 64
        write_jsonl(self.documents, [row])
        result = self.run_baseline("failed")
        self.assertEqual(result["status"], "complete_with_failures")
        prediction = read_jsonl(self.root / "failed" / "retrieval_predictions.jsonl")[0]
        self.assertEqual(prediction["status"], "document_failed")
        self.assertEqual(prediction["ranked_pages"], [])
        self.assertEqual(read_json(self.root / "failed" / "retrieval_metrics.json")["at_k"]["5"]["macro_evidence_recall"], 0)
        write_jsonl(self.documents, [self.document_row])
        row = copy.deepcopy(self.task_row)
        row["question"] = "unseenqueryword"
        write_jsonl(self.tasks, [row])
        self.run_baseline("no_match")
        prediction = read_jsonl(self.root / "no_match" / "retrieval_predictions.jsonl")[0]
        self.assertTrue(prediction["no_match"])
        self.assertEqual([p["page_index"] for p in prediction["ranked_pages"]], [0, 1, 2])

    def test_new_run_only_expected_counts_and_frozen_input_hashes(self):
        result = self.run_baseline()
        manifest = read_json(self.root / "run" / "run_manifest.json")
        self.assertEqual(manifest["inputs"]["documents"]["sha256"], sha256_file(self.documents))
        self.assertEqual(manifest["inputs"]["tasks"]["sha256"], sha256_file(self.tasks))
        self.assertEqual(manifest["artifacts"]["native_pages.jsonl"]["sha256"],
                         sha256_file(self.root / "run" / "native_pages.jsonl"))
        self.assertEqual(manifest["configuration"]["query_fields"], ["task_id", "doc_id", "question"])
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(result["questions"], 1)
        with self.assertRaises(FileExistsError):
            self.run_baseline()
        with self.assertRaises(ValueError):
            self.run_baseline("mismatch", expected_pages=2620)
        self.assertFalse((self.root / "mismatch").exists())
        for path in (self.root / "run" / "pages").iterdir():
            self.assertNotIn(":", path.name)
            self.assertNotIn("\\", path.name)

    def test_duplicate_or_unknown_manifest_ids_and_outputs_inside_git_rejected(self):
        write_jsonl(self.documents, [self.document_row, self.document_row])
        with self.assertRaises(ValueError):
            self.run_baseline()
        write_jsonl(self.documents, [self.document_row])
        write_jsonl(self.tasks, [self.task_row, self.task_row])
        with self.assertRaises(ValueError):
            self.run_baseline()
        unknown = copy.deepcopy(self.task_row)
        unknown["doc_id"] = "missing"
        write_jsonl(self.tasks, [unknown])
        with self.assertRaises(ValueError):
            self.run_baseline()
        write_jsonl(self.tasks, [self.task_row])
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside the Git"):
            self.run_baseline()

    def test_retrieval_only_does_not_validate_or_use_evidence_labels(self):
        row = copy.deepcopy(self.task_row)
        row["evidence_pages"] = []
        write_jsonl(self.tasks, [row])
        result = self.run_baseline("query_only", skip_evaluation=True)
        self.assertEqual(result["evaluation"], "skipped")
        self.assertFalse((self.root / "query_only" / "retrieval_metrics.json").exists())
        with self.assertRaises(ValueError):
            self.run_baseline("bad_labels")
        manifest = read_json(self.root / "bad_labels" / "run_manifest.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertTrue((self.root / "bad_labels" / "retrieval_predictions.jsonl").exists())

    def test_manifest_edit_after_retrieval_blocks_scoring(self):
        original = write_jsonl

        def mutate_after_prediction(path, records):
            original(path, records)
            if Path(path).name == "retrieval_predictions.jsonl":
                self.tasks.write_text(self.tasks.read_text() + "\n", encoding="utf-8")

        with patch("finocr.pipelines.native_baseline.write_jsonl", side_effect=mutate_after_prediction):
            with self.assertRaisesRegex(ValueError, "changed after retrieval"):
                self.run_baseline()
        self.assertFalse((self.root / "run" / "retrieval_metrics.json").exists())
        self.assertEqual(read_json(self.root / "run" / "run_manifest.json")["status"], "failed")

    def test_cli_end_to_end_and_failure_exit_codes(self):
        arguments = [sys.executable, "-m", "finocr.cli", "native-baseline",
                     "--documents", str(self.documents), "--tasks", str(self.tasks),
                     "--output-dir", str(self.root / "cli"), "--repository-root", str(self.root),
                     "--expected-documents", "1", "--expected-pages", "3", "--expected-questions", "1"]
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        completed = subprocess.run(arguments, env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["page_records"], 3)
        self.assertIn("Extracting", completed.stderr)
        rerun = subprocess.run(arguments, env=env, capture_output=True, text=True)
        self.assertEqual(rerun.returncode, 2)
        self.source.unlink()
        arguments[arguments.index(str(self.root / "cli"))] = str(self.root / "cli_failed")
        failed = subprocess.run(arguments, env=env, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1, failed.stderr)
        self.assertEqual(json.loads(failed.stdout)["failed_pages"], 3)
        # Standalone scoring uses only saved predictions and offline labels.
        scoring = subprocess.run(
            [sys.executable, "-m", "finocr.cli", "evaluate-retrieval", "--predictions",
             str(self.root / "cli" / "retrieval_predictions.jsonl"), "--tasks", str(self.tasks),
             "--output", str(self.root / "rescored.json")], env=env, capture_output=True, text=True)
        self.assertEqual(scoring.returncode, 0, scoring.stderr)
        self.assertEqual(read_json(self.root / "rescored.json")["at_k"],
                         read_json(self.root / "cli" / "retrieval_metrics.json")["at_k"])

    def test_streaming_jsonl_failure_is_atomic_and_utf8_uses_lf(self):
        target = self.root / "atomic.jsonl"
        target.write_bytes(b"original\n")

        def broken_records():
            yield {"text": "caf\u00e9"}
            raise RuntimeError("fixture generator failed")

        with self.assertRaises(RuntimeError):
            write_jsonl(target, broken_records())
        self.assertEqual(target.read_bytes(), b"original\n")
        self.assertFalse(list(self.root.glob(".atomic.jsonl.*.tmp")))
        write_jsonl(target, [{"text": "caf\u00e9"}])
        self.assertIn("caf\u00e9".encode("utf-8"), target.read_bytes())
        self.assertNotIn(b"\r", target.read_bytes())


if __name__ == "__main__":
    unittest.main()
