from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.models.material import Material
from src.rendering import units as _units
from src.simulation.grid import Grid


class MaterialPicker(QWidget):
    """Clickable list of materials. Emits material_selected when one is chosen."""

    material_selected = pyqtSignal(object)  # emits Material

    def __init__(self, materials: dict[str, Material], parent=None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 0)
        layout.setSpacing(3)

        header = QLabel("MATERIAL")
        header.setStyleSheet("color: #777; font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(header)

        for mat in materials.values():
            btn = self._make_button(mat)
            self._buttons[mat.id] = btn
            layout.addWidget(btn)

        layout.addStretch()

        # Emit initial selection without waiting for user click
        first = next(iter(materials.values()))
        self._set_active(first, emit=False)  # view will be set explicitly in app.py

    def _make_button(self, mat: Material) -> QPushButton:
        text_color = "#000" if _luminance(mat.color) > 0.5 else "#eee"
        btn = QPushButton(mat.name)
        btn.setCheckable(True)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {mat.color};
                color: {text_color};
                border: 2px solid transparent;
                border-radius: 3px;
                padding: 5px 8px;
                text-align: left;
                font-size: 12px;
            }}
            QPushButton:checked {{
                border: 2px solid #ffffff;
            }}
        """)
        btn.clicked.connect(lambda _checked, m=mat: self._set_active(m))
        return btn

    def _set_active(self, material: Material, emit: bool = True) -> None:
        for btn in self._buttons.values():
            btn.setChecked(False)
        self._buttons[material.id].setChecked(True)
        if emit:
            self.material_selected.emit(material)


class CellPropertiesPanel(QWidget):
    """Shows and edits the properties of the currently selected cell."""

    cell_modified = pyqtSignal()

    def __init__(self, grid: Grid, materials: dict[str, Material], parent=None) -> None:
        super().__init__(parent)
        self._grid = grid
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._current: tuple[int, int] | None = None
        self._sim_running: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("CELL PROPERTIES")
        header.setStyleSheet("color: #777; font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(header)

        # Material selector
        layout.addWidget(_small_label("Material"))
        self._mat_combo = QComboBox()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        layout.addWidget(self._mat_combo)

        # Temperature
        layout.addWidget(_small_label("Temperature"))
        self._temp_spin = QDoubleSpinBox()
        lo, hi = _units.spinbox_range()
        self._temp_spin.setRange(lo, hi)
        self._temp_spin.setDecimals(1)
        self._temp_spin.setSuffix(f" {_units.suffix()}")
        layout.addWidget(self._temp_spin)

        # Heat source toggle
        self._fixed_check = QCheckBox("Heat source (fixed T)")
        self._fixed_check.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(self._fixed_check)

        # Fixed-temperature row (hidden until heat source is checked)
        self._fixed_row = QWidget()
        fixed_inner = QVBoxLayout(self._fixed_row)
        fixed_inner.setContentsMargins(0, 0, 0, 0)
        fixed_inner.setSpacing(2)
        fixed_inner.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = QDoubleSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fixed_inner.addWidget(self._fixed_temp_spin)
        self._fixed_row.setVisible(False)
        layout.addWidget(self._fixed_row)

        layout.addStretch()

        # Connections
        self._mat_combo.currentIndexChanged.connect(self._on_material_changed)
        self._temp_spin.valueChanged.connect(self._on_temp_changed)
        self._fixed_check.toggled.connect(self._on_fixed_toggled)
        self._fixed_temp_spin.valueChanged.connect(self._on_fixed_temp_changed)

        self.setEnabled(False)

    def show_cell(self, row: int, col: int) -> None:
        self._current = (row, col)
        cell = self._grid.cell(row, col)

        # Populate controls without triggering change signals
        for w in (self._mat_combo, self._temp_spin, self._fixed_check, self._fixed_temp_spin):
            w.blockSignals(True)

        idx = self._mat_ids.index(cell.material.id) if cell.material.id in self._mat_ids else 0
        self._mat_combo.setCurrentIndex(idx)
        self._temp_spin.setValue(_units.to_display(cell.temperature))
        self._fixed_check.setChecked(cell.is_fixed)
        self._fixed_temp_spin.setValue(_units.to_display(cell.fixed_temp))
        self._fixed_row.setVisible(cell.is_fixed)
        self._temp_spin.setEnabled(not cell.is_fixed and not self._sim_running)

        for w in (self._mat_combo, self._temp_spin, self._fixed_check, self._fixed_temp_spin):
            w.blockSignals(False)

        self.setEnabled(True)

    def set_grid(self, grid: Grid) -> None:
        """Called when a new grid is loaded — resets the panel."""
        self._grid = grid
        self._current = None
        self.setEnabled(False)

    def refresh_display(self) -> None:
        """Re-read the selected cell's temperature and update the spinbox (no signal emitted).
        Called each sim tick so the display stays live while the sim is running."""
        if self._current is None:
            return
        cell = self._grid.cell(*self._current)
        self._temp_spin.blockSignals(True)
        self._temp_spin.setValue(_units.to_display(cell.temperature))
        self._temp_spin.blockSignals(False)

    def set_sim_running(self, running: bool) -> None:
        """Grey out the temperature spinbox while the simulation is running."""
        self._sim_running = running
        if self._current is not None:
            cell = self._grid.cell(*self._current)
            self._temp_spin.setEnabled(not running and not cell.is_fixed)

    def refresh_units(self) -> None:
        """Update spinbox suffixes and values when the display unit changes."""
        suf    = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        if self._current is not None:
            cell = self._grid.cell(*self._current)
            for spin in (self._temp_spin, self._fixed_temp_spin):
                spin.blockSignals(True)
                spin.setSuffix(suf)
                spin.setRange(lo, hi)
                spin.blockSignals(False)
            self._temp_spin.blockSignals(True)
            self._temp_spin.setValue(_units.to_display(cell.temperature))
            self._temp_spin.blockSignals(False)
            self._fixed_temp_spin.blockSignals(True)
            self._fixed_temp_spin.setValue(_units.to_display(cell.fixed_temp))
            self._fixed_temp_spin.blockSignals(False)
        else:
            for spin in (self._temp_spin, self._fixed_temp_spin):
                spin.blockSignals(True)
                spin.setSuffix(suf)
                spin.setRange(lo, hi)
                spin.blockSignals(False)

    # --- Signal handlers ---

    def _on_material_changed(self, idx: int) -> None:
        if self._current is None:
            return
        mat_id = self._mat_combo.itemData(idx)
        r, c = self._current
        self._grid.set_cell(r, c, material=self._materials[mat_id])
        self.cell_modified.emit()

    def _on_temp_changed(self, value: float) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, temperature=_units.from_display(value))
        self.cell_modified.emit()

    def _on_fixed_toggled(self, checked: bool) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, is_fixed=checked)
        self._fixed_row.setVisible(checked)
        self._temp_spin.setEnabled(not checked)
        if checked:
            # Initialise fixed temp to current cell temp
            cur_temp = self._temp_spin.value()
            self._fixed_temp_spin.blockSignals(True)
            self._fixed_temp_spin.setValue(cur_temp)
            self._fixed_temp_spin.blockSignals(False)
            self._grid.set_cell(r, c, fixed_temp=_units.from_display(cur_temp))
        self.cell_modified.emit()

    def _on_fixed_temp_changed(self, value: float) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, fixed_temp=_units.from_display(value))
        self.cell_modified.emit()


class GroupEditPanel(QWidget):
    """Edit panel for a multi-cell selection — applies changes to all selected cells."""

    group_modified = pyqtSignal()

    def __init__(self, materials: dict[str, Material], grid: Grid, parent=None) -> None:
        super().__init__(parent)
        self._grid = grid
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._cells: list[tuple[int, int]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("GROUP EDIT")
        header.setStyleSheet("color: #777; font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(header)

        self._count_label = QLabel("0 cells selected")
        self._count_label.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(self._count_label)

        layout.addWidget(_small_label("Material"))
        self._mat_combo = QComboBox()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        layout.addWidget(self._mat_combo)

        # Starting temperature (initial value for non-fixed cells)
        layout.addWidget(_small_label("Starting temperature"))
        self._temp_spin = QDoubleSpinBox()
        lo, hi = _units.spinbox_range()
        self._temp_spin.setRange(lo, hi)
        self._temp_spin.setDecimals(1)
        self._temp_spin.setSuffix(f" {_units.suffix()}")
        layout.addWidget(self._temp_spin)

        self._fixed_check = QCheckBox("Heat source (fixed T)")
        self._fixed_check.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(self._fixed_check)

        self._fixed_row = QWidget()
        fixed_inner = QVBoxLayout(self._fixed_row)
        fixed_inner.setContentsMargins(0, 0, 0, 0)
        fixed_inner.setSpacing(2)
        fixed_inner.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = QDoubleSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fixed_inner.addWidget(self._fixed_temp_spin)
        self._fixed_row.setVisible(False)
        layout.addWidget(self._fixed_row)

        self._apply_btn = QPushButton("Apply to selection")
        self._apply_btn.setStyleSheet(
            "background-color: #2a7a6e; color: #fff; padding: 6px; border-radius: 3px;"
        )
        layout.addWidget(self._apply_btn)

        layout.addStretch()

        self._fixed_check.toggled.connect(lambda checked: self._fixed_row.setVisible(checked))
        self._apply_btn.clicked.connect(self._apply)

        self.setEnabled(False)

    def show_cells(self, cells: list[tuple[int, int]]) -> None:
        self._cells = cells
        n = len(cells)
        self._count_label.setText(f"{n} cell{'s' if n != 1 else ''} selected")
        if not cells:
            self.setEnabled(False)
            return

        # Seed controls from the first selected cell
        first = self._grid.cell(*cells[0])
        self._mat_combo.blockSignals(True)
        idx = self._mat_ids.index(first.material.id) if first.material.id in self._mat_ids else 0
        self._mat_combo.setCurrentIndex(idx)
        self._mat_combo.blockSignals(False)

        self._temp_spin.blockSignals(True)
        self._temp_spin.setValue(_units.to_display(first.temperature))
        self._temp_spin.blockSignals(False)

        self._fixed_check.blockSignals(True)
        self._fixed_check.setChecked(first.is_fixed)
        self._fixed_check.blockSignals(False)
        self._fixed_row.setVisible(first.is_fixed)

        self._fixed_temp_spin.blockSignals(True)
        self._fixed_temp_spin.setValue(_units.to_display(first.fixed_temp))
        self._fixed_temp_spin.blockSignals(False)

        self.setEnabled(True)

    def set_grid(self, grid: Grid) -> None:
        self._grid = grid
        self._cells = []
        self.setEnabled(False)

    def refresh_units(self) -> None:
        suf    = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        first  = self._grid.cell(*self._cells[0]) if self._cells else None
        for spin, k_val in [
            (self._temp_spin,       first.temperature if first else None),
            (self._fixed_temp_spin, first.fixed_temp  if first else None),
        ]:
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            if k_val is not None:
                spin.setValue(_units.to_display(k_val))
            spin.blockSignals(False)

    def _apply(self) -> None:
        if not self._cells:
            return
        mat_id   = self._mat_combo.currentData()
        mat      = self._materials[mat_id]
        is_fixed = self._fixed_check.isChecked()
        temp_k   = _units.from_display(self._temp_spin.value())
        fixed_k  = _units.from_display(self._fixed_temp_spin.value()) if is_fixed else None

        for r, c in self._cells:
            self._grid.set_cell(r, c, material=mat, is_fixed=is_fixed, temperature=temp_k)
            if fixed_k is not None:
                self._grid.set_cell(r, c, fixed_temp=fixed_k)

        self.group_modified.emit()


class Sidebar(QWidget):
    """Left sidebar: material picker on top, cell/group properties panel below."""

    def __init__(self, materials: dict[str, Material], grid: Grid, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.picker = MaterialPicker(materials)
        layout.addWidget(self.picker)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #333; max-height: 1px;")
        layout.addWidget(sep)

        # Stacked widget — index 0: single-cell props, index 1: group edit
        self._stack = QStackedWidget()
        self.props_panel  = CellPropertiesPanel(grid, materials)
        self.group_panel  = GroupEditPanel(materials, grid)
        self._stack.addWidget(self.props_panel)   # 0
        self._stack.addWidget(self.group_panel)   # 1
        layout.addWidget(self._stack, stretch=1)

    def show_cells(self, cells: list[tuple[int, int]]) -> None:
        """Route to single-cell panel or group-edit panel depending on count."""
        if len(cells) == 1:
            self._stack.setCurrentIndex(0)
            self.props_panel.show_cell(*cells[0])
        elif len(cells) > 1:
            self._stack.setCurrentIndex(1)
            self.group_panel.show_cells(cells)

    def show_cell(self, row: int, col: int) -> None:
        """Convenience wrapper — kept for backwards compatibility."""
        self.show_cells([(row, col)])

    def set_grid(self, grid: Grid) -> None:
        self.props_panel.set_grid(grid)
        self.group_panel.set_grid(grid)


def _small_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #aaa; font-size: 11px;")
    return lbl


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255
