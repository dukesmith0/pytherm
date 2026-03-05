from __future__ import annotations

import json
import os
from pathlib import Path

from src.models.material import Material
from src.simulation.grid import Grid

PYTHERM_VERSION = 1


def save_pytherm(
    path: Path,
    grid: Grid,
    solver_dx: float,
    custom_materials: list[Material],
) -> None:
    """Serialize the current grid layout to a .pytherm JSON file."""
    cells = []
    for r in range(grid.rows):
        for c in range(grid.cols):
            cell = grid.cell(r, c)
            cells.append({
                "row": r,
                "col": c,
                "material_id": cell.material.id,
                "temperature_k": cell.temperature,
                "is_fixed": cell.is_fixed,
                "fixed_temp_k": cell.fixed_temp,
            })

    data = {
        "version": PYTHERM_VERSION,
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


def load_pytherm(path: Path) -> dict:
    """Load and return the raw data from a .pytherm file.

    Raises ValueError if the file format version is unrecognised.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    file_ver = data.get("version", 0)
    if file_ver > PYTHERM_VERSION:
        raise ValueError(
            f"File was saved by a newer version of PyTherm (format version {file_ver}). "
            f"Please update to the latest release."
        )
    return data
