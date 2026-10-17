"""Small source fixtures and simulated workers, never experimental OCR results."""
import copy
import io
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zlib

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import load_evidence_labels, run_native_baseline, sha256_file
from finocr.pipelines.ocr_comparison import compare_native_ocr, paired_changes
from finocr.pipelines.ocr_data import full_render
from finocr.pipelines.ocr_smoke import MODEL_NAMES, OCR_CONFIG, PACKAGE_PINS, normalize_ocr_result
from finocr.pipelines.ocr_tables import TABLE_POLICY, review_financial_tables, select_financial_tables
from finocr.pipelines.report_ocr import ReportWorker, _worker, cache_lock, run_report_ocr
from finocr.pipelines.report_rendering import file_identity, render_full_reports
from finocr.pipelines.stopword_comparison import compare_query_expansion, compare_stopwords
from test_native_baseline import text_pdf


def fixture_png():
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind+data))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + chunk(b"IEND", b"")


class FakeWorker:
    starts = 0
    calls = []
    timeout_page = None
    malformed_page = None
    fail_initialization = False
    def __init__(self, models, session_dir, initialization_timeout, progress):
        FakeWorker.starts += 1; self.session_dir = session_dir; session_dir.mkdir(parents=True)
        (session_dir / "worker.log").write_text("simulated fixture worker\n")
        write_json(session_dir / "startup.json", {"model_paths": models})
        self.ready = {"status": "ready", "initialization_seconds": .01,
            "runtime": {"packages": PACKAGE_PINS, "paddle_device": "cpu", "compiled_with_cuda": False}}
        if FakeWorker.fail_initialization:
            write_json(session_dir / "ready.json", {"status": "failed", "initialization_seconds": .01})
            raise RuntimeError("fixture initialization failure")
        write_json(session_dir / "ready.json", self.ready)
    def close(self): pass
    def page(self, image, image_identity, directory, timeout):
        page = int(image.stem.split("_")[1]); doc = "report" if image.parent.name.startswith("report-") else "unannotated"
        FakeWorker.calls.append((doc, page))
        if FakeWorker.timeout_page == (doc, page):
            FakeWorker.timeout_page = None
            raise TimeoutError("fixture page timeout")
        blank = (doc == "report" and page == 6) or (doc == "unannotated" and page == 1)
        text = "" if blank else "Revenue (1,234) \u221212.5% 2022" if page == 2 else "revenue " * 20
        payload = {"rec_texts": [text] if text else [], "rec_scores": [.9] if text else [],
                   "rec_polys": [[[0,0],[1,0],[1,1],[0,1]]] if text else []}
        write_json(directory / "raw_ocr_result.json", payload)
        if FakeWorker.malformed_page == (doc, page):
            result = {"status": "failed", "error": "fixture invalid OCR arrays", "inference_and_serialization_seconds": .02}
        else:
            normalized = normalize_ocr_result(payload)
            result = {"status": normalized["status"], "normalized": normalized, "error": None,
                      "inference_and_serialization_seconds": .02}
        write_json(directory / "worker_result.json", result)
        return result


class FullOcrTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.root = Path(self.temporary.name)
        self.documents = self.root / "documents.jsonl"; self.tasks = self.root / "tasks.jsonl"
        self.docs = []
        for doc_id, texts in [("report", ["quick ratio explanation", "2022 cash equivalents short term investments accounts receivable current liabilities",
                                "revenue depreciation amortization", "revenue revenue sales", "noise", "unrelated", None]),
                              ("unannotated", ["Other source", None])]:
            path = self.root / (doc_id + ".pdf"); text_pdf(path, texts)
            self.docs.append({"doc_id": doc_id, "pdf_path": str(path), "source_format": "pdf", "page_count": len(texts),
                              "metadata": {"sha256": sha256_file(path), "answers": ["NEVER_LEAK_ANSWER"]}})
        write_jsonl(self.documents, self.docs)
        self.labels = [{"task_id": "ratio", "doc_id": "report", "question": "quick ratio EBITDA 2022", "evidence_pages": [1,2],
                        "answers": ["NEVER_LEAK_ANSWER"], "metadata": {"justification": "NEVER_LEAK_JUSTIFICATION"}},
                       {"task_id": "revenue", "doc_id": "report", "question": "revenue", "evidence_pages": [2]},
                       {"task_id": "no_match", "doc_id": "report", "question": "zqxw", "evidence_pages": [0]}]
        write_jsonl(self.tasks, self.labels)
        self.native = self.root / "native"; self.stop = self.root / "stop"; self.expansion = self.root / "expansion"
        run_native_baseline(self.documents, self.tasks, self.native, repository_root=self.root)
        compare_stopwords(self.native, self.stop, repository_root=self.root)
        compare_query_expansion(self.native, self.stop, self.expansion, repository_root=self.root)
        self.render = self.root / "render"
        def render_fixture(command, **kwargs):
            Path(command[-1]).with_suffix(".png").write_bytes(fixture_png())
            return subprocess.CompletedProcess(command, 0, "", "")
        with patch("finocr.pipelines.report_rendering.renderer_identity", return_value={"fixture": True}), \
             patch("finocr.pipelines.report_rendering.code_provenance", return_value={"fixture": True}), \
             patch("finocr.pipelines.report_rendering.subprocess.run", side_effect=render_fixture):
            render_full_reports(self.documents, self.render, renderer_path="fixture", native_dir=self.native, repository_root=self.root)
        self.models = self.root / "models"; self.models.mkdir()
        model_manifest = {"status": "complete", "models": {}}
        for name in MODEL_NAMES:
            directory = self.models / name; directory.mkdir(); file = directory / "inference.yml"; file.write_text(name)
            model_manifest["models"][name] = {"directory": name, "files": {"inference.yml": file_identity(file)}}
        write_json(self.models / "model_manifest.json", model_manifest)
        self.ocr = self.root / "ocr"
        FakeWorker.starts = 0; FakeWorker.calls = []; FakeWorker.timeout_page = None
        FakeWorker.malformed_page = None; FakeWorker.fail_initialization = False
    def tearDown(self): self.temporary.cleanup()
    def run_ocr(self, **kwargs):
        with patch("finocr.pipelines.report_ocr.ReportWorker", FakeWorker), \
             patch("finocr.pipelines.report_ocr.runtime_identity", return_value={"python": "fixture", "bits": 64, "packages": PACKAGE_PINS}), \
             patch("finocr.pipelines.report_ocr.code_provenance", return_value={"python_source_sha256": "fixture"}):
            return run_report_ocr(self.render, self.models, self.ocr, repository_root=self.root, **kwargs)
    def compare(self, name="comparison"):
        return compare_native_ocr(self.native, self.expansion, self.ocr, self.root / name, repository_root=self.root)

    def test_full_coverage_worker_reuse_raw_numbers_and_no_label_inputs(self):
        self.run_ocr()
        rows = read_jsonl(self.ocr / "ocr_pages.jsonl")
        self.assertEqual([(r["doc_id"], r["page_index"]) for r in rows], [("report", p) for p in range(7)]+[("unannotated",p) for p in range(2)])
        self.assertEqual(FakeWorker.starts, 2); self.assertEqual(len(FakeWorker.calls), 9)
        self.assertTrue(all(r["page_index_base"] == 0 for r in rows))
        self.assertIn("\u221212.5%", rows[2]["raw_text"]); self.assertIn("-12.5%", rows[2]["search_text"])
        manifest = read_json(self.ocr / "run_manifest.json")
        self.assertTrue(manifest["full_ocr_coverage"]); self.assertEqual(manifest["coverage"]["blank_pages"], 2)
        self.assertEqual(manifest["timing"]["page_attempts"], 9)
        for p in self.ocr.rglob("*.json*"):
            self.assertNotIn("NEVER_LEAK", p.read_text())
        self.assertEqual(file_identity(self.ocr / "source-render/render_pages.jsonl"), file_identity(self.render / "render_pages.jsonl"))

    def test_resume_reuses_verified_commits_and_extends_diagnostic_without_reocr(self):
        _, plans, inputs = full_render(self.render)
        selection = self.root / "selection.json"
        write_json(selection, {"policy": {"version": "source-financial-tables-v1"}, "inputs": inputs,
            "pages": [{"doc_id": "report", "page_index": p} for p in (1,2)]})
        result = self.run_ocr(selection_path=selection)
        self.assertEqual(result["status"], "diagnostic_complete"); self.assertFalse(result["full_ocr_coverage"])
        self.assertEqual(result["coverage"]["pending_pages"], 7)
        rows = read_jsonl(self.ocr / "ocr_pages.jsonl")
        files = {r["record_path"]: (self.ocr / r["record_path"]).read_bytes() for r in rows if "record_path" in r}
        self.assertEqual(self.run_ocr(resume=True)["status"], "complete")
        self.assertEqual(len(FakeWorker.calls), 9)
        for name, data in files.items(): self.assertEqual((self.ocr / name).read_bytes(), data)
        calls = len(FakeWorker.calls); self.run_ocr(resume=True); self.assertEqual(len(FakeWorker.calls), calls)

    def test_timeout_failure_is_source_mapped_retained_then_retried(self):
        FakeWorker.timeout_page = ("report",1)
        result = self.run_ocr(); self.assertEqual(result["status"], "partial")
        failed = read_jsonl(self.ocr / "ocr_pages.jsonl")[1]
        self.assertEqual(failed["status"], "timed_out"); self.assertEqual(failed["search_text"], "")
        old = (self.ocr / failed["record_path"]).read_bytes()
        self.assertEqual(self.run_ocr(resume=True)["status"], "complete")
        retry = read_jsonl(self.ocr / "ocr_pages.jsonl")[1]
        self.assertEqual(retry["attempt_count"], 2); self.assertEqual((self.ocr / failed["record_path"]).read_bytes(), old)
        self.assertEqual(read_json(self.ocr / "run_manifest.json")["timing"]["page_attempts"], 10)

    def test_initialization_failure_is_not_repeated_for_every_page(self):
        FakeWorker.fail_initialization = True
        result = self.run_ocr()
        self.assertEqual(result["status"], "partial"); self.assertEqual(FakeWorker.starts, 2)
        self.assertEqual(result["coverage"]["failure_pages"], 9)
        self.assertEqual(result["coverage"]["pending_pages"], 0)
        self.assertTrue(all(not r["ocr_attempted"] for r in read_jsonl(self.ocr / "ocr_pages.jsonl")))

    def test_interruption_commits_current_failure_and_keeps_remaining_pending(self):
        def interrupt(message):
            if "zero-based page 1 " in message: raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_ocr(progress=interrupt)
        rows = read_jsonl(self.ocr / "ocr_pages.jsonl")
        self.assertEqual([r["status"] for r in rows[:3]], ["ok", "interrupted", "pending"])
        self.assertEqual(len(rows), 9)
        self.assertEqual(self.run_ocr(resume=True)["status"], "complete")
        self.assertEqual(read_jsonl(self.ocr / "ocr_pages.jsonl")[1]["attempt_count"], 2)

    def test_uncommitted_attempt_recovery_preserves_raw_and_retries(self):
        self.run_ocr(max_pages=1)
        from finocr.pipelines.report_rendering import safe_document_name
        uncommitted = self.ocr / "attempts" / safe_document_name("report") / "page_00001/attempt_0001"
        uncommitted.mkdir(parents=True); (uncommitted / "partial-raw.txt").write_text("retained fixture")
        self.run_ocr(resume=True)
        self.assertEqual((uncommitted / "partial-raw.txt").read_text(), "retained fixture")
        self.assertEqual(read_json(uncommitted / "record.json")["record"]["status"], "interrupted")
        row = read_jsonl(self.ocr / "ocr_pages.jsonl")[1]; self.assertEqual(row["attempt_count"], 2)

    def test_changed_input_model_raw_and_condition_reject_resume(self):
        self.run_ocr(max_pages=1)
        with self.assertRaisesRegex(ValueError, "resume inputs/configuration"):
            self.run_ocr(resume=True, page_timeout=601)
        row = read_jsonl(self.ocr / "ocr_pages.jsonl")[0]
        raw = (self.ocr / row["record_path"]).parent / "raw_ocr_result.json"; data = raw.read_bytes()
        raw.write_bytes(data+b"\n")
        with self.assertRaisesRegex(ValueError, "artifact checksum"): self.run_ocr(resume=True)
        raw.write_bytes(data)
        file = self.models / MODEL_NAMES[0] / "inference.yml"; model = file.read_bytes(); file.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "model files changed"): self.run_ocr(resume=True)
        file.write_bytes(model)
        render = read_jsonl(self.render / "render_pages.jsonl")[0]; image = self.render / render["image_path"]
        image.write_bytes(image.read_bytes()+b"changed")
        with self.assertRaisesRegex(ValueError, "checksum/geometry"): self.run_ocr(resume=True)

    def test_cache_lock_prevents_parallel_writers(self):
        self.ocr.mkdir()
        with cache_lock(self.ocr):
            with self.assertRaisesRegex(RuntimeError, "Another OCR process"):
                with cache_lock(self.ocr): pass

    def test_matched_retrieval_reproduces_control_before_labels_and_keeps_all_candidates(self):
        self.run_ocr()
        def labels_after_predictions(path):
            for name in ["native_predictions.jsonl", "ocr_predictions.jsonl"]:
                self.assertTrue((self.root / "comparison" / name).is_file())
            return load_evidence_labels(path)
        with patch("finocr.pipelines.ocr_comparison.load_evidence_labels", side_effect=labels_after_predictions): self.compare()
        directory = self.root / "comparison"; m = read_json(directory / "run_manifest.json")
        self.assertTrue(m["expansion_control_reproduced"]); self.assertEqual(m["primary_k"], 5)
        old = read_jsonl(self.expansion / "expanded_predictions.jsonl"); new = read_jsonl(directory / "native_predictions.jsonl")
        self.assertEqual([r["ranked_pages"] for r in old], [r["ranked_pages"] for r in new])
        for r in read_jsonl(directory / "ocr_predictions.jsonl"):
            self.assertEqual({p["page_index"] for p in r["ranked_pages"]}, set(range(7)))
        self.assertEqual(len(read_jsonl(directory / "index_stats.jsonl")),4)
        metrics = read_json(directory / "comparison_metrics.json")
        self.assertEqual(metrics["paired"]["multipage"]["question_count"], 1)
        self.assertIn("revenue", metrics["paired"]["recall5_regression_tasks"])
        report = (directory / "comparison_report.md").read_text()
        self.assertIn("Coverage: 2 reports / 9 page records", report)
        self.assertIn("| native | 100.000000% | 3/3 | 3/3 | 1 |", report)
        self.assertIn("| ocr | 66.666667% | 2/3 | 2/3 | 1 |", report)
        self.assertIn("Regressions: revenue.", report)
        self.assertIn("Multi-page complete@5: native 1/1; OCR 1/1.", report)
        self.assertIn("Execution output awaiting independent artifact review", report)
        self.assertNotIn("NEVER_LEAK", report)
        for p in directory.glob("*.jsonl"): self.assertNotIn("NEVER_LEAK", p.read_text())

    def test_pending_and_diagnostic_caches_cannot_supply_matched_scores(self):
        self.run_ocr(max_pages=1)
        with self.assertRaisesRegex(ValueError, "Finalize full-report"): self.compare()
        self.assertFalse((self.root / "comparison").exists())

    def test_failed_pages_stay_in_ranking_with_explicit_failure_coverage(self):
        FakeWorker.malformed_page = ("report",2)
        self.run_ocr(); self.compare()
        prediction = read_jsonl(self.root / "comparison/ocr_predictions.jsonl")[0]
        self.assertEqual(prediction["status"], "partial_extraction")
        self.assertEqual(len(prediction["ranked_pages"]), 7)
        metrics = read_json(self.root / "comparison/comparison_metrics.json")
        self.assertTrue(metrics["ocr_failure_inclusive"])
        self.assertEqual(read_json(self.ocr / "run_manifest.json")["coverage"]["failure_pages"], 1)

    def test_changed_control_and_committed_source_mapping_are_rejected(self):
        self.run_ocr()
        path = self.expansion / "run_manifest.json"; original = read_json(path)
        changed = copy.deepcopy(original); changed["configuration"]["b"] = .5; write_json(path, changed)
        with self.assertRaisesRegex(ValueError, "scoring/tokenization"): self.compare()
        write_json(path, original)
        row = read_jsonl(self.ocr / "ocr_pages.jsonl")[0]; record = self.ocr / row["record_path"]
        envelope = read_json(record); envelope["record"]["page_index"] = 1; write_json(record, envelope)
        with self.assertRaisesRegex(ValueError, "checksum"): self.compare()

    def test_source_table_selection_and_numeric_review_read_no_labels(self):
        table = "Consolidated Statements of Income\nIn millions\n" + " ".join(str(i) for i in range(100,125))
        table2 = table.replace("Statements of Income", "Balance Sheets")
        text_pdf(Path(self.docs[0]["pdf_path"]), [table,table2,"body","body","body","body",None])
        self.docs[0]["metadata"]["sha256"] = sha256_file(Path(self.docs[0]["pdf_path"])); write_jsonl(self.documents,self.docs)
        self.native = self.root / "tables-native"; run_native_baseline(self.documents,self.tasks,self.native,repository_root=self.root)
        self.render = self.root / "tables-render"
        def render_fixture(command, **kwargs):
            Path(command[-1]).with_suffix(".png").write_bytes(fixture_png()); return subprocess.CompletedProcess(command,0,"","")
        with patch("finocr.pipelines.report_rendering.renderer_identity", return_value={}), \
             patch("finocr.pipelines.report_rendering.code_provenance", return_value={}), \
             patch("finocr.pipelines.report_rendering.subprocess.run", side_effect=render_fixture):
            render_full_reports(self.documents,self.render,renderer_path="fixture",native_dir=self.native,repository_root=self.root)
        selection = self.root / "tables.json"
        with patch("finocr.pipelines.ocr_tables.REPORTS", ("report",)):
            result = select_financial_tables(self.native,self.render,selection)
        self.assertEqual([r["page_index"] for r in result["pages"]],[0,1])
        self.assertNotIn("NEVER_LEAK",json.dumps(result))
        self.run_ocr(selection_path=selection)
        review = review_financial_tables(self.native,self.ocr,selection,self.root / "table-review.json")
        self.assertEqual(len(review["pages"]),2); self.assertIn("not CER/WER",review["interpretation"])
        self.assertEqual(read_json(self.ocr / "run_manifest.json")["contract"]["configuration"],OCR_CONFIG)


class ReportWorkerTests(unittest.TestCase):
    def test_worker_loop_initializes_once_and_preserves_raw_for_each_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); session = root / "session"; session.mkdir()
            image = root / "image.png"; image.write_bytes(fixture_png())
            startup = root / "startup.json"; write_json(startup,{"session_dir":str(session),"model_paths":{}})
            requests = []
            for i in range(2):
                out = root / str(i); out.mkdir()
                requests.append({"image":str(image),"image_identity":file_identity(image),"output":str(out)})
            class Engine:
                calls = 0
                def predict(self, image):
                    Engine.calls += 1
                    class Result:
                        json = {"rec_texts":["(1,234) -12.5%"],"rec_scores":[.9],"rec_polys":[[[0,0],[1,0],[1,1],[0,1]]]}
                    return [Result()]
            runtime = {"packages":PACKAGE_PINS,"paddle_device":"cpu","compiled_with_cuda":False}
            stdin = io.StringIO("\n".join(json.dumps(r) for r in [*requests,{"stop":True}])+"\n")
            with patch("finocr.pipelines.report_ocr.create_ocr_engine",return_value=(Engine(),runtime,.1)) as initialize, \
                 patch("finocr.pipelines.report_ocr.sys.stdin",stdin): _worker(startup)
            self.assertEqual(initialize.call_count,1); self.assertEqual(Engine.calls,2)
            for i in range(2):
                self.assertEqual(read_json(root/str(i)/"worker_result.json")["status"],"ok")
                self.assertEqual(read_json(root/str(i)/"raw_ocr_result.json")["rec_texts"],["(1,234) -12.5%"])

    def test_real_coordinator_deadline_kills_a_hung_initialization(self):
        class Hung:
            killed = False
            def __init__(self,*args,**kwargs): self.stdin=io.StringIO()
            def poll(self): return -9 if Hung.killed else None
            def kill(self): Hung.killed=True
            def wait(self,**kwargs): return -9
        with tempfile.TemporaryDirectory() as temporary:
            with patch("finocr.pipelines.report_ocr.subprocess.Popen",Hung):
                with self.assertRaises(TimeoutError): ReportWorker({},Path(temporary)/"session",.01)
            self.assertTrue(Hung.killed)

    def test_paired_gains_regressions_and_multipage_completeness_have_separate_counts(self):
        def prediction(task,pages):
            return {"task_id":task,"doc_id":"r","ranked_pages":[{"page_index":p,"score":7-i} for i,p in enumerate(pages)]}
        labels=[{"task_id":"multi","doc_id":"r","evidence_pages":[1,6]}, {"task_id":"gain","doc_id":"r","evidence_pages":[4]}]
        before=[prediction("multi",[1,6,0,2,3,4,5]),prediction("gain",[0,1,2,3,5,6,4])]
        after=[prediction("multi",[1,0,2,3,4,5,6]),prediction("gain",[4,0,1,2,3,5,6])]
        rows=[{"doc_id":"r","page_index":p,"status":"ok"} for p in range(7)]
        result=paired_changes(before,after,labels,rows)
        self.assertEqual(result["recall5_gain_tasks"],["gain"])
        self.assertEqual(result["recall5_regression_tasks"],["multi"])
        self.assertEqual(result["multipage"]["native_complete5_count"],1)
        self.assertEqual(result["multipage"]["ocr_complete5_count"],0)
        self.assertEqual(result["multipage"]["questions"][0]["delta_recall5"],-.5)


if __name__ == "__main__": unittest.main()
