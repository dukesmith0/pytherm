from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)


class NewGridDialog(QDialog):
    """Modal dialog for configuring a new simulation grid."""

    def __init__(self, parent=None) -> None:
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

        self._ambient = QDoubleSpinBox()
        self._ambient.setRange(-273.15, 10000.0)
        self._ambient.setDecimals(1)
        self._ambient.setValue(20.0)
        self._ambient.setSuffix(" °C")
        form.addRow("Ambient temp:", self._ambient)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[int, int, float, float]:
        """Return (rows, cols, dx_metres, ambient_kelvin)."""
        rows = self._rows.value()
        cols = self._cols.value()
        dx_m = self._cell_size.value() / 100.0    # cm → m
        ambient_k = self._ambient.value() + 273.15 # °C → K
        return rows, cols, dx_m, ambient_k
