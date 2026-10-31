"""Kamera bilan ishlash: qurilmalar ro'yxati, past kechikishli o'qish, test uchun video manba."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class CameraDevice:
    index: int
    name: str
    backend: int
    usb_id: str | None = None  # "VID:PID" — haqiqiy USB kamerada bo'ladi

    def label(self) -> str:
        return f"{self.index}: {self.name}" + (f" ({self.usb_id})" if self.usb_id else "")


def _default_backend() -> int:
    if sys.platform == "win32":
        return cv2.CAP_DSHOW  # MSMF ga nisbatan tezroq ochiladi
    if sys.platform == "darwin":
        return cv2.CAP_AVFOUNDATION
    return cv2.CAP_V4L2


def list_cameras() -> list[CameraDevice]:
    backend = _default_backend()
    try:
        from cv2_enumerate_cameras import enumerate_cameras

        out = []
        for c in enumerate_cameras(backend):
            usb = f"{c.vid:04X}:{c.pid:04X}" if c.vid is not None and c.pid is not None else None
            out.append(CameraDevice(c.index, c.name or f"Camera {c.index}", backend, usb))
        if out:
            return out
    except Exception:  # noqa: BLE001 — kutubxona yo'q yoki qo'llab-quvvatlanmaydi
        pass
    out = []
    for i in range(4):
        cap = cv2.VideoCapture(i, backend)
        if cap.isOpened():
            out.append(CameraDevice(i, f"Camera {i}", backend))
        cap.release()
    return out


class FrameSource:
    name: str = ""

    def read(self) -> tuple[np.ndarray | None, float]:
        raise NotImplementedError

    def release(self) -> None:
        pass


class LiveCamera(FrameSource):
    """Kamerani alohida oqimda o'qiydi va doim eng so'nggi kadrni beradi (kechikishsiz)."""

    def __init__(self, device: CameraDevice, width: int = 1280, height: int = 720) -> None:
        self.name = device.name
        self.device = device
        self.cap = cv2.VideoCapture(device.index, device.backend)
        if not self.cap.isOpened():
            self.cap = cv2.VideoCapture(device.index)
        if not self.cap.isOpened():
            raise RuntimeError(f"Kamerani ochib bo'lmadi: {device.label()}")
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._frame: np.ndarray | None = None
        self._ts = 0.0
        self._seq = 0
        self._read_seq = -1
        self._cond = threading.Condition()
        self._running = True
        self._failures = 0
        self._thread = threading.Thread(target=self._loop, name="camera", daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while self._running:
            ok, frame = self.cap.read()
            if not ok or frame is None:
                self._failures += 1
                if self._failures > 50:
                    break
                time.sleep(0.02)
                continue
            self._failures = 0
            with self._cond:
                self._frame, self._ts = frame, time.monotonic()
                self._seq += 1
                self._cond.notify_all()
        with self._cond:
            self._running = False
            self._cond.notify_all()

    def read(self) -> tuple[np.ndarray | None, float]:
        with self._cond:
            self._cond.wait_for(lambda: self._seq != self._read_seq or not self._running, timeout=2.0)
            if self._frame is None or self._seq == self._read_seq:
                return None, time.monotonic()
            self._read_seq = self._seq
            return self._frame, self._ts

    def release(self) -> None:
        self._running = False
        self._thread.join(timeout=2.0)
        self.cap.release()


class VideoFileSource(FrameSource):
    """Video fayl yoki rasmlar papkasi — test/diagnostika uchun (kamerasiz)."""

    def __init__(self, path: str | Path, realtime: bool = False) -> None:
        self.name = f"file:{Path(path).name}"
        self.cap = cv2.VideoCapture(str(path))
        if not self.cap.isOpened():
            raise RuntimeError(f"Faylni ochib bo'lmadi: {path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        self.i = 0
        self.realtime = realtime
        self.t0 = time.monotonic()

    def read(self) -> tuple[np.ndarray | None, float]:
        ok, frame = self.cap.read()
        if not ok:
            return None, 0.0
        ts = self.i / self.fps
        self.i += 1
        if self.realtime:
            delay = self.t0 + ts - time.monotonic()
            if delay > 0:
                time.sleep(delay)
        return frame, ts

    def release(self) -> None:
        self.cap.release()
