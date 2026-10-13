import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.evaluation.retrieval import evaluate_retrieval
from finocr.pipelines.native_baseline import load_evidence_labels, run_native_baseline, sha256_file
from finocr.pipelines.note_comparison import compare_note_formats, paired_comparisons
from finocr.pipelines.section_comparison import compare_section_context
from finocr.pipelines.stopword_comparison import compare_query_expansion, compare_stopwords
from finocr.retrieval.note_context import build_note_context, note_policy_record
from finocr.retrieval.section_context import SourcePage, build_section_context, section_policy_record
from test_native_baseline import text_pdf


PARENT = "Notes to Consolidated Financial Statements"


class NoteSourceTests(unittest.TestCase):
    def context(self, *texts):
        return build_note_context([SourcePage("report", i, text) for i, text in enumerate(texts)])

    def bare(self, row):
        return [h for h in row["headings"] if h["kind"] == "note_bare_number" and h["mode"] == "observed"]

    def test_policy_snapshot_and_unchanged_section_v1(self):
        policy = note_policy_record()
        self.assertEqual(policy, read_json(Path(__file__).resolve().parents[1] / "configs/note_formats_v1.json"))
        self.assertEqual(policy["sha256"], "cbbc145937e12535a3db7243a28c9eebf0c5d20f14e42b85fe4e5bd4b9cebb2a")
        self.assertEqual(policy["section_v1_policy"], section_policy_record())
        self.assertEqual(section_policy_record()["sha256"], "159fd78a039d914e3c91489ccf37b40f43009a10e7808826e5b64b833b194b7e")

    def test_en_dash_addition_keeps_raw_offsets_and_other_note_forms(self):
        text = "\u2019\r\n  Note 21 \u2013 Legal Proceedings\r\nordinary legal prose.\r\nNote 22 \u2013 Segment Information\r\n"
        row = self.context(text)[0]
        self.assertEqual([h["kind"] for h in row["headings"]], ["note_en_dash", "note_en_dash"])
        for h in row["headings"]:
            self.assertEqual(text[h["source_start"]:h["source_end"]], h["heading_text"])
        self.assertEqual(row["headings"][0]["scope_end"], text.index("Note 22"))
        for punctuation in (":", ".", "\u2014", "-"):
            source = [SourcePage("report", 0, f"Note 1 {punctuation} Accounting Policies")]
            new = build_note_context(source)[0]; new.pop("note_detection")
            self.assertEqual(new, build_section_context(source)[0])
        # Frozen v1 still misses the new forms.
        self.assertEqual(build_section_context([SourcePage("report", 0, text)])[0]["headings"], [])

    def test_local_parent_one_then_strict_sequence_across_pages(self):
        rows = self.context(PARENT + "\n1.   Accounting Policies\nordinary prose.",
                            "ordinary continuing prose.", "2.   Acquisitions\n3. Restructuring\nordinary prose.")
        self.assertEqual([h["heading_text"] for h in self.bare(rows[2])], ["2.   Acquisitions", "3. Restructuring"])
        self.assertEqual(rows[1]["headings"][0]["mode"], "inherited")
        self.assertFalse(any(h["mode"] == "inherited" for h in rows[2]["headings"]))
        self.assertNotIn("policies", rows[2]["heading_tokens"])
        self.assertEqual(rows[2]["note_detection"]["state_before"]["last_bare_number"], 1)

    def test_prose_parent_late_one_gaps_repeats_and_backtracking_rejected(self):
        examples = [PARENT + ", included in Item 8, of this Annual Report.\n1. Accounting Policies",
                    "1. Accounting Policies\n" + PARENT,
                    PARENT + "\n2. Acquisitions"]
        for text in examples:
            self.assertEqual(self.bare(self.context(text)[0]), [])
        rows = self.context(PARENT, "1. Accounting Policies")
        self.assertEqual(self.bare(rows[1]), [])  # first note must be on parent page
        row = self.context(PARENT + "\n1. Accounting Policies\n3. Restructuring\n1. Other Policies\n2. Acquisitions\n2. Acquisitions")[0]
        self.assertEqual([h["heading_text"] for h in self.bare(row)], ["1. Accounting Policies", "2. Acquisitions"])
        self.assertEqual(sum(not c["accepted"] for c in row["note_detection"]["candidates"]), 3)

    def test_all_boundaries_clear_region_and_never_remove_candidates(self):
        contents = "\n".join(f"Note {i} - Topic Name {i + 2}" for i in range(1, 8))
        for boundary in ("Item 9. Changes in Accounting", "SIGNATURES", "Index to Exhibits",
                         "Exhibit 4.65\nordinary prose.", "UNITED STATES\nSECURITIES AND EXCHANGE COMMISSION",
                         contents, "", "Table of Contents\n12"):
            with self.subTest(boundary=boundary):
                rows = self.context(PARENT + "\n1. Accounting Policies", boundary, "2. Acquisitions")
                self.assertEqual(len(rows), 3)
                self.assertEqual(self.bare(rows[2]), [])
                self.assertIsNone(rows[1]["note_detection"]["state_after"]["parent_page_index"])
        row = self.context(PARENT + "\n1. Accounting Policies\nItem 9. Changes in Accounting\n2. Acquisitions")[0]
        self.assertEqual(len(self.bare(row)), 1)

    def test_source_hard_negatives_lists_tables_contents_and_prose(self):
        row = self.context(PARENT + "\n1. Accounting Policies\n2. $ 123 456\n2. Table Heading 42\n"
                           "2. Exercise of Options.\n2. We acquired a business.\n2. lower case title\n2. Debt")[0]
        self.assertEqual([h["heading_text"] for h in self.bare(row)], ["1. Accounting Policies", "2. Debt"])
        self.assertTrue(all(c["rejection_reason"] == "unsupported_title_syntax"
                            for c in row["note_detection"]["candidates"][1:-1]))
        outside = self.context("1. Vesting of Options\n2. Method of Payment")[0]
        self.assertEqual(self.bare(outside), [])
        self.assertTrue(all(c["rejection_reason"] == "outside_notes_region" for c in outside["note_detection"]["candidates"]))
        self.assertFalse(any(h["kind"] == "note_en_dash" for h in self.context("Note 21 \u2013 Legal Proceedings 108")[0]["headings"]))

    def test_continued_parent_preserves_sequence_but_never_chains_heading_text(self):
        rows = self.context(PARENT + "\n1. Accounting Policies", PARENT + " (continued)\n2. Acquisitions",
                            "ordinary prose.", "further prose.")
        self.assertEqual(len(self.bare(rows[1])), 1)
        self.assertEqual(rows[2]["headings"][0]["source_page_index"], 1)
        self.assertEqual(rows[3]["headings"], [])
        self.assertEqual(self.bare(self.context(PARENT + " (continued)\n1. Accounting Policies")[0])[0]["kind"], "note_bare_number")

    def test_partial_contents_item_reference_cannot_clear_region_and_candidate_limit_applies(self):
        row = self.context(PARENT + "\n1. Accounting Policies\nItem 9. Changes in Accounting 98\n2. Debt")[0]
        self.assertEqual([h["heading_text"] for h in self.bare(row)], ["1. Accounting Policies", "2. Debt"])
        # Twelve title words can exceed 32 lexical tokens when split by hyphens.
        row = self.context(PARENT + "\n1. Accounting Policies\n2. " + " ".join(["X-Y-Z"] * 12))[0]
        self.assertEqual(row["note_detection"]["candidates"][-1]["rejection_reason"], "candidate_limits")

    def test_paired_review_distinguishes_recall_from_first_hit_and_both_controls(self):
        labels = [{"task_id": "q", "doc_id": "report", "evidence_pages": [0, 3]}]
        orders = {"question_expansion": [0, 1, 2, 3], "section_context": [2, 1, 0, 3], "note_formats": [3, 0, 2, 1]}
        predictions = {key: {"q": {"task_id": "q", "doc_id": "report", "page_count": 4, "status": "ok", "no_match": False,
                       "ranked_pages": [{"page_index": p} for p in order]}} for key, order in orders.items()}
        metrics = {key: evaluate_retrieval(rows.values(), labels) for key, rows in predictions.items()}
        review = paired_comparisons(predictions, metrics, labels, [1, 3, 5])
        for control in ("question_expansion", "section_context"):
            self.assertEqual(review[control]["delta_at_k"]["3"]["macro_evidence_recall"], .5)
            self.assertEqual(review[control]["paired_counts_at_k"]["3"]["all_evidence_coverage"]["gains"], 1)
            self.assertEqual(review[control]["multi_page_delta_at_k"]["3"]["macro_evidence_recall"], .5)
        self.assertEqual(review["question_expansion"]["delta_mrr_full_ranking"], 0)
        self.assertAlmostEqual(review["section_context"]["delta_mrr_full_ranking"], 2/3)
        self.assertEqual(review["section_context"]["per_question"][0]["gold_page_ranks"][0]["rank_change"], -1)

    def test_new_boundary_closes_legal_continuation_without_changing_rule(self):
        second = "ordinary legal continuation.\nNote 22 \u2013 Segment Information\nordinary segment prose."
        rows = self.context("Fair Value Disclosures\nordinary prose.\nNote 21 \u2013 Legal Proceedings", second, "ordinary prose.", "ordinary prose.")
        inherited = rows[1]["headings"][0]
        self.assertEqual(inherited["heading_text"], "Note 21 \u2013 Legal Proceedings")
        self.assertEqual(inherited["scope_end"], second.index("Note 22"))
        self.assertEqual(rows[2]["headings"][0]["heading_text"], "Note 22 \u2013 Segment Information")
        self.assertEqual(rows[3]["headings"], [])

    def test_no_other_detector_cleanup_and_cap_duplicate_rules_unchanged(self):
        text = "Year Ended\nConsolidated Statements of Earnings from the fair value of the derivatives.\nFLNA QFNA PBNA LatAm Europe AMESA APAC Corporate"
        source = [SourcePage("report", 0, text)]
        row = build_note_context(source)[0]; row.pop("note_detection")
        self.assertEqual(row, build_section_context(source)[0])
        long_titles = ["Topic " + " ".join(["Distinct" + chr(65 + i)] * 11) for i in range(7)]
        row = self.context(PARENT + "\n1. Accounting Policies\n" + "\n".join(long_titles) + "\n2. Acquisitions\nNote 8 \u2013 Other Policies\nNote 8 \u2013 Other Policies")[0]
        self.assertLessEqual(row["heading_token_count"], 64)
        self.assertTrue(any(h["rejection_reason"] == "heading_token_cap" for h in row["headings"]))
        self.assertEqual(row["headings"][-1]["rejection_reason"], "duplicate_heading")

    def test_minimal_source_projection_causality_and_new_report_reset(self):
        source = SourcePage.from_record({"doc_id": "report", "page_index": 0, "raw_text": "2. Acquisitions",
                                        "answer": PARENT, "evidence_pages": [0], "justification": "1. Accounting Policies"})
        self.assertEqual(self.bare(build_note_context([source])[0]), [])
        first = self.context(PARENT + "\n1. Accounting Policies", "2. Debt")
        self.assertEqual(first, self.context(PARENT + "\n1. Accounting Policies", "2. Debt", "3. Acquisitions")[:2])
        self.context(PARENT + "\n1. Accounting Policies")
        self.assertEqual(self.bare(self.context("2. Debt")[0]), [])
        with self.assertRaises(TypeError):
            build_note_context([{"doc_id": "report", "page_index": 0, "raw_text": PARENT}])


class NoteComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.documents, self.tasks = self.root / "documents.jsonl", self.root / "tasks.jsonl"
        docs = []
        for name, texts in [("report", [PARENT + "\n1. Accounting Policies\nordinary text",
                            "2. Acquisitions\nordinary acquired text", "3. Legal Proceedings\nordinary legal text", None,
                            "Exhibit 4.65\nDescription of Securities\n2. Vesting of Options"]),
                            ("unannotated", [PARENT + "\n1. Accounting Policies", "2. Debt", None])]:
            pdf = self.root / f"{name}.pdf"; text_pdf(pdf, texts)
            docs.append({"doc_id": name, "pdf_path": str(pdf), "source_format": "pdf", "page_count": len(texts),
                         "metadata": {"sha256": sha256_file(pdf)}})
        write_jsonl(self.documents, docs)
        self.task_rows = [{"task_id": "q", "doc_id": "report", "question": "acquisitions legal",
                           "evidence_pages": [1, 2], "answers": ["NEVER_LEAK"],
                           "metadata": {"justification": "NEVER_LEAK", "evidence_text": "NEVER_LEAK"}},
                          {"task_id": "zero", "doc_id": "report", "question": "zqxuv", "evidence_pages": [4]}]
        write_jsonl(self.tasks, self.task_rows)
        self.native, self.expansion, self.section = self.controls("")

    def controls(self, suffix):
        native, stop, expansion, section = [self.root / (n + suffix) for n in ("native", "stop", "expansion", "section")]
        run_native_baseline(self.documents, self.tasks, native, repository_root=self.root)
        compare_stopwords(native, stop, tasks_path=self.tasks, repository_root=self.root)
        compare_query_expansion(native, stop, expansion, tasks_path=self.tasks, repository_root=self.root)
        compare_section_context(native, expansion, section, tasks_path=self.tasks, repository_root=self.root)
        return native, expansion, section

    def tearDown(self):
        self.temp.cleanup()

    def run_comparison(self, name="notes", **kwargs):
        return compare_note_formats(self.native, self.expansion, self.section, self.root / name,
                                    tasks_path=self.tasks, repository_root=self.root, **kwargs)

    def rehash(self, name):
        manifest = read_json(self.section / "run_manifest.json"); path = self.section / name
        manifest["artifacts"][name] = {"sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        write_json(self.section / "run_manifest.json", manifest)

    def test_full_cohort_both_controls_components_ties_and_immutable_inputs(self):
        before = {p: p.read_bytes() for d in (self.native, self.expansion, self.section) for p in d.rglob("*") if p.is_file()}
        result = self.run_comparison(); out = self.root / "notes"
        self.assertTrue(result["expansion_control_reproduced"] and result["section_control_reproduced"])
        self.assertEqual(len(read_jsonl(out / "note_context.jsonl")), 8)
        self.assertEqual(read_jsonl(out / "section_context.jsonl"), read_jsonl(self.section / "section_context.jsonl"))
        for name in ("baseline_reproduced_predictions.jsonl", "stopword_predictions.jsonl", "expanded_predictions.jsonl", "section_predictions.jsonl"):
            self.assertEqual([r["ranked_pages"] for r in read_jsonl(out / name)],
                             [r["ranked_pages"] for r in read_jsonl(self.section / name)])
        expanded = {r["task_id"]: {p["page_index"]: p["score"] for p in r["ranked_pages"]}
                    for r in read_jsonl(out / "expanded_predictions.jsonl")}
        for row in read_jsonl(out / "note_predictions.jsonl"):
            self.assertEqual({p["page_index"] for p in row["ranked_pages"]}, set(range(5)))
            for p in row["ranked_pages"]:
                self.assertEqual(p["body_score"], expanded[row["task_id"]][p["page_index"]])
                self.assertEqual(p["score"], p["body_score"] + .25 * p["heading_score"])
            if row["task_id"] == "zero":
                self.assertEqual([p["page_index"] for p in row["ranked_pages"]], list(range(5)))
        metrics = read_json(out / "comparison_metrics.json")
        self.assertEqual(set(metrics["note_comparisons"]), {"question_expansion", "section_context"})
        self.assertEqual(metrics["multi_page"]["note_formats"]["question_count"], 1)
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        manifest = read_json(out / "run_manifest.json")
        self.assertTrue(manifest["last_planned_heading_format_ablation"])
        for name, identity in manifest["artifacts"].items():
            self.assertEqual(identity, {"sha256": sha256_file(out / name), "size_bytes": (out / name).stat().st_size})

    def test_annotations_loaded_after_all_retrieval_outputs_and_never_leak(self):
        def check(path):
            for name in ("note_predictions.jsonl", "section_predictions.jsonl", "expanded_predictions.jsonl",
                         "baseline_reproduced_predictions.jsonl", "stopword_predictions.jsonl", "note_context.jsonl",
                         "section_context.jsonl", "note_context_summary.json", "section_context_summary.json",
                         "retrieval_queries.jsonl", "expanded_retrieval_queries.jsonl", "query_expansion_audit.jsonl"):
                self.assertTrue((self.root / "notes" / name).exists(), name)
            return load_evidence_labels(path)
        with patch("finocr.pipelines.section_comparison.load_evidence_labels", side_effect=check) as labels:
            self.run_comparison(); labels.assert_called_once()
        for path in (self.root / "notes").glob("*.jsonl"):
            self.assertNotIn("NEVER_LEAK", path.read_text())

    def test_label_mutation_does_not_change_context_queries_or_rankings(self):
        self.run_comparison("first")
        changed = copy.deepcopy(self.task_rows); changed[0].update(answers=["debt"], evidence_pages=[4],
                       metadata={"justification": PARENT, "evidence_text": "Legal Proceedings"})
        write_jsonl(self.tasks, changed)
        native, expansion, section = self.controls("2")
        compare_note_formats(native, expansion, section, self.root / "second", tasks_path=self.tasks, repository_root=self.root)
        for name in ("note_context.jsonl", "section_context.jsonl", "retrieval_queries.jsonl", "expanded_retrieval_queries.jsonl"):
            self.assertEqual(read_jsonl(self.root / "first" / name), read_jsonl(self.root / "second" / name))
        for name in ("note_predictions.jsonl", "section_predictions.jsonl", "expanded_predictions.jsonl"):
            self.assertEqual([r["ranked_pages"] for r in read_jsonl(self.root / "first" / name)],
                             [r["ranked_pages"] for r in read_jsonl(self.root / "second" / name)])

    def test_section_lineage_policy_and_missing_artifact_rejected_before_output(self):
        path = self.section / "run_manifest.json"; original = read_json(path)
        for case in ("lineage", "policy", "missing"):
            changed = copy.deepcopy(original)
            if case == "lineage": changed["expansion_reference_run_id"] = "wrong"
            if case == "policy": changed["configuration"]["section_policy"]["heading_weight"] = .5
            if case == "missing": changed["artifacts"].pop("section_context.jsonl")
            write_json(path, changed)
            with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
                with self.assertRaises(ValueError): self.run_comparison(case)
                labels.assert_not_called()
            self.assertFalse((self.root / case).exists())

    def test_rehashed_component_and_context_tampering_fail_before_labels(self):
        for name in ("section_predictions.jsonl", "section_context.jsonl"):
            original = (self.section / name).read_bytes()
            rows = read_jsonl(self.section / name)
            if name.startswith("section_predictions"):
                rows[0]["ranked_pages"][0]["heading_score"] += 1
            else:
                rows[0]["headings"][0]["scope_end"] += 1
            write_jsonl(self.section / name, rows); self.rehash(name)
            with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
                with self.assertRaisesRegex(ValueError, "failed reproduction"):
                    self.run_comparison(name)
                labels.assert_not_called()
            self.assertEqual(read_json(self.root / name / "run_manifest.json")["status"], "failed")
            (self.section / name).write_bytes(original); self.rehash(name)

    def test_rehashed_subgroup_metrics_tampering_never_completes(self):
        name = "comparison_metrics.json"; value = read_json(self.section / name)
        value["multi_page"]["section_context"]["mrr_full_ranking"] = 999
        write_json(self.section / name, value); self.rehash(name)
        with self.assertRaisesRegex(ValueError, "subgroup metrics failed reproduction"):
            self.run_comparison()
        self.assertEqual(read_json(self.root / "notes" / "run_manifest.json")["status"], "failed")
        self.assertFalse((self.root / "notes" / "comparison_metrics.json").exists())

    def test_source_or_reference_mutation_fails_before_labels(self):
        def mutate(message):
            path = self.section / "section_context.jsonl"; path.write_bytes(path.read_bytes() + b"\n")
        with patch("finocr.pipelines.section_comparison.load_evidence_labels") as labels:
            with self.assertRaisesRegex(ValueError, "changed during"):
                self.run_comparison(progress=mutate)
            labels.assert_not_called()

    def test_cli_success_policy_failure_and_output_guards(self):
        env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
        command = [sys.executable, "-m", "finocr.cli", "compare-note-formats", "--baseline-dir", str(self.native),
                   "--expansion-dir", str(self.expansion), "--section-dir", str(self.section), "--tasks", str(self.tasks),
                   "--repository-root", str(self.root / "code")]
        result = subprocess.run(command + ["--output-dir", str(self.root / "cli")], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["section_control_reproduced"])
        with self.assertRaises(FileExistsError): self.run_comparison("cli")
        with self.assertRaises(ValueError): self.run_comparison("section/nested")
        path = self.section / "run_manifest.json"; value = read_json(path); value["page_index_base"] = 1; write_json(path, value)
        failed = subprocess.run(command + ["--output-dir", str(self.root / "bad")], env=env, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 2)
        self.assertIn("Section-v1 reference", failed.stderr)


if __name__ == "__main__":
    unittest.main()
