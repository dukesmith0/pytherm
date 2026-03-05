# PyTherm Changelog

## v0.3.0 — 2026-03-04

### Added

- **Redesigned About dialog**: dark header with app icon, subtitle, version, and GitHub link — matches the welcome dialog aesthetic.
- **Base material selector**: New Grid dialog and welcome dialog now include a material dropdown so the grid can be filled with any material instead of always defaulting to Vacuum.
- **Zoom to Selection**: Ctrl+Shift+F fits the view to the selected cells' bounding box.
- **Copy/Paste cell properties**: Ctrl+C in select mode copies the first selected cell's material, temperature, and heat-source state to a clipboard; Ctrl+V pastes to all selected cells.
- **Paint temperature override**: checkbox and spinbox in the sidebar below the material picker; when enabled, every paint stroke also sets the cell temperature to the specified value.
- **Thermal properties in hover tooltip**: time constant tau = rho*cp*dx²/k (s) and thermal resistance R = dx/k (K·m²/W) shown for non-vacuum cells.
- **Grid coordinate overlay**: row and column indices drawn along the grid edges in `drawForeground` when cells are at least 24 px on screen.
- **Welcome dialog version**: now reads from `src/version.py` instead of a hardcoded string.
- **Rankine temperature unit**: all temperature spinboxes and displays now support Rankine (R) in addition to °C, K, and °F.
- **Inline unit parsing for temperature spinboxes**: type a value with a unit suffix (e.g. 100C, 373K, 212F, 491R) in any temperature spinbox; it auto-converts to the active display unit on commit.
- **Energy conservation display**: bottom bar shows E (current stored thermal energy above ambient), ref (E_start + accumulated energy from fixed cells and sink boundaries), and err (conservation error); updated every simulation tick.

### Performance

- **Viewport culling**: `drawBackground` and `drawForeground` now clamp all cell loops to the visible rect. 100x fewer iterations when zoomed in on a large grid.
- **Heatmap bounds cache**: `_heatmap_bounds()` computed once per frame in `drawBackground` and reused by `_draw_abbr`, `_draw_color_legend` — was called 3x per frame previously.
- **QColor cache**: `cell_color()` caches `QColor(hex_string)` by material color string — eliminates up to 40,000 hex parses per frame on large grids.
- **Fixed-cell position set**: lock-icon loop now iterates a cached `_fixed_cells` set (O(fixed count)) instead of scanning all cells every frame (O(N)).

## v0.2.0 — 2026-03-04

### Added

- **Temperature statistics status bar**: live min / avg / max temperature of all non-vacuum cells in the current display unit, updated every simulation tick.
- **Single-step button**: advance the simulation by a user-specified simulated duration (seconds) while paused. The step duration spinbox accepts values from 0.001 s to 3 600 s. Keyboard shortcut: N.
- **Steady-state mode**: "Stop at SS" checkbox in the toolbar. When enabled, Play runs the simulation normally and pauses automatically when the maximum temperature change across non-fixed, non-vacuum cells falls below 0.01 K per sub-step.
- **About dialog**: `Help > About PyTherm` shows the version, author, and a GitHub link.
- **Bug report button**: `Help > Report a Bug` opens the GitHub Issues page.
- **Export view as image**: `File > Export View as Image` (Ctrl+E) saves the current canvas as a PNG file.
- **Common liquids material library**: 8 new built-in liquid materials (Water, Seawater, Ethylene Glycol, Antifreeze 50/50, Engine Oil, Hydraulic Fluid, Gasoline, R-134a) in a new "Liquids" category.
- **Searchable material picker**: filter bar above the material list in the sidebar — type to filter by name or abbreviation.
- **Bottom toolbar**: view-related controls (Material/Heatmap toggle, heatmap scale, border conditions, temperature unit, Fit/Grid/Abbr) moved to a dedicated bottom toolbar so the top toolbar focuses on simulation controls.
- **Fill (paint bucket) tool**: flood-fill mode button in the toolbar (W key) — click any cell to fill all contiguous same-material cells with the active material using BFS.
- **Heatmap color legend**: a vertical gradient scale bar with min/max temperature labels appears in the bottom-right corner of the viewport in heatmap mode.
- **Sub-step count display**: solver sub-step count per tick shown next to the sim-time in the top toolbar.

### Fixed

| ID | Description |
| -- | ----------- |
| B-SS | Steady-state convergence check now uses the worst-case per-sub-step delta from the solver instead of the total tick-level delta, fixing false negatives at high speed multipliers. |
| B-GE | Group edit panel now uses a tri-state "Heat source" checkbox. When the selection has mixed fixed states, the checkbox shows a partial state and Apply skips writing `is_fixed`. |
| B-SF | Material search filter now also matches abbreviations (e.g. "Cu", "FR4", "LN2"). |
| B-CT | New grid cells default `fixed_temp` to `ambient_temp_k` instead of absolute zero. |

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
