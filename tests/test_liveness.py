import numpy as np
import pytest

from faceid.liveness.challenge import FACE_ACTIONS, HEAD_ACTIONS, Action, ChallengeRunner, random_sequence
from faceid.liveness.injection import InjectionMonitor, is_virtual_camera
from faceid.liveness.landmarks import MeshFace


def mesh(yaw=0.0, blink=0.0, smile=0.0, jaw=0.0) -> MeshFace:
    blend = {"eyeBlinkLeft": blink, "eyeBlinkRight": blink, "mouthSmileLeft": smile, "mouthSmileRight": smile,
             "jawOpen": jaw}
    return MeshFace(points=np.zeros((478, 3), np.float32), blend=blend, yaw_ratio=yaw)


ACTION_MESH = {
    Action.BLINK: mesh(blink=0.9),
    Action.SMILE: mesh(smile=0.8),
    Action.OPEN_MOUTH: mesh(jaw=0.7),
    Action.TURN_LEFT: mesh(yaw=0.5),
    Action.TURN_RIGHT: mesh(yaw=-0.5),
}


@pytest.mark.parametrize("n", [2, 3, 4, 5])
def test_sequence_has_head_and_face_actions(n):
    for _ in range(50):
        seq = random_sequence(n)
        assert len(seq) == n and len(set(seq)) == n
        assert any(a in HEAD_ACTIONS for a in seq)
        assert any(a in FACE_ACTIONS for a in seq)


def test_sequences_are_random():
    assert len({tuple(random_sequence(3)) for _ in range(200)}) > 10


def test_runner_completes_with_neutral_between():
    seq = [Action.TURN_LEFT, Action.SMILE, Action.BLINK]
    r = ChallengeRunner(seq, timeout_s=5)
    t = 0.0
    for act in seq:
        # neytralsiz harakat hisoblanmaydi
        assert not r.update(ACTION_MESH[act], t)
        r.update(mesh(), t)
        r.update(ACTION_MESH[act], t + 0.1)
        assert r.update(ACTION_MESH[act], t + 0.2)
        t += 1
    assert r.done and not r.failed


def test_runner_requires_neutral_first():
    r = ChallengeRunner([Action.SMILE, Action.BLINK], timeout_s=5)
    for i in range(10):  # doimiy tabassum — "armed" bo'lmaydi
        r.update(mesh(smile=0.9), i * 0.1)
    assert r.index == 0


def test_runner_timeout():
    r = ChallengeRunner([Action.BLINK, Action.TURN_LEFT], timeout_s=2)
    r.update(mesh(), 0.0)
    r.update(mesh(), 2.5)
    assert r.failed and r.failed_reason == "challenge_timeout"


def test_runner_wrong_direction_fails():
    r = ChallengeRunner([Action.TURN_LEFT, Action.SMILE], timeout_s=5)
    r.update(mesh(), 0)
    for i in range(5):
        r.update(mesh(yaw=-0.6), 0.1 * (i + 1))
    assert r.failed_reason == "challenge_wrong"


def test_runner_hw_mirrored_flips_direction():
    r = ChallengeRunner([Action.TURN_LEFT, Action.SMILE], timeout_s=5, hw_mirrored=True)
    r.update(mesh(), 0)
    r.update(mesh(yaw=-0.5), 0.1)
    assert r.update(mesh(yaw=-0.5), 0.2)


@pytest.mark.parametrize("name,virtual", [
    ("OBS Virtual Camera", True), ("ManyCam Virtual Webcam", True), ("Snap Camera", True),
    ("XSplit VCam", True), ("DroidCam Source 3", True), ("e2eSoft iVCam", True),
    ("Integrated Webcam", False), ("HD User Facing", False), ("Logitech BRIO", False),
    ("USB2.0 HD UVC WebCam", False), ("Integrated Camera", False), ("FaceTime HD Camera", False),
    ("NDI Webcam Video 1", True), ("Camo", True), ("Lenovo EasyCamera", False),
])
def test_virtual_camera_names(name, virtual):
    assert is_virtual_camera(name) is virtual


def test_virtual_camera_allowlist():
    assert not is_virtual_camera("OBS Virtual Camera", allowed=["obs virtual camera"])


def _noisy(rng, base):
    return np.clip(base + rng.normal(0, 3, base.shape), 0, 255).astype(np.uint8)


def test_injection_frozen_stream():
    rng = np.random.default_rng(0)
    still = _noisy(rng, np.full((240, 320, 3), 120.0))
    m = InjectionMonitor()
    for _ in range(40):
        m.update(still)
    assert "inj_frozen_stream" in m.flags


def test_injection_real_noise_ok():
    rng = np.random.default_rng(0)
    base = np.tile(np.linspace(40, 200, 320), (240, 1))[..., None].repeat(3, 2)
    m = InjectionMonitor()
    for _ in range(60):
        m.update(_noisy(rng, base))
    assert not m.suspicious


def test_injection_synthetic_noiseless():
    base = np.tile(np.linspace(40, 200, 320), (240, 1))[..., None].repeat(3, 2)
    m = InjectionMonitor()
    for i in range(60):
        m.update(np.clip(base + (i % 7), 0, 255).astype(np.uint8))  # harakat bor, shovqin yo'q
    assert "inj_synthetic_stream" in m.flags


def test_injection_resolution_change():
    rng = np.random.default_rng(0)
    m = InjectionMonitor()
    m.update(_noisy(rng, np.full((240, 320, 3), 100.0)))
    m.update(_noisy(rng, np.full((480, 640, 3), 100.0)))
    assert "inj_resolution_change" in m.flags
