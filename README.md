# PyTherm

A 2D thermal simulation tool. Paint materials onto a grid, set boundary conditions, and watch heat diffuse in real time.

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

## How to use

### Drawing

Select a material from the sidebar, then click or drag on the grid to paint cells. Use the Draw/Select toggle in the toolbar to switch between painting and selecting.

- Left click or drag: paint the active material
- Shift + drag: paint or select a rectangular region
- Ctrl + drag: paint or select along a straight line
- Right click: select a single cell

### Editing cells

Click a cell in Select mode to open its properties in the sidebar. You can set the temperature, mark it as a fixed heat source or sink, and change its material. Selecting multiple cells opens a group editor.

### Simulation

Press Play to start the simulation. Use the Speed dropdown to run faster than real time. Press Reset to restore all temperatures to the ambient value. Drawing is disabled while the simulation is running.

### Boundary conditions

The Borders buttons in the toolbar set each edge to either an insulator (no heat escapes) or a sink (edge is held at ambient temperature).

### Heatmap view

Switch to Heatmap mode to see temperatures as a color gradient. Auto scaling adjusts the range to the current min and max. You can also set the range manually.

### Temperature units

Use the Unit dropdown to display temperatures in Celsius, Kelvin, or Fahrenheit.

### New grid

File > New Grid lets you set the grid size, cell size in meters, and ambient temperature.

### Navigation

- Scroll wheel: zoom in and out
- Middle click and drag: pan
- Fit button: fit the grid to the window
- Grid button: toggle grid lines
