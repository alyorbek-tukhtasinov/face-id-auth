"""Biometrik shablonlarni shifrlash (ISO/IEC 24745 tamoyillari).

* AES-256-GCM — maxfiylik va yaxlitlik (har bir yozuv uchun noyob 96-bit nonce).
* AAD (qo'shimcha autentifikatsiya ma'lumoti) — yozuvni foydalanuvchi va
  shablon ID siga bog'laydi: shifrlangan shablonni boshqa foydalanuvchi
  yozuviga ko'chirib qo'yish hujumi ishlamaydi.
* Asosiy kalit OS ning xavfsiz omborida saqlanadi:
  Windows — Credential Manager (DPAPI), macOS — Keychain, Linux — Secret Service.
  Ombor mavjud bo'lmasa, kalit faqat egasi o'qiy oladigan faylda saqlanadi.
"""

from __future__ import annotations

import base64
import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SERVICE = "FaceIDNext"
KEY_NAME = "master-key-v1"


class KeyStore:
    def __init__(self, fallback_dir: Path, use_keyring: bool = True) -> None:
        self.fallback = fallback_dir / ".master.key"
        self.use_keyring = use_keyring and not os.environ.get("FACEID_NO_KEYRING")
        self.backend = "file"

    def _keyring(self):
        if not self.use_keyring:
            return None
        try:
            import keyring
            from keyring.backends import fail

            kr = keyring.get_keyring()
            if isinstance(kr, fail.Keyring) or "fail" in type(kr).__module__ or "null" in type(kr).__module__:
                return None
            return keyring
        except Exception:  # noqa: BLE001
            return None

    def load_or_create(self) -> bytes:
        kr = self._keyring()
        if kr is not None:
            try:
                val = kr.get_password(SERVICE, KEY_NAME)
                if val:
                    self.backend = "keyring"
                    return base64.b64decode(val)
                if not self.fallback.exists():
                    key = AESGCM.generate_key(bit_length=256)
                    kr.set_password(SERVICE, KEY_NAME, base64.b64encode(key).decode())
                    self.backend = "keyring"
                    return key
            except Exception:  # noqa: BLE001 — ombor ishlamasa faylga o'tamiz
                pass
        if self.fallback.exists():
            return base64.b64decode(self.fallback.read_bytes())
        key = AESGCM.generate_key(bit_length=256)
        self._write_private(self.fallback, base64.b64encode(key))
        return key

    @staticmethod
    def _write_private(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        if sys.platform == "win32":
            try:
                import subprocess

                user = os.environ.get("USERNAME", "")
                if user:
                    subprocess.run(["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
                                   capture_output=True, check=False)
            except Exception:  # noqa: BLE001
                pass

    def destroy(self) -> None:
        kr = self._keyring()
        if kr is not None:
            try:
                kr.delete_password(SERVICE, KEY_NAME)
            except Exception:  # noqa: BLE001
                pass
        if self.fallback.exists():
            self.fallback.write_bytes(secrets.token_bytes(64))
            self.fallback.unlink()


class TemplateCipher:
    VERSION = b"\x01"

    def __init__(self, key: bytes) -> None:
        if len(key) != 32:
            raise ValueError("AES-256 kaliti 32 bayt bo'lishi kerak")
        self._aes = AESGCM(key)

    def encrypt(self, data: bytes, aad: bytes) -> bytes:
        nonce = secrets.token_bytes(12)
        return self.VERSION + nonce + self._aes.encrypt(nonce, data, aad)

    def decrypt(self, blob: bytes, aad: bytes) -> bytes:
        if blob[:1] != self.VERSION:
            raise ValueError("Noma'lum shifr versiyasi")
        return self._aes.decrypt(blob[1:13], blob[13:], aad)
