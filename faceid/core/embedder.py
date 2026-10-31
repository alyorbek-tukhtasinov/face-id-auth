"""ArcFace R50 (WebFace600K) — 512 o'lchamli yuz vektori."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .onnx import create_session


class FaceEmbedder:
    dim = 512

    def __init__(self, model_path: Path | str) -> None:
        self.session = create_session(model_path)
        self.input_name = self.session.get_inputs()[0].name

    def embed(self, aligned_bgr: list[np.ndarray] | np.ndarray, flip_tta: bool = True) -> np.ndarray:
        """L2-normallangan vektor(lar). flip_tta — ko'zgu tasvir bilan o'rtachalash (aniqroq)."""
        imgs = [aligned_bgr] if isinstance(aligned_bgr, np.ndarray) and aligned_bgr.ndim == 3 else list(aligned_bgr)
        batch = imgs + [cv2.flip(i, 1) for i in imgs] if flip_tta else imgs
        blob = cv2.dnn.blobFromImages(batch, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True)
        out = np.asarray(self.session.run(None, {self.input_name: blob})[0], dtype=np.float32)
        if flip_tta:
            n = len(imgs)
            out = out[:n] + out[n:]
        out /= np.linalg.norm(out, axis=1, keepdims=True) + 1e-12
        return out
