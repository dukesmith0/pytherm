from __future__ import annotations

from dataclasses import dataclass

from src.models.material import Material


@dataclass
class Cell:
    material: Material
    temperature: float   # Kelvin — always stored internally in Kelvin
    is_fixed: bool = False
    fixed_temp: float = 0.0  # Kelvin — the pinned temperature if is_fixed is True
    is_flux: bool = False
    flux_q: float = 0.0  # W/m² — constant heat flux if is_flux is True (positive = into cell)
    label: str = ""      # Optional display label (max 8 chars); shared label = visual group
