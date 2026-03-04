from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from src.rendering import units as _units
from src.simulation.cell import Cell


class CellTooltip(QWidget):
    """Frameless floating tooltip that follows the cursor, showing cell info."""

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(
            "CellTooltip { background-color: #252525; border: 1px solid #555; border-radius: 4px; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        self._name = QLabel()
        self._name.setStyleSheet("font-weight: bold; color: #eee; font-size: 12px;")
        layout.addWidget(self._name)

        self._k     = QLabel()
        self._alpha = QLabel()
        self._temp  = QLabel()
        for lbl in (self._k, self._alpha, self._temp):
            lbl.setStyleSheet("color: #aaa; font-size: 11px;")
            layout.addWidget(lbl)

    def update_cell(self, cell: Cell) -> None:
        """Refresh the displayed values for the given cell."""
        mat = cell.material
        self._name.setText(mat.name)
        self._k.setText(f"k  =  {mat.k} W/(m·K)")
        self._alpha.setText(f"α  =  {mat.alpha:.3e} m²/s")
        self._temp.setText(f"T  =  {_units.to_display(cell.temperature):.1f} {_units.suffix()}")
        self.adjustSize()

    def move_near(self, global_pos: QPoint) -> None:
        """Position the tooltip near the cursor, nudging away from screen edges."""
        ox, oy = 16, 16
        screen = QApplication.screenAt(global_pos) or QApplication.primaryScreen()
        sg = screen.geometry()
        x = global_pos.x() + ox
        y = global_pos.y() + oy
        w, h = self.width(), self.height()
        if x + w > sg.right():
            x = global_pos.x() - w - ox
        if y + h > sg.bottom():
            y = global_pos.y() - h - oy
        self.move(x, y)
