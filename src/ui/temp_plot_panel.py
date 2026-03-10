from __future__ import annotations

import csv
import math
import statistics
from collections import deque

from PyQt6.QtCore import Qt, QPoint, QRectF, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import (
    QCheckBox, QComboBox, QDockWidget, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QToolTip, QVBoxLayout, QWidget,
)

from src.rendering import units as _units
from src.simulation.grid import Grid

_SERIES_COLORS = [
    QColor(0, 200, 180),    # teal   -- Mean / single cell
    QColor(255, 100,  80),  # red    -- Max
    QColor(255, 165,  50),  # orange -- Median
    QColor( 80, 140, 220),  # blue   -- Min
]
_GROUP_SERIES = ["Mean", "Max", "Median", "Min"]


def _nice_step(range_size: float, target_ticks: int = 4) -> float:
    """Return a 'nice' grid step for the given range (1, 2, or 5 times a power of 10)."""
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


class _PlotCanvas(QWidget):
    """Custom QPainter line chart: temperature vs. simulated time."""

    sync_hover_changed = pyqtSignal(object)   # float | None  -- shift-hover time cursor
    sync_pin_changed   = pyqtSignal(object)   # float | None  -- shift-click persistent pin

    _PAD_L, _PAD_R, _PAD_T, _PAD_B = 52, 12, 10, 26

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)
        self.setMouseTracking(True)
        self._series: dict[str, deque[tuple[float, float]]] = {}
        self._max_points = 500
        self._disabled: set[str] = set()
        # Zoom/pan state (None = auto from data)
        self._t_min_view: float | None = None
        self._t_max_view: float | None = None
        # Drag state
        self._drag_start_x: int | None = None
        self._drag_t_min_start: float = 0.0
        self._drag_t_max_start: float = 1.0
        # Hover state: (series_name, t, T_k) or None
        self._hover_data: tuple[str, float, float] | None = None
        # Per-plot pinned points: list of (series_name, t, T_k)
        self._pinned_points: list[tuple[str, float, float]] = []
        # Cross-panel sync cursors (set from outside)
        self._sync_hover_t: float | None = None
        self._sync_pin_t: float | None = None
        # Shift-hover tracking (to know when to emit clear)
        self._shift_hovering: bool = False
        # Click detection: press position to distinguish click from drag
        self._click_start: tuple[float, float] | None = None

    def set_disabled(self, names: set[str]) -> None:
        self._disabled = set(names)
        self.update()

    def reset_view(self) -> None:
        self._t_min_view = None
        self._t_max_view = None
        self.update()

    def set_max_points(self, n: int) -> None:
        self._max_points = n
        for name in list(self._series):
            old = list(self._series[name])
            self._series[name] = deque(old[-n:], maxlen=n)

    def set_series(self, names: list[str]) -> None:
        self._series = {name: deque(maxlen=self._max_points) for name in names}
        self._pinned_points = []
        self.reset_view()

    def add_point(self, name: str, t: float, temp_k: float) -> None:
        if name in self._series:
            self._series[name].append((t, temp_k))

    def clear(self, _checked: bool = False) -> None:
        for name in self._series:
            self._series[name].clear()
        self._pinned_points = []
        self.reset_view()

    def _all_t_range(self) -> tuple[float, float] | None:
        all_pts = [pt for s in self._series.values() for pt in s]
        if not all_pts:
            return None
        t_min = min(p[0] for p in all_pts)
        t_max = max(p[0] for p in all_pts)
        if t_max <= t_min:
            t_max = t_min + 1.0
        return t_min, t_max

    def _view_t_range(self) -> tuple[float, float] | None:
        data = self._all_t_range()
        if data is None:
            return None
        t_min = self._t_min_view if self._t_min_view is not None else data[0]
        t_max = self._t_max_view if self._t_max_view is not None else data[1]
        if t_max <= t_min:
            t_max = t_min + 1.0
        return t_min, t_max

    def _px_to_t(self, px: float, t_min: float, t_max: float, pad_l: int, plot_w: int) -> float:
        if plot_w == 0:
            return t_min
        return t_min + (px - pad_l) / plot_w * (t_max - t_min)

    # --- Sync cursor public API ---

    def set_sync_hover(self, t: float | None) -> None:
        self._sync_hover_t = t
        self.update()

    def set_sync_pin(self, t: float | None) -> None:
        self._sync_pin_t = t
        self.update()

    # --- Pin helpers ---

    def _find_nearest(self, px: float, py: float) -> tuple[str, float, float] | None:
        """Return (series_name, t, T_k) of the nearest visible point within 20px, or None."""
        vt = self._view_t_range()
        if vt is None:
            return None
        t_min, t_max = vt
        pad_l, pad_r, pad_t, pad_b = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        plot_w = self.width() - pad_l - pad_r
        plot_h = self.height() - pad_t - pad_b
        active_pts = [p for nm, s in self._series.items() if nm not in self._disabled for p in s]
        if not active_pts:
            return None
        T_k_all = [p[1] for p in active_pts]
        T_min_k = min(T_k_all)
        T_max_k = max(T_k_all)
        pk = max(1.0, (T_max_k - T_min_k) * 0.15)
        T_min_k -= pk
        T_max_k += pk
        T_min_d = _units.to_display(T_min_k)
        T_max_d = _units.to_display(T_max_k)
        dT_d = T_max_d - T_min_d

        def to_x(t: float) -> float:
            return pad_l + (t - t_min) / (t_max - t_min) * plot_w if t_max > t_min else float(pad_l)

        def to_y(T_k: float) -> float:
            if dT_d == 0:
                return pad_t + plot_h / 2
            return pad_t + plot_h - (_units.to_display(T_k) - T_min_d) / dT_d * plot_h

        best_dist_sq = 400.0  # 20px radius
        best: tuple[str, float, float] | None = None
        for name, pts in self._series.items():
            if name in self._disabled or not pts:
                continue
            for t_pt, T_k_pt in pts:
                d2 = (to_x(t_pt) - px) ** 2 + (to_y(T_k_pt) - py) ** 2
                if d2 < best_dist_sq:
                    best_dist_sq = d2
                    best = (name, t_pt, T_k_pt)
        return best

    def _handle_click(self, px: float, py: float, modifiers) -> None:
        """Handle a non-drag left-click: pin/unpin or sync-pin."""
        vt = self._view_t_range()
        if vt is None:
            return
        t_min, t_max = vt
        pad_l = self._PAD_L
        plot_w = self.width() - pad_l - self._PAD_R
        if not (pad_l <= px <= pad_l + plot_w):
            return
        t_cursor = self._px_to_t(px, t_min, t_max, pad_l, plot_w)
        if modifiers & Qt.KeyboardModifier.ShiftModifier:
            # Toggle global sync pin across all panels
            if self._sync_pin_t is not None and abs(self._sync_pin_t - t_cursor) < (t_max - t_min) * 0.05:
                self.sync_pin_changed.emit(None)
            else:
                self.sync_pin_changed.emit(t_cursor)
        else:
            # Toggle per-plot pin on nearest series point
            nearest = self._find_nearest(px, py)
            if nearest is None:
                return
            pname, pt, pT_k = nearest
            for i, (n, t, _T) in enumerate(self._pinned_points):
                if n == pname and abs(t - pt) < 1e-9:
                    del self._pinned_points[i]
                    self.update()
                    return
            self._pinned_points.append((pname, pt, pT_k))
            self.update()

    def _update_shift_hover(self, px: float, in_plot: bool, shift_held: bool) -> None:
        """Emit sync_hover_changed when shift is held over the plot, or clear it."""
        if shift_held and in_plot and self._drag_start_x is None:
            vt = self._view_t_range()
            if vt:
                t_min, t_max = vt
                plot_w = self.width() - self._PAD_L - self._PAD_R
                t_cur = self._px_to_t(px, t_min, t_max, self._PAD_L, plot_w)
                self._shift_hovering = True
                self.sync_hover_changed.emit(t_cur)
        elif self._shift_hovering:
            self._shift_hovering = False
            self.sync_hover_changed.emit(None)

    def wheelEvent(self, event) -> None:
        vt = self._view_t_range()
        if vt is None:
            return
        t_min, t_max = vt
        pad_l = self._PAD_L
        plot_w = self.width() - pad_l - self._PAD_R
        t_cursor = self._px_to_t(event.position().x(), t_min, t_max, pad_l, plot_w)
        delta = event.angleDelta().y()
        factor = 1.25 if delta > 0 else 1.0 / 1.25
        old_range = t_max - t_min
        new_range = old_range / factor
        frac = (t_cursor - t_min) / old_range if old_range > 0 else 0.5
        self._t_min_view = t_cursor - frac * new_range
        self._t_max_view = t_cursor + (1.0 - frac) * new_range
        self.update()
        event.accept()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            vt = self._view_t_range()
            if vt is None:
                return
            px, py = event.position().x(), event.position().y()
            self._drag_start_x = int(px)
            self._drag_t_min_start, self._drag_t_max_start = vt
            self._click_start = (px, py)
        elif event.button() == Qt.MouseButton.RightButton:
            self.reset_view()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._click_start is not None:
            px, py = event.position().x(), event.position().y()
            dx = px - self._click_start[0]
            dy = py - self._click_start[1]
            if dx * dx + dy * dy < 25.0:  # < 5px movement = click, not drag
                self._handle_click(px, py, event.modifiers())
        self._click_start = None
        self._drag_start_x = None

    def mouseDoubleClickEvent(self, event) -> None:
        self.reset_view()

    def leaveEvent(self, event) -> None:
        self._hover_data = None
        if self._shift_hovering:
            self._shift_hovering = False
            self.sync_hover_changed.emit(None)
        QToolTip.hideText()
        self.update()

    def mouseMoveEvent(self, event) -> None:
        px = event.position().x()
        py = event.position().y()
        pad_l, pad_r, pad_t, pad_b = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B
        plot_w = self.width() - pad_l - pad_r
        plot_h = self.height() - pad_t - pad_b
        shift_held = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)

        # Pan mode
        if self._drag_start_x is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            dx = px - self._drag_start_x
            old_range = self._drag_t_max_start - self._drag_t_min_start
            dt = -(dx / plot_w) * old_range if plot_w else 0.0
            self._t_min_view = self._drag_t_min_start + dt
            self._t_max_view = self._drag_t_max_start + dt
            self.update()
            return

        in_plot = pad_l <= px <= pad_l + plot_w and pad_t <= py <= pad_t + plot_h

        if not in_plot:
            self._hover_data = None
            QToolTip.hideText()
            self._update_shift_hover(px, False, shift_held)
            self.update()
            return

        nearest = self._find_nearest(px, py)
        if nearest:
            best_name, best_t, best_T_k = nearest
            self._hover_data = (best_name, best_t, best_T_k)
            suf = _units.suffix()
            T_display = _units.to_display(best_T_k)
            t_str = f"{best_t:.2f}s" if best_t < 1000 else f"{best_t:.1f}s"
            tip = f"{best_name}\nt = {t_str}\nT = {T_display:.2f} {suf}"
            QToolTip.showText(self.mapToGlobal(QPoint(int(px), int(py))), tip, self)
        else:
            self._hover_data = None
            QToolTip.hideText()
        self._update_shift_hover(px, True, shift_held)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw(painter)
        painter.end()

    def _draw(self, painter: QPainter) -> None:
        w, h = self.width(), self.height()
        pad_l, pad_r, pad_t, pad_b = self._PAD_L, self._PAD_R, self._PAD_T, self._PAD_B

        painter.fillRect(0, 0, w, h, QColor(28, 28, 38))

        active_pts = [
            pt for name, s in self._series.items()
            if name not in self._disabled
            for pt in s
        ]
        if not active_pts:
            painter.setPen(QColor(80, 80, 80))
            font = QFont()
            font.setPixelSize(11)
            painter.setFont(font)
            painter.drawText(
                QRectF(0, 0, w, h),
                Qt.AlignmentFlag.AlignCenter,
                "Select a cell to start tracking",
            )
            return

        vt = self._view_t_range()
        if vt is None:
            return
        t_min, t_max = vt

        T_k_all = [p[1] for p in active_pts]
        T_min_k = min(T_k_all)
        T_max_k = max(T_k_all)
        pad_k = max(1.0, (T_max_k - T_min_k) * 0.15)
        T_min_k -= pad_k
        T_max_k += pad_k

        plot_w = w - pad_l - pad_r
        plot_h = h - pad_t - pad_b

        T_min_d = _units.to_display(T_min_k)
        T_max_d = _units.to_display(T_max_k)
        dT_d = T_max_d - T_min_d

        def to_x(t: float) -> float:
            return pad_l + (t - t_min) / (t_max - t_min) * plot_w

        def to_y(T_k: float) -> float:
            if dT_d == 0:
                return pad_t + plot_h / 2
            return pad_t + plot_h - (_units.to_display(T_k) - T_min_d) / dT_d * plot_h

        def to_y_d(T_d: float) -> float:
            if dT_d == 0:
                return pad_t + plot_h / 2
            return pad_t + plot_h - (T_d - T_min_d) / dT_d * plot_h

        # Grid lines -- nice intervals anchored at 0
        font = QFont()
        font.setPixelSize(9)
        painter.setFont(font)
        grid_pen = QPen(QColor(45, 45, 60))
        grid_pen.setCosmetic(True)
        y_step = _nice_step(dT_d)
        y_tick = math.ceil(T_min_d / y_step) * y_step
        tick_count = 0
        while y_tick <= T_max_d + y_step * 1e-6 and tick_count < 20:
            gy = int(to_y_d(y_tick))
            if pad_t <= gy <= pad_t + plot_h:
                painter.setPen(grid_pen)
                painter.drawLine(pad_l, gy, pad_l + plot_w, gy)
                painter.setPen(QColor(75, 75, 95))
                painter.drawText(2, gy + 4, f"{y_tick:.0f}")
            y_tick = round(y_tick + y_step, 10)
            tick_count += 1
        grid_pen2 = QPen(QColor(40, 40, 55))
        grid_pen2.setCosmetic(True)
        origin_pen = QPen(QColor(60, 60, 80))
        origin_pen.setCosmetic(True)
        x_step = _nice_step(t_max - t_min)
        x_tick = math.ceil(t_min / x_step) * x_step
        tick_count = 0
        while x_tick <= t_max + x_step * 1e-6 and tick_count < 20:
            gx = int(to_x(x_tick))
            if pad_l <= gx <= pad_l + plot_w:
                painter.setPen(origin_pen if abs(x_tick) < x_step * 1e-6 else grid_pen2)
                painter.drawLine(gx, pad_t, gx, pad_t + plot_h)
            x_tick = round(x_tick + x_step, 10)
            tick_count += 1
        # Always draw t=0 reference if in view and not already drawn by the tick loop
        if t_min < 0 < t_max:
            gx0 = int(to_x(0.0))
            if pad_l <= gx0 <= pad_l + plot_w:
                painter.setPen(origin_pen)
                painter.drawLine(gx0, pad_t, gx0, pad_t + plot_h)

        # Axes
        axis_pen = QPen(QColor(70, 70, 70))
        axis_pen.setCosmetic(True)
        painter.setPen(axis_pen)
        painter.drawLine(pad_l, pad_t, pad_l, pad_t + plot_h)
        painter.drawLine(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h)

        # Axis labels
        suf = _units.suffix()
        painter.setPen(QColor(120, 120, 120))
        painter.drawText(2, pad_t + plot_h + 4, f"{T_min_d:.0f}{suf}")
        painter.drawText(2, pad_t + 9,          f"{T_max_d:.0f}{suf}")
        t_min_lbl = f"{t_min:.1f}s" if abs(t_min) < 1000 else f"{t_min:.0f}s"
        t_max_lbl = f"{t_max:.1f}s" if abs(t_max) < 1000 else f"{t_max:.0f}s"
        painter.drawText(pad_l, h - 4, t_min_lbl)
        t_label_x = int(pad_l + plot_w - len(t_max_lbl) * 5)
        painter.drawText(t_label_x, h - 4, t_max_lbl)

        # Clip to plot area so lines don't bleed into axis label margins
        painter.setClipRect(pad_l, pad_t, plot_w, plot_h)

        # Series lines
        for i, (name, pts) in enumerate(self._series.items()):
            if name in self._disabled or not pts:
                continue
            color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
            pen = QPen(color)
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            pt_list = list(pts)
            for j in range(1, len(pt_list)):
                x0 = int(to_x(pt_list[j - 1][0]))
                y0 = int(to_y(pt_list[j - 1][1]))
                x1 = int(to_x(pt_list[j][0]))
                y1 = int(to_y(pt_list[j][1]))
                painter.drawLine(x0, y0, x1, y1)

        # Sync hover cursor: dashed gray vertical line + small dots on each series
        if self._sync_hover_t is not None:
            sx = int(to_x(self._sync_hover_t))
            if pad_l <= sx <= pad_l + plot_w:
                pen = QPen(QColor(140, 140, 160), 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(sx, pad_t, sx, pad_t + plot_h)
                for i, (name, pts) in enumerate(self._series.items()):
                    if name in self._disabled or not pts:
                        continue
                    near = min(pts, key=lambda p: abs(p[0] - self._sync_hover_t))
                    color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(color)
                    painter.drawEllipse(sx - 3, int(to_y(near[1])) - 3, 6, 6)
                    painter.setBrush(Qt.BrushStyle.NoBrush)

        # Sync pin cursor: solid white vertical line + labeled dots on each series
        if self._sync_pin_t is not None:
            sx = int(to_x(self._sync_pin_t))
            if pad_l <= sx <= pad_l + plot_w:
                pen = QPen(QColor(210, 210, 220), 1, Qt.PenStyle.SolidLine)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(sx, pad_t, sx, pad_t + plot_h)
                font_s = QFont()
                font_s.setPixelSize(9)
                painter.setFont(font_s)
                for i, (name, pts) in enumerate(self._series.items()):
                    if name in self._disabled or not pts:
                        continue
                    near = min(pts, key=lambda p: abs(p[0] - self._sync_pin_t))
                    nx, ny = sx, int(to_y(near[1]))
                    color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(color)
                    painter.drawEllipse(nx - 4, ny - 4, 8, 8)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.setPen(QColor(210, 210, 220))
                    painter.drawText(nx + 6, ny + 4, f"{_units.to_display(near[1]):.1f}{suf}")

        # Hover crosshairs: dashed lines (vertical + horizontal) in series color
        if self._hover_data is not None:
            hname, ht, hT_k = self._hover_data
            if hname not in self._disabled and hname in self._series:
                hi = list(self._series.keys()).index(hname)
                hcolor = _SERIES_COLORS[hi % len(_SERIES_COLORS)]
                hx, hy = int(to_x(ht)), int(to_y(hT_k))
                pen = QPen(hcolor, 1, Qt.PenStyle.DashLine)
                pen.setCosmetic(True)
                painter.setPen(pen)
                painter.drawLine(hx, pad_t, hx, pad_t + plot_h)
                painter.drawLine(pad_l, hy, pad_l + plot_w, hy)

        # Pin crosshairs: solid lines + dot + label for each pinned point
        font_p = QFont()
        font_p.setPixelSize(9)
        for pname, pt, pT_k in self._pinned_points:
            if pname in self._disabled or pname not in self._series:
                continue
            pi = list(self._series.keys()).index(pname)
            pcolor = _SERIES_COLORS[pi % len(_SERIES_COLORS)]
            px_ = int(to_x(pt))
            py_ = int(to_y(pT_k))
            pen = QPen(pcolor, 1, Qt.PenStyle.SolidLine)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawLine(px_, pad_t, px_, pad_t + plot_h)
            painter.drawLine(pad_l, py_, pad_l + plot_w, py_)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pcolor)
            painter.drawEllipse(px_ - 5, py_ - 5, 10, 10)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            t_str = f"{pt:.1f}s" if pt < 1000 else f"{pt:.0f}s"
            lbl = f"{_units.to_display(pT_k):.1f}{suf} @ {t_str}"
            lbl_w = len(lbl) * 6
            painter.setFont(font_p)
            painter.setPen(pcolor)
            if px_ + 8 + lbl_w <= pad_l + plot_w:
                painter.drawText(px_ + 8, py_ - 2, lbl)
            else:
                painter.drawText(px_ - 8 - lbl_w, py_ - 2, lbl)

        painter.setClipping(False)

        # Hover dot (drawn after clip cleared so partial dots on edges stay visible)
        if self._hover_data is not None:
            hname, ht, hT_k = self._hover_data
            if hname not in self._disabled and hname in self._series:
                hi = list(self._series.keys()).index(hname)
                hcolor = _SERIES_COLORS[hi % len(_SERIES_COLORS)]
                hx = int(to_x(ht))
                hy = int(to_y(hT_k))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(hcolor)
                painter.drawEllipse(hx - 4, hy - 4, 8, 8)
                painter.setBrush(Qt.BrushStyle.NoBrush)

        # Legend (top-right corner), skip disabled
        font2 = QFont()
        font2.setPixelSize(9)
        painter.setFont(font2)
        lx = pad_l + plot_w - 70
        ly = pad_t + 10
        for i, name in enumerate(self._series):
            if name in self._disabled:
                continue
            color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
            painter.setPen(color)
            painter.drawText(lx, ly, name)
            ly += 13


class TempPlotPanel(QDockWidget):
    """Dockable temperature-vs-time plot panel."""

    closing              = pyqtSignal()        # emitted in closeEvent (C++ still valid)
    sync_hover_changed   = pyqtSignal(object)  # float | None -- bubbled from canvas
    sync_pin_changed     = pyqtSignal(object)  # float | None -- bubbled from canvas

    def __init__(self, grid: Grid, title: str = "Temperature Plot", parent=None) -> None:
        super().__init__(title, parent)
        self.setObjectName("TempPlotPanel")
        self._grid = grid
        self._tracked: list[tuple[int, int]] = []
        self._track_mode = "single"
        self._pinned: bool = False

        self._canvas = _PlotCanvas()
        self._canvas.sync_hover_changed.connect(self.sync_hover_changed)
        self._canvas.sync_pin_changed.connect(self.sync_pin_changed)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Info bar
        bar = QHBoxLayout()
        self._info_label = QLabel("No selection")
        self._info_label.setStyleSheet("color: #888; font-size: 10px;")
        self._info_label.setFixedWidth(110)  # wide enough for "Cell (199, 199)"
        bar.addWidget(self._info_label)
        bar.addStretch()

        self._label_combo = QComboBox()
        self._label_combo.setFixedWidth(110)
        self._label_combo.setToolTip("Quick-select cells by label")
        self._label_combo.addItem("(by label)")
        self._label_combo.currentIndexChanged.connect(self._on_label_selected)
        bar.addWidget(self._label_combo)

        export_btn = QPushButton("Export CSV")
        export_btn.setFixedWidth(82)
        export_btn.clicked.connect(self._export_csv)
        bar.addWidget(export_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(50)
        clear_btn.clicked.connect(self._canvas.clear)
        bar.addWidget(clear_btn)

        self._pin_btn = QPushButton("Pin")
        self._pin_btn.setCheckable(True)
        self._pin_btn.setFixedWidth(42)
        self._pin_btn.setToolTip("Pin: keep current series when selection changes")
        self._pin_btn.toggled.connect(self._on_pin_toggled)
        bar.addWidget(self._pin_btn)

        layout.addLayout(bar)

        # Series toggle bar (group mode only)
        self._toggle_bar = QWidget()
        toggle_layout = QHBoxLayout(self._toggle_bar)
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        toggle_layout.setSpacing(8)
        show_lbl = QLabel("Show:")
        show_lbl.setStyleSheet("color: #888; font-size: 10px;")
        toggle_layout.addWidget(show_lbl)
        self._series_checks: dict[str, QCheckBox] = {}
        for i, name in enumerate(_GROUP_SERIES):
            chk = QCheckBox(name)
            chk.setChecked(True)
            color = _SERIES_COLORS[i % len(_SERIES_COLORS)]
            chk.setStyleSheet(f"color: rgb({color.red()},{color.green()},{color.blue()}); font-size: 10px;")
            chk.toggled.connect(self._update_disabled)
            self._series_checks[name] = chk
            toggle_layout.addWidget(chk)
        toggle_layout.addStretch()
        self._toggle_bar.hide()
        layout.addWidget(self._toggle_bar)

        layout.addWidget(self._canvas, stretch=1)

        self.setWidget(inner)
        self.refresh_labels()

    # --- Public API ---

    @property
    def is_pinned(self) -> bool:
        return self._pinned

    def closeEvent(self, event) -> None:
        self.closing.emit()
        super().closeEvent(event)

    def set_grid(self, grid: Grid) -> None:
        self._grid = grid
        self._tracked = []
        self._canvas.set_series([])
        self._canvas.set_sync_hover(None)
        self._canvas.set_sync_pin(None)
        self._info_label.setText("No selection")
        self._toggle_bar.hide()
        self.refresh_labels()

    def set_sync_hover(self, t: float | None) -> None:
        self._canvas.set_sync_hover(t)

    def set_sync_pin(self, t: float | None) -> None:
        self._canvas.set_sync_pin(t)

    def set_max_points(self, n: int) -> None:
        self._canvas.set_max_points(n)

    def refresh_labels(self) -> None:
        labels = sorted({
            self._grid.cell(r, c).label
            for r in range(self._grid.rows)
            for c in range(self._grid.cols)
            if self._grid.cell(r, c).label
            and not self._grid.cell(r, c).material.is_vacuum
        })
        self._label_combo.blockSignals(True)
        self._label_combo.clear()
        self._label_combo.addItem("(by label)")
        for lbl in labels:
            self._label_combo.addItem(lbl)
        self._label_combo.blockSignals(False)

    def set_tracked_cells(self, cells: list[tuple[int, int]]) -> None:
        if self._pinned:
            return
        self._tracked = list(cells)
        if not cells:
            self._canvas.set_series([])
            self._info_label.setText("No selection")
            self._toggle_bar.hide()
            return
        if len(cells) == 1:
            r, c = cells[0]
            self._track_mode = "single"
            self._canvas.set_series([f"({r},{c})"])
            self._info_label.setText(f"Cell ({r}, {c})")
            self._toggle_bar.hide()
        else:
            self._track_mode = "group"
            self._canvas.set_series(_GROUP_SERIES)
            self._canvas.set_disabled({
                name for name, chk in self._series_checks.items() if not chk.isChecked()
            })
            self._info_label.setText(f"{len(cells)} cells")
            self._toggle_bar.show()

    def on_tick(self, sim_time: float) -> None:
        if not self._tracked:
            return
        temps = [
            self._grid.cell(r, c).temperature
            for r, c in self._tracked
            if not self._grid.cell(r, c).material.is_vacuum
        ]
        if not temps:
            return
        if self._track_mode == "single":
            name = f"({self._tracked[0][0]},{self._tracked[0][1]})"
            self._canvas.add_point(name, sim_time, temps[0])
        else:
            self._canvas.add_point("Mean",   sim_time, sum(temps) / len(temps))
            self._canvas.add_point("Max",    sim_time, max(temps))
            self._canvas.add_point("Median", sim_time, statistics.median(temps))
            self._canvas.add_point("Min",    sim_time, min(temps))
        self._canvas.update()

    def clear_history(self, _checked: bool = False) -> None:
        self._canvas.clear()

    def refresh_units(self) -> None:
        self._canvas.update()

    # --- Private ---

    def _on_pin_toggled(self, checked: bool) -> None:
        self._pinned = checked
        self._pin_btn.setText("Pinned" if checked else "Pin")

    def _update_disabled(self) -> None:
        disabled = {name for name, chk in self._series_checks.items() if not chk.isChecked()}
        self._canvas.set_disabled(disabled)

    def _on_label_selected(self, index: int) -> None:
        if index <= 0:
            return
        label = self._label_combo.itemText(index)
        cells = [
            (r, c)
            for r in range(self._grid.rows)
            for c in range(self._grid.cols)
            if self._grid.cell(r, c).label == label
            and not self._grid.cell(r, c).material.is_vacuum
        ]
        self.set_tracked_cells(cells)

    def _export_csv(self, _checked: bool = False) -> None:
        series = self._canvas._series
        if not any(series.values()):
            QMessageBox.information(self, "No Data", "No data to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Plot CSV", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        if not path.endswith(".csv"):
            path += ".csv"
        suf = _units.suffix()
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["time_s", "series", f"temp_{suf}"])
                for name, pts in series.items():
                    for t, T_k in pts:
                        writer.writerow([
                            f"{t:.4f}", name,
                            f"{_units.to_display(T_k):.4f}",
                        ])
        except OSError as e:
            QMessageBox.warning(self, "Export Failed", str(e))
