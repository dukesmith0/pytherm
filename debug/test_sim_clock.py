"""Tests for src.simulation.sim_clock.SimClock."""
from __future__ import annotations

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"


def _make_clock(flux_q=0.0):
    from src.simulation.grid import Grid
    from src.simulation.solver import Solver
    from src.simulation.sim_clock import SimClock
    from src.models.material_registry import MaterialRegistry
    from src.ui.grid_scene import GridScene
    reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
    al = reg.get("al6061")
    grid = Grid(4, 4, al, ambient_temp_k=293.15)
    if flux_q:
        grid.set_cell(1, 1, is_flux=True, flux_q=flux_q)
    scene = GridScene(grid)
    solver = Solver(dx=0.01)
    clock = SimClock(grid, solver, scene)
    clock.reset()
    return clock, grid


def test_e_cumulative_flux_grows():
    clock, _ = _make_clock(flux_q=5000.0)
    clock.step(duration=0.01)
    assert clock.e_cumulative_flux > 0.0
    assert clock.last_dt_sim > 0.0


def test_recalculate_energy_clears():
    clock, grid = _make_clock(flux_q=5000.0)
    clock.step(duration=0.1)
    assert clock.e_cumulative_flux > 0.0
    grid.ambient_temp_k = 300.0
    clock.recalculate_energy_reference()
    assert clock.e_cumulative_flux == 0.0
    assert clock.e_cumulative_fixed == 0.0
    assert clock.e_cumulative_sinks == 0.0


def test_step_advances_sim_time():
    clock, _ = _make_clock()
    clock.step(duration=2.5)
    assert abs(clock.sim_time - 2.5) < 1e-9


def test_smooth_step_default():
    clock, _ = _make_clock()
    assert clock._smooth_step is False


def test_set_smooth_step():
    clock, _ = _make_clock()
    clock.set_smooth_step(True)
    assert clock._smooth_step is True
