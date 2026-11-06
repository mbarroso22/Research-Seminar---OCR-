from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np

from finocr.cli import main
from finocr.io import read_json, read_jsonl, write_json
from finocr.pipelines import hybrid_comparison as pipeline
from finocr.pipelines.native_baseline import load_evidence_labels
from finocr.pipelines.report_rendering import file_identity
from finocr.retrieval import semantic as sem
import test_full_ocr as fixtures


class SemanticPolicyTests(unittest.TestCase):
    def test_fixed_policy_contains_no_sweep_and_exact_assets(self):
        p = sem.policy_record()
        self.assertEqual(p["model_revision"], "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a")
        self.assertEqual(p["window_content_tokens"], 384); self.assertEqual(p["window_overlap_tokens"], 64)
        self.assertEqual(p["rrf"]["constant"], 60); self.assertEqual(p["rrf"]["bm25_weight"], p["rrf"]["semantic_weight"])
        self.assertEqual(len(p["model_files"]), 7); self.assertEqual(p, sem.policy_record())

    def test_windows_cover_every_token_once_or_overlap_without_tail_loss(self):
        for n in (0, 1, 384, 385, 704, 705, 1500):
            with self.subTest(n=n):
                source = list(range(n)); windows = list(sem.token_windows(source))
                self.assertEqual(set(t for _, _, ids in windows for t in ids), set(source))
                for i, (a, b, ids) in enumerate(windows):
                    self.assertEqual(ids, source[a:b]); self.assertLessEqual(len(ids), 384)
                    if i: self.assertEqual(a, windows[i-1][1]-64)
                if windows: self.assertEqual(windows[-1][1], n)
                self.assertEqual(len(windows), 1 if 0 < n <= 384 else 0 if n == 0 else (n-384+319)//320+1)

    def test_cls_pooling_and_l2_are_not_mean_pooling(self):
        hidden = np.zeros((2, 3, 384), np.float32)
        hidden[:, 0, :2] = [3, 4]; hidden[:, 1:, 3] = 100
        result = sem.normalized_cls(hidden)
        np.testing.assert_allclose(result[:, :2], [[.6, .8], [.6, .8]], atol=1e-7)
        self.assertEqual(result.dtype, np.float32); self.assertTrue((result[:, 2:] == 0).all())

    def test_nonfinite_zero_and_wrong_output_rejected(self):
        for value in (np.zeros((1, 2, 384)), np.ones((1, 2, 383)), np.full((1, 2, 384), np.nan), np.full((1, 2, 384), np.inf)):
            with self.assertRaises(ValueError): sem.normalized_cls(value)

    def test_max_window_page_aggregation_keeps_blank_candidates_last(self):
        q = np.zeros(384, np.float32); q[0] = 1
        vectors = np.zeros((4, 384), np.float32); vectors[:, 0] = [-.7, .4, .4, .4]
        windows = [{"page_index": p, "window_index": w} for p, w in [(0, 0), (0, 1), (0, 2), (2, 0)]]
        rows = sem.semantic_rank(q, vectors, windows, 4)
        self.assertEqual([r["page_index"] for r in rows], [0, 2, 1, 3])
        self.assertEqual(rows[0]["best_window_index"], 1); self.assertEqual(len(rows), 4)
        vectors[:, 0] = -1
        self.assertEqual([r["page_index"] for r in sem.semantic_rank(q, vectors, windows, 4)], [0, 2, 1, 3])

    def test_semantic_rejects_wrong_vector_coverage_or_nonfinite_scores(self):
        q = np.ones(384, np.float32)
        with self.assertRaises(ValueError): sem.semantic_rank(q, np.ones((1, 384)), [], 1)
        with self.assertRaises(ValueError): sem.semantic_rank(q * np.nan, np.empty((0, 384)), [], 1)
        with self.assertRaises(ValueError): sem.semantic_rank(q, np.ones((1, 384)), [{"page_index": 1, "window_index": 0}], 1)

    def test_rrf_uses_full_rank_lists_equal_weights_and_page_id_ties(self):
        a = [{"page_index": p, "score": 100-p} for p in [2, 0, 1, 3, 4, 5, 6]]
        b = [{"page_index": p, "score": -p} for p in [0, 2, 1, 3, 4, 5, 6]]
        result = sem.reciprocal_rank_fusion(a, b)
        self.assertEqual([r["page_index"] for r in result], [0, 2, 1, 3, 4, 5, 6])
        self.assertEqual(result[0]["score"], 1/61+1/62); self.assertEqual(result[-1]["score"], 2/67)
        self.assertEqual(result[0]["bm25_rank"], 2); self.assertEqual(result[0]["semantic_rank"], 1)
        self.assertEqual(sem.reciprocal_rank_fusion(a, b)[0]["score"], sem.reciprocal_rank_fusion(b, a)[0]["score"])

    def test_rrf_rejects_missing_or_duplicate_candidates(self):
        a = [{"page_index": p} for p in (0, 1)]
        for b in ([{"page_index": 0}], [{"page_index": 0}, {"page_index": 0}], []):
            with self.assertRaises(ValueError): sem.reciprocal_rank_fusion(a, b)

    def test_model_preparation_verifies_bytes_and_never_overwrites(self):
        import hashlib
        content = b"fixture model, never executed"
        files = {"onnx/model.onnx": (hashlib.sha256(content).hexdigest(), len(content))}
        with tempfile.TemporaryDirectory() as temp, patch.object(sem, "MODEL_FILES", files), \
             patch.object(sem.urllib.request, "urlopen", return_value=contextlib.closing(io.BytesIO(content))) as download:
            self.assertEqual(sem.prepare_model(temp)["status"], "assets_verified_no_inference")
            sem.prepare_model(temp); self.assertEqual(download.call_count, 1)
            path = Path(temp) / "onnx/model.onnx"; path.write_bytes(b"altered")
            with self.assertRaisesRegex(ValueError, "Existing encoder asset differs"): sem.prepare_model(temp)
            self.assertEqual(path.read_bytes(), b"altered")

    def test_wrong_download_retained_and_cannot_be_silently_retried(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(sem, "MODEL_FILES", {"model": ("0" * 64, 4)}), \
             patch.object(sem.urllib.request, "urlopen", side_effect=lambda *a, **k: contextlib.closing(io.BytesIO(b"bad!"))):
            with self.assertRaisesRegex(ValueError, "hash/size mismatch"): sem.prepare_model(temp)
            self.assertEqual((Path(temp) / "model.download").read_bytes(), b"bad!")
            with self.assertRaises(FileExistsError): sem.prepare_model(temp)

    def test_optional_encoder_dependencies_are_not_needed_for_existing_cli(self):
        with patch.dict(sys.modules, {"onnxruntime": None, "tokenizers": None}):
            from finocr.cli import build_parser
            args = build_parser().parse_args(["prepare-hybrid-encoder", "--models-dir", "unused"])
            self.assertEqual(args.models_dir, "unused")

    def test_backend_fixed_batch_padding_masks_provider_and_cls(self):
        calls, sessions = [], []
        def node(name, kind="tensor(int64)"): return types.SimpleNamespace(name=name, type=kind, shape=["batch", "tokens"])
        class Tokenizer:
            @classmethod
            def from_file(cls, path): return cls()
            def no_truncation(self): pass
            def no_padding(self): pass
            def token_to_id(self, t): return {"[PAD]": 0, "[CLS]": 101, "[SEP]": 102}[t]
            def encode(self, text, add_special_tokens):
                if add_special_tokens: raise AssertionError("Specials must be added exactly once")
                return types.SimpleNamespace(ids=[7, 8])
        class Session:
            def __init__(self, path, **kwargs): sessions.append(kwargs)
            def get_providers(self): return ["CPUExecutionProvider"]
            def get_inputs(self): return [node(n) for n in ("input_ids", "attention_mask", "token_type_ids")]
            def get_outputs(self): return [node("last_hidden_state", "tensor(float)")]
            def run(self, names, values):
                calls.append(values)
                result = np.zeros((*values["input_ids"].shape, 384), np.float32); result[:, 0, 0] = 3; result[:, 0, 1] = 4
                return [result]
        ort = types.SimpleNamespace(SessionOptions=types.SimpleNamespace, InferenceSession=Session, __version__="1.22.0",
                                    ExecutionMode=types.SimpleNamespace(ORT_SEQUENTIAL=1), GraphOptimizationLevel=types.SimpleNamespace(ORT_ENABLE_ALL=99))
        with patch.dict(sys.modules, {"onnxruntime": ort, "tokenizers": types.SimpleNamespace(Tokenizer=Tokenizer)}), \
             patch.object(sem, "runtime_identity", return_value={}), patch.object(sem, "verify_model", return_value={}):
            encoder = sem.BgeOnnxEncoder("unused"); self.assertEqual(encoder.token_ids("source only"), [7, 8])
            result = encoder.encode_ids([[7], [7, 8]] * 5)
            self.assertEqual([len(c["input_ids"]) for c in calls], [8, 2])
            np.testing.assert_array_equal(calls[0]["input_ids"][0], [101, 7, 102, 0])
            np.testing.assert_array_equal(calls[0]["attention_mask"][0], [1, 1, 1, 0])
            self.assertEqual(calls[0]["input_ids"].dtype, np.int64); self.assertFalse(calls[0]["token_type_ids"].any())
            np.testing.assert_allclose(result[0, :2], [.6, .8], atol=1e-7)
            self.assertEqual(sessions[0]["providers"], ["CPUExecutionProvider"])
            self.assertEqual(sessions[0]["sess_options"].intra_op_num_threads, 2)
            with self.assertRaises(ValueError): encoder.encode_ids([[1] * 511])


class FakeEncoder:
    seen = []; overflow = False; fail = False
    identity = {"fixture": "mocked transport; no encoder model executed"}
    def __init__(self, directory):
        if self.fail: raise RuntimeError("fixture encoder initialization failure")
    def token_ids(self, text):
        self.seen.append(text)
        if self.overflow and text.startswith(sem.QUERY_INSTRUCTION): return [1] * 511
        return [sum(word.encode()) % 100 for word in text.split()]
    def encode_ids(self, sequences):
        result = np.zeros((len(sequences), 384), np.float32)
        for i, seq in enumerate(sequences):
            for token in seq: result[i, token] += 1
        if len(sequences): result /= np.linalg.norm(result, axis=1, keepdims=True)
        return result


class FakeMemory:
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def record(self): return {"mock": True}


class HybridPipelineTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.FullOcrTests(); self.fx.setUp(); self.addCleanup(self.fx.tearDown)
        self.fx.run_ocr(); self.fx.compare(); self.output = self.fx.root / "hybrid"
        self.spec = {"native_manifest": file_identity(self.fx.native / "run_manifest.json")["sha256"],
                     "ocr_manifest": file_identity(self.fx.ocr / "run_manifest.json")["sha256"],
                     "reference_manifest": file_identity(self.fx.root / "comparison/run_manifest.json")["sha256"],
                     "tasks": file_identity(self.fx.tasks)["sha256"], "totals": {"documents": 2, "pages": 9, "questions": 3}, "ocr_device": "cpu"}
        FakeEncoder.seen = []; FakeEncoder.overflow = False; FakeEncoder.fail = False
        self.before = {p: p.read_bytes() for p in self.fx.root.rglob("*") if p.is_file()}

    def run_comparison(self, **kwargs):
        with patch.object(pipeline, "PILOT", self.spec), patch.object(pipeline, "BgeOnnxEncoder", FakeEncoder), \
             patch.object(pipeline, "verify_model", return_value={}), patch.object(pipeline, "MemorySample", FakeMemory):
            return pipeline.compare_hybrid(self.fx.native, self.fx.root / "comparison", self.fx.ocr, self.fx.tasks,
                                           self.fx.models, self.output, repository_root=self.fx.root / "code", **kwargs)

    def test_matched_full_run_labels_only_after_six_rankings_and_no_leakage(self):
        def labels(path):
            for c in pipeline.CONDITIONS:
                for m in pipeline.METHODS: self.assertTrue((self.output / f"{c}_{m}_predictions.jsonl").is_file())
            return load_evidence_labels(path)
        with patch.object(pipeline, "load_evidence_labels", side_effect=labels): result = self.run_comparison()
        self.assertEqual(result["status"], "complete"); self.assertFalse(result["development_gate"]["pass"])
        for c in pipeline.CONDITIONS:
            old = read_jsonl(self.fx.root / "comparison" / f"{c}_predictions.jsonl")
            new = read_jsonl(self.output / f"{c}_bm25_predictions.jsonl")
            self.assertEqual([r["ranked_pages"] for r in new], [r["ranked_pages"] for r in old])
            for m in pipeline.METHODS:
                rows = read_jsonl(self.output / f"{c}_{m}_predictions.jsonl")
                for row in rows: self.assertEqual(set(r["page_index"] for r in row["ranked_pages"]), set(range(7)))
        self.assertFalse(any("NEVER_LEAK" in text for text in FakeEncoder.seen))
        self.assertTrue(any("other source" in text.casefold() for text in FakeEncoder.seen))  # unannotated report still encoded
        metrics = read_json(self.output / "comparison_metrics.json")
        self.assertEqual(metrics["paired"]["native"]["hybrid"]["multipage"]["question_count"], 1)
        self.assertEqual(len(metrics["paired"]["ocr"]["semantic"]["questions"]), 3)
        self.assertEqual(set(metrics["native_vs_ocr"]), set(pipeline.METHODS))
        manifest = read_json(self.output / "run_manifest.json")
        for name, identity in manifest["artifacts"].items(): self.assertEqual(file_identity(self.output / name), identity)
        self.assertTrue(read_json(self.output / "input_preservation.json")["all_match"])
        for path, data in self.before.items(): self.assertEqual(path.read_bytes(), data)

    def test_check_only_replays_controls_without_encoder_dependencies_or_labels(self):
        with patch.object(pipeline, "load_evidence_labels", side_effect=AssertionError("No labels allowed")):
            result = self.run_comparison(check_only=True)
        self.assertEqual(result["status"], "inputs_verified_no_encoder"); self.assertEqual(FakeEncoder.seen, [])
        self.assertFalse((self.output / "comparison_metrics.json").exists())

    def test_nonoriginal_or_inspected_cohort_is_rejected_before_encoding(self):
        self.spec["native_manifest"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "Not the frozen original"): self.run_comparison()
        self.assertFalse(FakeEncoder.seen); self.assertEqual(read_json(self.output / "run_manifest.json")["status"], "failed")

    def test_corrupt_raw_ocr_is_rejected_before_encoding(self):
        page = read_jsonl(self.fx.ocr / "ocr_pages.jsonl")[0]
        raw = (self.fx.ocr / page["record_path"]).parent / "raw_ocr_result.json"; raw.write_bytes(raw.read_bytes()+b"\n")
        with self.assertRaisesRegex(ValueError, "checksum"): self.run_comparison()
        self.assertFalse(FakeEncoder.seen)

    def test_wrong_saved_control_or_queries_cannot_pass_replay(self):
        # After fixture anchor replacement, a changed control still fails its
        # artifact hash, or replay if the fixture manifest is rehashed as well.
        reference = self.fx.root / "comparison"; path = reference / "native_predictions.jsonl"
        rows = read_jsonl(path); rows[0]["ranked_pages"][0]["score"] += .01
        from finocr.io import write_jsonl
        write_jsonl(path, rows)
        manifest = read_json(reference / "run_manifest.json"); manifest["artifacts"][path.name] = file_identity(path)
        write_json(reference / "run_manifest.json", manifest); self.spec["reference_manifest"] = file_identity(reference / "run_manifest.json")["sha256"]
        with self.assertRaisesRegex(ValueError, "Control ranking failed reproduction"): self.run_comparison()
        self.assertFalse(FakeEncoder.seen)

    def test_query_overflow_fails_without_silent_truncation_or_metrics(self):
        FakeEncoder.overflow = True
        with self.assertRaisesRegex(ValueError, "no silent truncation"): self.run_comparison()
        self.assertFalse((self.output / "comparison_metrics.json").exists())
        self.assertEqual(read_json(self.output / "run_manifest.json")["status"], "failed")

    def test_encoder_failure_retains_replayed_controls_and_failed_manifest(self):
        FakeEncoder.fail = True
        with self.assertRaisesRegex(RuntimeError, "fixture encoder"): self.run_comparison()
        self.assertTrue((self.output / "ocr_bm25_predictions.jsonl").is_file())
        self.assertFalse((self.output / "comparison_metrics.json").exists())
        self.assertEqual(read_json(self.output / "run_manifest.json")["stage"], "semantic_encoding")

    def test_existing_output_cannot_be_overwritten(self):
        self.output.mkdir(); (self.output / "retained").write_text("original")
        with self.assertRaises(FileExistsError): self.run_comparison()
        self.assertEqual((self.output / "retained").read_text(), "original")

    def test_cli_negative_gate_is_successful_execution_and_failure_is_nonzero(self):
        args = ["compare-hybrid-retrieval"]
        for name in ("native-dir", "reference-dir", "ocr-dir", "tasks", "models-dir", "output-dir"): args += ["--"+name, "unused"]
        with patch.object(pipeline, "compare_hybrid", return_value={"status": "complete", "development_gate": {"pass": False}}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        with patch.object(pipeline, "compare_hybrid", side_effect=ValueError("bad input")), contextlib.redirect_stderr(io.StringIO()):
            self.assertNotEqual(main(args), 0)

    def test_gate_requires_all_conditions_not_semantic_winner(self):
        def result(recall, complete, multipage):
            return {"question_count": 24, "at_k": {"5": {"macro_evidence_recall": recall}}, "per_question": [
                {"gold_page_count": 2 if i < 5 else 1, "at_k": {"5": {"all_evidence_coverage": int(i in complete)}}} for i in range(24)]}
        metrics = {c: {"bm25": result(.4, set(), False), "hybrid": result(.5, set(range(10)), True)} for c in pipeline.CONDITIONS}
        self.assertTrue(pipeline.development_gate(metrics)["pass"])
        metrics["ocr"]["hybrid"]["at_k"]["5"]["macro_evidence_recall"] = .4
        self.assertFalse(pipeline.development_gate(metrics)["pass"])
        metrics["ocr"]["hybrid"] = result(.5, set(range(5, 15)), False)
        self.assertFalse(pipeline.development_gate(metrics)["pass"])


if __name__ == "__main__": unittest.main()
