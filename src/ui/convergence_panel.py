from __future__ import annotations

import math
from collections import deque

from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

# Reuse the same theme variable from temp_plot_panel
from src.ui.temp_plot_panel import _pc
from PyQt6.QtWidgets import (
    QDockWidget, QHBoxLayout, QLabel, QPushButton, QToolTip, QVBoxLayout, QWidget,
)


def _nice_step(range_size: float, target_ticks: int = 4) -> float:
    if range_size <= 0:
        return 1.0
    raw = range_size / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    n = raw / mag
    if n <= 1.0:
        nice = 1.0
    elif n <= 2.0:
        nice = 2.0
    elif n <= 5.0:
        nice = 5.0
    else:
        nice = 10.0
    return nice * mag


class _ConvergenceCanvas(QWidget):
    """QPainter chart: max dT/dt (K/s) vs simulated time, log-scale Y."""

    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 60, 12, 10, 26

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self._data: deque[tuple[float, float]] = deque(maxlen=2000)
        self._ss_threshold: float = 0.01
        # Zoom/pan state
        self._t_min_view: float | None = None
        self._t_max_view: float | None = None
        # Drag state for panning
        self._drag_start_x: int | None = None
        self._drag_t_min_start: float = 0.0
        self._drag_t_max_start: float = 1.0
        # Hover state
        self._hover_data: tuple[float, float] | None = None  # (t, rate)

    def set_ss_threshold(self, val: float) -> None:
        self._ss_threshold = val
        self.update()

    def add_point(self, t: float, rate: float) -> None:
        self._data.append((t, max(rate, 1e-12)))
        self.update()

    def clear(self, _checked: bool = False) -> None:
        self._data.clear()
        self._t_min_view = None
        self._t_max_view = None
        self.update()

    def wheelEvent(self, event) -> None:
        if not self._data:
            return
        t_min, t_max = self._view_t_range()
        pad_l = self._PAD_L
        plot_w = self.width() - pad_l - self._PAD_R
        px = event.position().x()
        t_cursor = t_min + (px - pad_l) / plot_w * (t_max - t_min) if plot_w > 0 else t_min
        delta = event.angleDelta().y()
        factor = 1.25 if delta > 0 else 1.0 / 1.25
        old_range = t_max - t_min
        new_range = old_range / factor
        frac = (t_cursor - t_min) / old_range if old_range > 0 else 0.5
        self._t_min_view = t_cursor - frac * new_range
        self._t_max_view = t_cursor + (1.0 - frac) * new_range
        self.update()
        event.accept()

    def mouseDoubleClickEvent(self, event) -> None:
        self._t_min_view = None
        self._t_max_view = None
        self.update()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            vt = self._view_t_range() if self._data else None
            if vt:
                self._drag_start_x = int(event.position().x())
                self._drag_t_min_start, self._drag_t_max_start = vt
        elif event.button() == Qt.MouseButton.RightButton:
            self._t_min_view = None
            self._t_max_view = None
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        self._drag_start_x = None

    def mouseMoveEvent(self, event) -> None:
        px = event.position().x()
        py = event.position().y()
        pad_l = self._PAD_L
        plot_w = self.width() - pad_l - self._PAD_R

        # Pan drag
        if self._drag_start_x is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            old_range = self._drag_t_max_start - self._drag_t_min_start
            dt = -((px - self._drag_start_x) / plot_w) * old_range if plot_w > 0 else 0.0
            self._t_min_view = self._drag_t_min_start + dt
            self._t_max_view = self._drag_t_max_start + dt
            self.update()
            return

        # Hover: find nearest point
        if not self._data or plot_w <= 0:
            self._hover_data = None
            QToolTip.hideText()
            self.update()
            return
        t_min, t_max = self._view_t_range()
        t_cursor = t_min + (px - pad_l) / plot_w * (t_max - t_min)
        best = min(self._data, key=lambda p: abs(p[0] - t_cursor))
        self._hover_data = best
        t_str = f"{best[0]:.2f}s" if best[0] < 1000 else f"{best[0]:.1f}s"
        tip = f"t = {t_str}\ndT/dt = {best[1]:.4g} K/s"
        QToolTip.showText(self.mapToGlobal(QPoint(int(px), int(py))), tip, self)
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover_data = None
        QToolTip.hideText()
        self.update()

    def _view_t_range(self) -> tuple[float, float]:
        pts = list(self._data)
        d_min = pts[0][0] if pts else 0.0
        d_max = pts[-1][0] if pts else 1.0
        if d_max <= d_min:
            d_max = d_min + 1.0
        t_min = self._t_min_view if self._t_min_view is not None else d_min
        t_max = self._t_max_view if self._t_max_view is not None else d_max
        if t_max <= t_min:
            t_max = t_min + 1.0
        return t_min, t_max

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw(painter)
        painter.end()

    def _draw(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        pc = _pc()
        painter.fillRect(0, 0, w, h, pc["bg"])

        pts = list(self._data)
        if not pts:
            painter.setPen(pc["placeholder"])
            font = QFont()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(QRectF(0, 0, w, h), Qt.AlignmentFlag.AlignCenter,
                             "Run simulation to see convergence")
            return

        t_min, t_max = self._view_t_range()
        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        # Y range: log scale on rate values
        rates = [r for _, r in pts]
        r_min = max(1e-12, min(rates) * 0.5)
        r_max = max(rates) * 2.0
        # Include SS threshold in range
        r_min = min(r_min, self._ss_threshold * 0.1)
        r_max = max(r_max, self._ss_threshold * 10.0)
        log_min = math.log10(r_min)
        log_max = math.log10(r_max)
        if log_max <= log_min:
            log_max = log_min + 1.0

        def to_x(t: float) -> float:
            return pad_l + (t - t_min) / (t_max - t_min) * plot_w

        def to_y(rate: float) -> float:
            lr = math.log10(max(rate, 1e-15))
            return pad_t + plot_h - (lr - log_min) / (log_max - log_min) * plot_h

        # Grid lines
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        grid_pen = QPen(pc["grid"])
        grid_pen.setCosmetic(True)

        # Y grid: powers of 10
        y_exp_lo = int(math.floor(log_min))
        y_exp_hi = int(math.ceil(log_max))
        for exp in range(y_exp_lo, y_exp_hi + 1):
            val = 10.0 ** exp
            gy = int(to_y(val))
            if pad_t <= gy <= pad_t + plot_h:
                painter.setPen(grid_pen)
                painter.drawLine(pad_l, gy, pad_l + plot_w, gy)
                painter.setPen(pc["label"])
                if exp >= 0:
                    label = f"{val:.0f}"
                else:
                    label = f"1e{exp}"
                painter.drawText(2, gy + 4, label)

        # X grid
        x_step = _nice_step(t_max - t_min)
        x_tick = math.ceil(t_min / x_step) * x_step
        tick_count = 0
        while x_tick <= t_max + x_step * 1e-6 and tick_count < 20:
            gx = int(to_x(x_tick))
            if pad_l <= gx <= pad_l + plot_w:
                painter.setPen(grid_pen)
                painter.drawLine(gx, pad_t, gx, pad_t + plot_h)
            x_tick = round(x_tick + x_step, 10)
            tick_count += 1

        # Axes
        axis_pen = QPen(pc["axis"])
        axis_pen.setCosmetic(True)
        painter.setPen(axis_pen)
        painter.drawLine(pad_l, pad_t, pad_l, pad_t + plot_h)
        painter.drawLine(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h)

        # Axis labels
        painter.setPen(pc["label"])
        t_min_lbl = f"{t_min:.1f}s" if abs(t_min) < 1000 else f"{t_min:.0f}s"
        t_max_lbl = f"{t_max:.1f}s" if abs(t_max) < 1000 else f"{t_max:.0f}s"
        painter.drawText(pad_l, h - 4, t_min_lbl)
        t_label_x = int(pad_l + plot_w - len(t_max_lbl) * 5)
        painter.drawText(t_label_x, h - 4, t_max_lbl)

        # Y axis title
        painter.setPen(pc["label"])
        painter.drawText(2, pad_t + 9, "K/s")

        painter.setClipRect(pad_l, pad_t, plot_w, plot_h)

        # SS threshold line
        ss_y = int(to_y(self._ss_threshold))
        if pad_t <= ss_y <= pad_t + plot_h:
            ss_pen = QPen(QColor(255, 180, 60), 1, Qt.PenStyle.DashLine)
            ss_pen.setCosmetic(True)
            painter.setPen(ss_pen)
            painter.drawLine(pad_l, ss_y, pad_l + plot_w, ss_y)
            painter.setPen(QColor(255, 180, 60))
            painter.setClipping(False)
            painter.drawText(pad_l + 4, ss_y - 3, f"SS: {self._ss_threshold} K/s")
            painter.setClipRect(pad_l, pad_t, plot_w, plot_h)

        # Data line
        color = QColor(0, 200, 180)
        pen = QPen(color)
        pen.setCosmetic(True)
        pen.setWidth(2)
        painter.setPen(pen)
        for j in range(1, len(pts)):
            x0 = int(to_x(pts[j - 1][0]))
            y0 = int(to_y(pts[j - 1][1]))
            x1 = int(to_x(pts[j][0]))
            y1 = int(to_y(pts[j][1]))
            painter.drawLine(x0, y0, x1, y1)

        painter.setClipping(False)

        # Hover dot (no crosshairs)
        if self._hover_data is not None:
            ht, hr = self._hover_data
            hx = int(to_x(ht))
            hy = int(to_y(hr))
            if pad_l <= hx <= pad_l + plot_w and pad_t <= hy <= pad_t + plot_h:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 200, 180))
                painter.drawEllipse(hx - 4, hy - 4, 8, 8)
                painter.setBrush(Qt.BrushStyle.NoBrush)


class ConvergencePanel(QDockWidget):
    """Dockable convergence rate panel: max dT/dt vs simulated time."""

    closing = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__("Convergence Graph", parent)
        self.setObjectName("ConvergencePanel")

        self._canvas = _ConvergenceCanvas()
        self._is_first_tick = True

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        bar = QHBoxLayout()
        self._info_label = QLabel("max dT/dt vs time (log scale)")
        self._info_label.setStyleSheet("color: #aaa; font-size: 10px;")
        bar.addWidget(self._info_label)
        bar.addStretch()

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(50)
        clear_btn.clicked.connect(self._canvas.clear)
        bar.addWidget(clear_btn)

        layout.addLayout(bar)
        layout.addWidget(self._canvas, stretch=1)

        self.setWidget(inner)

    def closeEvent(self, event) -> None:
        self.closing.emit()
        super().closeEvent(event)

    def set_ss_threshold(self, val: float) -> None:
        self._canvas.set_ss_threshold(val)

    def on_tick(self, sim_time: float, substep_delta: float, substep_dt: float) -> None:
        if self._is_first_tick:
            self._is_first_tick = False
            return
        if substep_dt <= 0:
            return
        rate = substep_delta / substep_dt
        self._canvas.add_point(sim_time, rate)

    def clear_history(self, _checked: bool = False) -> None:
        self._is_first_tick = True
        self._canvas.clear()
