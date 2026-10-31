import math

import numpy as np
import pytest

from faceid.core.align import ARCFACE_DST, umeyama
from faceid.core.matcher import identify, score_against, verify
from faceid.core.quality import head_pose_from_kps
from faceid.evaluation import pad_metrics, verification_metrics


def _rand_unit(rng, n=512):
    v = rng.normal(size=n).astype(np.float32)
    return v / np.linalg.norm(v)


def test_umeyama_recovers_similarity():
    ang, s, t = math.radians(17), 2.3, np.array([40.0, -12.0])
    r = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
    src = ARCFACE_DST.astype(np.float64)
    dst = (s * (r @ src.T)).T + t
    m = umeyama(src, dst)
    np.testing.assert_allclose(m[:, :2], s * r, atol=1e-6)
    np.testing.assert_allclose(m[:, 2], t, atol=1e-6)


def test_frontal_pose_is_near_zero():
    yaw, pitch, roll = head_pose_from_kps(ARCFACE_DST * 3)
    assert abs(yaw) < 3 and abs(roll) < 1 and abs(pitch) < 12


def test_pose_yaw_sign():
    kps = ARCFACE_DST.copy()
    kps[2, 0] += 8  # burun rasmning o'ng tomoniga
    yaw, _, _ = head_pose_from_kps(kps)
    assert yaw > 10


def test_verify_and_identify():
    rng = np.random.default_rng(1)
    a, b = _rand_unit(rng), _rand_unit(rng)
    near_a = a + 0.3 * _rand_unit(rng)
    gallery = {1: np.stack([a, a + 0.05 * _rand_unit(rng)]), 2: np.stack([b])}
    assert verify(near_a, gallery[1], 0.45).accepted
    assert not verify(near_a, gallery[2], 0.45).accepted
    m = identify(near_a, gallery, 0.45, 0.08)
    assert m.accepted and m.user_id == 1
    assert identify(_rand_unit(rng), gallery, 0.45, 0.08).reason == "no_match"
    assert identify(a, {}, 0.45, 0.08).reason == "no_users"


def test_identify_rejects_ambiguous():
    rng = np.random.default_rng(2)
    a = _rand_unit(rng)
    gallery = {1: a[None], 2: (a + 0.02 * _rand_unit(rng))[None]}
    m = identify(a, gallery, 0.45, 0.08)
    assert not m.accepted and m.reason == "ambiguous"


def test_score_against_uses_top2():
    a = np.array([1, 0], np.float32)
    t = np.array([[1, 0], [0, 1], [0.8, 0.6]], np.float32)
    assert score_against(a, t) == pytest.approx(0.6 * 1.0 + 0.4 * 0.8)


def test_verification_metrics():
    rng = np.random.default_rng(0)
    gen = rng.normal(0.7, 0.08, 3000)
    imp = rng.normal(0.0, 0.08, 30000)
    rep = verification_metrics(gen, imp, current=0.45)
    assert rep.eer < 1e-3
    assert rep.fmr_at_current < 1e-3 and rep.fnmr_at_current < 0.01
    assert 1e-3 in rep.at_fmr


def test_pad_metrics():
    m = pad_metrics(np.array([0.9, 0.8, 0.2]), np.array([0.1, 0.75]), 0.7)
    assert m["APCER"] == pytest.approx(0.5)
    assert m["BPCER"] == pytest.approx(1 / 3)
