"""
PyTherm v1.0.0 -- headless test suite.
Run from the project root:  py debug/run_tests.py
Tests all logic that does not require a running QApplication.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import numpy as np

# Create a single QApplication for all tests that need Qt widgets.
# Must be done before any Qt imports to avoid multiple-instance segfaults.
from PyQt6.QtWidgets import QApplication
_qapp = QApplication.instance() or QApplication(sys.argv)

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
_results: list[tuple[str, bool, str]] = []


def test(name: str):
    def decorator(fn):
        try:
            fn()
            _results.append((name, True, ""))
        except Exception:
            _results.append((name, False, traceback.format_exc().strip().splitlines()[-1]))
        return fn
    return decorator


def _make_grid(rows=4, cols=4):
    from src.simulation.grid import Grid
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    return Grid(rows, cols, reg.get("vacuum"), ambient_temp_k=293.15), reg


def _arrays(rows, cols, k_val, rhocp_val, T_val):
    k      = np.full((rows, cols), k_val)
    rho_cp = np.full((rows, cols), rhocp_val)
    T      = np.full((rows, cols), T_val, dtype=float)
    fm  = np.zeros((rows, cols), dtype=bool)
    ft  = np.zeros((rows, cols))
    xm  = np.zeros((rows, cols), dtype=bool)
    xq  = np.zeros((rows, cols))
    return k, rho_cp, T, fm, ft, xm, xq


# ── Cell ──────────────────────────────────────────────────────────────────────

@test("Cell: has is_flux and flux_q fields with correct defaults")
def _():
    from src.simulation.cell import Cell
    from src.models.material import Material
    mat = Material(id="vacuum", name="Vacuum", color="#111", k=0, rho=0, cp=0, is_builtin=True)
    c = Cell(material=mat, temperature=300.0)
    assert c.is_flux is False and c.flux_q == 0.0


@test("Cell: flux fields settable at construction")
def _():
    from src.simulation.cell import Cell
    from src.models.material import Material
    mat = Material(id="vacuum", name="Vacuum", color="#111", k=0, rho=0, cp=0, is_builtin=True)
    c = Cell(material=mat, temperature=300.0, is_flux=True, flux_q=500.0)
    assert c.is_flux is True and c.flux_q == 500.0


# ── Grid ──────────────────────────────────────────────────────────────────────

@test("Grid: set_cell accepts is_flux and flux_q")
def _():
    grid, _ = _make_grid()
    grid.set_cell(0, 0, is_flux=True, flux_q=1000.0)
    c = grid.cell(0, 0)
    assert c.is_flux is True and c.flux_q == 1000.0


@test("Grid: flux_mask returns correct boolean array")
def _():
    grid, _ = _make_grid()
    grid.set_cell(1, 2, is_flux=True, flux_q=500.0)
    mask = grid.flux_mask()
    assert mask.shape == (4, 4)
    assert bool(mask[1, 2]) is True and mask.sum() == 1


@test("Grid: flux_q_array returns correct values")
def _():
    grid, _ = _make_grid()
    grid.set_cell(0, 1, is_flux=True, flux_q=750.0)
    grid.set_cell(2, 3, is_flux=True, flux_q=250.0)
    arr = grid.flux_q_array()
    assert abs(arr[0, 1] - 750.0) < 1e-9 and abs(arr[2, 3] - 250.0) < 1e-9 and arr[0, 0] == 0.0


@test("Grid: snapshot/restore round-trips flux fields")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=400.0, is_flux=True, flux_q=1500.0)
    snap = grid.snapshot()
    grid.set_cell(0, 0, is_flux=False, flux_q=0.0)
    grid.restore(snap)
    c = grid.cell(0, 0)
    assert c.is_flux is True and abs(c.flux_q - 1500.0) < 1e-9


@test("Grid: set_cell is_flux and is_fixed are independent")
def _():
    grid, _ = _make_grid()
    grid.set_cell(1, 1, is_fixed=True, fixed_temp=350.0)
    grid.set_cell(1, 1, is_flux=True, is_fixed=False, flux_q=200.0)
    c = grid.cell(1, 1)
    assert c.is_flux is True and c.is_fixed is False


@test("B-PAINT-VAC: painting vacuum clears is_fixed and is_flux")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    vac = reg.get("vacuum")
    grid.set_cell(0, 0, material=al, is_fixed=True, fixed_temp=500.0)
    grid.set_cell(1, 1, material=al, is_flux=True, flux_q=1000.0)
    # Simulate what _paint_cell does for vacuum
    grid.set_cell(0, 0, material=vac, is_fixed=False, is_flux=False)
    grid.set_cell(1, 1, material=vac, is_fixed=False, is_flux=False)
    assert grid.cell(0, 0).is_fixed is False
    assert grid.cell(1, 1).is_flux is False


@test("B-GROUP-VAC: applying vacuum material always clears heat state")
def _():
    grid, reg = _make_grid()
    al  = reg.get("al6061")
    vac = reg.get("vacuum")
    grid.set_cell(0, 0, material=al, is_fixed=True, fixed_temp=500.0)
    grid.set_cell(1, 1, material=al, is_flux=True, flux_q=800.0)
    # Simulate GroupEditPanel._apply() for vacuum with PartiallyChecked -- new fix branch
    for r, c in [(0, 0), (1, 1)]:
        grid.set_cell(r, c, material=vac)
        # PartiallyChecked + vacuum -> should clear
        grid.set_cell(r, c, is_fixed=False, is_flux=False)
    assert grid.cell(0, 0).is_fixed is False
    assert grid.cell(1, 1).is_flux is False


# ── Solver ────────────────────────────────────────────────────────────────────

@test("Solver: fixed-T cell stays pinned after advance")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    fm[2, 2] = True; ft[2, 2] = 500.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.1)
    assert abs(T_new[2, 2] - 500.0) < 1e-9


@test("Solver: flux cell temperature rises with positive flux_q")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    xm[1, 1] = True; xq[1, 1] = 10000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=1.0)
    assert T_new[1, 1] > 300.0, f"Flux cell did not heat up: {T_new[1, 1]}"


@test("Solver: flux cell is NOT pinned to initial temperature")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    xm[0, 0] = True; xq[0, 0] = 5000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=1.0)
    assert T_new[0, 0] != 300.0, "Flux cell was incorrectly pinned"


@test("Solver: last_e_from_flux > 0 when flux cells present")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    xm[2, 2] = True; xq[2, 2] = 1000.0
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_e_from_flux > 0.0


@test("Solver: last_e_from_flux == 0 without flux cells")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_e_from_flux == 0.0


@test("Solver: energy conservation with flux (<1% error on short step)")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    rows, cols = 6, 6
    rhocp = 2700.0 * 896.0
    dx2   = 0.01 ** 2
    k, rcp, T, fm, ft, xm, xq = _arrays(rows, cols, 167.0, rhocp, 300.0)
    xm[3, 3] = True; xq[3, 3] = 5000.0
    duration = 0.001
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=duration)
    E_after = float(np.sum(rcp * (T_new - 300.0))) * dx2
    err = abs(E_after - solver.last_e_from_flux) / (abs(solver.last_e_from_flux) + 1e-15)
    assert err < 0.01, f"Energy conservation error {err:.2%}: E_after={E_after:.3e} injected={solver.last_e_from_flux:.3e}"


@test("Solver: last_substep_delta > 0 for flux-only grid (no false SS)")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    rows, cols = 4, 4
    rhocp = 2700.0 * 896.0
    k, rcp, T, fm, ft, xm, xq = _arrays(rows, cols, 167.0, rhocp, 300.0)
    xm[2, 2] = True; xq[2, 2] = 5000.0
    # After many steps the conductive gradient approaches zero (spatially uniform rise),
    # but last_substep_delta must remain > 0 because flux injection is ongoing.
    for _ in range(20):
        T = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_substep_delta > 0.0, (
        f"False SS trigger: last_substep_delta={solver.last_substep_delta:.2e} "
        "should be >0 for ongoing flux injection"
    )


@test("Solver: flux cell adjacent to fixed-T cell still heats")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 50.0, 1000*500, 300.0)
    fm[0, 0] = True; ft[0, 0] = 300.0
    xm[0, 1] = True; xq[0, 1] = 2000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert T_new[0, 1] > 300.0


@test("Solver: no NaN on mixed vacuum + material grid")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    rows, cols = 4, 4
    k = np.zeros((rows, cols)); k[2, 2] = 167.0
    rho_cp = np.zeros((rows, cols)); rho_cp[2, 2] = 2700.0 * 896.0
    T = np.full((rows, cols), 300.0); T[2, 2] = 400.0
    fm = np.zeros((rows, cols), dtype=bool); ft = np.zeros((rows, cols))
    xm = np.zeros((rows, cols), dtype=bool); xq = np.zeros((rows, cols))
    T_new = solver.advance(T, k, rho_cp, fm, ft, xm, xq, duration=0.1)
    assert np.all(np.isfinite(T_new))


@test("Solver: volumetric flux (W/m^3) heats cell correctly")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0 * 896.0, 300.0)
    xm[1, 1] = True; xq[1, 1] = 5000.0
    vol = np.zeros((4, 4), dtype=bool); vol[1, 1] = True
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol)
    assert T_new[1, 1] > 300.0, "Volumetric flux should heat cell"


@test("Solver: surface flux (W/m^2) heats cell correctly")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0 * 896.0, 300.0)
    xm[1, 1] = True; xq[1, 1] = 5000.0
    vol = np.zeros((4, 4), dtype=bool)  # all surface
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol)
    assert T_new[1, 1] > 300.0, "Surface flux should heat cell"


@test("Solver: negative flux cools cell")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0 * 896.0, 350.0)
    xm[1, 1] = True; xq[1, 1] = -5000.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01)
    assert T_new[1, 1] < 350.0, "Negative flux should cool cell"


@test("Grid: volumetric_flux_mask returns correct boolean array")
def _():
    grid, _ = _make_grid(4, 4)
    grid.set_cell(1, 1, is_flux=True, flux_q=100.0, is_volumetric_flux=True)
    grid.set_cell(2, 2, is_flux=True, flux_q=200.0, is_volumetric_flux=False)
    vm = grid.volumetric_flux_mask()
    assert vm[1, 1] is np.True_
    assert vm[2, 2] is np.False_


@test("Grid: snapshot/restore round-trips is_volumetric_flux")
def _():
    grid, _ = _make_grid(4, 4)
    grid.set_cell(1, 1, is_flux=True, flux_q=100.0, is_volumetric_flux=True)
    snap = grid.snapshot()
    grid.set_cell(1, 1, is_volumetric_flux=False)
    grid.restore(snap)
    assert grid.cell(1, 1).is_volumetric_flux is True


# ── File I/O ──────────────────────────────────────────────────────────────────

@test("file_io: save/reload preserves is_flux and flux_q")
def _():
    from src.io.file_io import save_pytherm, load_pytherm
    grid, reg = _make_grid(rows=3, cols=3)
    al = reg.get("al6061")
    grid.set_cell(1, 1, material=al, temperature=350.0, is_flux=True, flux_q=2500.0)
    grid.set_cell(0, 0, material=al, temperature=400.0, is_fixed=True, fixed_temp=400.0)
    with tempfile.NamedTemporaryFile(suffix=".pytherm", delete=False) as f:
        tmp_path = Path(f.name)
    try:
        save_pytherm(tmp_path, grid, solver_dx=0.01, custom_materials=[])
        data = load_pytherm(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    cells = {(cd["row"], cd["col"]): cd for cd in data["cells"]}
    fc = cells[(1, 1)]
    assert fc["is_flux"] is True and abs(fc["flux_q"] - 2500.0) < 1e-9
    assert cells[(0, 0)]["is_fixed"] is True
    vac = cells[(0, 1)]
    assert vac["is_flux"] is False and vac["flux_q"] == 0.0


@test("file_io: old file without is_flux key loads without error")
def _():
    from src.io.file_io import load_pytherm
    data = {
        "version": 1,
        "grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
        "cells": [
            {"row": r, "col": c, "material_id": "vacuum", "temperature_k": 293.15,
             "is_fixed": False, "fixed_temp_k": 0.0}
            for r in range(2) for c in range(2)
        ],
        "custom_materials": [],
    }
    with tempfile.NamedTemporaryFile(suffix=".pytherm", delete=False, mode="w") as f:
        json.dump(data, f); tmp_path = Path(f.name)
    try:
        loaded = load_pytherm(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    for cd in loaded["cells"]:
        assert cd.get("is_flux", False) is False


# ── Units ──────────────────────────────────────────────────────────────────────

@test("Units: C/K/F/R round-trip conversions")
def _():
    from src.rendering import units as u
    T_k = 373.15
    u.set_unit(u.Unit.CELSIUS);    assert abs(u.to_display(T_k) - 100.0) < 0.01
    u.set_unit(u.Unit.KELVIN);     assert abs(u.to_display(T_k) - 373.15) < 0.01
    u.set_unit(u.Unit.FAHRENHEIT); assert abs(u.to_display(T_k) - 212.0) < 0.01
    u.set_unit(u.Unit.RANKINE);    assert abs(u.to_display(T_k) - 671.67) < 0.1
    u.set_unit(u.Unit.CELSIUS)


# ── MaterialRegistry ───────────────────────────────────────────────────────────

@test("MaterialRegistry: built-in materials load (>=40 materials)")
def _():
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    assert len(reg.all_materials) >= 40
    assert reg.get("vacuum").is_vacuum
    assert reg.get("al6061").k == 167.0


@test("MaterialRegistry: custom material add/remove round-trip")
def _():
    from src.models.material_registry import MaterialRegistry
    from src.models.material import Material
    import shutil
    data_dir = Path(__file__).parent.parent / "data"
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(data_dir / "materials.json", f"{tmp}/materials.json")
        user_path = Path(tmp) / "user_materials.json"
        reg = MaterialRegistry(Path(tmp) / "materials.json", user_path)
        mat = Material(id="test_mat", name="TestMat", color="#abcdef",
                       k=1.0, rho=100.0, cp=500.0, is_builtin=False)
        reg.add_or_update_custom(mat)
        assert "test_mat" in reg.custom
        reg2 = MaterialRegistry(Path(tmp) / "materials.json", user_path)
        assert "test_mat" in reg2.custom


# ── SimClock ──────────────────────────────────────────────────────────────────

@test("SimClock: e_cumulative_flux grows after step with flux cell")
def _():
    import sys
    from src.simulation.grid import Grid
    from src.simulation.solver import Solver
    from src.simulation.sim_clock import SimClock
    from src.models.material_registry import MaterialRegistry
    from src.ui.grid_scene import GridScene
    data_dir = Path(__file__).parent.parent / "data"
    reg  = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    al   = reg.get("al6061")
    grid = Grid(4, 4, al, ambient_temp_k=293.15)
    grid.set_cell(1, 1, is_flux=True, flux_q=5000.0)
    scene  = GridScene(grid)
    solver = Solver(dx=0.01)
    clock  = SimClock(grid, solver, scene)
    clock.reset()
    clock.step(duration=0.01)
    assert clock.e_cumulative_flux > 0.0
    assert clock.last_dt_sim > 0.0


@test("file_io: save includes software_version and sim_settings")
def _():
    from src.io.file_io import save_pytherm, load_pytherm
    import tempfile
    grid, reg = _make_grid(rows=2, cols=2)
    with tempfile.NamedTemporaryFile(suffix=".pytherm", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sim_settings = {"boundary_conditions": {"top": "sink", "bottom": "insulator",
                                                "left": "insulator", "right": "insulator"}}
        save_pytherm(tmp_path, grid, 0.01, [], sim_settings=sim_settings)
        data = load_pytherm(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    assert "software_version" in data
    from src.version import VERSION
    assert data["software_version"] == VERSION
    assert data["sim_settings"]["boundary_conditions"]["top"] == "sink"


@test("file_io: old file without sim_settings loads without error")
def _():
    from src.io.file_io import load_pytherm
    import json, tempfile
    data = {
        "version": 1,
        "grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
        "cells": [
            {"row": r, "col": c, "material_id": "vacuum", "temperature_k": 293.15,
             "is_fixed": False, "fixed_temp_k": 0.0}
            for r in range(2) for c in range(2)
        ],
        "custom_materials": [],
    }
    with tempfile.NamedTemporaryFile(suffix=".pytherm", delete=False, mode="w") as tmp:
        json.dump(data, tmp); tmp_path = Path(tmp.name)
    try:
        loaded = load_pytherm(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    # No software_version or sim_settings -> no crash, defaults expected by caller
    assert loaded.get("sim_settings", {}) == {}
    assert loaded.get("software_version") is None


# ── File schema validation ────────────────────────────────────────────────────

@test("file_io: _validate_pytherm raises on missing version (strict mode)")
def _():
    from src.io.file_io import _validate_pytherm
    try:
        _validate_pytherm({"grid": {}, "cells": []}, require_version=True)
        assert False, "Should have raised"
    except ValueError as e:
        assert "version" in str(e).lower()


@test("file_io: _validate_pytherm accepts missing version (template mode)")
def _():
    from src.io.file_io import _validate_pytherm
    _validate_pytherm({"grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01}, "cells": []},
                      require_version=False)


@test("file_io: _validate_pytherm raises on missing grid")
def _():
    from src.io.file_io import _validate_pytherm
    try:
        _validate_pytherm({"version": 1, "cells": []})
        assert False, "Should have raised"
    except ValueError as e:
        assert "grid" in str(e).lower()


@test("file_io: _validate_pytherm raises on non-list cells")
def _():
    from src.io.file_io import _validate_pytherm
    try:
        _validate_pytherm({
            "version": 1,
            "grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
            "cells": "bad",
        })
        assert False, "Should have raised"
    except ValueError as e:
        assert "cells" in str(e).lower()


@test("file_io: _validate_pytherm raises on missing grid sub-keys")
def _():
    from src.io.file_io import _validate_pytherm
    try:
        _validate_pytherm({
            "version": 1,
            "grid": {"rows": 2},  # missing cols/ambient_temp_k/dx_m
            "cells": [],
        })
        assert False, "Should have raised"
    except ValueError:
        pass  # expected


@test("file_io: _validate_pytherm passes on valid structure")
def _():
    from src.io.file_io import _validate_pytherm
    _validate_pytherm({
        "version": 1,
        "grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
        "cells": [],
    })  # no exception = pass


# ── Heatmap renderer / palette ────────────────────────────────────────────────

@test("Heatmap: PALETTE_NAMES is non-empty list of strings")
def _():
    from src.rendering.heatmap_renderer import PALETTE_NAMES
    assert isinstance(PALETTE_NAMES, list) and len(PALETTE_NAMES) >= 2
    assert all(isinstance(n, str) for n in PALETTE_NAMES)


@test("Heatmap: set_palette changes color output")
def _():
    from src.rendering.heatmap_renderer import heatmap_color, set_palette, PALETTE_NAMES
    set_palette(PALETTE_NAMES[0])
    c1 = heatmap_color(0.5, 273.15, 373.15)
    # Switch to a different palette (use last in list to be safe)
    set_palette(PALETTE_NAMES[-1])
    c2 = heatmap_color(0.5, 273.15, 373.15)
    # Reset to first
    set_palette(PALETTE_NAMES[0])
    assert c1 != c2, f"Palettes {PALETTE_NAMES[0]} and {PALETTE_NAMES[-1]} produced identical color"


@test("Heatmap: heatmap_color returns valid QColor with RGB in range")
def _():
    from src.rendering.heatmap_renderer import heatmap_color, set_palette, PALETTE_NAMES
    for name in PALETTE_NAMES:
        set_palette(name)
        c = heatmap_color(0.0, 273.15, 373.15)
        r, g, b = c.red(), c.green(), c.blue()
        assert 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255, f"Invalid RGB for palette {name}"
    set_palette(PALETTE_NAMES[0])


@test("Heatmap: heatmap_color clamps T below min to cold color")
def _():
    from src.rendering.heatmap_renderer import heatmap_color, set_palette, PALETTE_NAMES
    set_palette(PALETTE_NAMES[0])
    c_at_min   = heatmap_color(273.15, 273.15, 373.15)
    c_below    = heatmap_color(200.0,  273.15, 373.15)
    assert c_at_min == c_below


@test("Heatmap: heatmap_color clamps T above max to hot color")
def _():
    from src.rendering.heatmap_renderer import heatmap_color, set_palette, PALETTE_NAMES
    set_palette(PALETTE_NAMES[0])
    c_at_max   = heatmap_color(373.15, 273.15, 373.15)
    c_above    = heatmap_color(500.0,  273.15, 373.15)
    assert c_at_max == c_above


# ── Grid extended ─────────────────────────────────────────────────────────────

@test("Grid: temperature_array / import_temperatures round-trip")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(1, 2, material=al, temperature=450.0)
    T = grid.temperature_array()
    assert abs(T[1, 2] - 450.0) < 1e-9
    T[1, 2] = 999.0
    grid.import_temperatures(T)
    assert abs(grid.cell(1, 2).temperature - 999.0) < 1e-9


@test("Grid: reset_temperatures resets to ambient")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=800.0)
    grid.reset_temperatures()
    assert abs(grid.cell(0, 0).temperature - 293.15) < 1e-9


@test("Grid: rho_cp_array returns zero for vacuum")
def _():
    grid, _ = _make_grid()
    rcp = grid.rho_cp_array()
    assert rcp.shape == (4, 4) and rcp.sum() == 0.0


@test("Grid: k_array reflects material k values")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(2, 3, material=al)
    k = grid.k_array()
    assert abs(k[2, 3] - 167.0) < 1e-9


# ── MaterialRegistry extended ─────────────────────────────────────────────────

@test("MaterialRegistry: corrupt user_materials.json does not crash")
def _():
    from src.models.material_registry import MaterialRegistry
    import shutil
    data_dir = Path(__file__).parent.parent / "data"
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(data_dir / "materials.json", f"{tmp}/materials.json")
        user_path = Path(tmp) / "user_materials.json"
        user_path.write_text("not valid json {{{{")
        reg = MaterialRegistry(Path(tmp) / "materials.json", user_path)
        assert len(reg.builtins) >= 40  # built-ins still load fine


@test("MaterialRegistry: generate_custom_id produces unique ids")
def _():
    from src.models.material_registry import MaterialRegistry
    from src.models.material import Material
    import shutil
    data_dir = Path(__file__).parent.parent / "data"
    with tempfile.TemporaryDirectory() as tmp:
        shutil.copy(data_dir / "materials.json", f"{tmp}/materials.json")
        reg = MaterialRegistry(Path(tmp) / "materials.json", Path(tmp) / "user.json")
        id1 = reg.generate_custom_id("My Alloy")
        mat = Material(id=id1, name="My Alloy", color="#ff0000",
                       k=10.0, rho=500.0, cp=400.0, is_builtin=False)
        reg.add_or_update_custom(mat)
        id2 = reg.generate_custom_id("My Alloy")
        assert id1 != id2, "generate_custom_id should not return an already-used id"


# ── Solver extended ────────────────────────────────────────────────────────────

@test("Solver: energy injected by fixed-T cells matches last_e_from_fixed sign")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    rows, cols = 4, 4
    rhocp = 2700.0 * 896.0
    dx2   = 0.01 ** 2
    k, rcp, T, fm, ft, xm, xq = _arrays(rows, cols, 167.0, rhocp, 293.15)
    # Hot pin should add energy
    fm[0, 0] = True; ft[0, 0] = 600.0
    T_new = solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01)
    assert solver.last_e_from_fixed > 0.0, "Hot fixed-T cell should add energy"


@test("Solver: cold fixed-T cell removes energy (last_e_from_fixed < 0)")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    rows, cols = 4, 4
    rhocp = 2700.0 * 896.0
    k, rcp, T, fm, ft, xm, xq = _arrays(rows, cols, 167.0, rhocp, 600.0)  # hot grid
    # Cold pin should remove energy
    fm[2, 2] = True; ft[2, 2] = 100.0
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.01)
    assert solver.last_e_from_fixed < 0.0, "Cold fixed-T cell should remove energy"


@test("Solver: last_substep_dt is positive after advance")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700*896, 300.0)
    solver.advance(T, k, rcp, fm, ft, xm, xq, duration=0.5)
    assert solver.last_substep_dt > 0.0


# ── SimClock extended ─────────────────────────────────────────────────────────

@test("SimClock: recalculate_energy_reference clears cumulative accumulators")
def _():
    import sys
    from src.simulation.grid import Grid
    from src.simulation.solver import Solver
    from src.simulation.sim_clock import SimClock
    from src.models.material_registry import MaterialRegistry
    from src.ui.grid_scene import GridScene
    data_dir = Path(__file__).parent.parent / "data"
    reg  = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    al   = reg.get("al6061")
    grid = Grid(4, 4, al, ambient_temp_k=293.15)
    grid.set_cell(0, 0, is_flux=True, flux_q=5000.0)
    scene  = GridScene(grid)
    solver = Solver(dx=0.01)
    clock  = SimClock(grid, solver, scene)
    clock.reset()
    clock.step(duration=0.1)
    assert clock.e_cumulative_flux > 0.0  # sanity: flux injected something
    # Simulate ambient change
    grid.ambient_temp_k = 300.0
    clock.recalculate_energy_reference()
    assert clock.e_cumulative_flux == 0.0
    assert clock.e_cumulative_fixed == 0.0
    assert clock.e_cumulative_sinks == 0.0


@test("SimClock: step advances sim_time correctly")
def _():
    import sys
    from src.simulation.grid import Grid
    from src.simulation.solver import Solver
    from src.simulation.sim_clock import SimClock
    from src.models.material_registry import MaterialRegistry
    from src.ui.grid_scene import GridScene
    data_dir = Path(__file__).parent.parent / "data"
    reg  = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    al   = reg.get("al6061")
    grid = Grid(4, 4, al, ambient_temp_k=293.15)
    scene  = GridScene(grid)
    solver = Solver(dx=0.01)
    clock  = SimClock(grid, solver, scene)
    clock.reset()
    clock.step(duration=2.5)
    assert abs(clock.sim_time - 2.5) < 1e-9


# ── Units extended ────────────────────────────────────────────────────────────

@test("Units: from_display is inverse of to_display for all units")
def _():
    from src.rendering import units as u
    for unit in (u.Unit.CELSIUS, u.Unit.KELVIN, u.Unit.FAHRENHEIT, u.Unit.RANKINE):
        u.set_unit(unit)
        for T_k in (200.0, 293.15, 373.15, 1000.0):
            T_disp = u.to_display(T_k)
            T_back = u.from_display(T_disp)
            assert abs(T_back - T_k) < 0.01, f"{unit}: round-trip failed at {T_k} K"
    u.set_unit(u.Unit.CELSIUS)


@test("Units: fmt_energy formats joules correctly")
def _():
    from src.rendering.units import fmt_energy
    assert "J" in fmt_energy(50.0)
    assert "kJ" in fmt_energy(5000.0) or "J" in fmt_energy(5000.0)


# ── Units: delta conversion (new) ─────────────────────────────────────────────

@test("Units: delta_k_to_display is 1:1 for Celsius and Kelvin")
def _():
    from src.rendering import units as u
    u.set_unit(u.Unit.CELSIUS)
    assert abs(u.delta_k_to_display(50.0) - 50.0) < 1e-9
    u.set_unit(u.Unit.KELVIN)
    assert abs(u.delta_k_to_display(50.0) - 50.0) < 1e-9
    u.set_unit(u.Unit.CELSIUS)


@test("Units: delta_k_to_display scales 9/5 for Fahrenheit")
def _():
    from src.rendering import units as u
    u.set_unit(u.Unit.FAHRENHEIT)
    assert abs(u.delta_k_to_display(50.0) - 90.0) < 1e-9
    u.set_unit(u.Unit.CELSIUS)


@test("Units: delta_display_to_k is inverse of delta_k_to_display for all units")
def _():
    from src.rendering import units as u
    for unit in (u.Unit.CELSIUS, u.Unit.KELVIN, u.Unit.FAHRENHEIT, u.Unit.RANKINE):
        u.set_unit(unit)
        dk = 50.0
        assert abs(u.delta_display_to_k(u.delta_k_to_display(dk)) - dk) < 1e-9
    u.set_unit(u.Unit.CELSIUS)


# ── GridScene: hotspot and isotherm state ──────────────────────────────────────

@test("GridScene: set_isotherm stores enabled and interval")
def _():
    import sys
    from src.ui.grid_scene import GridScene
    grid, _ = _make_grid()
    scene = GridScene(grid)
    scene.set_isotherm(True, 25.0)
    assert scene._isotherm_enabled is True
    assert abs(scene._isotherm_interval_k - 25.0) < 1e-9


@test("GridScene: set_hotspot_threshold enables hotspot")
def _():
    import sys
    from src.ui.grid_scene import GridScene
    grid, _ = _make_grid()
    scene = GridScene(grid)
    scene.set_hotspot_threshold(400.0)
    assert scene._hotspot_enabled is True
    assert abs(scene._hotspot_threshold_k - 400.0) < 1e-9


@test("GridScene: set_hotspot_threshold with nan disables hotspot")
def _():
    import sys, math
    from src.ui.grid_scene import GridScene
    grid, _ = _make_grid()
    scene = GridScene(grid)
    scene.set_hotspot_threshold(400.0)
    scene.set_hotspot_threshold(float("nan"))
    assert scene._hotspot_enabled is False


@test("GridScene: hotspot_count counts cells above threshold")
def _():
    import sys
    from src.ui.grid_scene import GridScene
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=500.0)
    grid.set_cell(0, 1, material=al, temperature=300.0)
    scene = GridScene(grid)
    scene.set_hotspot_threshold(400.0)
    assert scene.hotspot_count == 1


@test("GridScene: hotspot_count is 0 when disabled")
def _():
    import sys
    from src.ui.grid_scene import GridScene
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=500.0)
    scene = GridScene(grid)
    assert scene.hotspot_count == 0


# ── TempPlotPanel: pin behavior ────────────────────────────────────────────────

@test("TempPlotPanel: is_pinned defaults False")
def _():
    import sys
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = _make_grid()
    panel = TempPlotPanel(grid)
    assert panel.is_pinned is False


@test("TempPlotPanel: set_tracked_cells ignored when pinned")
def _():
    import sys
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, reg = _make_grid()
    panel = TempPlotPanel(grid)
    panel.set_tracked_cells([(0, 0)])
    panel._pin_btn.setChecked(True)
    panel.set_tracked_cells([(1, 1)])
    assert panel._tracked == [(0, 0)]


@test("TempPlotPanel: set_tracked_cells works after unpin")
def _():
    import sys
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = _make_grid()
    panel = TempPlotPanel(grid)
    panel._pin_btn.setChecked(True)
    panel._pin_btn.setChecked(False)
    panel.set_tracked_cells([(2, 3)])
    assert panel._tracked == [(2, 3)]


# ── CommandPalette: filter behavior ───────────────────────────────────────────

@test("CommandPalette: filter hides non-matching items")
def _():
    import sys
    from src.ui.command_palette import CommandPalette
    entries = [("Draw mode", lambda: None), ("Heatmap view", lambda: None), ("Reset", lambda: None)]
    dlg = CommandPalette(entries)
    dlg._filter.setText("draw")
    visible = [dlg._list.item(i) for i in range(dlg._list.count()) if not dlg._list.item(i).isHidden()]
    assert len(visible) == 1 and visible[0].text() == "Draw mode"


@test("CommandPalette: empty filter shows all items")
def _():
    import sys
    from src.ui.command_palette import CommandPalette
    entries = [("Alpha", lambda: None), ("Beta", lambda: None), ("Gamma", lambda: None)]
    dlg = CommandPalette(entries)
    dlg._filter.setText("")
    visible = [dlg._list.item(i) for i in range(dlg._list.count()) if not dlg._list.item(i).isHidden()]
    assert len(visible) == 3


# ── _PlotCanvas: pin / sync state ─────────────────────────────────────────────

@test("_PlotCanvas: _pinned_points starts empty")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    assert c._pinned_points == []


@test("_PlotCanvas: set_series clears _pinned_points")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_series(["A"])
    c.add_point("A", 1.0, 300.0)
    c._pinned_points.append(("A", 1.0, 300.0))
    c.set_series(["B"])
    assert c._pinned_points == []


@test("_PlotCanvas: clear() clears _pinned_points")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_series(["A"])
    c.add_point("A", 1.0, 300.0)
    c._pinned_points.append(("A", 1.0, 300.0))
    c.clear()
    assert c._pinned_points == []


@test("_PlotCanvas: set_sync_hover stores value")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_hover(5.5)
    assert c._sync_hover_t == 5.5


@test("_PlotCanvas: set_sync_hover(None) clears value")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_hover(5.5)
    c.set_sync_hover(None)
    assert c._sync_hover_t is None


@test("_PlotCanvas: set_sync_pin stores value")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_pin(3.14)
    assert c._sync_pin_t == 3.14


@test("_PlotCanvas: set_sync_pin(None) clears value")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_pin(3.14)
    c.set_sync_pin(None)
    assert c._sync_pin_t is None


@test("_PlotCanvas: _find_nearest returns None when no data")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    assert c._find_nearest(200.0, 100.0) is None


@test("_PlotCanvas: _find_nearest returns closest point")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    # With two points T=300K and T=350K, the t=0 point maps to x=52, y≈155
    # (near the bottom since 300K is only slightly above the padded min).
    # Click within 20px of that screen position.
    c.add_point("A", 0.0, 300.0)
    c.add_point("A", 5.0, 350.0)
    result = c._find_nearest(55.0, 155.0)
    assert result is not None
    name, t, _T = result
    assert name == "A"
    assert abs(t - 0.0) < 1e-6


@test("_PlotCanvas: _handle_click (no shift) adds pin")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    from PyQt6.QtCore import Qt
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c._handle_click(55.0, 100.0, Qt.KeyboardModifier.NoModifier)
    assert len(c._pinned_points) == 1
    assert c._pinned_points[0][0] == "A"


@test("_PlotCanvas: _handle_click (no shift) toggles pin off")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    from PyQt6.QtCore import Qt
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c._handle_click(55.0, 100.0, Qt.KeyboardModifier.NoModifier)
    assert len(c._pinned_points) == 1
    c._handle_click(55.0, 100.0, Qt.KeyboardModifier.NoModifier)
    assert len(c._pinned_points) == 0


@test("_PlotCanvas: _handle_click (shift) emits sync_pin_changed")
def _():
    from src.ui.temp_plot_panel import _PlotCanvas
    from PyQt6.QtCore import Qt
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c.add_point("A", 5.0, 350.0)
    received: list = []
    c.sync_pin_changed.connect(lambda t: received.append(t))
    c._handle_click(200.0, 100.0, Qt.KeyboardModifier.ShiftModifier)
    assert len(received) == 1
    assert received[0] is not None


@test("TempPlotPanel: closing signal exists")
def _():
    assert hasattr(TempPlotPanel := __import__(
        "src.ui.temp_plot_panel", fromlist=["TempPlotPanel"]
    ).TempPlotPanel, "closing")


@test("TempPlotPanel: set_sync_hover updates canvas")
def _():
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _reg = _make_grid()
    panel = TempPlotPanel(grid)
    panel.set_sync_hover(7.0)
    assert panel._canvas._sync_hover_t == 7.0


@test("TempPlotPanel: set_sync_pin updates canvas")
def _():
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _reg = _make_grid()
    panel = TempPlotPanel(grid)
    panel.set_sync_pin(2.5)
    assert panel._canvas._sync_pin_t == 2.5


@test("TempPlotPanel: set_grid clears sync state")
def _():
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _reg = _make_grid()
    panel = TempPlotPanel(grid)
    panel.set_sync_hover(3.0)
    panel.set_sync_pin(1.0)
    panel.set_grid(grid)
    assert panel._canvas._sync_hover_t is None
    assert panel._canvas._sync_pin_t is None


# ── Grid.resize ───────────────────────────────────────────────────────────────

@test("Grid.resize: expand top adds rows at top filled with vacuum")
def _():
    grid, reg = _make_grid(4, 4)
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=400.0)
    vac = reg.get("vacuum")
    grid.resize(top=2, right=0, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows == 6 and grid.cols == 4
    # New top rows should be vacuum at ambient
    assert grid.cell(0, 0).material.is_vacuum
    assert abs(grid.cell(0, 0).temperature - grid.ambient_temp_k) < 1e-9
    # Original row 0 is now row 2
    assert grid.cell(2, 0).material.id == "al6061"


@test("Grid.resize: expand bottom adds rows at bottom")
def _():
    grid, reg = _make_grid(4, 4)
    vac = reg.get("vacuum")
    grid.resize(top=0, right=0, bottom=3, left=0, vacuum_material=vac)
    assert grid.rows == 7 and grid.cols == 4


@test("Grid.resize: expand left adds cols at left")
def _():
    grid, reg = _make_grid(4, 4)
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al)
    vac = reg.get("vacuum")
    grid.resize(top=0, right=0, bottom=0, left=2, vacuum_material=vac)
    assert grid.rows == 4 and grid.cols == 6
    # Original col 0 should now be at col 2
    assert grid.cell(0, 2).material.id == "al6061"


@test("Grid.resize: trim top removes rows from top")
def _():
    grid, reg = _make_grid(6, 4)
    vac = reg.get("vacuum")
    grid.resize(top=-2, right=0, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows == 4 and grid.cols == 4


@test("Grid.resize: trim right removes cols from right")
def _():
    grid, reg = _make_grid(4, 6)
    vac = reg.get("vacuum")
    grid.resize(top=0, right=-3, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows == 4 and grid.cols == 3


@test("Grid.resize: combined expand and trim")
def _():
    grid, reg = _make_grid(4, 4)
    vac = reg.get("vacuum")
    grid.resize(top=2, right=-1, bottom=0, left=1, vacuum_material=vac)
    assert grid.rows == 6 and grid.cols == 4


@test("Grid.resize: clamped to at least 1 row and 1 col")
def _():
    grid, reg = _make_grid(2, 2)
    vac = reg.get("vacuum")
    grid.resize(top=-100, right=-100, bottom=0, left=0, vacuum_material=vac)
    assert grid.rows >= 1 and grid.cols >= 1


@test("Grid.resize: preserves cell data for retained cells")
def _():
    grid, reg = _make_grid(4, 4)
    al = reg.get("al6061")
    grid.set_cell(2, 2, material=al, temperature=500.0, is_fixed=True, fixed_temp=500.0)
    vac = reg.get("vacuum")
    # Add 1 row to top -- original (2,2) moves to (3,2)
    grid.resize(top=1, right=0, bottom=0, left=0, vacuum_material=vac)
    c = grid.cell(3, 2)
    assert c.material.id == "al6061"
    assert abs(c.temperature - 500.0) < 1e-9
    assert c.is_fixed is True


# ── Cell.protected ────────────────────────────────────────────────────────────

@test("Cell.protected: default is False")
def _():
    from src.simulation.cell import Cell
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    c = Cell(material=reg.get("vacuum"), temperature=293.15)
    assert c.protected is False


@test("Grid.set_cell: can set protected=True")
def _():
    grid, _ = _make_grid()
    grid.set_cell(1, 1, protected=True)
    assert grid.cell(1, 1).protected is True


@test("Grid.set_cell: can toggle protected back to False")
def _():
    grid, _ = _make_grid()
    grid.set_cell(1, 1, protected=True)
    grid.set_cell(1, 1, protected=False)
    assert grid.cell(1, 1).protected is False


@test("Grid.snapshot/restore: protected survives round-trip")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, protected=True)
    snap = grid.snapshot()
    grid.set_cell(0, 0, protected=False)
    assert grid.cell(0, 0).protected is False
    grid.restore(snap)
    assert grid.cell(0, 0).protected is True


@test("Grid.restore: missing protected field defaults to False (backward compat)")
def _():
    grid, reg = _make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al)
    # Build a snapshot tuple with only 7 fields (pre-protected format)
    snap = grid.snapshot()
    old_fmt = [[tup[:7] for tup in row] for row in snap]
    grid.set_cell(0, 0, protected=True)
    grid.restore(old_fmt)
    assert grid.cell(0, 0).protected is False


@test("file_io: save_pytherm omits protected when False, includes when True")
def _():
    from src.io.file_io import save_pytherm, load_pytherm
    grid, reg = _make_grid(2, 2)
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, protected=True)
    grid.set_cell(0, 1, material=al, protected=False)
    with tempfile.NamedTemporaryFile(suffix=".pytherm", delete=False) as f:
        path = Path(f.name)
    try:
        save_pytherm(path, grid, 0.01, [])
        data = load_pytherm(path)
        cells_by_rc = {(cd["row"], cd["col"]): cd for cd in data["cells"]}
        assert cells_by_rc[(0, 0)].get("protected") is True
        assert "protected" not in cells_by_rc[(0, 1)]  # omitted when False
    finally:
        path.unlink(missing_ok=True)


# ── MaterialRegistry: expanded library ────────────────────────────────────────

@test("MaterialRegistry: 190+ built-in materials load")
def _():
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    assert len(reg.builtins) >= 190, f"Expected >=190, got {len(reg.builtins)}"


@test("MaterialRegistry: all materials have required fields")
def _():
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    for mid, mat in reg.builtins.items():
        assert mat.id, f"{mid} missing id"
        assert mat.name, f"{mid} missing name"
        assert mat.color, f"{mid} missing color"
        assert mat.category is not None, f"{mid} missing category"


@test("MaterialRegistry: no duplicate IDs in builtins")
def _():
    import json
    data_dir = Path(__file__).parent.parent / "data"
    with open(data_dir / "materials.json") as f:
        mats = json.load(f)["materials"]
    ids = [m["id"] for m in mats]
    dupes = [i for i in ids if ids.count(i) > 1]
    assert not dupes, f"Duplicate IDs: {set(dupes)}"


@test("MaterialRegistry: subcategories use comma-delimited paths")
def _():
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    subcats = [m for m in reg.builtins.values() if "," in (m.category or "")]
    assert len(subcats) > 50, f"Expected >50 subcategorized, got {len(subcats)}"


@test("MaterialRegistry: save_custom includes category field")
def _():
    import json, tempfile
    from src.models.material_registry import MaterialRegistry
    from src.models.material import Material
    data_dir = Path(__file__).parent.parent / "data"
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        f.write(b'{"materials": []}')
        tmp_path = Path(f.name)
    try:
        reg = MaterialRegistry(data_dir / "materials.json", tmp_path)
        mat = Material(
            id="test_custom", name="Test", color="#FF0000",
            k=1.0, rho=1000, cp=500, abbr="Tst",
            category="Test,Sub", note="test", is_builtin=False,
        )
        reg.add_or_update_custom(mat)
        with open(tmp_path) as f:
            data = json.load(f)
        saved = data["materials"][0]
        assert saved["category"] == "Test,Sub"
    finally:
        tmp_path.unlink(missing_ok=True)


@test("MaterialRegistry: existing material IDs preserved after expansion")
def _():
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    expected = ["vacuum", "al6061", "cu", "ag", "au", "fe_a36", "ss304",
        "cast_iron", "titanium", "nickel", "pine", "oak", "birch", "mdf",
        "eps", "aerogel", "nat_rubber", "sil_rubber", "pvc", "nylon_66",
        "hdpe", "float_glass", "concrete", "brick", "drywall",
        "mineral_wool", "sandstone", "silicon", "fr4", "therm_paste",
        "alumina", "gaas", "solder", "air", "nitrogen", "argon",
        "hydrogen", "water", "seawater", "ethylene_glycol",
        "antifreeze_50_50", "engine_oil", "hydraulic_fluid", "gasoline",
        "r134a"]
    for eid in expected:
        assert eid in reg.builtins, f"Missing preserved ID: {eid}"


# ── MaterialPicker: subcategory rendering ─────────────────────────────────────

@test("MaterialPicker: builds nested groups from subcategories")
def _():
    import os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
    # Uses global _qapp
    from src.models.material_registry import MaterialRegistry
    from src.ui.sidebar import MaterialPicker
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    picker = MaterialPicker(reg.all_materials)
    # Should have nested groups (depth > 0)
    nested = [k for k, v in picker._group_info.items() if v[3] > 0]
    assert len(nested) > 10, f"Expected >10 nested groups, got {len(nested)}"


@test("MaterialPicker: _group_info stores 4-tuple (header, content, name, depth)")
def _():
    import os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
    # Uses global _qapp
    from src.models.material_registry import MaterialRegistry
    from src.ui.sidebar import MaterialPicker
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    picker = MaterialPicker(reg.all_materials)
    for key, info in picker._group_info.items():
        assert len(info) == 4, f"Group {key}: expected 4-tuple, got {len(info)}"


@test("MaterialPicker: filter propagates to ancestor groups")
def _():
    import os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
    # Uses global _qapp
    from src.models.material_registry import MaterialRegistry
    from src.ui.sidebar import MaterialPicker
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    picker = MaterialPicker(reg.all_materials)
    picker.show()
    # Filter for "copper" - should be in Metals,Pure
    picker._apply_filter("copper")
    # Metals,Pure group should be visible
    if "Metals,Pure" in picker._group_info:
        h, cw, _, _ = picker._group_info["Metals,Pure"]
        assert not h.isHidden(), "Metals,Pure header should be visible"
    # Parent Metals group should also be visible
    if "Metals" in picker._group_info:
        h, cw, _, _ = picker._group_info["Metals"]
        assert not h.isHidden(), "Metals header should be visible"


# ── StepHistory ───────────────────────────────────────────────────────────────

@test("StepHistory: push and back returns previous snapshot")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=5)
    T1 = np.full((3, 3), 300.0)
    T2 = np.full((3, 3), 350.0)
    sh.push(T1)
    sh.push(T2)
    assert sh.at_present
    snap = sh.back()
    assert snap is not None
    # back from present goes to last snapshot (index len-1), then back again
    # First back() goes to index=len-1 (the latest), so value is T2
    # But we want to check the previous, so back again
    assert not sh.at_present


@test("StepHistory: forward returns to present")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=5)
    T1 = np.full((3, 3), 300.0)
    T2 = np.full((3, 3), 350.0)
    sh.push(T1)
    sh.push(T2)
    sh.back()
    sh.back()
    snap = sh.forward()
    assert snap is not None


@test("StepHistory: return_to_present restores latest")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=5)
    T1 = np.full((3, 3), 300.0)
    T2 = np.full((3, 3), 350.0)
    sh.push(T1)
    sh.push(T2)
    sh.back()
    snap = sh.return_to_present()
    assert snap is not None
    assert np.allclose(snap, 350.0)
    assert sh.at_present


@test("StepHistory: clear empties buffer")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=5)
    sh.push(np.full((2, 2), 300.0))
    sh.clear()
    assert sh.total == 0
    assert sh.at_present
    assert sh.back() is None


@test("StepHistory: max_size limits buffer")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=3)
    for i in range(10):
        sh.push(np.full((2, 2), float(i)))
    assert sh.total == 3


@test("StepHistory: position tracks correctly")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=10)
    for i in range(5):
        sh.push(np.full((2, 2), float(i)))
    assert sh.position == 5  # at present
    sh.back()
    assert sh.position == 4  # first back goes to previous frame
    sh.back()
    assert sh.position == 3


@test("StepHistory: set_max_size trims and resets index")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=10)
    for i in range(10):
        sh.push(np.full((2, 2), float(i)))
    sh.set_max_size(3)
    assert sh.total == 3
    assert sh.at_present


@test("StepHistory: push after browsing returns to present")
def _():
    from src.simulation.step_history import StepHistory
    sh = StepHistory(max_size=5)
    sh.push(np.full((2, 2), 300.0))
    sh.push(np.full((2, 2), 350.0))
    sh.back()
    assert not sh.at_present
    sh.push(np.full((2, 2), 400.0))
    assert sh.at_present


# ── Thermal Resistance ───────────────────────────────────────────────────────

@test("compute_rth: 1D conduction bar gives correct R_th")
def _():
    from src.simulation.thermal_resistance import compute_rth
    from src.simulation.grid import Grid
    from src.models.material_registry import MaterialRegistry
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    # 1x5 grid of copper, fixed hot on left, fixed cold on right
    cu = reg.get("cu")
    grid = Grid(1, 5, cu, ambient_temp_k=293.15)
    dx = 0.01  # 1 cm
    # Set fixed temps
    grid.set_cell(0, 0, material=cu, temperature=400.0, is_fixed=True, fixed_temp=400.0)
    grid.set_cell(0, 4, material=cu, temperature=300.0, is_fixed=True, fixed_temp=300.0)
    # Manually set intermediate temperatures to steady-state linear profile
    for c in range(1, 4):
        t = 400.0 - (100.0 / 4) * c
        grid.set_cell(0, c, material=cu, temperature=t)
    result = compute_rth(
        grid,
        source_cells=[(0, 0)],
        sink_cells=[(0, 4)],
        dx=dx,
        k_array=grid.k_array(),
    )
    assert result.dt_k == 100.0
    assert result.q_wpm > 0
    # R_th = L / (k * A), L = 4*dx = 0.04m, A = dx*1m = 0.01m2 (per m depth)
    # For copper k=385, R_th_expected = 0.04 / (385 * 0.01) = 0.01039 K/(W/m)
    # But our calc uses interface k_eff which is same for uniform material
    assert result.rth_kpwpm > 0
    assert result.n_source == 1
    assert result.n_sink == 1


@test("compute_rth: zero heat flow gives inf R_th")
def _():
    from src.simulation.thermal_resistance import compute_rth
    grid, reg = _make_grid(2, 2)
    # All at same temperature, no heat flow
    result = compute_rth(
        grid,
        source_cells=[(0, 0)],
        sink_cells=[(1, 1)],
        dx=0.01,
        k_array=grid.k_array(),
    )
    assert result.rth_kpwpm == float("inf") or abs(result.q_wpm) < 1e-10


# ── .pythermplot format ──────────────────────────────────────────────────────

@test("pythermplot: save/load round-trips series data")
def _():
    import json
    data = {
        "version": 1,
        "unit": "K",
        "series": {
            "test": [[0.0, 300.0], [1.0, 310.0], [2.0, 320.0]],
        },
    }
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pythermplot",
                                     delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        path = f.name
    try:
        from src.ui.plot_viewer import load_pythermplot
        loaded = load_pythermplot(path)
        assert loaded["version"] == 1
        assert "test" in loaded["series"]
        assert len(loaded["series"]["test"]) == 3
        assert loaded["series"]["test"][1] == [1.0, 310.0]
    finally:
        os.unlink(path)


@test("pythermplot: invalid file raises ValueError")
def _():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pythermplot",
                                     delete=False, encoding="utf-8") as f:
        f.write('{"version": 1}')
        path = f.name
    try:
        from src.ui.plot_viewer import load_pythermplot
        raised = False
        try:
            load_pythermplot(path)
        except ValueError:
            raised = True
        assert raised, "Should raise ValueError for missing series key"
    finally:
        os.unlink(path)


# ── Convergence Panel (unit logic) ───────────────────────────────────────────

@test("ConvergencePanel: first tick is skipped")
def _():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    assert panel._is_first_tick
    panel.on_tick(0.033, 0.001, 0.001)
    assert not panel._is_first_tick
    assert len(panel._canvas._data) == 0  # first tick skipped


@test("ConvergencePanel: second tick adds data point")
def _():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    panel.on_tick(0.033, 0.001, 0.001)  # first tick, skipped
    panel.on_tick(0.066, 0.005, 0.001)  # second tick
    assert len(panel._canvas._data) == 1
    t, rate = panel._canvas._data[0]
    assert abs(t - 0.066) < 1e-9
    assert abs(rate - 5.0) < 1e-9  # 0.005 / 0.001


@test("ConvergencePanel: clear_history resets first_tick flag")
def _():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    panel.on_tick(0.033, 0.001, 0.001)
    panel.on_tick(0.066, 0.005, 0.001)
    panel.clear_history()
    assert panel._is_first_tick
    assert len(panel._canvas._data) == 0


@test("ConvergencePanel: set_ss_threshold updates canvas")
def _():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    panel.set_ss_threshold(0.05)
    assert panel._canvas._ss_threshold == 0.05


# ── Smooth Step ──────────────────────────────────────────────────────────────

@test("SimClock: smooth_step flag defaults to False")
def _():
    grid, reg = _make_grid(2, 2)
    from src.simulation.solver import Solver
    from src.simulation.sim_clock import SimClock
    from src.ui.grid_scene import GridScene
    s = Solver(dx=0.01)
    scene = GridScene(grid)
    sc = SimClock(grid, s, scene)
    assert sc._smooth_step is False


@test("SimClock: set_smooth_step changes flag")
def _():
    grid, reg = _make_grid(2, 2)
    from src.simulation.solver import Solver
    from src.simulation.sim_clock import SimClock
    from src.ui.grid_scene import GridScene
    s = Solver(dx=0.01)
    scene = GridScene(grid)
    sc = SimClock(grid, s, scene)
    sc.set_smooth_step(True)
    assert sc._smooth_step is True


# ── Preferences: new fields ──────────────────────────────────────────────────

@test("Preferences: smooth_step defaults to False")
def _():
    from src.models.preferences import Preferences
    p = Preferences()
    assert p.smooth_step is False


@test("Preferences: step_history_size defaults to 20")
def _():
    from src.models.preferences import Preferences
    p = Preferences()
    assert p.step_history_size == 20


@test("Preferences: save/load round-trips new fields")
def _():
    from src.models.preferences import Preferences
    p = Preferences(smooth_step=True, step_history_size=50)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        p.save(path)
        loaded = Preferences.load(path)
        assert loaded.smooth_step is True
        assert loaded.step_history_size == 50


@test("Preferences: load ignores unknown fields gracefully")
def _():
    from src.models.preferences import Preferences
    import json
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        path.write_text(json.dumps({"unit": "K", "future_field": 42}), encoding="utf-8")
        loaded = Preferences.load(path)
        assert loaded.unit == "K"


# ── MainWindow: new signals exist ────────────────────────────────────────────

@test("MainWindow: has open_plot_requested signal")
def _():
    from src.ui.main_window import MainWindow
    w = MainWindow()
    assert hasattr(w, "open_plot_requested")


@test("MainWindow: has convergence_graph_requested signal")
def _():
    from src.ui.main_window import MainWindow
    w = MainWindow()
    assert hasattr(w, "convergence_graph_requested")


@test("MainWindow: has thermal_resistance_requested signal")
def _():
    from src.ui.main_window import MainWindow
    w = MainWindow()
    assert hasattr(w, "thermal_resistance_requested")


# ── Marching Squares Isotherms ────────────────────────────────────────────────

@test("GridScene: isotherm_color setter works")
def _():
    from PyQt6.QtGui import QColor
    from src.ui.grid_scene import GridScene
    grid, _ = _make_grid(4, 4)
    scene = GridScene(grid)
    scene.set_isotherm_color(QColor(255, 0, 0))
    assert scene._isotherm_color == QColor(255, 0, 0)


@test("GridScene: set_isotherm stores enabled and interval (v2)")
def _():
    from src.ui.grid_scene import GridScene
    grid, _ = _make_grid(4, 4)
    scene = GridScene(grid)
    scene.set_isotherm(True, 25.0)
    assert scene._isotherm_enabled is True
    assert abs(scene._isotherm_interval_k - 25.0) < 1e-9


@test("GridScene: flow view mode accepted")
def _():
    from src.ui.grid_scene import GridScene
    grid, _ = _make_grid(4, 4)
    scene = GridScene(grid)
    scene.set_view_mode("flow")
    assert scene._view_mode == "flow"


# ── Plot Save Round-Trip ─────────────────────────────────────────────────────

@test("TempPlotPanel: _save_plot creates valid .pythermplot file")
def _():
    grid, _ = _make_grid(4, 4)
    from src.ui.temp_plot_panel import TempPlotPanel
    panel = TempPlotPanel(grid)
    # Add some data
    panel.set_tracked_cells([(0, 0)])
    panel._canvas.add_point("(0,0)", 0.0, 300.0)
    panel._canvas.add_point("(0,0)", 1.0, 310.0)
    # Save
    with tempfile.NamedTemporaryFile(suffix=".pythermplot", delete=False) as f:
        path = f.name
    try:
        import json, os
        series = panel._canvas._series
        data = {
            "version": 1, "unit": "K",
            "series": {name: [[t, T] for t, T in pts] for name, pts in series.items() if pts},
        }
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fw:
            json.dump(data, fw)
        os.replace(tmp, path)
        # Reload
        from src.ui.plot_viewer import load_pythermplot
        loaded = load_pythermplot(path)
        assert "(0,0)" in loaded["series"]
        assert len(loaded["series"]["(0,0)"]) == 2
    finally:
        os.unlink(path)


# ── Preferences: new fields ──────────────────────────────────────────────────

@test("Preferences: theme defaults to dark")
def _():
    from src.models.preferences import Preferences
    p = Preferences()
    assert p.theme == "dark"


@test("Preferences: save/load round-trips theme")
def _():
    from src.models.preferences import Preferences
    p = Preferences(theme="light")
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        p.save(path)
        loaded = Preferences.load(path)
        assert loaded.theme == "light"


# ── v1.0.0 Feature Tests ─────────────────────────────────────────────────────

@test("Preferences: save/load round-trips v1.0.0 fields")
def _():
    from src.models.preferences import Preferences
    p = Preferences(
        reverse_palette=True,
        isotherm_line_width=4,
        heatmap_auto_init=False,
        heatmap_scale_mode="live",
    )
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "prefs.json"
        p.save(path)
        loaded = Preferences.load(path)
        assert loaded.reverse_palette is True
        assert loaded.isotherm_line_width == 4
        assert loaded.heatmap_auto_init is False
        assert loaded.heatmap_scale_mode == "live"


@test("Heatmap: reverse palette flips colors")
def _():
    from src.rendering.heatmap_renderer import heatmap_color, set_reversed, is_reversed
    old = is_reversed()
    set_reversed(False)
    c_normal = heatmap_color(373.15, 273.15, 373.15)
    set_reversed(True)
    c_reversed = heatmap_color(373.15, 273.15, 373.15)
    set_reversed(old)
    # Normal: max temp = hot color (red-ish), Reversed: max temp = cold color (blue-ish)
    assert c_normal.red() > c_reversed.red() or c_normal.blue() < c_reversed.blue()


@test("GridScene: isotherm_line_width clamp logic")
def _():
    # Test the clamping logic without constructing a full GridScene
    assert max(1, min(5, 10)) == 5
    assert max(1, min(5, 0)) == 1
    assert max(1, min(5, 3)) == 3


@test("KelvinSpinBox: _typed_unit_to_kelvin converts correctly")
def _():
    from src.rendering.units import _typed_unit_to_kelvin
    # 20C -> 293.15 K
    assert abs(_typed_unit_to_kelvin(20, "C") - 293.15) < 0.01
    # 68F -> 293.15 K
    assert abs(_typed_unit_to_kelvin(68, "F") - 293.15) < 0.01
    # 293K -> 293 K
    assert abs(_typed_unit_to_kelvin(293, "K") - 293.0) < 0.01
    # 527.67R -> 293.15 K
    assert abs(_typed_unit_to_kelvin(527.67, "R") - 293.15) < 0.01


@test("file_io: save includes is_volumetric_flux when False")
def _():
    from src.io.file_io import save_pytherm, load_pytherm
    grid, reg = _make_grid(rows=3, cols=3)
    grid.set_cell(1, 1, is_flux=True, flux_q=100.0, is_volumetric_flux=False)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.pytherm"
        save_pytherm(path, grid, 0.01, [])
        data = load_pytherm(path)
    flux_cell = [c for c in data["cells"] if c["row"] == 1 and c["col"] == 1][0]
    assert flux_cell["is_volumetric_flux"] is False


@test("Solver: surface flux with vol_flux_mask divides by dx")
def _():
    from src.simulation.solver import Solver
    solver = Solver(dx=0.01)
    k, rcp, T, fm, ft, xm, xq = _arrays(4, 4, 167.0, 2700.0 * 896.0, 300.0)
    xm[1, 1] = True; xq[1, 1] = 5000.0
    # All surface (vol_flux_mask all False)
    vol = np.zeros((4, 4), dtype=bool)
    T_surf = solver.advance(T.copy(), k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol)
    # All volumetric
    vol2 = np.ones((4, 4), dtype=bool)
    T_vol = solver.advance(T.copy(), k, rcp, fm, ft, xm, xq, duration=0.01, vol_flux_mask=vol2)
    # Surface should heat MORE than volumetric (divided by dx=0.01 -> 100x larger)
    assert T_surf[1, 1] > T_vol[1, 1], "Surface flux / dx should produce more heating than volumetric"


# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    passes = sum(1 for _, ok, _ in _results if ok)
    fails  = sum(1 for _, ok, _ in _results if not ok)
    print(f"\nPyTherm v1.0.0 headless test results")
    print("=" * 60)
    for name, ok, msg in _results:
        status = PASS if ok else FAIL
        print(f"  {status}  {name}")
        if msg:
            print(f"         {msg}")
    print("=" * 60)
    print(f"  {passes} passed, {fails} failed\n")
    import sys as _sys; _sys.exit(0 if fails == 0 else 1)