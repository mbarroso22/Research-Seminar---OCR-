import copy
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import load_evidence_labels, run_native_baseline, sha256_file
from finocr.pipelines.section_comparison import compare_section_context
from finocr.pipelines.stopword_comparison import compare_query_expansion, compare_stopwords
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery
from finocr.retrieval.section_context import (
    HEADING_WEIGHT, MAX_HEADING_TOKENS, SourcePage, build_section_context, rank_with_section_context, section_policy_record,
)
from finocr.retrieval.stopwords import tokenize_without_stopwords
from test_native_baseline import text_pdf


class SourceSectionTests(unittest.TestCase):
    def context(self, *texts):
        return build_section_context([SourcePage("report", i, text) for i, text in enumerate(texts)])

    def test_v1_fingerprint_and_checked_in_snapshot_match(self):
        policy = section_policy_record()
        self.assertEqual(policy["sha256"], "159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e")
        self.assertEqual(policy, read_json(Path(__file__).resolve().parents[1] / "configs" / "section_context_v1.json"))

    def test_raw_unicode_offsets_and_multiple_local_scopes(self):
        text = "Table of Contents\r\n  Forward-Looking Statements\r\nSome ordinary prose.\r\nItem 1. Business.\r\nCompany Overview\r\nOur Operations\r\n1) Division North\r\n"
        result = self.context(text)[0]
        observed = result["headings"]
        self.assertEqual([h["heading_text"] for h in observed],
                         ["Forward-Looking Statements", "Item 1. Business.", "Company Overview", "Our Operations"])
        for i, heading in enumerate(observed):
            self.assertEqual(text[heading["source_start"]:heading["source_end"]], heading["heading_text"])
            self.assertEqual(heading["scope_end"], observed[i + 1]["source_start"] if i + 1 < len(observed) else len(text))
        # A raw Unicode apostrophe changes bytes but offsets still refer to characters.
        other = self.context("\u2019\nConsolidated Statement of Income\n2022 2021\n")[0]["headings"][0]
        self.assertEqual(other["source_start"], 2)

    def test_list_continuation_ends_at_first_local_heading_and_does_not_chain(self):
        first = "Our Operations\n1) Northern division;\n2) Southern division;"
        second = "Table of Contents\n3) Western division;\nRegional Brands\nOur brand products include foods."
        rows = self.context(first, second, "Ordinary continuation prose.", "Further prose without a heading.")
        inherited = rows[1]["headings"][0]
        self.assertEqual(inherited["mode"], "inherited")
        self.assertEqual(inherited["source_page_index"], 0)
        self.assertEqual(inherited["scope_start"], len("Table of Contents\n"))
        self.assertEqual(inherited["scope_end"], second.index("Regional Brands"))
        self.assertEqual(rows[2]["headings"][0]["heading_text"], "Regional Brands")
        self.assertEqual(rows[2]["headings"][0]["source_page_index"], 1)
        self.assertEqual(rows[3]["headings"], [])

    def test_blank_navigation_signatures_and_exhibits_reset_without_removing_pages(self):
        for boundary in ("", "Table of Contents\n7\n", "SIGNATURES", "Exhibit 4.65\nDescription of Securities"):
            with self.subTest(boundary=boundary):
                rows = self.context("Our Operations", boundary, "ordinary continuation.")
                self.assertEqual(len(rows), 3)
                self.assertTrue(rows[1]["resets"])
                self.assertFalse(any(h["mode"] == "inherited" for h in rows[1]["headings"]))
                if "Description" not in boundary:
                    self.assertEqual(rows[2]["headings"], [])
                else:
                    self.assertEqual(rows[2]["headings"][0]["heading_text"], "Description of Securities")
        # Mid-page boundary stops inheritance exactly at that boundary.
        text = "ordinary opening.\nSIGNATURES\nordinary tail."
        row = self.context("Our Operations", text)[1]
        self.assertEqual(row["headings"][0]["scope_end"], text.index("SIGNATURES"))

    def test_contents_and_prose_references_are_not_current_headings(self):
        listing = "Table of Contents\n" + "\n".join(f"Item {i}. Business {i + 2}" for i in range(1, 8))
        rows = self.context("Our Operations", listing, "ordinary continuation.")
        self.assertEqual(rows[1]["heading_tokens"], [])
        self.assertEqual(rows[1]["resets"][0]["reason"], "contents_listing")
        self.assertEqual(rows[2]["headings"], [])
        text = 'Table of Contents\nSee Item 8. Financial Statements for further information.\nNet Revenue $ 86,392 $ 79,474\n(in millions)\n2022 2021'
        self.assertEqual(self.context(text)[0]["headings"], [])

    def test_statements_detected_without_item8_and_risk_heading_can_wrap(self):
        text = "Table of Contents\nConsolidated Statement of Cash Flows (continued)\n2022 2021 2020\nFinancing Activities"
        row = self.context(text)[0]
        self.assertEqual(row["headings"][0]["kind"], "statement")
        risk = "ordinary prose.\nChanges in levels of government defense spending could affect financial position and\nresults of operations.\nWe receive contracts from customers."
        heading = self.context(risk)[0]["headings"][0]
        self.assertEqual(heading["kind"], "risk_sentence")
        self.assertEqual(risk[heading["source_start"]:heading["source_end"]], heading["heading_text"])
        self.assertIn("\nresults of operations.", heading["heading_text"])
        self.assertEqual(heading["source_start"], len("ordinary prose.\n"))

    def test_complete_heading_budget_duplicate_policy_and_no_variable_inheritance(self):
        titles = ["Topic " + " ".join(["Distinct" + chr(65 + i)] * 11) for i in range(8)]
        row = self.context("\n".join(titles + [titles[0]]))[0]
        self.assertLessEqual(row["heading_token_count"], MAX_HEADING_TOKENS)
        self.assertEqual(row["heading_token_count"], 60)
        self.assertTrue(any(h["rejection_reason"] == "heading_token_cap" for h in row["headings"]))
        self.assertEqual(row["headings"][-1]["rejection_reason"], "duplicate_heading")
        rows = self.context("Our Operations\n(in USD billions)\n2022 2021", "plain continued prose.")
        self.assertNotIn("2022", rows[1]["heading_tokens"])
        self.assertNotIn("billions", rows[1]["heading_tokens"])
        self.assertNotIn("usd", rows[1]["heading_tokens"])

    def test_future_pages_and_annotation_metadata_cannot_change_earlier_context(self):
        record = {"doc_id": "report", "page_index": 0, "raw_text": "Our Operations",
                  "answers": ["NEVER_LEAK"], "evidence_pages": [0], "justification": "Cash Flow"}
        projected = SourcePage.from_record(record)
        self.assertEqual(projected, SourcePage("report", 0, "Our Operations"))
        earlier = self.context("Our Operations", "continuation prose.")
        later = self.context("Our Operations", "continuation prose.", "Consolidated Statement of Income")
        self.assertEqual(earlier, later[:2])
        with self.assertRaises(TypeError):
            build_section_context([record])
        with self.assertRaises(ValueError):
            build_section_context([SourcePage("one", 0, "heading"), SourcePage("two", 1, "heading")])

    def test_field_fusion_hand_formula_and_body_statistics_unchanged(self):
        body = BM25Index("report", [(0, "profit profit"), (1, "cash"), (2, "")])
        heads = BM25Index("report", [(0, ""), (1, "profit"), (2, "")])
        before = copy.deepcopy((body.counts, body.df, body.lengths, body.avgdl))
        ranked = rank_with_section_context(body, heads, RetrievalQuery("q", "report", "profit profit"))
        page1 = next(r for r in ranked if r["page_index"] == 1)
        # Heading N=3, df=1, avgdl=1/3, dl=1, norm=2.5.
        expected = HEADING_WEIGHT * math.log1p(2.5 / 1.5) * 2.2 / (1 + 1.2 * 2.5)
        self.assertAlmostEqual(page1["score"], expected)
        self.assertEqual(page1["body_score"], 0)
        self.assertEqual(before, (body.counts, body.df, body.lengths, body.avgdl))
        self.assertEqual({r["page_index"] for r in ranked}, {0, 1, 2})
        zero = rank_with_section_context(body, heads, RetrievalQuery("q", "report", "missing"))
        self.assertEqual([r["page_index"] for r in zero], [0, 1, 2])
        with self.assertRaises(ValueError):
            rank_with_section_context(body, BM25Index("report", [(0, "profit")]), RetrievalQuery("q", "report", "profit"))


class SectionComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.documents, self.tasks = self.root / "documents.jsonl", self.root / "tasks.jsonl"
        docs = []
        for name, texts in [("report", ["Our Operations\nregional operating income revenue 2022",
                            "Consolidated Statement of Cash Flows\ndepreciation amortization 2022", None,
                            "Exhibit 4.65\nDescription of Securities\ncapital shares"]),
                            ("unannotated", ["Consolidated Statement of Income\noperating profit", None])]:
            pdf = self.root / f"{name}.pdf"
            text_pdf(pdf, texts)
            docs.append({"doc_id": name, "pdf_path": str(pdf), "source_format": "pdf", "page_count": len(texts),
                         "metadata": {"sha256": sha256_file(pdf)}})
        write_jsonl(self.documents, docs)
        self.task_rows = [{"task_id": "q", "doc_id": "report", "question": "EBITDA in 2022",
                           "evidence_pages": [0, 1], "answers": ["NEVER_LEAK"],
                           "metadata": {"justification": "NEVER_LEAK", "evidence_text": "NEVER_LEAK"}},
                          {"task_id": "zero", "doc_id": "report", "question": "zqxuv", "evidence_pages": [3]}]
        write_jsonl(self.tasks, self.task_rows)
        self.native, stop, self.expansion = [self.root / n for n in ("native", "stop", "expansion")]
        self.make_controls(self.native, stop, self.expansion)

    def make_controls(self, native, stop, expansion):
        run_native_baseline(self.documents, self.tasks, native, repository_root=self.root)
        compare_stopwords(native, stop, tasks_path=self.tasks, repository_root=self.root)
        compare_query_expansion(native, stop, expansion, tasks_path=self.tasks, repository_root=self.root)

    def tearDown(self):
        self.temp.cleanup()

    def run_comparison(self, name="section", **kwargs):
        return compare_section_context(self.native, self.expansion, self.root / name,
                                       tasks_path=self.tasks, repository_root=self.root, **kwargs)

    def rehash(self, directory, name):
        path = directory / name
        manifest = read_json(directory / "run_manifest.json")
        manifest["artifacts"][name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        write_json(directory / "run_manifest.json", manifest)

    def test_full_cohort_controls_components_and_immutable_sources(self):
        before = {p: p.read_bytes() for d in (self.native, self.expansion) for p in d.rglob("*") if p.is_file()}
        result = self.run_comparison()
        self.assertTrue(result["expansion_control_reproduced"])
        contexts = read_jsonl(self.root / "section" / "section_context.jsonl")
        self.assertEqual(len(contexts), 6)
        self.assertEqual(contexts[2]["heading_tokens"], [])
        self.assertEqual(contexts[3]["resets"][0]["reason"], "exhibit_start")
        for name in ("baseline_reproduced_predictions.jsonl", "stopword_predictions.jsonl", "expanded_predictions.jsonl"):
            self.assertEqual([r["ranked_pages"] for r in read_jsonl(self.expansion / name)],
                             [r["ranked_pages"] for r in read_jsonl(self.root / "section" / name)])
        for prediction in read_jsonl(self.root / "section" / "section_predictions.jsonl"):
            self.assertEqual(len(prediction["ranked_pages"]), 4)
            self.assertEqual({r["page_index"] for r in prediction["ranked_pages"]}, {0, 1, 2, 3})
            for row in prediction["ranked_pages"]:
                self.assertEqual(row["score"], row["body_score"] + HEADING_WEIGHT * row["heading_score"])
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        manifest = read_json(self.root / "section" / "run_manifest.json")
        self.assertEqual(manifest["status"], "complete")
        self.assertEqual(manifest["configuration"]["section_policy"], section_policy_record())
        metrics = read_json(self.root / "section" / "comparison_metrics.json")
        self.assertEqual(metrics["multi_page"]["section_context"]["question_count"], 1)

    def test_labels_loaded_only_after_all_context_queries_and_predictions_saved(self):
        def check(path):
            out = self.root / "section"
            for name in ("section_predictions.jsonl", "expanded_predictions.jsonl", "stopword_predictions.jsonl",
                         "baseline_reproduced_predictions.jsonl", "section_context.jsonl", "section_context_summary.json",
                         "retrieval_queries.jsonl", "expanded_retrieval_queries.jsonl", "query_expansion_audit.jsonl"):
                self.assertTrue((out / name).exists(), name)
            return load_evidence_labels(path)
        with patch("finocr.pipelines.section_comparison.load_evidence_labels", side_effect=check):
            self.run_comparison()
        for path in (self.root / "section").glob("*.jsonl"):
            self.assertNotIn("NEVER_LEAK", path.read_text())

    def test_label_changes_cannot_change_context_or_any_rankings(self):
        self.run_comparison("first")
        changed = copy.deepcopy(self.task_rows)
        changed[0].update(answers=["gross margin 123"], evidence_pages=[3],
                          metadata={"justification": "Consolidated Statement of Income", "evidence_text": "Our Operations"})
        write_jsonl(self.tasks, changed)
        native2, stop2, expansion2 = [self.root / n for n in ("native2", "stop2", "expansion2")]
        self.make_controls(native2, stop2, expansion2)
        compare_section_context(native2, expansion2, self.root / "second", tasks_path=self.tasks, repository_root=self.root)
        for name in ("section_predictions.jsonl", "expanded_predictions.jsonl", "stopword_predictions.jsonl", "baseline_reproduced_predictions.jsonl"):
            self.assertEqual([r["ranked_pages"] for r in read_jsonl(self.root / "first" / name)],
                             [r["ranked_pages"] for r in read_jsonl(self.root / "second" / name)])
        self.assertEqual(read_jsonl(self.root / "first" / "section_context.jsonl"),
                         read_jsonl(self.root / "second" / "section_context.jsonl"))

    def test_reference_identity_and_policy_mismatch_rejected_before_labels(self):
        path = self.expansion / "run_manifest.json"
        original = read_json(path)
        for key, value in [("baseline_run_id", "wrong"), ("page_index_base", 1), ("task_sha256", "wrong")]:
            changed = copy.deepcopy(original); changed[key] = value; write_json(path, changed)
            with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
                with self.assertRaises(ValueError):
                    self.run_comparison(key)
                labels.assert_not_called()
            self.assertFalse((self.root / key).exists())
        changed = copy.deepcopy(original); changed["configuration"]["expansion_policy"]["maximum_added_terms"] = 9
        write_json(path, changed)
        with self.assertRaisesRegex(ValueError, "policy mismatch"):
            self.run_comparison("policy")

    def test_rehashed_expansion_score_error_rejects_run_before_labels(self):
        path = self.expansion / "expanded_predictions.jsonl"
        rows = read_jsonl(path); rows[0]["ranked_pages"][0]["score"] += 1; write_jsonl(path, rows)
        self.rehash(self.expansion, path.name)
        with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
            with self.assertRaisesRegex(ValueError, "ranking failed reproduction"):
                self.run_comparison()
            labels.assert_not_called()
        self.assertEqual(read_json(self.root / "section" / "run_manifest.json")["status"], "failed")
        self.assertFalse((self.root / "section" / "comparison_metrics.json").exists())

    def test_changed_cache_and_tasks_rejected(self):
        path = self.native / "native_pages.jsonl"
        data = path.read_bytes(); path.write_bytes(data + b"\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.run_comparison("cache")
        path.write_bytes(data)
        self.tasks.write_bytes(self.tasks.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "annotations changed"):
            self.run_comparison("tasks")

    def test_semantic_bad_page_ids_rejected_even_when_cache_lineage_rehashed(self):
        path = self.native / "native_pages.jsonl"
        rows = read_jsonl(path); rows[1]["page_index"] = 0; write_jsonl(path, rows)
        self.rehash(self.native, path.name)
        native = read_json(self.native / "run_manifest.json")
        ref = read_json(self.expansion / "run_manifest.json")
        ref["baseline_manifest_sha256"] = sha256_file(self.native / "run_manifest.json")
        ref["inputs"][path.name] = native["artifacts"][path.name]
        write_json(self.expansion / "run_manifest.json", ref)
        with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
            with self.assertRaisesRegex(ValueError, "duplicate"):
                self.run_comparison()
            labels.assert_not_called()

    def test_metrics_tampering_never_completes_run(self):
        path = self.expansion / "comparison_metrics.json"
        value = read_json(path); value["question_expansion"]["mrr_full_ranking"] = 999; write_json(path, value)
        self.rehash(self.expansion, path.name)
        with self.assertRaisesRegex(ValueError, "metrics failed reproduction"):
            self.run_comparison()
        self.assertEqual(read_json(self.root / "section" / "run_manifest.json")["status"], "failed")
        self.assertFalse((self.root / "section" / "comparison_metrics.json").exists())

    def test_mutation_during_context_processing_rejected_before_scoring(self):
        def mutate(message):
            path = self.expansion / "query_expansion_audit.jsonl"
            path.write_bytes(path.read_bytes() + b"\n")
        with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.run_comparison(progress=mutate)
            labels.assert_not_called()
        self.assertEqual(read_json(self.root / "section" / "run_manifest.json")["status"], "failed")

    def test_outputs_inside_repository_existing_runs_and_reused_output_rejected(self):
        self.run_comparison()
        with self.assertRaises(FileExistsError):
            self.run_comparison()
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside the Git"):
            compare_section_context(self.native, self.expansion, self.root / "inside", repository_root=self.root)
        with self.assertRaises(ValueError):
            compare_section_context(self.native, self.expansion, self.native / "nested", repository_root=self.root / "code")

    def test_cli_success_and_policy_error_exit(self):
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        command = [sys.executable, "-m", "finocr.cli", "compare-section-context", "--baseline-dir", str(self.native),
                   "--expansion-dir", str(self.expansion), "--tasks", str(self.tasks), "--repository-root", str(self.root)]
        # Fixtures are outside an actual Git checkout; choose a sibling output root.
        command[command.index("--repository-root") + 1] = str(self.root / "code")
        result = subprocess.run(command + ["--output-dir", str(self.root / "cli")], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["expansion_control_reproduced"])
        manifest = read_json(self.expansion / "run_manifest.json"); manifest["baseline_run_id"] = "wrong"
        write_json(self.expansion / "run_manifest.json", manifest)
        failed = subprocess.run(command + ["--output-dir", str(self.root / "bad_cli")], env=env, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("same complete", failed.stderr)


if __name__ == "__main__":
    unittest.main()
