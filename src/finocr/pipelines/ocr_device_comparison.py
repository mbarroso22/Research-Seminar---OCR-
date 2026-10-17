"""Read-only, source-only eight-page CPU/GPU inspection; no retrieval labels."""
from __future__ import annotations

from collections import Counter
from difflib import unified_diff
from pathlib import Path

from finocr.io import read_json, read_jsonl, write_json
from finocr.pipelines.ocr_data import COMPLETED, SOURCE_FIELDS, coverage, full_render, inside, require, validate_text_record
from finocr.pipelines.ocr_device import device_condition, validate_worker_runtime
from finocr.pipelines.ocr_tables import NUMBER
from finocr.pipelines.report_ocr import validate_commit
from finocr.pipelines.report_rendering import file_identity

DIAGNOSTIC_KEYS = tuple((f"financebench:{name}_2015_10K", page) for name, pages in
                        (("AMD", (55, 57)), ("BESTBUY", (58, 60)), ("BOEING", (50, 52)), ("PEPSICO", (73, 76))) for page in pages)


def validate_diagnostic(directory, selection, device):
    root = Path(directory).resolve(); manifest = read_json(root / "run_manifest.json")
    require(manifest["stage"] == "full_report_ocr" and manifest["mode"] == "diagnostic"
            and manifest["status"] in {"diagnostic_complete", "diagnostic_partial"}, "Use a retained diagnostic snapshot, not a live/full cache")
    for name, identity in manifest["artifacts"].items():
        require(file_identity(inside(root, name)) == identity, f"Diagnostic artifact checksum changed: {name}")
    contract = manifest["contract"]; configuration, pins = device_condition(device)
    require(contract["configuration"] == configuration and contract["package_pins"] == pins,
            "Diagnostic configuration differs from its fixed device condition")
    packages = contract["runtime"]["packages"]
    opposite = "paddlepaddle-gpu" if device == "cpu" else "paddlepaddle"
    require(all(packages.get(k) == v for k, v in pins.items()) and opposite not in packages,
            "Diagnostic package inventory differs from fixed device pins")
    _, plans, identities = full_render(root / "source-render")
    require(all(contract[k] == v for k, v in identities.items())
            and all(selection["inputs"][k] == v for k, v in identities.items()), "Diagnostic rendering/selection lineage differs")
    keys = [(r["doc_id"], r["page_index"]) for r in selection["pages"]]
    require(tuple(keys) == DIAGNOSTIC_KEYS and selection["page_index_base"] == 0
            and selection["policy"]["version"] == "source-financial-tables-v1", "Use the same eight predeclared source table pages")
    rows = read_jsonl(root / "ocr_pages.jsonl")
    require([(r["doc_id"], r["page_index"]) for r in rows] == [(r["doc_id"], r["page_index"]) for r in plans],
            "Diagnostic full-report candidate accounting changed")
    chosen = {}
    for row, plan in zip(rows, plans):
        validate_text_record(row)
        require(all(row[k] == plan[k] for k in (*SOURCE_FIELDS, "image_path")) and row["device"] == device,
                "Diagnostic source/page/device mapping changed")
        key = row["doc_id"], row["page_index"]
        if key not in keys:
            require(row["status"] == "pending" and row["attempt_count"] == 0, "Unexpected extra diagnostic page attempt")
            continue
        require(row["status"] != "pending", "Selected diagnostic page remains pending")
        require(row["attempt_count"] == len(row["attempt_history"]) and row["attempt_count"] > 0, "Diagnostic attempt history changed")
        for number, relative in enumerate(row["attempt_history"], 1):
            path = inside(root, relative + "/record.json")
            committed = validate_commit(root, path, plan, contract, manifest["run_id"])
            require(committed["attempt_history"] == row["attempt_history"][:number], "Diagnostic history prefix differs")
        require(committed == row and file_identity(inside(root, row["record_path"])) == row["record_identity"],
                "Diagnostic aggregate differs from its immutable commit")
        chosen[key] = row
    for path in (root / "sessions").glob("*/ready.json"):
        ready = read_json(path)
        if ready["status"] == "ready": validate_worker_runtime(ready["runtime"], device)
    require(coverage(rows) == manifest["coverage"] and not manifest["full_ocr_coverage"], "Diagnostic coverage declaration differs")
    return manifest, chosen


def compare_ocr_devices(cpu_dir, gpu_dir, selection_path, output_dir):
    cpu_root, gpu_root, output = (Path(p).resolve() for p in (cpu_dir, gpu_dir, output_dir))
    require(all(output != p and p not in output.parents and output not in p.parents for p in (cpu_root, gpu_root)),
            "Device comparison output must be separate from both caches")
    if output.exists(): raise FileExistsError("Use a new immutable device-comparison directory")
    selection = read_json(selection_path)
    identities = {"selection": file_identity(selection_path), "cpu_manifest": file_identity(cpu_root / "run_manifest.json"),
                  "gpu_manifest": file_identity(gpu_root / "run_manifest.json")}
    cpu, before = validate_diagnostic(cpu_root, selection, "cpu")
    gpu, after = validate_diagnostic(gpu_root, selection, "gpu:0")
    for name in ("render_manifest", "render_pages", "render_contract", "model_manifest", "page_timeout_seconds", "initialization_timeout_seconds"):
        require(cpu["contract"][name] == gpu["contract"][name], f"CPU/GPU fixed input/settings differ: {name}")
    a, b = cpu["contract"]["runtime"], gpu["contract"]["runtime"]
    package_differences = {k: {"cpu": a["packages"].get(k), "gpu": b["packages"].get(k)}
        for k in sorted(set(a["packages"]) | set(b["packages"])) if a["packages"].get(k) != b["packages"].get(k)}
    require(a["python"] == b["python"] and a["bits"] == b["bits"] == 64, "Match the CPU Python 3.12.10 x64 runtime")
    require(all(k in {"paddlepaddle", "paddlepaddle-gpu"} or d["cpu"] is None for k, d in package_differences.items()),
            "Non-framework CPU dependency versions changed; preserve the reference pins")
    details, diffs = [], {}
    for key in DIAGNOSTIC_KEYS:
        n, g = before[key], after[key]
        nc, gc = Counter(NUMBER.findall(n["search_text"])), Counter(NUMBER.findall(g["search_text"]))
        same_lines = [r["text"] for r in n["lines"]] == [r["text"] for r in g["lines"]]
        confidences = [abs(x["confidence"]-y["confidence"]) for x, y in zip(n["lines"], g["lines"])
                       if x["confidence"] is not None and y["confidence"] is not None] if same_lines else []
        details.append({"doc_id": key[0], "page_index": key[1], "page_index_base": 0,
            "image_identity": n["image_identity"], "cpu_status": n["status"], "gpu_status": g["status"],
            "raw_text_equal": n["raw_text"] == g["raw_text"], "search_text_equal": n["search_text"] == g["search_text"],
            "normalized_lines_equal": n["lines"] == g["lines"], "line_text_order_equal": same_lines,
            "line_polygon_order_equal": [r["polygon"] for r in n["lines"]] == [r["polygon"] for r in g["lines"]],
            "raw_json_equal": n["attempt_artifacts"].get("raw_ocr_result.json") is not None
                              and n["attempt_artifacts"].get("raw_ocr_result.json") == g["attempt_artifacts"].get("raw_ocr_result.json"),
            "cpu_line_count": len(n["lines"]), "gpu_line_count": len(g["lines"]),
            "max_aligned_confidence_difference": max(confidences) if confidences else None,
            "numeric_multisets_equal": nc == gc, "cpu_only_numeric_tokens": list((nc-gc).elements()),
            "gpu_only_numeric_tokens": list((gc-nc).elements()),
            "cpu_record": n["record_path"], "gpu_record": g["record_path"],
            "cpu_page_seconds": n["inference_and_serialization_seconds"], "gpu_page_seconds": g["inference_and_serialization_seconds"],
            "cpu_attempt_count": n["attempt_count"], "gpu_attempt_count": g["attempt_count"]})
        filename = f"page-{len(details):02d}-text.diff"
        diffs[filename] = "".join(unified_diff(n["raw_text"].splitlines(True), g["raw_text"].splitlines(True),
                                             fromfile="cpu raw text", tofile="gpu raw text"))
        details[-1]["text_diff"] = filename
    ready = all(r["status"] in COMPLETED for r in (*before.values(), *after.values()))
    result = {"schema_version": 1, "status": "awaiting_manual_review" if ready else "diagnostic_failures",
        "interpretation": "source-only output/timing comparison; not CER/WER, financial accuracy, retrieval or a device-isolated speedup benchmark",
        "full_gpu_recommendation": "pending review of real diagnostic outputs and financial signs/year/units/column associations",
        "inputs": identities, "package_differences": package_differences,
        "cpu_code": cpu["code"], "gpu_code": gpu["code"], "page_count": len(details), "pages": details,
        "raw_text_equal_pages": sum(r["raw_text_equal"] for r in details),
        "numeric_multisets_equal_pages": sum(r["numeric_multisets_equal"] for r in details),
        "timing": {"cpu_cumulative": cpu["timing"], "gpu_cumulative": gpu["timing"],
                   "cpu_latest_selected_page_seconds": sum(r["cpu_page_seconds"] or 0 for r in details),
                   "gpu_latest_selected_page_seconds": sum(r["gpu_page_seconds"] or 0 for r in details),
                   "policy": "synchronized GPU page timing, same eight pages and per-report initialization; first-run/retry histories retained; different machines and uncontrolled load may confound timing"}}
    output.mkdir(parents=True)
    for name, diff in diffs.items(): (output / name).write_text(diff, encoding="utf-8")
    for number, key in enumerate(DIAGNOSTIC_KEYS, 1):
        name = f"page-{number:02d}-lines.json"
        write_json(output / name, {"doc_id": key[0], "page_index": key[1], "cpu_lines": before[key]["lines"], "gpu_lines": after[key]["lines"]})
        result["pages"][number-1]["line_comparison"] = name
    write_json(output / "device_comparison.json", result)
    lines = ["# Eight-page CPU/GPU diagnostic", "", f"Status: {result['status']}; full GPU execution is pending review.",
        f"Exact raw text: {result['raw_text_equal_pages']}/{len(details)}; exact numeric multisets: {result['numeric_multisets_equal_pages']}/{len(details)}.", "",
        "| Report/page (zero-based) | CPU status | GPU status | Same text | Same numbers | CPU page seconds | GPU page seconds |",
        "|---|---|---|---:|---:|---:|---:|"]
    for r in details:
        lines.append(f"| {r['doc_id']} / {r['page_index']} | {r['cpu_status']} | {r['gpu_status']} | {r['raw_text_equal']} | {r['numeric_multisets_equal']} | {r['cpu_page_seconds']} | {r['gpu_page_seconds']} |")
    lines += ["", result["interpretation"], result["timing"]["policy"],
        "Inspect every PNG/raw line box and each diff; equal numeric tokens do not establish correct table associations.",
        "No automatic quality threshold approves a full run. Keep the CPU run and both caches separate.", ""]
    (output / "device_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    for path, identity in ((selection_path, identities["selection"]), (cpu_root / "run_manifest.json", identities["cpu_manifest"]), (gpu_root / "run_manifest.json", identities["gpu_manifest"])):
        require(file_identity(path) == identity, "Input changed during device comparison; retain snapshots")
    return result
