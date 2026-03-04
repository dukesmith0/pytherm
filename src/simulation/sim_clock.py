from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.simulation.grid import Grid
from src.simulation.solver import Solver
from src.ui.grid_scene import GridScene


class SimClock(QObject):
    """Drives the simulation loop at ~30 FPS and manages play/pause/reset state.

    On each timer tick:
      1. Compute simulated dt = wall_dt × speed_multiplier
      2. Export temperature array from Grid
      3. Call Solver.advance() — internally sub-stepped for CFL stability
      4. Import updated temperatures back into Grid
      5. Refresh the scene
      6. Emit tick(total_sim_time)
    """

    tick = pyqtSignal(float)          # total simulated time in seconds
    state_changed = pyqtSignal(bool)  # True = running, False = stopped
    nan_detected = pyqtSignal()       # emitted when NaN/Inf appears in temperature field

    INTERVAL_MS = 33  # ~30 FPS wall-clock update rate

    def __init__(self, grid: Grid, solver: Solver, scene: GridScene, parent=None) -> None:
        super().__init__(parent)
        self._grid = grid
        self._solver = solver
        self._scene = scene
        self._sim_time = 0.0
        self._speed = 1.0
        self._running = False

        self._timer = QTimer(self)
        self._timer.setInterval(self.INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

    # --- Properties ---

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def sim_time(self) -> float:
        return self._sim_time

    # --- Public API ---

    def set_speed(self, multiplier: float) -> None:
        self._speed = multiplier

    def play(self) -> None:
        if not self._running:
            self._running = True
            self._timer.start()
            self.state_changed.emit(True)

    def pause(self) -> None:
        if self._running:
            self._running = False
            self._timer.stop()
            self.state_changed.emit(False)

    def set_grid(self, grid: Grid) -> None:
        """Replace the grid (called when user creates a new simulation)."""
        self._grid = grid

    def reset(self) -> None:
        if self._running:
            self._running = False
            self._timer.stop()
            self.state_changed.emit(False)
        self._sim_time = 0.0
        self._grid.reset_temperatures()
        self._scene.reset_auto_heatmap_bounds()
        self._scene.refresh()
        self.tick.emit(0.0)

    def step(self, duration: float) -> None:
        """Advance the simulation by a fixed duration while paused."""
        if self._running:
            return
        self._advance(duration)
        self.tick.emit(self._sim_time)

    # --- Internal ---

    def _on_tick(self) -> None:
        dt_sim = (self.INTERVAL_MS / 1000.0) * self._speed
        self._advance(dt_sim)
        self.tick.emit(self._sim_time)

    def _advance(self, dt_sim: float) -> None:
        self._solver.ambient_k = self._grid.ambient_temp_k  # sync for sink BCs
        T = self._grid.temperature_array()
        k = self._grid.k_array()
        rho_cp = self._grid.rho_cp_array()
        fixed_mask = self._grid.fixed_mask()
        fixed_temps = self._grid.fixed_temps_array()
        T_new = self._solver.advance(T, k, rho_cp, fixed_mask, fixed_temps, duration=dt_sim)

        if np.any(np.isnan(T_new) | np.isinf(T_new)):
            self.pause()
            self.nan_detected.emit()
            return

        self._grid.import_temperatures(T_new)
        self._sim_time += dt_sim
        self._scene.refresh()
