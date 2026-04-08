"""Tests for src.io.file_io save/load and validation."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from src.io.file_io import save_pytherm, load_pytherm, _validate_pytherm


def test_save_load_flux(make_grid):
    grid, reg = make_grid(rows=3, cols=3)
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
    assert cells[(1, 1)]["is_flux"] is True and abs(cells[(1, 1)]["flux_q"] - 2500.0) < 1e-9
    assert cells[(0, 0)]["is_fixed"] is True
    assert cells[(0, 1)]["is_flux"] is False


def test_old_file_without_flux():
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


def test_save_includes_version_and_sim_settings(make_grid):
    grid, _ = make_grid(rows=2, cols=2)
    with tempfile.NamedTemporaryFile(suffix=".pytherm", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        sim_settings = {"boundary_conditions": {"top": "sink", "bottom": "insulator",
                                                "left": "insulator", "right": "insulator"}}
        save_pytherm(tmp_path, grid, 0.01, [], sim_settings=sim_settings)
        data = load_pytherm(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    from src.version import VERSION
    assert data["software_version"] == VERSION
    assert data["sim_settings"]["boundary_conditions"]["top"] == "sink"


def test_old_file_without_sim_settings():
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
    assert loaded.get("sim_settings", {}) == {}
    assert loaded.get("software_version") is None


def test_validate_raises_missing_version():
    import pytest
    with pytest.raises(ValueError, match="(?i)version"):
        _validate_pytherm({"grid": {}, "cells": []}, require_version=True)


def test_validate_accepts_missing_version_template():
    _validate_pytherm(
        {"grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01}, "cells": []},
        require_version=False,
    )


def test_validate_raises_missing_grid():
    import pytest
    with pytest.raises(ValueError, match="(?i)grid"):
        _validate_pytherm({"version": 1, "cells": []})


def test_validate_raises_non_list_cells():
    import pytest
    with pytest.raises(ValueError, match="(?i)cells"):
        _validate_pytherm({
            "version": 1,
            "grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
            "cells": "bad",
        })


def test_validate_raises_missing_grid_subkeys():
    import pytest
    with pytest.raises(ValueError):
        _validate_pytherm({"version": 1, "grid": {"rows": 2}, "cells": []})


def test_validate_passes_valid():
    _validate_pytherm({
        "version": 1,
        "grid": {"rows": 2, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
        "cells": [],
    })


def test_save_protected(make_grid):
    grid, reg = make_grid(2, 2)
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
        assert "protected" not in cells_by_rc[(0, 1)]
    finally:
        path.unlink(missing_ok=True)


def test_save_is_volumetric_flux(make_grid):
    grid, _ = make_grid(rows=3, cols=3)
    grid.set_cell(1, 1, is_flux=True, flux_q=100.0, is_volumetric_flux=False)
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "test.pytherm"
        save_pytherm(path, grid, 0.01, [])
        data = load_pytherm(path)
    flux_cell = [c for c in data["cells"] if c["row"] == 1 and c["col"] == 1][0]
    assert flux_cell["is_volumetric_flux"] is False


# ── Dimension validation (v1.1.0 security hardening) ────────────────────────

def test_validate_rejects_rows_below_1():
    import pytest
    with pytest.raises(ValueError):
        _validate_pytherm({
            "version": 1,
            "grid": {"rows": 0, "cols": 2, "ambient_temp_k": 293.15, "dx_m": 0.01},
            "cells": [],
        })


def test_validate_rejects_cols_above_200():
    import pytest
    with pytest.raises(ValueError):
        _validate_pytherm({
            "version": 1,
            "grid": {"rows": 10, "cols": 201, "ambient_temp_k": 293.15, "dx_m": 0.01},
            "cells": [],
        })


def test_validate_accepts_1x1():
    _validate_pytherm({
        "version": 1,
        "grid": {"rows": 1, "cols": 1, "ambient_temp_k": 293.15, "dx_m": 0.01},
        "cells": [],
    })


def test_validate_accepts_200x200():
    _validate_pytherm({
        "version": 1,
        "grid": {"rows": 200, "cols": 200, "ambient_temp_k": 293.15, "dx_m": 0.01},
        "cells": [],
    })
