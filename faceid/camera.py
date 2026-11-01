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


class CameraError(RuntimeError):
    """Kamera hech bir usulda kadr bermadi."""

    def __init__(self, device: CameraDevice, attempts: list[str]) -> None:
        super().__init__(f"{device.label()}: " + "; ".join(attempts))
        self.device = device
        self.attempts = attempts


@dataclass(frozen=True)
class CaptureConfig:
    label: str
    backend: int
    index: int
    fourcc: str | None
    width: int
    height: int


def _index_for(backend: int, name: str, fallback: int) -> int:
    """Turli backendlarda kameralar tartibi farq qilishi mumkin — nomi bo'yicha topamiz."""
    try:
        from cv2_enumerate_cameras import enumerate_cameras

        for c in enumerate_cameras(backend):
            if c.name == name:
                return c.index
    except Exception:  # noqa: BLE001
        pass
    return fallback


def capture_configs(device: CameraDevice, width: int, height: int) -> list[CaptureConfig]:
    """Kamerani ochish usullari — eng yaxshisidan eng soddasigacha."""
    out: list[CaptureConfig] = []
    if sys.platform == "win32":
        ds = device.index if device.backend == cv2.CAP_DSHOW else _index_for(cv2.CAP_DSHOW, device.name, device.index)
        ms = _index_for(cv2.CAP_MSMF, device.name, device.index)
        out += [
            CaptureConfig("DSHOW MJPG", cv2.CAP_DSHOW, ds, "MJPG", width, height),
            CaptureConfig("DSHOW", cv2.CAP_DSHOW, ds, None, width, height),
            CaptureConfig("MSMF", cv2.CAP_MSMF, ms, None, width, height),
            CaptureConfig("MSMF 640x480", cv2.CAP_MSMF, ms, None, 640, 480),
            CaptureConfig("DSHOW 640x480", cv2.CAP_DSHOW, ds, None, 640, 480),
        ]
    else:
        out += [
            CaptureConfig("MJPG", device.backend, device.index, "MJPG", width, height),
            CaptureConfig("default", device.backend, device.index, None, width, height),
        ]
    out.append(CaptureConfig("ANY", cv2.CAP_ANY, device.index, None, 0, 0))
    seen, uniq = set(), []
    for c in out:
        key = (c.backend, c.index, c.fourcc, c.width, c.height)
        if key not in seen:
            seen.add(key)
            uniq.append(c)
    return uniq


def open_capture(device: CameraDevice, width: int = 1280, height: int = 720, warmup_s: float = 3.0,
                 log=None) -> tuple[cv2.VideoCapture, CaptureConfig, np.ndarray]:
    """Har bir usulni sinaydi va haqiqatan kadr bergan birinchisini qaytaradi.

    Faqat ``isOpened()`` ga ishonib bo'lmaydi: ba'zi drayverlar (ko'p HP/Lenovo
    kameralari, DirectShow + MJPG) ochiladi-yu, lekin kadr bermaydi.
    """
    attempts: list[str] = []
    for cfg in capture_configs(device, width, height):
        t0 = time.monotonic()
        cap = cv2.VideoCapture(cfg.index, cfg.backend)
        if not cap.isOpened():
            cap.release()
            attempts.append(f"{cfg.label}: ochilmadi")
            if log:
                log(attempts[-1])
            continue
        if cfg.fourcc:
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*cfg.fourcc))
        if cfg.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, cfg.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, cfg.height)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        frame = None
        while time.monotonic() - t0 < warmup_s:
            ok, f = cap.read()
            if ok and f is not None and f.size:
                frame = f
                break
            time.sleep(0.05)
        if frame is not None:
            if log:
                log(f"{cfg.label}: OK {frame.shape[1]}x{frame.shape[0]} ({time.monotonic() - t0:.1f}s)")
            return cap, cfg, frame
        cap.release()
        attempts.append(f"{cfg.label}: ochildi, lekin kadr bermadi")
        if log:
            log(attempts[-1])
    raise CameraError(device, attempts)


class LiveCamera(FrameSource):
    """Kamerani alohida oqimda o'qiydi va doim eng so'nggi kadrni beradi (kechikishsiz)."""

    def __init__(self, device: CameraDevice, width: int = 1280, height: int = 720) -> None:
        self.name = device.name
        self.device = device
        self.cap, self.config, first = open_capture(device, width, height)
        self._frame: np.ndarray | None = first
        self._ts = time.monotonic()
        self._seq = 1
        self._read_seq = 0
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
                if self._failures > 150:  # ~3 soniya kadrsiz
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
