from __future__ import annotations

import sys
from pathlib import Path
from typing import Callable

import numpy as np

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont, QPalette, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QDialog, QFileDialog, QHBoxLayout, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)


from src.io.file_io import load_pytherm, save_pytherm
from src.io.recent_files import add_recent, load_recent, remove_recent
from src.models.material import Material
from src.models.material_registry import MaterialRegistry
from src.models.preferences import Preferences
from src.rendering import units as _units
from src.rendering.heatmap_renderer import active_palette_name as _active_palette_name
from src.simulation.grid import Grid
from src.simulation.history import GridHistory
from src.simulation.sim_clock import SimClock
from src.simulation.solver import Solver
from src.ui.bottom_bar import BottomBar
from src.ui.grid_scene import GridScene
from src.ui.grid_view import GridView
from src.ui.main_window import MainWindow
from src.ui.load_dialogs import MaterialConflictDialog, MaterialImportDialog
from src.ui.materials_manager import MaterialsManagerDialog
from src.ui.new_grid_dialog import NewGridDialog
from src.ui.resize_grid_dialog import ResizeGridDialog
from src.ui.save_dialogs import CustomMaterialsBundleDialog
from src.ui.sidebar import Sidebar
from src.ui.toolbar import Toolbar
from src.ui.command_palette import CommandPalette
from src.ui.legend_widget import LegendOverlay
from src.ui.preferences_dialog import PreferencesDialog
from src.ui.temp_plot_panel import TempPlotPanel
from src.ui.welcome_dialog import WelcomeDialog, make_app_icon
from src.utils.paths import get_bundle_data_dir, get_user_data_dir, get_templates_dir
from src.version import VERSION


def _apply_dark_theme(app: QApplication) -> None:
    """Dark CAD-style palette - mimics ANSYS/Fluent look."""
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
    app.setWindowIcon(make_app_icon())

    _bundle_dir = get_bundle_data_dir()
    _user_dir   = get_user_data_dir()
    _prefs_path = _user_dir / "preferences.json"
    prefs       = Preferences.load(_prefs_path)

    registry   = MaterialRegistry(_bundle_dir / "materials.json", _user_dir / "user_materials.json")
    materials  = registry.all_materials
    grid       = Grid(
        prefs.default_rows, prefs.default_cols,
        registry.get("vacuum"),
        ambient_temp_k=prefs.ambient_temp_k,
    )
    scene      = GridScene(grid)
    scene.set_min_auto_range(prefs.min_auto_heatmap_range_k)
    view       = GridView(scene)

    # dx = physical cell size in metres; default from prefs
    solver    = Solver(dx=prefs.default_dx_m)
    sim_clock = SimClock(grid, solver, scene)

    # Apply initial prefs
    _units.set_unit(_units.Unit(prefs.unit))
    sim_clock.set_speed(prefs.sim_speed)
    sim_clock.ss_threshold = prefs.ss_threshold_k_per_s

    history = GridHistory()
    history.set_max_steps(prefs.max_undo_steps)

    toolbar     = Toolbar()
    toolbar.set_dx(solver.dx)
    view.set_dx(solver.dx)
    bottom_bar  = BottomBar()
    bottom_bar.set_unit_value(prefs.unit)     # sync combo to prefs unit (no listeners yet)
    bottom_bar.set_speed_value(prefs.sim_speed)
    sidebar     = Sidebar(materials, grid)

    # ── Draw / Select / Fill mode ────────────────────────────────────────────
    toolbar.mode_changed.connect(view.set_mode)
    toolbar.mode_changed.connect(sidebar.set_mode)

    # ── Material picker → active drawing material ────────────────────────────
    sidebar.picker.material_selected.connect(view.set_active_material)
    sidebar.picker.material_selected.connect(sidebar.draw_panel.set_active_material)
    sidebar.draw_panel.material_changed.connect(view.set_active_material)
    sidebar.draw_panel.material_changed.connect(sidebar.picker.select_material)
    view.set_active_material(next(iter(materials.values())))

    # ── Cell / group selection → properties panels ───────────────────────────
    _current_selection: list[tuple[int, int]] = []

    def _on_cells_selected(cells: list[tuple[int, int]]) -> None:
        nonlocal _current_selection
        _current_selection = cells
        sidebar.show_cells(cells)
        for _p in _plot_panels:
            _p.set_tracked_cells(cells)
        if len(cells) == 1:
            lbl = grid.cell(*cells[0]).label
            if lbl:
                group = {
                    (r, c)
                    for r in range(grid.rows) for c in range(grid.cols)
                    if grid.cell(r, c).label == lbl and not grid.cell(r, c).material.is_vacuum
                }
                scene.set_group_highlight(group, label=lbl)
                return
        scene.set_group_highlight(set())

    view.cells_selected.connect(_on_cells_selected)
    sidebar.props_panel.cell_modified.connect(scene.refresh)
    sidebar.group_panel.group_modified.connect(scene.refresh)
    sidebar.props_panel.cell_modified.connect(scene.invalidate_fixed_cells)
    sidebar.group_panel.group_modified.connect(scene.invalidate_fixed_cells)
    view.cell_painted.connect(scene.invalidate_fixed_cells)
    sidebar.props_panel.cell_modified.connect(lambda: scene.set_group_highlight(set()))
    sidebar.group_panel.group_modified.connect(lambda: scene.set_group_highlight(set()))
    view.cell_painted.connect(lambda: scene.set_group_highlight(set()))
    sidebar.props_panel.cell_modified.connect(sim_clock.invalidate_arrays)
    sidebar.group_panel.group_modified.connect(sim_clock.invalidate_arrays)

    def _on_draw_settings_changed() -> None:
        view.set_paint_temp(sidebar.draw_panel.temperature_k)
        view.set_draw_heat_settings(
            sidebar.draw_panel.is_fixed,
            sidebar.draw_panel.fixed_temp_k,
            sidebar.draw_panel.is_flux,
            sidebar.draw_panel.flux_q,
        )
        view.set_draw_label(sidebar.draw_panel.label)

    sidebar.draw_panel.draw_settings_changed.connect(_on_draw_settings_changed)

    # ── Simulation controls ──────────────────────────────────────────────────
    bottom_bar.play_pause_toggled.connect(lambda on: sim_clock.play() if on else sim_clock.pause())
    bottom_bar.reset_requested.connect(sim_clock.reset)
    bottom_bar.speed_changed.connect(sim_clock.set_speed)

    def _on_dx_changed(dx_m: float) -> None:
        if sim_clock.is_running:
            sim_clock.pause()
        ans = QMessageBox.question(
            window, "Change Cell Size",
            f"Changing the cell size to {dx_m * 100:.4g} cm will reset the simulation.\n"
            "Continue?",
        )
        if ans == QMessageBox.StandardButton.Yes:
            solver.dx = dx_m
            view.set_dx(dx_m)
            sidebar.set_dx(dx_m)
            sim_clock.reset()
            window.mark_dirty()
        else:
            # Revert spinbox silently
            toolbar.set_dx(solver.dx)

    toolbar.dx_changed.connect(_on_dx_changed)
    sim_clock.tick.connect(bottom_bar.update_sim_time)
    sim_clock.state_changed.connect(bottom_bar.set_running)
    sim_clock.tick.connect(lambda _t: sidebar.props_panel.refresh_display())
    sim_clock.state_changed.connect(sidebar.props_panel.set_sim_running)

    def _on_nan_detected() -> None:
        QMessageBox.warning(
            window,
            "Simulation Unstable",
            "The temperature field contains NaN or Inf values.\n\n"
            "Likely causes:\n"
            "  \u2022 Extreme temperature difference between adjacent fixed-T cells\n"
            "  \u2022 Very high thermal conductivity with a large cell size\n\n"
            "Try reducing the simulation speed or resetting the grid (R).",
        )

    sim_clock.nan_detected.connect(_on_nan_detected)

    def _update_stats(_t: float) -> None:
        T = grid.temperature_array()
        rho_cp = grid.rho_cp_array()
        mask = rho_cp > 0
        if not np.any(mask):
            return
        T_active = T[mask]
        rcp_active = rho_cp[mask]
        if sim_clock.is_running:
            suf = _units.suffix()
            # Selection-scoped stats when cells are selected
            sel = _current_selection
            sel_active = [(r, c) for r, c in sel if rho_cp[r, c] > 0]
            if sel_active:
                sel_T = np.array([T[r, c] for r, c in sel_active])
                lo  = _units.to_display(float(sel_T.min()))
                hi  = _units.to_display(float(sel_T.max()))
                avg = _units.to_display(float(sel_T.mean()))
                area = len(sel_active) * solver.dx ** 2
                msg = (f"Selection ({len(sel_active)} cells, {area*1e4:.2g} cm\u00b2)  "
                       f"min: {lo:.1f} {suf}   avg: {avg:.1f} {suf}   max: {hi:.1f} {suf}")
            else:
                lo  = _units.to_display(float(T_active.min()))
                hi  = _units.to_display(float(T_active.max()))
                avg = _units.to_display(float(T_active.mean()))
                msg = f"T  min: {lo:.1f} {suf}   avg: {avg:.1f} {suf}   max: {hi:.1f} {suf}"
            n_hot = scene.hotspot_count
            if n_hot > 0:
                msg += f"   \u26a0 {n_hot} cell{'s' if n_hot != 1 else ''} above hotspot threshold"
            window.statusBar().showMessage(msg)
        # Energy conservation display in the bottom bar.
        # E_now = Σ ρCₚᵢ·(Tᵢ − T_amb)·dx²  [J/m, 1 m unit depth]
        e_now = float(np.dot(rcp_active, T_active - grid.ambient_temp_k)) * solver.dx ** 2
        e_ref = sim_clock.e_start + sim_clock.e_cumulative_fixed + sim_clock.e_cumulative_sinks + sim_clock.e_cumulative_flux
        bottom_bar.update_energy(e_now, e_ref)
        dt_sim = sim_clock.last_dt_sim
        if dt_sim > 0:
            power = (solver.last_e_from_fixed + solver.last_e_from_flux) / dt_sim
        else:
            power = 0.0
        bottom_bar.update_power(power)

    sim_clock.tick.connect(_update_stats)

    bottom_bar.step_requested.connect(sim_clock.step)
    bottom_bar.steady_mode_changed.connect(sim_clock.set_steady_mode)

    def _on_steady_state_reached() -> None:
        window.statusBar().showMessage("Steady state reached.")

    sim_clock.steady_state_reached.connect(_on_steady_state_reached)

    # Lock drawing while simulation is running
    sim_clock.state_changed.connect(view.set_drawing_locked)

    # ── View mode and heatmap scale ──────────────────────────────────────────
    toolbar.view_mode_changed.connect(scene.set_view_mode)
    toolbar.heatmap_auto_changed.connect(scene.set_heatmap_auto)
    toolbar.heatmap_range_changed.connect(scene.set_heatmap_range)

    from src.rendering.heatmap_renderer import set_palette as _set_palette
    def _on_palette_changed(name: str) -> None:
        _set_palette(name)
        scene.refresh()
    toolbar.palette_changed.connect(_on_palette_changed)

    toolbar.isotherm_changed.connect(scene.set_isotherm)
    toolbar.hotspot_threshold_changed.connect(scene.set_hotspot_threshold)

    # ── Border boundary conditions ───────────────────────────────────────────
    toolbar.boundary_conditions_changed.connect(
        lambda bc: setattr(solver, "boundary_conditions", bc)
    )

    # ── Temperature unit toggle ──────────────────────────────────────────────
    def _on_unit_changed(unit_str: str) -> None:
        _units.set_unit(_units.Unit(unit_str))
        sidebar.refresh_units()
        toolbar.refresh_units()
        bottom_bar.refresh_units()
        scene.refresh()
        for _p in _plot_panels:
            _p.refresh_units()
        _update_stats(sim_clock.sim_time)

    def _on_ambient_changed(k_val: float) -> None:
        grid.ambient_temp_k = k_val
        solver.ambient_k = k_val
        sim_clock.recalculate_energy_reference()

    bottom_bar.unit_changed.connect(_on_unit_changed)
    bottom_bar.ambient_changed.connect(_on_ambient_changed)

    # ── View utilities ───────────────────────────────────────────────────────
    toolbar.grid_lines_toggled.connect(
        lambda on: (setattr(scene, "show_grid_lines", on), scene.refresh())
    )
    toolbar.fit_view_requested.connect(view.fit_grid)
    toolbar.abbr_toggled.connect(scene.set_show_abbr)
    toolbar.label_toggled.connect(scene.set_show_label)

    # All closures below share 'grid' via nonlocal. _on_new_grid rebinds it
    # so Materials Manager, Save, etc. always operate on the live grid.
    window = MainWindow()
    window.delta_toggled.connect(scene.set_show_delta)
    window.addToolBar(toolbar)
    window.addToolBar(Qt.ToolBarArea.BottomToolBarArea, bottom_bar)
    window.set_canvas_widget(view)
    window.set_sidebar_widget(sidebar)

    _plot_panels: list[TempPlotPanel] = []

    def _make_plot_panel() -> TempPlotPanel:
        n = len(_plot_panels) + 1
        title = "Temperature Plot" if n == 1 else f"Temperature Plot {n}"
        panel = TempPlotPanel(grid, title=title)
        panel.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        panel.set_max_points(prefs.max_plot_points)
        window.add_dock_widget(Qt.DockWidgetArea.RightDockWidgetArea, panel)
        sim_clock.tick.connect(panel.on_tick)
        bottom_bar.reset_requested.connect(panel.clear_history)
        sidebar.props_panel.cell_modified.connect(panel.refresh_labels)
        sidebar.group_panel.group_modified.connect(panel.refresh_labels)
        view.cell_painted.connect(panel.refresh_labels)
        panel.closing.connect(lambda p=panel: _plot_panels.remove(p) if p in _plot_panels else None)
        panel.sync_hover_changed.connect(
            lambda t, src=panel: [_p.set_sync_hover(t) for _p in _plot_panels if _p is not src]
        )
        panel.sync_pin_changed.connect(
            lambda t, src=panel: [_p.set_sync_pin(t) for _p in _plot_panels]
        )
        _plot_panels.append(panel)
        return panel

    _make_plot_panel()  # create initial panel
    sidebar.props_panel.cell_modified.connect(sidebar.refresh_labels)
    sidebar.group_panel.group_modified.connect(sidebar.refresh_labels)
    view.cell_painted.connect(sidebar.refresh_labels)

    window.new_plot_requested.connect(_make_plot_panel)

    # ── Grid rebind helper ─────────────────────────────────────────────────
    _DEFAULT_BC = {"top": "insulator", "bottom": "insulator",
                   "left": "insulator", "right": "insulator"}

    def _apply_new_grid(new_grid: Grid, dx_m: float, *,
                        bc: dict | None = None,
                        file_path: str | None = None) -> None:
        nonlocal grid
        grid = new_grid
        _current_selection.clear()
        solver.dx = dx_m
        history.clear()
        sim_clock.reset()
        sim_clock.set_grid(grid)
        scene.set_grid(grid)
        sidebar.set_grid(grid)
        sidebar.set_dx(solver.dx)
        toolbar.set_dx(solver.dx)
        view.set_dx(solver.dx)
        view.reset_zoom()
        bottom_bar.set_ambient(grid.ambient_temp_k)
        for _p in _plot_panels:
            _p.set_grid(grid)
        if bc is not None:
            toolbar.set_boundary_conditions(bc)
        window.mark_clean(file_path)

    _legend_overlay = LegendOverlay(view)
    _legend_overlay.hide()

    def _on_legend_toggled(show: bool) -> None:
        if show:
            _legend_overlay.update_bounds(*scene.frame_bounds)
            _legend_overlay.show()
        else:
            _legend_overlay.hide()

    window.legend_toggled.connect(_on_legend_toggled)
    _legend_overlay.closed.connect(lambda: window._legend_action.setChecked(False))
    sim_clock.tick.connect(
        lambda _t: _legend_overlay.update_bounds(*scene.frame_bounds)
        if _legend_overlay.isVisible() else None
    )

    # ── Preferences ───────────────────────────────────────────────────────────

    def _show_preferences(_checked: bool = False) -> None:
        nonlocal prefs
        dlg = PreferencesDialog(prefs, window)
        if dlg.exec() != PreferencesDialog.DialogCode.Accepted:
            return
        new_prefs = dlg.updated_prefs()
        if new_prefs.unit != prefs.unit:
            bottom_bar.set_unit_value(new_prefs.unit)  # fires unit_changed -> _on_unit_changed
        if new_prefs.sim_speed != prefs.sim_speed:
            sim_clock.set_speed(new_prefs.sim_speed)
            bottom_bar.set_speed_value(new_prefs.sim_speed)
        if new_prefs.max_undo_steps != prefs.max_undo_steps:
            history.set_max_steps(new_prefs.max_undo_steps)
        if new_prefs.max_plot_points != prefs.max_plot_points:
            for _p in _plot_panels:
                _p.set_max_points(new_prefs.max_plot_points)
        if new_prefs.ss_threshold_k_per_s != prefs.ss_threshold_k_per_s:
            sim_clock.ss_threshold = new_prefs.ss_threshold_k_per_s
        if new_prefs.min_auto_heatmap_range_k != prefs.min_auto_heatmap_range_k:
            scene.set_min_auto_range(new_prefs.min_auto_heatmap_range_k)
        prefs = new_prefs
        prefs.save(_prefs_path)

    window.preferences_requested.connect(_show_preferences)

    # ── Debug Diagnostics ─────────────────────────────────────────────────────

    _diagnostics_dlg: QDialog | None = None

    def _show_diagnostics(_checked: bool = False) -> None:
        nonlocal _diagnostics_dlg
        if _diagnostics_dlg is not None and _diagnostics_dlg.isVisible():
            _diagnostics_dlg.raise_()
            _diagnostics_dlg.activateWindow()
            return

        dlg = QDialog(window)
        dlg.setWindowTitle("Debug Diagnostics")
        dlg.resize(460, 300)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(8, 8, 8, 8)

        txt = QPlainTextEdit()
        txt.setReadOnly(True)
        txt.setFont(QFont("Courier New", 10))
        layout.addWidget(txt)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(txt.toPlainText()))
        btn_row.addWidget(copy_btn)
        layout.addLayout(btn_row)

        def _refresh(_t: float = 0.0) -> None:
            nv = n_fixed = n_flux = 0
            temps = []
            for r in range(grid.rows):
                for c in range(grid.cols):
                    cell = grid.cell(r, c)
                    if cell.material.is_vacuum:
                        continue
                    nv += 1
                    if cell.is_fixed:
                        n_fixed += 1
                    if cell.is_flux:
                        n_flux += 1
                    temps.append(cell.temperature)
            t_min = min(temps) if temps else 0.0
            t_max = max(temps) if temps else 0.0
            t_mean = sum(temps) / len(temps) if temps else 0.0
            dt_ms = solver.last_substep_dt * 1000.0
            e_fixed = solver.last_e_from_fixed
            e_flux  = solver.last_e_from_flux
            e_sinks = solver.last_e_from_sinks
            lines = [
                f"Version:         {VERSION}",
                f"File:            {window._current_file or '(unsaved)'}",
                "",
                f"Grid:            {grid.rows} \u00d7 {grid.cols}  ({grid.rows * grid.cols} cells)",
                f"Non-vacuum:      {nv}   Fixed-T: {n_fixed}   Flux: {n_flux}",
                f"Cell size (dx):  {solver.dx * 100:.3f} cm  ({solver.dx:.5f} m)",
                f"Ambient:         {grid.ambient_temp_k:.2f} K",
                "",
                f"T min / mean / max: {t_min:.2f} / {t_mean:.2f} / {t_max:.2f} K",
                "",
                f"Sim time:        {sim_clock.sim_time:.3f} s",
                f"Sub-steps/frame: {solver.last_substep_count}",
                f"dt per sub-step: {dt_ms:.4f} ms",
                f"Max |\u0394T| (frame): {solver.last_max_delta:.4e} K",
                f"Max |\u0394T| (sub):   {solver.last_substep_delta:.4e} K",
                "",
                f"E from fixed-T:  {e_fixed:.4e} J/m (last frame)",
                f"E from flux:     {e_flux:.4e} J/m (last frame)",
                f"E from sinks:    {e_sinks:.4e} J/m (last frame)",
                "",
                f"SS threshold:    {sim_clock.ss_threshold:.4f} K/s",
                f"Palette:         {_active_palette_name()}",
            ]
            txt.setPlainText("\n".join(lines))

        _refresh()
        sim_clock.tick.connect(_refresh)
        dlg.finished.connect(lambda: sim_clock.tick.disconnect(_refresh))

        _diagnostics_dlg = dlg
        dlg.show()

    window.diagnostics_requested.connect(_show_diagnostics)

    # ── Save helpers ──────────────────────────────────────────────────────────

    def _custom_ids_in_grid() -> set[str]:
        ids: set[str] = set()
        for r in range(grid.rows):
            for c in range(grid.cols):
                mid = grid.cell(r, c).material.id
                if mid in registry.custom:
                    ids.add(mid)
        return ids

    def _commit_save(path: str, custom_mats: list) -> None:
        sim_settings = {"boundary_conditions": dict(solver.boundary_conditions)}
        save_pytherm(Path(path), grid, solver.dx, custom_mats, sim_settings=sim_settings)
        window.mark_clean(path)
        _rebuild_recent_menu(add_recent(path))

    def _do_save_as() -> bool:
        path, _ = QFileDialog.getSaveFileName(
            window, "Save As", "", "PyTherm Files (*.pytherm)"
        )
        if not path:
            return False
        if not path.endswith(".pytherm"):
            path += ".pytherm"
        all_custom = list(registry.custom.values())
        if all_custom:
            required_ids = _custom_ids_in_grid()
            dlg = CustomMaterialsBundleDialog(all_custom, required_ids, window)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return False
            custom_mats = dlg.selected_materials()
        else:
            custom_mats = []
        _commit_save(path, custom_mats)
        return True

    def _do_save() -> bool:
        if window._current_file:
            _commit_save(window._current_file, list(registry.custom.values()))
            return True
        return _do_save_as()

    def _prompt_save_before_continuing(action: str) -> bool:
        """Returns True if safe to proceed (saved or discarded), False if cancelled."""
        box = QMessageBox(window)
        box.setWindowTitle(f"{action} \u2014 Unsaved Changes")
        box.setText("You have unsaved changes. Save before continuing?")
        box.setIcon(QMessageBox.Icon.Warning)
        save_btn    = box.addButton("Save",    QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Cancel",                QMessageBox.ButtonRole.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == save_btn:
            return _do_save()
        return clicked == discard_btn

    def _do_export() -> None:
        path, _ = QFileDialog.getSaveFileName(
            window, "Export View as Image", "", "PNG Images (*.png)"
        )
        if not path:
            return
        if not path.endswith(".png"):
            path += ".png"
        pixmap = view.grab()
        if not pixmap.save(path, "PNG"):
            QMessageBox.warning(window, "Export Failed", f"Could not write:\n{path}")

    def _do_export_csv() -> None:
        import csv
        path, _ = QFileDialog.getSaveFileName(
            window, "Export Cell Data as CSV", "", "CSV Files (*.csv)"
        )
        if not path:
            return
        if not path.endswith(".csv"):
            path += ".csv"
        suf = _units.suffix()
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["row", "col", "material", f"temperature_{suf}"])
                for r in range(grid.rows):
                    for c in range(grid.cols):
                        cell = grid.cell(r, c)
                        writer.writerow([r, c, cell.material.name,
                                         f"{_units.to_display(cell.temperature):.4g}"])
        except OSError as e:
            QMessageBox.warning(window, "Export Failed", f"Could not write:\n{e}")

    window.save_requested.connect(_do_save)
    window.save_as_requested.connect(_do_save_as)
    window.export_requested.connect(_do_export)
    window.export_csv_requested.connect(_do_export_csv)
    window.set_save_fn(_do_save)

    # ── Open helpers ──────────────────────────────────────────────────────────

    def _make_unique_id(name: str, taken: set[str]) -> str:
        import re
        base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"
        candidate, i = base, 1
        while candidate in taken:
            candidate = f"{base}_{i}"
            i += 1
        return candidate

    def _rebuild_recent_menu(files: list[str] | None = None) -> None:
        if files is None:
            files = load_recent()
        window.open_recent_menu.clear()
        if files:
            for file_path in files:
                action = window.open_recent_menu.addAction(Path(file_path).name)
                action.setToolTip(file_path)
                action.triggered.connect(lambda _, p=file_path: _do_open(p))
        else:
            no_item = window.open_recent_menu.addAction("No Recent Files")
            no_item.setEnabled(False)

    def _do_open(path: str | None = None, add_to_recent: bool = True) -> None:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                window, "Open", "", "PyTherm Files (*.pytherm)"
            )
            if not path:
                return

        if not Path(path).exists():
            QMessageBox.warning(window, "File Not Found", f"Could not find:\n{path}")
            _rebuild_recent_menu(remove_recent(path))
            return

        if sim_clock.is_running:
            sim_clock.pause()

        if window.is_dirty and not _prompt_save_before_continuing("Open"):
            return

        try:
            data = load_pytherm(Path(path))
        except Exception as e:
            QMessageBox.critical(window, "Load Error", f"Failed to load file:\n{e}")
            return

        file_sw_ver = data.get("software_version")
        if file_sw_ver and file_sw_ver != VERSION and add_to_recent:
            box = QMessageBox(window)
            box.setWindowTitle("Version Mismatch")
            box.setIcon(QMessageBox.Icon.Information)
            box.setText(
                f"This file was saved with PyTherm v{file_sw_ver}.\n"
                f"You are running v{VERSION}.\n\n"
                "The file should load correctly, but minor incompatibilities "
                "may occur."
            )
            continue_btn = box.addButton("Continue", QMessageBox.ButtonRole.AcceptRole)  # noqa: F841
            cancel_btn   = box.addButton("Cancel",   QMessageBox.ButtonRole.RejectRole)
            box.exec()
            if box.clickedButton() == cancel_btn:
                return

        # Build material lookup: file material-id → final Material
        taken_ids   = set(registry.all_materials.keys())
        taken_names = {m.name for m in registry.all_materials.values()}
        file_id_to_material: dict[str, Material] = dict(registry.all_materials)

        bundled_mats: list[Material] = []
        for entry in data.get("custom_materials", []):
            try:
                bundled_mats.append(Material(**entry, is_builtin=False))
            except Exception as e:
                print(f"Warning: skipped malformed custom material entry: {e}")

        # Exact duplicates: same id AND same properties — silently reuse existing.
        def _is_exact_duplicate(mat: Material) -> bool:
            existing = registry.all_materials.get(mat.id)
            return (
                existing is not None
                and existing.name == mat.name
                and existing.color == mat.color
                and existing.k == mat.k
                and existing.rho == mat.rho
                and existing.cp == mat.cp
                and existing.note == mat.note
            )

        true_new: list[Material] = []
        for mat in bundled_mats:
            if _is_exact_duplicate(mat):
                file_id_to_material[mat.id] = registry.all_materials[mat.id]
            else:
                true_new.append(mat)

        conflicting    = [m for m in true_new if m.name in taken_names]
        non_conflicting = [m for m in true_new if m.name not in taken_names]
        to_add: list[Material] = []

        for mat in non_conflicting:
            new_id = _make_unique_id(mat.name, taken_ids)
            taken_ids.add(new_id)
            taken_names.add(mat.name)
            final = Material(
                id=new_id, name=mat.name, color=mat.color,
                k=mat.k, rho=mat.rho, cp=mat.cp, note=mat.note, is_builtin=False,
            )
            file_id_to_material[mat.id] = final
            to_add.append(final)

        if conflicting:
            conflict_dlg = MaterialConflictDialog(conflicting, set(taken_names), window)
            if conflict_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            for original, new_name in conflict_dlg.resolved():
                new_id = _make_unique_id(new_name, taken_ids)
                taken_ids.add(new_id)
                taken_names.add(new_name)
                final = Material(
                    id=new_id, name=new_name, color=original.color,
                    k=original.k, rho=original.rho, cp=original.cp,
                    note=original.note, is_builtin=False,
                )
                file_id_to_material[original.id] = final
                to_add.append(final)

        if to_add:
            import_dlg = MaterialImportDialog(to_add, window)
            if import_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            if import_dlg.persist():
                for mat in to_add:
                    registry.add_or_update_custom(mat)
            else:
                registry.add_session_materials(to_add)
            sidebar.refresh_materials(registry.all_materials)

        gd  = data["grid"]
        air = registry.get("air")
        new_grid = Grid(gd["rows"], gd["cols"], air, ambient_temp_k=gd["ambient_temp_k"])
        for cd in data.get("cells", []):
            r, c = cd["row"], cd["col"]
            mat  = file_id_to_material.get(cd["material_id"], air)
            new_grid.set_cell(
                r, c,
                material=mat,
                temperature=cd["temperature_k"],
                is_fixed=cd["is_fixed"],
                fixed_temp=cd.get("fixed_temp_k", 0.0),
                is_flux=cd.get("is_flux", False),
                flux_q=cd.get("flux_q", 0.0),
                label=cd.get("label", ""),
                protected=cd.get("protected", False),
            )

        ss = data.get("sim_settings", {})
        _apply_new_grid(
            new_grid, gd["dx_m"],
            bc=ss.get("boundary_conditions", _DEFAULT_BC),
            file_path=path if add_to_recent else None,
        )
        if add_to_recent:
            _rebuild_recent_menu(add_recent(path))

    def _rebuild_template_menu() -> None:
        """Scan <project_root>/templates/ and rebuild the Open Template menu."""
        window.open_template_menu.clear()
        templates_dir = get_templates_dir()
        if not templates_dir.is_dir():
            no_item = window.open_template_menu.addAction("No templates folder found")
            no_item.setEnabled(False)
            return
        _add_template_entries(window.open_template_menu, templates_dir)

    def _add_template_entries(menu, directory: Path) -> None:
        """Recursively add .pytherm files and subdirectory submenus."""
        found_any = False
        for item in sorted(directory.iterdir()):
            if item.is_dir():
                submenu = menu.addMenu(item.name)
                _add_template_entries(submenu, item)
                found_any = True
            elif item.suffix.lower() == ".pytherm":
                action = menu.addAction(item.stem)
                action.setToolTip(str(item))
                action.triggered.connect(
                    lambda _checked=False, p=str(item): _do_open(p, add_to_recent=False)
                )
                found_any = True
        if not found_any:
            empty = menu.addAction("(empty)")
            empty.setEnabled(False)

    def _on_return_to_welcome(_checked: bool = False) -> None:
        if sim_clock.is_running:
            sim_clock.pause()
        if window.is_dirty and not _prompt_save_before_continuing("Return to Welcome"):
            return
        welcome2 = WelcomeDialog(load_recent(), registry.all_materials)
        welcome2.exec()
        if welcome2.action == "new":
            rows, cols, dx_m, ambient_k, base_mat_id = welcome2.new_grid_values()
            new_grid = Grid(rows, cols, registry.get(base_mat_id), ambient_temp_k=ambient_k)
            _apply_new_grid(new_grid, dx_m)
        elif welcome2.action == "open":
            _do_open()
        elif welcome2.action == "recent":
            _do_open(welcome2.recent_path)

    window.welcome_requested.connect(_on_return_to_welcome)
    window.open_requested.connect(_do_open)
    _rebuild_recent_menu()   # populate on startup
    _rebuild_template_menu() # populate on startup

    # ── New Grid ──────────────────────────────────────────────────────────────

    def _on_new_grid() -> None:
        if sim_clock.is_running:
            ans = QMessageBox.question(
                window, "New Grid",
                "The simulation is running. Stop it and create a new grid?",
            )
            if ans != QMessageBox.StandardButton.Yes:
                return
            sim_clock.pause()

        if window.is_dirty and not _prompt_save_before_continuing("New Grid"):
            return

        dlg = NewGridDialog(registry.all_materials, window, defaults=prefs)
        if dlg.exec() != NewGridDialog.DialogCode.Accepted:
            return

        rows, cols, dx_m, ambient_k, base_mat_id = dlg.values()
        new_grid = Grid(rows, cols, registry.get(base_mat_id), ambient_temp_k=ambient_k)
        _apply_new_grid(new_grid, dx_m, bc=_DEFAULT_BC)

    window.new_grid_requested.connect(_on_new_grid)

    # ── Dirty tracking ────────────────────────────────────────────────────────
    view.cell_painted.connect(window.mark_dirty)
    sidebar.props_panel.cell_modified.connect(window.mark_dirty)
    sidebar.group_panel.group_modified.connect(window.mark_dirty)

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _push_history() -> None:
        history.push(grid)

    view.paint_started.connect(_push_history)
    view.paint_started.connect(sim_clock.invalidate_arrays)
    sidebar.props_panel.pre_cell_modified.connect(_push_history)
    sidebar.group_panel.pre_group_modified.connect(_push_history)

    def _restore_orphaned_materials() -> None:
        """Re-register any grid materials that were deleted but restored by undo/redo."""
        all_mats = registry.all_materials
        orphaned = []
        for r in range(grid.rows):
            for c in range(grid.cols):
                mat = grid.cell(r, c).material
                if not mat.is_builtin and mat.id not in all_mats:
                    orphaned.append(mat)
        if orphaned:
            registry.add_session_materials(orphaned)
            sidebar.refresh_materials(registry.all_materials)

    def _do_undo() -> None:
        if history.undo(grid):
            _restore_orphaned_materials()
            sim_clock.invalidate_arrays()
            scene.invalidate_fixed_cells()
            scene.refresh()
            window.mark_dirty()

    def _do_redo() -> None:
        if history.redo(grid):
            _restore_orphaned_materials()
            sim_clock.invalidate_arrays()
            scene.invalidate_fixed_cells()
            scene.refresh()
            window.mark_dirty()

    window.undo_requested.connect(_do_undo)
    window.redo_requested.connect(_do_redo)

    # ── Substep count display ────────────────────────────────────────────────
    sim_clock.tick.connect(lambda _: bottom_bar.update_substep_count(solver.last_substep_count))

    # ── Eyedropper wiring ────────────────────────────────────────────────────
    view.set_vacuum_material(registry.get("vacuum"))
    view.material_eyedropped.connect(sidebar.picker.select_material)

    # ── Keyboard shortcuts ────────────────────────────────────────────────────
    QShortcut(QKeySequence("D"),     window).activated.connect(toolbar.activate_draw_mode)
    QShortcut(QKeySequence("S"),     window).activated.connect(toolbar.activate_select_mode)
    QShortcut(QKeySequence("W"),     window).activated.connect(toolbar.activate_fill_mode)
    QShortcut(QKeySequence("Space"), window).activated.connect(bottom_bar.toggle_play_pause)
    QShortcut(QKeySequence("R"),     window).activated.connect(bottom_bar.trigger_reset)
    QShortcut(QKeySequence("F"),               window).activated.connect(view.fit_grid)
    QShortcut(QKeySequence("Ctrl+Shift+F"),    window).activated.connect(view.zoom_to_selection)
    QShortcut(QKeySequence("G"),               window).activated.connect(toolbar.toggle_grid_lines)
    QShortcut(QKeySequence("N"),               window).activated.connect(bottom_bar.trigger_step)
    QShortcut(QKeySequence("H"),               window).activated.connect(toolbar.activate_heatmap_mode)
    QShortcut(QKeySequence("M"),               window).activated.connect(toolbar.activate_material_mode)
    QShortcut(QKeySequence("Ctrl+U"),          window).activated.connect(bottom_bar.cycle_unit)

    # ── Find Hottest / Coldest Cell ───────────────────────────────────────────

    def _find_extremal_cell(find_max: bool) -> None:
        T = grid.temperature_array()
        rho_cp = grid.rho_cp_array()
        # active = non-vacuum AND not fixed-T
        mask = (rho_cp > 0) & ~grid.fixed_mask()
        if not np.any(mask):
            window.statusBar().showMessage("No active cells to search.")
            return
        if find_max:
            idx = int(np.argmax(np.where(mask, T, -np.inf)))
        else:
            idx = int(np.argmin(np.where(mask, T, np.inf)))
        r, c = divmod(idx, grid.cols)
        view.select_cells([(r, c)], center=True)
        toolbar.activate_select_mode()

    window.find_hottest_requested.connect(lambda: _find_extremal_cell(True))
    window.find_coldest_requested.connect(lambda: _find_extremal_cell(False))

    # ── Reset Selection to Ambient ─────────────────────────────────────────────

    def _reset_selection_to_ambient() -> None:
        sel = [
            (r, c) for r, c in _current_selection
            if not grid.cell(r, c).is_fixed and not grid.cell(r, c).is_flux
            and not grid.cell(r, c).material.is_vacuum
            and not grid.cell(r, c).protected
        ]
        if not sel:
            return
        _push_history()
        for r, c in sel:
            grid.cell(r, c).temperature = grid.ambient_temp_k
        sim_clock.invalidate_arrays()
        scene.refresh()
        window.mark_dirty()

    window.reset_selection_requested.connect(_reset_selection_to_ambient)

    # ── Resize Grid ────────────────────────────────────────────────────────────

    def _on_resize_grid(_checked: bool = False) -> None:
        if sim_clock.is_running:
            sim_clock.pause()
        dlg = ResizeGridDialog(grid.rows, grid.cols, window)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        top, right, bottom, left = dlg.values()
        vacuum = registry.get("vacuum")
        grid.resize(top, right, bottom, left, vacuum)
        history.clear()
        sim_clock.reset()
        sim_clock.set_grid(grid)
        scene.set_grid(grid)
        sidebar.set_grid(grid)
        for _p in _plot_panels:
            _p.set_grid(grid)
        _on_cells_selected([])
        window.mark_dirty()

    window.resize_grid_requested.connect(_on_resize_grid)

    # ── Command Palette ───────────────────────────────────────────────────────

    def _open_command_palette(_checked: bool = False) -> None:
        entries: list[tuple[str, Callable]] = [
            # Draw modes
            ("Draw mode",   toolbar.activate_draw_mode),
            ("Select mode", toolbar.activate_select_mode),
            ("Fill mode",   toolbar.activate_fill_mode),
            # View modes
            ("Heatmap view",   toolbar.activate_heatmap_mode),
            ("Material view",  toolbar.activate_material_mode),
            ("Toggle grid lines",    toolbar.toggle_grid_lines),
            ("Fit grid to window",   view.fit_grid),
            # Sim controls
            ("Play / Pause",         bottom_bar.toggle_play_pause),
            ("Reset simulation",     bottom_bar.trigger_reset),
            ("Step simulation",      bottom_bar.trigger_step),
            # File
            ("New Grid",    window.new_grid_requested.emit),
            ("Open...",     window.open_requested.emit),
            ("Save",        window.save_requested.emit),
            ("Save As...",  window.save_as_requested.emit),
            ("Export View as Image...", window.export_requested.emit),
            ("Export Cell Data as CSV...", window.export_csv_requested.emit),
            # Edit
            ("Undo",   window.undo_requested.emit),
            ("Redo",   window.redo_requested.emit),
            ("Materials Manager...", window.materials_manager_requested.emit),
            ("Find Hottest Cell",    lambda: _find_extremal_cell(True)),
            ("Find Coldest Cell",    lambda: _find_extremal_cell(False)),
            ("Reset Selection to Ambient", _reset_selection_to_ambient),
            ("Resize Grid...",       window.resize_grid_requested.emit),
            # View
            ("Temperature Legend",           lambda: window._legend_action.toggle()),
            ("Toggle Temperature Rise (dT)", lambda: window._delta_action.toggle()),
            ("New Temperature Plot",     _make_plot_panel),
            # Tools
            ("Preferences...",   window.preferences_requested.emit),
            ("Debug Diagnostics...", window.diagnostics_requested.emit),
        ]
        # Add "Switch to <material>" for every material in the registry
        for mat_id, mat in registry.all_materials.items():
            if not mat.is_vacuum:
                def _switch(m=mat):
                    sidebar.picker.select_material(m)
                entries.append((f"Material: {mat.name}", _switch))

        dlg = CommandPalette(entries, window)
        dlg.exec()

    window.command_palette_requested.connect(_open_command_palette)

    # ── Materials Manager ─────────────────────────────────────────────────────

    def _on_materials_manager() -> None:
        dlg = MaterialsManagerDialog(registry, grid, window)
        dlg.exec()
        if dlg.changed:
            sidebar.refresh_materials(registry.all_materials)
            scene.refresh()
            window.mark_dirty()

    window.materials_manager_requested.connect(_on_materials_manager)

    # ── Welcome dialog ────────────────────────────────────────────────────────
    welcome = WelcomeDialog(load_recent(), registry.all_materials)
    welcome.exec()

    if welcome.action == "new":
        rows, cols, dx_m, ambient_k, base_mat_id = welcome.new_grid_values()
        new_grid = Grid(rows, cols, registry.get(base_mat_id), ambient_temp_k=ambient_k)
        _apply_new_grid(new_grid, dx_m)

    window.show()

    if welcome.action == "open":
        _do_open()
    elif welcome.action == "recent":
        _do_open(welcome.recent_path)

    return app, window
