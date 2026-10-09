import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import run_native_baseline, sha256_file
from finocr.pipelines.stopword_comparison import compare_stopwords
from finocr.retrieval.bm25 import tokenize
from finocr.retrieval.stopwords import tokenize_without_stopwords
from test_native_baseline import text_pdf


class StopwordComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        pdf = self.root / "report.pdf"
        text_pdf(pdf, ["and to have for on this is what", "Revenue (100) -12.5% in 2022", None])
        documents = self.root / "documents.jsonl"
        self.tasks = self.root / "tasks.jsonl"
        write_jsonl(documents, [{"doc_id": "report", "pdf_path": str(pdf), "source_format": "pdf",
                                "page_count": 3, "metadata": {"sha256": sha256_file(pdf)}}])
        self.task_rows = [
            {"task_id": "q", "doc_id": "report", "question": "What is this revenue and for what?",
             "evidence_pages": [1], "answers": ["NEVER_LEAK_ANSWER"],
             "metadata": {"justification": "NEVER_LEAK_JUSTIFICATION"}},
            {"task_id": "function_only", "doc_id": "report", "question": "and to",
             "evidence_pages": [0], "answers": ["NEVER_LEAK_ANSWER"]},
        ]
        write_jsonl(self.tasks, self.task_rows)
        self.baseline = self.root / "baseline"
        run_native_baseline(documents, self.tasks, self.baseline, repository_root=self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_comparison(self, name="comparison"):
        return compare_stopwords(self.baseline, self.root / name, tasks_path=self.tasks, repository_root=self.root)

    def update_artifact_hash(self, name):
        manifest_path = self.baseline / "run_manifest.json"
        manifest = read_json(manifest_path)
        path = self.baseline / name
        manifest["artifacts"][name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        write_json(manifest_path, manifest)

    def test_original_tokenizer_unchanged_and_financial_negation_terms_retained(self):
        text = "What is revenue not -12.5% in FY22 and USD millions?"
        self.assertEqual(tokenize(text), ["what", "is", "revenue", "not", "-12.5%", "in", "fy", "22", "and", "usd", "millions"])
        self.assertEqual(tokenize_without_stopwords(text), ["revenue", "not", "-12.5%", "fy", "22", "usd", "millions"])

    def test_reproduces_original_before_comparison_and_keeps_full_page_scope(self):
        before = {p.name: p.read_bytes() for p in self.baseline.iterdir() if p.is_file()}
        result = self.run_comparison()
        self.assertTrue(result["baseline_reproduced"])
        self.assertEqual(result["page_records"], 3)
        original = read_jsonl(self.baseline / "retrieval_predictions.jsonl")
        reproduced = read_jsonl(self.root / "comparison" / "baseline_reproduced_predictions.jsonl")
        variant = read_jsonl(self.root / "comparison" / "stopword_predictions.jsonl")
        for a, b in zip(original, reproduced):
            self.assertEqual(a["ranked_pages"], b["ranked_pages"])
        self.assertEqual(variant[0]["ranked_pages"][0]["page_index"], 1)
        self.assertEqual(len(variant[0]["ranked_pages"]), 3)
        self.assertTrue(variant[1]["no_match"])
        self.assertTrue(all(p["score"] == 0 for p in variant[1]["ranked_pages"]))
        for filename, data in before.items():
            self.assertEqual((self.baseline / filename).read_bytes(), data)
        metrics = read_json(self.root / "comparison" / "comparison_metrics.json")
        self.assertEqual(metrics["baseline"]["question_count"], 2)
        self.assertEqual(metrics["stopwords"]["question_count"], 2)

    def test_label_loader_called_only_after_both_predictions_are_saved(self):
        from finocr.pipelines.native_baseline import load_evidence_labels

        def check(path):
            self.assertTrue((self.root / "comparison" / "baseline_reproduced_predictions.jsonl").exists())
            self.assertTrue((self.root / "comparison" / "stopword_predictions.jsonl").exists())
            return load_evidence_labels(path)

        with patch("finocr.pipelines.stopword_comparison.load_evidence_labels", side_effect=check):
            self.run_comparison()
        for name in ("retrieval_queries.jsonl", "stopword_predictions.jsonl", "baseline_reproduced_predictions.jsonl"):
            self.assertNotIn("NEVER_LEAK", (self.root / "comparison" / name).read_text())

    def test_modified_cache_and_changed_original_tasks_are_rejected(self):
        pages_path = self.baseline / "native_pages.jsonl"
        original = pages_path.read_bytes()
        pages_path.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_comparison()
        self.assertFalse((self.root / "comparison").exists())
        pages_path.write_bytes(original)
        changed = copy.deepcopy(self.task_rows)
        changed[0]["answers"] = ["different"]
        write_jsonl(self.tasks, changed)
        with self.assertRaisesRegex(ValueError, "frozen task"):
            self.run_comparison()

    def test_incomplete_diagnostic_subset_and_failed_reproduction_are_rejected(self):
        pages_path = self.baseline / "native_pages.jsonl"
        original = pages_path.read_bytes()
        write_jsonl(pages_path, read_jsonl(pages_path)[:1])
        self.update_artifact_hash("native_pages.jsonl")
        with self.assertRaisesRegex(ValueError, "Missing, duplicated"):
            self.run_comparison("subset")
        self.assertEqual(read_json(self.root / "subset" / "run_manifest.json")["status"], "failed")
        pages_path.write_bytes(original)
        self.update_artifact_hash("native_pages.jsonl")
        prediction_path = self.baseline / "retrieval_predictions.jsonl"
        predictions = read_jsonl(prediction_path)
        predictions[0]["ranked_pages"][0]["score"] += 1
        write_jsonl(prediction_path, predictions)
        self.update_artifact_hash("retrieval_predictions.jsonl")
        with self.assertRaisesRegex(ValueError, "failed reproduction"):
            self.run_comparison("mismatch")
        self.assertFalse((self.root / "mismatch" / "comparison_metrics.json").exists())

    def test_contaminated_query_projection_and_existing_output_rejected(self):
        self.run_comparison()
        with self.assertRaises(FileExistsError):
            self.run_comparison()
        path = self.baseline / "retrieval_queries.jsonl"
        queries = read_jsonl(path)
        queries[0]["answers"] = ["injected"]
        write_jsonl(path, queries)
        self.update_artifact_hash(path.name)
        with self.assertRaisesRegex(ValueError, "three allowed fields"):
            self.run_comparison("bad_queries")

    def test_cli_comparison_produces_manifest_and_metrics(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        completed = subprocess.run([
            sys.executable, "-m", "finocr.cli", "compare-stopwords", "--baseline-dir", str(self.baseline),
            "--output-dir", str(self.root / "cli"), "--tasks", str(self.tasks), "--repository-root", str(self.root),
        ], env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["baseline_reproduced"])
        self.assertEqual(read_json(self.root / "cli" / "run_manifest.json")["status"], "complete")
        self.assertTrue((self.root / "cli" / "comparison_metrics.json").exists())


if __name__ == "__main__":
    unittest.main()
