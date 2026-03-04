# PyTherm v0.2.0

A 2D thermal simulation tool. Draw a grid of materials, set heat sources and boundary conditions, then watch heat conduct through your design in real time.

## Requirements

- Python 3.10+
- PyQt6
- NumPy

Install dependencies:

```sh
pip install -r requirements.txt
```

## Running

```sh
python main.py
```

## Getting Started

When PyTherm opens, a startup dialog lets you configure a new grid or open a recent file. Set the number of rows and columns, the physical cell size, and the ambient temperature, then click **Create New Grid**.

## Drawing

Select a material from the sidebar on the left, then paint it onto the grid.

| Action | Result |
| --- | --- |
| Left-click / drag | Paint the active material |
| Shift + drag | Fill a rectangle |
| Ctrl + drag | Paint a straight line |
| Right-click | Select a cell |

Switch between **Draw**, **Fill**, and **Select** mode using the toolbar buttons or the D / W / S keys. In **Fill** mode, clicking a cell flood-fills all contiguous same-material cells with the active material.

## Editing Cells

Click a cell in Select mode to view and edit its properties in the sidebar. You can change its material, set a starting temperature, or mark it as a **fixed-temperature heat source**.

To edit multiple cells at once, hold Shift or Ctrl and drag to select a group. Use **(no change)** in the material dropdown to update temperature or fixed-T settings without overwriting cells that have different materials.

## Simulation

Press **Play** to start. The **Speed** control lets you run faster than real time. Press **Reset** to return all cells to ambient temperature. Drawing is locked while the simulation runs.

Use the **Step** button (or press **N**) to advance the simulation by a fixed duration while paused. Set the step duration with the spinbox next to the button.

Enable **Stop at SS** to run until the simulation reaches steady state — the simulation pauses automatically when the maximum temperature change per step falls below 0.01 K.

The status bar at the bottom shows live min / avg / max temperature of all non-vacuum cells.

## Materials

The built-in library includes metals, woods, polymers, construction materials, electronics, gases, and common liquids. Use **File > Materials Manager** to add or edit custom materials.

Use the filter bar at the top of the material picker to search by name.

## View Modes

**Material view** colors each cell by its material. Turn on **Abbr.** in the toolbar to show a short label in each cell corner.

**Heatmap view** colors cells from blue (cold) to red (hot). The scale fits automatically or can be set to a fixed range.

## Boundary Conditions

Use the edge buttons in the toolbar to set each grid border to **Insulator** (no heat loss) or **Sink** (held at ambient temperature).

## Temperature Units

Switch between Celsius, Kelvin, and Fahrenheit with the **Unit** dropdown in the toolbar.

## Files

| Action | Description |
| --- | --- |
| File > New Grid | Set grid size, cell size, and ambient temperature |
| File > Save / Save As | Save as a `.pytherm` file |
| File > Open / Open Recent | Reload a saved grid |
| File > Export View as Image | Save the current canvas as a PNG image (Ctrl+E) |
| File > Materials Manager | Add, edit, or delete custom materials |
| Help > What's New | View the full version changelog |
| Help > Report a Bug | Open the GitHub Issues page |
| Help > About PyTherm | Version, author, and GitHub link |

## Keyboard Shortcuts

| Key | Action |
| --- | --- |
| D | Draw mode |
| S | Select mode |
| W | Fill mode |
| Space | Play / Pause |
| R | Reset simulation |
| N | Single step |
| F | Fit grid to view |
| G | Toggle grid lines |
| Ctrl+Z | Undo |
| Ctrl+Shift+Z | Redo |
| Ctrl+E | Export view as image |

## Navigation

- **Scroll wheel** to zoom in and out
- **Middle-click drag** to pan
- **F key** or the Fit button to fit the grid to the window
