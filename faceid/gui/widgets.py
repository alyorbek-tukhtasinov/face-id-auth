"""Kamera ko'rinishi: oval ramka, progress halqasi, yo'nalish ko'rsatkichlari."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from ..liveness.challenge import Action
from ..session import FrameReport

ACCENT = QColor("#4F8CFF")
OK = QColor("#2ECC71")
BAD = QColor("#FF5C5C")
IDLE = QColor(255, 255, 255, 200)

ICONS = {
    Action.BLINK: "◡ ◡",
    Action.SMILE: "☺",
    Action.OPEN_MOUTH: "○",
}


class VideoView(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(480, 360)
        self.image: QImage | None = None
        self.report: FrameReport | None = None
        self.mirror = True
        self.selfie_view = True  # foydalanuvchi o'zini ko'zgudagidek ko'radimi
        self.final: bool | None = None

    def set_frame(self, img: QImage, rep: FrameReport | None) -> None:
        self.image = img.mirrored(True, False) if self.mirror else img
        self.report = rep
        self.update()

    def clear(self) -> None:
        self.image = None
        self.report = None
        self.final = None
        self.update()

    def _target(self) -> QRectF:
        if self.image is None:
            return QRectF(self.rect())
        iw, ih = self.image.width(), self.image.height()
        s = min(self.width() / iw, self.height() / ih)
        w, h = iw * s, ih * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def paintEvent(self, _ev) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#0B0F17"))
        tgt = self._target()
        if self.image is not None:
            p.drawImage(tgt, self.image)

        # Oval ramka (rasm markazida, balandlikning ~70%)
        oh = tgt.height() * 0.72
        ow = oh * 0.75
        oval = QRectF(tgt.center().x() - ow / 2, tgt.center().y() - oh / 2, ow, oh)
        shade = QPainterPath()
        shade.addRect(tgt)
        hole = QPainterPath()
        hole.addEllipse(oval)
        p.fillPath(shade.subtracted(hole), QColor(8, 12, 20, 150))

        rep = self.report
        color = IDLE
        if self.final is True:
            color = OK
        elif self.final is False:
            color = BAD
        elif rep is not None and rep.face_ok:
            color = OK
        p.setPen(QPen(color, 4))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(oval)

        # Progress halqasi
        if rep is not None and rep.progress > 0:
            ring = oval.adjusted(-10, -10, 10, 10)
            pen = QPen(ACCENT if self.final is None else color, 7)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.drawArc(ring, 90 * 16, -int(360 * 16 * min(rep.progress, 1.0)))

        # Yo'nalish ko'rsatkichi yoki mimika belgisi
        if rep is not None and rep.action is not None and self.final is None:
            if rep.action in (Action.TURN_LEFT, Action.TURN_RIGHT):
                left = (rep.action is Action.TURN_LEFT) == self.selfie_view
                self._arrow(p, oval, left)
            else:
                p.setPen(QPen(QColor("#FFFFFF")))
                p.setFont(QFont("Segoe UI", int(oval.height() * 0.08), QFont.Weight.Bold))
                p.drawText(QRectF(oval.left(), oval.bottom() + 6, oval.width(), oval.height() * 0.14),
                           Qt.AlignmentFlag.AlignCenter, ICONS.get(rep.action, ""))
        p.end()

    def _arrow(self, p: QPainter, oval: QRectF, left: bool) -> None:
        cy = oval.center().y()
        size = oval.width() * 0.18
        x = oval.left() - size * 0.6 if left else oval.right() + size * 0.6
        d = -1 if left else 1
        pts = [QPointF(x + d * size * 0.6, cy), QPointF(x - d * size * 0.3, cy - size * 0.5),
               QPointF(x - d * size * 0.3, cy + size * 0.5)]
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ACCENT)
        p.drawPolygon(QPolygonF(pts))


class StepDots(QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.n = 0
        self.i = 0
        self.setFixedHeight(18)

    def set(self, i: int, n: int) -> None:
        self.i, self.n = i, n
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802
        if self.n <= 0:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = 6
        gap = 14
        total = self.n * (2 * r) + (self.n - 1) * gap
        x0 = (self.width() - total) / 2
        for k in range(self.n):
            c = OK if k < self.i - 1 else (ACCENT if k == self.i - 1 else QColor("#3A4356"))
            p.setBrush(c)
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(x0 + r + k * (2 * r + gap), self.height() / 2), r, r)
        p.end()


def meter_text(value: float | None) -> str:
    if value is None or math.isnan(value):
        return "—"
    return f"{value:.0f}"
