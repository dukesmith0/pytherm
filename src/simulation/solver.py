from __future__ import annotations

import numpy as np

# Boundary condition string constants
INSULATOR = "insulator"  # zero heat-flux (Neumann): ghost cell = edge cell
SINK      = "sink"       # ambient-temperature (Dirichlet): ghost cell = ambient_k

_DEFAULT_BC: dict[str, str] = {
    "top": INSULATOR, "bottom": INSULATOR,
    "left": INSULATOR, "right": INSULATOR,
}


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
    """2D explicit finite-difference heat conduction solver.

    The heat equation in 2D is:  ∂T/∂t = ∂/∂x(α ∂T/∂x) + ∂/∂y(α ∂T/∂y)

    We discretize this on a uniform grid with cell spacing dx using the explicit
    (forward Euler) method with interface diffusivities — meaning the diffusivity
    at the boundary between two cells uses the harmonic mean of their individual
    diffusivities, which correctly weights the more resistive material.
    """

    def __init__(self, dx: float):
        # dx: physical size of each square cell in meters
        self.dx = dx
        self.last_substep_count = 0   # set after each advance(), useful for debugging
        self.boundary_conditions: dict[str, str] = dict(_DEFAULT_BC)
        self.ambient_k: float = 293.15

    def advance(self,
                T: np.ndarray,
                alpha: np.ndarray,
                fixed_mask: np.ndarray,
                fixed_temps: np.ndarray,
                duration: float) -> np.ndarray:
        """Advance the temperature field by `duration` simulated seconds.

        Internally sub-steps to satisfy the CFL stability condition:
            dt_safe ≤ dx² / (4 × α_max)
        Violating this causes exponentially growing oscillations (numerical blowup).
        Sub-stepping lets the user choose any duration while guaranteeing stability.

        Returns a new array — does not modify the input T.
        """
        T = T.copy()

        alpha_max = alpha.max()
        if alpha_max == 0:
            return T

        # CFL stability condition for 2D explicit FDM: dt ≤ dx² / (4 × α_max)
        # The factor of 4 comes from having 4 neighbors in 2D — each contributes dx².
        # Using 90% of the theoretical limit as a safety margin.
        dt_safe = 0.9 * self.dx ** 2 / (4.0 * alpha_max)
        n_steps = max(1, int(np.ceil(duration / dt_safe)))
        dt = duration / n_steps
        self.last_substep_count = n_steps

        dx2 = self.dx ** 2
        bc  = self.boundary_conditions
        amb = self.ambient_k

        # Precompute interface diffusivities — they only depend on material layout,
        # which doesn't change during sub-stepping. Computing them once saves work.
        #
        # Harmonic mean: α_interface = 2α₁α₂ / (α₁ + α₂)
        # This is the correct choice for materials in series (like resistors in series).
        # A thin insulating layer dominates the joint resistance — the harmonic mean
        # ensures the lower-α material has stronger influence than arithmetic averaging.
        A_pad = np.pad(alpha, 1, mode="edge")

        def hm(a: np.ndarray, b: np.ndarray) -> np.ndarray:
            s = a + b
            return np.where(s > 0, 2 * a * b / s, 0.0)

        a_r = hm(A_pad[1:-1, 1:-1], A_pad[1:-1, 2:])   # interface with right neighbor
        a_l = hm(A_pad[1:-1, 1:-1], A_pad[1:-1, :-2])  # interface with left neighbor
        a_d = hm(A_pad[1:-1, 1:-1], A_pad[2:,  1:-1])  # interface with cell below
        a_u = hm(A_pad[1:-1, 1:-1], A_pad[:-2, 1:-1])  # interface with cell above

        for _ in range(n_steps):
            T_pad = _pad_with_bc(T, bc, amb)
            T_c = T_pad[1:-1, 1:-1]

            # Heat flux into each cell from all four neighbors.
            # Each term: α_interface × (T_neighbor − T_cell)
            # Positive → neighbor is hotter → cell gains heat. Negative → cell loses heat.
            dT = (
                a_r * (T_pad[1:-1, 2:]  - T_c) +
                a_l * (T_pad[1:-1, :-2] - T_c) +
                a_d * (T_pad[2:,  1:-1] - T_c) +
                a_u * (T_pad[:-2, 1:-1] - T_c)
            ) / dx2

            T += dt * dT

            # Re-pin fixed-temperature cells after each sub-step.
            # Heat sources override whatever diffusion computed — they are held constant.
            T[fixed_mask] = fixed_temps[fixed_mask]

        return T
