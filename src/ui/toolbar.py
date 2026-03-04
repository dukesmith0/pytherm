from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QToolBar,
    QWidget,
)

from src.rendering import units as _units


class Toolbar(QToolBar):
    """Top toolbar — draw/select mode, simulation controls, view mode, and borders.

    All content lives in a horizontally-scrollable inner widget so that items
    are never hidden when the window is narrow.
    """

    draw_mode_changed           = pyqtSignal(bool)         # True = draw, False = select
    play_pause_toggled          = pyqtSignal(bool)         # True = play, False = pause
    reset_requested             = pyqtSignal()
    speed_changed               = pyqtSignal(float)        # new speed multiplier
    view_mode_changed           = pyqtSignal(str)          # "material" | "heatmap"
    heatmap_auto_changed        = pyqtSignal(bool)
    heatmap_range_changed       = pyqtSignal(float, float) # (min_K, max_K)
    boundary_conditions_changed = pyqtSignal(dict)         # per-side BC dict
    unit_changed                = pyqtSignal(str)          # "\u00b0C" | "K" | "\u00b0F"
    grid_lines_toggled          = pyqtSignal(bool)
    abbr_toggled                = pyqtSignal(bool)         # show material abbreviations
    fit_view_requested          = pyqtSignal()
    dx_changed                  = pyqtSignal(float)        # new dx in metres

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMovable(False)

        # All toolbar items live in a scrollable container so nothing is lost
        # when the window is narrow.
        self._content = QWidget()
        self._layout = QHBoxLayout(self._content)
        self._layout.setContentsMargins(2, 0, 2, 0)
        self._layout.setSpacing(2)

        # ── Draw / Select mode ──────────────────────────────────────────────
        self._btn_draw   = QPushButton("\u270f  Draw")
        self._btn_select = QPushButton("\u2196  Select")
        for btn in (self._btn_draw, self._btn_select):
            btn.setCheckable(True)
            btn.setFixedWidth(80)

        self._btn_draw.setToolTip("Draw mode — click or drag to paint cells with the active material (D)")
        self._btn_select.setToolTip("Select mode — click or drag to select cells for group editing (S)")

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._btn_draw)
        self._mode_group.addButton(self._btn_select)
        self._btn_draw.setChecked(True)

        self._layout.addWidget(self._btn_draw)
        self._layout.addWidget(self._btn_select)
        self._btn_draw.toggled.connect(lambda on: on and self.draw_mode_changed.emit(True))
        self._btn_select.toggled.connect(lambda on: on and self.draw_mode_changed.emit(False))

        self._add_sep()

        # ── Simulation controls ─────────────────────────────────────────────
        self._btn_play = QPushButton("\u25b6  Play")
        self._btn_play.setCheckable(True)
        self._btn_play.setFixedWidth(88)
        self._btn_play.setToolTip("Start or pause the thermal simulation (Space)")
        self._layout.addWidget(self._btn_play)

        self._btn_reset = QPushButton("\u21ba  Reset")
        self._btn_reset.setFixedWidth(80)
        self._btn_reset.setToolTip("Reset all cell temperatures to the ambient value (R)")
        self._layout.addWidget(self._btn_reset)

        self._add_sep()

        speed_label = QLabel("Speed:")
        speed_label.setStyleSheet("padding: 0 4px;")
        self._layout.addWidget(speed_label)

        self._speed_combo = QComboBox()
        self._speed_combo.setFixedWidth(82)
        self._speed_combo.setToolTip("Simulation speed multiplier relative to real time")
        for label, val in [
            ("1\u00d7",      1.0),
            ("10\u00d7",     10.0),
            ("100\u00d7",    100.0),
            ("1 000\u00d7",  1_000.0),
            ("10 000\u00d7", 10_000.0),
        ]:
            self._speed_combo.addItem(label, val)
        self._layout.addWidget(self._speed_combo)

        self._add_sep()

        self._time_label = QLabel("0:00:00.000")
        self._time_label.setStyleSheet("padding: 0 8px; color: #aaa;")
        self._layout.addWidget(self._time_label)

        self._add_sep()

        # ── View mode toggle ────────────────────────────────────────────────
        self._btn_material = QPushButton("Material")
        self._btn_heatmap  = QPushButton("Heatmap")
        for btn in (self._btn_material, self._btn_heatmap):
            btn.setCheckable(True)
            btn.setFixedWidth(80)

        self._btn_material.setToolTip("Material view — show each cell's material color")
        self._btn_heatmap.setToolTip("Heatmap view — show cell temperatures as a blue-to-red color gradient")

        self._view_group = QButtonGroup(self)
        self._view_group.addButton(self._btn_material)
        self._view_group.addButton(self._btn_heatmap)
        self._btn_material.setChecked(True)

        self._layout.addWidget(self._btn_material)
        self._layout.addWidget(self._btn_heatmap)

        self._btn_material.toggled.connect(lambda on: on and self._set_view("material"))
        self._btn_heatmap.toggled.connect(lambda on: on and self._set_view("heatmap"))

        self._add_sep()

        # ── Heatmap scale controls (hidden in material mode) ────────────────
        self._hm_min_k: float = 273.15   # 0 \u00b0C
        self._hm_max_k: float = 373.15   # 100 \u00b0C

        self._heatmap_controls = QWidget()
        hm = QHBoxLayout(self._heatmap_controls)
        hm.setContentsMargins(4, 0, 4, 0)
        hm.setSpacing(6)

        self._hm_auto = QCheckBox("Auto")
        self._hm_auto.setChecked(True)
        self._hm_auto.setToolTip("Auto-scale: fit the color range to the current min/max temperature each frame")
        hm.addWidget(self._hm_auto)

        hm.addWidget(QLabel("Min:"))
        self._hm_min = QDoubleSpinBox()
        self._hm_min.setRange(-273.15, 10000.0)
        self._hm_min.setValue(0.0)
        self._hm_min.setSuffix(" \u00b0C")
        self._hm_min.setFixedWidth(100)
        self._hm_min.setEnabled(False)
        self._hm_min.setToolTip("Minimum temperature — mapped to blue on the heatmap (requires Auto off)")
        hm.addWidget(self._hm_min)

        hm.addWidget(QLabel("Max:"))
        self._hm_max = QDoubleSpinBox()
        self._hm_max.setRange(-273.15, 10000.0)
        self._hm_max.setValue(100.0)
        self._hm_max.setSuffix(" \u00b0C")
        self._hm_max.setFixedWidth(100)
        self._hm_max.setEnabled(False)
        self._hm_max.setToolTip("Maximum temperature — mapped to red on the heatmap (requires Auto off)")
        hm.addWidget(self._hm_max)

        self._heatmap_controls.setVisible(False)
        self._layout.addWidget(self._heatmap_controls)

        self._add_sep()

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
            btn.setToolTip(f"{display} edge \u2014 unchecked = insulator (zero flux), checked = ambient sink")
            bw.addWidget(btn)
            self._border_btns[key] = btn
            btn.toggled.connect(lambda checked, k=key: self._on_border_toggled(k, checked))

        self._layout.addWidget(border_widget)

        self._add_sep()

        # ── Unit toggle ──────────────────────────────────────────────────────
        unit_lbl = QLabel("Unit:")
        unit_lbl.setStyleSheet("padding: 0 2px; color: #aaa;")
        self._layout.addWidget(unit_lbl)

        self._unit_combo = QComboBox()
        self._unit_combo.setFixedWidth(58)
        self._unit_combo.setToolTip("Temperature display unit — applies to all spinboxes and the heatmap labels")
        for u in ("\u00b0C", "K", "\u00b0F"):
            self._unit_combo.addItem(u)
        self._layout.addWidget(self._unit_combo)

        self._add_sep()

        # ── Cell size (dx) — editable spinbox ───────────────────────────────
        dx_lbl = QLabel("Cell:")
        dx_lbl.setStyleSheet("padding: 0 2px; color: #aaa;")
        self._layout.addWidget(dx_lbl)

        self._dx_spin = QDoubleSpinBox()
        self._dx_spin.setRange(0.1, 100.0)
        self._dx_spin.setDecimals(1)
        self._dx_spin.setValue(1.0)
        self._dx_spin.setSuffix(" cm")
        self._dx_spin.setFixedWidth(80)
        self._dx_spin.setToolTip("Physical cell size \u2014 changing this resets the simulation")
        self._layout.addWidget(self._dx_spin)

        self._add_sep()

        # ── View utilities ───────────────────────────────────────────────────
        btn_fit = QPushButton("\u229f Fit")
        btn_fit.setFixedWidth(56)
        btn_fit.setToolTip("Fit grid to view (F)")
        self._layout.addWidget(btn_fit)

        self._btn_gridlines = QPushButton("Grid")
        self._btn_gridlines.setCheckable(True)
        self._btn_gridlines.setChecked(True)
        self._btn_gridlines.setFixedWidth(46)
        self._btn_gridlines.setToolTip("Toggle grid lines (G)")
        self._layout.addWidget(self._btn_gridlines)

        self._btn_abbr = QPushButton("Abbr.")
        self._btn_abbr.setCheckable(True)
        self._btn_abbr.setChecked(False)
        self._btn_abbr.setFixedWidth(52)
        self._btn_abbr.setToolTip("Show material abbreviation in each cell")
        self._layout.addWidget(self._btn_abbr)

        self._layout.addStretch()

        # ── Wrap content in a horizontal scroll area ─────────────────────────
        scroll = QScrollArea()
        scroll.setWidget(self._content)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Match the toolbar height so the scroll area fits flush
        scroll.setFixedHeight(38)
        self.addWidget(scroll)

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
        self._btn_abbr.toggled.connect(self.abbr_toggled)
        self._dx_spin.valueChanged.connect(
            lambda v: self.dx_changed.emit(v / 100.0)  # cm → m
        )

    # ── Public API ──────────────────────────────────────────────────────────

    def activate_draw_mode(self) -> None:
        """Switch to draw mode (keyboard shortcut D)."""
        self._btn_draw.setChecked(True)

    def activate_select_mode(self) -> None:
        """Switch to select mode (keyboard shortcut S)."""
        self._btn_select.setChecked(True)

    def toggle_play_pause(self) -> None:
        """Toggle the play/pause button (keyboard shortcut Space)."""
        self._btn_play.toggle()

    def trigger_reset(self) -> None:
        """Emit reset_requested (keyboard shortcut R)."""
        self.reset_requested.emit()

    def toggle_grid_lines(self) -> None:
        """Toggle grid-lines visibility (keyboard shortcut G)."""
        self._btn_gridlines.toggle()

    def set_dx(self, dx_m: float) -> None:
        """Update the cell-size spinbox without emitting dx_changed. dx_m is in metres."""
        self._dx_spin.blockSignals(True)
        self._dx_spin.setValue(dx_m * 100.0)  # m → cm
        self._dx_spin.blockSignals(False)

    def set_running(self, running: bool) -> None:
        """Sync the play/pause button without re-emitting play_pause_toggled."""
        self._btn_play.blockSignals(True)
        self._btn_play.setChecked(running)
        self._btn_play.setText("\u2016  Pause" if running else "\u25b6  Play")
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

    def _add_sep(self) -> None:
        """Add a thin vertical separator line to the inner layout."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #444; margin: 4px 3px;")
        self._layout.addWidget(sep)

    def _set_view(self, mode: str) -> None:
        self._heatmap_controls.setVisible(mode == "heatmap")
        self.view_mode_changed.emit(mode)

    def _on_hm_auto_toggled(self, auto: bool) -> None:
        self._hm_min.setEnabled(not auto)
        self._hm_max.setEnabled(not auto)
        self.heatmap_auto_changed.emit(auto)

    def _emit_hm_range(self) -> None:
        lo = _units.from_display(self._hm_min.value())
        hi = _units.from_display(self._hm_max.value())
        if lo >= hi:
            return
        self._hm_min_k = lo
        self._hm_max_k = hi
        self.heatmap_range_changed.emit(self._hm_min_k, self._hm_max_k)

    def _on_border_toggled(self, key: str, checked: bool) -> None:
        display = self._border_labels[key]
        self._border_btns[key].setText(f"{display}: {'Sink' if checked else 'Ins.'}")
        bc = {k: "sink" if btn.isChecked() else "insulator" for k, btn in self._border_btns.items()}
        self.boundary_conditions_changed.emit(bc)
