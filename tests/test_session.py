"""Sessiya holat mashinasi — neyron tarmoqlarsiz, simulyatsiya qilingan foydalanuvchi bilan."""

from __future__ import annotations

import numpy as np
import pytest

from faceid.config import Settings
from faceid.core.types import Face, Quality
from faceid.liveness.challenge import Action
from faceid.liveness.landmarks import MeshFace
from faceid.session import BiometricSession, Mode, Phase


def unit(seed):
    v = np.random.default_rng(seed).normal(size=512).astype(np.float32)
    return v / np.linalg.norm(v)


class SimUser:
    """Ekrandagi ko'rsatmaga mos harakat qiladigan "foydalanuvchi"."""

    def __init__(self, identity: np.ndarray, pad: float = 0.95):
        self.identity = identity
        self.pad = pad
        self.faces = 1
        self.session: BiometricSession | None = None
        self.step = 0
        self.swap_to: np.ndarray | None = None
        self.jump = False
        self.cooperative = True

    def mesh(self) -> MeshFace:
        s = self.session
        self.step += 1
        yaw = blink = smile = jaw = 0.0
        if self.cooperative and s.phase is Phase.CHALLENGE and s.challenge.armed and self.step % 3 != 0:
            act = s.challenge.current
            yaw = {Action.TURN_LEFT: 0.5, Action.TURN_RIGHT: -0.5}.get(act, 0.0)
            blink = 0.9 if act is Action.BLINK else 0.0
            smile = 0.8 if act is Action.SMILE else 0.0
            jaw = 0.7 if act is Action.OPEN_MOUTH else 0.0
        if s.phase is Phase.CAPTURE and s.mode is Mode.ENROLL:
            name = s.enroll_targets[len(s.samples)][0]
            yaw = {"slight_left": 0.2, "slight_right": -0.2}.get(name, 0.0)
        blend = {"eyeBlinkLeft": blink, "eyeBlinkRight": blink, "mouthSmileLeft": smile, "mouthSmileRight": smile,
                 "jawOpen": jaw}
        return MeshFace(points=np.zeros((478, 3), np.float32), blend=blend, yaw_ratio=yaw)


class FakeLandmarker:
    def __init__(self, user):
        self.u = user

    def process_roi(self, frame, bbox):
        return [self.u.mesh() for _ in range(self.u.faces)]


class FakeDetector:
    def __init__(self, user):
        self.u = user
        self.x = 540.0

    def detect(self, frame, max_faces=0):
        if self.u.jump and self.u.session.phase is Phase.CHALLENGE:
            self.x = 100.0
        b = np.array([self.x, 200, self.x + 200, 460], np.float32)
        return [Face(bbox=b + i * 300, kps=np.zeros((5, 2), np.float32), score=0.9) for i in range(self.u.faces)]


class FakePAD:
    def __init__(self, user):
        self.u = user

    def score(self, frame, bbox):
        return self.u.pad


class FakeEngine:
    def __init__(self, user, settings):
        self.settings = settings
        self.u = user
        self.landmarker = FakeLandmarker(user)
        self.detector = FakeDetector(user)
        self.pad = FakePAD(user)

    def quality(self, frame, face):
        return Quality(score=90, components={"sharpness": 1.0})

    def embed_face(self, frame, face):
        ident = self.u.identity
        if self.u.swap_to is not None and self.u.session.phase is Phase.CAPTURE:
            ident = self.u.swap_to
        noise = np.random.default_rng(self.u.step).normal(size=512).astype(np.float32) * 0.01
        v = ident + noise
        return v / np.linalg.norm(v)


def run(user: SimUser, mode: Mode, gallery: dict, settings: Settings | None = None, max_frames=600):
    s = settings or Settings()
    eng = FakeEngine(user, s)
    sess = BiometricSession(eng, mode, lambda: gallery, s)
    user.session = sess
    rng = np.random.default_rng(0)
    for i in range(max_frames):
        frame = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)
        sess.process(frame, ts=i / 15)
        if sess.result is not None:
            return sess.result
    raise AssertionError("sessiya tugamadi")


def test_auth_success():
    me = unit(1)
    res = run(SimUser(me), Mode.AUTH, {7: np.stack([me, me])})
    assert res.success, res
    assert res.user_id == 7 and res.score > 0.9 and res.pad_score > 0.9


def test_auth_unknown_person():
    res = run(SimUser(unit(2)), Mode.AUTH, {7: unit(1)[None]})
    assert not res.success and res.reason == "no_match"


def test_auth_spoof_rejected_even_if_identity_matches():
    me = unit(1)
    res = run(SimUser(me, pad=0.2), Mode.AUTH, {7: me[None]})
    assert not res.success and res.reason == "pad_spoof"


def test_auth_photo_cannot_do_challenges():
    me = unit(1)
    u = SimUser(me)
    u.cooperative = False  # rasm harakat qila olmaydi
    res = run(u, Mode.AUTH, {7: me[None]})
    assert not res.success and res.reason == "challenge_timeout"


def test_face_swap_during_session():
    me = unit(1)
    u = SimUser(me)
    u.swap_to = unit(3)
    res = run(u, Mode.AUTH, {7: me[None]})
    assert not res.success and res.reason == "face_swap"


def test_face_jump_detected():
    me = unit(1)
    u = SimUser(me)
    u.jump = True
    res = run(u, Mode.AUTH, {7: me[None]})
    assert not res.success and res.reason == "face_swap"


def test_second_face_appears():
    me = unit(1)
    u = SimUser(me)
    eng_res = None
    s = Settings()
    eng = FakeEngine(u, s)
    sess = BiometricSession(eng, Mode.AUTH, lambda: {7: me[None]}, s)
    u.session = sess
    rng = np.random.default_rng(0)
    for i in range(300):
        if sess.phase is Phase.CHALLENGE:
            u.faces = 2
        sess.process(rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8), ts=i / 15)
        if sess.result:
            eng_res = sess.result
            break
    assert eng_res is not None and eng_res.reason == "multiple_faces"


def test_session_timeout():
    me = unit(1)
    u = SimUser(me)
    u.faces = 0
    s = Settings()
    s.session_timeout_s = 3
    res = run(u, Mode.AUTH, {7: me[None]}, s)
    assert res.reason == "session_timeout"


def test_injection_frozen_frames():
    me = unit(1)
    u = SimUser(me)
    s = Settings()
    eng = FakeEngine(u, s)
    sess = BiometricSession(eng, Mode.AUTH, lambda: {7: me[None]}, s)
    u.session = sess
    frame = np.random.default_rng(0).integers(0, 255, (720, 1280, 3), dtype=np.uint8)
    for i in range(100):
        sess.process(frame, ts=i / 15)
        if sess.result:
            break
    assert sess.result is not None and sess.result.reason == "inj_frozen_stream"


def test_enroll_success_collects_samples():
    res = run(SimUser(unit(5)), Mode.ENROLL, {})
    assert res.success, res
    assert len(res.embeddings) == Settings().enroll_samples
    assert res.details["consistency"] > 0.9


def test_enroll_duplicate_rejected():
    me = unit(5)
    res = run(SimUser(me), Mode.ENROLL, {3: me[None]})
    assert not res.success and res.reason == "already_enrolled" and res.user_id == 3


@pytest.mark.parametrize("n", [2, 4])
def test_challenge_count_setting(n):
    s = Settings()
    s.challenge_count = n
    me = unit(1)
    u = SimUser(me)
    res = run(u, Mode.AUTH, {1: me[None]}, s)
    assert res.success and len(res.details["challenges"]) == n
