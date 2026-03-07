from __future__ import annotations

import json
import os
from pathlib import Path

from src.models.material import Material
from src.simulation.grid import Grid
from src.version import VERSION

PYTHERM_VERSION = 1


def save_pytherm(
    path: Path,
    grid: Grid,
    solver_dx: float,
    custom_materials: list[Material],
    sim_settings: dict | None = None,
) -> None:
    """Serialize the current grid layout to a .pytherm JSON file."""
    cells = []
    for r in range(grid.rows):
        for c in range(grid.cols):
            cell = grid.cell(r, c)
            entry: dict = {
                "row": r,
                "col": c,
                "material_id": cell.material.id,
                "temperature_k": cell.temperature,
                "is_fixed": cell.is_fixed,
                "fixed_temp_k": cell.fixed_temp,
                "is_flux": cell.is_flux,
                "flux_q": cell.flux_q,
            }
            if cell.label:
                entry["label"] = cell.label
            cells.append(entry)

    data = {
        "version": PYTHERM_VERSION,
        "software_version": VERSION,
        "sim_settings": sim_settings or {},
        "grid": {
            "rows": grid.rows,
            "cols": grid.cols,
            "ambient_temp_k": grid.ambient_temp_k,
            "dx_m": solver_dx,
        },
        "cells": cells,
        "custom_materials": [
            {
                "id": m.id,
                "name": m.name,
                "color": m.color,
                "k": m.k,
                "rho": m.rho,
                "cp": m.cp,
                "note": m.note,
            }
            for m in custom_materials
        ],
    }

    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _validate_pytherm(data: dict) -> None:
    """Raise ValueError with a descriptive message if the file structure is invalid."""
    for key in ("version", "grid", "cells"):
        if key not in data:
            raise ValueError(f"Missing required field: '{key}'")
    if not isinstance(data["grid"], dict):
        raise ValueError("Field 'grid' must be an object")
    for key in ("rows", "cols", "ambient_temp_k", "dx_m"):
        if key not in data["grid"]:
            raise ValueError(f"Missing required field: 'grid.{key}'")
    if not isinstance(data["cells"], list):
        raise ValueError("Field 'cells' must be an array")


def load_pytherm(path: Path) -> dict:
    """Load and return the raw data from a .pytherm file.

    Raises ValueError if the file format version is unrecognised or structure is invalid.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    _validate_pytherm(data)
    file_ver = data.get("version", 0)
    if file_ver > PYTHERM_VERSION:
        raise ValueError(
            f"File was saved by a newer version of PyTherm (format version {file_ver}). "
            f"Please update to the latest release."
        )
    return data
