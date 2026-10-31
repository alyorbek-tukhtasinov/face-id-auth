"""SCRFD-10G yuz detektori (5 ta tayanch nuqta bilan)."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .onnx import create_session
from .types import Face

_STRIDES = (8, 16, 32)
_NUM_ANCHORS = 2


def nms(dets: np.ndarray, thresh: float) -> list[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 1) * np.maximum(0.0, yy2 - yy1 + 1)
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


class FaceDetector:
    def __init__(self, model_path: Path | str, input_size: int = 640, score_thresh: float = 0.5,
                 nms_thresh: float = 0.4) -> None:
        self.session = create_session(model_path)
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.score_thresh = score_thresh
        self.nms_thresh = nms_thresh
        self._centers: dict[tuple[int, int, int], np.ndarray] = {}

    def _anchor_centers(self, h: int, w: int, stride: int) -> np.ndarray:
        key = (h, w, stride)
        if key not in self._centers:
            c = np.stack(np.mgrid[:h, :w][::-1], axis=-1).astype(np.float32)
            c = (c * stride).reshape(-1, 2)
            c = np.stack([c] * _NUM_ANCHORS, axis=1).reshape(-1, 2)
            self._centers[key] = c
        return self._centers[key]

    def detect(self, img_bgr: np.ndarray, max_faces: int = 0) -> list[Face]:
        size = self.input_size
        h, w = img_bgr.shape[:2]
        if h / w > 1.0:
            new_h, new_w = size, max(1, int(size * w / h))
        else:
            new_w, new_h = size, max(1, int(size * h / w))
        scale = new_h / h
        canvas = np.zeros((size, size, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = cv2.resize(img_bgr, (new_w, new_h))
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128.0, (size, size), (127.5, 127.5, 127.5), swapRB=True)
        outs = self.session.run(None, {self.input_name: blob})

        all_scores, all_boxes, all_kps = [], [], []
        for i, stride in enumerate(_STRIDES):
            scores = outs[i].reshape(-1)
            boxes = outs[i + 3].reshape(-1, 4) * stride
            kps = outs[i + 6].reshape(-1, 10) * stride
            centers = self._anchor_centers(size // stride, size // stride, stride)
            pos = np.where(scores >= self.score_thresh)[0]
            if pos.size == 0:
                continue
            c = centers[pos]
            b = boxes[pos]
            all_boxes.append(np.stack([c[:, 0] - b[:, 0], c[:, 1] - b[:, 1],
                                       c[:, 0] + b[:, 2], c[:, 1] + b[:, 3]], axis=-1))
            k = kps[pos].reshape(-1, 5, 2) + c[:, None, :]
            all_kps.append(k)
            all_scores.append(scores[pos])

        if not all_scores:
            return []
        scores = np.concatenate(all_scores)
        boxes = np.concatenate(all_boxes) / scale
        kps = np.concatenate(all_kps) / scale
        dets = np.hstack([boxes, scores[:, None]]).astype(np.float32)
        keep = nms(dets, self.nms_thresh)
        faces = [Face(bbox=boxes[i].astype(np.float32), kps=kps[i].astype(np.float32), score=float(scores[i]))
                 for i in keep]
        faces.sort(key=lambda f: f.area, reverse=True)
        if max_faces > 0:
            faces = faces[:max_faces]
        return faces
