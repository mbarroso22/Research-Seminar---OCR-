"""Explicit device conditions; the frozen CPU configuration remains unchanged."""
from __future__ import annotations

from finocr.pipelines.ocr_data import require

GPU_PACKAGE_PINS = {"paddlepaddle-gpu": "3.3.0", "paddleocr": "3.3.2", "paddlex": "3.3.10"}


def device_condition(device):
    from finocr.pipelines.ocr_smoke import OCR_CONFIG, PACKAGE_PINS
    require(device in {"cpu", "gpu:0"}, "Supported OCR devices are cpu and gpu:0")
    return {**OCR_CONFIG, "device": device}, dict(PACKAGE_PINS if device == "cpu" else GPU_PACKAGE_PINS)


def validate_worker_runtime(runtime, device):
    _, pins = device_condition(device)
    require(runtime["packages"] == pins and runtime["paddle_device"] == device
            and runtime["compiled_with_cuda"] is (device == "gpu:0"), "OCR worker device/framework mismatch; CPU fallback is forbidden")
    if device == "gpu:0":
        require(runtime["cuda"] == "11.8", "GPU condition requires the official CUDA 11.8 wheel")


def synchronize(device):
    if device == "gpu:0":
        import paddle
        paddle.device.synchronize(device)
