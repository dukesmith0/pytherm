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
      3. Call Solver.advance() -- internally sub-stepped for CFL stability
      4. Import updated temperatures back into Grid
      5. Refresh the scene
      6. Emit tick(total_sim_time)
    """

    tick = pyqtSignal(float)             # total simulated time in seconds
    state_changed = pyqtSignal(bool)     # True = running, False = stopped
    nan_detected = pyqtSignal()          # emitted when NaN/Inf appears in temperature field
    steady_state_reached = pyqtSignal()  # emitted when convergence threshold is met

    INTERVAL_MS = 33  # ~30 FPS wall-clock update rate

    def __init__(self, grid: Grid, solver: Solver, scene: GridScene, parent=None) -> None:
        super().__init__(parent)
        self._grid = grid
        self._solver = solver
        self._scene = scene
        self._sim_time = 0.0
        self._speed = 1.0
        self._running = False
        self._steady_mode = False
        self._e_start = 0.0             # thermal energy at last reset [J/m]
        self._e_cumulative_fixed = 0.0  # total energy from fixed-T cells since reset [J/m]
        self._e_cumulative_sinks = 0.0  # total energy from sink BCs since reset [J/m]
        self._e_cumulative_flux = 0.0   # total energy from heat-flux cells since reset [J/m]
        self.last_dt_sim: float = 0.0   # simulated seconds of the last _advance() call
        self._arr_cache: dict | None = None  # cached material arrays (valid while running)
        self.ss_threshold: float = 0.01  # K/s convergence threshold for steady-state check

        self._smooth_step = False
        self._step_remaining: float = 0.0  # remaining duration for animated step

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

    @property
    def e_start(self) -> float:
        return self._e_start

    @property
    def e_cumulative_fixed(self) -> float:
        return self._e_cumulative_fixed

    @property
    def e_cumulative_sinks(self) -> float:
        return self._e_cumulative_sinks

    @property
    def e_cumulative_flux(self) -> float:
        return self._e_cumulative_flux

    # --- Public API ---

    def set_speed(self, multiplier: float) -> None:
        self._speed = multiplier

    def set_steady_mode(self, enabled: bool) -> None:
        self._steady_mode = enabled

    def set_smooth_step(self, enabled: bool) -> None:
        self._smooth_step = enabled

    def play(self) -> None:
        if not self._running:
            self._running = True
            self._timer.start()
            self.state_changed.emit(True)

    def pause(self) -> None:
        if self._running:
            self._running = False
            self._timer.stop()
            self._arr_cache = None
            self.state_changed.emit(False)

    def set_grid(self, grid: Grid) -> None:
        """Replace the grid (called when user creates a new simulation)."""
        self._grid = grid
        self._arr_cache = None

    def invalidate_arrays(self) -> None:
        """Clear the cached material arrays. Call after any grid structure change while paused."""
        self._arr_cache = None

    def recalculate_energy_reference(self) -> None:
        """Recalculate the energy baseline after an ambient temperature change.

        Resets e_start to the current field relative to the new ambient, and clears
        the cumulative energy accumulators so the conservation display stays meaningful.
        """
        T = self._grid.temperature_array()
        rho_cp = self._grid.rho_cp_array()
        dx2 = self._solver.dx ** 2
        self._e_start = float(np.dot(rho_cp.ravel(), (T - self._grid.ambient_temp_k).ravel())) * dx2
        self._e_cumulative_fixed = 0.0
        self._e_cumulative_sinks = 0.0
        self._e_cumulative_flux = 0.0

    def reset(self) -> None:
        if self._running:
            self._running = False
            self._timer.stop()
            self.state_changed.emit(False)
        self._arr_cache = None
        self._sim_time = 0.0
        self._grid.reset_temperatures()
        T = self._grid.temperature_array()
        rho_cp = self._grid.rho_cp_array()
        dx2 = self._solver.dx ** 2
        self._e_start = float(np.dot(rho_cp.ravel(), (T - self._grid.ambient_temp_k).ravel())) * dx2
        self._e_cumulative_fixed = 0.0
        self._e_cumulative_sinks = 0.0
        self._e_cumulative_flux = 0.0
        self._scene.reset_auto_heatmap_bounds()
        self._scene.refresh()
        self.tick.emit(0.0)

    def step(self, duration: float) -> None:
        """Advance the simulation by a fixed duration while paused.

        If smooth_step is enabled, starts an animated playback that auto-pauses
        after the requested duration elapses.
        """
        if self._running:
            return
        if self._smooth_step:
            self._step_remaining = duration
            self._running = True
            self._timer.start()
            self.state_changed.emit(True)
        else:
            self._advance(duration)
            self.tick.emit(self._sim_time)

    # --- Internal ---

    def _on_tick(self) -> None:
        dt_sim = (self.INTERVAL_MS / 1000.0) * self._speed
        stepping = self._step_remaining > 0
        if stepping:
            dt_sim = min(dt_sim, self._step_remaining)
            self._step_remaining -= dt_sim
        self._advance(dt_sim)
        self.tick.emit(self._sim_time)
        if stepping and self._step_remaining <= 0:
            self._step_remaining = 0.0
            self.pause()

    def _advance(self, dt_sim: float) -> None:
        is_first_tick = (self._sim_time == 0.0)  # skip SS check on tick 1 (all-ambient start)
        self._solver.ambient_k = self._grid.ambient_temp_k  # sync for sink BCs
        T = self._grid.temperature_array()
        if self._arr_cache is None:
            self._arr_cache = {
                "k":           self._grid.k_array(),
                "rho_cp":      self._grid.rho_cp_array(),
                "fixed_mask":  self._grid.fixed_mask(),
                "fixed_temps": self._grid.fixed_temps_array(),
                "flux_mask":   self._grid.flux_mask(),
                "flux_q":      self._grid.flux_q_array(),
                "vol_flux":    self._grid.volumetric_flux_mask(),
            }
        k           = self._arr_cache["k"]
        rho_cp      = self._arr_cache["rho_cp"]
        fixed_mask  = self._arr_cache["fixed_mask"]
        fixed_temps = self._arr_cache["fixed_temps"]
        flux_mask   = self._arr_cache["flux_mask"]
        flux_q      = self._arr_cache["flux_q"]
        vol_flux    = self._arr_cache["vol_flux"]
        T_new = self._solver.advance(T, k, rho_cp, fixed_mask, fixed_temps, flux_mask, flux_q,
                                     duration=dt_sim, vol_flux_mask=vol_flux)

        if np.any(np.isnan(T_new) | np.isinf(T_new)):
            self.pause()
            self.nan_detected.emit()
            return

        self._e_cumulative_fixed += self._solver.last_e_from_fixed
        self._e_cumulative_sinks += self._solver.last_e_from_sinks
        self._e_cumulative_flux  += self._solver.last_e_from_flux
        self.last_dt_sim = dt_sim
        self._grid.import_temperatures(T_new)
        self._sim_time += dt_sim
        self._scene.refresh()

        if self._steady_mode and not is_first_tick:
            if "active" not in self._arr_cache:
                self._arr_cache["active"] = (rho_cp > 0) & ~fixed_mask
            active = self._arr_cache["active"]
            if np.any(active):
                substep_dt = self._solver.last_substep_dt
                delta_rate = self._solver.last_substep_delta / substep_dt if substep_dt > 0 else 0.0
                if delta_rate < self.ss_threshold:
                    self.pause()
                    self.steady_state_reached.emit()
