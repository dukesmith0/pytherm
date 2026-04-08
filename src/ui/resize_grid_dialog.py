from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QSpinBox, QVBoxLayout,
)


class ResizeGridDialog(QDialog):
    """Modal dialog for adding or trimming rows/cols from each grid edge.

    Positive spinbox values add, negative values trim.
    Shows the resulting grid size as a live preview.
    """

    def __init__(self, current_rows: int, current_cols: int, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resize Grid")
        self.setFixedWidth(300)
        self._rows = current_rows
        self._cols = current_cols

        form = QFormLayout()
        form.setLabelAlignment(form.labelAlignment())

        def _spinbox(lo: int, hi: int) -> QSpinBox:
            sb = QSpinBox()
            sb.setRange(lo, hi)
            sb.setValue(0)
            sb.valueChanged.connect(self._update_preview)
            return sb

        max_rows = 200 - current_rows
        max_cols = 200 - current_cols
        self._top    = _spinbox(-current_rows + 1, max(0, max_rows))
        self._bottom = _spinbox(-current_rows + 1, max(0, max_rows))
        self._left   = _spinbox(-current_cols + 1, max(0, max_cols))
        self._right  = _spinbox(-current_cols + 1, max(0, max_cols))

        form.addRow("Add/trim top:",    self._top)
        form.addRow("Add/trim bottom:", self._bottom)
        form.addRow("Add/trim left:",   self._left)
        form.addRow("Add/trim right:",  self._right)

        self._preview = QLabel()
        self._preview.setStyleSheet("color: #b0b0cc; font-size: 11px;")
        form.addRow("Result:", self._preview)
        self._update_preview()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _update_preview(self) -> None:
        new_r = self._rows + self._top.value() + self._bottom.value()
        new_c = self._cols + self._left.value() + self._right.value()
        new_r = max(1, new_r)
        new_c = max(1, new_c)
        self._preview.setText(f"{new_r} \u00d7 {new_c}  (was {self._rows} \u00d7 {self._cols})")
        ok_btn = self.findChild(QDialogButtonBox)
        if ok_btn:
            has_change = (self._top.value() != 0 or self._bottom.value() != 0
                          or self._left.value() != 0 or self._right.value() != 0)
            within_limits = new_r <= 200 and new_c <= 200
            ok_btn.button(QDialogButtonBox.StandardButton.Ok).setEnabled(
                has_change and within_limits
            )

    def values(self) -> tuple[int, int, int, int]:
        """Return (top, right, bottom, left) deltas."""
        return (self._top.value(), self._right.value(),
                self._bottom.value(), self._left.value())
