from __future__ import annotations

import numpy as np

from src.models.material import Material
from src.simulation.cell import Cell


class Grid:
    def __init__(self, rows: int, cols: int, default_material: Material, ambient_temp_k: float):
        self.rows = rows
        self.cols = cols
        self.ambient_temp_k = ambient_temp_k
        self._cells: list[list[Cell]] = [
            [Cell(material=default_material, temperature=ambient_temp_k, fixed_temp=ambient_temp_k)
             for _ in range(cols)]
            for _ in range(rows)
        ]

    def cell(self, row: int, col: int) -> Cell:
        return self._cells[row][col]

    def set_cell(self, row: int, col: int, *,
                 material: Material | None = None,
                 temperature: float | None = None,
                 is_fixed: bool | None = None,
                 fixed_temp: float | None = None,
                 is_flux: bool | None = None,
                 flux_q: float | None = None,
                 label: str | None = None) -> None:
        c = self._cells[row][col]
        if material is not None:
            c.material = material
        if temperature is not None:
            c.temperature = temperature
        if is_fixed is not None:
            c.is_fixed = is_fixed
        if fixed_temp is not None:
            c.fixed_temp = fixed_temp
        if is_flux is not None:
            c.is_flux = is_flux
        if flux_q is not None:
            c.flux_q = flux_q
        if label is not None:
            c.label = label

    def reset_temperatures(self) -> None:
        """Reset simulated temperatures to ambient. Preserves materials and heat source configs."""
        for row in self._cells:
            for c in row:
                c.temperature = self.ambient_temp_k

    # --- NumPy interface for the solver ---

    def temperature_array(self) -> np.ndarray:
        """Export temperatures as a (rows, cols) float64 array."""
        return np.array(
            [[c.temperature for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def alpha_array(self) -> np.ndarray:
        """Export thermal diffusivities as a (rows, cols) float64 array.
        α = k / (ρ × Cₚ) — governs how fast temperature changes propagate."""
        return np.array(
            [[c.material.alpha for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def k_array(self) -> np.ndarray:
        """Export thermal conductivities as a (rows, cols) float64 array."""
        return np.array(
            [[c.material.k for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def rho_cp_array(self) -> np.ndarray:
        """Export volumetric heat capacity (ρ·Cₚ) as a (rows, cols) float64 array."""
        return np.array(
            [[c.material.rho * c.material.cp for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def fixed_mask(self) -> np.ndarray:
        """Boolean array: True where cells hold a constant temperature."""
        return np.array(
            [[c.is_fixed for c in row] for row in self._cells],
            dtype=bool,
        )

    def fixed_temps_array(self) -> np.ndarray:
        """Fixed temperatures in Kelvin. Only meaningful where fixed_mask is True."""
        return np.array(
            [[c.fixed_temp for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def flux_mask(self) -> np.ndarray:
        """Boolean array: True where cells inject a constant heat flux."""
        return np.array(
            [[c.is_flux for c in row] for row in self._cells],
            dtype=bool,
        )

    def flux_q_array(self) -> np.ndarray:
        """Heat flux values in W/m². Only meaningful where flux_mask is True."""
        return np.array(
            [[c.flux_q for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def replace_material(self, old_id: str, new_material: Material) -> None:
        """Replace every cell using old_id with new_material."""
        for row in self._cells:
            for c in row:
                if c.material.id == old_id:
                    c.material = new_material

    def snapshot(self) -> list[list[tuple]]:
        """Return a deep-copyable snapshot of all cell state."""
        return [
            [(c.material, c.temperature, c.is_fixed, c.fixed_temp, c.is_flux, c.flux_q, c.label)
             for c in row]
            for row in self._cells
        ]

    def restore(self, snap: list[list[tuple]]) -> None:
        """Restore cell state from a snapshot produced by snapshot()."""
        for r, row in enumerate(snap):
            for col, tup in enumerate(row):
                mat, temp, is_fixed, fixed_temp, is_flux, flux_q = tup[:6]
                lbl = tup[6] if len(tup) > 6 else ""
                self.set_cell(r, col,
                              material=mat,
                              temperature=temp,
                              is_fixed=is_fixed,
                              fixed_temp=fixed_temp,
                              is_flux=is_flux,
                              flux_q=flux_q,
                              label=lbl)

    def import_temperatures(self, T: np.ndarray) -> None:
        """Write solver output temperatures back into cells.
        The solver already re-pins fixed cells before returning, so no special casing needed."""
        for r, row in enumerate(self._cells):
            for col, c in enumerate(row):
                c.temperature = float(T[r, col])
