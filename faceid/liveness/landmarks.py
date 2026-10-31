"""MediaPipe Face Landmarker: 478 nuqta, 52 blendshape va bosh holati."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# MediaPipe/absl ortiqcha loglarini o'chirish
os.environ.setdefault("GLOG_minloglevel", "2")
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


@dataclass
class MeshFace:
    points: np.ndarray  # (478, 3), piksel koordinatalarida (z — nisbiy)
    blend: dict[str, float] = field(default_factory=dict)
    yaw_ratio: float = 0.0  # >0 — foydalanuvchi o'z CHAP tomoniga burilgan (kamera ko'zgusiz)
    pitch: float = 0.0  # gradus, transformatsiya matritsasidan
    roll: float = 0.0

    @property
    def bbox(self) -> np.ndarray:
        xy = self.points[:, :2]
        return np.array([xy[:, 0].min(), xy[:, 1].min(), xy[:, 0].max(), xy[:, 1].max()], dtype=np.float32)

    @property
    def blink(self) -> float:
        return min(self.blend.get("eyeBlinkLeft", 0.0), self.blend.get("eyeBlinkRight", 0.0))

    @property
    def eyes_open(self) -> float:
        return 1.0 - max(self.blend.get("eyeBlinkLeft", 0.0), self.blend.get("eyeBlinkRight", 0.0))

    @property
    def smile(self) -> float:
        return (self.blend.get("mouthSmileLeft", 0.0) + self.blend.get("mouthSmileRight", 0.0)) / 2

    @property
    def jaw_open(self) -> float:
        return self.blend.get("jawOpen", 0.0)

    def five_points(self) -> np.ndarray:
        """ArcFace tartibidagi 5 nuqta (rasmda: chap ko'z, o'ng ko'z, burun, og'iz chap, og'iz o'ng)."""
        p = self.points[:, :2]
        a, b = p[468], p[473]  # ko'z qorachiqlari
        left_eye, right_eye = (a, b) if a[0] < b[0] else (b, a)
        m1, m2 = p[61], p[291]
        ml, mr = (m1, m2) if m1[0] < m2[0] else (m2, m1)
        return np.stack([left_eye, right_eye, p[1], ml, mr]).astype(np.float32)


def yaw_ratio_from_points(p: np.ndarray) -> float:
    """Burun uchining yuz konturi o'rtasidan siljishi (-1..1).

    Kamera tasviri ko'zgulanmagan bo'lsa, foydalanuvchi o'z chap tomoniga
    burilganda burun rasmning o'ng tomoniga siljiydi → musbat qiymat.
    """
    a, b = p[234, 0], p[454, 0]  # yonoq/quloq oldi konturi
    left, right = min(a, b), max(a, b)
    half = (right - left) / 2 + 1e-6
    return float((p[1, 0] - (left + right) / 2) / half)


def euler_from_matrix(m: np.ndarray) -> tuple[float, float, float]:
    r = np.asarray(m)[:3, :3]
    sy = math.hypot(r[0, 0], r[1, 0])
    pitch = math.degrees(math.atan2(r[2, 1], r[2, 2]))
    yaw = math.degrees(math.atan2(-r[2, 0], sy))
    roll = math.degrees(math.atan2(r[1, 0], r[0, 0]))
    return pitch, yaw, roll


class Landmarker:
    def __init__(self, model_path: Path | str, max_faces: int = 2) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        opts = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            # IMAGE rejimi: har kadr mustaqil (kesim har kadrda siljiydi — tracking kerak emas)
            running_mode=vision.RunningMode.IMAGE,
            num_faces=max_faces,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
        )
        self._lm = vision.FaceLandmarker.create_from_options(opts)

    def process(self, img_bgr: np.ndarray, ts_ms: int = 0) -> list[MeshFace]:
        """Butun kadr bo'yicha (yuz kadr balandligining ~30% idan katta bo'lsa ishonchli)."""
        return self._run(img_bgr, 1.0, 0.0, 0.0)

    def process_roi(self, img_bgr: np.ndarray, bbox: np.ndarray, size: int = 384) -> list[MeshFace]:
        """Yuz atrofidagi kvadrat kesimda — uzoqdagi kichik yuzlar uchun ham ishonchli."""
        import cv2

        cx, cy = (bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2
        side = 2.0 * max(bbox[2] - bbox[0], bbox[3] - bbox[1])
        x0, y0 = cx - side / 2, cy - side / 2
        scale = side / size
        m = np.array([[1 / scale, 0, -x0 / scale], [0, 1 / scale, -y0 / scale]], dtype=np.float32)
        crop = cv2.warpAffine(img_bgr, m, (size, size), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        return self._run(crop, scale, x0, y0)

    def _run(self, img_bgr: np.ndarray, scale: float, x0: float, y0: float) -> list[MeshFace]:
        import cv2

        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        res = self._lm.detect(self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)))
        h, w = img_bgr.shape[:2]
        out: list[MeshFace] = []
        for i, lms in enumerate(res.face_landmarks or []):
            pts = np.array([[p.x * w * scale + x0, p.y * h * scale + y0, p.z * w * scale] for p in lms],
                           dtype=np.float32)
            blend = {}
            if res.face_blendshapes and i < len(res.face_blendshapes):
                blend = {c.category_name: float(c.score) for c in res.face_blendshapes[i]}
            pitch = roll = 0.0
            if res.facial_transformation_matrixes and i < len(res.facial_transformation_matrixes):
                pitch, _, roll = euler_from_matrix(res.facial_transformation_matrixes[i])
            out.append(MeshFace(points=pts, blend=blend, yaw_ratio=yaw_ratio_from_points(pts), pitch=pitch, roll=roll))
        return out

    def close(self) -> None:
        if self._lm is not None:
            try:
                self._lm.close()
            except Exception:  # noqa: BLE001 — yopishdagi xatolar ahamiyatsiz
                pass
            self._lm = None

    def __del__(self) -> None:  # pragma: no cover
        self.close()
