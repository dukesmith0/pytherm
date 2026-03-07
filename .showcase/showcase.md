# PyTherm Portfolio Showcase

Showcase `.pytherm` files live in `templates/Examples/`. This folder is gitignored -- local only.

---

## Audience Notes

| Audience | What they care about | Key scenarios |
| --- | --- | --- |
| Recruiter | Visual polish, real-world relevance, tech stack recognition | Hero shot (cpu_heatsink), building_wall |
| Thermal engineer | Physics correctness, interface conductance, BCs, energy balance | All |
| Aerospace engineer | TPS materials, high-temp gradients, structural heat loads | aerospace_tps, cpu_heatsink |
| Mechanical engineer | Component heat dissipation, geometry with voids, transient response | brake_rotor, pcb_hotspot |
| HVAC / building engineer | Envelope performance, embedded heating, multi-layer walls | building_wall, radiant_floor |
| Electronics / PCB engineer | Die thermal, trace routing, hotspot management | cpu_heatsink, pcb_hotspot |
| Software / hiring manager | Architecture (solver/renderer/UI separation), NumPy + PyQt6 | Full UI hero shot |

---

## Scenario Files

### `cpu_heatsink.pytherm` -- CPU Package Cross-Section

- **Grid:** 14 rows x 24 cols, dx = 1 mm (14 mm x 24 mm cross-section)
- **Physics:** Silicon die (8 x 4 mm, rows 8-11) injects 200 kW/m2 heat flux -- realistic for a
  high-performance CPU. Thermal paste (row 7) and copper heat spreader (row 6) conduct heat upward
  into six aluminum fin channels (rows 0-5). Fin tips (row 0) are fixed at 25 C (ambient), modeling
  convective cooling to ambient air. Bottom edge is a heat sink (ambient 25 C) to represent the PCB.
  FR4 substrate occupies rows 12-13.
- **Expected result at steady state:** Die reaches ~65-80 C. Fin tips hold at 25 C. Clear gradient
  through TIM, spreader, and fins. Hotter at die center, cooler at fin tips.
- **Best for:** Electronics engineers, thermal engineers, hero shot for any engineering audience.
- **Setup:** Load > Play > wait for steady state indicator.
- **UI tips:** Enable heatmap. Enable abbreviation labels (zoom in to see AL/TM/CU/SI/FR4). The
  bottom bar shows injected power in watts -- a concrete engineering number to reference.
- **Talking points:** Harmonic mean conductance at the Si/TIM/Cu interfaces. Per-cell CFL
  sub-stepping handles the orders-of-magnitude k ratio (silicon 148 vs. FR4 0.3 W/mK). The
  thermal paste layer (k = 4 W/mK) is the most thermally limiting interface -- zoom in to see it.

---

### `pcb_hotspot.pytherm` -- PCB Hotspot with Copper Traces

- **Grid:** 20 rows x 20 cols, dx = 2 mm (40 mm x 40 mm board section)
- **Physics:** 4x4 mm silicon chip (rows 8-11, cols 8-11) dissipates 500 kW/m2 -- a hot
  GPU-class die. Copper traces (rows 9-10 flanking the die) route heat laterally toward
  fixed copper edge pads (cols 0 and 19, fixed at 30 C), modeling heatsink attachment
  points or a large ground plane. Top and bottom edges are heat sinks (ambient 25 C),
  representing convection from both PCB surfaces.
- **Expected result at steady state:** Die core significantly hotter than the edges. The
  copper traces appear as a bright conduction path in the heatmap. FR4 zones (k = 0.3 W/mK)
  heat up slowly; the copper (k = 401 W/mK) glows hot near the die.
- **Best for:** PCB/electronics engineers, anyone in hardware design.
- **Setup:** Load > Play. Screenshot mid-transient shows heat spreading down the traces.
- **UI tips:** Heatmap mode. The two glowing copper trace paths tell the story visually.
- **Talking points:** k contrast between silicon (148 W/mK), copper (401 W/mK), and FR4
  (0.3 W/mK) is over 1000x. Harmonic mean correctly suppresses flux at FR4 boundaries.
  The top/bottom sink BCs make this a more realistic PCB model than an adiabatic simulation.

---

### `building_wall.pytherm` -- Insulated Wall Cross-Section

- **Grid:** 10 rows x 22 cols, dx = 5 cm (wall height x 110 cm cross-section)
- **Physics:** Interior drywall (col 0) fixed at 22 C (heated interior). Exterior brick
  (col 21) fixed at -10 C (cold winter day). Wall assembly left to right: drywall (2 cells)
  | mineral wool insulation (6 cells, k = 0.04 W/mK) | concrete block (5 cells) | brick
  (4 cells) | exterior insulation mineral wool (2 cells) | brick veneer (2 cells).
  Total assembly: ~110 cm wall with 32 K total temperature drop.
- **Expected result at steady state:** The mineral wool layers show steep color gradients
  (large resistance), while the concrete and brick show gentle gradients (better conductors
  within the wall context). The heatmap tells the insulation story visually.
- **Best for:** Recruiters, HVAC engineers, building scientists, architects.
- **Setup:** Load > Play > steady state. No interaction required.
- **UI tips:** Full window screenshot shows layer widths clearly. The color legend on the
  right communicates the temperature range instantly. Building wall is the strongest
  single-slide image for a general audience -- clear geometry, familiar context, beautiful gradient.
- **Talking points:** R-value is the reciprocal of the steady-state heat flux divided by
  the temperature difference. The mineral wool dominates the wall R-value despite being
  only part of the assembly. The concrete has k = 1.4 W/mK, mineral wool k = 0.04 -- a
  35x difference. This is immediately visible in the heatmap gradient widths.

---

### `aerospace_tps.pytherm` -- Hypersonic Thermal Protection System

- **Grid:** 10 rows x 20 cols, dx = 1 cm (10 cm TPS stack cross-section)
- **Physics:** Aerodynamic heating at 200 W/m2 applied to the outer aerogel face (row 0).
  This represents sustained heating on a Mach 5+ hypersonic vehicle (comparable to X-15 or
  HTV-2 flight regimes). TPS stack from outer to inner:
  - Rows 0-3: aerogel tiles (k = 0.015 W/mK, 4 cm) -- extreme thermal resistance
  - Rows 4-6: alumina ceramic carrier (k = 30 W/mK, 3 cm) -- structural/hot face
  - Rows 7-8: titanium airframe (k = 21.9 W/mK, 2 cm)
  - Row 9: titanium inner face fixed at 400 K (127 C) -- structural temperature limit
- **Expected result at steady state:** Outer aerogel surface reaches ~930 K (660 C).
  Inner titanium held at 400 K (127 C). Over 530 K temperature drop across 4 cm of aerogel.
  The alumina and titanium layers show almost no gradient (high k, small ΔT).
- **Best for:** Aerospace engineers, materials engineers, defense contractors.
- **Setup:** Load > Play > steady state.
- **UI tips:** Switch unit display to Kelvin to emphasize the extreme surface temperatures.
  The color scale from 400 K (blue) to 930 K (red) makes the aerogel's thermal resistance
  immediately dramatic. Zoom in on the aerogel/alumina interface to see the discontinuity.
- **Talking points:** The aerogel k is 2000x lower than the alumina. The harmonic mean
  k_eff at their interface is ≈ 0.03 W/mK -- aerogel-dominated. This is why aerogel is the
  primary insulator even though it is a minority of the stack volume. The titanium airframe
  (SR-71 construction material) is kept at 127 C despite the outer face reaching 660 C.

---

### `brake_rotor.pytherm` -- Ventilated Brake Disc

- **Grid:** 20 rows x 20 cols, dx = 3 mm (60 mm x 60 mm rotor cross-section)
- **Physics:** Cast iron disc with two radial air ventilation channels (rows 4-7 and 12-15,
  cols 3-13). Friction surface (col 19, right edge) receives 80 kW/m2 heat flux from pad
  contact -- representative of hard braking on a performance vehicle. Hub side (col 0) is
  free to equilibrate by conduction. Top and bottom edges are heat sinks (ambient 27 C),
  representing convective cooling from the rotor faces exposed to airflow.
- **Expected result at steady state:** Friction surface (right) runs hottest. Air ventilation
  channels appear as darker cooler voids in the heatmap -- the cast iron webs between them
  glow hotter, showing preferential conduction through the ribs. Heat spreads radially
  inward toward the hub.
- **Best for:** Mechanical engineers, automotive engineers, manufacturing.
- **Setup:** Load > Play > steady state. Enable material view briefly to show rib geometry,
  then switch to heatmap.
- **UI tips:** The ventilation slot geometry is the visual story. Air (k = 0.026 W/mK) is
  nearly an insulator next to cast iron (k = 52 W/mK) -- a 2000x ratio. The heatmap makes
  this contrast obvious.
- **Talking points:** 80 kW/m2 is 80 W/cm2 -- realistic for hard braking. The ventilation
  slots reduce the effective cross-sectional area for radial conduction, creating the rib
  pattern visible in the heatmap. Top/bottom sinks model the convective film coefficient
  implicitly via the ambient BC.

---

### `radiant_floor.pytherm` -- Radiant Floor Heating

- **Grid:** 18 rows x 20 cols, dx = 1 cm (18 cm deep x 20 cm wide floor cross-section)
- **Physics:** Two embedded copper pipes (row 4, cols 4-6 and 13-15) fixed at 60 C --
  typical hot water supply temperature for a hydronic heating system. Concrete slab
  (rows 1-8) conducts heat upward to the floor surface. Top edge is a heat sink
  (ambient 22 C room air), allowing heat to flow from the floor into the room. Mineral
  wool insulation (rows 9-13, k = 0.04 W/mK) below the slab prevents downward heat loss.
  Structural concrete base (rows 14-17) with bottom edge as a heat sink (earth/ambient).
- **Expected result at steady state:** Two warm oval blooms centered on the pipe positions
  spread upward through the concrete. The floor surface (row 0) warms above room temperature
  (typically 25-29 C) -- the whole point of radiant floor heating. The mineral wool layer
  shows a sharp temperature drop on its underside, confirming the insulation is working.
- **Best for:** HVAC engineers, building engineers, residential/commercial construction.
- **Setup:** Load > Play > steady state.
- **UI tips:** The dual-bloom heat pattern is immediately intuitive. Compare temperature at
  the floor surface (row 0) vs. room ambient -- the delta is the useful heat output. The
  mineral wool layer below reads colder in the heatmap, a clean visual confirmation of its
  insulation function.
- **Talking points:** Copper pipes (k = 401 W/mK) distribute heat efficiently within the
  concrete mass (k = 1.4 W/mK). The concrete acts as thermal mass -- it smooths out the
  temperature distribution between the pipes. The sub-slab insulation (mineral wool,
  k = 0.04 W/mK) means nearly all energy goes upward into the room, not downward into the earth.

---

## Suggested Slideshow Order (4-5 slides)

**Slide 1 -- Hero (full application UI)**
File: `cpu_heatsink.pytherm` at steady state.
Full window screenshot. Shows dark CAD-style theme, heatmap, color legend, sidebar material
picker, and bottom bar sim controls simultaneously.
Caption: "Real-time 2D thermal simulation desktop app. Python, NumPy, PyQt6."

**Slide 2 -- Engineering Depth (physics)**
File: `cpu_heatsink.pytherm` zoomed in, or `pcb_hotspot.pytherm`.
Heatmap with abbreviation labels visible. Bottom bar showing injected power in watts.
Caption: "Explicit FDM solver. Harmonic mean conductance at material interfaces.
Heat flux BCs. Per-cell CFL sub-stepping. 45-material database."

**Slide 3 -- Real-World System (broad appeal)**
File: `building_wall.pytherm` at steady state.
Full grid, full window. The warm-to-cold gradient across material layers is immediately legible
to any engineer or recruiter -- no domain knowledge required.
Caption: "Multi-material conduction across heterogeneous assemblies. Correct interface physics."

**Slide 4 -- Technical Feature Close-up**
Any loaded scenario. Hover a cell to show the material tooltip (k, rho, cp, category).
Or open the material picker to show the categorized library.
Caption: "Interactive editing. Built-in material library. Undo/redo. Named labels."

**Slide 5 (optional, audience-targeted)**
Pick the scenario most relevant to the role:

- Aerospace: `aerospace_tps.pytherm` in Kelvin mode -- 530+ K gradient at a glance
- Mechanical / automotive: `brake_rotor.pytherm` -- rib geometry + heatmap overlay
- Electronics: `pcb_hotspot.pytherm` -- copper trace heat routing
- HVAC / building: `radiant_floor.pytherm` -- dual bloom warmth pattern

---

## README GIF / Animation Guidance

The README gif should show PyTherm doing what it does best: transient heat spreading in real time.

**Best scenario for the gif:** `cpu_heatsink.pytherm` or `building_wall.pytherm`.

- cpu_heatsink: dramatic color evolution from ambient blue to orange/red at the die, spreading
  upward through the fins. More technically impressive. Better for engineering-focused audiences.
- building_wall: slow, clean, professional. Color gradient locks into place. Best for general
  audiences and recruiters.

**Gif script (cpu_heatsink recommended):**

1. Open the file. Material view is visible -- show the geometry for 1-2 seconds.
2. Switch to heatmap. Press Play.
3. Record the transient: watch the die region bloom red, heat spread upward through the spreader
   and fins, tips stabilize blue. Stop at steady state (the SS indicator fires).
4. Total gif length: 6-10 seconds at 1-2x playback speed. Aim for ~15 fps, under 5 MB.

**Crop:** Show the grid and the bottom bar (sim time, energy display). Can crop the sidebar to
save horizontal space. Keep the color legend visible at the right edge.

**What the gif must show for each audience:**

- Recruiter: color changing = the app is doing something impressive and real
- Thermal engineer: the gradient matches intuition (hottest at source, cooling at tips)
- Software engineer: smooth real-time rendering, the UI controls are responsive

---

## Quick Audience Targeting

| Applying to | Lead with | Follow with |
| --- | --- | --- |
| Aerospace company | aerospace_tps | cpu_heatsink |
| Automotive / tier-1 supplier | brake_rotor | building_wall |
| Electronics / semiconductor | cpu_heatsink | pcb_hotspot |
| HVAC / building systems | building_wall | radiant_floor |
| Software / tooling role | Full UI hero shot (cpu_heatsink) | pcb_hotspot |
| Defense / government lab | aerospace_tps | cpu_heatsink |
| Consulting / generalist | building_wall | brake_rotor |

---

## What Engineers Look For (recruiter prep)

**Thermal engineers** will zoom in on interface temperatures. Be ready to explain:

- Harmonic mean conductance: k_eff = 2*k_i*k_j / (k_i + k_j). This is the correct
  series-resistance formula for two half-cells in contact. Arithmetic mean is wrong for
  heterogeneous materials -- it over-weights the conductive side.
- Why k=0 (vacuum) gives zero flux: the harmonic mean collapses to zero if either material
  has k=0. Implemented via np.where to avoid division by zero.

**Aerospace engineers** will ask about time-stepping stability. Answer:

- Per-cell CFL: `dt_safe = 0.9 * min_i(dx^2 * rhocp_i / k_sum_i)`. The global naive bound
  (based on max k) is overly conservative by 100-2000x on mixed-material grids. Per-cell
  bounds use each cell's actual interface conductances.
- For the TPS scenario, the aerogel's low k means its CFL limit is very large (slow diffusion),
  while the titanium (high k, moderate rhocp) sets the actual binding limit.

**Mechanical engineers** will recognize the brake rotor geometry immediately. Note:

- The air ventilation channels create ~2000x k contrast vs. cast iron. The heatmap shows
  preferential conduction through the ribs -- physically correct behavior.
- 80 kW/m2 friction heat flux at the pad contact face. Top/bottom sinks model convective
  air cooling from the rotor faces.

**HVAC engineers** will care about:

- Correct mineral wool properties (k = 0.04 W/mK). The insulation dominates wall R-value.
- Radiant floor: copper pipe at 60 C is standard hydronic supply. The floor surface warms
  to ~27-29 C (delta ~5-7 C above room), which is realistic for slab heating.
- Sub-slab insulation (mineral wool) directs nearly all heat upward -- visible in heatmap.

**Software engineers / hiring managers** care about architecture. Mention explicitly:

- Solver (`solver.py`) fully separated from renderer and UI. NumPy-vectorized FDM.
- PyQt6 QGraphicsView with viewport culling: only visible cells drawn per frame.
- Signal/slot wiring in `app.py`. No global state except one `nonlocal grid` rebind pattern.
- Undo/redo via grid snapshot stack (GridHistory). Atomic file writes (.tmp + os.replace).
- 49-test headless debug suite (`debug/run_tests.py`).

---

## Numerical Method Reference

### Governing Equation

PyTherm solves the 2D transient heat conduction equation (Fourier's Law):

```text
rho * Cp * dT/dt = div(k * grad(T))
```

Discretized on a uniform grid (cell side `dx` [m]) with a 4-neighbor stencil:

```text
(rho*Cp)_i * dT_i/dt = sum_j [ k_eff_ij * (T_j - T_i) / dx^2 ]
```

All temperatures stored and computed in Kelvin. Unit conversions happen only at the display layer.

---

### Heterogeneous Interface Conductance

At an interface between two materials, the effective conductivity uses the harmonic mean:

```text
k_eff = 2 * k_i * k_j / (k_i + k_j)
```

The two half-cells (thickness dx/2) are in thermal series:

```text
R = (dx/2)/k_i + (dx/2)/k_j   =>   k_eff = dx/R = 2*k_i*k_j / (k_i + k_j)
```

For aluminum (167 W/mK) to aerogel (0.015 W/mK): arithmetic mean gives ~83 W/mK, harmonic
mean gives ~0.03 W/mK. Only the harmonic mean is physically correct.

---

### CFL Stability and Per-Cell Sub-Stepping

Explicit integration is conditionally stable. Time step bound:

```text
dt_safe = 0.9 * min_i( dx^2 * (rho*Cp)_i / sum_j(k_eff_ij) )
```

Per-cell bounds are typically 100-2000x larger than the naive global bound on mixed grids.
The solver sub-steps internally within each wall-clock frame.

---

### Boundary Conditions

**Edge boundaries:**

- Insulator (Neumann, zero-flux): ghost cell = edge cell temperature. `dT/dn = 0`. Default.
- Sink (Dirichlet, ambient): ghost cell = ambient temperature. Edge cells equilibrate toward ambient.

**Interior cell BCs:**

- Fixed-T (Dirichlet): temperature overwritten back to target after every sub-step.
  Models an ideal heater/cooler with infinite thermal mass.
- Heat flux (Neumann): constant power density `q` [W/m2] injected each sub-step:
  `dT += q * dt / (rho*Cp)`. Models aerodynamic heating, resistive heater, or friction source.

---

### Energy Conservation and Steady-State Detection

The bottom bar shows live energy conservation: stored energy vs. accumulated input/output.
Error near zero confirms numerical stability. Error growth indicates speed multiplier is too high.

Steady-state auto-pause fires when:

```text
max|dT| / dt_substep < 0.01 K/s
```

A first-tick guard prevents spurious trigger immediately after reset.

---

### Implementation Notes

- Solver is fully NumPy-vectorized. FDM fluxes computed as array shifts -- no Python cell loops.
- Rendering: QGraphicsView with viewport culling. Only visible cells drawn per frame.
- All file writes atomic: `.tmp` sibling + `os.replace()`.
- Material arrays cached in SimClock (`_arr_cache`). Invalidated on cell paint or BC change.
