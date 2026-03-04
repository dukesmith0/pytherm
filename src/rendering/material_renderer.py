from __future__ import annotations

from PyQt6.QtGui import QColor, QPainter, QPen

from src.simulation.cell import Cell


def cell_color(cell: Cell) -> QColor:
    """Return the display color for a cell in material view."""
    return QColor(cell.material.color)


def draw_lock_icon(painter: QPainter, x: int, y: int, cp: int) -> None:
    """Draw a small yellow padlock in the top-left corner of a cell.

    A dark outline is drawn behind both the body and shackle so the icon
    remains visible against bright cell colors (e.g. Gold cells).
    """
    painter.save()

    s = max(8, cp // 4)        # total icon height
    bw = max(6, s * 3 // 4)   # body width
    bh = max(4, s // 2)       # body height
    pad = 2
    inset = bw // 4
    stroke_w = max(1, s // 5)

    bx = x + pad
    by = y + pad + s - bh     # body sits below the shackle

    dark   = QColor(30, 30, 30, 210)
    yellow = QColor(255, 210, 0, 220)

    # Body: dark border then yellow fill
    painter.fillRect(bx - 1, by - 1, bw + 2, bh + 2, dark)
    painter.fillRect(bx, by, bw, bh, yellow)

    # Shackle: dark arc (wider) then yellow arc on top
    dark_pen = QPen(dark)
    dark_pen.setWidth(stroke_w + 2)
    dark_pen.setCosmetic(False)
    painter.setPen(dark_pen)
    painter.drawArc(bx + inset, y + pad, bw - 2 * inset, (s - bh) * 2, 0, 180 * 16)

    yellow_pen = QPen(yellow)
    yellow_pen.setWidth(stroke_w)
    yellow_pen.setCosmetic(False)
    painter.setPen(yellow_pen)
    painter.drawArc(bx + inset, y + pad, bw - 2 * inset, (s - bh) * 2, 0, 180 * 16)

    painter.restore()
