from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Preferences:
    unit: str = "\u00b0C"
    ambient_temp_k: float = 293.15
    default_rows: int = 10
    default_cols: int = 10
    default_dx_m: float = 0.01
    sim_speed: float = 1.0
    max_undo_steps: int = 50
    max_plot_points: int = 500
    ss_threshold_k_per_s: float = 0.01
    min_auto_heatmap_range_k: float = 10.0
    smooth_step: bool = False
    step_history_size: int = 20
    isotherm_color: str = "#E6E6E6"
    plot_every_n_ticks: int = 1

    _VALID_UNITS = {"\u00b0C", "K", "\u00b0F", "R"}

    @classmethod
    def load(cls, path: Path) -> "Preferences":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = set(cls.__dataclass_fields__)
            p = cls(**{k: v for k, v in data.items() if k in known})
            if p.unit not in cls._VALID_UNITS:
                p.unit = "\u00b0C"
            return p
        except Exception:
            return cls()

    def save(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(tmp, path)
