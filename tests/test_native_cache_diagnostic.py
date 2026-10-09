import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import run_native_baseline, sha256_file
from finocr.pipelines.stopword_comparison import compare_query_expansion, compare_stopwords
from finocr.retrieval.bm25 import BM25Index, RetrievalQuery
from test_native_baseline import text_pdf

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "diagnose_native_cache.py"
SPEC = importlib.util.spec_from_file_location("native_cache_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


class NativeCacheScoreTests(unittest.TestCase):
    def test_term_attribution_counts_blank_pages_and_binary_query_frequency(self):
        index = BM25Index("report", [(0, "profit profit"), (1, "cash"), (2, "")])
        query = RetrievalQuery("q", "report", "profit profit cash absent")
        detail = diagnostic.term_breakdown(index, query, 0, {"profit"})
        # N=3, avgdl=1, df(profit)=1 and page length=2; independent hand formula.
        expected = math.log1p(2.5 / 1.5) * 2 * 2.2 / (2 + 1.2 * 1.75)
        self.assertAlmostEqual(detail["added_score"], expected)
        self.assertEqual(detail["base_score"], 0)
        self.assertEqual(len(detail["terms"]), 3)
        self.assertAlmostEqual(detail["expanded_score"], index.rank(query)[0]["score"])
        self.assertEqual(diagnostic.term_breakdown(index, query, 2, {"profit"})["expanded_score"], 0)
        blank = BM25Index("report", [(0, ""), (1, "")])
        self.assertEqual(diagnostic.term_breakdown(blank, query, 0, set())["expanded_score"], 0)

    def test_full_order_and_scope_required_even_for_zero_ties(self):
        query = RetrievalQuery("q", "report", "missing")
        rank = BM25Index("report", [(0, ""), (1, "")]).rank(query)
        saved = {"doc_id": "report", "page_index_base": 0, "page_count": 2, "ranked_pages": rank[::-1]}
        with self.assertRaisesRegex(ValueError, "order"):
            diagnostic.check_ranking(rank, saved, query)
        saved["ranked_pages"] = rank
        saved["doc_id"] = "other"
        with self.assertRaisesRegex(ValueError, "scope"):
            diagnostic.check_ranking(rank, saved, query)


class NativeCacheDiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        pdf = self.root / "source.pdf"
        text_pdf(pdf, ["operating profit revenue 2022", "depreciation amortization cash flows 2022", None])
        documents, tasks = self.root / "documents.jsonl", self.root / "tasks.jsonl"
        write_jsonl(documents, [{"doc_id": "report", "pdf_path": str(pdf), "source_format": "pdf",
                                "page_count": 3, "metadata": {"sha256": sha256_file(pdf)}}])
        write_jsonl(tasks, [{"task_id": "q", "doc_id": "report", "question": "EBITDA in 2022",
                            "evidence_pages": [0, 1], "answers": ["LABEL_SENTINEL"],
                            "metadata": {"justification": "LABEL_SENTINEL"}}])
        self.native, stop, self.expansion = [self.root / name for name in ("native", "stop", "expansion")]
        run_native_baseline(documents, tasks, self.native, repository_root=self.root)
        compare_stopwords(self.native, stop, tasks_path=tasks, repository_root=self.root)
        compare_query_expansion(self.native, stop, self.expansion, tasks_path=tasks, repository_root=self.root)
        # Diagnostics must work without the task file, source PDF or any gold artifacts.
        tasks.unlink()
        pdf.unlink()

    def tearDown(self):
        self.temp.cleanup()

    def run_diagnostic(self):
        return diagnostic.diagnose(self.native, self.expansion, "q", [0])

    def test_reproduction_has_no_labels_and_review_pages_do_not_filter_candidates(self):
        before = {p: p.read_bytes() for d in (self.native, self.expansion) for p in d.iterdir() if p.is_file()}
        result = self.run_diagnostic()
        self.assertEqual(result["reproduced_rankings"], 3)
        self.assertEqual(result["reproduced_page_scores"], 9)
        self.assertEqual(result["trace"]["N"], 3)
        self.assertEqual(len(result["trace"]["pages"]), 1)
        self.assertEqual(len(result["trace"]["top5"]["expansion"]), 3)
        self.assertFalse(result["labels_loaded"])
        self.assertNotIn("LABEL_SENTINEL", json.dumps(result))
        self.assertEqual(before, {p: p.read_bytes() for p in before})

    def test_changed_cache_is_rejected_before_ranking(self):
        with (self.native / "native_pages.jsonl").open("a") as stream:
            stream.write("\n")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.run_diagnostic()

    def test_rehashed_query_with_label_field_still_rejected(self):
        path = self.expansion / "retrieval_queries.jsonl"
        rows = read_jsonl(path)
        rows[0]["answers"] = ["LABEL_SENTINEL"]
        write_jsonl(path, rows)
        manifest = read_json(self.expansion / "run_manifest.json")
        manifest["artifacts"][path.name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        write_json(self.expansion / "run_manifest.json", manifest)
        with self.assertRaisesRegex(ValueError, "allowlist"):
            self.run_diagnostic()

    def test_semantic_cache_validation_rejects_duplicate_pages(self):
        rows = read_jsonl(self.native / "native_pages.jsonl")
        rows[1]["page_index"] = 0
        with self.assertRaisesRegex(ValueError, "duplicate"):
            diagnostic.validate_cache(rows, read_json(self.native / "run_manifest.json"),
                                      read_json(self.native / "extraction_summary.json"))
