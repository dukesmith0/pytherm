from __future__ import annotations

from dataclasses import dataclass

from src.models.material import Material


@dataclass
class Cell:
    material: Material
    temperature: float   # Kelvin — always stored internally in Kelvin
    is_fixed: bool = False
    fixed_temp: float = 0.0  # Kelvin — the pinned temperature if is_fixed is True
