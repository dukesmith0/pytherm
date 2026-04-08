from __future__ import annotations

from PyQt6.QtCore import QEvent, QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QFont, QLinearGradient, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from src.rendering import units as _units
from src.rendering.heatmap_renderer import heatmap_color

_legend_theme = "dark"

def _lc():
    if _legend_theme == "light":
        return {
            "bg": QColor(245, 245, 248), "border": QColor(180, 180, 180),
            "title_bg": "#e0e0e0", "title_border": "#bbb",
            "title_text": "#333", "label": QColor(40, 40, 40),
            "tick": QColor(150, 150, 150), "tick_label": QColor(60, 60, 60),
            "btn_text": "#555", "btn_hover": "#ddd",
        }
    return {
        "bg": QColor(30, 30, 30), "border": QColor(68, 68, 68),
        "title_bg": "#2a2a2a", "title_border": "#444",
        "title_text": "#ccc", "label": QColor(200, 200, 200),
        "tick": QColor(100, 100, 100), "tick_label": QColor(180, 180, 180),
        "btn_text": "#aaa", "btn_hover": "#3a3a3a",
    }

_BTN_STYLE = (
    "QPushButton { background: transparent; color: #b0b0b0; font-size: 11px; "
    "border: none; padding: 0; }"
    "QPushButton:hover { color: #fff; background: #3a3a3a; border-radius: 2px; }"
)
_BTN_STYLE_PIN = _BTN_STYLE + "QPushButton:checked { color: #29b6f6; }"

_TITLE_H   = 22
_LABEL_W   = 54
_BAR_W_SM  = 16
_BAR_W_LG  = 32
_BAR_H_SM  = 140
_BAR_H_LG  = 220


class LegendOverlay(QWidget):
    """Floating, draggable temperature scale legend.

    Parented to the GridView so it stays within the canvas area.
    """

    closed = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._t_min: float = 273.15
        self._t_max: float = 373.15
        self._flow_mode: bool = False
        self._pinned: bool = True
        self._expanded: bool = False
        self._drag_origin: QPoint | None = None

        self.setWindowFlags(Qt.WindowType.Widget)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self._build_titlebar()
        self._do_resize()

        # Track parent resizes to re-snap corner position
        if parent:
            parent.installEventFilter(self)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_theme(self, theme: str) -> None:
        global _legend_theme
        _legend_theme = theme
        lc = _lc()
        self._titlebar.setStyleSheet(
            f"#LegendTitleBar {{ background: {lc['title_bg']}; border-bottom: 1px solid {lc['title_border']}; }}"
        )
        self.update()

    def update_bounds(self, t_min: float, t_max: float, flow_mode: bool = False) -> None:
        if t_min != self._t_min or t_max != self._t_max or flow_mode != self._flow_mode:
            self._t_min = t_min
            self._t_max = t_max
            self._flow_mode = flow_mode
            self.update()

    # ── Internal layout ───────────────────────────────────────────────────────

    def _build_titlebar(self) -> None:
        self._titlebar = QWidget(self)
        self._titlebar.setFixedHeight(_TITLE_H)
        self._titlebar.setObjectName("LegendTitleBar")
        self._titlebar.setStyleSheet(
            "#LegendTitleBar { background: #2a2a2a; border-bottom: 1px solid #444; }"
        )

        row = QHBoxLayout(self._titlebar)
        row.setContentsMargins(6, 0, 4, 0)
        row.setSpacing(2)

        lbl = QLabel("Color Scale")
        lbl.setStyleSheet("color: #ccc; font-size: 10px;")
        row.addWidget(lbl)
        row.addStretch()

        self._pin_btn = QPushButton("P")
        self._pin_btn.setFixedSize(18, 18)
        self._pin_btn.setCheckable(True)
        self._pin_btn.setChecked(True)
        self._pin_btn.setToolTip("Pin to corner / unpin to drag")
        self._pin_btn.setStyleSheet(_BTN_STYLE_PIN)
        self._pin_btn.clicked.connect(self._on_pin_clicked)
        row.addWidget(self._pin_btn)

        self._exp_btn = QPushButton("+")
        self._exp_btn.setFixedSize(18, 18)
        self._exp_btn.setToolTip("Expand / collapse")
        self._exp_btn.setStyleSheet(_BTN_STYLE)
        self._exp_btn.clicked.connect(self._on_expand_clicked)
        row.addWidget(self._exp_btn)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(18, 18)
        close_btn.setToolTip("Close")
        close_btn.setStyleSheet(
            _BTN_STYLE + "QPushButton:hover { color: #f66; background: #3a3a3a; border-radius: 2px; }"
        )
        close_btn.clicked.connect(self._on_close_clicked)
        row.addWidget(close_btn)

        # Enable drag on the titlebar background (not on buttons)
        self._titlebar.installEventFilter(self)

    def _do_resize(self) -> None:
        bw = _BAR_W_LG if self._expanded else _BAR_W_SM
        bh = _BAR_H_LG if self._expanded else _BAR_H_SM
        w  = bw + _LABEL_W + 8
        h  = _TITLE_H + bh + 8
        self.setFixedSize(w, h)
        self._titlebar.setFixedWidth(w)
        if self._pinned and self.parent():
            self._snap_to_corner()

    def _snap_to_corner(self) -> None:
        if not self.parent():
            return
        p = self.parent()
        self.move(p.width() - self.width() - 8, p.height() - self.height() - 8)

    # ── Qt events ─────────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._pinned:
            self._snap_to_corner()

    def eventFilter(self, obj, event) -> bool:
        # Parent resize -> re-snap if pinned
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            if self._pinned and self.isVisible():
                self._snap_to_corner()
            return False

        # Titlebar drag
        if obj is self._titlebar:
            t = event.type()
            if t == QEvent.Type.MouseButtonPress:
                if not self._pinned and event.button() == Qt.MouseButton.LeftButton:
                    self._drag_origin = (
                        event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                    )
                    return True
            elif t == QEvent.Type.MouseMove:
                if self._drag_origin is not None and (
                    event.buttons() == Qt.MouseButton.LeftButton
                ):
                    new_pos = event.globalPosition().toPoint() - self._drag_origin
                    if self.parent():
                        p = self.parent()
                        nx = max(0, min(new_pos.x(), p.width()  - self.width()))
                        ny = max(0, min(new_pos.y(), p.height() - self.height()))
                        self.move(nx, ny)
                    else:
                        self.move(new_pos)
                    return True
            elif t == QEvent.Type.MouseButtonRelease:
                self._drag_origin = None

        return super().eventFilter(obj, event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)

        # Background + border
        lc = _lc()
        p.fillRect(self.rect(), lc["bg"])
        border_pen = QPen(lc["border"])
        border_pen.setWidth(1)
        p.setPen(border_pen)
        p.drawRect(0, 0, self.width() - 1, self.height() - 1)

        bw = _BAR_W_LG if self._expanded else _BAR_W_SM
        bh = _BAR_H_LG if self._expanded else _BAR_H_SM
        bx = 4
        by = _TITLE_H + 4

        # Gradient bar
        grad = QLinearGradient(bx, by, bx, by + bh)
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            t = self._t_max - frac * (self._t_max - self._t_min)
            grad.setColorAt(frac, heatmap_color(t, self._t_min, self._t_max))
        p.fillRect(bx, by, bw, bh, QBrush(grad))

        bar_pen = QPen(QColor(80, 80, 80))
        bar_pen.setWidth(1)
        p.setPen(bar_pen)
        p.drawRect(bx, by, bw - 1, bh - 1)

        # Labels
        font = QFont()
        font.setPixelSize(10)
        p.setFont(font)
        p.setPen(lc["label"])

        lx  = bx + bw + 4

        def _fmt(v: float) -> str:
            if self._flow_mode:
                if v < 1e-9:
                    return "0 W"
                if v >= 1e6:
                    return f"{v / 1e6:.1f} MW"
                if v >= 1000:
                    return f"{v / 1000:.1f} kW"
                if v >= 1:
                    return f"{v:.1f} W"
                if v >= 0.001:
                    return f"{v * 1000:.0f} mW"
                return f"{v * 1e6:.0f} \u00b5W"
            return f"{_units.to_display(v):.0f} {_units.suffix()}"

        p.drawText(lx, by + 11, _fmt(self._t_max))
        p.drawText(lx, by + bh, _fmt(self._t_min))

        if self._expanded:
            tick_pen = QPen(lc["tick"])
            p.setPen(tick_pen)
            for frac in (0.25, 0.5, 0.75):
                t   = self._t_max - frac * (self._t_max - self._t_min)
                ty  = by + int(frac * bh)
                p.drawLine(bx + bw, ty, bx + bw + 3, ty)
                p.setPen(lc["tick_label"])
                p.drawText(lx, ty + 4, _fmt(t))
                p.setPen(tick_pen)

        p.end()

    # ── Button handlers ───────────────────────────────────────────────────────

    def _on_pin_clicked(self, _checked: bool = False) -> None:
        self._pinned = self._pin_btn.isChecked()
        if self._pinned:
            self._snap_to_corner()

    def _on_expand_clicked(self, _checked: bool = False) -> None:
        self._expanded = not self._expanded
        self._exp_btn.setText("-" if self._expanded else "+")
        self._do_resize()

    def _on_close_clicked(self, _checked: bool = False) -> None:
        self.hide()
        self.closed.emit()
