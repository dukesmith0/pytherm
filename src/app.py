from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtGui import QColor, QPalette, QShortcut, QKeySequence
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QMessageBox

from src.io.file_io import load_pytherm, save_pytherm
from src.io.recent_files import add_recent, load_recent, remove_recent
from src.models.material import Material
from src.models.material_registry import MaterialRegistry
from src.rendering import units as _units
from src.simulation.grid import Grid
from src.simulation.history import GridHistory
from src.simulation.sim_clock import SimClock
from src.simulation.solver import Solver
from src.ui.grid_scene import GridScene
from src.ui.grid_view import GridView
from src.ui.main_window import MainWindow
from src.ui.load_dialogs import MaterialConflictDialog, MaterialImportDialog
from src.ui.materials_manager import MaterialsManagerDialog
from src.ui.new_grid_dialog import NewGridDialog
from src.ui.save_dialogs import CustomMaterialsBundleDialog
from src.ui.sidebar import Sidebar
from src.ui.toolbar import Toolbar
from src.ui.welcome_dialog import WelcomeDialog, make_app_icon


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
    app.setWindowIcon(make_app_icon())

    _data_dir  = Path(__file__).parent.parent / "data"
    registry   = MaterialRegistry(_data_dir / "materials.json", _data_dir / "user_materials.json")
    materials  = registry.all_materials
    grid       = Grid(10, 10, registry.get("vacuum"), ambient_temp_k=293.15)
    scene      = GridScene(grid)
    view       = GridView(scene)

    # dx = physical cell size in metres; 1 cm default (user-configurable via New Grid)
    solver    = Solver(dx=0.01)
    sim_clock = SimClock(grid, solver, scene)

    history = GridHistory()

    toolbar = Toolbar()
    toolbar.set_dx(solver.dx)
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
            sim_clock.reset()
            window.mark_dirty()
        else:
            # Revert spinbox silently
            toolbar.set_dx(solver.dx)

    toolbar.dx_changed.connect(_on_dx_changed)
    sim_clock.tick.connect(toolbar.update_sim_time)
    sim_clock.state_changed.connect(toolbar.set_running)
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
    toolbar.abbr_toggled.connect(scene.set_show_abbr)

    # All closures below share 'grid' via nonlocal. _on_new_grid rebinds it
    # so Materials Manager, Save, etc. always operate on the live grid.
    window = MainWindow()
    window.addToolBar(toolbar)
    window.set_canvas_widget(view)
    window.set_sidebar_widget(sidebar)

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
        save_pytherm(Path(path), grid, solver.dx, custom_mats)
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

    window.save_requested.connect(_do_save)
    window.save_as_requested.connect(_do_save_as)
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

    def _do_open(path: str | None = None) -> None:
        nonlocal grid
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

        # Build material lookup: file material-id → final Material
        taken_ids   = set(registry.all_materials.keys())
        taken_names = {m.name for m in registry.all_materials.values()}
        file_id_to_material: dict[str, Material] = dict(registry.all_materials)

        bundled_mats: list[Material] = []
        for entry in data.get("custom_materials", []):
            try:
                bundled_mats.append(Material(**entry, is_builtin=False))
            except Exception:
                pass  # skip malformed entries

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
            )

        grid = new_grid
        solver.dx = gd["dx_m"]
        history.clear()
        sim_clock.reset()
        sim_clock.set_grid(grid)
        scene.set_grid(grid)
        sidebar.set_grid(grid)
        toolbar.set_dx(solver.dx)
        view.reset_zoom()
        window.mark_clean(path)
        _rebuild_recent_menu(add_recent(path))

    window.open_requested.connect(_do_open)
    _rebuild_recent_menu()  # populate on startup

    # ── New Grid ──────────────────────────────────────────────────────────────

    def _on_new_grid() -> None:
        nonlocal grid
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

        dlg = NewGridDialog(window)
        if dlg.exec() != NewGridDialog.DialogCode.Accepted:
            return

        rows, cols, dx_m, ambient_k = dlg.values()
        grid = Grid(rows, cols, registry.get("vacuum"), ambient_temp_k=ambient_k)
        solver.dx = dx_m
        history.clear()
        sim_clock.reset()
        sim_clock.set_grid(grid)
        scene.set_grid(grid)
        sidebar.set_grid(grid)
        toolbar.set_dx(solver.dx)
        view.reset_zoom()
        window.mark_clean()

    window.new_grid_requested.connect(_on_new_grid)

    # ── Dirty tracking ────────────────────────────────────────────────────────
    view.cell_painted.connect(window.mark_dirty)
    sidebar.props_panel.cell_modified.connect(window.mark_dirty)
    sidebar.group_panel.group_modified.connect(window.mark_dirty)

    # ── Undo / Redo ───────────────────────────────────────────────────────────

    def _push_history() -> None:
        history.push(grid)

    view.paint_started.connect(_push_history)
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
            scene.refresh()
            window.mark_dirty()

    def _do_redo() -> None:
        if history.redo(grid):
            _restore_orphaned_materials()
            scene.refresh()
            window.mark_dirty()

    window.undo_requested.connect(_do_undo)
    window.redo_requested.connect(_do_redo)

    # ── Keyboard shortcuts ────────────────────────────────────────────────────
    QShortcut(QKeySequence("D"),     window).activated.connect(toolbar.activate_draw_mode)
    QShortcut(QKeySequence("S"),     window).activated.connect(toolbar.activate_select_mode)
    QShortcut(QKeySequence("Space"), window).activated.connect(toolbar.toggle_play_pause)
    QShortcut(QKeySequence("R"),     window).activated.connect(toolbar.trigger_reset)
    QShortcut(QKeySequence("F"),     window).activated.connect(view.fit_grid)
    QShortcut(QKeySequence("G"),     window).activated.connect(toolbar.toggle_grid_lines)

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
    welcome = WelcomeDialog(load_recent())
    welcome.exec()

    if welcome.action == "new":
        rows, cols, dx_m, ambient_k = welcome.new_grid_values()
        grid = Grid(rows, cols, registry.get("vacuum"), ambient_temp_k=ambient_k)
        solver.dx = dx_m
        history.clear()
        sim_clock.reset()
        sim_clock.set_grid(grid)
        scene.set_grid(grid)
        sidebar.set_grid(grid)
        toolbar.set_dx(solver.dx)
        window.mark_clean()

    window.show()

    if welcome.action == "open":
        _do_open()
    elif welcome.action == "recent":
        _do_open(welcome.recent_path)

    return app, window
