from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.models.material import Material
from src.rendering import units as _units
from src.rendering.units import TempSpinBox
from src.simulation.grid import Grid

# Theme-aware color helpers
_theme = "dark"

def _colors():
    if _theme == "light":
        return {
            "text": "#1e1e1e", "text_dim": "#555", "text_mid": "#555",
            "bg_input": "#fff", "border": "#bbb", "sep": "#ccc",
            "header_hover": "#ddd", "header_text": "#333",
            "group_bg": "#e8e8e8", "selected_bg": "#d0e8ff",
        }
    return {
        "text": "#dcdcdc", "text_dim": "#b0b0b0", "text_mid": "#b0b0b0",
        "bg_input": "#1e1e1e", "border": "#444", "sep": "#333",
        "header_hover": "#2e2e2e", "header_text": "#ccc",
        "group_bg": "#2a2a2a", "selected_bg": "#1a3a4a",
    }


class MaterialPicker(QWidget):
    """Clickable material list with collapsible category groups and a scroll area.

    Layout:
      • Vacuum alone at the top (no group header)
      • Collapsible sections for each builtin category (start collapsed)
      • "My Materials" collapsible section at the bottom for user-defined materials
    """

    material_selected = pyqtSignal(object)  # emits Material

    _CATEGORY_ORDER = [
        "Metals", "Woods", "Polymers", "Construction", "Electronics",
        "Minerals", "Gases", "Liquids", "Earth", "Organic", "Food",
    ]

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
            "font-size: 10px; font-weight: bold; padding-top: 4px;"
        )
        outer.addWidget(header)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Filter materials...")
        self._search.setClearButtonEnabled(True)
        c = _colors()
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {c['bg_input']}; border: 1px solid {c['border']}; "
            f"border-radius: 3px; padding: 3px 6px; color: {c['text']}; font-size: 11px; }}"
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

    def _apply_theme(self) -> None:
        """Re-style group headers and search for the active theme."""
        c = _colors()
        self._search.setStyleSheet(
            f"QLineEdit {{ background: {c['bg_input']}; border: 1px solid {c['border']}; "
            f"border-radius: 3px; padding: 3px 6px; color: {c['text']}; font-size: 11px; }}"
        )
        for header_btn, _content, _name, _depth in self._group_info.values():
            header_btn.setStyleSheet(
                f"QPushButton {{ border: none; border-radius: 2px; padding: 3px 4px; "
                f"text-align: left; color: {c['header_text']}; font-weight: bold; }}"
                f"QPushButton:hover {{ background-color: {c['header_hover']}; }}"
            )

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

        # Partition materials into a category tree.
        # Category "Metals,Pure" -> tree["Metals"]["Pure"]["__mats__"] = [mat, ...]
        vacuum_mat: Material | None = None
        tree: dict = {}
        custom_mats: list[Material] = []

        for mat in materials.values():
            if mat.is_vacuum:
                vacuum_mat = mat
            elif mat.is_builtin:
                parts = [p.strip() for p in (mat.category or "Other").split(",")]
                node = tree
                for part in parts:
                    node = node.setdefault(part, {})
                node.setdefault("__mats__", []).append(mat)
            else:
                custom_mats.append(mat)

        # 1. Vacuum at top
        if vacuum_mat:
            btn = self._make_button(vacuum_mat)
            self._buttons[vacuum_mat.id] = btn
            self._mat_group[vacuum_mat.id] = None
            self._clayout.addWidget(btn)

        # 2. Builtin categories in fixed order, then extras
        seen: set[str] = set()
        for top in self._CATEGORY_ORDER:
            if top in tree:
                seen.add(top)
                self._render_node(top, top, tree[top], self._clayout, 0)
        for top in sorted(tree.keys()):
            if top not in seen:
                self._render_node(top, top, tree[top], self._clayout, 0)

        # 3. Custom "My Materials" section
        if custom_mats:
            self._add_group(
                "My Materials", "My Materials", custom_mats, self._clayout, 0
            )

        self._clayout.addStretch()

        if hasattr(self, "_search"):
            self._apply_filter(self._search.text())

    def _render_node(
        self, display_name: str, full_path: str, node: dict,
        layout: QVBoxLayout, depth: int,
    ) -> None:
        """Recursively render a category tree node."""
        mats = node.get("__mats__", [])
        children = {k: v for k, v in node.items() if k != "__mats__"}

        # Add this node's header + content container
        cl = self._add_group(display_name, full_path, mats, layout, depth)

        # Recurse into children (sorted alphabetically)
        for child_name in sorted(children.keys()):
            child_path = f"{full_path},{child_name}"
            self._render_node(child_name, child_path, children[child_name], cl, depth + 1)

    def _apply_filter(self, text: str) -> None:
        """Show/hide material buttons and group headers based on a name substring match."""
        query = text.strip().lower()

        if not query:
            for btn in self._buttons.values():
                btn.setVisible(True)
            for cat, (hdr, cw, _dn, _d) in self._group_info.items():
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
            if matches:
                # Mark this group and all ancestor groups as having a match
                cat = self._mat_group.get(mid)
                while cat is not None:
                    if cat in group_has_match:
                        group_has_match[cat] = True
                    if "," in cat:
                        cat = cat.rsplit(",", 1)[0]
                    else:
                        break

        for cat, (hdr, cw, _dn, _d) in self._group_info.items():
            has_match = group_has_match.get(cat, False)
            hdr.setVisible(has_match)
            cw.setVisible(has_match)

    def _add_group(
        self, display_name: str, full_key: str, mats: list[Material],
        layout: QVBoxLayout, depth: int = 0,
    ) -> QVBoxLayout:
        """Add a collapsible group. Returns the content layout for nesting children."""
        collapsed = self._group_collapsed.get(full_key, True)
        indent = "  " * (depth + 1)

        c = _colors()
        font_size = "10px" if depth == 0 else "9px"

        header_btn = QPushButton(f"{indent}{'▶' if collapsed else '▼'}  {display_name}")
        header_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c["group_bg"]};
                color: {c["header_text"]};
                border: none;
                border-radius: 2px;
                padding: 3px 4px;
                text-align: left;
                font-size: {font_size};
                font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {c["header_hover"]}; }}
        """)
        layout.addWidget(header_btn)

        content = QWidget()
        cl = QVBoxLayout(content)
        margin_left = 4 + depth * 8
        cl.setContentsMargins(margin_left, 0, 0, 2)
        cl.setSpacing(2)

        for mat in mats:
            btn = self._make_button(mat)
            self._buttons[mat.id] = btn
            self._mat_group[mat.id] = full_key
            cl.addWidget(btn)

        content.setVisible(not collapsed)
        layout.addWidget(content)
        self._group_info[full_key] = (header_btn, content, display_name, depth)

        def _toggle(_checked: bool = False, k: str = full_key,
                    hdr: QPushButton = header_btn, cw: QWidget = content,
                    name: str = display_name, d: int = depth) -> None:
            will_collapse = cw.isVisible()
            self._group_collapsed[k] = will_collapse
            cw.setVisible(not will_collapse)
            ind = "  " * (d + 1)
            hdr.setText(f"{ind}{'▶' if will_collapse else '▼'}  {name}")

        header_btn.clicked.connect(_toggle)
        return cl

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

    def select_material(self, material: Material) -> None:
        """Programmatically select a material (e.g. from eyedropper) without emitting material_selected."""
        self._set_active(material, emit=False)

    def _set_active(self, material: Material, emit: bool = True) -> None:
        for btn in self._buttons.values():
            btn.setChecked(False)
        if material.id not in self._buttons:
            return
        self._buttons[material.id].setChecked(True)
        # Expand the group and all ancestor groups if collapsed
        key = self._mat_group.get(material.id)
        while key:
            if key in self._group_info:
                hdr, cw, display_name, depth = self._group_info[key]
                if not cw.isVisible():
                    self._group_collapsed[key] = False
                    cw.setVisible(True)
                    indent = "  " * (depth + 1)
                    hdr.setText(f"{indent}\u25bc  {display_name}")
            if "," in key:
                key = key.rsplit(",", 1)[0]
            else:
                break
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
        self._dx_m: float = 0.01

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("CELL PROPERTIES")
        header.setStyleSheet("font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(header)

        layout.addWidget(_small_label("Material"))
        self._mat_combo = QComboBox()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        layout.addWidget(self._mat_combo)

        layout.addWidget(_small_label("Label"))
        self._label_edit = QComboBox()
        self._label_edit.setEditable(True)
        self._label_edit.lineEdit().setMaxLength(8)
        self._label_edit.lineEdit().setPlaceholderText("up to 8 chars")
        self._label_edit.setStyleSheet("font-size: 11px;")
        self._label_edit.addItem("")
        layout.addWidget(self._label_edit)

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

        self._heat_check = QCheckBox("Heat source")
        self._heat_check.setStyleSheet("font-size: 11px;")
        ts_layout.addWidget(self._heat_check)

        self._heat_row = QWidget()
        heat_inner = QVBoxLayout(self._heat_row)
        heat_inner.setContentsMargins(8, 0, 0, 0)
        heat_inner.setSpacing(4)

        radio_row = QWidget()
        radio_layout = QHBoxLayout(radio_row)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(8)
        self._fixed_radio = QRadioButton("Fixed T")
        self._flux_radio  = QRadioButton("Heat flux")
        self._fixed_radio.setStyleSheet("font-size: 11px;")
        self._flux_radio.setStyleSheet("font-size: 11px;")
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._fixed_radio)
        self._radio_group.addButton(self._flux_radio)
        self._fixed_radio.setChecked(True)
        radio_layout.addWidget(self._fixed_radio)
        radio_layout.addWidget(self._flux_radio)
        radio_layout.addStretch()
        heat_inner.addWidget(radio_row)

        self._fixed_area = QWidget()
        fa_layout = QVBoxLayout(self._fixed_area)
        fa_layout.setContentsMargins(0, 0, 0, 0)
        fa_layout.setSpacing(2)
        fa_layout.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = TempSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fa_layout.addWidget(self._fixed_temp_spin)
        heat_inner.addWidget(self._fixed_area)

        self._flux_area = QWidget()
        fla_layout = QVBoxLayout(self._flux_area)
        fla_layout.setContentsMargins(0, 0, 0, 0)
        fla_layout.setSpacing(2)
        fla_layout.addWidget(_small_label("Heat flux"))
        self._flux_m2_spin = QDoubleSpinBox()
        self._flux_m2_spin.setRange(-1e8, 1e8)
        self._flux_m2_spin.setDecimals(2)
        self._flux_m2_spin.setSuffix(" W/m\u00b2")
        self._flux_m2_spin.setFixedWidth(130)
        fla_layout.addWidget(self._flux_m2_spin)
        self._flux_cell_spin = QDoubleSpinBox()
        self._flux_cell_spin.setRange(-1e6, 1e6)
        self._flux_cell_spin.setDecimals(4)
        self._flux_cell_spin.setSuffix(" W/cell")
        self._flux_cell_spin.setFixedWidth(130)
        fla_layout.addWidget(self._flux_cell_spin)
        self._volumetric_check = QCheckBox("Volumetric (W/m\u00b3)")
        self._volumetric_check.setChecked(True)
        self._volumetric_check.setStyleSheet("font-size: 10px;")
        self._volumetric_check.setToolTip("Volumetric heat generation (W/m\u00b3) or surface flux (W/m\u00b2)")
        fla_layout.addWidget(self._volumetric_check)
        self._flux_area.setVisible(False)
        heat_inner.addWidget(self._flux_area)

        self._heat_row.setVisible(False)
        ts_layout.addWidget(self._heat_row)

        layout.addWidget(self._thermal_section)
        layout.addStretch()

        self._mat_combo.currentIndexChanged.connect(self._on_material_changed)
        self._label_edit.lineEdit().editingFinished.connect(self._on_label_changed)
        self._label_edit.activated.connect(lambda _: self._on_label_changed())
        self._temp_spin.valueChanged.connect(self._on_temp_changed)
        self._heat_check.toggled.connect(self._on_heat_toggled)
        self._fixed_radio.toggled.connect(self._on_mode_radio_toggled)
        self._flux_radio.toggled.connect(self._on_mode_radio_toggled)
        self._fixed_temp_spin.valueChanged.connect(self._on_fixed_temp_changed)
        self._flux_m2_spin.valueChanged.connect(self._on_flux_m2_changed)
        self._flux_cell_spin.valueChanged.connect(self._on_flux_cell_changed)
        self._volumetric_check.toggled.connect(self._on_volumetric_toggled)

        self.setEnabled(False)

    def set_dx(self, dx_m: float) -> None:
        self._dx_m = dx_m
        if self._current is not None:
            self.show_cell(*self._current)

    def show_cell(self, row: int, col: int) -> None:
        self._current = (row, col)
        cell = self._grid.cell(row, col)
        is_heat = cell.is_fixed or cell.is_flux

        for w in (self._mat_combo, self._temp_spin, self._heat_check,
                  self._fixed_radio, self._flux_radio,
                  self._fixed_temp_spin, self._flux_m2_spin, self._flux_cell_spin):
            w.blockSignals(True)
        self._label_edit.blockSignals(True)

        idx = self._mat_ids.index(cell.material.id) if cell.material.id in self._mat_ids else 0
        self._mat_combo.setCurrentIndex(idx)
        self._label_edit.setCurrentText(cell.label)
        self._temp_spin.setValue(_units.to_display(cell.temperature))
        self._heat_check.setChecked(is_heat)
        self._heat_row.setVisible(is_heat)
        fixed_t_k = cell.fixed_temp if cell.fixed_temp > 1.0 else cell.temperature
        self._fixed_temp_spin.setValue(_units.to_display(fixed_t_k))
        if cell.is_flux:
            self._flux_radio.setChecked(True)
            self._flux_m2_spin.setValue(cell.flux_q)
            dx2 = self._dx_m ** 2
            self._flux_cell_spin.setValue(cell.flux_q * dx2)
            self._volumetric_check.setChecked(cell.is_volumetric_flux)
            self._fixed_area.setVisible(False)
            self._flux_area.setVisible(True)
        else:
            self._fixed_radio.setChecked(True)
            self._fixed_area.setVisible(True)
            self._flux_area.setVisible(False)
        self._temp_spin.setEnabled(not is_heat and not self._sim_running)

        for w in (self._mat_combo, self._temp_spin, self._heat_check,
                  self._fixed_radio, self._flux_radio,
                  self._fixed_temp_spin, self._flux_m2_spin, self._flux_cell_spin):
            w.blockSignals(False)
        self._label_edit.blockSignals(False)

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

    def refresh_labels(self) -> None:
        labels = sorted({
            self._grid.cell(r, c).label
            for r in range(self._grid.rows)
            for c in range(self._grid.cols)
            if self._grid.cell(r, c).label
        })
        current = self._label_edit.currentText()
        self._label_edit.blockSignals(True)
        self._label_edit.clear()
        self._label_edit.addItem("")
        for lbl in labels:
            self._label_edit.addItem(lbl)
        self._label_edit.setCurrentText(current)
        self._label_edit.blockSignals(False)

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
            is_heat = cell.is_fixed or cell.is_flux
            self._temp_spin.setEnabled(not running and not is_heat)

    def refresh_units(self) -> None:
        suf    = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        for spin in (self._temp_spin, self._fixed_temp_spin):
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            spin.blockSignals(False)
        if self._current is not None:
            cell = self._grid.cell(*self._current)
            self._temp_spin.blockSignals(True)
            self._temp_spin.setValue(_units.to_display(cell.temperature))
            self._temp_spin.blockSignals(False)
            self._fixed_temp_spin.blockSignals(True)
            self._fixed_temp_spin.setValue(_units.to_display(cell.fixed_temp))
            self._fixed_temp_spin.blockSignals(False)

    # --- Signal handlers ---

    def _on_material_changed(self, idx: int) -> None:
        if self._current is None:
            return
        self.pre_cell_modified.emit()
        mat_id = self._mat_combo.itemData(idx)
        mat = self._materials[mat_id]
        r, c = self._current
        if mat.is_vacuum:
            self._grid.set_cell(r, c, material=mat, is_fixed=False, is_flux=False)
        else:
            self._grid.set_cell(r, c, material=mat)
        self._thermal_section.setVisible(not mat.is_vacuum)
        self.cell_modified.emit()

    def _on_label_changed(self) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, label=self._label_edit.currentText()[:8])
        self.cell_modified.emit()

    def _on_temp_changed(self, value: float) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, temperature=_units.from_display(value))
        self.cell_modified.emit()

    def _on_heat_toggled(self, checked: bool) -> None:
        if self._current is None:
            return
        self.pre_cell_modified.emit()
        r, c = self._current
        self._heat_row.setVisible(checked)
        self._temp_spin.setEnabled(not checked and not self._sim_running)
        if not checked:
            self._grid.set_cell(r, c, is_fixed=False, is_flux=False)
        else:
            # Apply whichever mode is currently selected
            self._apply_heat_mode(r, c, initialising=True)
        self.cell_modified.emit()

    def _on_mode_radio_toggled(self, checked: bool) -> None:
        if not checked or self._current is None:
            return
        self._fixed_area.setVisible(self._fixed_radio.isChecked())
        self._flux_area.setVisible(self._flux_radio.isChecked())
        if self._heat_check.isChecked():
            self.pre_cell_modified.emit()
            r, c = self._current
            self._apply_heat_mode(r, c, initialising=False)
            self.cell_modified.emit()

    def _apply_heat_mode(self, r: int, c: int, initialising: bool) -> None:
        if self._fixed_radio.isChecked():
            cur_temp = self._temp_spin.value()
            if initialising:
                self._fixed_temp_spin.blockSignals(True)
                self._fixed_temp_spin.setValue(cur_temp)
                self._fixed_temp_spin.blockSignals(False)
            self._grid.set_cell(r, c, is_fixed=True, is_flux=False,
                                fixed_temp=_units.from_display(self._fixed_temp_spin.value()))
            self._fixed_area.setVisible(True)
            self._flux_area.setVisible(False)
        else:
            self._grid.set_cell(r, c, is_flux=True, is_fixed=False,
                                flux_q=self._flux_m2_spin.value(),
                                is_volumetric_flux=self._volumetric_check.isChecked())
            self._fixed_area.setVisible(False)
            self._flux_area.setVisible(True)

    def _on_fixed_temp_changed(self, value: float) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, fixed_temp=_units.from_display(value))
        self.cell_modified.emit()

    def _on_flux_m2_changed(self, value: float) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._flux_cell_spin.blockSignals(True)
        self._flux_cell_spin.setValue(value * self._dx_m ** 2)
        self._flux_cell_spin.blockSignals(False)
        self._grid.set_cell(r, c, flux_q=value)
        self.cell_modified.emit()

    def _on_flux_cell_changed(self, value: float) -> None:
        if self._current is None:
            return
        r, c = self._current
        q = value / self._dx_m ** 2 if self._dx_m > 0 else 0.0
        self._flux_m2_spin.blockSignals(True)
        self._flux_m2_spin.setValue(q)
        self._flux_m2_spin.blockSignals(False)
        self._grid.set_cell(r, c, flux_q=q)
        self.cell_modified.emit()

    def _on_volumetric_toggled(self, checked: bool) -> None:
        if self._current is None:
            return
        r, c = self._current
        self._grid.set_cell(r, c, is_volumetric_flux=checked)
        self.cell_modified.emit()


class GroupEditPanel(QWidget):
    """Edit panel for a multi-cell selection -- applies changes to all selected cells."""

    pre_group_modified = pyqtSignal()  # emitted BEFORE Apply writes to the grid
    group_modified = pyqtSignal()

    def __init__(self, materials: dict[str, Material], grid: Grid, parent=None) -> None:
        super().__init__(parent)
        self._grid = grid
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._cells: list[tuple[int, int]] = []
        self._prev_check_state: Qt.CheckState = Qt.CheckState.Unchecked
        self._dx_m: float = 0.01

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("GROUP EDIT")
        header.setStyleSheet("font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(header)

        self._count_label = QLabel("0 cells selected")
        self._count_label.setStyleSheet("font-size: 11px;")
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

        self._heat_check = QCheckBox("Heat source")
        self._heat_check.setTristate(True)
        self._heat_check.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._heat_check)

        # Heat source detail row
        self._heat_row = QWidget()
        heat_inner = QVBoxLayout(self._heat_row)
        heat_inner.setContentsMargins(8, 0, 0, 0)
        heat_inner.setSpacing(4)

        radio_row = QWidget()
        radio_layout = QHBoxLayout(radio_row)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(8)
        self._fixed_radio = QRadioButton("Fixed T")
        self._flux_radio  = QRadioButton("Heat flux")
        self._fixed_radio.setStyleSheet("font-size: 11px;")
        self._flux_radio.setStyleSheet("font-size: 11px;")
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._fixed_radio)
        self._radio_group.addButton(self._flux_radio)
        self._fixed_radio.setChecked(True)
        radio_layout.addWidget(self._fixed_radio)
        radio_layout.addWidget(self._flux_radio)
        radio_layout.addStretch()
        heat_inner.addWidget(radio_row)

        self._fixed_area = QWidget()
        fa_layout = QVBoxLayout(self._fixed_area)
        fa_layout.setContentsMargins(0, 0, 0, 0)
        fa_layout.setSpacing(2)
        fa_layout.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = TempSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fa_layout.addWidget(self._fixed_temp_spin)
        heat_inner.addWidget(self._fixed_area)

        self._flux_area = QWidget()
        fla_layout = QVBoxLayout(self._flux_area)
        fla_layout.setContentsMargins(0, 0, 0, 0)
        fla_layout.setSpacing(2)
        fla_layout.addWidget(_small_label("Heat flux"))
        self._flux_m2_spin = QDoubleSpinBox()
        self._flux_m2_spin.setRange(-1e8, 1e8)
        self._flux_m2_spin.setDecimals(2)
        self._flux_m2_spin.setSuffix(" W/m\u00b2")
        self._flux_m2_spin.setFixedWidth(130)
        fla_layout.addWidget(self._flux_m2_spin)
        self._flux_cell_spin = QDoubleSpinBox()
        self._flux_cell_spin.setRange(-1e6, 1e6)
        self._flux_cell_spin.setDecimals(4)
        self._flux_cell_spin.setSuffix(" W/cell")
        self._flux_cell_spin.setFixedWidth(130)
        fla_layout.addWidget(self._flux_cell_spin)
        self._volumetric_check = QCheckBox("Volumetric (W/m\u00b3)")
        self._volumetric_check.setChecked(True)
        self._volumetric_check.setStyleSheet("font-size: 10px;")
        self._volumetric_check.setToolTip("Volumetric heat generation (W/m\u00b3) or surface flux (W/m\u00b2)")
        fla_layout.addWidget(self._volumetric_check)
        self._flux_area.setVisible(False)
        heat_inner.addWidget(self._flux_area)

        self._heat_row.setVisible(False)
        layout.addWidget(self._heat_row)

        layout.addWidget(_small_label("Label"))
        self._label_edit = QComboBox()
        self._label_edit.setEditable(True)
        self._label_edit.lineEdit().setMaxLength(8)
        self._label_edit.lineEdit().setPlaceholderText("(no change)")
        self._label_edit.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._label_edit)

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

        self._heat_check.toggled.connect(self._on_heat_toggled)
        self._heat_check.clicked.connect(self._on_heat_check_clicked)
        self._fixed_radio.toggled.connect(self._on_mode_radio_toggled)
        self._flux_radio.toggled.connect(self._on_mode_radio_toggled)
        self._fixed_temp_spin.valueChanged.connect(self._on_fixed_temp_changed)
        self._flux_m2_spin.valueChanged.connect(self._on_flux_m2_changed)
        self._flux_cell_spin.valueChanged.connect(self._on_flux_cell_changed)
        self._apply_btn.clicked.connect(self._apply)

        self.setEnabled(False)

    def set_dx(self, dx_m: float) -> None:
        self._dx_m = dx_m

    def show_cells(self, cells: list[tuple[int, int]]) -> None:
        self._cells = cells
        n = len(cells)
        self._count_label.setText(f"{n} cell{'s' if n != 1 else ''} selected")
        if not cells:
            self.setEnabled(False)
            return

        labels_in_sel = {self._grid.cell(*c).label for c in cells}
        self._label_edit.setCurrentText(next(iter(labels_in_sel)) if len(labels_in_sel) == 1 else "")

        first = self._grid.cell(*cells[0])
        self._mat_combo.blockSignals(True)
        mat_ids_in_selection = {self._grid.cell(*c).material.id for c in cells}
        if len(mat_ids_in_selection) == 1 and first.material.id in self._mat_ids:
            idx = self._mat_combo.findData(first.material.id)
            self._mat_combo.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            self._mat_combo.setCurrentIndex(0)
        self._mat_combo.blockSignals(False)

        # Heat source check state
        heat_states = {(self._grid.cell(*c).is_fixed or self._grid.cell(*c).is_flux) for c in cells}
        self._heat_check.blockSignals(True)
        if len(heat_states) == 1:
            self._heat_check.setCheckState(
                Qt.CheckState.Checked if next(iter(heat_states)) else Qt.CheckState.Unchecked
            )
        else:
            self._heat_check.setCheckState(Qt.CheckState.PartiallyChecked)
        self._heat_check.blockSignals(False)
        self._prev_check_state = self._heat_check.checkState()
        is_partial = self._heat_check.checkState() == Qt.CheckState.PartiallyChecked
        is_heat_checked = self._heat_check.checkState() == Qt.CheckState.Checked
        self._heat_row.setVisible(is_heat_checked and not is_partial)

        # Radio: determine mode from first cell
        self._fixed_radio.blockSignals(True)
        self._flux_radio.blockSignals(True)
        if first.is_flux:
            self._flux_radio.setChecked(True)
            self._fixed_area.setVisible(False)
            self._flux_area.setVisible(True)
        else:
            self._fixed_radio.setChecked(True)
            self._fixed_area.setVisible(True)
            self._flux_area.setVisible(False)
        self._fixed_radio.blockSignals(False)
        self._flux_radio.blockSignals(False)

        fixed_t_k = first.fixed_temp if first.fixed_temp > 1.0 else first.temperature
        self._fixed_temp_spin.blockSignals(True)
        self._fixed_temp_spin.setValue(_units.to_display(fixed_t_k))
        self._fixed_temp_spin.blockSignals(False)
        self._flux_m2_spin.blockSignals(True)
        self._flux_m2_spin.setValue(first.flux_q)
        self._flux_m2_spin.blockSignals(False)
        self._flux_cell_spin.blockSignals(True)
        self._flux_cell_spin.setValue(first.flux_q * self._dx_m ** 2)
        self._flux_cell_spin.blockSignals(False)
        self._volumetric_check.blockSignals(True)
        self._volumetric_check.setChecked(first.is_volumetric_flux)
        self._volumetric_check.blockSignals(False)

        is_heat = first.is_fixed or first.is_flux
        temp_display = (first.fixed_temp if first.is_fixed else first.temperature) if not is_partial else first.temperature
        self._temp_spin.blockSignals(True)
        self._temp_spin.setValue(_units.to_display(temp_display))
        self._temp_spin.setEnabled(not is_heat or is_partial)
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

    def refresh_labels(self) -> None:
        labels = sorted({
            self._grid.cell(r, c).label
            for r in range(self._grid.rows)
            for c in range(self._grid.cols)
            if self._grid.cell(r, c).label
        })
        current = self._label_edit.currentText()
        self._label_edit.blockSignals(True)
        self._label_edit.clear()
        for lbl in labels:
            self._label_edit.addItem(lbl)
        self._label_edit.setCurrentText(current)
        self._label_edit.blockSignals(False)

    def refresh_units(self) -> None:
        suf    = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        first  = self._grid.cell(*self._cells[0]) if self._cells else None
        temp_k = (first.fixed_temp if (first and first.is_fixed) else (first.temperature if first else None)) if first else None
        for spin, k_val in [
            (self._temp_spin,       temp_k),
            (self._fixed_temp_spin, first.fixed_temp if first else None),
        ]:
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            if k_val is not None:
                spin.setValue(_units.to_display(k_val))
            spin.blockSignals(False)

    def _on_heat_toggled(self, checked: bool) -> None:
        self._heat_row.setVisible(checked)
        self._temp_spin.setEnabled(not checked)
        if checked:
            self._temp_spin.blockSignals(True)
            val = self._fixed_temp_spin.value() if self._fixed_radio.isChecked() else self._temp_spin.value()
            self._temp_spin.setValue(val)
            self._temp_spin.blockSignals(False)

    def _on_heat_check_clicked(self, _checked: bool = False) -> None:
        """Skip PartiallyChecked when user clicks: go directly to Checked or Unchecked."""
        state = self._heat_check.checkState()
        if state != Qt.CheckState.PartiallyChecked:
            self._prev_check_state = state
            return
        target = (
            Qt.CheckState.Unchecked
            if self._prev_check_state == Qt.CheckState.Checked
            else Qt.CheckState.Checked
        )
        self._heat_check.setCheckState(target)
        self._prev_check_state = target

    def _on_mode_radio_toggled(self, checked: bool) -> None:
        if not checked:
            return
        self._fixed_area.setVisible(self._fixed_radio.isChecked())
        self._flux_area.setVisible(self._flux_radio.isChecked())

    def _on_fixed_temp_changed(self, value: float) -> None:
        if self._heat_check.isChecked() and self._fixed_radio.isChecked():
            self._temp_spin.blockSignals(True)
            self._temp_spin.setValue(value)
            self._temp_spin.blockSignals(False)

    def _on_flux_m2_changed(self, value: float) -> None:
        self._flux_cell_spin.blockSignals(True)
        self._flux_cell_spin.setValue(value * self._dx_m ** 2)
        self._flux_cell_spin.blockSignals(False)

    def _on_flux_cell_changed(self, value: float) -> None:
        q = value / self._dx_m ** 2 if self._dx_m > 0 else 0.0
        self._flux_m2_spin.blockSignals(True)
        self._flux_m2_spin.setValue(q)
        self._flux_m2_spin.blockSignals(False)

    def _apply(self) -> None:
        if not self._cells:
            return
        self.pre_group_modified.emit()
        mat_id = self._mat_combo.currentData()
        if mat_id is not None and mat_id not in self._materials:
            mat_id = None
        mat        = self._materials[mat_id] if mat_id is not None else None
        heat_state = self._heat_check.checkState()
        is_checked = heat_state == Qt.CheckState.Checked
        temp_k     = _units.from_display(self._temp_spin.value())
        new_label  = self._label_edit.currentText()[:8] if self._label_edit.currentText() else None

        for r, c in self._cells:
            kwargs: dict = {"material": mat, "temperature": temp_k}
            if new_label is not None:
                kwargs["label"] = new_label
            self._grid.set_cell(r, c, **kwargs)
            if heat_state == Qt.CheckState.PartiallyChecked:
                if mat is not None and mat.is_vacuum:
                    self._grid.set_cell(r, c, is_fixed=False, is_flux=False)
                continue
            if not is_checked:
                self._grid.set_cell(r, c, is_fixed=False, is_flux=False)
            elif self._fixed_radio.isChecked():
                self._grid.set_cell(r, c, is_fixed=True, is_flux=False,
                                    fixed_temp=_units.from_display(self._fixed_temp_spin.value()))
            else:
                self._grid.set_cell(r, c, is_flux=True, is_fixed=False,
                                    flux_q=self._flux_m2_spin.value(),
                                    is_volumetric_flux=self._volumetric_check.isChecked())

        self.group_modified.emit()


class DrawPropertiesPanel(QWidget):
    """Brush-template panel for draw/fill mode. Settings are stamped onto cells when painted."""

    material_changed    = pyqtSignal(object)   # emits Material when user changes combo
    draw_settings_changed = pyqtSignal()       # fires on any brush-setting change

    def __init__(self, materials: dict[str, Material], parent=None) -> None:
        super().__init__(parent)
        self._materials = materials
        self._mat_ids   = list(materials.keys())
        self._dx_m: float = 0.01

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        header = QLabel("DRAW PROPERTIES")
        header.setStyleSheet("font-size: 10px; font-weight: bold; padding-top: 4px;")
        layout.addWidget(header)

        layout.addWidget(_small_label("Material"))
        self._mat_combo = QComboBox()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        layout.addWidget(self._mat_combo)

        self._thermal_section = QWidget()
        ts = QVBoxLayout(self._thermal_section)
        ts.setContentsMargins(0, 0, 0, 0)
        ts.setSpacing(4)

        ts.addWidget(_small_label("Temperature"))
        self._temp_spin = TempSpinBox()
        lo, hi = _units.spinbox_range()
        self._temp_spin.setRange(lo, hi)
        self._temp_spin.setDecimals(1)
        self._temp_spin.setSuffix(f" {_units.suffix()}")
        ts.addWidget(self._temp_spin)

        self._heat_check = QCheckBox("Heat source")
        self._heat_check.setStyleSheet("font-size: 11px;")
        ts.addWidget(self._heat_check)

        self._heat_row = QWidget()
        heat_inner = QVBoxLayout(self._heat_row)
        heat_inner.setContentsMargins(8, 0, 0, 0)
        heat_inner.setSpacing(4)

        radio_row = QWidget()
        radio_layout = QHBoxLayout(radio_row)
        radio_layout.setContentsMargins(0, 0, 0, 0)
        radio_layout.setSpacing(8)
        self._fixed_radio = QRadioButton("Fixed T")
        self._flux_radio  = QRadioButton("Heat flux")
        self._fixed_radio.setStyleSheet("font-size: 11px;")
        self._flux_radio.setStyleSheet("font-size: 11px;")
        self._radio_group = QButtonGroup(self)
        self._radio_group.addButton(self._fixed_radio)
        self._radio_group.addButton(self._flux_radio)
        self._fixed_radio.setChecked(True)
        radio_layout.addWidget(self._fixed_radio)
        radio_layout.addWidget(self._flux_radio)
        radio_layout.addStretch()
        heat_inner.addWidget(radio_row)

        self._fixed_area = QWidget()
        fa_layout = QVBoxLayout(self._fixed_area)
        fa_layout.setContentsMargins(0, 0, 0, 0)
        fa_layout.setSpacing(2)
        fa_layout.addWidget(_small_label("Fixed temperature"))
        self._fixed_temp_spin = TempSpinBox()
        self._fixed_temp_spin.setRange(lo, hi)
        self._fixed_temp_spin.setDecimals(1)
        self._fixed_temp_spin.setSuffix(f" {_units.suffix()}")
        fa_layout.addWidget(self._fixed_temp_spin)
        heat_inner.addWidget(self._fixed_area)

        self._flux_area = QWidget()
        fla_layout = QVBoxLayout(self._flux_area)
        fla_layout.setContentsMargins(0, 0, 0, 0)
        fla_layout.setSpacing(2)
        fla_layout.addWidget(_small_label("Heat flux"))
        self._flux_m2_spin = QDoubleSpinBox()
        self._flux_m2_spin.setRange(-1e8, 1e8)
        self._flux_m2_spin.setDecimals(2)
        self._flux_m2_spin.setSuffix(" W/m\u00b2")
        self._flux_m2_spin.setFixedWidth(130)
        fla_layout.addWidget(self._flux_m2_spin)
        self._flux_cell_spin = QDoubleSpinBox()
        self._flux_cell_spin.setRange(-1e6, 1e6)
        self._flux_cell_spin.setDecimals(4)
        self._flux_cell_spin.setSuffix(" W/cell")
        self._flux_cell_spin.setFixedWidth(130)
        fla_layout.addWidget(self._flux_cell_spin)
        self._volumetric_check = QCheckBox("Volumetric (W/m\u00b3)")
        self._volumetric_check.setChecked(True)
        self._volumetric_check.setStyleSheet("font-size: 10px;")
        self._volumetric_check.setToolTip("Volumetric heat generation (W/m\u00b3) or surface flux (W/m\u00b2)")
        fla_layout.addWidget(self._volumetric_check)
        self._flux_area.setVisible(False)
        heat_inner.addWidget(self._flux_area)

        self._heat_row.setVisible(False)
        ts.addWidget(self._heat_row)

        layout.addWidget(self._thermal_section)

        layout.addWidget(_small_label("Label"))
        self._label_edit = QLineEdit()
        self._label_edit.setMaxLength(8)
        self._label_edit.setPlaceholderText("stamp label (up to 8 chars)")
        self._label_edit.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._label_edit)

        layout.addStretch()

        self._mat_combo.currentIndexChanged.connect(self._on_material_changed)
        self._temp_spin.valueChanged.connect(self._emit_settings)
        self._heat_check.toggled.connect(self._on_heat_toggled)
        self._fixed_radio.toggled.connect(self._on_mode_radio_toggled)
        self._fixed_temp_spin.valueChanged.connect(self._emit_settings)
        self._flux_m2_spin.valueChanged.connect(self._on_flux_m2_changed)
        self._flux_cell_spin.valueChanged.connect(self._on_flux_cell_changed)
        self._label_edit.textChanged.connect(self._emit_settings)

    # -- Properties --

    @property
    def temperature_k(self) -> float:
        return _units.from_display(self._temp_spin.value())

    @property
    def is_fixed(self) -> bool:
        return self._heat_check.isChecked() and self._fixed_radio.isChecked()

    @property
    def fixed_temp_k(self) -> float:
        return _units.from_display(self._fixed_temp_spin.value())

    @property
    def is_flux(self) -> bool:
        return self._heat_check.isChecked() and self._flux_radio.isChecked()

    @property
    def label(self) -> str:
        return self._label_edit.text()[:8]

    @property
    def flux_q(self) -> float:
        return self._flux_m2_spin.value()

    @property
    def is_volumetric_flux(self) -> bool:
        return self._volumetric_check.isChecked()

    # -- Public API --

    def set_active_material(self, mat: Material) -> None:
        """Sync material combo from the picker without emitting material_changed."""
        idx = self._mat_combo.findData(mat.id)
        if idx >= 0:
            self._mat_combo.blockSignals(True)
            self._mat_combo.setCurrentIndex(idx)
            self._mat_combo.blockSignals(False)
        is_vac = mat.is_vacuum
        self._thermal_section.setVisible(not is_vac)
        if is_vac:
            self._heat_check.blockSignals(True)
            self._heat_check.setChecked(False)
            self._heat_check.blockSignals(False)
            self._heat_row.setVisible(False)

    def set_dx(self, dx_m: float) -> None:
        self._dx_m = dx_m

    def refresh_materials(self, materials: dict[str, Material]) -> None:
        active_id = self._mat_combo.currentData()
        self._materials = materials
        self._mat_ids = list(materials.keys())
        self._mat_combo.blockSignals(True)
        self._mat_combo.clear()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        idx = self._mat_combo.findData(active_id)
        self._mat_combo.setCurrentIndex(max(idx, 0))
        self._mat_combo.blockSignals(False)

    def refresh_units(self) -> None:
        suf = f" {_units.suffix()}"
        lo, hi = _units.spinbox_range()
        for spin in (self._temp_spin, self._fixed_temp_spin):
            spin.blockSignals(True)
            spin.setSuffix(suf)
            spin.setRange(lo, hi)
            spin.blockSignals(False)

    # -- Handlers --

    def _on_material_changed(self, idx: int) -> None:
        mat_id = self._mat_combo.itemData(idx)
        if mat_id not in self._materials:
            return
        mat = self._materials[mat_id]
        self._thermal_section.setVisible(not mat.is_vacuum)
        if mat.is_vacuum:
            self._heat_check.blockSignals(True)
            self._heat_check.setChecked(False)
            self._heat_check.blockSignals(False)
            self._heat_row.setVisible(False)
        self.material_changed.emit(mat)
        self._emit_settings()

    def _emit_settings(self, _=None) -> None:
        self.draw_settings_changed.emit()

    def _on_heat_toggled(self, checked: bool) -> None:
        self._heat_row.setVisible(checked)
        self._emit_settings()

    def _on_mode_radio_toggled(self, checked: bool) -> None:
        if not checked:
            return
        self._fixed_area.setVisible(self._fixed_radio.isChecked())
        self._flux_area.setVisible(self._flux_radio.isChecked())
        self._emit_settings()

    def _on_flux_m2_changed(self, value: float) -> None:
        self._flux_cell_spin.blockSignals(True)
        self._flux_cell_spin.setValue(value * self._dx_m ** 2)
        self._flux_cell_spin.blockSignals(False)
        self._emit_settings()

    def _on_flux_cell_changed(self, value: float) -> None:
        q = value / self._dx_m ** 2 if self._dx_m > 0 else 0.0
        self._flux_m2_spin.blockSignals(True)
        self._flux_m2_spin.setValue(q)
        self._flux_m2_spin.blockSignals(False)
        self._emit_settings()


class Sidebar(QWidget):
    """Left sidebar: material picker on top, cell/group properties panel below."""

    def __init__(self, materials: dict[str, Material], grid: Grid, parent=None) -> None:
        super().__init__(parent)
        self._current_mode: str = "draw"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.picker = MaterialPicker(materials)
        layout.addWidget(self.picker, stretch=1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: palette(mid); max-height: 1px;")
        layout.addWidget(sep)

        # Stacked widget:
        #   index 0 = draw_panel  (draw/fill mode)
        #   index 1 = props_panel (select mode, 1 cell)
        #   index 2 = group_panel (select mode, N cells)
        self._stack = QStackedWidget()
        self.draw_panel  = DrawPropertiesPanel(materials)
        self.props_panel = CellPropertiesPanel(grid, materials)
        self.group_panel = GroupEditPanel(materials, grid)
        self._stack.addWidget(self.draw_panel)   # 0
        self._stack.addWidget(self.props_panel)  # 1
        self._stack.addWidget(self.group_panel)  # 2
        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, stretch=1)

    def set_mode(self, mode: str) -> None:
        """Switch the bottom panel when the toolbar mode changes."""
        self._current_mode = mode
        if mode in ("draw", "fill"):
            self._stack.setCurrentIndex(0)

    def refresh_materials(self, materials: dict[str, Material]) -> None:
        self.picker.refresh_materials(materials)
        self.draw_panel.refresh_materials(materials)
        self.props_panel.refresh_materials(materials)
        self.group_panel.refresh_materials(materials)

    def show_cells(self, cells: list[tuple[int, int]]) -> None:
        """Route to single-cell or group-edit panel; ignored in draw/fill mode."""
        if self._current_mode != "select":
            return
        if len(cells) == 1:
            self._stack.setCurrentIndex(1)
            self.props_panel.show_cell(*cells[0])
        elif len(cells) > 1:
            self._stack.setCurrentIndex(2)
            self.group_panel.show_cells(cells)

    def show_cell(self, row: int, col: int) -> None:
        """Convenience wrapper -- kept for backwards compatibility."""
        self.show_cells([(row, col)])

    def set_grid(self, grid: Grid) -> None:
        self.props_panel.set_grid(grid)
        self.group_panel.set_grid(grid)

    def set_dx(self, dx_m: float) -> None:
        self.draw_panel.set_dx(dx_m)
        self.props_panel.set_dx(dx_m)
        self.group_panel.set_dx(dx_m)

    def refresh_labels(self) -> None:
        self.props_panel.refresh_labels()
        self.group_panel.refresh_labels()

    def refresh_units(self) -> None:
        self.draw_panel.refresh_units()
        self.props_panel.refresh_units()
        self.group_panel.refresh_units()

    def set_theme(self, theme: str) -> None:
        global _theme
        _theme = theme
        c = _colors()
        self.setStyleSheet(f"""
            QLabel {{ color: {c["text"]}; }}
            QCheckBox {{ color: {c["text"]}; }}
            QRadioButton {{ color: {c["text"]}; }}
            QLineEdit {{ background: {c["bg_input"]}; color: {c["text"]}; border: 1px solid {c["border"]}; border-radius: 3px; padding: 2px 4px; }}
            QComboBox {{ background: {c["bg_input"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
            QSpinBox, QDoubleSpinBox {{ background: {c["bg_input"]}; color: {c["text"]}; border: 1px solid {c["border"]}; }}
        """)
        self.picker._apply_theme()


def _small_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("font-size: 11px;")
    return lbl


def _luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255
