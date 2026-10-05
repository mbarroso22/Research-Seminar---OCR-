import unittest

from finocr.metrics import (
    evidence_page_f1,
    normalized_edit_similarity,
    numeric_match,
    recall_at_k,
    reciprocal_rank,
)


class MetricTests(unittest.TestCase):
    def test_edit_similarity_identity(self) -> None:
        self.assertEqual(normalized_edit_similarity("Revenue 100", "revenue 100"), 1.0)

    def test_retrieval_metrics(self) -> None:
        relevant = {2, 7}
        ranking = [7, 1, 2]
        self.assertEqual(recall_at_k(relevant, ranking, 1), 0.5)
        self.assertEqual(reciprocal_rank(relevant, ranking), 1.0)
        self.assertAlmostEqual(evidence_page_f1(relevant, {2}), 2 / 3)

    def test_numeric_match(self) -> None:
        self.assertTrue(numeric_match("$1,000.00", "1005", tolerance=0.01))
        self.assertTrue(numeric_match("(125)", "-125", tolerance=0.0))
        self.assertFalse(numeric_match("1000", "1200", tolerance=0.01))


if __name__ == "__main__":
    unittest.main()

