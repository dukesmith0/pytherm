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
                 is_volumetric_flux: bool | None = None,
                 label: str | None = None,
                 protected: bool | None = None) -> None:
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
        if is_volumetric_flux is not None:
            c.is_volumetric_flux = is_volumetric_flux
        if label is not None:
            c.label = label
        if protected is not None:
            c.protected = protected

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
        α = k / (ρ × Cₚ) -- governs how fast temperature changes propagate."""
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
        """Heat source values. Units depend on is_volumetric_flux: W/m^2 (surface) or W/m^3 (volumetric)."""
        return np.array(
            [[c.flux_q for c in row] for row in self._cells],
            dtype=np.float64,
        )

    def volumetric_flux_mask(self) -> np.ndarray:
        """Boolean array: True where flux cells use volumetric (W/m^3) mode."""
        return np.array(
            [[c.is_volumetric_flux for c in row] for row in self._cells],
            dtype=bool,
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
            [(c.material, c.temperature, c.is_fixed, c.fixed_temp, c.is_flux, c.flux_q,
              c.label, c.protected, c.is_volumetric_flux)
             for c in row]
            for row in self._cells
        ]

    def restore(self, snap: list[list[tuple]]) -> None:
        """Restore cell state from a snapshot produced by snapshot()."""
        for r, row in enumerate(snap):
            for col, tup in enumerate(row):
                mat, temp, is_fixed, fixed_temp, is_flux, flux_q = tup[:6]
                lbl = tup[6] if len(tup) > 6 else ""
                prot = tup[7] if len(tup) > 7 else False
                vol = tup[8] if len(tup) > 8 else False
                self.set_cell(r, col,
                              material=mat,
                              temperature=temp,
                              is_fixed=is_fixed,
                              fixed_temp=fixed_temp,
                              is_flux=is_flux,
                              flux_q=flux_q,
                              label=lbl,
                              protected=prot,
                              is_volumetric_flux=vol)

    def resize(self, top: int, right: int, bottom: int, left: int,
               vacuum_material: Material) -> None:
        """Expand or trim grid edges. Positive = add rows/cols, negative = trim.
        New cells are filled with vacuum at ambient temperature.
        Clamped so at least 1 row and 1 col remain."""
        def _new_cell() -> Cell:
            return Cell(material=vacuum_material, temperature=self.ambient_temp_k,
                        fixed_temp=self.ambient_temp_k)

        trim_top    = min(max(0, -top),    max(0, self.rows - 1))
        trim_bottom = min(max(0, -bottom), max(0, self.rows - trim_top - 1))
        trim_left   = min(max(0, -left),   max(0, self.cols - 1))
        trim_right  = min(max(0, -right),  max(0, self.cols - trim_left - 1))
        add_top     = max(0, top)
        add_bottom  = max(0, bottom)
        add_left    = max(0, left)
        add_right   = max(0, right)

        # Trim rows from top/bottom
        end = self.rows - trim_bottom if trim_bottom else None
        cells = self._cells[trim_top:end]

        # Trim/expand columns in each row
        new_col_count = self.cols - trim_left - trim_right + add_left + add_right
        trimmed_rows = []
        for row in cells:
            end_c = len(row) - trim_right if trim_right else None
            trimmed = row[trim_left:end_c]
            trimmed_rows.append(
                [_new_cell() for _ in range(add_left)] + trimmed + [_new_cell() for _ in range(add_right)]
            )
        cells = trimmed_rows

        # Add top/bottom rows
        new_row = lambda: [_new_cell() for _ in range(new_col_count)]
        cells = [new_row() for _ in range(add_top)] + cells + [new_row() for _ in range(add_bottom)]

        self._cells = cells
        self.rows = len(cells)
        self.cols = len(cells[0]) if cells else 0

    def import_temperatures(self, T: np.ndarray) -> None:
        """Write solver output temperatures back into cells.
        The solver already re-pins fixed cells before returning, so no special casing needed."""
        for r, row in enumerate(self._cells):
            for col, c in enumerate(row):
                c.temperature = float(T[r, col])
