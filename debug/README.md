# PyTherm v1.1.0 Debug / Test Files

## Automated Tests

```
python -m pytest debug/ -v
```

Runs 161 pytest tests covering: Cell dataclass, Grid API, Solver physics,
file I/O, unit conversions, MaterialRegistry, SimClock energy tracking,
heat flow view, volumetric flux, theme system, heatmap scale modes,
step history, thermal resistance, convergence panel, and more.
No GUI window is opened. All should pass.

### Test Files

| File | Module | Tests |
|------|--------|-------|
| `test_cell.py` | Cell dataclass | 3 |
| `test_grid.py` | Grid API | 17 |
| `test_grid_resize.py` | Grid.resize() | 8 |
| `test_solver.py` | FDM solver | 16 |
| `test_file_io.py` | .pytherm save/load | 16 |
| `test_units.py` | Temperature units | 7 |
| `test_material_registry.py` | Material library | 10 |
| `test_sim_clock.py` | SimClock timer | 5 |
| `test_step_history.py` | Step history buffer | 8 |
| `test_thermal_resistance.py` | R_th computation | 2 |
| `test_preferences.py` | Preferences dataclass | 11 |
| `test_heatmap.py` | Heatmap palettes | 7 |
| `test_ui.py` | UI components | 53 |

---

## Manual Test File: `manual_test.pytherm`

Open with **File > Open** in PyTherm.

**Grid layout (8x8, dx=2cm, ambient=20C/293K):**

| Location | Material | Type | Value |
|---|---|---|---|
| Row 0, all cols | Aluminum | Normal | ambient temp |
| Row 1, col 1 | Copper | **Fixed-T heater** | 600K (327C) |
| Row 1, col 6 | Copper | **Heat flux A** | 5000 W/m2 |
| Row 2-5, even cols | Aluminum | Normal | ambient temp |
| Row 2-5, odd cols | Vacuum | Insulation | - |
| Row 6, col 3 | Copper | **Heat flux B** | 2000 W/m2 |
| Row 6, col 5 | Copper | **Fixed-T cooler** | 250K (-23C) |
| Row 7, all cols | Aluminum | Normal | ambient temp |
