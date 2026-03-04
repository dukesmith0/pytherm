from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.material import Material


class CustomMaterialsBundleDialog(QDialog):
    """Choose which custom materials to bundle into a .pytherm save file."""

    def __init__(
        self,
        all_custom: list[Material],
        required_ids: set[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Include Custom Materials")
        self.setMinimumWidth(420)
        self._all_custom = all_custom
        self._required_ids = required_ids
        self._checkboxes: dict[str, QCheckBox] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        desc = QLabel(
            "Choose which custom materials to include in this save file.\n"
            "Materials used in the grid are required and pre-selected."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; font-size: 11px; padding-bottom: 6px;")
        layout.addWidget(desc)

        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setSpacing(4)
        inner.setContentsMargins(0, 0, 0, 0)

        for mat in self._all_custom:
            is_required = mat.id in self._required_ids
            label = f"{mat.name}  (k={mat.k:g}, ρ={mat.rho:g}, Cₚ={mat.cp:g})"
            if is_required:
                label += "  — required"
            cb = QCheckBox(label)
            cb.setChecked(is_required)  # optional materials start unchecked
            cb.setEnabled(not is_required)
            self._checkboxes[mat.id] = cb
            inner.addWidget(cb)

        inner.addStretch()

        if len(self._all_custom) > 8:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(300)
            scroll.setWidget(container)
            layout.addWidget(scroll)
        else:
            layout.addWidget(container)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def selected_materials(self) -> list[Material]:
        return [m for m in self._all_custom if self._checkboxes[m.id].isChecked()]
