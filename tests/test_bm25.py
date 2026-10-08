import math
import unittest

from finocr.retrieval.bm25 import BM25Index, RetrievalQuery, normalize_search_text, tokenize


class BM25Tests(unittest.TestCase):
    def query(self, text):
        return RetrievalQuery("q", "report", text)

    def test_matches_independently_calculated_formula_including_empty_page(self):
        index = BM25Index("report", [(0, "revenue revenue cost"), (1, "revenue"), (2, "")])
        ranking = index.rank(self.query("revenue revenue"))
        # N=3, df=2, avgdl=4/3. Repeated query words have binary frequency.
        idf = math.log(1 + 1.5 / 2.5)
        expected = {
            0: idf * 2 * 2.2 / (2 + 1.2 * (0.25 + 0.75 * 3 / (4 / 3))),
            1: idf * 1 * 2.2 / (1 + 1.2 * (0.25 + 0.75 * 1 / (4 / 3))),
            2: 0,
        }
        for row in ranking:
            self.assertAlmostEqual(row["score"], expected[row["page_index"]], places=12)
        self.assertEqual([row["page_index"] for row in ranking], [1, 0, 2])

    def test_length_normalization_and_term_frequency_saturation(self):
        index = BM25Index("report", [(0, "profit x x x x x"), (1, "profit"), (2, "profit profit")])
        scores = {row["page_index"]: row["score"] for row in index.rank(self.query("profit"))}
        self.assertGreater(scores[1], scores[0])
        self.assertGreater(scores[2], scores[1])
        self.assertLess(scores[2], 2 * scores[1])

    def test_ties_and_no_overlap_keep_every_page_in_zero_based_order(self):
        index = BM25Index("report", [(3, "cost"), (0, ""), (2, "cost"), (1, "")])
        self.assertEqual([row["page_index"] for row in index.rank(self.query("cost"))], [2, 3, 0, 1])
        rows = index.rank(self.query("unseen"))
        self.assertEqual([row["page_index"] for row in rows], [0, 1, 2, 3])
        self.assertTrue(all(row["score"] == 0 for row in rows))

    def test_unicode_financial_text_normalization_and_token_contract(self):
        raw = "\ufb01nancial\u00a0loss\n\u221212.50% ($1,234.00) 2022 Café"
        normalized = normalize_search_text(raw)
        self.assertEqual(normalized, "financial loss -12.50% ($1,234.00) 2022 Café")
        self.assertEqual(tokenize(raw), ["financial", "loss", "-12.50%", "1,234.00", "2022", "café"])

    def test_query_projection_never_retains_labels_and_raw_tasks_are_rejected(self):
        record = {"task_id": "q", "doc_id": "report", "question": "cost",
                  "answers": ["profit"], "evidence_pages": [0],
                  "metadata": {"justification": "profit", "evidence_text": "profit"}}
        query = RetrievalQuery.from_record(record)
        self.assertEqual(query.to_dict(), {"task_id": "q", "doc_id": "report", "question": "cost"})
        index = BM25Index("report", [(0, "profit"), (1, "cost")])
        self.assertEqual(index.rank(query)[0]["page_index"], 1)
        with self.assertRaises(TypeError):
            index.rank(record)
        with self.assertRaises(ValueError):
            index.rank(RetrievalQuery("q", "other_report", "cost"))

    def test_bad_indices_parameters_and_empty_question_rejected(self):
        for pages in ([(0, "a"), (0, "b")], [(-1, "a")], [(True, "a")]):
            with self.assertRaises(ValueError):
                BM25Index("report", pages)
        for parameters in ({"k1": 0}, {"k1": float("nan")}, {"b": 1.1}, {"b": float("inf")}):
            with self.assertRaises(ValueError):
                BM25Index("report", [], **parameters)
        with self.assertRaises(ValueError):
            RetrievalQuery.from_record({"task_id": "q", "doc_id": "r", "question": " "})


if __name__ == "__main__":
    unittest.main()
