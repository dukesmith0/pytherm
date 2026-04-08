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
    QVBoxLayout,
    QWidget,
)

from src.rendering import units as _units
from src.rendering.heatmap_renderer import PALETTE_NAMES
from src.rendering.units import TempSpinBox, delta_k_to_display, delta_display_to_k


class Toolbar(QToolBar):
    """Top toolbar with two rows.

    Row 1 (always visible): mode, cell size, view toggle, borders, view utilities.
    Row 2 (heatmap/flow only): min/max range, palette, isotherms, hotspot.
    """

    mode_changed                = pyqtSignal(str)          # "draw" | "select" | "fill"
    dx_changed                  = pyqtSignal(float)        # new dx in metres
    view_mode_changed           = pyqtSignal(str)          # "material" | "heatmap"
    heatmap_auto_changed        = pyqtSignal(bool)         # auto-init from grid bounds
    heatmap_scale_mode_changed  = pyqtSignal(str)          # "static" | "live" | "smart"
    heatmap_range_changed       = pyqtSignal(float, float) # (min_K, max_K)
    palette_changed             = pyqtSignal(str)          # palette name
    isotherm_changed            = pyqtSignal(bool, float)  # (enabled, interval_K)
    hotspot_threshold_changed   = pyqtSignal(float)        # threshold_K; nan = disabled
    boundary_conditions_changed = pyqtSignal(dict)
    grid_lines_toggled          = pyqtSignal(bool)
    abbr_toggled                = pyqtSignal(bool)
    label_toggled               = pyqtSignal(bool)
    heat_vectors_toggled        = pyqtSignal(bool)
    fit_view_requested          = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMovable(False)
        self._isotherm_interval_k: float = 50.0
        self._hotspot_threshold_k: float = 373.15   # 100 °C

        # Root container: two rows stacked vertically
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ══════════════════════════════════════════════════════════════════════
        # ROW 1: always visible
        # ══════════════════════════════════════════════════════════════════════
        row1_widget = QWidget()
        self._row1 = QHBoxLayout(row1_widget)
        self._row1.setContentsMargins(2, 0, 2, 0)
        self._row1.setSpacing(2)

        # -- Draw / Select / Fill mode ----------------------------------------
        self._btn_draw   = QPushButton("\u270f  Draw")
        self._btn_select = QPushButton("\u2196  Select")
        self._btn_fill   = QPushButton("\u25a0  Fill")
        for btn in (self._btn_draw, self._btn_select, self._btn_fill):
            btn.setCheckable(True)
            btn.setFixedWidth(72)

        self._btn_draw.setToolTip("Draw mode -- click or drag to paint cells with the active material (D)")
        self._btn_select.setToolTip("Select mode -- click or drag to select cells for group editing (S)")
        self._btn_fill.setToolTip("Fill mode -- click to flood-fill all contiguous same-material cells (W)")

        self._mode_group = QButtonGroup(self)
        self._mode_group.addButton(self._btn_draw)
        self._mode_group.addButton(self._btn_select)
        self._mode_group.addButton(self._btn_fill)
        self._btn_draw.setChecked(True)

        self._row1.addWidget(self._btn_draw)
        self._row1.addWidget(self._btn_select)
        self._row1.addWidget(self._btn_fill)

        self._btn_draw.toggled.connect(lambda on: on and self.mode_changed.emit("draw"))
        self._btn_select.toggled.connect(lambda on: on and self.mode_changed.emit("select"))
        self._btn_fill.toggled.connect(lambda on: on and self.mode_changed.emit("fill"))

        self._add_sep(self._row1)

        # -- Cell size (dx) ---------------------------------------------------
        dx_lbl = QLabel("Cell:")
        dx_lbl.setStyleSheet("padding: 0 2px; color: #b0b0b0;")
        self._row1.addWidget(dx_lbl)

        self._dx_spin = QDoubleSpinBox()
        self._dx_spin.setRange(0.1, 100.0)
        self._dx_spin.setDecimals(1)
        self._dx_spin.setValue(1.0)
        self._dx_spin.setSuffix(" cm")
        self._dx_spin.setFixedWidth(80)
        self._dx_spin.setToolTip("Physical cell size -- changing this resets the simulation")
        self._row1.addWidget(self._dx_spin)

        self._add_sep(self._row1)

        # -- View mode toggle -------------------------------------------------
        self._btn_material = QPushButton("Material")
        self._btn_heatmap  = QPushButton("Heatmap")
        self._btn_flux     = QPushButton("Heat Flow")
        for btn in (self._btn_material, self._btn_heatmap, self._btn_flux):
            btn.setCheckable(True)
            btn.setFixedWidth(80)

        self._btn_material.setToolTip("Material view -- show each cell's material color")
        self._btn_heatmap.setToolTip("Heatmap view -- show cell temperatures as a color gradient")
        self._btn_flux.setToolTip("Heat flow view -- show rate of heat flow (W) through each cell")

        self._view_group = QButtonGroup(self)
        self._view_group.addButton(self._btn_material)
        self._view_group.addButton(self._btn_heatmap)
        self._view_group.addButton(self._btn_flux)
        self._btn_material.setChecked(True)

        self._row1.addWidget(self._btn_material)
        self._row1.addWidget(self._btn_heatmap)
        self._row1.addWidget(self._btn_flux)

        self._btn_material.toggled.connect(lambda on: on and self._set_view("material"))
        self._btn_heatmap.toggled.connect(lambda on: on and self._set_view("heatmap"))
        self._btn_flux.toggled.connect(lambda on: on and self._set_view("flow"))

        self._add_sep(self._row1)

        self._row1.addStretch()

        # -- Border boundary conditions ---------------------------------------
        border_widget = QWidget()
        bw = QHBoxLayout(border_widget)
        bw.setContentsMargins(4, 0, 4, 0)
        bw.setSpacing(2)
        lbl = QLabel("Borders:")
        lbl.setStyleSheet("padding: 0 2px; color: #b0b0b0;")
        bw.addWidget(lbl)

        self._border_btns: dict[str, QPushButton] = {}
        self._border_labels: dict[str, str] = {
            "top": "Top", "bottom": "Bot", "left": "Left", "right": "Right"
        }
        for key, display in self._border_labels.items():
            btn = QPushButton(f"{display}: Insulated")
            btn.setCheckable(True)
            btn.setFixedWidth(100)
            btn.setToolTip(f"{display} edge boundary condition.\n"
                          f"Insulated: no heat crosses this edge (zero flux).\n"
                          f"Fixed T: edge held at ambient temperature, heat flows freely.")
            bw.addWidget(btn)
            self._border_btns[key] = btn
            btn.toggled.connect(lambda checked, k=key: self._on_border_toggled(k, checked))

        self._row1.addWidget(border_widget)

        self._add_sep(self._row1)

        # -- View utilities ---------------------------------------------------
        btn_fit = QPushButton("\u229f Fit")
        btn_fit.setFixedWidth(56)
        btn_fit.setToolTip("Fit grid to view (F)")
        self._row1.addWidget(btn_fit)

        self._btn_gridlines = QPushButton("Grid")
        self._btn_gridlines.setCheckable(True)
        self._btn_gridlines.setChecked(True)
        self._btn_gridlines.setFixedWidth(46)
        self._btn_gridlines.setToolTip("Toggle grid lines (G)")
        self._row1.addWidget(self._btn_gridlines)

        self._btn_abbr = QPushButton("Abbr.")
        self._btn_abbr.setCheckable(True)
        self._btn_abbr.setChecked(False)
        self._btn_abbr.setFixedWidth(52)
        self._btn_abbr.setToolTip("Show material abbreviation in each cell")
        self._row1.addWidget(self._btn_abbr)

        self._btn_label = QPushButton("Label")
        self._btn_label.setCheckable(True)
        self._btn_label.setChecked(True)
        self._btn_label.setFixedWidth(52)
        self._btn_label.setToolTip("Show cell label overlays")
        self._row1.addWidget(self._btn_label)

        self._btn_vectors = QPushButton("Vectors")
        self._btn_vectors.setCheckable(True)
        self._btn_vectors.setChecked(False)
        self._btn_vectors.setFixedWidth(62)
        self._btn_vectors.setToolTip("Show heat flow direction arrows (heatmap/flow mode)")
        self._row1.addWidget(self._btn_vectors)

        # Wrap row 1 in a scroll area
        row1_scroll = QScrollArea()
        row1_scroll.setWidget(row1_widget)
        row1_scroll.setWidgetResizable(True)
        row1_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        row1_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row1_scroll.setFrameShape(QFrame.Shape.NoFrame)
        row1_scroll.setFixedHeight(38)
        root_layout.addWidget(row1_scroll)

        # ══════════════════════════════════════════════════════════════════════
        # ROW 2: heatmap / flow controls (hidden in material mode)
        # ══════════════════════════════════════════════════════════════════════
        self._hm_min_k: float = 273.15   # 0 C
        self._hm_max_k: float = 373.15   # 100 C

        self._heatmap_row = QWidget()
        hm = QHBoxLayout(self._heatmap_row)
        hm.setContentsMargins(4, 2, 4, 2)
        hm.setSpacing(6)

        hm.addWidget(QLabel("Min:"))
        self._hm_min = TempSpinBox()
        lo, hi = _units.spinbox_range()
        self._hm_min.setRange(lo, hi)
        self._hm_min.setValue(_units.to_display(self._hm_min_k))
        self._hm_min.setSuffix(f" {_units.suffix()}")
        self._hm_min.setFixedWidth(100)
        self._hm_min.setToolTip("Minimum temperature -- cold end of color gradient (manual bounds)")
        hm.addWidget(self._hm_min)

        hm.addWidget(QLabel("Max:"))
        self._hm_max = TempSpinBox()
        self._hm_max.setRange(lo, hi)
        self._hm_max.setValue(_units.to_display(self._hm_max_k))
        self._hm_max.setSuffix(f" {_units.suffix()}")
        self._hm_max.setFixedWidth(100)
        self._hm_max.setToolTip("Maximum temperature -- hot end of color gradient (manual bounds)")
        hm.addWidget(self._hm_max)

        self._add_sep(hm)

        hm.addWidget(QLabel("Palette:"))
        self._palette_combo = QComboBox()
        for name in PALETTE_NAMES:
            self._palette_combo.addItem(name)
        self._palette_combo.setFixedWidth(90)
        self._palette_combo.setToolTip("Heatmap color palette")
        hm.addWidget(self._palette_combo)

        self._add_sep(hm)

        self._iso_check = QCheckBox("Isotherms")
        self._iso_check.setChecked(False)
        self._iso_check.setToolTip("Draw contour lines at even temperature intervals")
        hm.addWidget(self._iso_check)

        self._iso_spin = QDoubleSpinBox()
        self._iso_spin.setRange(0.1, 5000.0)
        self._iso_spin.setDecimals(1)
        self._iso_spin.setValue(delta_k_to_display(self._isotherm_interval_k))
        self._iso_spin.setSuffix(f" {_units.suffix()}")
        self._iso_spin.setFixedWidth(80)
        self._iso_spin.setToolTip("Temperature interval between isotherm lines")
        hm.addWidget(self._iso_spin)

        self._add_sep(hm)

        self._hot_check = QCheckBox("Hotspot >")
        self._hot_check.setChecked(False)
        self._hot_check.setToolTip("Highlight cells exceeding the threshold temperature in red")
        hm.addWidget(self._hot_check)

        lo, hi = _units.spinbox_range()
        self._hot_spin = TempSpinBox()
        self._hot_spin.setRange(lo, hi)
        self._hot_spin.setValue(_units.to_display(self._hotspot_threshold_k))
        self._hot_spin.setSuffix(f" {_units.suffix()}")
        self._hot_spin.setFixedWidth(100)
        self._hot_spin.setToolTip("Hotspot threshold temperature")
        hm.addWidget(self._hot_spin)

        hm.addStretch()

        self._heatmap_row.setVisible(False)
        root_layout.addWidget(self._heatmap_row)

        # Add root to toolbar
        self.addWidget(root)

        # -- Wire all signals -------------------------------------------------
        self._dx_spin.valueChanged.connect(
            lambda v: self.dx_changed.emit(v / 100.0)  # cm -> m
        )
        self._hm_min.valueChanged.connect(self._emit_hm_range)
        self._hm_max.valueChanged.connect(self._emit_hm_range)
        self._palette_combo.currentTextChanged.connect(self.palette_changed)
        self._iso_check.toggled.connect(self._emit_isotherm)
        self._iso_spin.valueChanged.connect(self._emit_isotherm)
        self._hot_check.toggled.connect(self._emit_hotspot)
        self._hot_spin.valueChanged.connect(self._emit_hotspot)
        btn_fit.clicked.connect(self.fit_view_requested)
        self._btn_gridlines.toggled.connect(self.grid_lines_toggled)
        self._btn_abbr.toggled.connect(self.abbr_toggled)
        self._btn_label.toggled.connect(self.label_toggled)
        self._btn_vectors.toggled.connect(self.heat_vectors_toggled)

    # -- Public API -----------------------------------------------------------

    def activate_draw_mode(self) -> None:
        """Switch to draw mode (keyboard shortcut D)."""
        self._btn_draw.setChecked(True)

    def activate_select_mode(self) -> None:
        """Switch to select mode (keyboard shortcut S)."""
        self._btn_select.setChecked(True)

    def activate_fill_mode(self) -> None:
        """Switch to fill mode (keyboard shortcut W)."""
        self._btn_fill.setChecked(True)

    def activate_heatmap_mode(self) -> None:
        """Switch to heatmap view (keyboard shortcut H)."""
        self._btn_heatmap.setChecked(True)

    def activate_material_mode(self) -> None:
        """Switch to material view (keyboard shortcut M)."""
        self._btn_material.setChecked(True)

    def set_boundary_conditions(self, bc: dict) -> None:
        """Restore BC button states from a dict, emitting one signal at the end."""
        for key, btn in self._border_btns.items():
            btn.blockSignals(True)
            is_sink = bc.get(key, "insulator") == "sink"
            btn.setChecked(is_sink)
            label = self._border_labels[key]
            btn.setText(f"{label}: {'Fixed T' if is_sink else 'Insulated'}")
            btn.blockSignals(False)
        self.boundary_conditions_changed.emit(bc)

    def set_dx(self, dx_m: float) -> None:
        """Update the cell-size spinbox without emitting dx_changed. dx_m is in metres."""
        self._dx_spin.blockSignals(True)
        self._dx_spin.setValue(dx_m * 100.0)  # m -> cm
        self._dx_spin.blockSignals(False)

    def toggle_grid_lines(self) -> None:
        """Toggle grid-lines visibility (keyboard shortcut G)."""
        self._btn_gridlines.toggle()

    def refresh_units(self) -> None:
        """Refresh heatmap spinbox suffixes and values to the current display unit."""
        suf    = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        for spin, k_val in [(self._hm_min, self._hm_min_k), (self._hm_max, self._hm_max_k)]:
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            spin.setValue(_units.to_display(k_val))
            spin.blockSignals(False)
        self._iso_spin.blockSignals(True)
        self._iso_spin.setSuffix(suf)
        self._iso_spin.setValue(delta_k_to_display(self._isotherm_interval_k))
        self._iso_spin.blockSignals(False)
        self._hot_spin.blockSignals(True)
        self._hot_spin.setSuffix(suf)
        self._hot_spin.setRange(lo, hi)
        self._hot_spin.setValue(_units.to_display(self._hotspot_threshold_k))
        self._hot_spin.blockSignals(False)

    # -- Internal -------------------------------------------------------------

    @staticmethod
    def _add_sep(layout: QHBoxLayout) -> None:
        """Add a thin vertical separator line to the given layout."""
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #444; margin: 4px 3px;")
        layout.addWidget(sep)

    def activate_flow_mode(self) -> None:
        """Switch to heat flow view."""
        self._btn_flux.setChecked(True)

    def _set_view(self, mode: str) -> None:
        self._heatmap_row.setVisible(mode in ("heatmap", "flow"))
        self.view_mode_changed.emit(mode)

    def set_auto_init(self, auto: bool) -> None:
        """Called from preferences to sync the auto-init state."""
        self.heatmap_auto_changed.emit(auto)

    def set_scale_mode(self, mode: str) -> None:
        """Called from preferences to sync the scale mode."""
        self.heatmap_scale_mode_changed.emit(mode)

    def _emit_hm_range(self) -> None:
        lo = _units.from_display(self._hm_min.value())
        hi = _units.from_display(self._hm_max.value())
        if lo >= hi:
            return
        self._hm_min_k = lo
        self._hm_max_k = hi
        self.heatmap_range_changed.emit(self._hm_min_k, self._hm_max_k)

    def _emit_isotherm(self) -> None:
        self._isotherm_interval_k = max(0.01, delta_display_to_k(self._iso_spin.value()))
        self.isotherm_changed.emit(self._iso_check.isChecked(), self._isotherm_interval_k)

    def _emit_hotspot(self) -> None:
        self._hotspot_threshold_k = _units.from_display(self._hot_spin.value())
        val = self._hotspot_threshold_k if self._hot_check.isChecked() else float("nan")
        self.hotspot_threshold_changed.emit(val)

    def _on_border_toggled(self, key: str, checked: bool) -> None:
        display = self._border_labels[key]
        self._border_btns[key].setText(f"{display}: {'Fixed T' if checked else 'Insulated'}")
        bc = {k: "sink" if btn.isChecked() else "insulator" for k, btn in self._border_btns.items()}
        self.boundary_conditions_changed.emit(bc)
