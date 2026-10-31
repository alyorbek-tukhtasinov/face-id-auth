"""Soxta video oqimi (injection) hujumlarini aniqlash — CEN/TS 18099 yondashuvi.

Taqdimot hujumidan (kamera oldiga rasm qo'yish) farqli o'laroq, injection
hujumida kamera umuman chetlab o'tiladi: virtual kamera drayveri orqali
oldindan tayyorlangan yoki deepfake video uzatiladi. Lokal tizimda
quyidagi signallar tekshiriladi:

1. Qurilma nomi — ma'lum virtual kamera dasturlari (OBS, ManyCam, ...).
2. Muzlagan kadrlar — haqiqiy sensor har kadrda shovqin beradi; aynan bir
   xil kadrlar ketma-ketligi statik rasm uzatilayotganini bildiradi.
3. Shovqinsiz kadrlar — sintetik/qayta kodlangan oqimda sensor shovqini
   g'ayritabiiy darajada past bo'ladi.
4. O'lcham o'zgarishi — sessiya davomida kadr o'lchami o'zgarmasligi kerak.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import cv2
import numpy as np

VIRTUAL_CAMERA_KEYWORDS = (
    "obs", "virtual", "manycam", "xsplit", "snap camera", "splitcam", "vcam", "e2esoft", "youcam",
    "camtwist", "mmhmm", "camo", "droidcam", "iriun", "epoccam", "ndi", "newtek", "avatarify",
    "deepfake", "facerig", "animaze", "chromacam", "sparkocam", "fake", "dummy", "v4l2loopback",
    "loopback", "unity video capture", "screen capture", "vmix",
)


_VIRTUAL_RE = re.compile(r"\b(" + "|".join(re.escape(k) for k in VIRTUAL_CAMERA_KEYWORDS) + r")\b")


def is_virtual_camera(name: str, allowed: list[str] | None = None) -> bool:
    n = (name or "").lower().strip()
    if allowed and any(a.lower().strip() == n for a in allowed):
        return False
    return _VIRTUAL_RE.search(n) is not None


def noise_sigma(gray: np.ndarray) -> float:
    """Tasvir shovqinining tez bahosi (Immerkær, 1996)."""
    k = np.array([[1, -2, 1], [-2, 4, -2], [1, -2, 1]], dtype=np.float32)
    g = gray.astype(np.float32)
    conv = cv2.filter2D(g, -1, k)
    h, w = g.shape
    return float(np.sqrt(np.pi / 2) * np.abs(conv[1:-1, 1:-1]).sum() / (6 * (w - 2) * (h - 2)))


@dataclass
class InjectionMonitor:
    frozen_limit: int = 10  # ketma-ket bir xil kadrlar soni
    frozen_diff: float = 0.15  # o'rtacha mutlaq farq (0..255)
    min_noise: float = 0.25
    low_noise_ratio: float = 0.9
    _prev: np.ndarray | None = None
    _frozen_run: int = 0
    _shape: tuple[int, ...] | None = None
    _frames: int = 0
    _low_noise: int = 0
    flags: list[str] = field(default_factory=list)

    def update(self, frame_bgr: np.ndarray) -> None:
        self._frames += 1
        if self._shape is None:
            self._shape = frame_bgr.shape
        elif frame_bgr.shape != self._shape:
            self._flag("inj_resolution_change")
        # INTER_NEAREST — sensor shovqini o'rtachalanmaydi (harakatsiz, lekin tirik sahna
        # ham har kadrda farq qiladi), INTER_AREA esa uni "muzlagan"ga o'xshatib qo'yardi.
        small = cv2.cvtColor(cv2.resize(frame_bgr, (320, 180), interpolation=cv2.INTER_NEAREST), cv2.COLOR_BGR2GRAY)
        if self._prev is not None and self._prev.shape == small.shape:
            diff = float(cv2.absdiff(small, self._prev).mean())
            self._frozen_run = self._frozen_run + 1 if diff < self.frozen_diff else 0
            if self._frozen_run >= self.frozen_limit:
                self._flag("inj_frozen_stream")
        self._prev = small
        if self._frames % 5 == 0:
            g = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            h, w = g.shape
            patch = g[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
            if noise_sigma(patch) < self.min_noise:
                self._low_noise += 1
        checks = self._frames // 5
        if checks >= 8 and self._low_noise / checks >= self.low_noise_ratio:
            self._flag("inj_synthetic_stream")

    def _flag(self, f: str) -> None:
        if f not in self.flags:
            self.flags.append(f)

    @property
    def suspicious(self) -> bool:
        return bool(self.flags)
