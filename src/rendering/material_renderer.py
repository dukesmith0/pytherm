from __future__ import annotations

from PyQt6.QtGui import QColor, QPainter, QPen

from src.simulation.cell import Cell


def cell_color(cell: Cell) -> QColor:
    """Return the display color for a cell in material view."""
    return QColor(cell.material.color)


def draw_lock_icon(painter: QPainter, x: int, y: int, cp: int) -> None:
    """Draw a small yellow padlock in the top-left corner of a cell."""
    painter.save()

    s = max(8, cp // 4)        # total icon height
    bw = max(6, s * 3 // 4)   # body width
    bh = max(4, s // 2)       # body height
    pad = 2

    bx = x + pad
    by = y + pad + s - bh     # body sits below the shackle

    # Body — filled yellow rectangle
    painter.fillRect(bx, by, bw, bh, QColor(255, 210, 0, 220))

    # Shackle — semicircular arc above the body
    pen = QPen(QColor(255, 210, 0, 220))
    pen.setWidth(max(1, s // 5))
    pen.setCosmetic(False)
    painter.setPen(pen)
    inset = bw // 4
    painter.drawArc(bx + inset, y + pad, bw - 2 * inset, (s - bh) * 2, 0, 180 * 16)

    painter.restore()
