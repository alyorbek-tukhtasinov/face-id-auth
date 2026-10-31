from __future__ import annotations

import os
from pathlib import Path

import onnxruntime as ort


def create_session(path: Path | str) -> ort.InferenceSession:
    """CPU (yoki mavjud bo'lsa DirectML/CUDA) uchun optimallashtirilgan ONNX sessiyasi."""
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    opts.log_severity_level = 3
    threads = int(os.environ.get("FACEID_THREADS", "0"))
    if threads:
        opts.intra_op_num_threads = threads
    available = ort.get_available_providers()
    preferred = [p for p in ("CUDAExecutionProvider", "DmlExecutionProvider") if p in available]
    if os.environ.get("FACEID_CPU_ONLY"):
        preferred = []
    return ort.InferenceSession(str(path), sess_options=opts, providers=[*preferred, "CPUExecutionProvider"])
