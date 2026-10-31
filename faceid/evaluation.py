"""Biometrik ko'rsatkichlarni o'lchash (ISO/IEC 19795-1, ISO/IEC 30107-3).

* Tanib olish: FMR (False Match Rate), FNMR (False Non-Match Rate), EER va
  berilgan FMR uchun chegara qiymati. LFW ``pairs.txt`` formati yoki
  "har bir shaxs — alohida papka" tuzilmasi qo'llab-quvvatlanadi.
* PAD: APCER (hujumni haqiqiy deb qabul qilish) va BPCER (haqiqiyni rad etish).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class VerificationReport:
    genuine: int
    impostor: int
    eer: float
    eer_threshold: float
    at_fmr: dict[float, tuple[float, float]]  # fmr -> (threshold, fnmr)
    fnmr_at_current: float
    fmr_at_current: float
    current_threshold: float

    def text(self) -> str:
        lines = [
            f"Juftliklar: {self.genuine} genuine, {self.impostor} impostor",
            f"EER: {self.eer * 100:.3f}% (chegara {self.eer_threshold:.3f})",
        ]
        for fmr, (thr, fnmr) in sorted(self.at_fmr.items(), reverse=True):
            lines.append(f"FMR={fmr:g}: chegara {thr:.3f}, FNMR {fnmr * 100:.3f}%")
        lines.append(f"Joriy chegara {self.current_threshold:.3f}: FMR {self.fmr_at_current * 100:.4f}%, "
                     f"FNMR {self.fnmr_at_current * 100:.3f}%")
        return "\n".join(lines)


def verification_metrics(genuine: np.ndarray, impostor: np.ndarray, current: float,
                         fmr_targets: tuple[float, ...] = (1e-2, 1e-3, 1e-4)) -> VerificationReport:
    genuine = np.sort(np.asarray(genuine, dtype=np.float64))
    impostor = np.sort(np.asarray(impostor, dtype=np.float64))
    thr = np.unique(np.concatenate([genuine, impostor]))
    fmr = 1.0 - np.searchsorted(impostor, thr, side="left") / max(len(impostor), 1)
    fnmr = np.searchsorted(genuine, thr, side="left") / max(len(genuine), 1)
    i = int(np.argmin(np.abs(fmr - fnmr)))
    at = {}
    for target in fmr_targets:
        ok = np.where(fmr <= target)[0]
        if ok.size and len(impostor) >= 1 / target / 10:
            j = int(ok[0])
            at[target] = (float(thr[j]), float(fnmr[j]))
    fmr_c = float((impostor >= current).mean()) if len(impostor) else 0.0
    fnmr_c = float((genuine < current).mean()) if len(genuine) else 0.0
    return VerificationReport(len(genuine), len(impostor), float((fmr[i] + fnmr[i]) / 2), float(thr[i]), at,
                              fnmr_c, fmr_c, current)


def pad_metrics(real_scores: np.ndarray, attack_scores: np.ndarray, threshold: float) -> dict[str, float]:
    real = np.asarray(real_scores)
    att = np.asarray(attack_scores)
    return {
        "APCER": float((att >= threshold).mean()) if att.size else float("nan"),
        "BPCER": float((real < threshold).mean()) if real.size else float("nan"),
        "threshold": threshold,
        "n_real": int(real.size),
        "n_attack": int(att.size),
    }


def _embed_file(engine, path: Path) -> np.ndarray | None:
    img = cv2.imread(str(path))
    if img is None:
        return None
    faces = engine.analyze_still(img, max_faces=1)
    return faces[0].embedding if faces else None


def load_lfw_pairs(pairs_file: Path, root: Path) -> list[tuple[Path, Path, bool]]:
    out = []
    lines = pairs_file.read_text().strip().splitlines()
    for ln in lines[1:]:
        p = ln.split()
        if len(p) == 3:
            out.append((root / p[0] / f"{p[0]}_{int(p[1]):04d}.jpg", root / p[0] / f"{p[0]}_{int(p[2]):04d}.jpg", True))
        elif len(p) == 4:
            out.append((root / p[0] / f"{p[0]}_{int(p[1]):04d}.jpg", root / p[2] / f"{p[2]}_{int(p[3]):04d}.jpg", False))
    return out


def folder_pairs(root: Path, max_impostor: int = 20000, seed: int = 0) -> list[tuple[Path, Path, bool]]:
    ids = {d.name: sorted(f for f in d.iterdir() if f.suffix.lower() in IMG_EXT) for d in root.iterdir() if d.is_dir()}
    ids = {k: v for k, v in ids.items() if v}
    pairs = [(a, b, True) for files in ids.values() for a, b in itertools.combinations(files, 2)]
    rng = np.random.default_rng(seed)
    names = list(ids)
    seen = set()
    for _ in range(max_impostor * 3):
        if len(seen) >= max_impostor or len(names) < 2:
            break
        a, b = rng.choice(len(names), 2, replace=False)
        fa = ids[names[a]][rng.integers(len(ids[names[a]]))]
        fb = ids[names[b]][rng.integers(len(ids[names[b]]))]
        key = (min(fa, fb), max(fa, fb))
        if key not in seen:
            seen.add(key)
            pairs.append((fa, fb, False))
    return pairs


def evaluate_pairs(engine, pairs: list[tuple[Path, Path, bool]], current: float, progress=None) -> VerificationReport:
    cache: dict[Path, np.ndarray | None] = {}
    gen, imp = [], []
    for k, (a, b, same) in enumerate(pairs):
        for p in (a, b):
            if p not in cache:
                cache[p] = _embed_file(engine, p)
        ea, eb = cache[a], cache[b]
        if ea is None or eb is None:
            continue
        (gen if same else imp).append(float(np.dot(ea, eb)))
        if progress and k % 100 == 0:
            progress(k, len(pairs))
    return verification_metrics(np.array(gen), np.array(imp), current)


def evaluate_pad_dirs(engine, real_dir: Path, attack_dir: Path, threshold: float) -> dict[str, float]:
    def scores(d: Path) -> list[float]:
        out = []
        for f in sorted(d.rglob("*")):
            if f.suffix.lower() not in IMG_EXT:
                continue
            img = cv2.imread(str(f))
            if img is None:
                continue
            faces = engine.still_detector.detect(img, max_faces=1)
            if faces:
                out.append(engine.pad.score(img, faces[0].bbox))
        return out

    return pad_metrics(np.array(scores(real_dir)), np.array(scores(attack_dir)), threshold)
