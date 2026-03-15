# PyTherm Changelog

## v1.0.0 -- 2026-03-15

### Added

- **Heat flow view**: third view mode alongside Material and Heatmap. Colors cells by total heat flow rate (W) using the active palette. Shows flow values in each cell (W/kW/mW). Toggle with the Heat Flow button or Q key.
- **Volumetric heat flux**: flux cells now support volumetric (W/m^3) or surface (W/m^2) modes via a checkbox in the sidebar. Volumetric is the default (matches v0.6.0 behavior). Both modes support negative values for heat removal.
- **Light/dark theme**: switchable in Preferences. Theme applies to canvas, sidebar, material picker, plots, convergence graph, and color legend. Dark is the default.
- **Keyboard shortcuts help**: Help > Keyboard Shortcuts (Ctrl+/) shows a searchable dialog with 30+ shortcuts in 5 categories.
- **Heatmap scale modes**: Static (fixed bounds), Live (tracks grid min/max every frame), and Smart (bounds only expand). Configurable in Preferences alongside Auto-init toggle.
- **Reverse palette**: Preferences checkbox flips the heatmap color palette (hot=blue, cold=red).
- **Isotherm customization**: color picker and line width (1-5px) in Preferences.
- **Color legend**: renamed from Temperature Legend, adapts units for heat flow mode. Floating, draggable, theme-aware.
- **6 new example templates**: Diamond Heatspreader, Thermos Flask, Conduction Race (Cu vs Steel), Nuclear Fuel Rod (volumetric flux), Re-entry Tile (1500K plasma), Thermoelectric Cooler (negative flux).
- **Social preview**: 1280x640 SVG with icon grid for GitHub.

### Changed

- **Templates version-free**: templates no longer include version fields, preventing version mismatch warnings on app updates. User saves still include version.
- **File validation**: version field is optional for template loading (backward compat), required for user files.
- **Toolbar decluttered**: Auto-init and Scale mode moved to Preferences. Toolbar keeps Min/Max spinboxes, Palette, Isotherms.
- **Max speed**: removed 10,000x speed option (1,000x is the max).
- **Theme extraction**: QPalette theme code moved from app.py to app_theme.py.
- **Accessibility**: secondary text contrast improved across 6 files (all >= 4:1 on dark, >= 3:1 on light).

### Bug Fixes

- **QColor import crash**: `QColor` accidentally removed from app.py imports when extracting theme code.
- **Heat flow zero display**: values < 1e-9 now show "0 W" instead of "0.0e+00W".
- **Legend units on view switch**: Color Legend now updates units immediately when switching between Heatmap and Heat Flow while paused.
- **Flux regression**: volumetric flux default changed to True so existing files and templates behave identically to v0.6.0.
- **Missing template materials**: pipe_cross_section referenced non-existent material IDs (carbon_steel, water_25c), fixed to fe_a36/water.

### Known Issues

None.

## v0.6.0 -- 2026-03-14

### Added

- **Convergence graph**: View > Convergence Graph opens a dockable panel plotting max dT/dt (K/s) vs simulated time on a log-scale Y axis. Horizontal dashed line at the steady-state threshold. Useful for visualizing solver stability, diagnosing oscillations, and confirming convergence rate.
- **Thermal resistance report**: Analysis > Thermal Resistance Report computes R_th = dT/Q (K per W per metre depth) between source and sink cell groups. Fixed-T cells in selection are treated as source, non-fixed as sink. Dialog shows dT, Q, R_th with copy-to-clipboard.
- **.pythermplot format**: Save Plot button on TempPlotPanel saves temperature-vs-time series as JSON (.pythermplot). File > Open Plot loads saved files into a read-only PlotViewerDialog.
- **Smooth step transitions**: When enabled in Preferences, the Step button animates at the simulation's CFL rate instead of jumping to the final state. Auto-pauses when the requested duration elapses.
- **Step history navigation**: `[` and `]` keys browse a circular buffer of temperature snapshots (default 20, configurable in Preferences). Escape returns to the present. Pauses the simulation while browsing.
- **Analysis menu**: New menu between View and Tools for thermal analysis tools.

### Changed

- **Menu reorganization**: Find Hottest/Coldest Cell moved from Edit to View (they navigate the view, not edit data). Resize Grid moved higher in Edit. Open Plot added to File menu. Convergence Graph added to View menu.
- **Preferences**: added "Animate step" checkbox and "Step history size" spinbox.

### Known Issues

None.

## v0.5.1 — 2026-03-11

### Changed

- **196 built-in materials**: expanded from 45 materials across 8 categories to 196 materials across 26+ hierarchical subcategories. Comma-delimited category paths (e.g. "Metals,Pure") render as nested collapsible groups in the sidebar.
- **`_apply_new_grid` helper**: extracted shared grid-rebind logic from 4 call sites (New Grid, Open, Welcome, Return-to-Welcome) into a single helper with `nonlocal grid`. Reduced `create_app()` from ~1094 to ~1063 lines and eliminated ~60 lines of duplication.
- **Documentation consolidation**: `.vibe/` files, `MEMORY.md`, `CLAUDE.md`, `README.md`, and `docs/index.html` updated to reflect material expansion and refactoring.

### Bug Fixes

- **B-ICON-OVERLAP**: multiple cell icons (protected + fixed-T, or protected + flux) drawn at the same position now stack side-by-side with cumulative x-offset.
- **B-TEMPLATE-VERSION**: opening a template no longer shows a version incompatibility warning dialog.
- **B-GROUP-HIGHLIGHT-PERSIST**: orange group-label highlight no longer persists after opening a new file or creating a new grid.
- **B-SAVE-CATEGORY**: `material_registry.save_custom()` now includes the `category` field, preventing custom materials from losing their category on save.

### Known Issues

None.

## v0.5.0 — 2026-03-10

### Added

- **Protect cells from overpainting**: `cell.protected` flag prevents draw, flood-fill, delete, and paste operations from modifying a cell. Toggle via right-click context menu ("Protect Cell / Unprotect Cell", "Protect Selection") or `P` key in select mode. Protected cells show a yellow lock icon. Fixed-T cells now show a blue pin icon (replacing the lock). Saves in `.pytherm`; round-trips through undo/redo.
- **PyInstaller packaging**: `pytherm.spec` + `.github/workflows/build.yml` for Windows/macOS/Linux release executables triggered on version tags. `src/utils/paths.py` provides `sys._MEIPASS`-aware path helpers so the frozen exe finds bundled data and writes user data next to itself.
- **icon.ico**: App icon converted from `icon.svg` (16/32/48/64/128/256 px); referenced in `pytherm.spec`.
- **Find Hottest / Coldest Cell**: `Edit > Find Hottest Cell (Ctrl+Shift+H)` and `Edit > Find Coldest Cell (Ctrl+Shift+L)` select and center the extremal non-fixed, non-vacuum cell.
- **Reset Selection to Ambient**: `Edit > Reset Selection to Ambient` resets temperature of all selected non-fixed, non-flux, non-protected, non-vacuum cells.
- **Selection Aggregate Stats**: status bar shows min/avg/max temperature and area for the current selection during playback.
- **Right-click context menu**: copy/paste cell properties, protect/unprotect, select group by label. Works in draw mode (protect only) and select mode (all actions).
- **Grid Resize**: `Edit > Resize Grid` opens a dialog to add or trim rows/cols from any edge. Clears undo history (same as New Grid). New cells are vacuum at ambient.
- **Debug Diagnostics**: `Tools > Debug Diagnostics (Ctrl+Shift+D)` opens a non-modal dialog with live simulation stats updated each tick.
- **Command Palette**: `Tools > Command Palette (Ctrl+Shift+P)` fuzzy-searchable list of all actions and materials.
- **Named cell labels**: `Cell.label` (up to 8 chars). Cells with a shared label form a group -- orange group highlight appears on select. Labels shown in both material and heatmap views.
- **Isotherm lines**: heatmap-mode overlay of temperature contour lines. Toggle + interval spinbox in toolbar heatmap controls.
- **Hotspot highlight**: semi-transparent red overlay on cells above a configurable threshold (toolbar). Count shown in status bar during playback.
- **Delta-T overlay (dT)**: `View > Temperature Rise (dT) (Ctrl+D)` -- heatmap shows signed T - T_ambient instead of absolute temperature.
- **Return to Welcome Screen**: `File > Return to Welcome Screen` prompts save if dirty and reopens the startup dialog.
- **Multiple temperature plot panels**: `View > New Temperature Plot` creates additional dockable plot panels. Panels can be pinned independently.
- **Plot synchronized cursors**: Shift+hover draws a dashed gray cursor on all other panels; Shift+click places a global sync pin on all panels.
- **Middle-click eyedropper**: middle-click a cell in draw mode to pick its material as active.
- **Export Cell Data as CSV**: `File > Export > Export Cell Data as CSV` exports row, col, material, temperature for all cells.
- **Ctrl+A selects all non-vacuum cells** in select mode.

### Changed

- Fixed-T cells now show a **blue pin icon** (was: yellow lock). Protected cells use the yellow lock.
- `data/` and `templates/` path resolution updated to use `src/utils/paths.py` (frozen-exe safe).
- `.gitignore`: removed `*.spec` entry so `pytherm.spec` can be committed.

### Bug Fixes

- **B-CONTEXT-MODE**: right-click in draw mode called `_do_select` unconditionally, switching the sidebar. Fixed with `and self._mode == "select"` guard.
- **B-CONTEXT-COPY-DRAW**: "Copy Properties" in context menu was enabled in draw/fill mode. Now disabled unless in select mode.
- **B-CONTEXT-DEAD-VAR**: dead variable `r_min, c_min = cell` in paste handler. Removed.
- **B-PLOT-JITTER**: `_info_label` in `TempPlotPanel` had no fixed width; text changes caused layout reflow jitter. Fixed with `setFixedWidth(110)`.

### Known Issues

None.

## v0.4.0 — 2026-03-06

### Added

- **Heat flux boundary condition**: cells can now be set to either "Fixed T" (pins temperature) or "Heat Flux" (injects constant W/m² heat each sub-step). The sidebar "Heat source" checkbox expands to show Fixed T / Heat Flux radio buttons, a fixed-temperature spinbox, and two linked flux spinboxes (W/m² and W/cell that auto-update each other).
- **Flame icon on flux cells**: heat-flux cells display a QPainter-drawn flame icon (cubic Bezier with orange-to-yellow gradient) instead of a lock icon.
- **Injected power display**: bottom bar shows "Inj: X W/m" or "Inj: X kW/m" -- total heat injection rate from all fixed-T and heat-flux cells each tick.
- **Speed options 2x and 5x**: the speed combo now includes 2x and 5x steps between 1x and 10x.
- **Cursor-anchored zoom**: scroll-to-zoom now anchors to the cursor position instead of the viewport center.
- **Row/col in hover tooltip**: the floating cell tooltip now shows the grid row and column position.
- **Temperature plot: crosshairs and pinned points**: hover over a plot to see dashed crosshairs (vertical + horizontal) in the series color at the nearest data point. Click to toggle a per-plot pin -- solid crosshairs + dot + inline temperature/time label. Multiple pins per panel supported.
- **Temperature plot: synchronized cursor**: Shift+hover draws a dashed gray vertical cursor on all OTHER open panels. Shift+click places a solid white global pin on ALL panels simultaneously; Shift+click again to clear.
- **Temperature plot: label combo populated on open**: new panels created via `View > New Temperature Plot` now populate the label dropdown immediately from the current grid. Painting labeled cells also refreshes all panels' label combos.
- **Min auto heatmap range**: auto heatmap scale enforces a minimum K span (default 10 °C/K), preventing the gradient from over-saturating on near-isothermal grids. Configurable in Preferences under "Min auto heatmap range".
- **Temperature Legend toggle**: `View > Temperature Legend (Ctrl+L)` shows/hides the floating `LegendOverlay` (draggable, pin/expand/close). Off by default.
- **Deselect on re-click**: clicking an already-selected single cell in select mode deselects it and clears any group highlight. Clicking outside the grid or pressing Escape also deselects and clears the orange group highlight overlay.

### Physics

- **Per-cell CFL sub-stepping**: `dt_safe` is now computed from each cell's actual interface conductances (`rhocp_i / k_sum_i`) rather than global extremes -- eliminates the extreme over-conservatism on mixed-material grids (e.g. aluminium + air).
- **Heat flux injection**: flux cells inject `dT = flux_q * dt * inv_rhocp` before fixed-T pinning each sub-step. Energy from flux cells is tracked in `e_cumulative_flux` and included in the energy conservation reference.

### Bug Fixes

- **B-SPEED**: speed combo jumped 1x -> 10x. Fixed by adding 2x and 5x entries.
- **B-ZOOM**: zoom was not cursor-anchored. Fixed with post-scale scene translation.
- **B-TOOLTIP-RC**: hover tooltip omitted row/col. Fixed by passing position from `mouseMoveEvent`.
- **B-SYNC-DOT**: sync cursor dots appeared offset from the vertical line. Fixed by drawing dots at the line's x position rather than the nearest data point's x.
- **B-LEGEND-ALWAYS-ON**: temperature legend color bar appeared even when the menu item was unchecked. Fixed by defaulting `_show_legend = False`.
- **B-LEGEND-WINDOW**: `View > Temperature Legend` now opens the floating `LegendOverlay` widget (draggable titlebar, pin/expand/close, auto-updates bounds each tick). The in-scene color bar remains off by default.
- **B-PLOT-LABEL-EMPTY**: second plot panels started with an empty label dropdown. Fixed by calling `refresh_labels()` in `TempPlotPanel.__init__`.
- **B-BC-RADIO**: Fixed T and Heat Flux radio buttons in both `CellPropertiesPanel` and `GroupEditPanel` could not be toggled back after the first switch. Root cause: `_flux_radio.toggled` was not connected to `_on_mode_radio_toggled`, so only the deselect event (`checked=False`) fired when switching. Also fixed the fixed-temperature spinbox showing -273 °C for flux cells by always populating it in `show_cell`, using `cell.temperature` as fallback when `fixed_temp <= 1 K`.

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
