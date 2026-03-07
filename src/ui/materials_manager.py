from __future__ import annotations

import json
import os
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.models.material import Material
from src.models.material_registry import MaterialRegistry
from src.simulation.grid import Grid
from src.ui.load_dialogs import MaterialConflictDialog


class MaterialsManagerDialog(QDialog):
    """View and manage built-in (read-only) and custom materials."""

    def __init__(self, registry: MaterialRegistry, grid: Grid, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Materials Manager")
        self.setMinimumSize(720, 460)
        self._registry = registry
        self._grid = grid
        self.changed = False
        self._build_ui()
        self._rebuild_table()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._table = QTableWidget()
        self._table.setColumnCount(6)
        self._table.setHorizontalHeaderLabels(["", "Name", "k (W/m·K)", "ρ (kg/m³)", "Cₚ (J/kg·K)", "Note"])
        hh = self._table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self._table.setColumnWidth(0, 32)
        hh.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        self._table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("Add Material")
        self._edit_btn = QPushButton("Edit")
        self._delete_btn = QPushButton("Delete")
        self._edit_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._on_add)
        self._edit_btn.clicked.connect(self._on_edit)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._add_btn)
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._delete_btn)
        btn_row.addStretch()

        import_btn = QPushButton("Import...")
        import_btn.setToolTip("Import custom materials from a JSON file")
        import_btn.clicked.connect(self._on_import)
        export_btn = QPushButton("Export...")
        export_btn.setToolTip("Export your custom materials to a JSON file")
        export_btn.clicked.connect(self._on_export)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(export_btn)
        layout.addLayout(btn_row)

        close_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_box.rejected.connect(self.accept)
        layout.addWidget(close_box)

    def _rebuild_table(self) -> None:
        all_mats = list(self._registry.all_materials.values())
        self._mat_ids: list[str] = [m.id for m in all_mats]
        self._table.setRowCount(len(all_mats))

        for row, mat in enumerate(all_mats):
            swatch = QTableWidgetItem()
            swatch.setBackground(QColor(mat.color))
            swatch.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            self._table.setItem(row, 0, swatch)

            for col, text in enumerate(
                [mat.name, f"{mat.k:g}", f"{mat.rho:g}", f"{mat.cp:g}", mat.note], start=1
            ):
                item = QTableWidgetItem(text)
                item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                if mat.is_builtin:
                    item.setForeground(QColor("#666"))
                self._table.setItem(row, col, item)

        self._on_selection_changed()

    def _selected_id(self) -> str | None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._mat_ids):
            return None
        return self._mat_ids[row]

    def _on_selection_changed(self) -> None:
        mat_id = self._selected_id()
        is_custom = mat_id is not None and mat_id in self._registry.custom
        self._edit_btn.setEnabled(is_custom)
        self._delete_btn.setEnabled(is_custom)

    def _on_double_click(self) -> None:
        if self._edit_btn.isEnabled():
            self._on_edit()

    def _on_add(self) -> None:
        existing_names = {m.name for m in self._registry.all_materials.values()}
        dlg = MaterialEditDialog(existing_names=existing_names, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.values()
        mat_id = self._registry.generate_custom_id(vals["name"])
        mat = Material(
            id=mat_id, name=vals["name"], color=vals["color"],
            k=vals["k"], rho=vals["rho"], cp=vals["cp"],
            note=vals["note"], is_builtin=False,
        )
        self._registry.add_or_update_custom(mat)
        self.changed = True
        self._rebuild_table()

    def _on_edit(self) -> None:
        mat_id = self._selected_id()
        if mat_id is None:
            return
        mat = self._registry.get(mat_id)
        existing_names = {m.name for m in self._registry.all_materials.values() if m.id != mat_id}
        dlg = MaterialEditDialog(material=mat, existing_names=existing_names, parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        vals = dlg.values()
        updated = Material(
            id=mat_id, name=vals["name"], color=vals["color"],
            k=vals["k"], rho=vals["rho"], cp=vals["cp"],
            note=vals["note"], is_builtin=False,
        )
        self._registry.add_or_update_custom(updated)
        self._grid.replace_material(mat_id, updated)
        self.changed = True
        self._rebuild_table()

    def _on_delete(self) -> None:
        mat_id = self._selected_id()
        if mat_id is None:
            return
        mat = self._registry.get(mat_id)
        ans = QMessageBox.question(
            self, "Delete Material",
            f'Delete "{mat.name}"? All cells using this material will be converted to Air.',
        )
        if ans != QMessageBox.StandardButton.Yes:
            return
        self._grid.replace_material(mat_id, self._registry.get("air"))
        self._registry.remove_custom(mat_id)
        self.changed = True
        self._rebuild_table()

    def _on_export(self) -> None:
        customs = list(self._registry.custom.values())
        if not customs:
            QMessageBox.information(self, "Export Materials", "No custom materials to export.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Materials", "", "JSON Files (*.json)"
        )
        if not path:
            return
        data = {
            "materials": [
                {"id": m.id, "name": m.name, "color": m.color,
                 "k": m.k, "rho": m.rho, "cp": m.cp, "note": m.note, "abbr": m.abbr}
                for m in customs
            ]
        }
        try:
            tmp = Path(path).with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, path)
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Could not save file:\n{e}")
            return
        QMessageBox.information(self, "Export Materials", f"Exported {len(customs)} material(s).")

    def _on_import(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Materials", "", "JSON Files (*.json)"
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if "materials" not in data or not isinstance(data["materials"], list):
                raise ValueError("Missing 'materials' list")
            incoming = [Material(**entry, is_builtin=False) for entry in data["materials"]]
        except Exception as e:
            QMessageBox.critical(self, "Import Failed", f"Could not read file:\n{e}")
            return

        existing = self._registry.all_materials
        to_import = []
        for m in incoming:
            if m.id in existing:
                ex = existing[m.id]
                if ex.name == m.name and ex.k == m.k and ex.rho == m.rho and ex.cp == m.cp and ex.color == m.color:
                    continue  # exact duplicate -- skip silently
            to_import.append(m)

        if not to_import:
            QMessageBox.information(self, "Import Materials", "All materials are already present.")
            return

        existing_names = {m.name for m in existing.values()}
        conflicts = [m for m in to_import if m.name in existing_names]
        no_conflict = [m for m in to_import if m.name not in existing_names]

        if conflicts:
            dlg = MaterialConflictDialog(conflicts, existing_names, parent=self)
            if dlg.exec() != QDialog.DialogCode.Accepted:
                return
            for mat, new_name in dlg.resolved():
                new_id = self._registry.generate_custom_id(new_name)
                no_conflict.append(Material(
                    id=new_id, name=new_name, color=mat.color,
                    k=mat.k, rho=mat.rho, cp=mat.cp,
                    note=mat.note, abbr=mat.abbr, is_builtin=False,
                ))

        for m in no_conflict:
            self._registry.add_or_update_custom(m)
        self.changed = True
        self._rebuild_table()
        QMessageBox.information(self, "Import Materials", f"Imported {len(no_conflict)} material(s).")


class MaterialEditDialog(QDialog):
    """Add or edit a single custom material."""

    def __init__(
        self,
        material: Material | None = None,
        *,
        existing_names: set[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Material" if material else "Add Material")
        self.setMinimumWidth(380)
        self._existing_names = existing_names
        self._color = material.color if material else "#888888"
        self._build_ui(material)

    def _build_ui(self, mat: Material | None) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self._name_edit = QLineEdit(mat.name if mat else "")
        form.addRow(_req_label("Name"), self._name_edit)

        color_row = QHBoxLayout()
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(32, 24)
        self._color_hex = QLineEdit(self._color)
        self._color_hex.setMaximumWidth(100)
        color_row.addWidget(self._color_btn)
        color_row.addWidget(self._color_hex)
        color_row.addStretch()
        self._refresh_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        self._color_hex.editingFinished.connect(self._hex_committed)
        form.addRow(_req_label("Color"), color_row)

        self._k_spin = _prop_spinbox(0.0001, 10000, 4, mat.k if mat else 1.0)
        form.addRow(_req_label("k (W/m·K)"), self._k_spin)

        self._rho_spin = _prop_spinbox(0.001, 100000, 2, mat.rho if mat else 1000.0)
        form.addRow(_req_label("ρ (kg/m³)"), self._rho_spin)

        self._cp_spin = _prop_spinbox(0.001, 100000, 2, mat.cp if mat else 1000.0)
        form.addRow(_req_label("Cₚ (J/kg·K)"), self._cp_spin)

        self._abbr_edit = QLineEdit(mat.abbr if mat else "")
        self._abbr_edit.setMaxLength(8)
        self._abbr_edit.setPlaceholderText("Optional — up to 8 chars")
        form.addRow(QLabel("Abbr."), self._abbr_edit)

        self._note_edit = QLineEdit(mat.note if mat else "")
        self._note_edit.setMaxLength(100)
        self._note_edit.setPlaceholderText("Optional — max 100 characters")
        form.addRow(QLabel("Note"), self._note_edit)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def values(self) -> dict:
        return {
            "name": self._name_edit.text().strip(),
            "color": self._color,
            "k": self._k_spin.value(),
            "rho": self._rho_spin.value(),
            "cp": self._cp_spin.value(),
            "abbr": self._abbr_edit.text().strip()[:8],
            "note": self._note_edit.text().strip(),
        }

    def _pick_color(self) -> None:
        c = QColorDialog.getColor(QColor(self._color), self, "Pick Material Color")
        if c.isValid():
            self._color = c.name()
            self._color_hex.setText(self._color)
            self._refresh_color_btn()

    def _hex_committed(self) -> None:
        txt = self._color_hex.text().strip()
        if not txt.startswith("#"):
            txt = "#" + txt
        c = QColor(txt)
        if c.isValid():
            self._color = c.name()
        self._color_hex.setText(self._color)  # normalise or revert
        self._refresh_color_btn()

    def _refresh_color_btn(self) -> None:
        self._color_btn.setStyleSheet(
            f"background-color: {self._color}; border: 1px solid #555;"
        )

    def _validate_and_accept(self) -> None:
        self._hex_committed()  # flush any pending hex input
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        if name in self._existing_names:
            QMessageBox.warning(self, "Validation", f'A material named "{name}" already exists.')
            return
        self.accept()


# --- Helpers ---

def _req_label(text: str) -> QLabel:
    lbl = QLabel(f"{text}  <span style='color: #ff6b6b'>*</span>")
    lbl.setTextFormat(Qt.TextFormat.RichText)
    return lbl


def _prop_spinbox(lo: float, hi: float, decimals: int, value: float) -> QDoubleSpinBox:
    sb = QDoubleSpinBox()
    sb.setRange(lo, hi)
    sb.setDecimals(decimals)
    sb.setValue(value)
    return sb
