from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from src.simulation.grid import Grid


@dataclass
class RthResult:
    """Result of a thermal resistance calculation."""
    dt_k: float          # temperature difference (K)
    q_wpm: float         # heat flow rate (W per metre depth)
    rth_kpwpm: float     # thermal resistance (K/W per metre depth)
    t_source_avg_k: float
    t_sink_avg_k: float
    n_source: int
    n_sink: int


def compute_rth(
    grid: Grid,
    source_cells: list[tuple[int, int]],
    sink_cells: list[tuple[int, int]],
    dx: float,
    k_array: np.ndarray,
) -> RthResult:
    """Compute thermal resistance between source and sink cell groups.

    R_th = dT / Q  (K per W per metre depth)

    dT = mean(T_source) - mean(T_sink)
    Q  = net heat flow from source cells into the grid (W/m).

    For fixed-T source cells, Q is computed from the conductive flux at
    cell interfaces. For non-fixed sources, Q uses the last-tick energy.
    This function should be called at or near steady state for meaningful
    results.
    """
    T = grid.temperature_array()

    # Source and sink average temperatures
    source_temps = np.array([T[r, c] for r, c in source_cells])
    sink_temps = np.array([T[r, c] for r, c in sink_cells])
    t_source_avg = float(source_temps.mean())
    t_sink_avg = float(sink_temps.mean())
    dt = t_source_avg - t_sink_avg

    # Compute Q: net heat flow from source cells via interface conduction
    dx2 = dx ** 2
    rows, cols = T.shape

    def _hm(a: float, b: float) -> float:
        s = a + b
        return 2.0 * a * b / s if s > 0 else 0.0

    q_total = 0.0
    source_set = set(source_cells)
    for r, c in source_cells:
        k_center = float(k_array[r, c])
        if k_center == 0:
            continue
        # Sum flux from this source cell to all neighbors NOT in source set
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in source_set:
                k_n = float(k_array[nr, nc])
                k_eff = _hm(k_center, k_n)
                # Heat flow = k_eff * (T_source - T_neighbor) [W/m]
                # (flux/dx cancels with dx cell face area per unit depth)
                q_total += k_eff * (T[r, c] - T[nr, nc])

    # q_total is in W/m (per metre depth)
    rth = dt / q_total if abs(q_total) > 1e-15 else float("inf")

    return RthResult(
        dt_k=dt,
        q_wpm=q_total,
        rth_kpwpm=rth,
        t_source_avg_k=t_source_avg,
        t_sink_avg_k=t_sink_avg,
        n_source=len(source_cells),
        n_sink=len(sink_cells),
    )
