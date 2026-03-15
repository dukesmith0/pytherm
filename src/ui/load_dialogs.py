from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.models.material import Material


class MaterialImportDialog(QDialog):
    """Ask whether to import bundled custom materials for this session or persistently."""

    def __init__(self, materials: list[Material], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Import Custom Materials")
        self.setMinimumWidth(420)
        self._build_ui(materials)

    def _build_ui(self, materials: list[Material]) -> None:
        layout = QVBoxLayout(self)

        names = ", ".join(m.name for m in materials)
        desc = QLabel(
            f"This file includes custom material(s):\n{names}\n\n"
            "How would you like to import them?"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding-bottom: 8px;")
        layout.addWidget(desc)

        self._session_radio = QRadioButton(
            "Session only -- available now, not saved to your materials"
        )
        self._persist_radio = QRadioButton(
            "Save to your custom materials -- available in future sessions"
        )
        self._session_radio.setChecked(True)
        layout.addWidget(self._session_radio)
        layout.addWidget(self._persist_radio)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def persist(self) -> bool:
        return self._persist_radio.isChecked()


class MaterialConflictDialog(QDialog):
    """Let the user rename loaded materials that conflict with existing names."""

    def __init__(
        self,
        conflicts: list[Material],
        taken_names: set[str],
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Resolve Material Conflicts")
        self.setMinimumWidth(500)
        self._conflicts = conflicts
        self._taken_names = taken_names
        self._edits: list[QLineEdit] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        desc = QLabel(
            "The following materials conflict with existing names.\n"
            "Assign new names before continuing:"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        container = QWidget()
        inner = QVBoxLayout(container)
        inner.setSpacing(6)

        for mat in self._conflicts:
            row = QHBoxLayout()
            orig_lbl = QLabel(mat.name)
            orig_lbl.setStyleSheet("color: #aaa; min-width: 120px;")
            arrow = QLabel("\u2192")
            arrow.setStyleSheet("color: #999; padding: 0 6px;")
            edit = QLineEdit(f"{mat.name}-Copy")
            self._edits.append(edit)
            row.addWidget(orig_lbl)
            row.addWidget(arrow)
            row.addWidget(edit, stretch=1)
            inner.addLayout(row)

        inner.addStretch()

        if len(self._conflicts) > 6:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setMaximumHeight(280)
            scroll.setWidget(container)
            layout.addWidget(scroll)
        else:
            layout.addWidget(container)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._validate_and_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _validate_and_accept(self) -> None:
        new_names = [e.text().strip() for e in self._edits]

        if any(not n for n in new_names):
            QMessageBox.warning(self, "Validation", "All names must be non-empty.")
            return

        if len(set(new_names)) != len(new_names):
            QMessageBox.warning(self, "Validation", "Each name must be unique.")
            return

        for name in new_names:
            if name in self._taken_names:
                QMessageBox.warning(
                    self, "Validation",
                    f'"{name}" is already taken. Choose a different name.',
                )
                return

        self.accept()

    def resolved(self) -> list[tuple[Material, str]]:
        """Returns [(original_material, new_name), ...]."""
        return list(zip(self._conflicts, [e.text().strip() for e in self._edits]))
