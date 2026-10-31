"""Aktiv hayotiylik: tasodifiy challenge-javob.

Har sessiyada harakatlar ketma-ketligi kriptografik tasodifiy tanlanadi
(``secrets``), shuning uchun oldindan yozib olingan video bilan o'tib
bo'lmaydi. Har bir harakatdan oldin yuz neytral holatga qaytishi shart —
bu "doimiy tabassum" yoki "doimiy burilgan" holatda ushlab turishni bloklaydi.
Kamida bitta bosh burish (3D harakat) va bitta mimika (deformatsiya) talab
qilinadi: tekis rasm/qog'oz niqob ikkalasini bir vaqtda bajara olmaydi.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from enum import Enum

from .landmarks import MeshFace


class Action(str, Enum):
    BLINK = "blink"
    SMILE = "smile"
    OPEN_MOUTH = "open_mouth"
    TURN_LEFT = "turn_left"  # foydalanuvchining o'z chap tomoniga
    TURN_RIGHT = "turn_right"


HEAD_ACTIONS = (Action.TURN_LEFT, Action.TURN_RIGHT)
FACE_ACTIONS = (Action.BLINK, Action.SMILE, Action.OPEN_MOUTH)


@dataclass
class Thresholds:
    turn: float = 0.38  # yaw_ratio: ~20-25°
    neutral_turn: float = 0.18
    blink: float = 0.55
    eyes_open: float = 0.65  # 1 - max(blink) — ko'zlar ochiq
    smile: float = 0.55
    neutral_smile: float = 0.3
    jaw: float = 0.40
    neutral_jaw: float = 0.18
    hold_frames: int = 2  # harakat ketma-ket shuncha kadr ko'rinishi kerak


def random_sequence(n: int) -> list[Action]:
    """Kamida bitta bosh burish va bitta mimika bo'lgan tasodifiy ketma-ketlik."""
    rng = secrets.SystemRandom()
    n = max(2, min(n, 5))
    seq = [rng.choice(HEAD_ACTIONS), rng.choice(FACE_ACTIONS)]
    pool = [a for a in Action if a not in seq]
    rng.shuffle(pool)
    seq += pool[: n - 2]
    rng.shuffle(seq)
    return seq


def is_neutral(m: MeshFace, th: Thresholds, hw_mirrored: bool = False) -> bool:
    return (
        abs(m.yaw_ratio) < th.neutral_turn
        and m.smile < th.neutral_smile
        and m.jaw_open < th.neutral_jaw
        and m.eyes_open > th.eyes_open - 0.15
    )


def action_detected(action: Action, m: MeshFace, th: Thresholds, hw_mirrored: bool = False) -> bool:
    yaw = -m.yaw_ratio if hw_mirrored else m.yaw_ratio
    if action is Action.TURN_LEFT:
        return yaw > th.turn
    if action is Action.TURN_RIGHT:
        return yaw < -th.turn
    if action is Action.BLINK:
        return m.blink > th.blink
    if action is Action.SMILE:
        return m.smile > th.smile and abs(yaw) < th.turn
    if action is Action.OPEN_MOUTH:
        return m.jaw_open > th.jaw and abs(yaw) < th.turn
    return False


def wrong_action(action: Action, m: MeshFace, th: Thresholds, hw_mirrored: bool = False) -> bool:
    """Teskari tomonga burilish — tasodifiy javob berishga urinish belgisi."""
    yaw = -m.yaw_ratio if hw_mirrored else m.yaw_ratio
    if action is Action.TURN_LEFT:
        return yaw < -th.turn
    if action is Action.TURN_RIGHT:
        return yaw > th.turn
    return False


@dataclass
class ChallengeRunner:
    sequence: list[Action]
    timeout_s: float
    th: Thresholds = field(default_factory=Thresholds)
    hw_mirrored: bool = False
    index: int = 0
    armed: bool = False  # neytral holat ko'rildi, harakat kutilmoqda
    started_at: float | None = None
    _hold: int = 0
    _wrong: int = 0
    failed_reason: str = ""

    @property
    def current(self) -> Action | None:
        return self.sequence[self.index] if self.index < len(self.sequence) else None

    @property
    def done(self) -> bool:
        return self.index >= len(self.sequence)

    @property
    def failed(self) -> bool:
        return bool(self.failed_reason)

    def update(self, m: MeshFace, now: float) -> bool:
        """Bitta kadrni qayta ishlaydi. Joriy harakat bajarilsa True qaytaradi."""
        if self.done or self.failed:
            return False
        if self.started_at is None:
            self.started_at = now
        if now - self.started_at > self.timeout_s:
            self.failed_reason = "challenge_timeout"
            return False
        act = self.sequence[self.index]
        if not self.armed:
            if is_neutral(m, self.th) or (act is Action.BLINK and abs(m.yaw_ratio) < self.th.neutral_turn
                                          and m.eyes_open > self.th.eyes_open):
                self.armed = True
            return False
        if wrong_action(act, m, self.th, self.hw_mirrored):
            self._wrong += 1
            if self._wrong >= 4:
                self.failed_reason = "challenge_wrong"
            return False
        if action_detected(act, m, self.th, self.hw_mirrored):
            self._hold += 1
            if self._hold >= self.th.hold_frames:
                self.index += 1
                self.armed = False
                self._hold = 0
                self._wrong = 0
                self.started_at = now
                return True
        else:
            self._hold = 0
        return False
