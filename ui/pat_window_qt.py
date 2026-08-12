"""
PAT OS
ui/pat_window_qt.py

Standalone PySide6 visual prototype for PAT.

Purpose
-------
A modern, frameless, animated HUD that keeps PAT's backend untouched.
This prototype uses Qt Widgets + QPainter for:
- translucent glass-style panels
- layered shadows and highlights
- a dimensional animated PAT core
- listening / thinking / speaking / confirmation states
- live-style waveform animation
- ActiveTarget presentation
- system status tiles

It is intentionally NOT connected to main.py, the router, AudioManager,
or FORGE yet.
"""

from __future__ import annotations

import math
import random
import sys
import time
from dataclasses import dataclass

from PySide6.QtCore import (
    QPoint,
    QPointF,
    QRectF,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QConicalGradient,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# ============================================================
# THEME
# ============================================================

BG = QColor("#03070d")
BG_2 = QColor("#07131f")

PANEL = QColor(7, 18, 29, 230)
PANEL_2 = QColor(9, 25, 39, 220)

TEXT = QColor("#eaf7ff")
MUTED = QColor("#728da5")

CYAN = QColor("#24ddff")
BLUE = QColor("#4f86ff")
PURPLE = QColor("#9d65ff")
GREEN = QColor("#38ef9c")
AMBER = QColor("#ffc857")
RED = QColor("#ff6178")

BORDER = QColor("#19394f")
BORDER_BRIGHT = QColor("#2d7095")

FONT_UI = "Segoe UI"
FONT_MONO = "Consolas"


def qcolor(value: QColor, alpha: int | None = None) -> QColor:
    color = QColor(value)
    if alpha is not None:
        color.setAlpha(alpha)
    return color


def mix(
    a: QColor,
    b: QColor,
    amount: float,
) -> QColor:
    amount = max(0.0, min(1.0, amount))

    return QColor(
        int(a.red() + (b.red() - a.red()) * amount),
        int(a.green() + (b.green() - a.green()) * amount),
        int(a.blue() + (b.blue() - a.blue()) * amount),
        int(a.alpha() + (b.alpha() - a.alpha()) * amount),
    )


@dataclass(frozen=True)
class VisualState:
    label: str
    color: QColor
    speed: float


STATES = {
    "IDLE": VisualState(
        "IDLE",
        CYAN,
        0.026,
    ),
    "LISTENING": VisualState(
        "LISTENING",
        GREEN,
        0.065,
    ),
    "THINKING": VisualState(
        "THINKING",
        PURPLE,
        0.105,
    ),
    "SPEAKING": VisualState(
        "SPEAKING",
        BLUE,
        0.085,
    ),
    "WAITING": VisualState(
        "AWAITING CONFIRMATION",
        RED,
        0.045,
    ),
}


# ============================================================
# BASE GLASS PANEL
# ============================================================

class GlassPanel(QFrame):
    def __init__(
        self,
        title: str,
        accent: QColor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.title = title
        self.accent = QColor(accent)

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 12)
        shadow.setColor(QColor(0, 0, 0, 185))
        self.setGraphicsEffect(shadow)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        rect = QRectF(self.rect()).adjusted(
            1.5,
            1.5,
            -1.5,
            -1.5,
        )

        path = QPainterPath()
        path.addRoundedRect(
            rect,
            18,
            18,
        )

        gradient = QLinearGradient(
            rect.topLeft(),
            rect.bottomRight(),
        )
        gradient.setColorAt(
            0.0,
            QColor(13, 31, 47, 238),
        )
        gradient.setColorAt(
            0.48,
            QColor(7, 18, 29, 232),
        )
        gradient.setColorAt(
            1.0,
            QColor(4, 12, 20, 238),
        )

        painter.fillPath(
            path,
            gradient,
        )

        border = mix(
            BORDER,
            self.accent,
            0.36,
        )
        border.setAlpha(205)

        painter.setPen(
            QPen(
                border,
                1.5,
            )
        )
        painter.drawPath(path)

        # Inner bevel.
        inner = rect.adjusted(
            5,
            5,
            -5,
            -5,
        )

        inner_path = QPainterPath()
        inner_path.addRoundedRect(
            inner,
            14,
            14,
        )

        painter.setPen(
            QPen(
                QColor(
                    self.accent.red(),
                    self.accent.green(),
                    self.accent.blue(),
                    58,
                ),
                1.0,
            )
        )
        painter.drawPath(inner_path)

        # Top specular highlight.
        highlight = QLinearGradient(
            rect.left() + 24,
            rect.top(),
            rect.right() - 24,
            rect.top(),
        )
        highlight.setColorAt(
            0.0,
            QColor(
                self.accent.red(),
                self.accent.green(),
                self.accent.blue(),
                0,
            ),
        )
        highlight.setColorAt(
            0.50,
            QColor(210, 245, 255, 145),
        )
        highlight.setColorAt(
            1.0,
            QColor(
                self.accent.red(),
                self.accent.green(),
                self.accent.blue(),
                0,
            ),
        )

        painter.setPen(
            QPen(
                highlight,
                1.2,
            )
        )
        painter.drawLine(
            QPointF(
                rect.left() + 24,
                rect.top() + 4,
            ),
            QPointF(
                rect.right() - 24,
                rect.top() + 4,
            ),
        )

        # Accent side light.
        side_gradient = QLinearGradient(
            rect.left(),
            rect.top() + 45,
            rect.left(),
            rect.bottom() - 45,
        )
        side_gradient.setColorAt(
            0.0,
            qcolor(
                self.accent,
                0,
            ),
        )
        side_gradient.setColorAt(
            0.5,
            qcolor(
                self.accent,
                225,
            ),
        )
        side_gradient.setColorAt(
            1.0,
            qcolor(
                self.accent,
                0,
            ),
        )

        painter.setPen(
            QPen(
                side_gradient,
                3.0,
            )
        )
        painter.drawLine(
            QPointF(
                rect.left() + 3,
                rect.top() + 48,
            ),
            QPointF(
                rect.left() + 3,
                rect.bottom() - 48,
            ),
        )

        # Title.
        painter.setPen(self.accent)
        painter.setFont(
            QFont(
                FONT_MONO,
                10,
                QFont.Weight.Bold,
            )
        )
        painter.drawText(
            QRectF(
                rect.left() + 22,
                rect.top() + 15,
                rect.width() - 44,
                25,
            ),
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )

        painter.setPen(
            QPen(
                QColor(65, 104, 132, 110),
                1,
            )
        )
        painter.drawLine(
            QPointF(
                rect.left() + 20,
                rect.top() + 48,
            ),
            QPointF(
                rect.right() - 20,
                rect.top() + 48,
            ),
        )

        super().paintEvent(event)


# ============================================================
# WAVEFORM
# ============================================================

class WaveformWidget(QWidget):
    def __init__(
        self,
        accent: QColor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.accent = QColor(accent)
        self.phase = 0.0
        self.intensity = 0.18

        self.setMinimumHeight(70)

    def set_intensity(
        self,
        value: float,
    ) -> None:
        self.intensity = max(
            0.05,
            min(1.0, value),
        )

    def tick(
        self,
        speed: float,
    ) -> None:
        self.phase += speed
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        rect = QRectF(self.rect()).adjusted(
            4,
            4,
            -4,
            -4,
        )

        center_y = rect.center().y()

        painter.setPen(
            QPen(
                qcolor(
                    self.accent,
                    55,
                ),
                1,
            )
        )
        painter.drawLine(
            QPointF(
                rect.left(),
                center_y,
            ),
            QPointF(
                rect.right(),
                center_y,
            ),
        )

        path = QPainterPath()

        count = 74

        for index in range(count):
            t = index / max(
                count - 1,
                1,
            )

            x = (
                rect.left()
                + rect.width() * t
            )

            envelope = (
                math.sin(
                    math.pi * t
                )
                ** 0.65
            )

            wave = (
                math.sin(
                    self.phase * 5.1
                    + index * 0.46
                )
                + 0.35
                * math.sin(
                    self.phase * 8.7
                    + index * 1.12
                )
            )

            amplitude = (
                rect.height()
                * 0.28
                * self.intensity
                * envelope
            )

            y = center_y + wave * amplitude

            if index == 0:
                path.moveTo(
                    x,
                    y,
                )
            else:
                path.lineTo(
                    x,
                    y,
                )

        glow_pen = QPen(
            qcolor(
                self.accent,
                65,
            ),
            6.0,
        )
        glow_pen.setCapStyle(
            Qt.PenCapStyle.RoundCap
        )

        painter.setPen(glow_pen)
        painter.drawPath(path)

        main_pen = QPen(
            self.accent,
            1.8,
        )
        main_pen.setCapStyle(
            Qt.PenCapStyle.RoundCap
        )

        painter.setPen(main_pen)
        painter.drawPath(path)

        super().paintEvent(event)


# ============================================================
# PAT CORE
# ============================================================

class PatCoreWidget(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.state = "IDLE"
        self.phase = 0.0
        self.secondary_phase = 0.0

        self.speech_levels = [
            0.2
            for _ in range(44)
        ]
        self.speech_targets = [
            0.2
            for _ in range(44)
        ]

        self.last_speech_update = 0.0

        self.think_angles = [
            random.random()
            * math.tau
            for _ in range(5)
        ]

        self.setMinimumSize(
            430,
            430,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

    def set_state(
        self,
        state: str,
    ) -> None:
        if state in STATES:
            self.state = state
            self.update()

    def tick(self) -> None:
        visual = STATES[self.state]

        self.phase += visual.speed
        self.secondary_phase = (
            self.secondary_phase
            + visual.speed * 0.27
        ) % 1.0

        self.update()

    def _draw_glow_circle(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        color: QColor,
        alpha: int,
        width: float,
    ) -> None:
        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )
        painter.setPen(
            QPen(
                qcolor(
                    color,
                    alpha,
                ),
                width,
            )
        )
        painter.drawEllipse(
            center,
            radius,
            radius,
        )

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing,
            True,
        )

        rect = QRectF(self.rect())
        center = rect.center()

        visual = STATES[self.state]
        accent = visual.color

        pulse = (
            math.sin(
                self.phase * 2.2
            )
            + 1
        ) / 2

        base = min(
            rect.width(),
            rect.height(),
        )

        orb_radius = (
            base * 0.19
            + pulse * 4
        )

        ring_radius = base * 0.315

        # ====================================================
        # PEDESTAL / 3D BASE
        # ====================================================

        pedestal_center = QPointF(
            center.x(),
            center.y() + base * 0.285,
        )

        shadow_rect = QRectF(
            pedestal_center.x() - base * 0.34,
            pedestal_center.y() - base * 0.055,
            base * 0.68,
            base * 0.15,
        )

        shadow_gradient = QRadialGradient(
            pedestal_center,
            base * 0.34,
        )
        shadow_gradient.setColorAt(
            0.0,
            QColor(0, 0, 0, 210),
        )
        shadow_gradient.setColorAt(
            1.0,
            QColor(0, 0, 0, 0),
        )

        painter.setBrush(shadow_gradient)
        painter.setPen(
            Qt.PenStyle.NoPen
        )
        painter.drawEllipse(shadow_rect)

        # Stacked elliptical platform rings.
        for index in range(7):
            shrink = index * base * 0.018
            y = pedestal_center.y() + index * 4

            platform_rect = QRectF(
                center.x()
                - base * 0.30
                + shrink,
                y - base * 0.07,
                base * 0.60
                - shrink * 2,
                base * 0.14,
            )

            platform_fill = QLinearGradient(
                platform_rect.topLeft(),
                platform_rect.bottomLeft(),
            )
            platform_fill.setColorAt(
                0.0,
                QColor(19, 49, 70, 230),
            )
            platform_fill.setColorAt(
                0.55,
                QColor(6, 20, 32, 245),
            )
            platform_fill.setColorAt(
                1.0,
                QColor(2, 8, 14, 255),
            )

            painter.setBrush(
                platform_fill
            )

            platform_pen = QPen(
                qcolor(
                    mix(
                        BORDER,
                        accent,
                        min(
                            0.15
                            + index * 0.08,
                            0.75,
                        ),
                    ),
                    180,
                ),
                1.5,
            )
            painter.setPen(platform_pen)
            painter.drawEllipse(
                platform_rect
            )

        top_platform = QRectF(
            center.x() - base * 0.255,
            pedestal_center.y()
            - base * 0.078,
            base * 0.51,
            base * 0.125,
        )

        top_gradient = QRadialGradient(
            top_platform.center(),
            top_platform.width() / 2,
        )
        top_gradient.setColorAt(
            0.0,
            qcolor(
                accent,
                82,
            ),
        )
        top_gradient.setColorAt(
            0.38,
            QColor(6, 28, 42, 245),
        )
        top_gradient.setColorAt(
            1.0,
            QColor(2, 11, 19, 250),
        )

        painter.setBrush(top_gradient)
        painter.setPen(
            QPen(
                qcolor(
                    accent,
                    175,
                ),
                2,
            )
        )
        painter.drawEllipse(
            top_platform
        )

        # Holographic vertical light.
        beam = QLinearGradient(
            center.x(),
            center.y() - orb_radius,
            center.x(),
            pedestal_center.y(),
        )

        beam.setColorAt(
            0.0,
            qcolor(
                accent,
                0,
            ),
        )
        beam.setColorAt(
            0.45,
            qcolor(
                accent,
                48,
            ),
        )
        beam.setColorAt(
            1.0,
            qcolor(
                accent,
                140,
            ),
        )

        painter.setPen(
            QPen(
                beam,
                2,
            )
        )

        for offset in (
            -45,
            -28,
            -12,
            0,
            12,
            28,
            45,
        ):
            painter.drawLine(
                QPointF(
                    center.x()
                    + offset * 0.55,
                    center.y()
                    + orb_radius * 0.70,
                ),
                QPointF(
                    center.x()
                    + offset,
                    pedestal_center.y()
                    - base * 0.03,
                ),
            )

        # ====================================================
        # OUTER HALO
        # ====================================================

        for offset, alpha in (
            (27, 18),
            (20, 24),
            (13, 32),
            (7, 45),
        ):
            self._draw_glow_circle(
                painter,
                center,
                ring_radius + offset,
                accent,
                alpha,
                5,
            )

        # Conical segmented ring.
        conical = QConicalGradient(
            center,
            -self.phase * 42,
        )
        conical.setColorAt(
            0.0,
            qcolor(
                accent,
                245,
            ),
        )
        conical.setColorAt(
            0.13,
            qcolor(
                accent,
                25,
            ),
        )
        conical.setColorAt(
            0.28,
            qcolor(
                BLUE,
                210,
            ),
        )
        conical.setColorAt(
            0.50,
            qcolor(
                accent,
                20,
            ),
        )
        conical.setColorAt(
            0.73,
            qcolor(
                PURPLE,
                210,
            ),
        )
        conical.setColorAt(
            1.0,
            qcolor(
                accent,
                245,
            ),
        )

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )
        painter.setPen(
            QPen(
                conical,
                4.0,
            )
        )
        painter.drawEllipse(
            center,
            ring_radius,
            ring_radius,
        )

        # Multiple rotating arcs.
        for radius_factor, speed, span, pen_width in (
            (1.00, 52, 82, 3.0),
            (0.91, -78, 55, 2.0),
            (0.82, 112, 38, 2.0),
        ):
            radius = (
                ring_radius
                * radius_factor
            )

            arc_rect = QRectF(
                center.x() - radius,
                center.y() - radius,
                radius * 2,
                radius * 2,
            )

            painter.setPen(
                QPen(
                    accent,
                    pen_width,
                )
            )

            start_deg = (
                self.phase * speed
            ) % 360

            painter.drawArc(
                arc_rect,
                int(start_deg * 16),
                int(span * 16),
            )

        # ====================================================
        # ORB
        # ====================================================

        # Glow around orb.
        orb_glow = QRadialGradient(
            center,
            orb_radius * 1.55,
        )
        orb_glow.setColorAt(
            0.0,
            qcolor(
                accent,
                130,
            ),
        )
        orb_glow.setColorAt(
            0.48,
            qcolor(
                accent,
                45,
            ),
        )
        orb_glow.setColorAt(
            1.0,
            qcolor(
                accent,
                0,
            ),
        )

        painter.setBrush(orb_glow)
        painter.setPen(
            Qt.PenStyle.NoPen
        )
        painter.drawEllipse(
            center,
            orb_radius * 1.55,
            orb_radius * 1.55,
        )

        orb_fill = QRadialGradient(
            QPointF(
                center.x() - orb_radius * 0.35,
                center.y() - orb_radius * 0.43,
            ),
            orb_radius * 1.35,
            QPointF(
                center.x() - orb_radius * 0.35,
                center.y() - orb_radius * 0.43,
            ),
        )

        orb_fill.setColorAt(
            0.0,
            QColor(75, 133, 166, 230),
        )
        orb_fill.setColorAt(
            0.15,
            QColor(15, 56, 80, 248),
        )
        orb_fill.setColorAt(
            0.52,
            QColor(5, 24, 38, 255),
        )
        orb_fill.setColorAt(
            1.0,
            QColor(1, 8, 15, 255),
        )

        painter.setBrush(orb_fill)
        painter.setPen(
            QPen(
                qcolor(
                    accent,
                    235,
                ),
                3.0,
            )
        )
        painter.drawEllipse(
            center,
            orb_radius,
            orb_radius,
        )

        # Equator for 3D depth.
        equator_rect = QRectF(
            center.x() - orb_radius * 1.22,
            center.y() - orb_radius * 0.28,
            orb_radius * 2.44,
            orb_radius * 0.56,
        )

        painter.setBrush(
            Qt.BrushStyle.NoBrush
        )
        painter.setPen(
            QPen(
                qcolor(
                    accent,
                    110,
                ),
                1.4,
            )
        )
        painter.drawEllipse(
            equator_rect
        )

        # Latitude rings.
        for offset in (
            -0.45,
            -0.22,
            0.22,
            0.45,
        ):
            y = (
                center.y()
                + orb_radius * offset
            )

            half_width = (
                orb_radius
                * math.sqrt(
                    max(
                        1
                        - offset * offset,
                        0.05,
                    )
                )
            )

            lat_rect = QRectF(
                center.x()
                - half_width,
                y - 5,
                half_width * 2,
                10,
            )

            painter.setPen(
                QPen(
                    qcolor(
                        accent,
                        65,
                    ),
                    1,
                )
            )
            painter.drawEllipse(
                lat_rect
            )

        # Gloss highlight.
        gloss = QRadialGradient(
            QPointF(
                center.x() - orb_radius * 0.38,
                center.y() - orb_radius * 0.42,
            ),
            orb_radius * 0.66,
        )
        gloss.setColorAt(
            0.0,
            QColor(255, 255, 255, 95),
        )
        gloss.setColorAt(
            0.40,
            QColor(180, 230, 255, 28),
        )
        gloss.setColorAt(
            1.0,
            QColor(255, 255, 255, 0),
        )

        painter.setBrush(gloss)
        painter.setPen(
            Qt.PenStyle.NoPen
        )
        painter.drawEllipse(
            QPointF(
                center.x() - orb_radius * 0.20,
                center.y() - orb_radius * 0.22,
            ),
            orb_radius * 0.72,
            orb_radius * 0.72,
        )

        # PAT text.
        painter.setPen(TEXT)
        painter.setFont(
            QFont(
                FONT_UI,
                max(
                    20,
                    int(base * 0.058),
                ),
                QFont.Weight.Bold,
            )
        )
        painter.drawText(
            QRectF(
                center.x() - orb_radius,
                center.y() - 32,
                orb_radius * 2,
                48,
            ),
            Qt.AlignmentFlag.AlignCenter,
            "PAT",
        )

        painter.setPen(accent)
        painter.setFont(
            QFont(
                FONT_MONO,
                9,
                QFont.Weight.Bold,
            )
        )
        painter.drawText(
            QRectF(
                center.x() - orb_radius,
                center.y() + 20,
                orb_radius * 2,
                24,
            ),
            Qt.AlignmentFlag.AlignCenter,
            visual.label,
        )

        # ====================================================
        # STATE-SPECIFIC MOTION
        # ====================================================

        if self.state == "LISTENING":
            self._paint_listening(
                painter,
                center,
                ring_radius,
                accent,
            )

        elif self.state == "THINKING":
            self._paint_thinking(
                painter,
                center,
                ring_radius,
                accent,
            )

        elif self.state == "SPEAKING":
            self._paint_speaking(
                painter,
                center,
                ring_radius,
                accent,
            )

        elif self.state == "WAITING":
            self._paint_waiting(
                painter,
                center,
                ring_radius,
                accent,
            )

        else:
            self._paint_idle(
                painter,
                center,
                ring_radius,
                accent,
            )

        super().paintEvent(event)

    def _paint_idle(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        accent: QColor,
    ) -> None:
        breath = (
            math.sin(
                self.phase * 1.8
            )
            + 1
        ) / 2

        self._draw_glow_circle(
            painter,
            center,
            radius + 20 + breath * 6,
            accent,
            int(
                35 + breath * 45
            ),
            2,
        )

    def _paint_listening(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        accent: QColor,
    ) -> None:
        for offset in (
            0.0,
            0.33,
            0.66,
        ):
            cycle = (
                self.secondary_phase
                + offset
            ) % 1.0

            pulse_radius = (
                radius
                + 18
                + cycle * 70
            )

            alpha = int(
                130
                * (1.0 - cycle)
            )

            self._draw_glow_circle(
                painter,
                center,
                pulse_radius,
                accent,
                alpha,
                2.2,
            )

    def _paint_thinking(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        accent: QColor,
    ) -> None:
        for index, base_angle in enumerate(
            self.think_angles
        ):
            angle = (
                base_angle
                + self.phase
                * (
                    0.82
                    + index * 0.06
                )
            )

            orbit = (
                radius
                + 32
                + 9
                * math.sin(
                    self.phase * 1.8
                    + index
                )
            )

            x = (
                center.x()
                + math.cos(angle)
                * orbit
            )

            y = (
                center.y()
                + math.sin(angle)
                * orbit * 0.46
            )

            node = QPointF(
                x,
                y,
            )

            painter.setPen(
                QPen(
                    qcolor(
                        accent,
                        45,
                    ),
                    1,
                )
            )
            painter.drawLine(
                center,
                node,
            )

            node_radius = (
                4
                + 2
                * (
                    0.5
                    + 0.5
                    * math.sin(
                        self.phase * 3
                        + index
                    )
                )
            )

            glow = QRadialGradient(
                node,
                node_radius * 3,
            )
            glow.setColorAt(
                0.0,
                qcolor(
                    accent,
                    230,
                ),
            )
            glow.setColorAt(
                1.0,
                qcolor(
                    accent,
                    0,
                ),
            )

            painter.setBrush(glow)
            painter.setPen(
                Qt.PenStyle.NoPen
            )
            painter.drawEllipse(
                node,
                node_radius * 3,
                node_radius * 3,
            )

            painter.setBrush(accent)
            painter.drawEllipse(
                node,
                node_radius,
                node_radius,
            )

    def _paint_speaking(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        accent: QColor,
    ) -> None:
        now = time.monotonic()

        if (
            now
            - self.last_speech_update
            > 0.085
        ):
            self.last_speech_update = now

            self.speech_targets = [
                random.uniform(
                    0.06,
                    1.0,
                )
                for _ in self.speech_targets
            ]

        count = len(
            self.speech_levels
        )

        for index in range(count):
            current = (
                self.speech_levels[index]
            )
            target = (
                self.speech_targets[index]
            )

            level = (
                current
                + (target - current)
                * 0.27
            )

            self.speech_levels[index] = level

            angle = (
                math.tau
                * index
                / count
                + self.phase * 0.18
            )

            start_radius = (
                radius + 16
            )

            length = (
                7
                + level * 28
            )

            start = QPointF(
                center.x()
                + math.cos(angle)
                * start_radius,
                center.y()
                + math.sin(angle)
                * start_radius,
            )

            end = QPointF(
                center.x()
                + math.cos(angle)
                * (
                    start_radius
                    + length
                ),
                center.y()
                + math.sin(angle)
                * (
                    start_radius
                    + length
                ),
            )

            painter.setPen(
                QPen(
                    qcolor(
                        accent,
                        int(
                            110
                            + level * 145
                        ),
                    ),
                    2.6,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                )
            )
            painter.drawLine(
                start,
                end,
            )

    def _paint_waiting(
        self,
        painter: QPainter,
        center: QPointF,
        radius: float,
        accent: QColor,
    ) -> None:
        rect = QRectF(
            center.x()
            - radius
            - 18,
            center.y()
            - radius
            - 18,
            (
                radius
                + 18
            )
            * 2,
            (
                radius
                + 18
            )
            * 2,
        )

        painter.setPen(
            QPen(
                accent,
                3,
            )
        )

        for index in range(12):
            if index % 2:
                continue

            start = (
                index * 30
                + self.phase * 48
            )

            painter.drawArc(
                rect,
                int(start * 16),
                int(17 * 16),
            )


# ============================================================
# STATUS TILE
# ============================================================

class StatusTile(QFrame):
    def __init__(
        self,
        title: str,
        value: str,
        accent: QColor,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.accent = QColor(accent)

        self.setObjectName(
            "StatusTile"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            16,
            12,
            16,
            12,
        )
        layout.setSpacing(2)

        title_label = QLabel(title)
        title_label.setObjectName(
            "StatusTitle"
        )

        value_label = QLabel(value)
        value_label.setObjectName(
            "StatusValue"
        )

        value_label.setStyleSheet(
            f"color: {self.accent.name()};"
        )

        layout.addWidget(
            title_label
        )
        layout.addWidget(
            value_label
        )

        self.setStyleSheet(
            """
            QFrame#StatusTile {
                background: rgba(8, 21, 33, 210);
                border: 1px solid rgba(58, 103, 132, 125);
                border-radius: 13px;
            }

            QLabel#StatusTitle {
                color: #dceeff;
                font-family: Consolas;
                font-size: 10px;
                font-weight: 600;
            }

            QLabel#StatusValue {
                font-family: Consolas;
                font-size: 9px;
                font-weight: 700;
            }
            """
        )


# ============================================================
# TITLE BAR
# ============================================================

class TitleBar(QFrame):
    def __init__(
        self,
        window: "PATWindow",
    ) -> None:
        super().__init__(window)

        self.window_ref = window

        self.drag_start: QPoint | None = None
        self.window_start: QPoint | None = None

        self.setFixedHeight(58)
        self.setObjectName(
            "TitleBar"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            18,
            0,
            12,
            0,
        )
        layout.setSpacing(12)

        logo = QLabel("PAT")
        logo.setObjectName(
            "Logo"
        )

        subtitle = QLabel(
            "// PERSONAL AI TECHNICIAN"
        )
        subtitle.setObjectName(
            "Subtitle"
        )

        center = QLabel(
            "PAT VISUAL CORE"
        )
        center.setObjectName(
            "CenterTitle"
        )
        center.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        online = QLabel(
            "● SYSTEM ONLINE"
        )
        online.setObjectName(
            "Online"
        )

        minimize = QPushButton("—")
        maximize = QPushButton("□")
        close = QPushButton("×")

        for button in (
            minimize,
            maximize,
            close,
        ):
            button.setObjectName(
                "WindowButton"
            )
            button.setFixedSize(
                38,
                34,
            )
            button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

        close.setObjectName(
            "CloseButton"
        )

        minimize.clicked.connect(
            window.showMinimized
        )

        maximize.clicked.connect(
            window.toggle_maximize
        )

        close.clicked.connect(
            window.close
        )

        layout.addWidget(logo)
        layout.addWidget(subtitle)
        layout.addStretch(1)
        layout.addWidget(
            center,
            1,
        )
        layout.addStretch(1)
        layout.addWidget(online)
        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)

        self.setStyleSheet(
            """
            QFrame#TitleBar {
                background: rgba(5, 15, 25, 235);
                border: 1px solid rgba(50, 106, 142, 150);
                border-radius: 16px;
            }

            QLabel#Logo {
                color: #24ddff;
                font-family: "Segoe UI";
                font-size: 24px;
                font-weight: 800;
            }

            QLabel#Subtitle {
                color: #dceeff;
                font-family: Consolas;
                font-size: 10px;
            }

            QLabel#CenterTitle {
                color: #728da5;
                font-family: Consolas;
                font-size: 10px;
                font-weight: 700;
            }

            QLabel#Online {
                color: #38ef9c;
                font-family: Consolas;
                font-size: 9px;
                font-weight: 700;
            }

            QPushButton#WindowButton,
            QPushButton#CloseButton {
                color: #7893a9;
                background: transparent;
                border: none;
                border-radius: 8px;
                font-size: 17px;
            }

            QPushButton#WindowButton:hover {
                color: #eaf7ff;
                background: rgba(47, 102, 137, 80);
            }

            QPushButton#CloseButton:hover {
                color: white;
                background: rgba(255, 97, 120, 175);
            }
            """
        )

    def mousePressEvent(
        self,
        event,
    ) -> None:
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.drag_start = (
                event.globalPosition()
                .toPoint()
            )
            self.window_start = (
                self.window_ref.pos()
            )

        super().mousePressEvent(
            event
        )

    def mouseMoveEvent(
        self,
        event,
    ) -> None:
        if (
            self.drag_start is not None
            and self.window_start
            is not None
            and event.buttons()
            & Qt.MouseButton.LeftButton
            and not self.window_ref.isMaximized()
        ):
            delta = (
                event.globalPosition()
                .toPoint()
                - self.drag_start
            )

            self.window_ref.move(
                self.window_start
                + delta
            )

        super().mouseMoveEvent(
            event
        )

    def mouseReleaseEvent(
        self,
        event,
    ) -> None:
        self.drag_start = None
        self.window_start = None

        super().mouseReleaseEvent(
            event
        )

    def mouseDoubleClickEvent(
        self,
        event,
    ) -> None:
        if (
            event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.window_ref.toggle_maximize()

        super().mouseDoubleClickEvent(
            event
        )


# ============================================================
# MAIN WINDOW
# ============================================================

class PATWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()

        self.setWindowTitle(
            "PAT // Personal AI Technician"
        )

        self.resize(
            1280,
            780,
        )

        self.setMinimumSize(
            1080,
            680,
        )

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Window
        )

        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )

        self.current_state = "IDLE"

        self._build_ui()
        self._apply_styles()

        self.timer = QTimer(self)
        self.timer.timeout.connect(
            self._tick
        )
        self.timer.start(16)

    # ========================================================
    # BUILD
    # ========================================================

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName(
            "Root"
        )

        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        outer.setSpacing(10)

        self.title_bar = TitleBar(
            self
        )
        outer.addWidget(
            self.title_bar
        )

        body = QHBoxLayout()
        body.setSpacing(12)

        # LEFT
        left_column = QVBoxLayout()
        left_column.setSpacing(12)

        self.input_panel = GlassPanel(
            "YOU // INPUT",
            CYAN,
        )

        input_layout = QVBoxLayout(
            self.input_panel
        )
        input_layout.setContentsMargins(
            22,
            62,
            22,
            20,
        )
        input_layout.setSpacing(12)

        self.user_text_label = QLabel(
            "Open YouTube."
        )
        self.user_text_label.setObjectName(
            "BigText"
        )
        self.user_text_label.setWordWrap(
            True
        )

        self.input_wave = WaveformWidget(
            CYAN
        )

        input_meta = QHBoxLayout()

        voice_label = QLabel(
            "VOICE STATUS\nREADY"
        )
        voice_label.setObjectName(
            "MetaText"
        )

        language_label = QLabel(
            "LANGUAGE\nEN-US"
        )
        language_label.setObjectName(
            "MetaText"
        )
        language_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        input_meta.addWidget(
            voice_label
        )
        input_meta.addStretch()
        input_meta.addWidget(
            language_label
        )

        input_layout.addWidget(
            self.user_text_label
        )
        input_layout.addWidget(
            self.input_wave,
            1,
        )
        input_layout.addLayout(
            input_meta
        )

        self.system_panel = GlassPanel(
            "SYSTEM STATUS",
            GREEN,
        )
        self.system_panel.setMaximumHeight(
            180
        )

        sys_layout = QVBoxLayout(
            self.system_panel
        )
        sys_layout.setContentsMargins(
            22,
            62,
            22,
            20,
        )

        sys_state = QLabel(
            "System Online"
        )
        sys_state.setObjectName(
            "SystemOnline"
        )

        sys_sub = QLabel(
            "All systems operational"
        )
        sys_sub.setObjectName(
            "SmallMuted"
        )

        sys_layout.addWidget(
            sys_state
        )
        sys_layout.addWidget(
            sys_sub
        )
        sys_layout.addStretch()

        left_column.addWidget(
            self.input_panel,
            1,
        )
        left_column.addWidget(
            self.system_panel,
        )

        # CENTER
        center_column = QVBoxLayout()
        center_column.setSpacing(8)

        self.core = PatCoreWidget()

        self.active_target_panel = QFrame()
        self.active_target_panel.setObjectName(
            "ActiveTarget"
        )
        self.active_target_panel.setFixedHeight(
            72
        )

        target_layout = QHBoxLayout(
            self.active_target_panel
        )
        target_layout.setContentsMargins(
            22,
            8,
            22,
            8,
        )

        target_title = QLabel(
            "ACTIVE TARGET"
        )
        target_title.setObjectName(
            "TargetTitle"
        )

        self.target_kind_label = QLabel(
            "WEBSITE"
        )
        self.target_kind_label.setObjectName(
            "TargetKind"
        )

        target_slash = QLabel("//")
        target_slash.setObjectName(
            "TargetSlash"
        )

        self.target_value_label = QLabel(
            "youtube"
        )
        self.target_value_label.setObjectName(
            "TargetValue"
        )

        target_group = QVBoxLayout()
        target_group.setSpacing(1)
        target_group.addWidget(
            target_title
        )

        target_line = QHBoxLayout()
        target_line.setSpacing(10)
        target_line.addWidget(
            self.target_kind_label
        )
        target_line.addWidget(
            target_slash
        )
        target_line.addWidget(
            self.target_value_label
        )
        target_line.addStretch()

        target_group.addLayout(
            target_line
        )

        target_layout.addLayout(
            target_group,
            1,
        )

        chevrons = QLabel("» » »")
        chevrons.setObjectName(
            "Chevrons"
        )
        target_layout.addWidget(
            chevrons
        )

        center_column.addWidget(
            self.core,
            1,
        )
        center_column.addWidget(
            self.active_target_panel
        )

        # RIGHT
        right_column = QVBoxLayout()
        right_column.setSpacing(12)

        self.response_panel = GlassPanel(
            "PAT // RESPONSE",
            PURPLE,
        )

        response_layout = QVBoxLayout(
            self.response_panel
        )
        response_layout.setContentsMargins(
            22,
            62,
            22,
            20,
        )
        response_layout.setSpacing(12)

        self.pat_text_label = QLabel(
            "Opening YouTube."
        )
        self.pat_text_label.setObjectName(
            "BigText"
        )
        self.pat_text_label.setWordWrap(
            True
        )

        self.response_wave = WaveformWidget(
            PURPLE
        )

        self.state_label = QLabel(
            "IDLE"
        )
        self.state_label.setObjectName(
            "StateLabel"
        )

        response_layout.addWidget(
            self.pat_text_label
        )
        response_layout.addWidget(
            self.response_wave,
            1,
        )
        response_layout.addWidget(
            self.state_label
        )

        self.info_panel = GlassPanel(
            "PAT CORE",
            BLUE,
        )
        self.info_panel.setMaximumHeight(
            180
        )

        info_layout = QVBoxLayout(
            self.info_panel
        )
        info_layout.setContentsMargins(
            22,
            62,
            22,
            18,
        )
        info_layout.setSpacing(6)

        hint = QLabel(
            "1  IDLE\n"
            "2  LISTENING\n"
            "3  THINKING\n"
            "4  SPEAKING\n"
            "5  CONFIRMATION"
        )
        hint.setObjectName(
            "SmallMuted"
        )

        info_layout.addWidget(
            hint
        )

        right_column.addWidget(
            self.response_panel,
            1,
        )
        right_column.addWidget(
            self.info_panel,
        )

        body.addLayout(
            left_column,
            27,
        )
        body.addLayout(
            center_column,
            46,
        )
        body.addLayout(
            right_column,
            27,
        )

        outer.addLayout(
            body,
            1,
        )

        # BOTTOM STATUS ROW
        bottom = QGridLayout()
        bottom.setHorizontalSpacing(
            8
        )

        status_items = (
            (
                "MIC",
                "ACTIVE",
                GREEN,
            ),
            (
                "AI ENGINE",
                "READY",
                CYAN,
            ),
            (
                "MEMORY",
                "ONLINE",
                BLUE,
            ),
            (
                "INTERNET",
                "CONNECTED",
                CYAN,
            ),
            (
                "AUDIO",
                "ON",
                PURPLE,
            ),
            (
                "SAFETY",
                "SECURE",
                GREEN,
            ),
        )

        for column, (
            title,
            value,
            accent,
        ) in enumerate(
            status_items
        ):
            bottom.addWidget(
                StatusTile(
                    title,
                    value,
                    accent,
                ),
                0,
                column,
            )

        outer.addLayout(
            bottom
        )

    # ========================================================
    # STYLE
    # ========================================================

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#Root {
                background:
                    qlineargradient(
                        x1: 0, y1: 0,
                        x2: 0, y2: 1,
                        stop: 0 #02060c,
                        stop: 0.60 #050e18,
                        stop: 1 #071522
                    );
                border: 1px solid rgba(46, 108, 145, 150);
                border-radius: 20px;
            }

            QLabel#BigText {
                color: #eaf7ff;
                font-family: "Segoe UI";
                font-size: 18px;
                font-weight: 500;
            }

            QLabel#MetaText {
                color: #728da5;
                font-family: Consolas;
                font-size: 9px;
            }

            QLabel#SmallMuted {
                color: #728da5;
                font-family: Consolas;
                font-size: 9px;
            }

            QLabel#SystemOnline {
                color: #38ef9c;
                font-family: "Segoe UI";
                font-size: 17px;
                font-weight: 700;
            }

            QLabel#StateLabel {
                color: #24ddff;
                font-family: Consolas;
                font-size: 10px;
                font-weight: 700;
            }

            QFrame#ActiveTarget {
                background:
                    qlineargradient(
                        x1: 0, y1: 0,
                        x2: 1, y2: 1,
                        stop: 0 rgba(11, 34, 51, 235),
                        stop: 0.55 rgba(6, 20, 32, 240),
                        stop: 1 rgba(10, 27, 43, 230)
                    );
                border: 1px solid rgba(50, 121, 160, 180);
                border-radius: 16px;
            }

            QLabel#TargetTitle {
                color: #728da5;
                font-family: Consolas;
                font-size: 8px;
                font-weight: 700;
            }

            QLabel#TargetKind {
                color: #24ddff;
                font-family: Consolas;
                font-size: 13px;
                font-weight: 800;
            }

            QLabel#TargetSlash {
                color: #728da5;
                font-family: Consolas;
                font-size: 13px;
            }

            QLabel#TargetValue {
                color: #eaf7ff;
                font-family: Consolas;
                font-size: 13px;
            }

            QLabel#Chevrons {
                color: #24ddff;
                font-family: Consolas;
                font-size: 20px;
                font-weight: 800;
            }
            """
        )

        target_shadow = QGraphicsDropShadowEffect(
            self.active_target_panel
        )
        target_shadow.setBlurRadius(
            30
        )
        target_shadow.setOffset(
            0,
            10,
        )
        target_shadow.setColor(
            QColor(0, 0, 0, 175)
        )
        self.active_target_panel.setGraphicsEffect(
            target_shadow
        )

    # ========================================================
    # PUBLIC UI API
    # ========================================================

    def set_state(
        self,
        state: str,
    ) -> None:
        state = state.upper()

        if state not in STATES:
            return

        self.current_state = state
        visual = STATES[state]

        self.core.set_state(
            state
        )

        self.state_label.setText(
            visual.label
        )

        self.state_label.setStyleSheet(
            f"color: {visual.color.name()};"
        )

        if state == "LISTENING":
            self.input_wave.set_intensity(
                0.90
            )
            self.response_wave.set_intensity(
                0.16
            )

        elif state == "THINKING":
            self.input_wave.set_intensity(
                0.20
            )
            self.response_wave.set_intensity(
                0.35
            )

        elif state == "SPEAKING":
            self.input_wave.set_intensity(
                0.12
            )
            self.response_wave.set_intensity(
                1.00
            )

        elif state == "WAITING":
            self.input_wave.set_intensity(
                0.12
            )
            self.response_wave.set_intensity(
                0.18
            )

        else:
            self.input_wave.set_intensity(
                0.16
            )
            self.response_wave.set_intensity(
                0.16
            )

    def set_user_text(
        self,
        text: str,
    ) -> None:
        self.user_text_label.setText(
            text
        )

    def set_pat_text(
        self,
        text: str,
    ) -> None:
        self.pat_text_label.setText(
            text
        )

    def set_active_target(
        self,
        kind: str | None,
        value: str | None,
    ) -> None:
        if not kind or not value:
            self.target_kind_label.setText(
                "NONE"
            )
            self.target_value_label.setText(
                "NO ACTIVE TARGET"
            )
            return

        self.target_kind_label.setText(
            kind.upper()
        )
        self.target_value_label.setText(
            value
        )

    # ========================================================
    # TIMER / KEYS
    # ========================================================

    def _tick(self) -> None:
        visual = STATES[
            self.current_state
        ]

        self.core.tick()

        self.input_wave.tick(
            visual.speed * 0.70
        )

        self.response_wave.tick(
            visual.speed * 0.82
        )

    def keyPressEvent(
        self,
        event,
    ) -> None:
        states = {
            Qt.Key.Key_1: "IDLE",
            Qt.Key.Key_2: "LISTENING",
            Qt.Key.Key_3: "THINKING",
            Qt.Key.Key_4: "SPEAKING",
            Qt.Key.Key_5: "WAITING",
        }

        if event.key() in states:
            self.set_state(
                states[event.key()]
            )
            return

        if (
            event.key()
            == Qt.Key.Key_Escape
        ):
            self.close()
            return

        super().keyPressEvent(
            event
        )

    # ========================================================
    # WINDOW
    # ========================================================

    def toggle_maximize(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


# ============================================================
# STANDALONE DEMO
# ============================================================

def run_demo() -> int:
    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "PAT Visual Core"
    )

    window = PATWindow()

    window.set_user_text(
        "Open YouTube."
    )

    window.set_pat_text(
        "Opening YouTube."
    )

    window.set_active_target(
        "website",
        "youtube",
    )

    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(
        run_demo()
    )
