"""Neyron tarmoq modellari: yuklab olish va SHA-256 bilan yaxlitligini tekshirish.

Katta modellar repozitoriyga qo'shilmaydi — birinchi ishga tushirishda
rasmiy manbalardan yuklanadi va har bir fayl xesh bo'yicha tekshiriladi
(ta'minot zanjiri hujumlaridan himoya).
"""

from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .config import BUNDLED_MODELS, models_dir

ProgressFn = Callable[[str, int, int], None]


@dataclass(frozen=True)
class ModelFile:
    name: str
    sha256: str
    url: str
    member: str | None = None  # zip ichidagi fayl nomi
    archive_sha256: str | None = None
    license: str = ""


BUFFALO_L = "https://github.com/deepinsight/insightface/releases/download/v0.7/buffalo_l.zip"
BUFFALO_L_SHA = "80ffe37d8a5940d59a7384c201a2a38d4741f2f3c51eef46ebb28218a7b0ca2f"

DOWNLOADABLE: dict[str, ModelFile] = {
    "detector": ModelFile(
        name="det_10g.onnx",
        sha256="5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91",
        url=BUFFALO_L,
        member="det_10g.onnx",
        archive_sha256=BUFFALO_L_SHA,
        license="InsightFace SCRFD-10G — faqat notijorat/ilmiy maqsadda",
    ),
    "recognizer": ModelFile(
        name="w600k_r50.onnx",
        sha256="4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43",
        url=BUFFALO_L,
        member="w600k_r50.onnx",
        archive_sha256=BUFFALO_L_SHA,
        license="InsightFace ArcFace R50 (WebFace600K) — faqat notijorat/ilmiy maqsadda",
    ),
    "landmarker": ModelFile(
        name="face_landmarker.task",
        sha256="64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        url="https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task",
        license="Google MediaPipe — Apache 2.0",
    ),
}

# Repozitoriy bilan birga keladigan kichik modellar (Apache 2.0, Minivision).
BUNDLED: dict[str, tuple[str, str]] = {
    "pad_v2": ("minifasnet_v2_2.7_80x80.onnx", "a4c272348fe35e1b2a023e2877c918dbf359a1c434508c6c13cab1c9d2172954"),
    "pad_v1se": ("minifasnet_v1se_4.0_80x80.onnx", "40d9c8fb92fa6fed5e964ba69d8d125f160bc4c9227583080456acb6e7a6ffe9"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_path(key: str) -> Path:
    if key in DOWNLOADABLE:
        return models_dir() / DOWNLOADABLE[key].name
    if key in BUNDLED:
        return BUNDLED_MODELS / BUNDLED[key][0]
    raise KeyError(key)


def missing_models(verify_hash: bool = False) -> list[str]:
    out = []
    for key, mf in DOWNLOADABLE.items():
        p = models_dir() / mf.name
        if not p.exists() or (verify_hash and sha256_file(p) != mf.sha256):
            out.append(key)
    for key, (_name, sha) in BUNDLED.items():
        p = model_path(key)
        if not p.exists() or (verify_hash and sha256_file(p) != sha):
            out.append(key)
    return out


def _download(url: str, dst: Path, progress: ProgressFn | None, label: str) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "FaceIDNext/2.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if progress:
                progress(label, done, total)


def ensure_models(progress: ProgressFn | None = None) -> None:
    """Yetishmayotgan modellarni yuklab oladi va xeshini tekshiradi."""
    target = models_dir()
    need = [k for k in DOWNLOADABLE if k in missing_models(verify_hash=True)]
    archives: dict[str, list[ModelFile]] = {}
    for key in need:
        mf = DOWNLOADABLE[key]
        if mf.member:
            archives.setdefault(mf.url, []).append(mf)
        else:
            with tempfile.TemporaryDirectory() as td:
                tmp = Path(td) / mf.name
                _download(mf.url, tmp, progress, mf.name)
                if sha256_file(tmp) != mf.sha256:
                    raise RuntimeError(f"{mf.name}: SHA-256 mos kelmadi — fayl buzilgan yoki soxta")
                shutil.move(str(tmp), target / mf.name)

    for url, members in archives.items():
        with tempfile.TemporaryDirectory() as td:
            arc = Path(td) / "archive.zip"
            _download(url, arc, progress, Path(url).name)
            if members[0].archive_sha256 and sha256_file(arc) != members[0].archive_sha256:
                raise RuntimeError(f"{Path(url).name}: SHA-256 mos kelmadi")
            with zipfile.ZipFile(arc) as zf:
                names = {Path(n).name: n for n in zf.namelist()}
                for mf in members:
                    src = names.get(mf.member or "")
                    if src is None:
                        raise RuntimeError(f"Arxivda {mf.member} topilmadi")
                    out = Path(td) / mf.name
                    with zf.open(src) as s, open(out, "wb") as d:
                        shutil.copyfileobj(s, d)
                    if sha256_file(out) != mf.sha256:
                        raise RuntimeError(f"{mf.name}: SHA-256 mos kelmadi")
                    shutil.move(str(out), target / mf.name)

    still = missing_models()
    if still:
        raise RuntimeError("Modellar topilmadi: " + ", ".join(still))
