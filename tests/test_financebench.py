from __future__ import annotations

import unittest

from finocr.datasets.financebench import select_financebench_pilot


class FinanceBenchPilotTests(unittest.TestCase):
    def test_selector_uses_qa_coverage_sector_diversity_and_time_span(self) -> None:
        rows = []
        specifications = [
            ("A", "Technology", 9),
            ("B", "Technology", 8),
            ("C", "Health Care", 7),
            ("D", "Industrials", 6),
        ]
        for company, sector, qa_cases in specifications:
            for year in range(2015, 2023):
                rows.append(
                    {
                        "doc_id": f"financebench:{company}_{year}_10K",
                        "doc_name": f"{company}_{year}_10K",
                        "company": company,
                        "sector": sector,
                        "fiscal_year": year,
                        "doc_type": "10k",
                        "pdf_valid": True,
                        "page_count": 100,
                        "qa_case_count": qa_cases if year == 2022 else 0,
                    }
                )
        selected = select_financebench_pilot(rows, company_count=3)
        self.assertEqual({row["company"] for row in selected}, {"A", "C", "D"})
        for company in {"A", "C", "D"}:
            years = [row["fiscal_year"] for row in selected if row["company"] == company]
            self.assertEqual(years, [2015, 2019, 2022])


if __name__ == "__main__":
    unittest.main()
