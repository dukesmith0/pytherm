"""Shared fixtures for PyTherm test suite."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Single QApplication for all tests (must exist before any Qt widget import)
from PyQt6.QtWidgets import QApplication
_qapp = QApplication.instance() or QApplication(sys.argv)


DATA_DIR = Path(__file__).parent.parent / "data"


@pytest.fixture
def make_grid():
    """Factory fixture: returns (grid, registry) with vacuum-filled grid."""
    from src.simulation.grid import Grid
    from src.models.material_registry import MaterialRegistry

    def _make(rows=4, cols=4):
        reg = MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")
        grid = Grid(rows, cols, reg.get("vacuum"), ambient_temp_k=293.15)
        return grid, reg

    return _make


@pytest.fixture
def registry():
    from src.models.material_registry import MaterialRegistry
    return MaterialRegistry(DATA_DIR / "materials.json", DATA_DIR / "user_materials.json")


@pytest.fixture
def solver():
    from src.simulation.solver import Solver
    return Solver(dx=0.01)


def make_arrays(rows, cols, k_val, rhocp_val, T_val):
    """Create uniform test arrays for solver tests."""
    k      = np.full((rows, cols), k_val)
    rho_cp = np.full((rows, cols), rhocp_val)
    T      = np.full((rows, cols), T_val, dtype=float)
    fm  = np.zeros((rows, cols), dtype=bool)
    ft  = np.zeros((rows, cols))
    xm  = np.zeros((rows, cols), dtype=bool)
    xq  = np.zeros((rows, cols))
    return k, rho_cp, T, fm, ft, xm, xq
