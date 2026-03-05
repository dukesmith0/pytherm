from __future__ import annotations

import numpy as np

# Boundary condition string constants
INSULATOR = "insulator"  # zero heat-flux (Neumann): ghost cell = edge cell
SINK      = "sink"       # ambient-temperature (Dirichlet): ghost cell = ambient_k

_DEFAULT_BC: dict[str, str] = {
    "top": INSULATOR, "bottom": INSULATOR,
    "left": INSULATOR, "right": INSULATOR,
}


def _hm(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Harmonic mean of two conductivity arrays at a cell interface."""
    s = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(s > 0, 2 * a * b / s, 0.0)


def _pad_with_bc(T: np.ndarray, bc: dict[str, str], ambient_k: float) -> np.ndarray:
    """Manual per-side padding that respects boundary conditions.

    Insulator → ghost cell copies the edge cell (∂T/∂n = 0).
    Sink      → ghost cell is held at ambient_k (T = T_ambient).
    Corners always copy the nearest edge cell (insulator behaviour).
    """
    rows, cols = T.shape
    P = np.empty((rows + 2, cols + 2), dtype=T.dtype)
    P[1:-1, 1:-1] = T

    P[0,    1:-1] = ambient_k if bc.get("top")    == SINK else T[0, :]
    P[-1,   1:-1] = ambient_k if bc.get("bottom") == SINK else T[-1, :]
    P[1:-1, 0]    = ambient_k if bc.get("left")   == SINK else T[:, 0]
    P[1:-1, -1]   = ambient_k if bc.get("right")  == SINK else T[:, -1]

    # Corners: edge-mode (no diagonal heat flux in 4-neighbour FDM)
    P[0,  0]  = T[0,  0];  P[0,  -1] = T[0,  -1]
    P[-1, 0]  = T[-1, 0];  P[-1, -1] = T[-1, -1]

    return P


class Solver:
    """2D explicit finite-difference heat conduction solver for heterogeneous materials.

    Correct form of the heterogeneous heat equation:
        (ρCₚ)ᵢ · dTᵢ/dt = Σⱼ k_eff_ij · (Tⱼ − Tᵢ) / dx²

    where k_eff_ij = 2·kᵢ·kⱼ / (kᵢ + kⱼ) is the harmonic mean conductivity at the
    interface between cells i and j.  Dividing by (ρCₚ)ᵢ of the centre cell (not an
    interface average) correctly captures the energy stored in each cell.
    """

    def __init__(self, dx: float):
        # dx: physical size of each square cell in meters
        self.dx = dx
        self.last_substep_count = 0   # set after each advance(), useful for debugging
        self.last_max_delta = 0.0     # max per-sub-step |ΔT| over non-fixed cells
        self.last_e_from_fixed = 0.0  # energy injected by fixed-T cells in last advance() [J/m]
        self.last_e_from_sinks = 0.0  # energy exchanged via sink BCs in last advance() [J/m]
        self.boundary_conditions: dict[str, str] = dict(_DEFAULT_BC)
        self.ambient_k: float = 293.15

    def advance(self,
                T: np.ndarray,
                k: np.ndarray,
                rho_cp: np.ndarray,
                fixed_mask: np.ndarray,
                fixed_temps: np.ndarray,
                duration: float) -> np.ndarray:
        """Advance the temperature field by `duration` simulated seconds.

        Internally sub-steps to satisfy the CFL stability condition:
            dt_safe ≤ 0.9 · dx² · min(ρCₚ) / (4 · k_max)
        where min(ρCₚ) is taken over non-vacuum cells only.

        Returns a new array — does not modify the input T.
        """
        T = T.copy()

        k_max = k.max()
        if k_max == 0:
            self.last_e_from_fixed = 0.0
            self.last_e_from_sinks = 0.0
            return T

        rhocp_nonzero = rho_cp[rho_cp > 0]
        if rhocp_nonzero.size == 0:
            self.last_e_from_fixed = 0.0
            self.last_e_from_sinks = 0.0
            return T
        rhocp_min = rhocp_nonzero.min()

        # CFL stability condition for the heterogeneous explicit FDM.
        # Derived from: dt ≤ dx² · (ρCₚ)_i / (Σ k_eff_ij) for all cells i.
        # Worst case: (ρCₚ)_i = min non-vacuum, and all 4 k_eff = k_max.
        dt_safe = 0.9 * self.dx ** 2 * rhocp_min / (4.0 * k_max)
        n_steps = max(1, int(np.ceil(duration / dt_safe)))
        dt = duration / n_steps
        self.last_substep_count = n_steps
        max_delta = 0.0
        not_fixed = ~fixed_mask

        dx2 = self.dx ** 2
        bc  = self.boundary_conditions
        amb = self.ambient_k

        # Precompute interface conductivities — depend only on material layout,
        # which doesn't change during sub-stepping.
        #
        # Harmonic mean: k_eff = 2·k₁·k₂ / (k₁ + k₂)
        # Correctly models materials in series: the resistive material dominates.
        # Returns 0 when either cell is vacuum (k=0), blocking all heat transfer.
        K_pad = np.pad(k, 1, mode="edge")
        k_r = _hm(K_pad[1:-1, 1:-1], K_pad[1:-1, 2:])   # interface with right neighbor
        k_l = _hm(K_pad[1:-1, 1:-1], K_pad[1:-1, :-2])  # interface with left neighbor
        k_d = _hm(K_pad[1:-1, 1:-1], K_pad[2:,  1:-1])  # interface with cell below
        k_u = _hm(K_pad[1:-1, 1:-1], K_pad[:-2, 1:-1])  # interface with cell above

        # 1 / (ρCₚ) for each cell; vacuum cells (ρCₚ=0) get 0 so they never update.
        inv_rhocp = np.where(rho_cp > 0, 1.0 / np.where(rho_cp > 0, rho_cp, 1.0), 0.0)

        # Precompute flags for energy bookkeeping (constant across sub-steps).
        has_fixed   = bool(np.any(fixed_mask))
        top_sink    = bc.get("top")    == SINK
        bottom_sink = bc.get("bottom") == SINK
        left_sink   = bc.get("left")   == SINK
        right_sink  = bc.get("right")  == SINK

        e_from_fixed = 0.0
        e_from_sinks = 0.0

        for _ in range(n_steps):
            # Energy entering grid from sink boundaries this sub-step (pre-FDM temperatures).
            # E_sink = dt · k_edge · (T_amb − T_edge)  [J/m, 1 m unit depth]
            # The dx² in the flux denominator cancels with the dx² cell-area factor.
            if top_sink:
                e_from_sinks += dt * float(np.sum(k[0,  :] * (amb - T[0,  :])))
            if bottom_sink:
                e_from_sinks += dt * float(np.sum(k[-1, :] * (amb - T[-1, :])))
            if left_sink:
                e_from_sinks += dt * float(np.sum(k[:,  0] * (amb - T[:,  0])))
            if right_sink:
                e_from_sinks += dt * float(np.sum(k[:, -1] * (amb - T[:, -1])))

            T_pad = _pad_with_bc(T, bc, amb)
            T_c = T_pad[1:-1, 1:-1]

            # Conductive flux into each cell from all four neighbors.
            # flux_i = Σⱼ k_eff_ij · (Tⱼ − Tᵢ) / dx²
            flux = (
                k_r * (T_pad[1:-1, 2:]  - T_c) +
                k_l * (T_pad[1:-1, :-2] - T_c) +
                k_d * (T_pad[2:,  1:-1] - T_c) +
                k_u * (T_pad[:-2, 1:-1] - T_c)
            ) / dx2

            dT = dt * flux * inv_rhocp
            T += dT

            # Energy injected/removed by fixed-T cells (pinning correction).
            # E_fixed = ρCₚ · (T_fixed − T_fdm) · dx²  [J/m]
            if has_fixed:
                e_from_fixed += float(
                    np.dot(rho_cp[fixed_mask], fixed_temps[fixed_mask] - T[fixed_mask])
                ) * dx2
                # Re-pin fixed-temperature cells after each sub-step.
                T[fixed_mask] = fixed_temps[fixed_mask]

            # Track worst-case per-sub-step delta over non-fixed cells only.
            if np.any(not_fixed):
                step_delta = float(np.max(np.abs(dT[not_fixed])))
                if step_delta > max_delta:
                    max_delta = step_delta

        self.last_max_delta  = max_delta
        self.last_e_from_fixed = e_from_fixed
        self.last_e_from_sinks = e_from_sinks
        return T
