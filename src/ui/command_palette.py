from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
)


class CommandPalette(QDialog):
    """Floating command palette: type to filter, Enter to invoke, Escape to close."""

    def __init__(self, entries: list[tuple[str, Callable]], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(480, 320)

        self._entries = entries

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Type to filter commands...")
        self._filter.setClearButtonEnabled(True)
        layout.addWidget(self._filter)

        self._list = QListWidget()
        layout.addWidget(self._list)

        self._filter.textChanged.connect(self._apply_filter)
        self._list.itemActivated.connect(self._invoke)
        self._filter.returnPressed.connect(self._invoke_top)

        self._populate(entries)

    def _populate(self, entries: list[tuple[str, Callable]]) -> None:
        self._list.clear()
        for label, action in entries:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, action)
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)

    def _apply_filter(self, text: str) -> None:
        q = text.lower()
        visible_first: QListWidgetItem | None = None
        for i in range(self._list.count()):
            item = self._list.item(i)
            matches = q == "" or q in item.text().lower()
            item.setHidden(not matches)
            if matches and visible_first is None:
                visible_first = item
        if visible_first is not None:
            self._list.setCurrentItem(visible_first)

    def _invoke(self, item: QListWidgetItem | None = None) -> None:
        if item is None:
            item = self._list.currentItem()
        if item is None or item.isHidden():
            return
        action: Callable = item.data(Qt.ItemDataRole.UserRole)
        self.accept()
        action()

    def _invoke_top(self) -> None:
        for i in range(self._list.count()):
            item = self._list.item(i)
            if not item.isHidden():
                self._invoke(item)
                return

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.reject()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            self._list.setFocus()
            self._list.keyPressEvent(event)
        else:
            super().keyPressEvent(event)
