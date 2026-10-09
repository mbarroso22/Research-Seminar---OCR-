import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import load_evidence_labels, run_native_baseline, sha256_file
from finocr.pipelines.stopword_comparison import compare_query_expansion, compare_stopwords
from finocr.retrieval.bm25 import RetrievalQuery, tokenize
from finocr.retrieval.query_expansion import RULES, expand_query, policy_record
from finocr.retrieval.stopwords import tokenize_without_stopwords
from test_native_baseline import text_pdf


class QueryExpansionRuleTests(unittest.TestCase):
    def expand(self, text):
        return expand_query(RetrievalQuery("task", "report", text))

    def test_fixed_terms_preserve_original_numbers_negation_and_wording(self):
        original = "Is the QUICK ratio not -12.5% in FY2022?"
        query, audit = self.expand(original)
        self.assertTrue(query.question.startswith(original + " "))
        self.assertEqual(audit["matched_rule_ids"], ["quick_ratio"])
        self.assertIn("receivable", audit["added_terms"])
        self.assertIn("liabilities", audit["added_terms"])
        self.assertIn("-12.5%", tokenize(query.question))
        self.assertIn("2022", tokenize(query.question))
        self.assertIn("not", tokenize(query.question))
        self.assertFalse(any(any(c.isdigit() for c in t) for t in audit["added_terms"]))

    def test_matching_uses_original_token_boundaries_and_hyphenation(self):
        for text, expected in [("acid-test ratio", "quick_ratio"), ("D&A margin", "depreciation_amortization"),
                               ("gross profit margins", "gross_margin"), ("return on assets", "return_on_assets")]:
            with self.subTest(text=text):
                self.assertIn(expected, self.expand(text)[1]["matched_rule_ids"])
        self.assertEqual(self.expand("EBITDAish and quickness ratio")[1]["matched_rule_ids"], [])

    def test_unmatched_question_is_exact_identity_and_expansion_is_not_recursive(self):
        original = "What were major acquisitions in 2023?"
        query, audit = self.expand(original)
        self.assertEqual(query.question, original)
        self.assertEqual(audit["added_terms"], [])
        # EBITDA adds depreciation/amortization, but never triggers the D&A rule.
        query, audit = self.expand("EBITDA")
        self.assertEqual(audit["matched_rule_ids"], ["ebitda"])
        self.assertNotIn("flows", audit["added_terms"])

    def test_multiple_rules_union_deduplicates_and_has_fixed_cap(self):
        original = "quick ratio current ratio gross margin operating margin net margin EBITDA EBIT capex D&A ROA ROE debt equity"
        query, audit = self.expand(original)
        self.assertEqual(len(audit["matched_rule_ids"]), len(RULES))
        self.assertEqual(audit["added_terms"], sorted(set(audit["added_terms"])))
        self.assertTrue(set(audit["added_terms"]).isdisjoint(tokenize_without_stopwords(original)))
        self.assertEqual(len(audit["added_terms"]), 32)
        self.assertGreater(audit["discarded_term_count"], 0)
        self.assertEqual(query.task_id, "task")
        self.assertEqual(query.doc_id, "report")

    def test_minimal_input_type_and_policy_hash(self):
        with self.assertRaises(TypeError):
            expand_query({"question": "quick ratio", "answers": ["leak"]})
        policy = policy_record()
        checksum = policy.pop("sha256")
        expected = hashlib.sha256(json.dumps(policy, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        self.assertEqual(checksum, expected)


class QueryExpansionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.documents = self.root / "documents.jsonl"
        self.tasks = self.root / "tasks.jsonl"
        rows = []
        for name, texts in [("report", ["quick ratio explanation and details", "2022 cash equivalents short term investments accounts receivable current liabilities", "revenue depreciation amortization", None]),
                            ("unannotated", ["other report cash", None])]:
            pdf = self.root / (name + ".pdf")
            text_pdf(pdf, texts)
            rows.append({"doc_id": name, "pdf_path": str(pdf), "source_format": "pdf", "page_count": len(texts),
                         "metadata": {"sha256": sha256_file(pdf)}})
        write_jsonl(self.documents, rows)
        self.task_rows = [
            {"task_id": "ratio", "doc_id": "report", "question": "What is the quick ratio in FY2022?", "evidence_pages": [1, 2],
             "answers": ["NEVER_LEAK_ANSWER"], "metadata": {"justification": "NEVER_LEAK_JUSTIFICATION"}},
            {"task_id": "plain", "doc_id": "report", "question": "revenue", "evidence_pages": [2],
             "metadata": {"evidence_text": "gross margin NEVER_LEAK_EVIDENCE"}},
            {"task_id": "no_match", "doc_id": "report", "question": "zqxv", "evidence_pages": [0]},
        ]
        write_jsonl(self.tasks, self.task_rows)
        self.baseline = self.root / "baseline"
        self.stopwords = self.root / "stopwords"
        run_native_baseline(self.documents, self.tasks, self.baseline, repository_root=self.root)
        compare_stopwords(self.baseline, self.stopwords, tasks_path=self.tasks, repository_root=self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_comparison(self, name="expansion"):
        return compare_query_expansion(self.baseline, self.stopwords, self.root / name,
                                       tasks_path=self.tasks, repository_root=self.root)

    def rehash(self, directory, name):
        manifest = read_json(directory / "run_manifest.json")
        path = directory / name
        manifest["artifacts"][name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        write_json(directory / "run_manifest.json", manifest)

    def test_three_conditions_share_scope_and_only_question_terms_change(self):
        before = {str(p): p.read_bytes() for d in (self.baseline, self.stopwords) for p in d.rglob("*") if p.is_file()}
        result = self.run_comparison()
        self.assertTrue(result["stopword_baseline_reproduced"])
        self.assertEqual((result["documents"], result["page_records"], result["questions"]), (2, 6, 3))
        self.assertEqual(result["transformed_questions"], 1)
        out = self.root / "expansion"
        for previous, new in [(self.baseline / "retrieval_predictions.jsonl", out / "baseline_reproduced_predictions.jsonl"),
                              (self.stopwords / "stopword_predictions.jsonl", out / "stopword_predictions.jsonl")]:
            self.assertEqual([r["ranked_pages"] for r in read_jsonl(previous)], [r["ranked_pages"] for r in read_jsonl(new)])
        stop = read_jsonl(out / "stopword_predictions.jsonl")
        expanded = read_jsonl(out / "expanded_predictions.jsonl")
        self.assertEqual(expanded[0]["ranked_pages"][0]["page_index"], 1)
        self.assertEqual(expanded[1]["ranked_pages"], stop[1]["ranked_pages"])
        self.assertTrue(expanded[2]["no_match"])
        for row in expanded:
            self.assertEqual(row["page_index_base"], 0)
            self.assertEqual({p["page_index"] for p in row["ranked_pages"]}, set(range(4)))
        queries = read_jsonl(out / "expanded_retrieval_queries.jsonl")
        self.assertTrue(all(set(q) == {"task_id", "doc_id", "question"} for q in queries))
        self.assertEqual(read_jsonl(out / "query_expansion_audit.jsonl")[1]["matched_rule_ids"], [])
        metrics = read_json(out / "comparison_metrics.json")
        self.assertEqual(set(metrics["delta_at_k"]), {"baseline", "stopwords"})
        self.assertEqual(metrics["question_expansion"]["question_count"], 3)
        self.assertEqual(metrics["question_expansion"]["no_match_question_count"], 1)
        manifest = read_json(out / "run_manifest.json")
        self.assertTrue(manifest["configuration"]["query_expansion"])
        self.assertEqual(manifest["configuration"]["expansion_policy"], policy_record())
        self.assertEqual(manifest["indexing_seconds"]["question_expansion_incremental"], 0)
        for path, content in before.items():
            self.assertEqual(Path(path).read_bytes(), content)

    def test_annotations_are_loaded_after_all_predictions_and_no_gold_leaks(self):
        def check(path):
            out = self.root / "expansion"
            for name in ("baseline_reproduced_predictions.jsonl", "stopword_predictions.jsonl", "expanded_predictions.jsonl"):
                self.assertTrue((out / name).exists())
            return load_evidence_labels(path)
        with patch("finocr.pipelines.stopword_comparison.load_evidence_labels", side_effect=check):
            self.run_comparison()
        for file in (self.root / "expansion").glob("*.jsonl"):
            self.assertNotIn("NEVER_LEAK", file.read_text())

    def test_different_answers_justifications_and_evidence_do_not_change_rankings(self):
        self.run_comparison("first")
        changed = copy.deepcopy(self.task_rows)
        changed[0]["answers"] = ["gross margin 12345"]
        changed[0]["metadata"]["justification"] = "capital expenditure should not trigger a rule"
        changed[0]["evidence_pages"] = [0]
        write_jsonl(self.tasks, changed)
        base2, stop2 = self.root / "base2", self.root / "stop2"
        run_native_baseline(self.documents, self.tasks, base2, repository_root=self.root)
        compare_stopwords(base2, stop2, tasks_path=self.tasks, repository_root=self.root)
        compare_query_expansion(base2, stop2, self.root / "second", tasks_path=self.tasks, repository_root=self.root)
        for name in ("baseline_reproduced_predictions.jsonl", "stopword_predictions.jsonl", "expanded_predictions.jsonl"):
            first = read_jsonl(self.root / "first" / name)
            second = read_jsonl(self.root / "second" / name)
            self.assertEqual([r["ranked_pages"] for r in first], [r["ranked_pages"] for r in second])
        self.assertEqual(read_jsonl(self.root / "first" / "query_expansion_audit.jsonl"),
                         read_jsonl(self.root / "second" / "query_expansion_audit.jsonl"))

    def test_wrong_reference_identity_policy_or_checksum_is_rejected(self):
        path = self.stopwords / "run_manifest.json"
        original = read_json(path)
        mutations = [("baseline_run_id", "wrong"), ("baseline_manifest_sha256", "wrong"),
                     ("page_index_base", 1), ("task_sha256", "wrong")]
        for key, value in mutations:
            with self.subTest(key=key):
                changed = copy.deepcopy(original); changed[key] = value; write_json(path, changed)
                with self.assertRaisesRegex(ValueError, "same frozen"):
                    self.run_comparison(key)
                self.assertFalse((self.root / key).exists())
        changed = copy.deepcopy(original); changed["configuration"]["k1"] = 9; write_json(path, changed)
        with self.assertRaisesRegex(ValueError, "same frozen"):
            self.run_comparison("policy")
        write_json(path, original)
        predictions = self.stopwords / "stopword_predictions.jsonl"
        predictions.write_bytes(predictions.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_comparison("checksum")

    def test_stopword_score_mismatch_even_with_updated_hash_fails_before_labels(self):
        path = self.stopwords / "stopword_predictions.jsonl"
        rows = read_jsonl(path); rows[0]["ranked_pages"][0]["score"] += 1; write_jsonl(path, rows)
        self.rehash(self.stopwords, path.name)
        with patch("finocr.pipelines.stopword_comparison.load_evidence_labels") as labels:
            with self.assertRaisesRegex(ValueError, "Stopword baseline ranking failed reproduction"):
                self.run_comparison()
            labels.assert_not_called()
        self.assertEqual(read_json(self.root / "expansion" / "run_manifest.json")["status"], "failed")
        self.assertFalse((self.root / "expansion" / "comparison_metrics.json").exists())

    def test_incomplete_cache_and_contaminated_queries_rejected(self):
        path = self.baseline / "native_pages.jsonl"
        data = path.read_bytes(); path.write_bytes(data + b"\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            self.run_comparison("cache")
        path.write_bytes(data)
        path = self.baseline / "retrieval_queries.jsonl"
        queries = read_jsonl(path); queries[0]["evidence_pages"] = [1]; write_jsonl(path, queries)
        self.rehash(self.baseline, path.name)
        with self.assertRaisesRegex(ValueError, "three allowed fields"):
            self.run_comparison("query")

    def test_reference_metrics_tamper_cannot_be_reported_as_success(self):
        path = self.stopwords / "comparison_metrics.json"
        metrics = read_json(path); metrics["stopwords"]["mrr_full_ranking"] = 999; write_json(path, metrics)
        self.rehash(self.stopwords, path.name)
        with self.assertRaisesRegex(ValueError, "metrics do not reproduce"):
            self.run_comparison()
        self.assertFalse((self.root / "expansion" / "comparison_metrics.json").exists())

    def test_reference_mutation_during_run_rejected_and_no_completed_manifest(self):
        def mutate(path):
            labels = load_evidence_labels(path)
            artifact = self.stopwords / "comparison_metrics.json"
            artifact.write_bytes(artifact.read_bytes() + b"\n")
            return labels
        with patch("finocr.pipelines.stopword_comparison.load_evidence_labels", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "reference artifact changed during"):
                self.run_comparison()
        self.assertEqual(read_json(self.root / "expansion" / "run_manifest.json")["status"], "failed")

    def test_existing_output_and_repository_output_rejected(self):
        self.run_comparison()
        with self.assertRaises(FileExistsError):
            self.run_comparison()
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside the Git"):
            self.run_comparison("inside")

    def test_cli_round_trip_and_mismatched_reference_exit(self):
        env = os.environ.copy(); env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
        command = [sys.executable, "-m", "finocr.cli", "compare-query-expansion", "--baseline-dir", str(self.baseline),
                   "--stopword-dir", str(self.stopwords), "--tasks", str(self.tasks), "--repository-root", str(self.root)]
        completed = subprocess.run(command + ["--output-dir", str(self.root / "cli")], env=env, capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["stopword_baseline_reproduced"])
        manifest = read_json(self.stopwords / "run_manifest.json"); manifest["baseline_run_id"] = "wrong"
        write_json(self.stopwords / "run_manifest.json", manifest)
        failed = subprocess.run(command + ["--output-dir", str(self.root / "bad_cli")], env=env, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("same frozen", failed.stderr)


if __name__ == "__main__":
    unittest.main()
