"""Tests for src.simulation.thermal_resistance.compute_rth."""
from __future__ import annotations

from src.simulation.thermal_resistance import compute_rth


def test_1d_conduction_bar(make_grid):
    from src.simulation.grid import Grid
    from src.models.material_registry import MaterialRegistry
    from pathlib import Path
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    cu = reg.get("cu")
    grid = Grid(1, 5, cu, ambient_temp_k=293.15)
    dx = 0.01
    grid.set_cell(0, 0, material=cu, temperature=400.0, is_fixed=True, fixed_temp=400.0)
    grid.set_cell(0, 4, material=cu, temperature=300.0, is_fixed=True, fixed_temp=300.0)
    for c in range(1, 4):
        t = 400.0 - (100.0 / 4) * c
        grid.set_cell(0, c, material=cu, temperature=t)
    result = compute_rth(grid, source_cells=[(0, 0)], sink_cells=[(0, 4)], dx=dx, k_array=grid.k_array())
    assert result.dt_k == 100.0
    assert result.q_wpm > 0
    assert result.rth_kpwpm > 0
    assert result.n_source == 1
    assert result.n_sink == 1


def test_zero_heat_flow(make_grid):
    grid, _ = make_grid(2, 2)
    result = compute_rth(grid, source_cells=[(0, 0)], sink_cells=[(1, 1)], dx=0.01, k_array=grid.k_array())
    assert result.rth_kpwpm == float("inf") or abs(result.q_wpm) < 1e-10
