"""Setup-only GPU/driver/runtime check; no OCR model or retrieval is run."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time

from finocr.io import read_json, write_json
from finocr.pipelines.ocr_data import require
from finocr.pipelines.ocr_device import synchronize
from finocr.pipelines.report_ocr import runtime_identity
from finocr.pipelines.report_rendering import file_identity


def check(cpu_dir, output):
    destination = Path(output)
    require(not destination.exists(), "Choose a fresh GPU inventory output file")
    started = time.perf_counter()
    inventory = {"stage": "gpu_setup_check", "started_utc": datetime.now(timezone.utc).isoformat(),
                 "interpretation": "setup observations only; no OCR inference, financial accuracy or retrieval result"}
    try:
        inventory["environment"] = runtime_identity("gpu:0")
        require(sys.version_info[:3] == (3, 12, 10), "Match CPU Python 3.12.10")
        reference = Path(cpu_dir) / "run_manifest.json"
        require(file_identity(reference)["sha256"] == "cd0fa0c899c9298dcc75194318114b6b947840fd663a4847ced4cf6452412d7e", "Use the retained CPU diagnostic")
        expected = read_json(reference)["contract"]["runtime"]["packages"]
        actual = inventory["environment"]["packages"]
        require(all(actual.get(k) == v for k, v in expected.items() if k not in {"paddlepaddle", "financial-ocr-research"}),
                "Non-framework reference dependencies differ")
        inventory["additional_packages"] = {k: v for k, v in actual.items() if k not in expected}
        inventory["nvidia_smi"] = subprocess.check_output(["nvidia-smi", "--query-gpu=index,name,driver_version,memory.total,memory.free",
            "--format=csv,noheader,nounits"], text=True).strip().splitlines()
        driver = inventory["nvidia_smi"][0].split(",")[2].strip()
        require(tuple(int(x) for x in driver.split(".")) >= (522, 6), "This CUDA 11.8 condition requires Windows driver >=522.06")
        import paddle
        require(paddle.is_compiled_with_cuda() and paddle.version.cuda() == "11.8", "Wrong framework/CUDA build; CPU fallback is forbidden")
        paddle.set_device("gpu:0")
        paddle.utils.run_check()
        synchronize("gpu:0")
        props = paddle.device.cuda.get_device_properties(0)
        require((props.major, props.minor) >= (7, 5), "Official Windows wheel requires compute capability >=7.5")
        inventory.update(status="setup_complete", paddle_device=paddle.device.get_device(), cuda=paddle.version.cuda(),
                         cudnn=paddle.version.cudnn(), gpu_name=props.name, gpu_memory_bytes=props.total_memory,
                         gpu_compute_capability=[props.major, props.minor])
    except BaseException as exc:
        inventory.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        inventory["elapsed_seconds"] = time.perf_counter()-started
        write_json(destination, inventory)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cpu-dir", required=True); parser.add_argument("--output", required=True)
    args = parser.parse_args()
    check(args.cpu_dir, args.output)
