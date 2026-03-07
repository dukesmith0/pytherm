![PyTherm](docs/media/banner.svg)

**PyTherm** is an interactive 2D heat conduction simulator built with Python, PyQt6, and NumPy. Draw a grid of engineering materials, configure heat sources and boundary conditions, and watch thermal conduction evolve in real time — running up to 10,000x faster than real time via explicit FDM with per-cell CFL sub-stepping.

![Example](docs/media/example.gif)

---

## Quick Start

**Requirements:** Python 3.10+, PyQt6, NumPy

```sh
pip install -r requirements.txt
python main.py
```

A startup dialog lets you set grid dimensions, cell size (dx), and ambient temperature. Click **Create New Grid** to begin, or load a bundled example from **File > Open Template**.

---

## Features

### Physics

- 2D transient heat equation: `rho*Cp * dT/dt = div(k * grad(T))`
- Harmonic mean of k at material interfaces -- correct for materials in thermal series
- Per-cell CFL sub-stepping: up to ~2000x faster than a global bound on mixed-material grids
- Fixed-temperature (Dirichlet) and constant heat flux (Neumann, W/m²) interior BCs
- Per-edge boundary conditions: insulator or ambient sink, set independently
- Live energy conservation display (stored energy vs. reference, per-frame error)

### Materials

- 45 built-in materials across 8 categories: metals, woods, polymers, construction, electronics, gases, liquids
- Add, edit, and delete custom materials via Edit > Materials Manager; persisted to JSON
- Import/export material sets as JSON

### Simulation

- Play/Pause/Reset; speed multiplier 1x to 10,000x real time
- Single-step mode: advance by a set duration while paused
- Steady-state auto-stop (configurable threshold, default 0.01 K/s)
- Temperature units: °C, K, °F, Rankine -- switchable live

### UI

- Zoomable/pannable grid canvas with material and heatmap view modes
- 4 heatmap palettes: Classic, Viridis, Plasma, Grayscale
- Floating temperature legend (Ctrl+L); delta-T overlay (Ctrl+D)
- Cell hover tooltip: live T, stored delta-E, thermal time constant τ, thermal resistance R
- Named cell labels (up to 8 chars) with group highlight
- Draw, rectangle-fill, flood-fill, and select modes; multi-cell group editing
- Configurable undo/redo stack; save/load `.pytherm` JSON; PNG export
- Temperature vs. time plot for selected cells (multiple dockable panels, synchronized cursors)

---

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| Space | Play / Pause |
| R | Reset to ambient |
| N | Single step |
| F | Fit grid to window |
| G | Toggle grid lines |
| D / S / W | Draw / Select / Fill mode |
| H / M | Heatmap / Material view |
| Ctrl+D | Toggle temperature rise (dT) overlay |
| Ctrl+U | Cycle unit (°C → K → °F → R) |
| Ctrl+A | Select all non-vacuum cells |
| Ctrl+click | Toggle cell in selection |
| Middle-click | Eyedropper -- pick material (draw mode) |
| Escape | Deselect all |
| Delete / Backspace | Clear selection to Vacuum |
| Ctrl+Z / Ctrl+Shift+Z | Undo / Redo |
| Ctrl+E | Export view as PNG |
| Ctrl+L | Toggle Temperature Legend |
| Ctrl+, | Preferences |

**Drawing:** Left-click/drag = paint, Shift+drag = rectangle fill, Ctrl+drag = straight line.

**Edge BCs:** Set Top/Bottom/Left/Right independently in the toolbar: **Insulator** or **Sink** (held at ambient).

**Bottom bar** shows simulated time, sub-steps/frame, injected power (W/m), and live energy balance.

---

## Menus

| Action | Location |
| --- | --- |
| New Grid | File > New Grid |
| Open / Open Recent | File > Open |
| Open Template | File > Open Template |
| Save / Save As | File > Save (Ctrl+S) |
| Export image / CSV | File > Export... |
| Materials Manager | Edit > Materials Manager |
| Temperature Legend | View > Temperature Legend (Ctrl+L) |
| Preferences | Tools > Preferences (Ctrl+,) |
| Debug Diagnostics | Tools > Debug Diagnostics (Ctrl+Shift+D) |

---

## How It Works

The FDM solver (`src/simulation/solver.py`) operates on NumPy arrays cached at the start of each frame:

```text
1. Compute harmonic-mean interface conductances (k_r, k_l, k_u, k_d)
2. Per-cell CFL time step: dt_safe = 0.9 * min( rho_cp / k_sum ) * dx²
3. Sub-step n times: T_new = T + dt * flux / rho_cp
4. Inject heat flux: dT += flux_q * dt / rho_cp
5. Re-pin fixed-T cells: T[fixed_mask] = T_fixed
6. Emit T array to UI
```

| Decision | Rationale |
| --- | --- |
| Harmonic mean of k | Correct for materials in series; arithmetic mean over-predicts flux |
| Center-cell rho\*Cp | Each cell stores its own energy; interface-averaging would violate conservation |
| Per-cell CFL | Global bound is ~2000x too conservative on mixed-material grids |
| Explicit time integration | Stability guaranteed by CFL; sufficient for interactive use |
| Kelvin internally | No negative-temperature edge cases; conversions only at the display layer |

---

## Model Scope and Assumptions

PyTherm solves a specific, well-defined physics problem. Understanding what it models -- and what it does not -- is important for interpreting results correctly.

### What is modeled

- **2D transient conduction** -- Fourier's Law discretized on a uniform square grid. No depth axis; all energy quantities are per unit depth (J/m, W/m).
- **Heterogeneous materials** -- harmonic mean of k at cell interfaces, correct for materials in thermal series.
- **Isotropic, constant material properties** -- scalar k, rho, Cp per material; properties do not vary with temperature or direction.
- **Interior boundary conditions** -- fixed-temperature (Dirichlet) cells and constant heat flux (Neumann, W/m²) cells.
- **Edge boundary conditions** -- insulator (zero flux) or ambient sink (Dirichlet at ambient T), set per edge independently.

### What is not modeled

| Phenomenon | Implication |
| --- | --- |
| **Convection** | Fluid cells use only molecular k. Bulk mixing, natural convection, and forced convection are not simulated. Heat transfer at fluid interfaces is significantly underestimated for liquids and gases. |
| **Radiation** | No surface-to-surface or surface-to-environment radiative exchange. Important above ~500 °C or in vacuum environments. |
| **Thermal contact resistance** | Adjacent cells are assumed to be in perfect thermal contact. Real interfaces (TIM layers, gaps, rough surfaces) add resistance not captured here. |
| **Volumetric heat generation** | No q_vol [W/m³] for Joule heating, chemical reactions, or nuclear heating. Point sources can be approximated with fixed-T or flux cells but are not volumetric. |
| **Temperature-dependent properties** | k, rho, and Cp are constant for each material. Behavior at elevated or cryogenic temperatures -- where properties can shift significantly -- is not captured. |
| **Anisotropic conductivity** | Each cell has a single scalar k. Fiber composites, rolled metals, and wood grain are treated as isotropic. |
| **Phase change** | Melting, solidification, and latent heat are not modeled. |
| **3D geometry** | All results are inherently 2D. Through-thickness gradients, edge effects, and out-of-plane heat paths are ignored. |
| **Spatially varying ambient temperature** | The grid uses a single ambient temperature as reference. Non-uniform environmental conditions are not supported. |
| **Implicit time integration** | The solver is explicit (forward Euler). CFL sub-stepping maintains stability, but very stiff problems (large k-contrast, small dx) require many sub-steps per frame. |

These assumptions make PyTherm appropriate for qualitative thermal layout studies, educational demonstrations, and first-order engineering estimates in solid-dominated assemblies. For high-accuracy or certification-grade analysis, validate results against a tested FEA or CFD tool.

---

## References

Material properties (k, rho, Cp) sourced from:

> Incropera, F.P. et al. (2011). *Fundamentals of Heat and Mass Transfer*, 7th ed. Wiley. ISBN 978-0-470-50197-9.

---

## License

MIT License - Craig "Duke" Smith, 2026. See [LICENSE](LICENSE).
