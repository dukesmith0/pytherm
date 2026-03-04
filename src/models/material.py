from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Material:
    id: str
    name: str
    color: str       # hex string, e.g. "#B87333"
    k: float         # thermal conductivity  W/(m·K)
    rho: float       # density               kg/m³
    cp: float        # specific heat         J/(kg·K)
    note: str = ""   # optional user note, max 100 chars
    abbr: str = ""   # 1–4 char label shown in cell corner (e.g. "Cu", "FR4", "A36")
    category: str = ""   # display group, e.g. "Metals" (empty = ungrouped / top-level)
    is_builtin: bool = False

    @property
    def alpha(self) -> float:
        # Thermal diffusivity α = k / (ρ × Cₚ)  [m²/s]
        # Returns 0 for vacuum/inert materials (k=rho=cp=0) — no heat transport.
        denom = self.rho * self.cp
        return 0.0 if denom == 0 else self.k / denom

    @property
    def is_vacuum(self) -> bool:
        """True for thermally inert materials (k=ρ=Cₚ=0) — perfect insulators."""
        return self.rho == 0 and self.cp == 0


def load_materials(path: str | Path, *, is_builtin: bool = False) -> dict[str, Material]:
    """Load materials from a JSON file, keyed by material id."""
    with open(path) as f:
        data = json.load(f)
    return {
        entry["id"]: Material(**entry, is_builtin=is_builtin)
        for entry in data["materials"]
    }
