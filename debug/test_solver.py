"""Tests for src.simulation.solver.Solver."""
from __future__ import annotations

import numpy as np


def _arrays(rows, cols, k_val, rhocp_val, T_val):
    """Create uniform test arrays for solver tests."""
    k      = np.full((rows, cols), k_val)
    rho_cp = np.full((rows, cols), rhocp_val)
    T      = np.full((rows, cols), T_val, dtype=float)
    fm  = np.zeros((rows, cols), dtype=bool)
    ft  = np.zeros((rows, cols))
    xm  = np.zeros((rows, cols), dtype=bool)
    xq  = np.zeros((rows, cols))
    return k, rho_cp, T, fm, ft, xm, xq


def test_fixed_temp_stays_pinned(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    fm[2, 2] = True; ft[2, 2] = 500.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.1)
    assert abs(T_new[2, 2] - 500.0) < 1e-9


def test_flux_cell_heats(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    xm[1, 1] = True; xq[1, 1] = 10000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=1.0)
    assert T_new[1, 1] > 300.0


def test_flux_cell_not_pinned(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    xm[0, 0] = True; xq[0, 0] = 5000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=1.0)
    assert T_new[0, 0] != 300.0


def test_e_from_flux_positive(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    xm[2, 2] = True; xq[2, 2] = 1000.0
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_e_from_flux > 0.0


def test_e_from_flux_zero_without_flux(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_e_from_flux == 0.0


def test_energy_conservation(solver):
    rows, cols = 6, 6
    rhocp = 2700.0 * 896.0
    dx2 = 0.01 ** 2
    k, rcp, T, fm, ft, xm, xq = _arrays(rows, cols, 167.0, rhocp, 300.0)
    xm[3, 3] = True; xq[3, 3] = 5000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.001)
    E_after = float(np.sum(rcp * (T_new - 300.0))) * dx2
    err = abs(E_after - solver.last_e_from_flux) / (abs(solver.last_e_from_flux) + 1e-15)
    assert err < 0.01


def test_no_false_ss_with_flux(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 300.0)
    xm[2, 2] = True; xq[2, 2] = 5000.0
    for _ in range(20):
        T = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_substep_delta > 0.0


def test_flux_adjacent_to_fixed(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 50.0, 1000*500, 300.0)
    fm[0, 0] = True; ft[0, 0] = 300.0
    xm[0, 1] = True; xq[0, 1] = 2000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert T_new[0, 1] > 300.0


def test_no_nan_mixed_vacuum(solver):
    rows, cols = 4, 4
    k = np.zeros((rows, cols)); k[2, 2] = 167.0
    rho_cp = np.zeros((rows, cols)); rho_cp[2, 2] = 2700.0 * 896.0
    T = np.full((rows, cols), 300.0); T[2, 2] = 400.0
    fm = np.zeros((rows, cols), dtype=bool); ft = np.zeros((rows, cols))
    xm = np.zeros((rows, cols), dtype=bool); xq = np.zeros((rows, cols))
    T_new = solver.advance(T, k, rho_cp, fm, ft, xm, xq, duration=0.1)
    assert np.all(np.isfinite(T_new))


def test_volumetric_flux(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 300.0)
    xm[1, 1] = True; xq[1, 1] = 5000.0
    vol = np.zeros((4, 4), dtype=bool); vol[1, 1] = True
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol)
    assert T_new[1, 1] > 300.0


def test_surface_flux(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 300.0)
    xm[1, 1] = True; xq[1, 1] = 5000.0
    vol = np.zeros((4, 4), dtype=bool)
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol)
    assert T_new[1, 1] > 300.0


def test_negative_flux_cools(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 350.0)
    xm[1, 1] = True; xq[1, 1] = -5000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01)
    assert T_new[1, 1] < 350.0


def test_hot_fixed_adds_energy(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 293.15)
    fm[0, 0] = True; ft[0, 0] = 600.0
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01)
    assert solver.last_e_from_fixed > 0.0


def test_cold_fixed_removes_energy(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 600.0)
    fm[2, 2] = True; ft[2, 2] = 100.0
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01)
    assert solver.last_e_from_fixed < 0.0


def test_last_substep_dt_positive(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_substep_dt > 0.0


def test_surface_flux_heats_more_than_volumetric(solver):
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0*896.0, 300.0)
    xm[1, 1] = True; xq[1, 1] = 5000.0
    vol = np.zeros((4, 4), dtype=bool)
    T_surf = solver.advance(T.copy(), k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol)
    vol2 = np.ones((4, 4), dtype=bool)
    T_vol = solver.advance(T.copy(), k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol2)
    assert T_surf[1, 1] > T_vol[1, 1]
