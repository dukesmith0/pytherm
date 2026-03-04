from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    color: str   # hex string, e.g. "#B87333"
    k: float     # thermal conductivity  W/(m·K)
    rho: float   # density               kg/m³
    cp: float    # specific heat         J/(kg·K)

    @property
    def alpha(self) -> float:
        # Thermal diffusivity α = k / (ρ × Cₚ)  [m²/s]
        # This is the single number that governs how fast temperature
        # changes spread through a material — high α means fast spread.
        return self.k / (self.rho * self.cp)


def load_materials(path: str | Path) -> dict[str, Material]:
    """Load all materials from a JSON file, keyed by material id."""
    with open(path) as f:
        data = json.load(f)
    return {
        entry["id"]: Material(**entry)
        for entry in data["materials"]
    }
