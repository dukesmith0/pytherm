from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QLabel, QPushButton, QSpinBox, QVBoxLayout, QWidget,
)

from src.models.preferences import Preferences
from src.rendering.units import KelvinSpinBox


# Speed options must match BottomBar._speed_combo options.
_SPEED_OPTIONS: list[tuple[str, float]] = [
    ("1\u00d7",       1.0),
    ("10\u00d7",      10.0),
    ("100\u00d7",     100.0),
    ("1\u202f000\u00d7",  1_000.0),
]


class PreferencesDialog(QDialog):
    def __init__(self, prefs: Preferences, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        self.setFixedWidth(320)

        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        def _section(title: str) -> None:
            lbl = QLabel(f"  {title}")
            lbl.setStyleSheet("font-weight: bold; color: #999; font-size: 10px; padding-top: 6px;")
            form.addRow(lbl)

        _section("Appearance")

        self._theme = QComboBox()
        self._theme.addItem("Dark", "dark")
        self._theme.addItem("Light", "light")
        self._theme.setCurrentIndex(0 if prefs.theme == "dark" else 1)
        self._theme.setToolTip("Application color theme (takes effect immediately)")
        form.addRow("Theme:", self._theme)

        self._unit = QComboBox()
        for u in ("\u00b0C", "K", "\u00b0F", "R"):
            self._unit.addItem(u)
        self._unit.setCurrentText(prefs.unit)
        form.addRow("Default unit:", self._unit)

        _section("Grid Defaults")

        self._ambient = KelvinSpinBox()
        self._ambient.setRange(0.0, 10_000.0)
        self._ambient.setDecimals(2)
        self._ambient.setSuffix(" K")
        self._ambient.setValue(prefs.ambient_temp_k)
        self._ambient.setToolTip("Default ambient temperature. Type a value with suffix (e.g. 20C, 293K, 68F) to auto-convert.")
        form.addRow("Default ambient:", self._ambient)

        self._rows = QSpinBox()
        self._rows.setRange(1, 200)
        self._rows.setValue(prefs.default_rows)
        form.addRow("Default rows:", self._rows)

        self._cols = QSpinBox()
        self._cols.setRange(1, 200)
        self._cols.setValue(prefs.default_cols)
        form.addRow("Default columns:", self._cols)

        self._dx = QDoubleSpinBox()
        self._dx.setRange(0.01, 100.0)
        self._dx.setDecimals(2)
        self._dx.setSuffix(" cm")
        self._dx.setValue(prefs.default_dx_m * 100.0)
        form.addRow("Default cell size:", self._dx)

        _section("Simulation")

        self._speed = QComboBox()
        for label, val in _SPEED_OPTIONS:
            self._speed.addItem(label, val)
        # Select closest match
        best = min(range(len(_SPEED_OPTIONS)), key=lambda i: abs(_SPEED_OPTIONS[i][1] - prefs.sim_speed))
        self._speed.setCurrentIndex(best)
        form.addRow("Default sim speed:", self._speed)

        self._max_undo = QSpinBox()
        self._max_undo.setRange(1, 500)
        self._max_undo.setValue(prefs.max_undo_steps)
        form.addRow("Max undo steps:", self._max_undo)

        self._max_plot = QSpinBox()
        self._max_plot.setRange(50, 5000)
        self._max_plot.setValue(prefs.max_plot_points)
        form.addRow("Max plot points:", self._max_plot)

        self._ss_threshold = QDoubleSpinBox()
        self._ss_threshold.setRange(0.0001, 100.0)
        self._ss_threshold.setDecimals(4)
        self._ss_threshold.setSuffix(" K/s")
        self._ss_threshold.setValue(prefs.ss_threshold_k_per_s)
        form.addRow("SS threshold:", self._ss_threshold)

        _section("Display")

        self._min_auto_range = QDoubleSpinBox()
        self._min_auto_range.setRange(0.1, 10_000.0)
        self._min_auto_range.setDecimals(1)
        self._min_auto_range.setSuffix(" °C / K")
        self._min_auto_range.setValue(prefs.min_auto_heatmap_range_k)
        self._min_auto_range.setToolTip(
            "Minimum temperature span for the auto heatmap scale.\n"
            "Prevents the gradient from over-saturating on near-isothermal grids."
        )
        form.addRow("Min auto heatmap range:", self._min_auto_range)

        self._hm_auto_init = QCheckBox()
        self._hm_auto_init.setChecked(prefs.heatmap_auto_init)
        self._hm_auto_init.setToolTip(
            "Auto: initialize bounds from grid min/max at sim start\n"
            "Manual: use the toolbar min/max spinbox values"
        )
        form.addRow("Auto init bounds:", self._hm_auto_init)

        self._hm_scale_mode = QComboBox()
        self._hm_scale_mode.addItem("Static", "static")
        self._hm_scale_mode.addItem("Live", "live")
        self._hm_scale_mode.addItem("Smart", "smart")
        idx = {"static": 0, "live": 1, "smart": 2}.get(prefs.heatmap_scale_mode, 2)
        self._hm_scale_mode.setCurrentIndex(idx)
        self._hm_scale_mode.setToolTip(
            "Static: bounds stay fixed at starting values\n"
            "Live: bounds track current grid min/max every frame\n"
            "Smart: bounds only expand (min can decrease, max can increase)"
        )
        form.addRow("Scale mode:", self._hm_scale_mode)

        self._reverse_palette = QCheckBox()
        self._reverse_palette.setChecked(prefs.reverse_palette)
        self._reverse_palette.setToolTip("Flip the color palette so hot maps to blue and cold to red")
        form.addRow("Reverse palette:", self._reverse_palette)

        self._smooth_step = QCheckBox()
        self._smooth_step.setChecked(prefs.smooth_step)
        self._smooth_step.setToolTip(
            "When enabled, Step animates at max CFL rate\n"
            "instead of jumping to the final state."
        )
        form.addRow("Animate step:", self._smooth_step)

        self._step_history = QSpinBox()
        self._step_history.setRange(5, 200)
        self._step_history.setValue(prefs.step_history_size)
        self._step_history.setToolTip("Number of temperature snapshots kept for step history navigation")
        form.addRow("Step history size:", self._step_history)

        _section("Overlays")
        self._iso_color = QColor(prefs.isotherm_color)
        self._iso_color_btn = QPushButton()
        self._iso_color_btn.setFixedWidth(60)
        self._iso_color_btn.setFixedHeight(24)
        self._update_color_btn()
        self._iso_color_btn.setToolTip("Color for isotherm contour lines")
        self._iso_color_btn.clicked.connect(self._pick_isotherm_color)
        form.addRow("Isotherm color:", self._iso_color_btn)

        self._iso_width = QSpinBox()
        self._iso_width.setRange(1, 5)
        self._iso_width.setValue(prefs.isotherm_line_width)
        self._iso_width.setToolTip("Line width for isotherm contour lines (px)")
        form.addRow("Isotherm line width:", self._iso_width)

        _section("Data")
        self._plot_step = QSpinBox()
        self._plot_step.setRange(1, 100)
        self._plot_step.setValue(prefs.plot_every_n_ticks)
        self._plot_step.setToolTip(
            "Record a plot data point every Nth simulation tick.\n"
            "1 = every tick (highest fidelity), higher = less data."
        )
        form.addRow("Plot every N ticks:", self._plot_step)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(btns)

    def _update_color_btn(self) -> None:
        self._iso_color_btn.setStyleSheet(
            f"background-color: {self._iso_color.name()}; border: 1px solid #555;"
        )

    def _pick_isotherm_color(self, _checked: bool = False) -> None:
        color = QColorDialog.getColor(self._iso_color, self, "Isotherm Color")
        if color.isValid():
            self._iso_color = color
            self._update_color_btn()

    def updated_prefs(self) -> Preferences:
        return Preferences(
            unit=self._unit.currentText(),
            ambient_temp_k=self._ambient.value(),
            default_rows=self._rows.value(),
            default_cols=self._cols.value(),
            default_dx_m=self._dx.value() / 100.0,
            sim_speed=self._speed.currentData(),
            max_undo_steps=self._max_undo.value(),
            max_plot_points=self._max_plot.value(),
            ss_threshold_k_per_s=self._ss_threshold.value(),
            min_auto_heatmap_range_k=self._min_auto_range.value(),
            heatmap_auto_init=self._hm_auto_init.isChecked(),
            heatmap_scale_mode=self._hm_scale_mode.currentData(),
            smooth_step=self._smooth_step.isChecked(),
            step_history_size=self._step_history.value(),
            isotherm_color=self._iso_color.name(),
            isotherm_line_width=self._iso_width.value(),
            reverse_palette=self._reverse_palette.isChecked(),
            plot_every_n_ticks=self._plot_step.value(),
            theme=self._theme.currentData(),
        )
