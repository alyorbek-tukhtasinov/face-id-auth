"""Yuz tasviri sifatini baholash.

ISO/IEC 29794-5:2025 (va uning OFIQ ma'lumotnoma ilovasi) dagi asosiy
komponentlarga tayanadi: o'lcham, o'tkirlik, yoritilganlik, kontrast,
yorug'lik bir xilligi, ortiqcha/kam ekspozitsiya, bosh holati (yaw/pitch/roll)
va kadrda to'liq joylashganlik. Har bir komponent 0..1 oralig'ida,
umumiy ball 0..100 — vaznli geometrik o'rtacha.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from .types import Face, Quality

# Komponent vaznlari (umumiy ballga ta'siri)
_WEIGHTS = {
    "size": 1.0,
    "sharpness": 1.5,
    "brightness": 1.0,
    "contrast": 0.7,
    "uniformity": 0.7,
    "exposure": 0.8,
    "pose": 1.5,
    "framing": 1.0,
    "confidence": 0.8,
}


def _ramp(x: float, lo: float, hi: float) -> float:
    """lo dan past — 0, hi dan yuqori — 1, oraliqda chiziqli."""
    if hi == lo:
        return float(x >= hi)
    return float(np.clip((x - lo) / (hi - lo), 0.0, 1.0))


def _band(x: float, lo0: float, lo1: float, hi1: float, hi0: float) -> float:
    """[lo1, hi1] — 1, [lo0, hi0] dan tashqari — 0."""
    if x < lo1:
        return _ramp(x, lo0, lo1)
    if x > hi1:
        return 1.0 - _ramp(x, hi1, hi0)
    return 1.0


def head_pose_from_kps(kps: np.ndarray) -> tuple[float, float, float]:
    """5 nuqtadan taxminiy yaw, pitch, roll (gradusda).

    Rasm koordinatalarida (ko'zgu effektisiz): musbat yaw — burun rasmning
    o'ng tomoniga siljigan.
    """
    le, re, nose, ml, mr = kps.astype(np.float64)
    eye_mid = (le + re) / 2
    mouth_mid = (ml + mr) / 2
    dx, dy = re - le
    roll = math.degrees(math.atan2(dy, dx))
    ang = math.radians(-roll)
    rot = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    eye_d = math.hypot(dx, dy) + 1e-6
    n = rot @ (nose - eye_mid)
    m = rot @ (mouth_mid - eye_mid)
    # Burunning ko'zlar o'rtasidan gorizontal siljishi (ko'z masofasiga nisbatan)
    yaw = math.degrees(math.asin(float(np.clip(2.0 * n[0] / eye_d, -1.0, 1.0)))) * 0.9
    # Frontal yuzda burun ko'z-og'iz oralig'ining ~0.56 qismida joylashadi.
    # (Tabassumda og'iz burchaklari ko'tariladi — pitch taxmini qo'pol.)
    ratio = n[1] / (m[1] + 1e-6)
    pitch = (0.56 - ratio) * 120.0
    return yaw, pitch, roll


def assess(img_bgr: np.ndarray, face: Face, aligned: np.ndarray | None = None) -> Quality:
    from .align import align_face

    if aligned is None:
        aligned = align_face(img_bgr, face.kps)
    gray = cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY)
    # Faqat yuzning markaziy qismi (fon ta'sirini kamaytirish)
    core = gray[24:104, 20:92]

    h, w = img_bgr.shape[:2]
    comp: dict[str, float] = {}
    issues: list[str] = []

    # 1) O'lcham — ko'zlar orasidagi masofa (ISO 19794-5: >= 60 px tavsiya)
    ied = face.eye_distance
    comp["size"] = _ramp(ied, 28, 60)
    if ied < 40:
        issues.append("q_too_far")
    elif face.width > 0.85 * min(h, w):
        issues.append("q_too_close")

    # 2) O'tkirlik — Laplas dispersiyasi (asl o'lchamga keltirilgan)
    lap = cv2.Laplacian(core, cv2.CV_64F).var()
    comp["sharpness"] = _ramp(lap, 15, 90)
    if lap < 25:
        issues.append("q_blurry")

    # 3) Yoritilganlik
    mean = float(core.mean())
    comp["brightness"] = _band(mean, 35, 80, 185, 235)
    if mean < 60:
        issues.append("q_too_dark")
    elif mean > 205:
        issues.append("q_too_bright")

    # 4) Kontrast
    std = float(core.std())
    comp["contrast"] = _ramp(std, 12, 35)
    if std < 15:
        issues.append("q_low_contrast")

    # 5) Yorug'lik bir xilligi (chap/o'ng yarim)
    left, right = core[:, : core.shape[1] // 2].mean(), core[:, core.shape[1] // 2 :].mean()
    diff = abs(left - right) / (max(left, right) + 1e-6)
    comp["uniformity"] = 1.0 - _ramp(diff, 0.25, 0.6)
    if diff > 0.5:
        issues.append("q_uneven_light")

    # 6) Ekspozitsiya — kesilgan (0 yoki 255) piksellar ulushi
    clipped = float(((core <= 5) | (core >= 250)).mean())
    comp["exposure"] = 1.0 - _ramp(clipped, 0.03, 0.2)

    # 7) Bosh holati
    yaw, pitch, roll = head_pose_from_kps(face.kps)
    pose_dev = max(abs(yaw) / 25.0, abs(pitch) / 35.0, abs(roll) / 20.0)
    comp["pose"] = 1.0 - _ramp(pose_dev, 0.4, 1.2)
    if pose_dev > 1.0:
        issues.append("q_look_straight")

    # 8) Kadrda to'liq joylashganlik
    x1, y1, x2, y2 = face.bbox
    margin = min(x1, y1, w - x2, h - y2) / max(face.width, 1.0)
    comp["framing"] = _ramp(margin, -0.15, 0.05)
    if margin < -0.05:
        issues.append("q_center_face")

    # 9) Detektor ishonchi
    comp["confidence"] = _ramp(face.score, 0.5, 0.8)

    total_w = sum(_WEIGHTS.values())
    log_sum = sum(_WEIGHTS[k] * math.log(max(v, 0.02)) for k, v in comp.items())
    score = 100.0 * math.exp(log_sum / total_w)
    return Quality(score=score, components=comp, issues=issues, yaw=yaw, pitch=pitch, roll=roll)
