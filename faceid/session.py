"""Biometrik sessiya: joylashish → aktiv challenge → yakuniy kadr → qaror.

Bitta sinf ham ro'yxatdan o'tish (ENROLL), ham kirish (AUTH) uchun ishlatiladi.
Qaror quyidagi barcha shartlar bajarilgandagina ijobiy bo'ladi:

* injection signallari yo'q (virtual kamera, muzlagan/sintetik oqim);
* butun sessiya davomida kadrda faqat bitta yuz, u uzilmasdan kuzatilgan;
* passiv PAD o'rtacha bahosi chegaradan yuqori;
* barcha tasodifiy challenge'lar vaqtida bajarilgan;
* boshlang'ich va yakuniy kadrdagi shaxs bir xil (yuz almashtirilmagan);
* (AUTH) shaxs ro'yxatdagi foydalanuvchi bilan mos keladi.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from .config import Settings
from .core.matcher import MatchResult, identify, verify
from .core.types import Face, Quality
from .engine import Engine
from .liveness.challenge import Action, ChallengeRunner, is_neutral, random_sequence
from .liveness.injection import InjectionMonitor
from .liveness.landmarks import MeshFace


class Mode(str, Enum):
    ENROLL = "enroll"
    AUTH = "auth"


class Phase(str, Enum):
    POSITION = "position"
    CHALLENGE = "challenge"
    CAPTURE = "capture"
    DONE = "done"


@dataclass
class SessionResult:
    success: bool
    reason: str = ""
    user_id: int | None = None
    score: float = 0.0
    pad_score: float = 0.0
    embeddings: list[np.ndarray] = field(default_factory=list)
    qualities: list[float] = field(default_factory=list)
    details: dict = field(default_factory=dict)


@dataclass
class FrameReport:
    phase: Phase
    instruction: str  # i18n kaliti
    progress: float = 0.0
    face_box: np.ndarray | None = None
    face_ok: bool = False
    quality: Quality | None = None
    pad_score: float | None = None
    action: Action | None = None
    step: int = 0
    steps: int = 0
    action_done: bool = False
    result: SessionResult | None = None


# Ro'yxatdan o'tishda yig'iladigan namunalar: (nom, yaw_ratio oralig'i)
ENROLL_POSES: list[tuple[str, float, float]] = [
    ("front", -0.12, 0.12),
    ("slight_left", 0.10, 0.32),
    ("front", -0.12, 0.12),
    ("slight_right", -0.32, -0.10),
    ("front", -0.12, 0.12),
]

GalleryFn = Callable[[], dict[int, np.ndarray]]


class BiometricSession:
    def __init__(self, engine: Engine, mode: Mode, gallery: GalleryFn, settings: Settings | None = None,
                 claimed_user: int | None = None, camera_mirrored: bool = False, clock: Callable[[], float] = time.monotonic) -> None:
        self.e = engine
        self.s = settings or engine.settings
        self.mode = mode
        self.gallery = gallery
        self.claimed_user = claimed_user
        self.clock = clock
        self.t0: float | None = None  # birinchi kadr vaqti
        self.phase = Phase.POSITION
        self.inj = InjectionMonitor()
        self.camera_mirrored = camera_mirrored
        self.challenge = ChallengeRunner(random_sequence(self.s.challenge_count), self.s.challenge_timeout_s,
                                         hw_mirrored=camera_mirrored)
        self.pad_scores: list[float] = []
        self.anchor: np.ndarray | None = None  # boshlang'ich kadr embeddingi
        self.samples: list[np.ndarray] = []
        self.sample_q: list[float] = []
        self._stable = 0
        self._last_center: tuple[float, float] | None = None
        self._lost_since: float | None = None
        self._last_sample_t = 0.0
        self._frame_i = 0
        self.result: SessionResult | None = None

    # ------------------------------------------------------------------ helpers
    @property
    def enroll_targets(self) -> list[tuple[str, float, float]]:
        n = max(3, min(self.s.enroll_samples, len(ENROLL_POSES)))
        return ENROLL_POSES[:n]

    def _finish(self, success: bool, reason: str = "", **kw) -> SessionResult:
        pad = float(np.mean(self.pad_scores)) if self.pad_scores else 0.0
        self.result = SessionResult(success=success, reason=reason, pad_score=pad, **kw)
        self.phase = Phase.DONE
        return self.result

    def _report(self, instruction: str, **kw) -> FrameReport:
        return FrameReport(phase=self.phase, instruction=instruction, result=self.result, **kw)

    def _position_issue(self, frame: np.ndarray, face: Face) -> str | None:
        h, w = frame.shape[:2]
        fh = face.height / h
        cx, cy = face.center
        if fh < 0.22:
            return "pos_move_closer"
        if fh > 0.80:
            return "pos_move_back"
        if abs(cx - w / 2) > 0.16 * w or abs(cy - h / 2) > 0.20 * h:
            return "pos_center"
        return None

    def _pad_ok(self) -> tuple[bool, float]:
        if len(self.pad_scores) < self.s.passive_min_frames:
            return False, 0.0
        arr = np.asarray(self.pad_scores)
        mean = float(arr.mean())
        frac = float((arr > 0.5).mean())
        return mean >= self.s.passive_threshold and frac >= 0.7, mean

    # --------------------------------------------------------------- main loop
    def process(self, frame: np.ndarray, ts: float | None = None) -> FrameReport:
        if self.phase is Phase.DONE:
            return self._report("done")
        now = self.clock() if ts is None else ts
        if self.t0 is None:
            self.t0 = now
        self._frame_i += 1

        if now - self.t0 > self.s.session_timeout_s:
            self._finish(False, "session_timeout")
            return self._report("fail_session_timeout")

        # 1) Injection
        self.inj.update(frame)
        if self.inj.suspicious:
            self._finish(False, self.inj.flags[0])
            return self._report("fail_" + self.inj.flags[0])

        # 2) Detektor butun kadr bo'yicha (bir nechta yuzni ham ko'radi),
        #    yuz belgilari esa topilgan yuz atrofidagi kesimda.
        faces = [f for f in self.e.detector.detect(frame, max_faces=3) if f.score > 0.6]
        n = len(faces)

        if n == 0:
            if self.phase is not Phase.POSITION:
                self._lost_since = self._lost_since or now
                if now - self._lost_since > 1.2:
                    self._finish(False, "face_lost")
                    return self._report("fail_face_lost")
            self._stable = 0
            return self._report("q_no_face", steps=len(self.challenge.sequence))
        self._lost_since = None

        face = faces[0]
        meshes = self.e.landmarker.process_roi(frame, face.bbox) if n == 1 else []
        n = max(n, len(meshes))
        if n > 1:
            if self.phase is not Phase.POSITION:
                self._finish(False, "multiple_faces")
                return self._report("fail_multiple_faces")
            self._stable = 0
            return self._report("q_multiple_faces")
        if not meshes:
            # Detektor yuzni ko'rdi, lekin yuz belgilari olinmadi (masalan, kuchli burilish)
            self._stable = 0
            return self._report("q_look_straight", face_box=face.bbox, steps=len(self.challenge.sequence))
        mesh = meshes[0]

        # 3) Uzluksizlik — yuz bir kadrda "sakrab" ketmasligi kerak
        c = face.center
        if self._last_center is not None and self.phase is not Phase.POSITION:
            jump = np.hypot(c[0] - self._last_center[0], c[1] - self._last_center[1]) / max(face.width, 1.0)
            if jump > 0.75:
                self._finish(False, "face_swap")
                return self._report("fail_face_swap")
        self._last_center = c

        q = self.e.quality(frame, face)

        # 4) Passiv PAD — har ikkinchi kadrda, yuz deyarli frontal bo'lsa
        pad_now = None
        if self._frame_i % 2 == 0 and abs(mesh.yaw_ratio) < 0.3 and q.components.get("sharpness", 0) > 0.3:
            pad_now = self.e.pad.score(frame, face.bbox)
            self.pad_scores.append(pad_now)

        # Aniq soxtalik (masalan, ekran yoki bosma rasm) — challenge'larni kutmasdan to'xtatamiz
        if len(self.pad_scores) >= 2 * self.s.passive_min_frames:
            recent = float(np.mean(self.pad_scores[-2 * self.s.passive_min_frames:]))
            if recent < 0.5 * self.s.passive_threshold:
                self._finish(False, "pad_spoof", details={"pad_mean": recent})
                return self._report("fail_pad_spoof", face_box=face.bbox)

        common = dict(face_box=face.bbox, quality=q, pad_score=pad_now, steps=len(self.challenge.sequence))

        if self.phase is Phase.POSITION:
            return self._phase_position(frame, face, mesh, q, now, common)
        if self.phase is Phase.CHALLENGE:
            return self._phase_challenge(frame, face, mesh, q, now, common)
        if self.phase is Phase.CAPTURE:
            if self.mode is Mode.AUTH:
                return self._phase_capture_auth(frame, face, mesh, q, now, common)
            return self._phase_capture_enroll(frame, face, mesh, q, now, common)
        return self._report("done")

    # ------------------------------------------------------------------ phases
    def _phase_position(self, frame, face: Face, mesh: MeshFace, q: Quality, now, common) -> FrameReport:
        issue = self._position_issue(frame, face)
        min_q = self.s.enroll_min_quality if self.mode is Mode.ENROLL else self.s.verify_min_quality
        if issue is None and q.issues:
            issue = q.issues[0]
        if issue is None and q.score < min_q:
            issue = "q_low_quality"
        if issue is None and not is_neutral(mesh, self.challenge.th):
            issue = "q_neutral_face"
        if issue:
            self._stable = 0
            return self._report(issue, **common)
        self._stable += 1
        if self._stable < 6:
            return self._report("pos_hold_still", face_ok=True, progress=self._stable / 6 * 0.1, **common)
        self.anchor = self.e.embed_face(frame, face)
        if self.mode is Mode.ENROLL:
            self.samples.append(self.anchor)
            self.sample_q.append(q.score)
        self.phase = Phase.CHALLENGE
        self.challenge.started_at = now
        return self._report("ch_" + self.challenge.current.value, face_ok=True, progress=0.1,
                            action=self.challenge.current, step=1, **common)

    def _phase_challenge(self, frame, face, mesh, q, now, common) -> FrameReport:
        done = self.challenge.update(mesh, now)
        if self.challenge.failed:
            self._finish(False, self.challenge.failed_reason)
            return self._report("fail_" + self.challenge.failed_reason, **common)
        total = len(self.challenge.sequence)
        prog = 0.1 + 0.6 * self.challenge.index / total
        if self.challenge.done:
            self.phase = Phase.CAPTURE
            self._stable = 0
            key = "cap_look_straight" if self.mode is Mode.AUTH else "en_" + self.enroll_targets[len(self.samples)][0]
            return self._report(key, face_ok=True, progress=prog, step=total, action_done=True, **common)
        act = self.challenge.current
        key = ("ch_" + act.value) if self.challenge.armed else "ch_return_neutral"
        return self._report(key, face_ok=True, progress=prog, action=act, step=self.challenge.index + 1,
                            action_done=done, **common)

    def _phase_capture_auth(self, frame, face, mesh, q, now, common) -> FrameReport:
        if not is_neutral(mesh, self.challenge.th) or q.score < self.s.verify_min_quality:
            self._stable = 0
            return self._report("cap_look_straight", progress=0.75, **common)
        self._stable += 1
        if self._stable < 3:
            return self._report("cap_look_straight", face_ok=True, progress=0.8, **common)
        final = self.e.embed_face(frame, face)
        return self._decide_auth(final, common)

    def _phase_capture_enroll(self, frame, face, mesh, q, now, common) -> FrameReport:
        targets = self.enroll_targets
        idx = len(self.samples)
        name, lo, hi = targets[idx]
        prog = 0.7 + 0.28 * idx / len(targets)
        yaw = -mesh.yaw_ratio if self.camera_mirrored else mesh.yaw_ratio
        pose_ok = lo <= yaw <= hi and mesh.smile < 0.35 and mesh.jaw_open < 0.2 and mesh.eyes_open > 0.5
        issues = [i for i in q.issues if not (name != "front" and i == "q_look_straight")]
        if not pose_ok or issues or q.score < self.s.enroll_min_quality * (0.85 if name != "front" else 1.0) \
                or now - self._last_sample_t < 0.35:
            self._stable = 0
            return self._report(issues[0] if issues and pose_ok else "en_" + name, progress=prog, **common)
        self._stable += 1
        if self._stable < 3:
            return self._report("en_" + name, face_ok=True, progress=prog, **common)
        self._stable = 0
        self._last_sample_t = now
        self.samples.append(self.e.embed_face(frame, face))
        self.sample_q.append(q.score)
        if len(self.samples) >= len(targets):
            return self._decide_enroll(common)
        return self._report("en_" + targets[len(self.samples)][0], face_ok=True, action_done=True,
                            progress=0.7 + 0.28 * len(self.samples) / len(targets), **common)

    # --------------------------------------------------------------- decisions
    def _liveness_gate(self, common) -> FrameReport | None:
        ok, mean = self._pad_ok()
        if not ok:
            reason = "pad_insufficient" if len(self.pad_scores) < self.s.passive_min_frames else "pad_spoof"
            self._finish(False, reason, details={"pad_frames": len(self.pad_scores), "pad_mean": mean})
            return self._report("fail_" + reason, **common)
        return None

    def _decide_auth(self, final: np.ndarray, common) -> FrameReport:
        gate = self._liveness_gate(common)
        if gate:
            return gate
        assert self.anchor is not None
        continuity = float(np.dot(self.anchor, final))
        if continuity < 0.5:
            self._finish(False, "face_swap", details={"continuity": continuity})
            return self._report("fail_face_swap", **common)
        probe = self.anchor + final
        probe /= np.linalg.norm(probe) + 1e-12
        gallery = self.gallery()
        if self.claimed_user is not None:
            templates = gallery.get(self.claimed_user, np.zeros((0, 512), np.float32))
            m: MatchResult = verify(probe, templates, self.s.match_threshold)
            m.user_id = self.claimed_user if m.accepted else None
        else:
            m = identify(probe, gallery, self.s.match_threshold, self.s.identification_margin)
        det = {"continuity": continuity, "second": m.second_score, "challenges": [a.value for a in self.challenge.sequence]}
        if not m.accepted:
            self._finish(False, m.reason, score=m.score, details=det)
            return self._report("fail_" + m.reason, **common)
        self._finish(True, user_id=m.user_id, score=m.score, embeddings=[probe], details=det)
        return self._report("ok_welcome", progress=1.0, face_ok=True, **common)

    def _decide_enroll(self, common) -> FrameReport:
        gate = self._liveness_gate(common)
        if gate:
            return gate
        embs = np.stack(self.samples)
        center = embs.mean(0)
        center /= np.linalg.norm(center) + 1e-12
        consistency = float((embs @ center).min())
        if consistency < 0.55:
            self._finish(False, "enroll_inconsistent", details={"consistency": consistency})
            return self._report("fail_enroll_inconsistent", **common)
        gallery = self.gallery()
        if gallery:
            m = identify(center, gallery, self.s.match_threshold, 0.0)
            if m.score >= self.s.match_threshold:
                # identify() noaniqlikda user_id bermaydi — eng yaqin foydalanuvchini o'zimiz topamiz
                from .core.matcher import score_against
                dup = max(gallery, key=lambda u: score_against(center, gallery[u]))
                self._finish(False, "already_enrolled", user_id=dup, score=m.score)
                return self._report("fail_already_enrolled", **common)
        self._finish(True, embeddings=list(embs), qualities=list(self.sample_q),
                     details={"consistency": consistency, "challenges": [a.value for a in self.challenge.sequence]})
        return self._report("ok_enrolled", progress=1.0, face_ok=True, **common)
