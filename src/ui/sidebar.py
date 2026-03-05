from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.models.material import Material
from src.rendering import units as _units
from src.rendering.units import TempSpinBox
from src.simulation.grid import Grid


class MaterialPicker(QWidget):
    """Clickable material list with collapsible category groups and a scroll area.

    Layout:
      • Vacuum alone at the top (no group header)
      • Collapsible sections for each builtin category (start collapsed)
      • "My Materials" collapsible section at the bottom for user-defined materials
    """

    material_selected = pyqtSignal(object)  # emits Material

    _CATEGORY_ORDER = ["Metals", "Woods", "Polymers", "Construction", "Electronics", "Gases", "Liquids"]

    def __init__(self, materials: dict[str, Material], parent=None) -> None:
        super().__init__(parent)
        self._buttons: dict[str, QPushButton] = {}
        # category key -> (header button, content widget)
        self._group_info: dict[str, tuple[QPushButton, QWidget]] = {}
        # preserved collapse state across refresh calls (True = collapsed)
        self._group_collapsed: dict[str, bool] = {}
        # material id -> group key (None = top-level / vacuum)
        self._mat_group: dict[str, str | None] = {}
        # full material dict, updated in _rebuild
        self._all_materials: dict[str, Material] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 0)
        outer.setSpacing(3)

        header = QLabel("MATERIAL")
        header.setStyleSheet(
            "color: #777; font-size: 10px; font-weight: bold; padding-top: 4px;"
        )
        outer.addWidget(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter materials...")
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet(
            "QLineEdit { background: #1e1e1e; border: 1px solid #444; "
            "border-radius: 3px; padding: 3px 6px; color: #ccc; font-size: 11px; }"
        )
        outer.addWidget(self._search)
        self._search.textChanged.connect(self._apply_filter)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._container = QWidget()
        self._clayout = QVBoxLayout(self._container)
        self._clayout.setContentsMargins(0, 2, 0, 4)
        self._clayout.setSpacing(2)
        scroll.setWidget(self._container)

        outer.addWidget(scroll, stretch=1)

        self._rebuild(materials)
        first = next(iter(materials.values()), None)
        if first:
            self._set_active(first, emit=False)

    # --- Public API ---

    def refresh_materials(self, materials: dict[str, Material]) -> None:
        """Rebuild the button list after materials are added/removed/edited."""
        active_id = next(
            (mid for mid, btn in self._buttons.items() if btn.isChecked()), None
        )
        self._rebuild(materials)
        target = self._all_materials.get(active_id) or next(
            iter(self._all_materials.values()), None
        )
        if target:
            self._set_active(target, emit=True)

    # --- Internal ---

    def _rebuild(self, materials: dict[str, Material]) -> None:
        self._all_materials = dict(materials)
        self._buttons.clear()
        self._group_info.clear()
        self._mat_group.clear()

        # Clear layout
        while self._clayout.count():
            item = self._clayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Partition materials
        vacuum_mat: Material | None = None
        grouped: dict[str, list[Material]] = {}
        custom_mats: list[Material] = []

        for mat in materials.values():
            if mat.is_vacuum:
                vacuum_mat = mat
            elif mat.is_builtin:
                cat = mat.category or "Other"
                grouped.setdefault(cat, []).append(mat)
            else:
                custom_mats.append(mat)

        # 1. Vacuum at top — no group header
        if vacuum_mat:
            btn = self._make_button(vacuum_mat)
            self._buttons[vacuum_mat.id] = btn
            self._mat_group[vacuum_mat.id] = None
            self._clayout.addWidget(btn)

        # 2. Builtin categories in fixed order, then any extras
        seen: set[str] = set()
        for cat in self._CATEGORY_ORDER:
            if cat in grouped:
                seen.add(cat)
                self._add_group(cat, grouped[cat])
        for cat, mats in grouped.items():
            if cat not in seen:
                self._add_group(cat, mats)

        # 3. Custom "My Materials" section
        if custom_mats:
            self._add_group("My Materials", custom_mats)

        self._clayout.addStretch()

        if hasattr(self, "_search"):
            self._apply_filter(self._search.text())

    def _apply_filter(self, text: str) -> None:
        """Show/hide material buttons and group headers based on a name substring match."""
        query = text.strip().lower()

        if not query:
            for btn in self._buttons.values():
                btn.setVisible(True)
            for cat, (hdr, cw) in self._group_info.items():
                hdr.setVisible(True)
                cw.setVisible(not self._group_collapsed.get(cat, True))
            return

        group_has_match: dict[str, bool] = {cat: False for cat in self._group_info}

        for mid, btn in self._buttons.items():
            mat = self._all_materials.get(mid)
            name_match = query in (mat.name.lower() if mat else "")
            abbr_match = query in (mat.abbr.lower() if mat else "")
            matches = name_match or abbr_match
            btn.setVisible(matches)
            cat = self._mat_group.get(mid)
            if cat is not None and matches:
                group_has_match[cat] = True

        for cat, (hdr, cw) in self._group_info.items():
            has_match = group_has_match.get(cat, False)
            hdr.setVisible(has_match)
            cw.setVisible(has_match)

    def _add_group(self, category: str, mats: list[Material]) -> None:
        collapsed = self._group_collapsed.get(category, True)

        header_btn = QPushButton(f"  {'▶' if collapsed else '▼'}  {category}")
        header_btn.setStyleSheet("""
            QPushButton {
                background-color: #252525;
                color: #999;
                border: none;
                border-radius: 2px;
                padding: 3px 4px;
                text-align: left;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2e2e2e; }
        """)
        self._clayout.addWidget(header_btn)

        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(4, 0, 0, 2)
        cl.setSpacing(2)

        for mat in mats:
            btn = self._make_button(mat)
            self._buttons[mat.id] = btn
            self._mat_group[mat.id] = category
            cl.addWidget(btn)

        content.setVisible(not collapsed)
        self._clayout.addWidget(content)
        self._group_info[category] = (header_btn, content)

        def _toggle(_checked: bool = False, cat: str = category,
                    hdr: QPushButton = header_btn, cw: QWidget = content) -> None:
            will_collapse = cw.isVisible()
            self._group_collapsed[cat] = will_collapse
            cw.setVisible(not will_collapse)
            hdr.setText(f"  {'▶' if will_collapse else '▼'}  {cat}")

        header_btn.clicked.connect(_toggle)

    def _make_button(self, mat: Material) -> QPushButton:
        text_color = "#000" if _luminance(mat.color) > 0.5 else "#eee"
        props_line = f"k={mat.k:g}  \u03c1={mat.rho:g}  C\u1d56={mat.cp:g}"
        btn = QPushButton()
        btn.setCheckable(True)
        btn.setText(f"{mat.name}\n{props_line}")
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {mat.color};
                color: {text_color};
                border: 2px solid transparent;
                border-radius: 3px;
                padding: 4px 8px;
                text-align: left;
                font-size: 12px;
            }}
            QPushButton:checked {{
                border: 2px solid #ffffff;
            }}
        """)
        tooltip_parts = [
            f"k = {mat.k:g} W/(m·K)",
            f"\u03c1 = {mat.rho:g} kg/m\u00b3",
            f"C\u209a = {mat.cp:g} J/(kg·K)",
        ]
        if mat.note:
            tooltip_parts.append(f"\nNote: {mat.note}")
        btn.setToolTip("\n".join(tooltip_parts))
        btn.clicked.connect(lambda _checked, m=mat: self._set_active(m))
        return btn

    def _set_active(self, material: Material, emit: bool = True) -> None:
        for btn in self._buttons.values():
            btn.setChecked(False)
        if material.id not in self._buttons:
            return
        self._buttons[material.id].setChecked(True)
        # Expand the group containing this material if it is currently collapsed
        group_key = self._mat_group.get(material.id)
        if group_key and group_key in self._group_info:
            hdr, cw = self._group_info[group_key]
            if not cw.isVisible():
                self._group_collapsed[group_key] = False
                cw.setVisible(True)
                hdr.setText(f"  \u25bc  {group_key}")
        if emit:
            self.material_selected.emit(material)


class CellPropertiesPanel(QWidget):
    """Shows and edits the properties of the currently selected cell."""

    pre_cell_modified = pyqtSignal()  # emitted BEFORE applying material/fixed changes
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

        # Temperature + heat source — hidden for vacuum cells
        self._thermal_section = QWidget()
        ts_layout = QVBoxLayout(self._thermal_section)
        ts_layout.setContentsMargins(0, 0, 0, 0)
        ts_layout.setSpacing(4)

        ts_layout.addWidget(_small_label("Temperature"))
        self._temp_spin = TempSpinBox()
        lo, hi = _units.spinbox_range()
        self._temp_spin.setRange(lo, hi)
        self._temp_spin.setDecimals(1)
        self._temp_spin.setSuffix(f" {_units.suffix()}")
        ts_layout.addWidget(self._temp_spin)

        self._fixed_check = QCheckBox("Heat source (fixed T)")
        self._fixed_check.setStyleSheet("color: #ccc; font-size: 11px;")
        ts_layout.addWidget(self._fixed_check)

        self._fixed_row = QWidget()
        fixed_inner = QVBoxLayout(self._fixed_row)
        fixed_inner.setContentsMargins(0, 0, 0, 0)
        fixed_inner.setSpacing(2)
        fixed_inner.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = TempSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fixed_inner.addWidget(self._fixed_temp_spin)
        self._fixed_row.setVisible(False)
        ts_layout.addWidget(self._fixed_row)

        layout.addWidget(self._thermal_section)
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

        self._thermal_section.setVisible(not cell.material.is_vacuum)
        self.setEnabled(True)

    def refresh_materials(self, materials: dict[str, Material]) -> None:
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._mat_combo.clear()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        self._current = None
        self.setEnabled(False)

    def set_grid(self, grid: Grid) -> None:
        self._grid = grid
        self._current = None
        self.setEnabled(False)

    def refresh_display(self) -> None:
        if self._current is None:
            return
        cell = self._grid.cell(*self._current)
        self._temp_spin.blockSignals(True)
        self._temp_spin.setValue(_units.to_display(cell.temperature))
        self._temp_spin.blockSignals(False)

    def set_sim_running(self, running: bool) -> None:
        self._sim_running = running
        if self._current is not None:
            cell = self._grid.cell(*self._current)
            self._temp_spin.setEnabled(not running and not cell.is_fixed)

    def refresh_units(self) -> None:
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
        self.pre_cell_modified.emit()
        mat_id = self._mat_combo.itemData(idx)
        mat = self._materials[mat_id]
        r, c = self._current
        if mat.is_vacuum:
            self._grid.set_cell(r, c, material=mat, is_fixed=False)
        else:
            self._grid.set_cell(r, c, material=mat)
        self._thermal_section.setVisible(not mat.is_vacuum)
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
        self.pre_cell_modified.emit()
        r, c = self._current
        self._grid.set_cell(r, c, is_fixed=checked)
        self._fixed_row.setVisible(checked)
        self._temp_spin.setEnabled(not checked)
        if checked:
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

    pre_group_modified = pyqtSignal()  # emitted BEFORE Apply writes to the grid
    group_modified = pyqtSignal()

    def __init__(self, materials: dict[str, Material], grid: Grid, parent=None) -> None:
        super().__init__(parent)
        self._grid = grid
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._cells: list[tuple[int, int]] = []
        self._prev_check_state: Qt.CheckState = Qt.CheckState.Unchecked

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
        self._mat_combo.addItem("(no change)", None)
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        layout.addWidget(self._mat_combo)

        layout.addWidget(_small_label("Starting temperature"))
        self._temp_spin = TempSpinBox()
        lo, hi = _units.spinbox_range()
        self._temp_spin.setRange(lo, hi)
        self._temp_spin.setDecimals(1)
        self._temp_spin.setSuffix(f" {_units.suffix()}")
        layout.addWidget(self._temp_spin)

        self._fixed_check = QCheckBox("Heat source (fixed T)")
        self._fixed_check.setTristate(True)
        self._fixed_check.setStyleSheet("color: #ccc; font-size: 11px;")
        layout.addWidget(self._fixed_check)

        self._fixed_row = QWidget()
        fixed_inner = QVBoxLayout(self._fixed_row)
        fixed_inner.setContentsMargins(0, 0, 0, 0)
        fixed_inner.setSpacing(2)
        fixed_inner.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = TempSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fixed_inner.addWidget(self._fixed_temp_spin)
        self._fixed_row.setVisible(False)
        layout.addWidget(self._fixed_row)

        self._apply_btn = QPushButton("Apply to selection")
        self._apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #2a7a6e;
                color: #fff;
                padding: 6px;
                border-radius: 3px;
            }
            QPushButton:hover   { background-color: #348f81; }
            QPushButton:pressed { background-color: #1f5c52; }
        """)
        layout.addWidget(self._apply_btn)

        layout.addStretch()

        self._fixed_check.toggled.connect(self._on_fixed_toggled)
        self._fixed_check.clicked.connect(self._on_fixed_check_clicked)
        self._fixed_temp_spin.valueChanged.connect(self._on_fixed_temp_changed)
        self._apply_btn.clicked.connect(self._apply)

        self.setEnabled(False)

    def show_cells(self, cells: list[tuple[int, int]]) -> None:
        self._cells = cells
        n = len(cells)
        self._count_label.setText(f"{n} cell{'s' if n != 1 else ''} selected")
        if not cells:
            self.setEnabled(False)
            return

        first = self._grid.cell(*cells[0])
        self._mat_combo.blockSignals(True)
        mat_ids_in_selection = {self._grid.cell(*c).material.id for c in cells}
        if len(mat_ids_in_selection) == 1 and first.material.id in self._mat_ids:
            # All cells share the same material — pre-select it
            idx = self._mat_combo.findData(first.material.id)
            self._mat_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            # Mixed materials — default to "(no change)"
            self._mat_combo.setCurrentIndex(0)
        self._mat_combo.blockSignals(False)

        self._fixed_check.blockSignals(True)
        is_fixed_states = {self._grid.cell(*c).is_fixed for c in cells}
        if len(is_fixed_states) == 1:
            self._fixed_check.setCheckState(
                Qt.CheckState.Checked if first.is_fixed else Qt.CheckState.Unchecked
            )
        else:
            self._fixed_check.setCheckState(Qt.CheckState.PartiallyChecked)
        self._fixed_check.blockSignals(False)
        self._prev_check_state = self._fixed_check.checkState()
        is_partial = self._fixed_check.checkState() == Qt.CheckState.PartiallyChecked
        self._fixed_row.setVisible(first.is_fixed and not is_partial)

        self._fixed_temp_spin.blockSignals(True)
        self._fixed_temp_spin.setValue(_units.to_display(first.fixed_temp))
        self._fixed_temp_spin.blockSignals(False)

        # Starting temp spin: disabled and mirrors fixed_temp when fixed; shows cell temp otherwise
        temp_display = (first.fixed_temp if first.is_fixed else first.temperature) if not is_partial else first.temperature
        self._temp_spin.blockSignals(True)
        self._temp_spin.setValue(_units.to_display(temp_display))
        self._temp_spin.setEnabled(not first.is_fixed or is_partial)
        self._temp_spin.blockSignals(False)

        self.setEnabled(True)

    def refresh_materials(self, materials: dict[str, Material]) -> None:
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._mat_combo.clear()
        self._mat_combo.addItem("(no change)", None)
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        self._cells = []
        self.setEnabled(False)

    def set_grid(self, grid: Grid) -> None:
        self._grid = grid
        self._cells = []
        self.setEnabled(False)

    def refresh_units(self) -> None:
        suf    = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        first  = self._grid.cell(*self._cells[0]) if self._cells else None
        temp_k = (first.fixed_temp if (first and first.is_fixed) else first.temperature) if first else None
        for spin, k_val in [
            (self._temp_spin,       temp_k),
            (self._fixed_temp_spin, first.fixed_temp  if first else None),
        ]:
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            if k_val is not None:
                spin.setValue(_units.to_display(k_val))
            spin.blockSignals(False)

    def _on_fixed_toggled(self, checked: bool) -> None:
        self._fixed_row.setVisible(checked)
        self._temp_spin.setEnabled(not checked)
        if checked:
            self._temp_spin.blockSignals(True)
            self._temp_spin.setValue(self._fixed_temp_spin.value())
            self._temp_spin.blockSignals(False)

    def _on_fixed_check_clicked(self, _checked: bool = False) -> None:
        """Skip PartiallyChecked when user clicks: go directly to Checked or Unchecked."""
        state = self._fixed_check.checkState()
        if state != Qt.CheckState.PartiallyChecked:
            self._prev_check_state = state
            return
        target = (
            Qt.CheckState.Unchecked
            if self._prev_check_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._fixed_check.setCheckState(target)
        self._prev_check_state = target

    def _on_fixed_temp_changed(self, value: float) -> None:
        if self._fixed_check.isChecked():
            self._temp_spin.blockSignals(True)
            self._temp_spin.setValue(value)
            self._temp_spin.blockSignals(False)

    def _apply(self) -> None:
        if not self._cells:
            return
        self.pre_group_modified.emit()
        mat_id   = self._mat_combo.currentData()   # None → "(no change)"
        if mat_id is not None and mat_id not in self._materials:
            mat_id = None
        mat         = self._materials[mat_id] if mat_id is not None else None
        fixed_state = self._fixed_check.checkState()
        is_checked  = fixed_state == Qt.CheckState.Checked
        temp_k      = _units.from_display(self._temp_spin.value())
        fixed_k     = _units.from_display(self._fixed_temp_spin.value()) if is_checked else None

        for r, c in self._cells:
            self._grid.set_cell(r, c, material=mat, temperature=temp_k)
            if fixed_state != Qt.CheckState.PartiallyChecked:
                self._grid.set_cell(r, c, is_fixed=is_checked)
                if fixed_k is not None:
                    self._grid.set_cell(r, c, fixed_temp=fixed_k)

        self.group_modified.emit()


class Sidebar(QWidget):
    """Left sidebar: material picker on top, cell/group properties panel below."""

    paint_temp_changed = pyqtSignal(object)  # float | None

    def __init__(self, materials: dict[str, Material], grid: Grid, parent=None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.picker = MaterialPicker(materials)
        layout.addWidget(self.picker, stretch=1)

        # Paint temperature override row
        paint_row = QWidget()
        pr_layout = QVBoxLayout(paint_row)
        pr_layout.setContentsMargins(8, 4, 8, 4)
        pr_layout.setSpacing(2)

        self._paint_check = QCheckBox("Override paint temperature")
        self._paint_check.setStyleSheet("color: #aaa; font-size: 11px;")
        pr_layout.addWidget(self._paint_check)

        self._paint_spin = TempSpinBox()
        lo, hi = _units.spinbox_range()
        self._paint_spin.setRange(lo, hi)
        self._paint_spin.setDecimals(1)
        self._paint_spin.setSuffix(f" {_units.suffix()}")
        self._paint_spin.setEnabled(False)
        pr_layout.addWidget(self._paint_spin)

        layout.addWidget(paint_row)

        self._paint_check.toggled.connect(self._on_paint_check)
        self._paint_spin.valueChanged.connect(self._on_paint_spin)

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

    def refresh_materials(self, materials: dict[str, Material]) -> None:
        self.picker.refresh_materials(materials)
        self.props_panel.refresh_materials(materials)
        self.group_panel.refresh_materials(materials)

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

    def refresh_units(self) -> None:
        self.props_panel.refresh_units()
        self.group_panel.refresh_units()
        lo, hi = _units.spinbox_range()
        self._paint_spin.blockSignals(True)
        self._paint_spin.setSuffix(f" {_units.suffix()}")
        self._paint_spin.setRange(lo, hi)
        self._paint_spin.blockSignals(False)

    def _on_paint_check(self, checked: bool) -> None:
        self._paint_spin.setEnabled(checked)
        self.paint_temp_changed.emit(
            _units.from_display(self._paint_spin.value()) if checked else None
        )

    def _on_paint_spin(self, value: float) -> None:
        if self._paint_check.isChecked():
            self.paint_temp_changed.emit(_units.from_display(value))


def _small_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #aaa; font-size: 11px;")
    return lbl


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255
