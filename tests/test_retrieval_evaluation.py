import copy
import unittest

from finocr.evaluation.retrieval import evaluate_retrieval


class RetrievalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.labels = [
            {"task_id": "a", "doc_id": "r", "evidence_pages": [1, 3, 3]},
            {"task_id": "b", "doc_id": "r", "evidence_pages": [2]},
        ]
        self.predictions = [
            {"task_id": "a", "doc_id": "r", "page_count": 4, "status": "ok", "no_match": False,
             "ranked_pages": [{"page_index": p, "score": 4 - i} for i, p in enumerate([1, 0, 3, 2])]},
            {"task_id": "b", "doc_id": "r", "page_count": 4, "status": "document_failed", "no_match": True,
             "ranked_pages": []},
        ]

    def test_multi_evidence_metrics_are_distinct_and_failures_stay_in_denominator(self):
        result = evaluate_retrieval(self.predictions, self.labels)
        # a retrieves half its distinct evidence at 1; b fails: macro recall=.25,
        # hit=.5, all-evidence=0. At 3, a covers all, b still fails: all three=.5.
        self.assertEqual(result["at_k"]["1"]["macro_evidence_recall"], 0.25)
        self.assertEqual(result["at_k"]["1"]["any_evidence_hit_rate"], 0.5)
        self.assertEqual(result["at_k"]["1"]["all_evidence_coverage_rate"], 0)
        self.assertEqual(result["at_k"]["3"]["macro_evidence_recall"], 0.5)
        self.assertEqual(result["at_k"]["3"]["all_evidence_coverage_rate"], 0.5)
        self.assertEqual(result["mrr_full_ranking"], 0.5)
        self.assertEqual(result["question_count"], 2)
        self.assertEqual(result["failed_question_count"], 1)

    def test_zero_score_tie_hits_are_counted_and_disclosed(self):
        prediction = copy.deepcopy(self.predictions[0])
        prediction["no_match"] = True
        prediction["ranked_pages"] = [{"page_index": p, "score": 0} for p in range(4)]
        label = {"task_id": "a", "doc_id": "r", "evidence_pages": [0]}
        result = evaluate_retrieval([prediction], [label])
        self.assertEqual(result["at_k"]["1"]["any_evidence_hit_rate"], 1)
        self.assertEqual(result["no_match_question_count"], 1)
        self.assertIn("chance", result["zero_score_policy"])

    def test_mrr_uses_full_ranking_not_top_five(self):
        prediction = copy.deepcopy(self.predictions[0])
        prediction["page_count"] = 6
        prediction["ranked_pages"] = [{"page_index": p, "score": 6 - p} for p in range(6)]
        label = {"task_id": "a", "doc_id": "r", "evidence_pages": [5]}
        result = evaluate_retrieval([prediction], [label])
        self.assertEqual(result["at_k"]["5"]["macro_evidence_recall"], 0)
        self.assertAlmostEqual(result["mrr_full_ranking"], 1 / 6)

    def test_invalid_labels_candidates_and_prediction_coverage_rejected(self):
        for bad in ([], [-1], [4], [True], ["1"]):
            labels = copy.deepcopy(self.labels)
            labels[0]["evidence_pages"] = bad
            with self.assertRaises(ValueError):
                evaluate_retrieval(self.predictions, labels)
        for bad in ([1, 1], [-1], [4], [True]):
            predictions = copy.deepcopy(self.predictions)
            predictions[0]["ranked_pages"] = [{"page_index": p, "score": 1} for p in bad]
            with self.assertRaises(ValueError):
                evaluate_retrieval(predictions, self.labels)
        for predictions, labels in (
            (self.predictions[:1], self.labels), (self.predictions, self.labels[:1]),
            (self.predictions + self.predictions[:1], self.labels),
            (self.predictions, self.labels + self.labels[:1]),
        ):
            with self.assertRaises(ValueError):
                evaluate_retrieval(predictions, labels)
        for ks in ((), (0,), (1, 1), (True,)):
            with self.assertRaises(ValueError):
                evaluate_retrieval(self.predictions, self.labels, ks=ks)

    def test_wrong_page_base_truncated_rankings_and_failure_ranks_are_rejected(self):
        for field, value in (("page_index_base", 1), ("page_count", True),
                             ("status", "unknown"), ("no_match", "false")):
            predictions = copy.deepcopy(self.predictions)
            predictions[0][field] = value
            with self.assertRaises(ValueError):
                evaluate_retrieval(predictions, self.labels)
        predictions = copy.deepcopy(self.predictions)
        predictions[0]["ranked_pages"] = predictions[0]["ranked_pages"][:1]
        with self.assertRaises(ValueError):
            evaluate_retrieval(predictions, self.labels)
        predictions = copy.deepcopy(self.predictions)
        predictions[1]["ranked_pages"] = [{"page_index": 2, "score": 1}]
        with self.assertRaises(ValueError):
            evaluate_retrieval(predictions, self.labels)


if __name__ == "__main__":
    unittest.main()
