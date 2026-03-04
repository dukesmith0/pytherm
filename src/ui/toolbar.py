from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolBar,
    QWidget,
)

from src.rendering import units as _units


class Toolbar(QToolBar):
    """Top toolbar — draw/select mode, simulation controls, view mode, and borders."""

    draw_mode_changed           = pyqtSignal(bool)         # True = draw, False = select
    play_pause_toggled          = pyqtSignal(bool)         # True = play, False = pause
    reset_requested             = pyqtSignal()
    speed_changed               = pyqtSignal(float)        # new speed multiplier
    view_mode_changed           = pyqtSignal(str)          # "material" | "heatmap"
    heatmap_auto_changed        = pyqtSignal(bool)
    heatmap_range_changed       = pyqtSignal(float, float) # (min_K, max_K)
    boundary_conditions_changed = pyqtSignal(dict)         # per-side BC dict
    unit_changed                = pyqtSignal(str)          # "°C" | "K" | "°F"
    grid_lines_toggled          = pyqtSignal(bool)
    fit_view_requested          = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMovable(False)

        # ── Draw / Select mode ──────────────────────────────────────────────
        self._btn_draw   = QPushButton("✏  Draw")
        self._btn_select = QPushButton("↖  Select")
        for btn in (self._btn_draw, self._btn_select):
            btn.setCheckable(True)
            btn.setFixedWidth(80)

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._btn_draw)
        self._mode_group.addButton(self._btn_select)
        self._btn_draw.setChecked(True)

        self.addWidget(self._btn_draw)
        self.addWidget(self._btn_select)
        self._btn_draw.toggled.connect(lambda on: on and self.draw_mode_changed.emit(True))
        self._btn_select.toggled.connect(lambda on: on and self.draw_mode_changed.emit(False))

        self.addSeparator()

        # ── Simulation controls ─────────────────────────────────────────────
        self._btn_play = QPushButton("▶  Play")
        self._btn_play.setCheckable(True)
        self._btn_play.setFixedWidth(88)
        self.addWidget(self._btn_play)

        self._btn_reset = QPushButton("↺  Reset")
        self._btn_reset.setFixedWidth(80)
        self.addWidget(self._btn_reset)

        self.addSeparator()

        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("padding: 0 4px;")
        self.addWidget(speed_label)

        self._speed_combo = QComboBox()
        self._speed_combo.setFixedWidth(82)
        for label, val in [
            ("1×",      1.0),
            ("10×",     10.0),
            ("100×",    100.0),
            ("1 000×",  1_000.0),
            ("10 000×", 10_000.0),
        ]:
            self._speed_combo.addItem(label, val)
        self.addWidget(self._speed_combo)

        self.addSeparator()

        self._time_label = QLabel("0:00:00.000")
        self._time_label.setStyleSheet("padding: 0 8px; color: #aaa;")
        self.addWidget(self._time_label)

        self.addSeparator()

        # ── View mode toggle ────────────────────────────────────────────────
        self._btn_material = QPushButton("Material")
        self._btn_heatmap  = QPushButton("Heatmap")
        for btn in (self._btn_material, self._btn_heatmap):
            btn.setCheckable(True)
            btn.setFixedWidth(80)

        self._view_group = QButtonGroup(self)
        self._view_group.addButton(self._btn_material)
        self._view_group.addButton(self._btn_heatmap)
        self._btn_material.setChecked(True)

        self.addWidget(self._btn_material)
        self.addWidget(self._btn_heatmap)

        self._btn_material.toggled.connect(lambda on: on and self._set_view("material"))
        self._btn_heatmap.toggled.connect(lambda on: on and self._set_view("heatmap"))

        self.addSeparator()

        # ── Heatmap scale controls (hidden in material mode) ────────────────
        self._hm_min_k: float = 273.15   # 0 °C
        self._hm_max_k: float = 373.15   # 100 °C

        self._heatmap_controls = QWidget()
        hm = QHBoxLayout(self._heatmap_controls)
        hm.setContentsMargins(4, 0, 4, 0)
        hm.setSpacing(6)

        self._hm_auto = QCheckBox("Auto")
        self._hm_auto.setChecked(True)
        hm.addWidget(self._hm_auto)

        hm.addWidget(QLabel("Min:"))
        self._hm_min = QDoubleSpinBox()
        self._hm_min.setRange(-273.15, 10000.0)
        self._hm_min.setValue(0.0)
        self._hm_min.setSuffix(" °C")
        self._hm_min.setFixedWidth(100)
        self._hm_min.setEnabled(False)
        hm.addWidget(self._hm_min)

        hm.addWidget(QLabel("Max:"))
        self._hm_max = QDoubleSpinBox()
        self._hm_max.setRange(-273.15, 10000.0)
        self._hm_max.setValue(100.0)
        self._hm_max.setSuffix(" °C")
        self._hm_max.setFixedWidth(100)
        self._hm_max.setEnabled(False)
        hm.addWidget(self._hm_max)

        self._heatmap_controls.setVisible(False)
        self.addWidget(self._heatmap_controls)

        self.addSeparator()

        # ── Border boundary conditions ───────────────────────────────────────
        border_widget = QWidget()
        bw = QHBoxLayout(border_widget)
        bw.setContentsMargins(4, 0, 4, 0)
        bw.setSpacing(2)
        lbl = QLabel("Borders:")
        lbl.setStyleSheet("padding: 0 2px; color: #aaa;")
        bw.addWidget(lbl)

        self._border_btns: dict[str, QPushButton] = {}
        self._border_labels: dict[str, str] = {
            "top": "Top", "bottom": "Bot", "left": "Left", "right": "Right"
        }
        for key, display in self._border_labels.items():
            btn = QPushButton(f"{display}: Ins.")
            btn.setCheckable(True)
            btn.setFixedWidth(72)
            btn.setToolTip(f"{display} edge — unchecked = insulator (zero flux), checked = ambient sink")
            bw.addWidget(btn)
            self._border_btns[key] = btn
            btn.toggled.connect(lambda checked, k=key: self._on_border_toggled(k, checked))

        self.addWidget(border_widget)

        self.addSeparator()

        # ── Unit toggle ──────────────────────────────────────────────────────
        unit_lbl = QLabel("Unit:")
        unit_lbl.setStyleSheet("padding: 0 2px; color: #aaa;")
        self.addWidget(unit_lbl)

        self._unit_combo = QComboBox()
        self._unit_combo.setFixedWidth(58)
        for u in ("°C", "K", "°F"):
            self._unit_combo.addItem(u)
        self.addWidget(self._unit_combo)

        self.addSeparator()

        # ── View utilities ───────────────────────────────────────────────────
        btn_fit = QPushButton("⊡ Fit")
        btn_fit.setFixedWidth(56)
        btn_fit.setToolTip("Fit grid to view (F)")
        self.addWidget(btn_fit)

        self._btn_gridlines = QPushButton("Grid")
        self._btn_gridlines.setCheckable(True)
        self._btn_gridlines.setChecked(True)
        self._btn_gridlines.setFixedWidth(46)
        self._btn_gridlines.setToolTip("Toggle grid lines")
        self.addWidget(self._btn_gridlines)

        # ── Wire all signals ─────────────────────────────────────────────────
        self._btn_play.toggled.connect(self.play_pause_toggled)
        self._btn_reset.clicked.connect(self.reset_requested)
        self._speed_combo.currentIndexChanged.connect(
            lambda i: self.speed_changed.emit(self._speed_combo.itemData(i))
        )
        self._hm_auto.toggled.connect(self._on_hm_auto_toggled)
        self._hm_min.valueChanged.connect(self._emit_hm_range)
        self._hm_max.valueChanged.connect(self._emit_hm_range)
        self._unit_combo.currentTextChanged.connect(self.unit_changed)
        btn_fit.clicked.connect(self.fit_view_requested)
        self._btn_gridlines.toggled.connect(self.grid_lines_toggled)

    # ── Public API ──────────────────────────────────────────────────────────

    def set_running(self, running: bool) -> None:
        """Sync the play/pause button without re-emitting play_pause_toggled."""
        self._btn_play.blockSignals(True)
        self._btn_play.setChecked(running)
        self._btn_play.setText("‖  Pause" if running else "▶  Play")
        self._btn_play.blockSignals(False)

    def update_sim_time(self, t: float) -> None:
        h  = int(t // 3600)
        m  = int((t % 3600) // 60)
        s  = int(t % 60)
        ms = int((t % 1) * 1000)
        self._time_label.setText(f"{h}:{m:02d}:{s:02d}.{ms:03d}")

    def refresh_units(self) -> None:
        """Refresh heatmap spinbox suffixes and values to the current display unit."""
        suf      = f" {_units.suffix()}"
        lo, hi   = _units.spinbox_range()
        for spin, k_val in [(self._hm_min, self._hm_min_k), (self._hm_max, self._hm_max_k)]:
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            spin.setValue(_units.to_display(k_val))
            spin.blockSignals(False)

    # ── Internal ────────────────────────────────────────────────────────────

    def _set_view(self, mode: str) -> None:
        self._heatmap_controls.setVisible(mode == "heatmap")
        self.view_mode_changed.emit(mode)

    def _on_hm_auto_toggled(self, auto: bool) -> None:
        self._hm_min.setEnabled(not auto)
        self._hm_max.setEnabled(not auto)
        self.heatmap_auto_changed.emit(auto)

    def _emit_hm_range(self) -> None:
        self._hm_min_k = _units.from_display(self._hm_min.value())
        self._hm_max_k = _units.from_display(self._hm_max.value())
        self.heatmap_range_changed.emit(self._hm_min_k, self._hm_max_k)

    def _on_border_toggled(self, key: str, checked: bool) -> None:
        display = self._border_labels[key]
        self._border_btns[key].setText(f"{display}: {'Sink' if checked else 'Ins.'}")
        bc = {k: "sink" if btn.isChecked() else "insulator" for k, btn in self._border_btns.items()}
        self.boundary_conditions_changed.emit(bc)
