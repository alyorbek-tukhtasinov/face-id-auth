"""ArcFace standartidagi 112x112 yuz tekislash (o'xshashlik transformatsiyasi)."""

from __future__ import annotations

import cv2
import numpy as np

ARCFACE_DST = np.array(
    [[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366], [41.5493, 92.3655], [70.7299, 92.2041]],
    dtype=np.float32,
)


def umeyama(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Masshtab, burilish va siljishni topadi (Umeyama, 1991). 2x3 matritsa qaytaradi."""
    src = src.astype(np.float64)
    dst = dst.astype(np.float64)
    n = src.shape[0]
    mu_s, mu_d = src.mean(0), dst.mean(0)
    sc, dc = src - mu_s, dst - mu_d
    cov = dc.T @ sc / n
    u, s, vt = np.linalg.svd(cov)
    d = np.ones(2)
    if np.linalg.det(cov) < 0:
        d[-1] = -1
    r = u @ np.diag(d) @ vt
    var_s = (sc**2).sum() / n
    scale = (s * d).sum() / var_s if var_s > 0 else 1.0
    t = mu_d - scale * r @ mu_s
    m = np.zeros((2, 3))
    m[:, :2] = scale * r
    m[:, 2] = t
    return m


def align_face(img_bgr: np.ndarray, kps: np.ndarray, size: int = 112) -> np.ndarray:
    dst = ARCFACE_DST * (size / 112.0)
    m = umeyama(kps, dst)
    return cv2.warpAffine(img_bgr, m, (size, size), flags=cv2.INTER_LINEAR, borderValue=0.0)
