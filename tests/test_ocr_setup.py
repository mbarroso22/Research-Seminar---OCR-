import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.native_baseline import run_native_baseline, sha256_file
from finocr.pipelines.ocr_smoke import MODEL_NAMES, normalize_ocr_result, run_ocr_smoke, verified_models
from finocr.pipelines.report_rendering import file_identity, png_info, render_full_reports, safe_document_name
from test_native_baseline import text_pdf


class RenderingFixtures:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name)
        self.documents = self.root / "documents.jsonl"
        self.renderer = shutil.which("pdftoppm")
        self.docs = []
        for doc_id, name, texts in [("report:one", "one.pdf", ["Cover text", "Table 2022 2021", None, "Exhibit text"]),
                                    ("report_two", "two.pdf", ["Unannotated report", None])]:
            pdf = self.root / name; text_pdf(pdf, texts)
            self.docs.append({"doc_id": doc_id, "pdf_path": str(pdf), "source_format": "pdf", "page_count": len(texts),
                "metadata": {"sha256": sha256_file(pdf), "answers": ["NEVER_LEAK"], "evidence_pages": [1]}})
        write_jsonl(self.documents, self.docs)

    def tearDown(self): self.temp.cleanup()

    def render(self, name="render", **kwargs):
        if not self.renderer: self.skipTest("Actual Poppler required for PDF rendering integration")
        return render_full_reports(self.documents, self.root / name, renderer_path=self.renderer,
                                   repository_root=self.root, expected_documents=2, expected_pages=6, **kwargs)


class RenderingSetupTests(RenderingFixtures, unittest.TestCase):

    def encrypt_first_report(self, *, password="", owner_password="owner-secret"):
        path = Path(self.docs[0]["pdf_path"])
        text_pdf(path, ["Cover text", "Table 2022 2021", None, "Exhibit text"])
        reader = PdfReader(path); writer = PdfWriter()
        try:
            writer.append(reader)
            writer.encrypt(password, owner_password=owner_password, algorithm="AES-128")
            encrypted = self.root / "encrypted.pdf"
            writer.write(encrypted)
        finally:
            reader.close(); writer.close()
        encrypted.replace(path)
        self.docs[0]["metadata"]["sha256"] = sha256_file(path)
        write_jsonl(self.documents, self.docs)
        return path

    def test_empty_password_encrypted_pdf_keeps_native_identity_and_page_ids(self):
        for index, (owner, expected_result) in enumerate((("owner-secret", 1), ("", 2))):
            with self.subTest(decryption_result=expected_result):
                path = self.encrypt_first_report(owner_password=owner)
                original_bytes = path.read_bytes()
                reader = PdfReader(path)
                try:
                    self.assertTrue(reader.is_encrypted)
                    self.assertEqual(reader.decrypt(""), expected_result)
                    self.assertTrue(reader.is_encrypted)
                    self.assertEqual(len(reader.pages), 4)
                finally:
                    reader.close()
                tasks = self.root / "tasks.jsonl"
                write_jsonl(tasks, [{"task_id": "q", "doc_id": "report:one", "question": "cover", "evidence_pages": [0]}])
                native_dir = self.root / f"native-encrypted-{index}"
                native_result = run_native_baseline(self.documents, tasks, native_dir, repository_root=self.root)
                self.assertEqual(native_result["status"], "complete")
                name = f"render-encrypted-{index}"
                result = self.render(name, native_dir=native_dir)
                self.assertTrue(result["full_report_rendering_complete"])
                rows = read_jsonl(self.root / name / "render_pages.jsonl")
                self.assertEqual([(r["doc_id"], r["page_index"]) for r in rows],
                    [("report:one", i) for i in range(4)] + [("report_two", i) for i in range(2)])
                self.assertTrue(all(r["status"] == "ok" and r["page_index_base"] == 0 for r in rows))
                self.assertTrue(all(r["document_sha256"] == self.docs[0]["metadata"]["sha256"]
                                    for r in rows if r["doc_id"] == "report:one"))
                self.assertEqual(path.read_bytes(), original_bytes)
                self.assertEqual(sha256_file(path), self.docs[0]["metadata"]["sha256"])

    def test_nonempty_password_pdf_fails_preflight_without_manifest_or_rendering(self):
        path = self.encrypt_first_report(password="required-secret")
        original_bytes = path.read_bytes()
        output = self.root / "protected"
        with patch("finocr.pipelines.report_rendering.renderer_identity", return_value={}), \
                patch("finocr.pipelines.report_rendering.subprocess.run") as renderer:
            with self.assertRaisesRegex(ValueError, "empty password cannot decrypt.*report:one"):
                render_full_reports(self.documents, output, renderer_path="preflight-only", repository_root=self.root)
            renderer.assert_not_called()
        self.assertFalse((output / "run_manifest.json").exists())
        self.assertFalse(output.exists())
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_empty_password_pdf_still_requires_matching_page_count(self):
        path = self.encrypt_first_report()
        original_bytes = path.read_bytes()
        self.docs[0]["page_count"] = 5
        write_jsonl(self.documents, self.docs)
        output = self.root / "wrong-encrypted-count"
        with patch("finocr.pipelines.report_rendering.renderer_identity", return_value={}), \
                patch("finocr.pipelines.report_rendering.subprocess.run") as renderer:
            with self.assertRaisesRegex(ValueError, "PDF page count mismatch.*report:one.*expected 5, found 4"):
                render_full_reports(self.documents, output, renderer_path="preflight-only", repository_root=self.root,
                                    expected_documents=2, expected_pages=7)
            renderer.assert_not_called()
        self.assertFalse((output / "run_manifest.json").exists())
        self.assertFalse(output.exists())
        self.assertEqual(path.read_bytes(), original_bytes)

    def test_real_full_report_pixels_blank_pages_and_label_exclusion(self):
        result = self.render(); self.assertTrue(result["full_report_rendering_complete"])
        rows = read_jsonl(self.root / "render/render_pages.jsonl")
        self.assertEqual([(r["doc_id"], r["page_index"]) for r in rows],
            [("report:one", i) for i in range(4)] + [("report_two", i) for i in range(2)])
        self.assertTrue(all(r["status"] == "ok" and r["page_index_base"] == 0 for r in rows))
        for row in rows:
            self.assertEqual(row["image_info"], {"width": 1700, "height": 2200, "colour_mode": "RGB", "bit_depth": 8})
            self.assertEqual(file_identity(self.root / "render" / row["image_path"]), row["image_identity"])
        for path in (self.root / "render").rglob("*.json*"):
            self.assertNotIn("NEVER_LEAK", path.read_text())
        self.assertNotEqual(safe_document_name("a:b"), safe_document_name("a_b"))

    def test_sample_preserves_full_plan_then_resume_fills_missing_only(self):
        result = self.render(sample=True)
        self.assertEqual(result["status"], "sample_complete")
        rows = read_jsonl(self.root / "render/render_pages.jsonl"); self.assertEqual(len(rows), 6)
        self.assertEqual([r["page_index"] for r in rows if r["status"] == "pending"], [1])
        retained = {r["image_path"]: (self.root / "render" / r["image_path"]).stat().st_mtime_ns for r in rows if r["status"] == "ok"}
        self.assertTrue(self.render(resume=True)["full_report_rendering_complete"])
        for name, modified in retained.items(): self.assertEqual((self.root / "render" / name).stat().st_mtime_ns, modified)
        with self.assertRaises(FileExistsError): self.render()
        with self.assertRaisesRegex(ValueError, "settings changed"): self.render(resume=True, dpi=300)

    def test_rotated_pdf_records_rotation_and_dimensions(self):
        path = Path(self.docs[0]["pdf_path"])
        reader = PdfReader(path); writer = PdfWriter(); writer.append(reader)
        writer.pages[0].rotate(90)
        temporary = self.root / "rotated.pdf"; writer.write(temporary); reader.close(); temporary.replace(path)
        self.docs[0]["metadata"]["sha256"] = sha256_file(path); write_jsonl(self.documents, self.docs)
        self.render(sample=True)
        row = read_jsonl(self.root / "render/render_pages.jsonl")[0]
        self.assertEqual(row["pdf_rotation"], 90)
        self.assertEqual((row["image_info"]["width"], row["image_info"]["height"]), (2200, 1700))

    def test_original_native_cohort_identity_required(self):
        tasks = self.root / "tasks.jsonl"
        write_jsonl(tasks, [{"task_id": "q", "doc_id": "report:one", "question": "cover", "evidence_pages": [0]}])
        run_native_baseline(self.documents, tasks, self.root / "native", repository_root=self.root)
        self.render(native_dir=self.root / "native")
        self.docs[0]["metadata"]["answers"] = ["changed annotation"]
        write_jsonl(self.documents, self.docs)
        with self.assertRaisesRegex(ValueError, "native run/document identity"):
            self.render("wrong", native_dir=self.root / "native")
        self.assertFalse((self.root / "wrong").exists())

    def test_corrupt_image_and_changed_source_rejected(self):
        self.render(sample=True); rows = read_jsonl(self.root / "render/render_pages.jsonl")
        image = self.root / "render" / rows[0]["image_path"]; image.write_bytes(image.read_bytes() + b"corruption")
        with self.assertRaisesRegex(ValueError, "checksum/metadata"):
            self.render(resume=True)
        path = Path(self.docs[0]["pdf_path"]); path.write_bytes(path.read_bytes() + b"changed")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.render("new")

    def test_truncated_png_is_not_accepted_as_a_rendered_page(self):
        self.render(sample=True)
        row = read_jsonl(self.root / "render/render_pages.jsonl")[0]
        image = self.root / "render" / row["image_path"]
        image.write_bytes(image.read_bytes()[:33])
        with self.assertRaisesRegex(ValueError, "incomplete"):
            png_info(image)

    def test_one_page_renderer_error_retained_and_retried(self):
        original = subprocess.run
        def fail_one(command, **kwargs):
            if "-f" in command and command[command.index("-f") + 1] == "2" and command[-2].endswith("one.pdf"):
                return subprocess.CompletedProcess(command, 1, "", "fixture renderer failure")
            return original(command, **kwargs)
        with patch("finocr.pipelines.report_rendering.subprocess.run", side_effect=fail_one):
            result = self.render()
        self.assertEqual(result["status"], "partial")
        rows = read_jsonl(self.root / "render/render_pages.jsonl")
        self.assertEqual(rows[1]["status"], "failed"); self.assertEqual(len(rows), 6)
        self.assertTrue(self.render(resume=True)["full_report_rendering_complete"])

    def test_wrong_counts_missing_renderer_and_repository_output_rejected(self):
        with self.assertRaisesRegex(ValueError, "cohort/page totals"):
            render_full_reports(self.documents, self.root / "bad", renderer_path="missing", expected_pages=7)
        with self.assertRaisesRegex(ValueError, "does not exist"):
            render_full_reports(self.documents, self.root / "bad", renderer_path=self.root / "missing")
        (self.root / ".git").mkdir()
        with self.assertRaisesRegex(ValueError, "outside Git"): self.render()

    def test_input_mutation_during_rendering_never_completes_cache(self):
        def mutate(message):
            self.documents.write_bytes(self.documents.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "changed during rendering"):
            self.render(sample=True, progress=mutate)
        manifest = read_json(self.root / "render/run_manifest.json")
        self.assertEqual(manifest["status"], "failed")
        self.assertFalse(manifest["full_report_rendering_complete"])


class OcrContractTests(unittest.TestCase):
    def test_line_order_numbers_signs_and_raw_payload_preserved(self):
        payload = {"res": {"rec_texts": ["2022 (1,234) USD", "margin \u221212.5%"], "rec_scores": [.9, .8],
                    "rec_polys": [[[0,0],[10,0],[10,10],[0,10]], [[0,20],[10,20],[10,30],[0,30]]]}}
        before = copy.deepcopy(payload); result = normalize_ocr_result(payload)
        self.assertEqual(result["raw_text"], "2022 (1,234) USD\nmargin \u221212.5%")
        self.assertEqual(result["search_text"], "2022 (1,234) USD margin -12.5%")
        self.assertEqual(payload, before)
        self.assertEqual([r["order"] for r in result["lines"]], [0,1])

    def test_empty_and_malformed_outputs_not_silent_success(self):
        self.assertEqual(normalize_ocr_result({"rec_texts": [], "rec_scores": [], "rec_polys": []})["status"], "blank_ocr_text")
        for payload in ({"rec_texts": ["text"], "rec_scores": [], "rec_polys": []},
                        {"rec_texts": ["text"], "rec_scores": [float("nan")], "rec_polys": [[[0,0]]*4]},
                        {"rec_texts": ["text"], "rec_scores": [.5], "rec_polys": [[[0,0]]]}):
            with self.assertRaises(ValueError): normalize_ocr_result(payload)

    def test_model_bundle_pins_and_tampering(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); manifest = {"status": "complete", "models": {}}
            for name in MODEL_NAMES:
                directory = root / name; directory.mkdir(); (directory / "inference.yml").write_text(name)
                manifest["models"][name] = {"directory": name, "files": {"inference.yml": file_identity(directory / "inference.yml")}}
            write_json(root / "model_manifest.json", manifest)
            self.assertEqual(set(verified_models(root)[0]), set(MODEL_NAMES))
            (root / MODEL_NAMES[0] / "inference.yml").write_text("modified")
            with self.assertRaisesRegex(ValueError, "changed or incomplete"): verified_models(root)


class SmokeOrchestrationTests(RenderingFixtures, unittest.TestCase):

    def setUp(self):
        super().setUp(); self.render(sample=True)
        self.models = self.root / "models"; self.models.mkdir()
        manifest = {"status": "complete", "models": {}}
        for name in MODEL_NAMES:
            directory = self.models / name; directory.mkdir(); (directory / "inference.yml").write_text(name)
            manifest["models"][name] = {"directory": name, "files": {"inference.yml": file_identity(directory / "inference.yml")}}
        write_json(self.models / "model_manifest.json", manifest)

    def run_smoke(self, **kwargs):
        return run_ocr_smoke(self.root / "render", self.models, self.root / "smoke", doc_id="report:one", page_index=0,
                             repository_root=self.root, **kwargs)

    def test_fake_worker_mapping_and_setup_only_output(self):
        class FakeWorker:
            returncode = 0
            def __init__(inner, command, **kwargs):
                request = read_json(command[-1]); out = Path(request["output"])
                payload = {"rec_texts": ["Cover 2022"], "rec_scores": [.9], "rec_polys": [[[0,0],[10,0],[10,10],[0,10]]]}
                write_json(out / "raw_ocr_result.json", payload)
                write_json(out / "worker_result.json", {"normalized": normalize_ocr_result(payload), "timings": {}, "runtime": {}})
            def poll(inner): return 0
        with patch("finocr.pipelines.ocr_smoke.code_provenance", return_value={"fixture": True}), \
                patch("finocr.pipelines.ocr_smoke.subprocess.Popen", FakeWorker):
            result = self.run_smoke()
        self.assertEqual(result["status"], "smoke_complete"); self.assertFalse(result["full_ocr_coverage"])
        row = read_jsonl(self.root / "smoke/ocr_pages.jsonl")[0]
        self.assertEqual((row["doc_id"], row["page_index"], row["page_index_base"]), ("report:one",0,0))
        self.assertNotIn("NEVER_LEAK", json.dumps(row))
        manifest = read_json(self.root / "smoke/run_manifest.json")
        self.assertEqual(manifest["cohort_totals"], {"documents":2,"pages":6})
        self.assertEqual(manifest["selected_pages"],1)

    def test_worker_deadline_preserves_failure_and_kills_process(self):
        class HungWorker:
            killed = False
            def __init__(inner, *args, **kwargs): pass
            def poll(inner): return None
            def kill(inner): HungWorker.killed = True
            def wait(inner): return -1
        with patch("finocr.pipelines.ocr_smoke.code_provenance", return_value={"fixture": True}), \
                patch("finocr.pipelines.ocr_smoke.subprocess.Popen", HungWorker):
            with self.assertRaises(TimeoutError): self.run_smoke(timeout_seconds=.01)
        self.assertTrue(HungWorker.killed)
        self.assertEqual(read_json(self.root / "smoke/run_manifest.json")["status"], "timed_out")
        self.assertEqual(read_jsonl(self.root / "smoke/ocr_pages.jsonl")[0]["page_index"],0)

    def test_pending_image_and_changed_render_manifest_rejected(self):
        with self.assertRaisesRegex(ValueError, "not successfully rendered"):
            run_ocr_smoke(self.root / "render", self.models, self.root / "smoke", doc_id="report:one", page_index=1)
        path = self.root / "render/render_pages.jsonl"; path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"): self.run_smoke()


if __name__ == "__main__": unittest.main()
