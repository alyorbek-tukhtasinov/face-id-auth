"""Passiv soxta yuz aniqlash (PAD) — MiniFASNet ansambli (Minivision, Apache 2.0).

Bosilgan rasm, telefon/monitor ekranidagi rasm yoki video kabi
taqdimot hujumlarini bitta kadrdan aniqlaydi. Ikki xil masshtabdagi
kesim (2.7x va 4.0x) bo'yicha natijalar o'rtachalanadi.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from ..core.onnx import create_session


def _crop(img: np.ndarray, bbox_xywh: tuple[float, float, float, float], scale: float, out: int) -> np.ndarray:
    """Silent-Face-Anti-Spoofing dagi CropImage bilan bir xil kesish."""
    src_h, src_w = img.shape[:2]
    x, y, bw, bh = bbox_xywh
    scale = min((src_h - 1) / bh, (src_w - 1) / bw, scale)
    nw, nh = bw * scale, bh * scale
    cx, cy = bw / 2 + x, bh / 2 + y
    x1, y1, x2, y2 = cx - nw / 2, cy - nh / 2, cx + nw / 2, cy + nh / 2
    if x1 < 0:
        x2 -= x1
        x1 = 0
    if y1 < 0:
        y2 -= y1
        y1 = 0
    if x2 > src_w - 1:
        x1 -= x2 - src_w + 1
        x2 = src_w - 1
    if y2 > src_h - 1:
        y1 -= y2 - src_h + 1
        y2 = src_h - 1
    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
    patch = img[max(y1, 0) : y2 + 1, max(x1, 0) : x2 + 1]
    return cv2.resize(patch, (out, out))


def portrait_window(img: np.ndarray, bbox: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Kadrdan yuz atrofidagi 3:4 (portret) oynani kesadi.

    MiniFASNet 3:4 nisbatli tasvirlarda o'qitilgan; keng (16:9) web-kamera
    kadrida shu nisbatga keltirish natijani barqarorlashtiradi.
    """
    h, w = img.shape[:2]
    win_w = min(w, int(round(h * 3 / 4)))
    cx = (bbox[0] + bbox[2]) / 2
    x0 = int(np.clip(cx - win_w / 2, 0, w - win_w))
    shifted = bbox.copy()
    shifted[[0, 2]] -= x0
    return img[:, x0 : x0 + win_w], shifted


class PassivePAD:
    def __init__(self, models: list[tuple[Path | str, float]]) -> None:
        """models — [(onnx yo'li, kesim masshtabi), ...]"""
        self.models = []
        for path, scale in models:
            sess = create_session(path)
            self.models.append((sess, sess.get_inputs()[0].name, scale))

    def score(self, img_bgr: np.ndarray, bbox: np.ndarray) -> float:
        """Yuzning haqiqiy (tirik) bo'lish ehtimoli, 0..1."""
        win, b = portrait_window(img_bgr, bbox)
        xywh = (float(b[0]), float(b[1]), float(b[2] - b[0] + 1), float(b[3] - b[1] + 1))
        probs = []
        for sess, name, scale in self.models:
            patch = _crop(win, xywh, scale, 80)
            blob = patch.astype(np.float32).transpose(2, 0, 1)[None]  # BGR, 0..255, normallashtirishsiz
            logits = sess.run(None, {name: blob})[0][0]
            e = np.exp(logits - logits.max())
            probs.append(float(e[1] / e.sum()))
        return float(np.mean(probs))
