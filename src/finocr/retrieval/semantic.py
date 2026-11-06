"""One preregistered development policy; no model/weight/window CLI switches.

The encoder sees only saved expanded questions and normalized source-page text.
Imports of optional numeric/runtime packages are lazy: baseline environments work
unchanged. Preparation downloads bytes only; it never calls a model forward pass.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import struct
import sys
import urllib.request

from finocr.io import read_json, write_json
from finocr.pipelines.report_rendering import file_identity

MODEL_REPO = "BAAI/bge-small-en-v1.5"
MODEL_REVISION = "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a"
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
DIMENSIONS, WINDOW_TOKENS, OVERLAP_TOKENS, BATCH_SIZE, RRF_CONSTANT = 384, 384, 64, 8, 60
MODEL_FILES = {
    "config.json": ("094f8e891b932f2000c92cfc663bac4c62069f5d8af5b5278c4306aef3084750", 743),
    "tokenizer.json": ("d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66", 711396),
    "vocab.txt": ("07eced375cec144d27c900241f3e339478dec958f92fddbc551f295c992038a3", 231508),
    "tokenizer_config.json": ("9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3", 366),
    "special_tokens_map.json": ("b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3", 125),
    "1_Pooling/config.json": ("d1caf60c96f5fba2157c0c26b76d80818fad6cf0b8eb5e73ec372ff9818eba5c", 190),
    "onnx/model.onnx": ("828e1496d7fabb79cfa4dcd84fa38625c0d3d21da474a00f08db0f559940cf35", 133093490),
}
RUNTIME_PINS = {"onnxruntime": "1.22.0", "tokenizers": "0.21.1", "numpy": "1.26.4", "psutil": "7.2.2"}
THREAD_ENV = {"OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
              "TOKENIZERS_PARALLELISM": "false"}


def policy_record():
    policy = {
        "version": "development-bge-small-onnx-rrf-v1", "model_repo": MODEL_REPO, "model_revision": MODEL_REVISION,
        "model_files": {n: {"sha256": h, "size_bytes": s} for n, (h, s) in MODEL_FILES.items()},
        "model_precision": "creator FP32 ONNX export; no quantization", "dimensions": DIMENSIONS,
        "tokenizer": "pinned tokenizer.json; WordPiece; built-in normalization; no extra normalization",
        "query": "instruction + saved expansion-v1 question; one query encoding shared by both representations",
        "query_instruction": QUERY_INSTRUCTION, "query_max_content_tokens": 510, "query_overflow": "reject; never truncate",
        "passage": "saved search_text only; no prefix, headings, labels, cross-page or cross-report context",
        "window_content_tokens": WINDOW_TOKENS, "window_overlap_tokens": OVERLAP_TOKENS,
        "window_end": "stop when end reaches page token count; no dropped tail or redundant trailing window",
        "special_tokens": {"CLS": 101, "SEP": 102, "PAD": 0}, "padding": "right; longest sequence within fixed batch",
        "pooling": "last_hidden_state[:,0,:] CLS; float32 L2 normalization",
        "similarity": "float32 cosine via fixed-order einsum; clip to [-1,1]; maximum window score per page",
        "window_tie": "earliest window index", "semantic_tie": "score descending, zero-based page ID ascending",
        "empty_page": "no windows; score -1; after every encoded page even at score -1; page ID ascending",
        "candidates": "every physical page of the question's report, including empty pages; no prefilter",
        "rrf": {"constant": RRF_CONSTANT, "bm25_weight": 1, "semantic_weight": 1, "rank_base": 1,
                "scope": "both complete page rankings", "tie": "unrounded score descending, zero-based page ID ascending"},
        "batch_size": BATCH_SIZE, "execution_order": "shared queries; native then OCR; saved report/page order; window start ascending",
        "provider": "CPUExecutionProvider only", "ort_execution": "sequential; intra-op 2, inter-op 1; deterministic compute",
        "ort_graph_optimization": "ORT_ENABLE_ALL", "thread_environment": THREAD_ENV, "runtime_pins": RUNTIME_PINS,
        "primary_k": 5, "diagnostic_ks": [1, 3, 5], "cohort": "original development pilot only",
    }
    data = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    return {**policy, "sha256": hashlib.sha256(data).hexdigest()}


def verify_model(directory):
    root = Path(directory).resolve()
    found = {}
    for name, (sha, size) in MODEL_FILES.items():
        identity = file_identity(root / name)
        if identity != {"sha256": sha, "size_bytes": size}:
            raise ValueError(f"Pinned encoder asset differs: {name}")
        found[name] = identity
    return found


def prepare_model(directory, *, progress=None):
    """New model directory, or reuse matching completed assets; never overwrite."""
    root = Path(directory).resolve(); root.mkdir(parents=True, exist_ok=True)
    for name, (sha, size) in MODEL_FILES.items():
        path = root / name
        if path.exists():
            if file_identity(path) != {"sha256": sha, "size_bytes": size}:
                raise ValueError(f"Existing encoder asset differs; preserve and use a new directory: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".download")
        if temporary.exists():
            raise FileExistsError(f"Preserve partial download and choose a new model directory: {temporary}")
        if progress: progress(f"Downloading pinned {name} ({size:,} bytes); no inference")
        url = f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{name}"
        with urllib.request.urlopen(url, timeout=60) as response, temporary.open("xb") as handle:
            while block := response.read(1024 * 1024): handle.write(block)
        if file_identity(temporary) != {"sha256": sha, "size_bytes": size}:
            raise ValueError(f"Downloaded encoder hash/size mismatch; partial retained: {temporary}")
        temporary.rename(path)
    assets = verify_model(root)
    record = {"status": "assets_verified_no_inference", "policy": policy_record(), "files": assets}
    manifest = root / "encoder_assets.json"
    if manifest.exists():
        if read_json(manifest) != record: raise ValueError("Existing encoder preparation record differs")
    else: write_json(manifest, record)
    return record


def token_windows(ids):
    """Return (start, end, content IDs); offsets exclude CLS/SEP."""
    start = 0
    while start < len(ids):
        end = min(start + WINDOW_TOKENS, len(ids))
        yield start, end, ids[start:end]
        if end == len(ids): break
        start = end - OVERLAP_TOKENS


def runtime_identity():
    if sys.version_info[:3] != (3, 12, 10) or platform.system() != "Windows" or struct.calcsize("P") != 8:
        raise ValueError("Fixed encoder condition requires Windows x64 / CPython 3.12.10")
    versions = {n: importlib.metadata.version(n) for n in RUNTIME_PINS}
    if versions != RUNTIME_PINS: raise ValueError(f"Encoder runtime pins differ: {versions}")
    if any(os.environ.get(k) != v for k, v in THREAD_ENV.items()):
        raise ValueError("Set the fixed encoder thread environment before importing numeric packages")
    return {"python": sys.version, "executable": sys.executable, "platform": platform.platform(),
            "processor": platform.processor(), "packages": versions, "thread_environment": dict(THREAD_ENV)}


def normalized_cls(hidden):
    import numpy as np
    values = np.asarray(hidden, dtype=np.float32)
    if values.ndim != 3 or values.shape[2] != DIMENSIONS or values.shape[1] < 1:
        raise ValueError("Encoder output shape differs from fixed CLS policy")
    cls = values[:, 0, :].copy()
    norm = np.sqrt(np.sum(cls * cls, axis=1, keepdims=True, dtype=np.float32))
    if not np.isfinite(cls).all() or not np.isfinite(norm).all() or (norm <= 0).any():
        raise ValueError("Encoder produced nonfinite/zero embedding")
    return np.ascontiguousarray(cls / norm, dtype=np.float32)


class BgeOnnxEncoder:
    def __init__(self, directory):
        self.identity = runtime_identity()
        self.assets = verify_model(directory)
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.tokenizer = Tokenizer.from_file(str(Path(directory) / "tokenizer.json"))
        self.tokenizer.no_truncation(); self.tokenizer.no_padding()
        if [self.tokenizer.token_to_id(t) for t in ("[PAD]", "[CLS]", "[SEP]")] != [0, 101, 102]:
            raise ValueError("Pinned tokenizer special IDs differ")
        opts = ort.SessionOptions()
        opts.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        opts.intra_op_num_threads, opts.inter_op_num_threads = 2, 1
        opts.use_deterministic_compute = True
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(Path(directory) / "onnx/model.onnx"), sess_options=opts,
                                           providers=["CPUExecutionProvider"])
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("Encoder silently changed execution provider")
        inputs = self.session.get_inputs(); outputs = self.session.get_outputs()
        if ({v.name: v.type for v in inputs} != {n: "tensor(int64)" for n in ("input_ids", "attention_mask", "token_type_ids")}
                or not any(v.name == "last_hidden_state" and v.type == "tensor(float)" for v in outputs)):
            raise ValueError("Pinned ONNX input/output contract differs")
        self.identity.update(ort_version=ort.__version__, providers=self.session.get_providers(),
                             input_schema=[{"name": v.name, "shape": v.shape, "type": v.type} for v in inputs],
                             output_schema=[{"name": v.name, "shape": v.shape, "type": v.type} for v in outputs])

    def token_ids(self, text):
        if not isinstance(text, str): raise TypeError("Encoder text must be a source/question string")
        return self.tokenizer.encode(text, add_special_tokens=False).ids

    def encode_ids(self, sequences):
        """Fixed batches; no query/passages mixed within a batch."""
        import numpy as np
        result = []
        for start in range(0, len(sequences), BATCH_SIZE):
            batch = sequences[start:start + BATCH_SIZE]
            if any(not s or len(s) > 510 for s in batch): raise ValueError("Invalid/overflowing encoder sequence")
            width = max(map(len, batch)) + 2
            ids = np.zeros((len(batch), width), dtype=np.int64); mask = np.zeros_like(ids)
            for row, content in enumerate(batch):
                values = [101, *content, 102]; ids[row, :len(values)] = values; mask[row, :len(values)] = 1
            hidden = self.session.run(["last_hidden_state"], {"input_ids": ids, "attention_mask": mask,
                                      "token_type_ids": np.zeros_like(ids)})[0]
            if len(hidden) != len(batch): raise ValueError("Encoder output batch coverage differs")
            result.append(normalized_cls(hidden))
        return np.concatenate(result, axis=0) if result else np.empty((0, DIMENSIONS), dtype=np.float32)


def semantic_rank(query_vector, vectors, windows, page_count):
    import numpy as np
    if vectors.shape != (len(windows), DIMENSIONS) or query_vector.shape != (DIMENSIONS,):
        raise ValueError("Semantic vector/window coverage differs")
    if not np.isfinite(vectors).all() or not np.isfinite(query_vector).all(): raise ValueError("Nonfinite similarity input")
    scores = np.clip(np.einsum("ij,j->i", vectors, query_vector, optimize=False), -1, 1)
    pages = [{"page_index": p, "score": -1.0, "empty": True, "best_window_index": None} for p in range(page_count)]
    for i, (window, score) in enumerate(zip(windows, scores)):
        p = window["page_index"]
        if type(p) is not int or not 0 <= p < page_count: raise ValueError("Window crosses report/page candidates")
        row = pages[p]
        if row["empty"] or float(score) > row["score"]:
            row.update(score=float(score), empty=False, best_window_index=window["window_index"])
    return sorted(pages, key=lambda r: (r["empty"], -r["score"], r["page_index"]))


def reciprocal_rank_fusion(bm25, semantic):
    def ranks(rows):
        result = {r["page_index"]: i for i, r in enumerate(rows, 1)}
        if len(result) != len(rows): raise ValueError("RRF duplicate page candidate")
        return result
    left, right = ranks(bm25), ranks(semantic)
    if not left or set(left) != set(right): raise ValueError("RRF candidate sets differ")
    rows = [{"page_index": p, "score": 1 / (RRF_CONSTANT + left[p]) + 1 / (RRF_CONSTANT + right[p]),
             "bm25_rank": left[p], "semantic_rank": right[p]} for p in left]
    return sorted(rows, key=lambda r: (-r["score"], r["page_index"]))
