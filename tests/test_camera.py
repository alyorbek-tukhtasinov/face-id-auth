"""Kamerani ochish: "ochildi, lekin kadr bermadi" holatida boshqa usulga o'tish."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from faceid import camera as C


class FakeCap:
    """Faqat ``good`` backend + FOURCC siz sozlamada kadr beradigan kamera (HP drayveriga o'xshash)."""

    opened: list[FakeCap] = []

    def __init__(self, index, backend, good=(cv2.CAP_DSHOW, False), dead=False):
        self.index, self.backend = index, backend
        self.fourcc = False
        self.good = good
        self.dead = dead
        self.released = False
        FakeCap.opened.append(self)

    def isOpened(self):  # noqa: N802
        return True

    def set(self, prop, val):
        if prop == cv2.CAP_PROP_FOURCC:
            self.fourcc = True
        return True

    def read(self):
        if not self.dead and (self.backend, self.fourcc) == self.good:
            return True, np.full((720, 1280, 3), 100, np.uint8)
        return False, None

    def release(self):
        self.released = True


@pytest.fixture
def win(monkeypatch):
    monkeypatch.setattr(C.sys, "platform", "win32")
    FakeCap.opened = []
    return C.CameraDevice(0, "HP True Vision 5MP Camera", cv2.CAP_DSHOW, "04F2:B767")


def test_falls_back_when_mjpg_gives_no_frames(win, monkeypatch):
    monkeypatch.setattr(C.cv2, "VideoCapture", lambda i, b: FakeCap(i, b))
    log = []
    cap, cfg, frame = C.open_capture(win, warmup_s=0.15, log=log.append)
    assert cfg.label == "DSHOW" and frame.shape == (720, 1280, 3)
    assert "kadr bermadi" in log[0]
    assert FakeCap.opened[0].released and not cap.released


def test_msmf_fallback(win, monkeypatch):
    monkeypatch.setattr(C.cv2, "VideoCapture", lambda i, b: FakeCap(i, b, good=(cv2.CAP_MSMF, False)))
    _, cfg, _ = C.open_capture(win, warmup_s=0.1)
    assert cfg.label == "MSMF"


def test_all_fail_raises_with_attempts(win, monkeypatch):
    monkeypatch.setattr(C.cv2, "VideoCapture", lambda i, b: FakeCap(i, b, dead=True))
    with pytest.raises(C.CameraError) as ei:
        C.open_capture(win, warmup_s=0.05)
    assert len(ei.value.attempts) >= 5
    assert all(c.released for c in FakeCap.opened)


def test_live_camera_delivers_frames(win, monkeypatch):
    monkeypatch.setattr(C.cv2, "VideoCapture", lambda i, b: FakeCap(i, b))
    cam = C.LiveCamera(win)
    try:
        for _ in range(3):
            frame, _ = cam.read()
            assert frame is not None
        assert cam.config.label == "DSHOW"
    finally:
        cam.release()
