"""Barcha neyron tarmoq modellarini bir marta yuklaydigan biometrik dvigatel."""

from __future__ import annotations

import numpy as np

from . import models as M
from .config import Settings
from .core.align import align_face
from .core.detector import FaceDetector
from .core.embedder import FaceEmbedder
from .core.quality import assess
from .core.types import Face, Quality


def _disable_telemetry() -> None:
    try:
        import onnxruntime as ort

        ort.disable_telemetry_events()
    except Exception:  # noqa: BLE001
        pass


class Engine:
    def __init__(self, settings: Settings | None = None, detector_size: int = 384) -> None:
        _disable_telemetry()
        self.settings = settings or Settings.load()
        missing = M.missing_models()
        if missing:
            raise RuntimeError("Modellar topilmadi: " + ", ".join(missing) + ". `python -m faceid models` ni ishga tushiring.")
        self.detector = FaceDetector(M.model_path("detector"), input_size=detector_size)
        self.still_detector = FaceDetector(M.model_path("detector"), input_size=640)
        self.embedder = FaceEmbedder(M.model_path("recognizer"))
        from .liveness.passive import PassivePAD

        self.pad = PassivePAD([(M.model_path("pad_v2"), 2.7), (M.model_path("pad_v1se"), 4.0)])
        self._landmarker = None

    @property
    def landmarker(self):
        if self._landmarker is None:
            from .liveness.landmarks import Landmarker

            self._landmarker = Landmarker(M.model_path("landmarker"))
        return self._landmarker

    def embed_face(self, img_bgr: np.ndarray, face: Face) -> np.ndarray:
        if face.aligned is None:
            face.aligned = align_face(img_bgr, face.kps)
        face.embedding = self.embedder.embed(face.aligned)[0]
        return face.embedding

    def quality(self, img_bgr: np.ndarray, face: Face) -> Quality:
        if face.aligned is None:
            face.aligned = align_face(img_bgr, face.kps)
        return assess(img_bgr, face, face.aligned)

    def analyze_still(self, img_bgr: np.ndarray, max_faces: int = 0) -> list[Face]:
        """Statik rasm (baholash/test uchun): aniqlash + embedding."""
        faces = self.still_detector.detect(img_bgr, max_faces=max_faces)
        for f in faces:
            self.embed_face(img_bgr, f)
        return faces

    def close(self) -> None:
        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None
