from __future__ import annotations

import math
from pathlib import Path

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.rendering import units as _units
from src.rendering.units import TempSpinBox
from src.version import VERSION as _VERSION_RAW

_VERSION = f"v{_VERSION_RAW}"
_AUTHOR  = 'Craig "Duke" Smith'
_YEAR    = "2026"
_GITHUB  = "https://github.com/dukesmith0/pytherm"


def _wc():
    """Welcome dialog / About dialog theme-aware colors."""
    from PyQt6.QtWidgets import QApplication
    p = QApplication.instance().palette()
    is_dark = p.window().color().lightnessF() < 0.5
    if is_dark:
        return {
            "header_bg": "#16162a", "title": "#fff", "subtitle": "#9999cc",
            "meta": "#8888aa", "link": "#4488bb", "link_hover": "#88ccff",
            "section": "#b0b0b0", "field": "#b0b0b0", "recent": "#b0b0b0",
            "recent_hover_bg": "#333355", "recent_hover_fg": "#fff",
            "sep": "#333", "btn_create_bg": "#2a7a6e", "btn_create_hover": "#37a090",
            "btn_open_bg": "#38385a", "btn_open_fg": "#ccc",
            "btn_open_hover_bg": "#4a4a72", "btn_open_hover_fg": "#fff",
        }
    return {
        "header_bg": "#e0e0f0", "title": "#1e1e1e", "subtitle": "#5555aa",
        "meta": "#666688", "link": "#2266aa", "link_hover": "#1155cc",
        "section": "#666", "field": "#555", "recent": "#555",
        "recent_hover_bg": "#d0d0e8", "recent_hover_fg": "#1e1e1e",
        "sep": "#ccc", "btn_create_bg": "#2a7a6e", "btn_create_hover": "#37a090",
        "btn_open_bg": "#d0d0e8", "btn_open_fg": "#333",
        "btn_open_hover_bg": "#b8b8d8", "btn_open_hover_fg": "#1e1e1e",
    }


# ── Logo / icon drawing ──────────────────────────────────────────────────────

def _heatmap_color(t: float) -> QColor:
    """t in [0, 1]: 0 = cold (blue) → 1 = hot (red)."""
    stops = [
        (0.00, (  0,   0, 255)),
        (0.25, (  0, 255, 255)),
        (0.50, (  0, 255,   0)),
        (0.75, (255, 255,   0)),
        (1.00, (255,   0,   0)),
    ]
    t = max(0.0, min(1.0, t))
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return QColor(
                int(c0[0] + f * (c1[0] - c0[0])),
                int(c0[1] + f * (c1[1] - c0[1])),
                int(c0[2] + f * (c1[2] - c0[2])),
            )
    return QColor(255, 0, 0)


def make_logo_pixmap(size: int = 80) -> QPixmap:
    """Draw the PyTherm icon: a 5×5 heatmap grid, hot top-left → cold bottom-right."""
    px = QPixmap(size, size)
    px.fill(QColor(28, 28, 40))

    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)

    n   = 5
    gap = max(1, size // 32)
    cell = (size - gap * (n + 1)) / n
    max_d = math.sqrt((n - 1) ** 2 + (n - 1) ** 2)

    for r in range(n):
        for c in range(n):
            d = math.sqrt(r * r + c * c)
            t = 1.0 - d / max_d
            p.setBrush(_heatmap_color(t))
            x = int(gap + c * (cell + gap))
            y = int(gap + r * (cell + gap))
            p.drawRoundedRect(x, y, int(cell), int(cell), 2, 2)

    p.end()
    return px


def make_app_icon() -> QIcon:
    """Return the application window icon (64 × 64 px)."""
    return QIcon(make_logo_pixmap(64))


# ── Welcome dialog ───────────────────────────────────────────────────────────

class WelcomeDialog(QDialog):
    """Startup dialog shown when PyTherm launches.

    After exec(), inspect ``self.action``:
      ``"new"``    -- user filled grid options and clicked Create;
                     call :meth:`new_grid_values` to retrieve them.
      ``"open"``   -- user clicked Open File.
      ``"recent"`` -- user clicked a recent file; ``self.recent_path`` is set.
      ``""``        -- dialog was dismissed without a choice (start with default grid).
    """

    def __init__(self, recent_files: list[str], materials: dict | None = None,
                 parent=None) -> None:
        super().__init__(parent)
        self.action:      str = ""
        self.recent_path: str = ""
        self._materials = materials or {}

        self.setWindowTitle("PyTherm")
        self.setFixedWidth(460)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header: logo + branding ──────────────────────────────────────────
        c = _wc()
        header = QWidget()
        header.setAutoFillBackground(True)
        pal = header.palette()
        pal.setColor(header.backgroundRole(), QColor(c["header_bg"]))
        header.setPalette(pal)

        hlayout = QHBoxLayout(header)
        hlayout.setContentsMargins(20, 20, 20, 20)
        hlayout.setSpacing(18)

        logo_lbl = QLabel()
        logo_lbl.setPixmap(make_logo_pixmap(72))
        logo_lbl.setFixedSize(72, 72)
        hlayout.addWidget(logo_lbl)

        text_col = QVBoxLayout()
        text_col.setSpacing(3)
        text_col.setContentsMargins(0, 0, 0, 0)

        lbl_title = QLabel("PyTherm")
        lbl_title.setStyleSheet(f"color: {c['title']}; font-size: 26px; font-weight: bold;")
        text_col.addWidget(lbl_title)

        lbl_sub = QLabel("2D Heat Conduction Simulator")
        lbl_sub.setStyleSheet(f"color: {c['subtitle']}; font-size: 12px;")
        text_col.addWidget(lbl_sub)

        lbl_meta = QLabel(f"{_VERSION}  ·  Made by {_AUTHOR}  ·  {_YEAR}")
        lbl_meta.setStyleSheet(f"color: {c['meta']}; font-size: 11px;")
        text_col.addWidget(lbl_meta)

        btn_gh = QPushButton("⌖  github.com/dukesmith0/pytherm")
        btn_gh.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {c['link']}; font-size: 11px;
                text-align: left; padding: 0;
            }}
            QPushButton:hover {{ color: {c['link_hover']}; }}
        """)
        btn_gh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_gh.setFlat(True)
        btn_gh.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(_GITHUB)))
        text_col.addWidget(btn_gh)

        hlayout.addLayout(text_col)
        hlayout.addStretch()
        root.addWidget(header)

        # ── Body ────────────────────────────────────────────────────────────
        body = QWidget()
        blayout = QVBoxLayout(body)
        blayout.setContentsMargins(20, 18, 20, 20)
        blayout.setSpacing(12)

        # New simulation section
        blayout.addWidget(_section_label("NEW SIMULATION", c["section"]))

        dim_row = QHBoxLayout()
        dim_row.setSpacing(8)
        dim_row.addWidget(_field_label("Rows:"))
        self._rows = QSpinBox()
        self._rows.setRange(1, 200)
        self._rows.setValue(20)
        self._rows.setFixedWidth(62)
        dim_row.addWidget(self._rows)
        dim_row.addSpacing(10)
        dim_row.addWidget(_field_label("Columns:"))
        self._cols = QSpinBox()
        self._cols.setRange(1, 200)
        self._cols.setValue(20)
        self._cols.setFixedWidth(62)
        dim_row.addWidget(self._cols)
        dim_row.addStretch()
        blayout.addLayout(dim_row)

        opts_row = QHBoxLayout()
        opts_row.setSpacing(8)
        opts_row.addWidget(_field_label("Cell size:"))
        self._cell_size = QDoubleSpinBox()
        self._cell_size.setRange(0.1, 100.0)
        self._cell_size.setDecimals(1)
        self._cell_size.setValue(1.0)
        self._cell_size.setSuffix(" cm")
        self._cell_size.setFixedWidth(90)
        opts_row.addWidget(self._cell_size)
        opts_row.addSpacing(10)
        opts_row.addWidget(_field_label("Ambient:"))
        lo, hi = _units.spinbox_range()
        self._ambient = TempSpinBox()
        self._ambient.setRange(lo, hi)
        self._ambient.setDecimals(1)
        self._ambient.setValue(_units.to_display(293.15))  # 20 °C default
        self._ambient.setSuffix(f" {_units.suffix()}")
        self._ambient.setFixedWidth(100)
        opts_row.addWidget(self._ambient)
        opts_row.addStretch()
        blayout.addLayout(opts_row)

        if self._materials:
            mat_row = QHBoxLayout()
            mat_row.setSpacing(8)
            mat_row.addWidget(_field_label("Base material:"))
            self._mat_combo = QComboBox()
            for mat in self._materials.values():
                self._mat_combo.addItem(mat.name, mat.id)
            self._mat_combo.setFixedWidth(160)
            mat_row.addWidget(self._mat_combo)
            mat_row.addStretch()
            blayout.addLayout(mat_row)
        else:
            self._mat_combo = None

        btn_new = QPushButton("▶   Create New Grid")
        btn_new.setStyleSheet(
            f"QPushButton {{ background-color: {c['btn_create_bg']}; color: #fff; padding: 9px 0; "
            f"border-radius: 4px; font-size: 13px; font-weight: bold; }} "
            f"QPushButton:hover {{ background-color: {c['btn_create_hover']}; }}"
        )
        btn_new.clicked.connect(self._on_new)
        blayout.addWidget(btn_new)

        blayout.addWidget(_sep(c["sep"]))

        # Open file
        btn_open = QPushButton("📂   Open Existing File...")
        btn_open.setStyleSheet(
            f"QPushButton {{ background-color: {c['btn_open_bg']}; color: {c['btn_open_fg']}; padding: 9px 0; "
            f"border-radius: 4px; font-size: 13px; }} "
            f"QPushButton:hover {{ background-color: {c['btn_open_hover_bg']}; color: {c['btn_open_hover_fg']}; }}"
        )
        btn_open.clicked.connect(self._on_open)
        blayout.addWidget(btn_open)

        # Recent files
        if recent_files:
            blayout.addWidget(_sep(c["sep"]))
            blayout.addWidget(_section_label("RECENT FILES", c["section"]))
            for path in recent_files[:5]:
                name = Path(path).name
                r_btn = QPushButton(f"  ▸  {name}")
                r_btn.setToolTip(path)
                r_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent; border: none; color: {c['recent']};
                        text-align: left; padding: 4px 8px; font-size: 12px;
                        border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {c['recent_hover_fg']}; background: {c['recent_hover_bg']}; }}
                """)
                r_btn.clicked.connect(lambda _c, p=path: self._on_recent(p))
                blayout.addWidget(r_btn)

        root.addWidget(body)

    # ── Public ──────────────────────────────────────────────────────────────

    def new_grid_values(self) -> tuple[int, int, float, float, str]:
        """Return ``(rows, cols, dx_metres, ambient_kelvin, base_material_id)``."""
        mat_id = self._mat_combo.currentData() if self._mat_combo else "vacuum"
        return (
            self._rows.value(),
            self._cols.value(),
            self._cell_size.value() / 100.0,
            _units.from_display(self._ambient.value()),
            mat_id,
        )

    # ── Internal ────────────────────────────────────────────────────────────

    def _on_new(self) -> None:
        self.action = "new"
        self.accept()

    def _on_open(self) -> None:
        self.action = "open"
        self.accept()

    def _on_recent(self, path: str) -> None:
        self.action = "recent"
        self.recent_path = path
        self.accept()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _section_label(text: str, color: str = "#b0b0b0") -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {color}; font-size: 10px; font-weight: bold;")
    return lbl


def _field_label(text: str) -> QLabel:
    c = _wc()
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {c['field']}; font-size: 12px;")
    return lbl


def _sep(color: str = "#333") -> QFrame:
    sep = QFrame()
    sep.setFrameShape(QFrame.Shape.HLine)
    sep.setStyleSheet(f"background: {color}; max-height: 1px;")
    return sep
