"""Fon oqimlari: modellarni yuklash va kamera + biometrik sessiya."""

from __future__ import annotations

import traceback

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QImage

from ..camera import CameraDevice, CameraError, FrameSource, LiveCamera, VideoFileSource, list_cameras
from ..config import Settings
from ..liveness.injection import is_virtual_camera
from ..session import BiometricSession, FrameReport, Mode, SessionResult


class LoaderThread(QThread):
    progress = Signal(str, int)
    loaded = Signal(object)
    failed = Signal(str)

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    def run(self) -> None:
        try:
            from .. import models
            from ..engine import Engine

            if models.missing_models():
                def cb(name: str, done: int, total: int) -> None:
                    self.progress.emit(name, int(done * 100 / total) if total else 0)

                models.ensure_models(cb)
            self.progress.emit("", -1)
            eng = Engine(self.settings)
            # Birinchi chaqiriqlarni "isitish" — keyingi kadrlar tezroq
            dummy = np.zeros((480, 640, 3), np.uint8)
            eng.detector.detect(dummy)
            eng.landmarker.process(dummy, 0)
            self.loaded.emit(eng)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.failed.emit(str(exc))


def to_qimage(frame_bgr: np.ndarray) -> QImage:
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()


class SessionWorker(QThread):
    frame = Signal(QImage, object)  # (kadr, FrameReport)
    finished_result = Signal(object)  # SessionResult
    error = Signal(str, str)  # (i18n kaliti, texnik tafsilot)
    status = Signal(str)  # i18n kaliti

    def __init__(self, engine, settings: Settings, mode: Mode, gallery, claimed_user: int | None = None,
                 source_path: str | None = None) -> None:
        super().__init__()
        self.engine = engine
        self.settings = settings
        self.mode = mode
        self.gallery = gallery
        self.claimed = claimed_user
        self.source_path = source_path
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def _open(self) -> FrameSource:
        if self.source_path:
            return VideoFileSource(self.source_path, realtime=True)
        cams = list_cameras()
        dev = next((c for c in cams if c.index == self.settings.camera_index), None)
        if dev is None:
            dev = cams[0] if cams else CameraDevice(self.settings.camera_index, f"Camera {self.settings.camera_index}",
                                                    cv2.CAP_ANY)
        if self.settings.block_virtual_cameras and is_virtual_camera(dev.name, self.settings.allowed_camera_names):
            raise PermissionError("inj_virtual_camera")
        return LiveCamera(dev, self.settings.camera_width, self.settings.camera_height)

    def run(self) -> None:
        self.status.emit("cam_opening")
        try:
            src = self._open()
        except PermissionError:
            self.finished_result.emit(SessionResult(False, "inj_virtual_camera"))
            return
        except CameraError as exc:
            self.error.emit("fail_camera_no_frames", "; ".join(exc.attempts))
            return
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.error.emit("fail_camera", str(exc))
            return
        if self._stop:
            src.release()
            return
        session = BiometricSession(self.engine, self.mode, self.gallery, self.settings, claimed_user=self.claimed,
                                   camera_mirrored=getattr(self.settings, "camera_hw_mirrored", False))
        try:
            empty = 0
            while not self._stop:
                frame, _ts = src.read()
                if frame is None:
                    empty += 1
                    if empty > 5:
                        self.error.emit("fail_camera_stopped", getattr(src, "name", ""))
                        return
                    continue
                empty = 0
                rep: FrameReport = session.process(frame)
                self.frame.emit(to_qimage(frame), rep)
                if session.result is not None:
                    self.finished_result.emit(session.result)
                    return
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.error.emit("fail_internal", f"{type(exc).__name__}: {exc}")
        finally:
            src.release()
