# PyTherm v0.4.0 Debug / Test Files

## Automated Tests

```
python debug/run_tests.py
```

Runs 21 headless tests covering: Cell dataclass, Grid API, Solver physics,
file I/O, unit conversions, MaterialRegistry, and SimClock energy tracking.
No GUI window is opened. All should pass (green).

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

---

## Manual Test Checklist

After opening `manual_test.pytherm`, check each item and note pass/fail.
You can send results (screenshot or text) back to Claude for follow-up.

### 1. File Load

- [ ] File opens without error
- [ ] Grid shows 8x8 layout
- [ ] Row 0 and 7 show aluminum color
- [ ] Row 1 and 6 show copper color
- [ ] Even interior cells show aluminum, odd cells show vacuum (black)

### 2. Cell Icons

- [ ] **Lock icon** visible on row 1 col 1 (fixed-T heater)
- [ ] **Lock icon** visible on row 6 col 5 (fixed-T cooler)
- [ ] **Flame icon** visible on row 1 col 6 (flux cell A)
- [ ] **Flame icon** visible on row 6 col 3 (flux cell B)
- [ ] No lock/flame on normal aluminum or vacuum cells

### 3. Cell Properties Panel -- select a single flux cell (row 1, col 6)

- [ ] "Heat source" checkbox is checked
- [ ] "Heat Flux" radio button is selected (not "Fixed T")
- [ ] W/m2 spinbox shows 5000.0
- [ ] W/cell spinbox shows 5000 * (0.02)^2 = 2.0 W/cell
- [ ] "Starting temperature" spinbox is disabled (greyed out)
- [ ] "Fixed temperature" area is hidden

### 4. Cell Properties Panel -- select the fixed-T cell (row 1, col 1)

- [ ] "Heat source" checkbox is checked
- [ ] "Fixed T" radio button is selected
- [ ] "Fixed temperature" spinbox shows ~327C (600K)
- [ ] W/m2 spinbox is hidden (flux area not visible)
- [ ] "Starting temperature" spinbox is disabled

### 5. Cell Properties Panel -- select a normal aluminum cell

- [ ] "Heat source" checkbox is unchecked
- [ ] Heat source detail row is hidden (no radios or spinboxes visible)
- [ ] "Starting temperature" spinbox is enabled

### 6. Linked spinboxes (W/m2 <-> W/cell)

- [ ] Click on flux cell (row 1, col 6). W/m2 = 5000, W/cell = 2.0
- [ ] Change W/m2 to 10000 -- W/cell should auto-update to 4.0
- [ ] Change W/cell to 1.0 -- W/m2 should auto-update to 2500.0
- [ ] Do NOT click Apply yet

### 7. Mode switching (Fixed T <-> Heat Flux) without Apply

- [ ] Select flux cell (row 1, col 6)
- [ ] Click "Fixed T" radio -- fixed temperature area should appear, flux area hide
- [ ] Click "Heat Flux" radio -- flux area should reappear, fixed area hide
- [ ] Switch back to Heat Flux

### 8. Apply button

- [ ] Select flux cell (row 1, col 6), set W/m2 = 8000, click Apply
- [ ] Deselect and reselect -- W/m2 should now show 8000
- [ ] W/cell should show 8000 * 0.0004 = 3.2

### 9. Simulation -- press Play (Space)

- [ ] Injected power label ("Inj: X W/m") appears in bottom bar
- [ ] Power value is non-zero and positive
- [ ] Flux cells visibly heat up in heatmap mode (switch to Heatmap view)
- [ ] Fixed-T heater (row 1, col 1) stays at 600K (lock holds)
- [ ] Fixed-T cooler (row 6, col 5) stays at 250K
- [ ] Energy conservation "err" stays small (< a few J/m)
- [ ] Substep count visible and non-zero

### 10. Heatmap with flux cells

- [ ] Switch to Heatmap view
- [ ] Flux cells show heat gradient radiating outward from them
- [ ] Flame icons are still visible on flux cells in heatmap mode
- [ ] Lock icons still visible on fixed-T cells

### 11. Group Edit Panel -- select multiple cells

- [ ] Drag-select a region containing: flux cell A, fixed-T heater, and some aluminum cells
- [ ] Group Edit panel appears (not Cell Properties)
- [ ] "Heat source" checkbox shows partial/mixed state (partially checked)
- [ ] Count label shows correct cell count

### 12. Speed combo (Bottom Bar)

- [ ] Speed dropdown shows: 1x, 2x, 5x, 10x, 50x, 100x, ... (check 2x and 5x exist)

### 13. Tooltip (hover over cells without clicking)

- [ ] Hover over any cell -- tooltip appears
- [ ] Tooltip shows "row X, col Y" position
- [ ] Tooltip shows temperature, material, tau, R values for non-vacuum cells

### 14. Zoom

- [ ] Scroll wheel zooms in/out
- [ ] Zoom stays centered under cursor (not viewport center)
- [ ] Test at different cursor positions across the grid

### 15. Undo / Redo

- [ ] Make a change (e.g. click a cell, change its flux value, Apply)
- [ ] Press Ctrl+Z -- change should be undone
- [ ] Press Ctrl+Y -- change should be redone
- [ ] Undo while simulation is paused works correctly

### 16. Copy / Paste flux cell properties

- [ ] In Select mode, click on flux cell (row 1, col 6)
- [ ] Press Ctrl+C to copy
- [ ] Click on a normal aluminum cell, press Ctrl+V
- [ ] The aluminum cell should now be a flux cell with same flux_q
- [ ] Flame icon should appear on the pasted cell

### 17. Save and Reload

- [ ] File > Save As -- save to a new file
- [ ] File > New Grid (to clear)
- [ ] File > Open the saved file
- [ ] Flux cells load with correct flux_q values and flame icons
- [ ] Fixed-T cells load with correct fixed temperatures

### 18. Unit switching

- [ ] Change unit to F (Fahrenheit) in the bottom bar unit combo
- [ ] Fixed-T heater should show ~615F (600K = 620.33F)
- [ ] Fixed-T cooler should show ~-9.67F (250K)
- [ ] Switch back to C

