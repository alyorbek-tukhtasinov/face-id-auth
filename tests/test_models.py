"""Haqiqiy neyron tarmoqlar bilan integratsiya testlari (modellar yuklangan bo'lsa)."""

from __future__ import annotations

import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from tests.conftest import DATA


@pytest.fixture(scope="module")
def astro():
    img = cv2.imread(str(DATA / "astronaut.jpg"))
    assert img is not None
    return img


def _on_canvas(img, w=1280, h=720, scale=1.6):
    """Rasmni web-kamera kadriga o'xshash 16:9 fonga joylashtiradi."""
    face = cv2.resize(img, None, fx=scale, fy=scale)
    canvas = np.full((h, w, 3), 90, np.uint8)
    fh, fw = face.shape[:2]
    y0, x0 = (h - fh) // 2, (w - fw) // 2
    canvas[max(y0, 0):max(y0, 0) + min(fh, h), x0:x0 + fw] = face[:min(fh, h)]
    return canvas


def _replay(img):
    """Ekrandan qayta suratga olish simulyatsiyasi: moire, kontrast pasayishi, xiralik."""
    h, w = img.shape[:2]
    yy, xx = np.mgrid[:h, :w]
    moire = (np.sin(xx * 0.9) * np.sin(yy * 0.9) * 18).astype(np.float32)
    out = cv2.GaussianBlur(img, (0, 0), 1.2).astype(np.float32) * 0.85 + 30 + moire[..., None]
    return np.clip(out, 0, 255).astype(np.uint8)


def test_detect_and_quality(engine, astro):
    faces = engine.analyze_still(astro)
    assert len(faces) == 1
    f = faces[0]
    assert f.score > 0.7 and f.embedding.shape == (512,)
    q = engine.quality(astro, f)
    assert q.score > 60, q


def test_same_person_high_similarity(engine, astro):
    base = engine.analyze_still(astro)[0].embedding
    variants = [
        cv2.convertScaleAbs(astro, alpha=1.25, beta=-25),
        cv2.GaussianBlur(astro, (0, 0), 1.0),
        cv2.resize(cv2.resize(astro, (200, 200)), (384, 384)),
        cv2.warpAffine(astro, cv2.getRotationMatrix2D((192, 192), 8, 1.0), (384, 384)),
    ]
    for v in variants:
        e = engine.analyze_still(v)[0].embedding
        assert float(base @ e) > 0.7


def test_quality_penalizes_degradation(engine, astro):
    f = engine.still_detector.detect(astro)[0]
    good = engine.quality(astro, f).score
    blurred = cv2.GaussianBlur(astro, (0, 0), 4)
    fb = engine.still_detector.detect(blurred)[0]
    assert engine.quality(blurred, fb).score < good - 15


def _face_closeup(engine, img, height=420):
    """Yuz atrofini kesib, web-kamera masofasidagidek kattalashtiradi."""
    f = engine.still_detector.detect(img)[0]
    cx, cy = f.center
    half = max(f.width, f.height) * 1.3
    x0, y0 = int(max(cx - half, 0)), int(max(cy - half, 0))
    crop = img[y0:int(cy + half), x0:int(cx + half)]
    return cv2.resize(crop, (height, height), interpolation=cv2.INTER_CUBIC)


def test_passive_pad_outputs(engine, astro):
    """PAD natijasi 0..1 oralig'ida va deterministik.

    Eslatma: astronavt surati — skaner qilingan bosma foto (ya'ni o'zi "qayta
    suratga olingan"), shuning uchun u tirik yuz namunasi bo'la olmaydi.
    Haqiqiy APCER/BPCER `python -m faceid evaluate --pad-real ... --pad-attack ...`
    bilan o'z kamerangiz yozuvlarida o'lchanadi.
    """
    live = _on_canvas(_face_closeup(engine, astro), scale=1.0)
    f = engine.detector.detect(live)[0]
    s1, s2 = engine.pad.score(live, f.bbox), engine.pad.score(live, f.bbox)
    assert 0.0 <= s1 <= 1.0 and s1 == s2
    fa = engine.detector.detect(_replay(live))[0]
    assert 0.0 <= engine.pad.score(_replay(live), fa.bbox) <= 1.0


def test_landmarker_blendshapes(engine, astro):
    # Yuz kadr balandligining ~25% i — to'liq kadrda MediaPipe uni topmaydi, ROI rejimida topadi
    frame = _on_canvas(_face_closeup(engine, astro), scale=1.0)
    face = engine.detector.detect(frame)[0]
    meshes = engine.landmarker.process_roi(frame, face.bbox)
    assert len(meshes) == 1
    m = meshes[0]
    assert abs(m.yaw_ratio) < 0.3
    assert m.eyes_open > 0.5
    five = m.five_points()
    assert five.shape == (5, 2) and five[0, 0] < five[1, 0]
    # ROI koordinatalari asl kadrga to'g'ri qaytarilgan: MediaPipe va SCRFD ko'z nuqtalari yaqin
    assert np.abs(five[:2] - face.kps[:2]).max() < 0.15 * face.width


@pytest.mark.skipif(not os.environ.get("FACEID_TEST_IMAGES"), reason="FACEID_TEST_IMAGES ko'rsatilmagan")
def test_different_people_low_similarity(engine):
    """FACEID_TEST_IMAGES — bir nechta turli odamlar tushgan guruh surati."""
    img = cv2.imread(str(Path(os.environ["FACEID_TEST_IMAGES"])))
    faces = [f for f in engine.analyze_still(img) if f.eye_distance > 20]
    assert len(faces) >= 3
    embs = np.stack([f.embedding for f in faces])
    sims = embs @ embs.T
    off = sims[~np.eye(len(faces), dtype=bool)]
    assert off.max() < 0.35, off.max()
