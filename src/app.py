from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.models.material import load_materials
from src.rendering import units as _units
from src.simulation.grid import Grid
from src.simulation.sim_clock import SimClock
from src.simulation.solver import Solver
from src.ui.grid_scene import GridScene
from src.ui.grid_view import GridView
from src.ui.main_window import MainWindow
from src.ui.new_grid_dialog import NewGridDialog
from src.ui.sidebar import Sidebar
from src.ui.toolbar import Toolbar


def _apply_dark_theme(app: QApplication) -> None:
    """Dark CAD-style palette — mimics ANSYS/Fluent look."""
    app.setStyle("Fusion")
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window,          QColor(45,  45,  45))
    p.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Base,            QColor(30,  30,  30))
    p.setColor(QPalette.ColorRole.AlternateBase,   QColor(55,  55,  55))
    p.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Button,          QColor(50,  50,  50))
    p.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    p.setColor(QPalette.ColorRole.Highlight,       QColor(0,   150, 136))  # teal accent
    p.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    p.setColor(QPalette.ColorRole.Mid,             QColor(60,  60,  60))
    p.setColor(QPalette.ColorRole.Dark,            QColor(20,  20,  20))
    p.setColor(QPalette.ColorRole.Shadow,          QColor(10,  10,  10))
    p.setColor(QPalette.ColorRole.ToolTipBase,     QColor(35,  35,  35))
    p.setColor(QPalette.ColorRole.ToolTipText,     QColor(200, 200, 200))
    # Disabled state — dim text so greyed-out widgets are visually obvious
    dis = QPalette.ColorGroup.Disabled
    p.setColor(dis, QPalette.ColorRole.Text,       QColor(90,  90,  90))
    p.setColor(dis, QPalette.ColorRole.WindowText, QColor(90,  90,  90))
    p.setColor(dis, QPalette.ColorRole.ButtonText, QColor(90,  90,  90))
    p.setColor(dis, QPalette.ColorRole.Base,       QColor(38,  38,  38))
    app.setPalette(p)


def create_app() -> tuple[QApplication, MainWindow]:
    app = QApplication(sys.argv)
    _apply_dark_theme(app)

    materials  = load_materials(Path("data/materials.json"))
    grid       = Grid(10, 10, materials["air"], ambient_temp_k=293.15)
    scene      = GridScene(grid)
    view       = GridView(scene)

    # dx = physical cell size in metres; 1 cm default (user-configurable via New Grid)
    solver    = Solver(dx=0.01)
    sim_clock = SimClock(grid, solver, scene)

    toolbar = Toolbar()
    sidebar = Sidebar(materials, grid)

    # ── Draw / Select mode ───────────────────────────────────────────────────
    toolbar.draw_mode_changed.connect(view.set_draw_mode)

    # ── Material picker → active drawing material ────────────────────────────
    sidebar.picker.material_selected.connect(view.set_active_material)
    view.set_active_material(next(iter(materials.values())))

    # ── Cell / group selection → properties panels ───────────────────────────
    view.cells_selected.connect(sidebar.show_cells)
    sidebar.props_panel.cell_modified.connect(scene.refresh)
    sidebar.group_panel.group_modified.connect(scene.refresh)

    # ── Simulation controls ──────────────────────────────────────────────────
    toolbar.play_pause_toggled.connect(lambda on: sim_clock.play() if on else sim_clock.pause())
    toolbar.reset_requested.connect(sim_clock.reset)
    toolbar.speed_changed.connect(sim_clock.set_speed)
    sim_clock.tick.connect(toolbar.update_sim_time)
    sim_clock.state_changed.connect(toolbar.set_running)
    sim_clock.tick.connect(lambda _t: sidebar.props_panel.refresh_display())
    sim_clock.state_changed.connect(sidebar.props_panel.set_sim_running)

    # Lock drawing while simulation is running
    sim_clock.state_changed.connect(view.set_drawing_locked)

    # ── View mode and heatmap scale ──────────────────────────────────────────
    toolbar.view_mode_changed.connect(scene.set_view_mode)
    toolbar.heatmap_auto_changed.connect(scene.set_heatmap_auto)
    toolbar.heatmap_range_changed.connect(scene.set_heatmap_range)

    # ── Border boundary conditions ───────────────────────────────────────────
    toolbar.boundary_conditions_changed.connect(
        lambda bc: setattr(solver, "boundary_conditions", bc)
    )

    # ── Temperature unit toggle ──────────────────────────────────────────────
    def _on_unit_changed(unit_str: str) -> None:
        _units.set_unit(_units.Unit(unit_str))
        sidebar.props_panel.refresh_units()
        sidebar.group_panel.refresh_units()
        toolbar.refresh_units()
        scene.refresh()

    toolbar.unit_changed.connect(_on_unit_changed)

    # ── View utilities ───────────────────────────────────────────────────────
    toolbar.grid_lines_toggled.connect(
        lambda on: (setattr(scene, "show_grid_lines", on), scene.refresh())
    )
    toolbar.fit_view_requested.connect(view.fit_grid)

    # ── New Grid ─────────────────────────────────────────────────────────────
    window = MainWindow()
    window.addToolBar(toolbar)
    window.set_canvas_widget(view)
    window.set_sidebar_widget(sidebar)

    def _on_new_grid() -> None:
        if sim_clock.is_running:
            ans = QMessageBox.question(
                window, "New Grid",
                "The simulation is running. Stop it and create a new grid?",
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            sim_clock.pause()

        dlg = NewGridDialog(window)
        if dlg.exec() != NewGridDialog.DialogCode.Accepted:
            return

        rows, cols, dx_m, ambient_k = dlg.values()
        new_grid = Grid(rows, cols, materials["air"], ambient_temp_k=ambient_k)
        solver.dx = dx_m
        sim_clock.reset()
        sim_clock.set_grid(new_grid)
        scene.set_grid(new_grid)
        sidebar.set_grid(new_grid)
        view.reset_zoom()

    window.new_grid_requested.connect(_on_new_grid)
    window.show()
    return app, window
