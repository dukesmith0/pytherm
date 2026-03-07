from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
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
from src.rendering.units import TempSpinBox


class BottomBar(QToolBar):
    """Bottom toolbar -- simulation playback controls and time display.

    All content lives in a horizontally-scrollable inner widget so that items
    are never hidden when the window is narrow.
    """

    play_pause_toggled  = pyqtSignal(bool)   # True = play, False = pause
    reset_requested     = pyqtSignal()
    step_requested      = pyqtSignal(float)  # simulated seconds to advance
    steady_mode_changed = pyqtSignal(bool)   # True = stop at steady state
    speed_changed       = pyqtSignal(float)  # new speed multiplier
    unit_changed        = pyqtSignal(str)    # "\u00b0C" | "K" | "\u00b0F"
    ambient_changed     = pyqtSignal(float)  # new ambient temperature in Kelvin

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMovable(False)

        self._content = QWidget()
        self._layout = QHBoxLayout(self._content)
        self._layout.setContentsMargins(2, 0, 2, 0)
        self._layout.setSpacing(2)

        # -- Simulation controls ----------------------------------------------
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

        # -- Speed ------------------------------------------------------------
        speed_lbl = QLabel("Speed:")
        speed_lbl.setStyleSheet("padding: 0 4px;")
        self._layout.addWidget(speed_lbl)

        self._speed_combo = QComboBox()
        self._speed_combo.setFixedWidth(82)
        self._speed_combo.setToolTip("Simulation speed multiplier relative to real time")
        for label, val in [
            ("1\u00d7",      1.0),
            ("2\u00d7",      2.0),
            ("5\u00d7",      5.0),
            ("10\u00d7",     10.0),
            ("100\u00d7",    100.0),
            ("1 000\u00d7",  1_000.0),
            ("10 000\u00d7", 10_000.0),
        ]:
            self._speed_combo.addItem(label, val)
        self._layout.addWidget(self._speed_combo)

        self._add_sep()

        self._btn_step = QPushButton("Step")
        self._btn_step.setFixedWidth(52)
        self._btn_step.setToolTip("Advance the simulation by the step duration (disabled while running)")
        self._layout.addWidget(self._btn_step)

        self._step_spin = QDoubleSpinBox()
        self._step_spin.setRange(0.001, 3600.0)
        self._step_spin.setDecimals(3)
        self._step_spin.setValue(1.0)
        self._step_spin.setSuffix(" s")
        self._step_spin.setFixedWidth(80)
        self._step_spin.setToolTip("Simulated duration of a single step (seconds)")
        self._layout.addWidget(self._step_spin)

        self._chk_steady = QCheckBox("Stop at SS")
        self._chk_steady.setToolTip(
            "Run until steady state \u2014 pauses automatically when max \u0394T rate < 0.01 K/s"
        )
        self._layout.addWidget(self._chk_steady)

        self._add_sep()

        self._time_label = QLabel("0:00:00.000")
        self._time_label.setStyleSheet("padding: 0 8px; color: #aaa;")
        self._layout.addWidget(self._time_label)

        self._substep_label = QLabel("")
        self._substep_label.setStyleSheet("padding: 0 4px; color: #666; font-size: 11px;")
        self._layout.addWidget(self._substep_label)

        self._energy_label = QLabel("")
        self._energy_label.setStyleSheet("padding: 0 8px; color: #aaa; font-size: 11px;")
        self._energy_label.setToolTip(
            "E: current stored energy above ambient\n"
            "ref: E_start + energy in from fixed cells + energy in from sinks\n"
            "err: conservation error (E \u2212 ref); should be near zero"
        )
        self._layout.addWidget(self._energy_label)

        self._power_label = QLabel("")
        self._power_label.setStyleSheet("padding: 0 8px; color: #aaa; font-size: 11px;")
        self._power_label.setToolTip(
            "Total heat injection rate from fixed-T and heat-flux cells (W per metre depth)"
        )
        self._layout.addWidget(self._power_label)

        self._layout.addStretch()

        # -- Ambient temperature (right-anchored) -----------------------------
        self._add_sep()

        amb_lbl = QLabel("Amb:")
        amb_lbl.setStyleSheet("padding: 0 2px; color: #aaa;")
        self._layout.addWidget(amb_lbl)

        self._ambient_k: float = 293.15
        lo, hi = _units.spinbox_range()
        self._amb_spin = TempSpinBox()
        self._amb_spin.setRange(lo, hi)
        self._amb_spin.setValue(_units.to_display(self._ambient_k))
        self._amb_spin.setSuffix(f" {_units.suffix()}")
        self._amb_spin.setFixedWidth(100)
        self._amb_spin.setToolTip("Ambient temperature \u2014 used as reset reference and for sink boundary conditions")
        self._layout.addWidget(self._amb_spin)

        # -- Unit toggle (right-anchored) -------------------------------------
        self._add_sep()

        unit_lbl = QLabel("Unit:")
        unit_lbl.setStyleSheet("padding: 0 2px; color: #aaa;")
        self._layout.addWidget(unit_lbl)

        self._unit_combo = QComboBox()
        self._unit_combo.setFixedWidth(58)
        self._unit_combo.setToolTip("Temperature display unit \u2014 applies to all spinboxes and the heatmap labels")
        for u in ("\u00b0C", "K", "\u00b0F", "R"):
            self._unit_combo.addItem(u)
        self._layout.addWidget(self._unit_combo)

        # -- Wrap content in a horizontal scroll area -------------------------
        scroll = QScrollArea()
        scroll.setWidget(self._content)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setFixedHeight(38)
        self.addWidget(scroll)

        # -- Wire all signals -------------------------------------------------
        self._btn_play.toggled.connect(self.play_pause_toggled)
        self._btn_reset.clicked.connect(self.reset_requested)
        self._btn_step.clicked.connect(lambda: self.step_requested.emit(self._step_spin.value()))
        self._chk_steady.toggled.connect(self.steady_mode_changed)
        self._speed_combo.currentIndexChanged.connect(
            lambda i: self.speed_changed.emit(self._speed_combo.itemData(i))
        )
        self._unit_combo.currentTextChanged.connect(self.unit_changed)
        self._amb_spin.valueChanged.connect(self._on_ambient_spin_changed)

    # -- Public API -----------------------------------------------------------

    def toggle_play_pause(self) -> None:
        """Toggle the play/pause button (keyboard shortcut Space)."""
        self._btn_play.toggle()

    def trigger_reset(self) -> None:
        """Emit reset_requested (keyboard shortcut R)."""
        self.reset_requested.emit()

    def trigger_step(self) -> None:
        """Emit step_requested if the step button is enabled (keyboard shortcut N)."""
        if self._btn_step.isEnabled():
            self.step_requested.emit(self._step_spin.value())

    def cycle_unit(self) -> None:
        """Cycle to the next temperature unit (Ctrl+U)."""
        n = self._unit_combo.count()
        self._unit_combo.setCurrentIndex((self._unit_combo.currentIndex() + 1) % n)

    def set_unit_value(self, unit_str: str) -> None:
        """Set the unit combo (fires unit_changed signal)."""
        self._unit_combo.setCurrentText(unit_str)

    def set_speed_value(self, v: float) -> None:
        """Set the speed combo to the closest matching option without emitting speed_changed."""
        best = min(range(self._speed_combo.count()),
                   key=lambda i: abs(self._speed_combo.itemData(i) - v))
        self._speed_combo.blockSignals(True)
        self._speed_combo.setCurrentIndex(best)
        self._speed_combo.blockSignals(False)

    def set_ambient(self, k_val: float) -> None:
        """Set the ambient spinbox without emitting ambient_changed."""
        self._ambient_k = k_val
        self._amb_spin.blockSignals(True)
        self._amb_spin.setValue(_units.to_display(k_val))
        self._amb_spin.blockSignals(False)

    def refresh_units(self) -> None:
        """Refresh ambient spinbox suffix, range, and value for the current display unit."""
        lo, hi = _units.spinbox_range()
        self._amb_spin.blockSignals(True)
        self._amb_spin.setSuffix(f" {_units.suffix()}")
        self._amb_spin.setRange(lo, hi)
        self._amb_spin.setValue(_units.to_display(self._ambient_k))
        self._amb_spin.blockSignals(False)

    def set_running(self, running: bool) -> None:
        """Sync the play/pause button without re-emitting play_pause_toggled."""
        self._btn_play.blockSignals(True)
        self._btn_play.setChecked(running)
        self._btn_play.setText("\u2016  Pause" if running else "\u25b6  Play")
        self._btn_play.blockSignals(False)
        self._btn_step.setEnabled(not running)
        self._amb_spin.setEnabled(not running)

    def update_sim_time(self, t: float) -> None:
        h  = int(t // 3600)
        m  = int((t % 3600) // 60)
        s  = int(t % 60)
        ms = int((t % 1) * 1000)
        self._time_label.setText(f"{h}:{m:02d}:{s:02d}.{ms:03d}")

    def update_substep_count(self, n: int) -> None:
        """Update the sub-step count display next to the sim-time."""
        self._substep_label.setText(f"[{n} sub]")

    def update_energy(self, e_now: float, e_ref: float) -> None:
        """Update the energy conservation display."""
        err = e_now - e_ref
        self._energy_label.setText(
            f"E: {_units.fmt_energy(e_now)}  "
            f"ref: {_units.fmt_energy(e_ref)}  "
            f"err: {_units.fmt_energy(err)}"
        )

    def update_power(self, power_wpm: float) -> None:
        """Update the total heat injection display (W/m depth)."""
        if power_wpm == 0.0:
            self._power_label.setText("")
            return
        if abs(power_wpm) >= 1000.0:
            self._power_label.setText(f"Inj: {power_wpm / 1000:.3g} kW/m")
        else:
            self._power_label.setText(f"Inj: {power_wpm:.3g} W/m")

    # -- Internal -------------------------------------------------------------

    def _on_ambient_spin_changed(self, _val: float) -> None:
        k = _units.from_display(self._amb_spin.value())
        self._ambient_k = k
        self.ambient_changed.emit(k)

    def _add_sep(self) -> None:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setFixedWidth(1)
        sep.setStyleSheet("background: #444; margin: 4px 3px;")
        self._layout.addWidget(sep)
