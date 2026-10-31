"""Yuz vektorlarini solishtirish: 1:1 tasdiqlash va 1:N identifikatsiya."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12))


def score_against(probe: np.ndarray, templates: np.ndarray) -> float:
    """Probe vektorni foydalanuvchining barcha shablonlari bilan solishtiradi.

    Eng yaxshi ikkita natijaning o'rtachasi olinadi — bitta tasodifiy
    yuqori natijaga nisbatan barqarorroq.
    """
    if templates.size == 0:
        return -1.0
    t = templates / (np.linalg.norm(templates, axis=1, keepdims=True) + 1e-12)
    p = probe / (np.linalg.norm(probe) + 1e-12)
    sims = np.sort(t @ p)[::-1]
    if sims.size >= 2:
        return float(0.6 * sims[0] + 0.4 * sims[1])
    return float(sims[0])


@dataclass
class MatchResult:
    user_id: int | None
    score: float
    second_score: float
    accepted: bool
    reason: str = ""


def identify(probe: np.ndarray, gallery: dict[int, np.ndarray], threshold: float, margin: float) -> MatchResult:
    """1:N — galereyadagi eng yaxshi nomzod; noaniqlik bo'lsa rad etadi."""
    if not gallery:
        return MatchResult(None, -1.0, -1.0, False, "no_users")
    scores = sorted(((score_against(probe, t), uid) for uid, t in gallery.items()), reverse=True)
    best, uid = scores[0]
    second = scores[1][0] if len(scores) > 1 else -1.0
    if best < threshold:
        return MatchResult(None, best, second, False, "no_match")
    if second >= threshold and best - second < margin:
        return MatchResult(None, best, second, False, "ambiguous")
    return MatchResult(uid, best, second, True)


def verify(probe: np.ndarray, templates: np.ndarray, threshold: float) -> MatchResult:
    s = score_against(probe, templates)
    return MatchResult(None, s, -1.0, s >= threshold, "" if s >= threshold else "no_match")
