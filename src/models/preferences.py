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
    heatmap_auto_init: bool = True
    heatmap_scale_mode: str = "smart"  # "static" | "live" | "smart"
    smooth_step: bool = False
    step_history_size: int = 20
    isotherm_color: str = "#E6E6E6"
    isotherm_line_width: int = 2
    reverse_palette: bool = False
    plot_every_n_ticks: int = 1
    theme: str = "dark"

    _VALID_UNITS = {"\u00b0C", "K", "\u00b0F", "R"}

    @classmethod
    def load(cls, path: Path) -> "Preferences":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = set(cls.__dataclass_fields__)
            p = cls(**{k: v for k, v in data.items() if k in known})
            if p.unit not in cls._VALID_UNITS:
                p.unit = "\u00b0C"
            p._clamp()
            return p
        except Exception:
            return cls()

    def _clamp(self) -> None:
        """Ensure loaded values fall within valid ranges."""
        def _c(val: float, lo: float, hi: float) -> float:
            return max(lo, min(hi, val))

        self.ambient_temp_k = _c(self.ambient_temp_k, 0.0, 10_000.0)
        self.default_rows = int(_c(self.default_rows, 1, 200))
        self.default_cols = int(_c(self.default_cols, 1, 200))
        self.default_dx_m = _c(self.default_dx_m, 0.01, 100.0)
        self.sim_speed = _c(self.sim_speed, 0.1, 1000.0)
        self.max_undo_steps = int(_c(self.max_undo_steps, 1, 500))
        self.max_plot_points = int(_c(self.max_plot_points, 50, 5000))
        self.ss_threshold_k_per_s = _c(self.ss_threshold_k_per_s, 0.0001, 100.0)
        self.min_auto_heatmap_range_k = _c(self.min_auto_heatmap_range_k, 0.1, 10_000.0)
        self.step_history_size = int(_c(self.step_history_size, 5, 200))
        self.isotherm_line_width = int(_c(self.isotherm_line_width, 1, 5))
        self.plot_every_n_ticks = int(_c(self.plot_every_n_ticks, 1, 100))
        if self.heatmap_scale_mode not in ("static", "live", "smart"):
            self.heatmap_scale_mode = "smart"
        if self.theme not in ("dark", "light"):
            self.theme = "dark"

    def save(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
            os.replace(tmp, path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
