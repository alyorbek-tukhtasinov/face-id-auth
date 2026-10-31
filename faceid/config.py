"""Sozlamalar va fayl yo'llari.

Barcha ma'lumotlar foydalanuvchining shaxsiy papkasida saqlanadi:
  Windows : %LOCALAPPDATA%\\FaceIDNext
  macOS   : ~/Library/Application Support/FaceIDNext
  Linux   : ~/.local/share/FaceIDNext
``FACEID_HOME`` muhit o'zgaruvchisi orqali boshqa joy ko'rsatish mumkin.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

APP_NAME = "FaceIDNext"


def data_dir() -> Path:
    env = os.environ.get("FACEID_HOME")
    if env:
        base = Path(env).expanduser()
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def models_dir() -> Path:
    env = os.environ.get("FACEID_MODELS")
    d = Path(env).expanduser() if env else data_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


BUNDLED_MODELS = Path(__file__).resolve().parent.parent / "assets" / "models"


@dataclass
class Settings:
    """Foydalanuvchi o'zgartira oladigan sozlamalar (settings.json)."""

    # --- Interfeys ---
    language: str = "uz"  # uz | ru | en
    voice_enabled: bool = True
    camera_index: int = 0
    camera_width: int = 1280
    camera_height: int = 720
    mirror_preview: bool = True
    # Ba'zi kamera drayverlari tasvirni o'zi ko'zgulaydi — bunda "chap/o'ng" teskari bo'ladi.
    camera_hw_mirrored: bool = False

    # --- Tanib olish (ArcFace cosine o'xshashlik) ---
    # Qattiq standart qiymat. Kattaroq qiymat — xavfsizroq, lekin egasini
    # rad etish ehtimoli oshadi. `python -m faceid evaluate` bilan kalibrlang.
    match_threshold: float = 0.45
    # 1:N rejimida eng yaxshi va ikkinchi nomzod orasidagi minimal farq.
    identification_margin: float = 0.08

    # --- Sifat (ISO/IEC 29794-5 ga asoslangan) ---
    enroll_min_quality: float = 60.0
    verify_min_quality: float = 40.0
    enroll_samples: int = 5

    # --- Hayotiylik (PAD, ISO/IEC 30107-3) ---
    passive_threshold: float = 0.70  # sessiya bo'yicha o'rtacha "real" ehtimoli
    passive_min_frames: int = 6
    challenge_count: int = 3
    challenge_timeout_s: float = 7.0
    session_timeout_s: float = 45.0
    block_virtual_cameras: bool = True
    allowed_camera_names: list[str] = field(default_factory=list)

    # --- Xavfsizlik siyosati ---
    max_failed_attempts: int = 5
    lockout_base_s: int = 30  # har keyingi blokda 2 barobar oshadi
    audit_retention_days: int = 365

    @classmethod
    def path(cls) -> Path:
        return data_dir() / "settings.json"

    @classmethod
    def load(cls) -> Settings:
        p = cls.path()
        s = cls()
        if p.exists():
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                known = {f.name for f in fields(cls)}
                for k, v in raw.items():
                    if k in known:
                        setattr(s, k, v)
            except (OSError, ValueError):
                pass
        return s

    def save(self) -> None:
        self.path().write_text(json.dumps(asdict(self), indent=2, ensure_ascii=False), encoding="utf-8")
