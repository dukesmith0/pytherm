"""Tests for src.simulation.cell.Cell dataclass."""
from __future__ import annotations

from src.simulation.cell import Cell
from src.models.material import Material


def _vac():
    return Material(id="vacuum", name="Vacuum", color="#111", k=0, rho=0, cp=0, is_builtin=True)


def test_flux_defaults():
    c = Cell(material=_vac(), temperature=300.0)
    assert c.is_flux is False and c.flux_q == 0.0


def test_flux_settable():
    c = Cell(material=_vac(), temperature=300.0, is_flux=True, flux_q=500.0)
    assert c.is_flux is True and c.flux_q == 500.0


def test_protected_default():
    c = Cell(material=_vac(), temperature=293.15)
    assert c.protected is False
