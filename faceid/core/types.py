from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class Face:
    """Aniqlangan yuz. Koordinatalar asl kadr pikselida."""

    bbox: np.ndarray  # [x1, y1, x2, y2]
    kps: np.ndarray  # (5, 2): chap ko'z, o'ng ko'z, burun, og'iz chap, og'iz o'ng (rasm bo'yicha)
    score: float
    embedding: np.ndarray | None = None
    aligned: np.ndarray | None = None  # 112x112 BGR

    @property
    def width(self) -> float:
        return float(self.bbox[2] - self.bbox[0])

    @property
    def height(self) -> float:
        return float(self.bbox[3] - self.bbox[1])

    @property
    def area(self) -> float:
        return max(self.width, 0.0) * max(self.height, 0.0)

    @property
    def center(self) -> tuple[float, float]:
        return float((self.bbox[0] + self.bbox[2]) / 2), float((self.bbox[1] + self.bbox[3]) / 2)

    @property
    def eye_distance(self) -> float:
        return float(np.linalg.norm(self.kps[1] - self.kps[0]))


@dataclass
class Quality:
    score: float  # 0..100
    components: dict[str, float] = field(default_factory=dict)  # har biri 0..1
    issues: list[str] = field(default_factory=list)  # i18n kalitlari
    yaw: float = 0.0
    pitch: float = 0.0
    roll: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.issues
