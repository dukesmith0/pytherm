from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from src.rendering import units as _units
from src.rendering.units import TempSpinBox


class NewGridDialog(QDialog):
    """Modal dialog for configuring a new simulation grid."""

    def __init__(self, materials: dict, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Grid")
        self.setFixedWidth(280)

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())

        self._rows = QSpinBox()
        self._rows.setRange(1, 40)
        self._rows.setValue(10)
        form.addRow("Rows:", self._rows)

        self._cols = QSpinBox()
        self._cols.setRange(1, 40)
        self._cols.setValue(10)
        form.addRow("Columns:", self._cols)

        self._cell_size = QDoubleSpinBox()
        self._cell_size.setRange(0.1, 100.0)
        self._cell_size.setDecimals(1)
        self._cell_size.setValue(1.0)
        self._cell_size.setSuffix(" cm")
        form.addRow("Cell size:", self._cell_size)

        lo, hi = _units.spinbox_range()
        self._ambient = TempSpinBox()
        self._ambient.setRange(lo, hi)
        self._ambient.setDecimals(1)
        self._ambient.setValue(_units.to_display(293.15))  # 20 °C default
        self._ambient.setSuffix(f" {_units.suffix()}")
        form.addRow("Ambient temp:", self._ambient)

        self._mat_combo = QComboBox()
        for mat in materials.values():
            self._mat_combo.addItem(mat.name, mat.id)
        form.addRow("Base material:", self._mat_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[int, int, float, float, str]:
        """Return (rows, cols, dx_metres, ambient_kelvin, base_material_id)."""
        return (
            self._rows.value(),
            self._cols.value(),
            self._cell_size.value() / 100.0,
            _units.from_display(self._ambient.value()),
            self._mat_combo.currentData(),
        )
