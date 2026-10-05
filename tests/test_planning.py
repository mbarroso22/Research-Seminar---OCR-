import unittest

from finocr.pipelines.planning import build_page_windows
from finocr.schemas import DocumentRecord


class PlanningTests(unittest.TestCase):
    def test_windows_are_in_range_and_deterministic(self) -> None:
        document = DocumentRecord(
            doc_id="doc",
            dataset="test",
            pdf_path="missing.pdf",
            split="dev",
            page_count=12,
        )
        first = build_page_windows(document, [1, 5, 20], windows_per_size=3, seed=9)
        second = build_page_windows(document, [1, 5, 20], windows_per_size=3, seed=9)
        self.assertEqual(first, second)
        self.assertTrue(all(0 <= item.start_page < item.end_page <= 12 for item in first))
        self.assertTrue(any(item.page_count == 12 for item in first))


if __name__ == "__main__":
    unittest.main()

