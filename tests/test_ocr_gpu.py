"""Device isolation, synchronized worker timing, immutable comparison fixtures."""
import copy
import io
import json
import importlib.metadata
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import test_full_ocr as fixtures
from finocr.cli import main
from finocr.io import read_json, read_jsonl, write_json, write_jsonl
from finocr.pipelines.ocr_data import full_render
from finocr.pipelines.ocr_device import GPU_PACKAGE_PINS, device_condition, validate_worker_runtime
from finocr.pipelines.ocr_device_comparison import compare_ocr_devices
from finocr.pipelines.ocr_smoke import MODEL_NAMES, OCR_CONFIG, PACKAGE_PINS, create_ocr_engine
from finocr.pipelines.report_ocr import _worker, run_report_ocr, runtime_identity
from finocr.pipelines.report_rendering import file_identity


class GpuWorker(fixtures.FakeWorker):
    def __init__(self, models, session_dir, initialization_timeout, progress, device):
        super().__init__(models, session_dir, initialization_timeout, progress)
        self.ready["runtime"] = {"packages": GPU_PACKAGE_PINS, "paddle_device": device, "compiled_with_cuda": True, "cuda": "11.8"}
        write_json(session_dir / "ready.json", self.ready)


class GpuTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.FullOcrTests(); self.f.setUp()
        self.keys = (("report", 1), ("report", 2))
        _, _, inputs = full_render(self.f.render)
        self.selection = self.f.root / "selection.json"
        write_json(self.selection, {"policy": {"version": "source-financial-tables-v1"}, "inputs": inputs,
            "page_index_base": 0, "pages": [{"doc_id": d, "page_index": p} for d, p in self.keys]})
    def tearDown(self): self.f.tearDown()
    def gpu(self, **kwargs):
        with patch("finocr.pipelines.report_ocr.ReportWorker", GpuWorker), \
             patch("finocr.pipelines.report_ocr.runtime_identity", return_value={"python": "fixture", "bits": 64, "packages": GPU_PACKAGE_PINS}), \
             patch("finocr.pipelines.report_ocr.code_provenance", return_value={"python_source_sha256": "fixture"}):
            return run_report_ocr(self.f.render, self.f.models, self.f.root / "gpu", repository_root=self.f.root, device="gpu:0", **kwargs)
    def compare(self):
        with patch("finocr.pipelines.ocr_device_comparison.DIAGNOSTIC_KEYS", self.keys):
            return compare_ocr_devices(self.f.ocr, self.f.root / "gpu", self.selection, self.f.root / "device-comparison")

    def test_only_device_changes_configuration_and_cpu_constants_stay_fixed(self):
        old = copy.deepcopy(OCR_CONFIG)
        configuration, pins = device_condition("gpu:0")
        self.assertEqual({**configuration, "device": "cpu"}, old)
        self.assertEqual(device_condition("cpu"), (old, PACKAGE_PINS)); self.assertEqual(pins, GPU_PACKAGE_PINS)
        with self.assertRaisesRegex(ValueError, "devices"): device_condition("gpu:1")
        self.assertEqual(OCR_CONFIG, old)

    def test_gpu_device_and_cuda_mismatch_cannot_fall_back_to_cpu(self):
        runtime = {"packages": GPU_PACKAGE_PINS, "paddle_device": "gpu:0", "compiled_with_cuda": True, "cuda": "11.8"}
        validate_worker_runtime(runtime, "gpu:0")
        for bad in ({"paddle_device": "cpu"}, {"compiled_with_cuda": False}, {"cuda": "12.6"}):
            with self.assertRaises(ValueError): validate_worker_runtime({**runtime, **bad}, "gpu:0")

    def fake_engine_modules(self, cuda="11.8", returned_device="gpu:0"):
        gpu = SimpleNamespace(synchronize=Mock(), get_device_properties=Mock(return_value=SimpleNamespace(
            name="fixture RTX", total_memory=8*1024**3, major=8, minor=6)))
        paddle = SimpleNamespace(is_compiled_with_cuda=lambda:True, set_device=Mock(), seed=Mock(),
            version=SimpleNamespace(cuda=lambda:cuda, cudnn=lambda:"8.9.7"),
            device=SimpleNamespace(get_device=lambda:returned_device, cuda=gpu, synchronize=Mock()))
        ocr = SimpleNamespace(PaddleOCR=Mock(return_value=object()))
        def version(name):
            if name == "paddlepaddle": raise importlib.metadata.PackageNotFoundError(name)
            return GPU_PACKAGE_PINS[name]
        return paddle, ocr, version

    def test_engine_uses_same_models_fp32_settings_and_records_actual_cuda(self):
        paddle, ocr, version = self.fake_engine_modules()
        models = {name: str(self.f.models/name) for name in MODEL_NAMES}
        with patch.dict("sys.modules", {"paddle":paddle,"paddleocr":ocr}), \
             patch("finocr.pipelines.ocr_smoke.sys.version_info",(3,12,10)), \
             patch("finocr.pipelines.ocr_smoke.importlib.metadata.version",side_effect=version),patch("sys.stdout",io.StringIO()):
            _, runtime, _ = create_ocr_engine(models,device="gpu:0")
        kwargs=ocr.PaddleOCR.call_args.kwargs
        self.assertEqual({k:kwargs[k] for k in OCR_CONFIG},{**OCR_CONFIG,"device":"gpu:0"})
        self.assertEqual(kwargs["text_detection_model_dir"],models[MODEL_NAMES[0]])
        self.assertEqual(kwargs["text_recognition_model_dir"],models[MODEL_NAMES[1]])
        self.assertEqual(runtime["cuda"],"11.8");paddle.device.synchronize.assert_called_once_with("gpu:0")

    def test_engine_rejects_wrong_cuda_wheel_before_initializing_models(self):
        paddle, ocr, version = self.fake_engine_modules(cuda="12.6")
        with patch.dict("sys.modules", {"paddle":paddle,"paddleocr":ocr}), \
             patch("finocr.pipelines.ocr_smoke.sys.version_info",(3,12,10)), \
             patch("finocr.pipelines.ocr_smoke.importlib.metadata.version",side_effect=version),patch("sys.stdout",io.StringIO()):
            with self.assertRaisesRegex(RuntimeError,"CUDA 11.8"):create_ocr_engine({},device="gpu:0")
        ocr.PaddleOCR.assert_not_called()

    def test_mixed_cpu_gpu_environment_is_rejected_in_preflight(self):
        packages=[SimpleNamespace(metadata={"Name":k},version=v) for k,v in {**GPU_PACKAGE_PINS,"paddlepaddle":"3.3.0"}.items()]
        with patch("finocr.pipelines.report_ocr.sys.version_info",(3,12,10)), \
             patch("finocr.pipelines.report_ocr.importlib.metadata.distributions",return_value=packages), \
             patch("finocr.pipelines.report_ocr.importlib.metadata.version",side_effect=GPU_PACKAGE_PINS.__getitem__):
            with self.assertRaisesRegex(ValueError,"separate environments"):runtime_identity("gpu:0")

    def test_gpu_cache_has_full_source_plan_reuses_pages_and_rejects_cpu_resume(self):
        self.assertEqual(self.gpu(selection_path=self.selection)["status"], "diagnostic_complete")
        rows = read_jsonl(self.f.root / "gpu/ocr_pages.jsonl")
        self.assertEqual(len(rows), 9); self.assertTrue(all(r["device"] == "gpu:0" for r in rows))
        old = (self.f.root / "gpu" / rows[1]["record_path"]).read_bytes()
        calls = len(fixtures.FakeWorker.calls); self.gpu(selection_path=self.selection, resume=True)
        self.assertEqual(calls, len(fixtures.FakeWorker.calls))
        self.assertEqual((self.f.root / "gpu" / rows[1]["record_path"]).read_bytes(), old)
        self.f.ocr = self.f.root / "gpu"
        with self.assertRaisesRegex(ValueError, "resume inputs/configuration"): self.f.run_ocr(resume=True)

    def test_comparison_checks_same_images_raw_outputs_and_leaves_approval_pending(self):
        self.f.run_ocr(selection_path=self.selection); self.gpu(selection_path=self.selection)
        before = file_identity(self.f.ocr / "run_manifest.json")
        result = self.compare()
        self.assertEqual(result["status"], "awaiting_manual_review"); self.assertEqual(result["raw_text_equal_pages"], 2)
        self.assertEqual(result["numeric_multisets_equal_pages"], 2)
        self.assertIn("pending review", result["full_gpu_recommendation"])
        self.assertEqual(file_identity(self.f.ocr / "run_manifest.json"), before)
        report = (self.f.root / "device-comparison/device_comparison.md").read_text()
        self.assertIn("full GPU execution is pending review", report)
        self.assertNotIn("NEVER_LEAK", json.dumps(result))

    def test_numeric_and_text_difference_are_reported_without_accuracy_claims(self):
        self.f.run_ocr(selection_path=self.selection)
        original = GpuWorker.page
        def different(worker, image, identity, directory, timeout):
            result = original(worker, image, identity, directory, timeout)
            raw = read_json(directory / "raw_ocr_result.json")
            raw["rec_texts"] = [t.replace("(1,234)", "1,234").replace("2022", "2023") for t in raw["rec_texts"]]
            write_json(directory / "raw_ocr_result.json", raw)
            result["normalized"] = fixtures.normalize_ocr_result(raw); write_json(directory / "worker_result.json", result)
            return result
        with patch.object(GpuWorker, "page", different): self.gpu(selection_path=self.selection)
        result = self.compare()
        self.assertEqual(result["raw_text_equal_pages"], 1); self.assertEqual(result["numeric_multisets_equal_pages"], 1)
        detail = result["pages"][1]
        self.assertIn("(1,234)", detail["cpu_only_numeric_tokens"]); self.assertIn("2023", detail["gpu_only_numeric_tokens"])
        self.assertIn("not CER/WER", result["interpretation"])

    def test_raw_tampering_and_settings_change_block_comparison(self):
        self.f.run_ocr(selection_path=self.selection); self.gpu(selection_path=self.selection)
        row = read_jsonl(self.f.root / "gpu/ocr_pages.jsonl")[1]
        raw = (self.f.root / "gpu" / row["record_path"]).parent / "raw_ocr_result.json"
        data = raw.read_bytes(); raw.write_bytes(data+b"\n")
        with self.assertRaisesRegex(ValueError, "checksum"): self.compare()
        raw.write_bytes(data)
        path = self.f.root / "gpu/run_manifest.json"; m = read_json(path);m["contract"]["configuration"]["precision"] = "fp16";write_json(path,m)
        with self.assertRaisesRegex(ValueError, "configuration"): self.compare()

    def test_changed_nonframework_dependency_blocks_device_comparison(self):
        self.f.run_ocr(selection_path=self.selection); self.gpu(selection_path=self.selection)
        cpu=self.f.ocr/'run_manifest.json';gpu=self.f.root/'gpu/run_manifest.json'
        for path,version in ((cpu,'old'),(gpu,'changed')):
            m=read_json(path);m['contract']['runtime']['packages']['numpy']=version;write_json(path,m)
            # No page attempts are rewritten; the immutable runtime checks reject this too.
        with self.assertRaises(ValueError):self.compare()

    def test_failed_gpu_page_is_explicit_and_prevents_full_recommendation(self):
        self.f.run_ocr(selection_path=self.selection)
        fixtures.FakeWorker.malformed_page = ("report", 2); self.gpu(selection_path=self.selection)
        result = self.compare(); self.assertEqual(result["status"], "diagnostic_failures")
        self.assertEqual(result["pages"][1]["gpu_status"], "failed")

    def test_full_gpu_cache_retrieval_reproduces_expansion_control(self):
        self.gpu(); self.f.ocr = self.f.root / "gpu"; self.f.compare()
        manifest = read_json(self.f.root / "comparison/run_manifest.json")
        self.assertTrue(manifest["expansion_control_reproduced"]); self.assertEqual(manifest["ocr_device"], "gpu:0")
        self.assertEqual(len(read_jsonl(self.f.root / "comparison/index_stats.jsonl")), 4)

    def test_gpu_worker_synchronizes_each_page_and_initializes_once(self):
        root = self.f.root; session = root / "worker-session";session.mkdir()
        startup = root / "startup.json";write_json(startup,{"session_dir":str(session),"model_paths":{},"device":"gpu:0"})
        image = next(self.f.render.rglob("*.png")); requests=[]
        for i in range(2):
            destination=root/f"worker-out-{i}";destination.mkdir()
            requests.append({"image":str(image),"image_identity":file_identity(image),"output":str(destination)})
        class Engine:
            def predict(self, image): return [SimpleNamespace(json={"rec_texts":["-12.5%"],"rec_scores":[.9],"rec_polys":[[[0,0],[1,0],[1,1],[0,1]]]})]
        stream=io.StringIO("\n".join(json.dumps(r) for r in [*requests,{"stop":True}])+"\n")
        with patch("finocr.pipelines.report_ocr.create_ocr_engine",return_value=(Engine(),{},.01)) as engine, \
             patch("finocr.pipelines.report_ocr.synchronize") as synchronize, patch("finocr.pipelines.report_ocr.sys.stdin",stream): _worker(startup)
        engine.assert_called_once_with({},device="gpu:0");self.assertEqual(synchronize.call_count,4)

    def test_cli_device_comparison_routes_to_read_only_comparator(self):
        result={"status":"awaiting_manual_review","page_count":8,"raw_text_equal_pages":8,"numeric_multisets_equal_pages":8,"full_gpu_recommendation":"pending"}
        with patch("finocr.pipelines.ocr_device_comparison.compare_ocr_devices",return_value=result) as compare,patch("sys.stdout",io.StringIO()):
            self.assertEqual(main(["compare-ocr-devices","--cpu-dir","c","--gpu-dir","g","--selection","s","--output-dir","o"]),0)
        compare.assert_called_once_with("c","g","s","o")
