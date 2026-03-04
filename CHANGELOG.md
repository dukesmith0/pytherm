# PyTherm Changelog

## v0.1.0 — 2026-03-04

### Major Changes

- First versioned release of PyTherm, a 2D interactive thermal simulation tool.
- Solver corrected to use the physically exact heterogeneous FDM formulation:
  harmonic mean of k at cell interfaces divided by the receiving cell's own rhocp
  (previously used harmonic mean of alpha, which was incorrect for materials with
  different heat capacities).
- CFL stability condition updated to match the corrected solver: `dt_safe = 0.9 * dx^2 * rhocp_min / (4 * k_max)`.

### Features

- **Grid editor**: interactive 2D grid with draw and select modes, rubber-band rectangle fill, and Bresenham-line paint tool.
- **Material library**: 38+ built-in materials across metals, polymers, ceramics, insulation, gases, and semiconductors, each with thermal conductivity (k), density (rho), heat capacity (cp), display color, abbreviation, and category.
- **Custom materials**: create, edit, and delete user-defined materials via the Materials Manager. Custom materials persist to `data/user_materials.json`.
- **Material abbreviation overlay**: toggle abbreviated labels in each cell corner.
- **Simulation**: explicit finite-difference heat conduction at configurable speed (1x to 10,000x real-time), Play/Pause/Reset controls, configurable physical cell size (dx).
- **Boundary conditions**: per-edge toggle between insulator (zero flux) and ambient sink (Dirichlet).
- **Fixed-temperature heat sources**: pin any cell to a target temperature as a constant heat source or sink.
- **Heatmap view**: blue-to-red temperature gradient with anchored auto-scale (bounds only expand, never collapse) or manual min/max range.
- **Temperature units**: toggle between Celsius, Kelvin, and Fahrenheit throughout the UI.
- **Cell properties panel**: inspect and edit a single selected cell's material, temperature, and fixed-T state.
- **Group edit panel**: apply material, temperature, and fixed-T changes to a multi-cell selection.
- **Undo/redo**: full undo history for paint strokes and property edits.
- **Save/load**: `.pytherm` JSON format with bundled custom materials. Save As with optional material bundle selection.
- **Recent files**: persisted list of recently opened files in the File menu; stale paths are filtered automatically.
- **Welcome dialog**: startup splash with New Grid, Open, and Recent options.
- **Zoom and fit-to-view**: mouse-wheel zoom, Ctrl+scroll, fit-to-grid (F key).
- **Tooltip overlays**: descriptive tooltips on all toolbar buttons.
- **NaN/Inf watchdog**: simulation pauses automatically with a descriptive dialog if the temperature field becomes numerically unstable.
- **Atomic file writes**: all JSON files are written to a `.tmp` sibling then atomically replaced to prevent corruption from mid-write crashes.
- **Crash dialog**: uncaught exceptions display a user-friendly dialog with crash code, collapsible stack trace, copy-to-clipboard, and a link to GitHub Issues.

### Bug Fixes

| ID | Description |
| -- | ----------- |
| B0 | Category group headers showed "False" / "True" instead of the category name. |
| B1 | Group edit Apply button had no hover/pressed visual feedback. |
| B2 | Heatmap manual scale showed flat green when min >= max. |
| B3 | Data file paths were relative to CWD, causing crashes when launched from another directory. |
| B4 | Recent files menu showed paths that no longer exist on disk. |
| B5 | GroupEditPanel raised KeyError if the selected material was deleted between panel open and Apply. |
| B6 | Solver used harmonic mean of alpha at interfaces instead of harmonic mean of k divided by center-cell rhocp. |
| B7 | CFL condition used alpha_max after B6 fix; corrected to use k_max / rhocp_min. |
| B8 | Undo after material deletion restored orphaned Material objects not in the registry, causing silent save data loss. |
| B9 | Group edit "Starting temperature" spinbox was not disabled when "Heat source (fixed T)" was checked, and did not mirror the fixed temperature value. |

### Known Bugs

None.
