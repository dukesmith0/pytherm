"""Tests for src.simulation.grid.Grid."""
from __future__ import annotations

import numpy as np


def test_set_cell_flux(make_grid):
    grid, _ = make_grid()
    grid.set_cell(0, 0, is_flux=True, flux_q=1000.0)
    c = grid.cell(0, 0)
    assert c.is_flux is True and c.flux_q == 1000.0


def test_flux_mask(make_grid):
    grid, _ = make_grid()
    grid.set_cell(1, 2, is_flux=True, flux_q=500.0)
    mask = grid.flux_mask()
    assert mask.shape == (4, 4)
    assert bool(mask[1, 2]) is True and mask.sum() == 1


def test_flux_q_array(make_grid):
    grid, _ = make_grid()
    grid.set_cell(0, 1, is_flux=True, flux_q=750.0)
    grid.set_cell(2, 3, is_flux=True, flux_q=250.0)
    arr = grid.flux_q_array()
    assert abs(arr[0, 1] - 750.0) < 1e-9 and abs(arr[2, 3] - 250.0) < 1e-9 and arr[0, 0] == 0.0


def test_snapshot_restore_flux(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=400.0, is_flux=True, flux_q=1500.0)
    snap = grid.snapshot()
    grid.set_cell(0, 0, is_flux=False, flux_q=0.0)
    grid.restore(snap)
    c = grid.cell(0, 0)
    assert c.is_flux is True and abs(c.flux_q - 1500.0) < 1e-9


def test_flux_and_fixed_independent(make_grid):
    grid, _ = make_grid()
    grid.set_cell(1, 1, is_fixed=True, fixed_temp=350.0)
    grid.set_cell(1, 1, is_flux=True, is_fixed=False, flux_q=200.0)
    c = grid.cell(1, 1)
    assert c.is_flux is True and c.is_fixed is False


def test_paint_vacuum_clears_heat_state(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    vac = reg.get("vacuum")
    grid.set_cell(0, 0, material=al, is_fixed=True, fixed_temp=500.0)
    grid.set_cell(1, 1, material=al, is_flux=True, flux_q=1000.0)
    grid.set_cell(0, 0, material=vac, is_fixed=False, is_flux=False)
    grid.set_cell(1, 1, material=vac, is_fixed=False, is_flux=False)
    assert grid.cell(0, 0).is_fixed is False
    assert grid.cell(1, 1).is_flux is False


def test_group_vacuum_clears_heat_state(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    vac = reg.get("vacuum")
    grid.set_cell(0, 0, material=al, is_fixed=True, fixed_temp=500.0)
    grid.set_cell(1, 1, material=al, is_flux=True, flux_q=800.0)
    for r, c in [(0, 0), (1, 1)]:
        grid.set_cell(r, c, material=vac)
        grid.set_cell(r, c, is_fixed=False, is_flux=False)
    assert grid.cell(0, 0).is_fixed is False
    assert grid.cell(1, 1).is_flux is False


def test_volumetric_flux_mask(make_grid):
    grid, _ = make_grid(4, 4)
    grid.set_cell(1, 1, is_flux=True, flux_q=100.0, is_volumetric_flux=True)
    grid.set_cell(2, 2, is_flux=True, flux_q=200.0, is_volumetric_flux=False)
    vm = grid.volumetric_flux_mask()
    assert vm[1, 1] is np.True_
    assert vm[2, 2] is np.False_


def test_snapshot_restore_volumetric_flux(make_grid):
    grid, _ = make_grid(4, 4)
    grid.set_cell(1, 1, is_flux=True, flux_q=100.0, is_volumetric_flux=True)
    snap = grid.snapshot()
    grid.set_cell(1, 1, is_volumetric_flux=False)
    grid.restore(snap)
    assert grid.cell(1, 1).is_volumetric_flux is True


def test_temperature_array_round_trip(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(1, 2, material=al, temperature=450.0)
    T = grid.temperature_array()
    assert abs(T[1, 2] - 450.0) < 1e-9
    T[1, 2] = 999.0
    grid.import_temperatures(T)
    assert abs(grid.cell(1, 2).temperature - 999.0) < 1e-9


def test_reset_temperatures(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=800.0)
    grid.reset_temperatures()
    assert abs(grid.cell(0, 0).temperature - 293.15) < 1e-9


def test_rho_cp_array_zero_for_vacuum(make_grid):
    grid, _ = make_grid()
    rcp = grid.rho_cp_array()
    assert rcp.shape == (4, 4) and rcp.sum() == 0.0


def test_k_array_reflects_material(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(2, 3, material=al)
    k = grid.k_array()
    assert abs(k[2, 3] - 167.0) < 1e-9


def test_set_protected(make_grid):
    grid, _ = make_grid()
    grid.set_cell(1, 1, protected=True)
    assert grid.cell(1, 1).protected is True


def test_toggle_protected(make_grid):
    grid, _ = make_grid()
    grid.set_cell(1, 1, protected=True)
    grid.set_cell(1, 1, protected=False)
    assert grid.cell(1, 1).protected is False


def test_snapshot_restore_protected(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, protected=True)
    snap = grid.snapshot()
    grid.set_cell(0, 0, protected=False)
    assert grid.cell(0, 0).protected is False
    grid.restore(snap)
    assert grid.cell(0, 0).protected is True


def test_restore_missing_protected_defaults_false(make_grid):
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al)
    snap = grid.snapshot()
    old_fmt = [[tup[:7] for tup in row] for row in snap]
    grid.set_cell(0, 0, protected=True)
    grid.restore(old_fmt)
    assert grid.cell(0, 0).protected is False
