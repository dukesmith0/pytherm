"""Tests for UI components: GridScene, TempPlotPanel, CommandPalette, ConvergencePanel, MainWindow."""
from __future__ import annotations

import math
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor


# ── GridScene ────────────────────────────────────────────────────────────────

def test_gridscene_isotherm(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    scene.set_isotherm(True, 25.0)
    assert scene._isotherm_enabled is True
    assert abs(scene._isotherm_interval_k - 25.0) < 1e-9


def test_gridscene_hotspot_threshold(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    scene.set_hotspot_threshold(400.0)
    assert scene._hotspot_enabled is True
    assert abs(scene._hotspot_threshold_k - 400.0) < 1e-9


def test_gridscene_hotspot_nan_disables(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    scene.set_hotspot_threshold(400.0)
    scene.set_hotspot_threshold(float("nan"))
    assert scene._hotspot_enabled is False


def test_gridscene_hotspot_count(make_grid):
    from src.ui.grid_scene import GridScene
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=500.0)
    grid.set_cell(0, 1, material=al, temperature=300.0)
    scene = GridScene(grid)
    scene.set_hotspot_threshold(400.0)
    assert scene.hotspot_count == 1


def test_gridscene_hotspot_zero_when_disabled(make_grid):
    from src.ui.grid_scene import GridScene
    grid, reg = make_grid()
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=500.0)
    scene = GridScene(grid)
    assert scene.hotspot_count == 0


def test_gridscene_isotherm_color(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid(4, 4)
    scene = GridScene(grid)
    scene.set_isotherm_color(QColor(255, 0, 0))
    assert scene._isotherm_color == QColor(255, 0, 0)


def test_gridscene_isotherm_v2(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid(4, 4)
    scene = GridScene(grid)
    scene.set_isotherm(True, 25.0)
    assert scene._isotherm_enabled is True
    assert abs(scene._isotherm_interval_k - 25.0) < 1e-9


def test_gridscene_flow_view(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid(4, 4)
    scene = GridScene(grid)
    scene.set_view_mode("flow")
    assert scene._view_mode == "flow"


# ── TempPlotPanel ────────────────────────────────────────────────────────────

def test_plotpanel_pin_default(make_grid):
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = make_grid()
    panel = TempPlotPanel(grid)
    assert panel.is_pinned is False


def test_plotpanel_set_tracked_ignored_when_pinned(make_grid):
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = make_grid()
    panel = TempPlotPanel(grid)
    panel.set_tracked_cells([(0, 0)])
    panel._pin_btn.setChecked(True)
    panel.set_tracked_cells([(1, 1)])
    assert panel._tracked == [(0, 0)]


def test_plotpanel_set_tracked_after_unpin(make_grid):
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = make_grid()
    panel = TempPlotPanel(grid)
    panel._pin_btn.setChecked(True)
    panel._pin_btn.setChecked(False)
    panel.set_tracked_cells([(2, 3)])
    assert panel._tracked == [(2, 3)]


def test_plotpanel_closing_signal():
    from src.ui.temp_plot_panel import TempPlotPanel
    assert hasattr(TempPlotPanel, "closing")


def test_plotpanel_set_sync_hover(make_grid):
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = make_grid()
    panel = TempPlotPanel(grid)
    panel.set_sync_hover(7.0)
    assert panel._canvas._sync_hover_t == 7.0


def test_plotpanel_set_sync_pin(make_grid):
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = make_grid()
    panel = TempPlotPanel(grid)
    panel.set_sync_pin(2.5)
    assert panel._canvas._sync_pin_t == 2.5


def test_plotpanel_set_grid_clears_sync(make_grid):
    from src.ui.temp_plot_panel import TempPlotPanel
    grid, _ = make_grid()
    panel = TempPlotPanel(grid)
    panel.set_sync_hover(3.0)
    panel.set_sync_pin(1.0)
    panel.set_grid(grid)
    assert panel._canvas._sync_hover_t is None
    assert panel._canvas._sync_pin_t is None


def test_plotpanel_save_round_trip(make_grid):
    import json, os, tempfile
    from src.ui.temp_plot_panel import TempPlotPanel
    from src.ui.plot_viewer import load_pythermplot
    grid, _ = make_grid(4, 4)
    panel = TempPlotPanel(grid)
    panel.set_tracked_cells([(0, 0)])
    panel._canvas.add_point("(0,0)", 0.0, 300.0)
    panel._canvas.add_point("(0,0)", 1.0, 310.0)
    with tempfile.NamedTemporaryFile(suffix=".pythermplot", delete=False) as f:
        path = f.name
    try:
        series = panel._canvas._series
        data = {"version": 1, "unit": "K",
                "series": {name: [[t, T] for t, T in pts] for name, pts in series.items() if pts}}
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fw:
            json.dump(data, fw)
        os.replace(tmp, path)
        loaded = load_pythermplot(path)
        assert "(0,0)" in loaded["series"]
        assert len(loaded["series"]["(0,0)"]) == 2
    finally:
        os.unlink(path)


# ── _PlotCanvas ──────────────────────────────────────────────────────────────

def test_plotcanvas_pinned_starts_empty():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    assert c._pinned_points == []


def test_plotcanvas_set_series_clears_pins():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_series(["A"])
    c.add_point("A", 1.0, 300.0)
    c._pinned_points.append(("A", 1.0, 300.0))
    c.set_series(["B"])
    assert c._pinned_points == []


def test_plotcanvas_clear_clears_pins():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_series(["A"])
    c.add_point("A", 1.0, 300.0)
    c._pinned_points.append(("A", 1.0, 300.0))
    c.clear()
    assert c._pinned_points == []


def test_plotcanvas_sync_hover_set():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_hover(5.5)
    assert c._sync_hover_t == 5.5


def test_plotcanvas_sync_hover_clear():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_hover(5.5)
    c.set_sync_hover(None)
    assert c._sync_hover_t is None


def test_plotcanvas_sync_pin_set():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_pin(3.14)
    assert c._sync_pin_t == 3.14


def test_plotcanvas_sync_pin_clear():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.set_sync_pin(3.14)
    c.set_sync_pin(None)
    assert c._sync_pin_t is None


def test_plotcanvas_find_nearest_empty():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    assert c._find_nearest(200.0, 100.0) is None


def test_plotcanvas_find_nearest():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c.add_point("A", 5.0, 350.0)
    result = c._find_nearest(55.0, 155.0)
    assert result is not None
    name, t, _ = result
    assert name == "A"
    assert abs(t - 0.0) < 1e-6


def test_plotcanvas_click_adds_pin():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c._handle_click(55.0, 100.0, Qt.KeyboardModifier.NoModifier)
    assert len(c._pinned_points) == 1
    assert c._pinned_points[0][0] == "A"


def test_plotcanvas_click_toggles_pin():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c._handle_click(55.0, 100.0, Qt.KeyboardModifier.NoModifier)
    assert len(c._pinned_points) == 1
    c._handle_click(55.0, 100.0, Qt.KeyboardModifier.NoModifier)
    assert len(c._pinned_points) == 0


def test_plotcanvas_shift_click_emits_sync():
    from src.ui.temp_plot_panel import _PlotCanvas
    c = _PlotCanvas()
    c.resize(400, 200)
    c.set_series(["A"])
    c.add_point("A", 0.0, 300.0)
    c.add_point("A", 5.0, 350.0)
    received = []
    c.sync_pin_changed.connect(lambda t: received.append(t))
    c._handle_click(200.0, 100.0, Qt.KeyboardModifier.ShiftModifier)
    assert len(received) == 1
    assert received[0] is not None


# ── CommandPalette ───────────────────────────────────────────────────────────

def test_command_palette_filter():
    from src.ui.command_palette import CommandPalette
    entries = [("Draw mode", lambda: None), ("Heatmap view", lambda: None), ("Reset", lambda: None)]
    dlg = CommandPalette(entries)
    dlg._filter.setText("draw")
    visible = [dlg._list.item(i) for i in range(dlg._list.count()) if not dlg._list.item(i).isHidden()]
    assert len(visible) == 1 and visible[0].text() == "Draw mode"


def test_command_palette_empty_filter():
    from src.ui.command_palette import CommandPalette
    entries = [("Alpha", lambda: None), ("Beta", lambda: None), ("Gamma", lambda: None)]
    dlg = CommandPalette(entries)
    dlg._filter.setText("")
    visible = [dlg._list.item(i) for i in range(dlg._list.count()) if not dlg._list.item(i).isHidden()]
    assert len(visible) == 3


# ── ConvergencePanel ─────────────────────────────────────────────────────────

def test_convergence_first_tick_skipped():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    assert panel._is_first_tick
    panel.on_tick(0.033, 0.001, 0.001)
    assert not panel._is_first_tick
    assert len(panel._canvas._data) == 0


def test_convergence_second_tick_adds():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    panel.on_tick(0.033, 0.001, 0.001)
    panel.on_tick(0.066, 0.005, 0.001)
    assert len(panel._canvas._data) == 1
    t, rate = panel._canvas._data[0]
    assert abs(t - 0.066) < 1e-9
    assert abs(rate - 5.0) < 1e-9


def test_convergence_clear():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    panel.on_tick(0.033, 0.001, 0.001)
    panel.on_tick(0.066, 0.005, 0.001)
    panel.clear_history()
    assert panel._is_first_tick
    assert len(panel._canvas._data) == 0


def test_convergence_ss_threshold():
    from src.ui.convergence_panel import ConvergencePanel
    panel = ConvergencePanel()
    panel.set_ss_threshold(0.05)
    assert panel._canvas._ss_threshold == 0.05


# ── MaterialPicker ───────────────────────────────────────────────────────────

def test_material_picker_nested_groups():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from src.models.material_registry import MaterialRegistry
    from src.ui.sidebar import MaterialPicker
    from pathlib import Path
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    picker = MaterialPicker(reg.all_materials)
    nested = [k for k, v in picker._group_info.items() if v[3] > 0]
    assert len(nested) > 10


def test_material_picker_group_info_tuple():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from src.models.material_registry import MaterialRegistry
    from src.ui.sidebar import MaterialPicker
    from pathlib import Path
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    picker = MaterialPicker(reg.all_materials)
    for key, info in picker._group_info.items():
        assert len(info) == 4


def test_material_picker_filter_propagates():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from src.models.material_registry import MaterialRegistry
    from src.ui.sidebar import MaterialPicker
    from pathlib import Path
    data_dir = Path(__file__).parent.parent / "data"
    reg = MaterialRegistry(data_dir / "materials.json", data_dir / "user_materials.json")
    picker = MaterialPicker(reg.all_materials)
    picker.show()
    picker._apply_filter("copper")
    if "Metals,Pure" in picker._group_info:
        h, cw, _, _ = picker._group_info["Metals,Pure"]
        assert not h.isHidden()
    if "Metals" in picker._group_info:
        h, cw, _, _ = picker._group_info["Metals"]
        assert not h.isHidden()


# ── MainWindow ───────────────────────────────────────────────────────────────

def test_mainwindow_open_plot_signal():
    from src.ui.main_window import MainWindow
    w = MainWindow()
    assert hasattr(w, "open_plot_requested")


def test_mainwindow_convergence_signal():
    from src.ui.main_window import MainWindow
    w = MainWindow()
    assert hasattr(w, "convergence_graph_requested")


def test_mainwindow_thermal_resistance_signal():
    from src.ui.main_window import MainWindow
    w = MainWindow()
    assert hasattr(w, "thermal_resistance_requested")


# ── .pythermplot format ──────────────────────────────────────────────────────

def test_pythermplot_round_trip():
    import json, tempfile
    data = {"version": 1, "unit": "K",
            "series": {"test": [[0.0, 300.0], [1.0, 310.0], [2.0, 320.0]]}}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pythermplot", delete=False, encoding="utf-8") as f:
        json.dump(data, f); path = f.name
    try:
        from src.ui.plot_viewer import load_pythermplot
        loaded = load_pythermplot(path)
        assert loaded["version"] == 1
        assert "test" in loaded["series"]
        assert len(loaded["series"]["test"]) == 3
    finally:
        os.unlink(path)


def test_pythermplot_invalid():
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pythermplot", delete=False, encoding="utf-8") as f:
        f.write('{"version": 1}'); path = f.name
    try:
        from src.ui.plot_viewer import load_pythermplot
        import pytest
        with pytest.raises(ValueError):
            load_pythermplot(path)
    finally:
        os.unlink(path)


# ── Heat flow vectors (v1.1.0) ───────────────────────────────────────────────

def test_gridscene_heat_vectors_default_off(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    assert scene._show_heat_vectors is False


def test_gridscene_heat_vectors_toggle(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    scene.set_show_heat_vectors(True)
    assert scene._show_heat_vectors is True
    scene.set_show_heat_vectors(False)
    assert scene._show_heat_vectors is False


def test_gridscene_heat_vectors_vacuum_grid(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid(2, 2)
    scene = GridScene(grid)
    scene.set_show_heat_vectors(True)
    scene.refresh()


def test_gridscene_heat_vectors_1x1(make_grid):
    from src.ui.grid_scene import GridScene
    grid, reg = make_grid(1, 1)
    al = reg.get("al6061")
    grid.set_cell(0, 0, material=al, temperature=350.0)
    scene = GridScene(grid)
    scene.set_show_heat_vectors(True)
    scene.refresh()


# ── Isotherm edge cases (v1.1.0) ────────────────────────────────────────────

def test_isotherm_zero_interval_clamped(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    scene.set_isotherm(True, 0.0)
    assert scene._isotherm_interval_k >= 0.01


def test_isotherm_negative_interval_clamped(make_grid):
    from src.ui.grid_scene import GridScene
    grid, _ = make_grid()
    scene = GridScene(grid)
    scene.set_isotherm(True, -10.0)
    assert scene._isotherm_interval_k >= 0.01


# ── Resize dialog clamping (v1.1.0) ─────────────────────────────────────────

def test_resize_dialog_max_at_200():
    from src.ui.resize_grid_dialog import ResizeGridDialog
    dlg = ResizeGridDialog(current_rows=200, current_cols=200)
    assert dlg._top.maximum() == 0
    assert dlg._bottom.maximum() == 0
    assert dlg._left.maximum() == 0
    assert dlg._right.maximum() == 0


def test_resize_dialog_max_at_150():
    from src.ui.resize_grid_dialog import ResizeGridDialog
    dlg = ResizeGridDialog(current_rows=150, current_cols=150)
    assert dlg._top.maximum() == 50
    assert dlg._left.maximum() == 50


def test_resize_dialog_trim_minimum():
    from src.ui.resize_grid_dialog import ResizeGridDialog
    dlg = ResizeGridDialog(current_rows=3, current_cols=3)
    assert dlg._top.minimum() == -2
    assert dlg._left.minimum() == -2
