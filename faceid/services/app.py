"""Ilova xizmatlari: ma'lumotlar bazasi, administrator paroli, kirish siyosati."""

from __future__ import annotations

import time
from dataclasses import dataclass

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from ..config import Settings, data_dir
from ..session import Mode, SessionResult
from ..storage.crypto import KeyStore, TemplateCipher
from ..storage.db import Database, User


def _derive(master: bytes, info: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=info).derive(master)


@dataclass
class AuthOutcome:
    success: bool
    reason: str
    user: User | None = None
    score: float = 0.0
    locked_for_s: int = 0


class FaceIDService:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings.load()
        base = data_dir()
        self.keystore = KeyStore(base)
        master = self.keystore.load_or_create()
        self.db = Database(base / "faceid.db", TemplateCipher(_derive(master, b"faceid/templates/v1")),
                           _derive(master, b"faceid/audit/v1"))
        self._ph = PasswordHasher()  # Argon2id
        self.db.prune_audit(self.settings.audit_retention_days)

    # ------------------------------------------------------------- admin
    @property
    def has_admin_password(self) -> bool:
        return self.db.get_meta("admin_pw") is not None

    def set_admin_password(self, password: str) -> None:
        if len(password) < 8:
            raise ValueError("Parol kamida 8 belgidan iborat bo'lishi kerak")
        self.db.set_meta("admin_pw", self._ph.hash(password))
        self.db.audit("admin_password_set")

    def check_admin_password(self, password: str) -> bool:
        locked = float(self.db.get_meta("admin_locked_until") or 0)
        if time.time() < locked:
            return False
        h = self.db.get_meta("admin_pw")
        if not h:
            return False
        try:
            self._ph.verify(h, password)
            self.db.set_meta("admin_failed", "0")
            self.db.audit("admin_login", ok=True)
            return True
        except VerificationError:
            failed = int(self.db.get_meta("admin_failed") or 0) + 1
            self.db.set_meta("admin_failed", str(failed))
            if failed >= self.settings.max_failed_attempts:
                self.db.set_meta("admin_locked_until", str(time.time() + self.settings.lockout_base_s * 4))
                self.db.set_meta("admin_failed", "0")
            self.db.audit("admin_login", ok=False)
            return False

    def admin_locked_for(self) -> int:
        return max(0, int(float(self.db.get_meta("admin_locked_until") or 0) - time.time()))

    # -------------------------------------------------------------- flows
    def gallery(self):
        """Faqat bloklanmagan foydalanuvchilar."""
        now = time.time()
        active = {u.id for u in self.db.users() if u.locked_until <= now}
        return {k: v for k, v in self.db.gallery().items() if k in active}

    def locked_for(self, uid: int) -> int:
        u = self.db.user(uid)
        return max(0, int(u.locked_until - time.time())) if u else 0

    # Umumiy cheklov: 1:N rejimida noma'lum yuz bilan ketma-ket urinishlar
    # (masalan, turli rasmlar/niqoblarni sinab ko'rish) ham bloklanadi.
    def global_locked_for(self) -> int:
        return max(0, int(float(self.db.get_meta("auth_locked_until") or 0) - time.time()))

    def _global_attempt(self, success: bool) -> None:
        if success:
            self.db.set_meta("auth_streak", "0")
            return
        streak = int(self.db.get_meta("auth_streak") or 0) + 1
        if streak >= self.settings.max_failed_attempts:
            n = int(self.db.get_meta("auth_lockouts") or 0)
            self.db.set_meta("auth_locked_until", str(time.time() + self.settings.lockout_base_s * (2 ** min(n, 6))))
            self.db.set_meta("auth_lockouts", str(n + 1))
            self.db.audit("global_lockout", streak=streak)
            streak = 0
        self.db.set_meta("auth_streak", str(streak))

    def complete_enrollment(self, name: str, result: SessionResult) -> int:
        if not result.success:
            raise ValueError(result.reason)
        if self.db.user_by_name(name):
            raise ValueError("name_taken")
        role = "admin" if not self.db.users() else "user"
        uid = self.db.add_user(name, result.embeddings, result.qualities, role=role)
        self.db.audit("enroll", uid, templates=len(result.embeddings), pad=round(result.pad_score, 3),
                      **{k: v for k, v in result.details.items() if k in ("consistency", "challenges")})
        return uid

    def record_auth(self, result: SessionResult, mode: Mode = Mode.AUTH, claimed: int | None = None) -> AuthOutcome:
        uid = result.user_id if result.success else claimed
        # Bloklangan foydalanuvchi galereyada yo'q, lekin 1:1 rejimda tekshiramiz
        if claimed is not None and self.locked_for(claimed):
            self.db.audit("auth", claimed, ok=False, reason="locked")
            return AuthOutcome(False, "locked", self.db.user(claimed), locked_for_s=self.locked_for(claimed))
        self.db.record_attempt(uid, result.success, self.settings.lockout_base_s, self.settings.max_failed_attempts)
        self._global_attempt(result.success)
        self.db.audit("auth", uid, ok=result.success, reason=result.reason, score=round(result.score, 4),
                      pad=round(result.pad_score, 3), mode=mode.value)
        user = self.db.user(uid) if uid is not None else None
        locked = max(self.locked_for(uid) if uid is not None else 0, self.global_locked_for())
        return AuthOutcome(result.success, result.reason, user, result.score, locked)

    def delete_user(self, uid: int) -> None:
        self.db.delete_user(uid)
        self.db.audit("user_deleted", uid)

    def wipe_all(self) -> None:
        """Barcha biometrik ma'lumotlarni butunlay o'chirish (unutilish huquqi)."""
        for u in self.db.users():
            self.db.delete_user(u.id)
        self.db.audit("wipe_all")
