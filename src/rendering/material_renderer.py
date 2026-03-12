from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen

from src.simulation.cell import Cell

_color_cache: dict[str, QColor] = {}


def cell_color(cell: Cell) -> QColor:
    """Return the display color for a cell in material view."""
    color = cell.material.color
    if color not in _color_cache:
        _color_cache[color] = QColor(color)
    return _color_cache[color]


def draw_lock_icon(painter: QPainter, x: int, y: int, cp: int, x_offset: int = 0) -> None:
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

    bx = x + pad + x_offset
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


def draw_pin_icon(painter: QPainter, x: int, y: int, cp: int, x_offset: int = 0) -> None:
    """Draw a small blue pin in the top-left corner of a fixed-temperature cell."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = max(8, cp // 4)
    pad = 2
    head_r = max(2, s // 3)
    shaft_w = max(1, s // 6)

    px = x + pad + head_r + x_offset
    py_head = y + pad + head_r
    py_tip  = y + pad + s

    dark = QColor(30, 30, 30, 210)
    blue = QColor(100, 200, 255, 230)

    dark_pen = QPen(dark)
    dark_pen.setWidth(shaft_w + 2)
    dark_pen.setCosmetic(False)
    painter.setPen(dark_pen)
    painter.drawLine(px, py_head, px, py_tip)

    blue_pen = QPen(blue)
    blue_pen.setWidth(shaft_w)
    blue_pen.setCosmetic(False)
    painter.setPen(blue_pen)
    painter.drawLine(px, py_head, px, py_tip)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(dark))
    painter.drawEllipse(px - head_r - 1, py_head - head_r - 1,
                        (head_r + 1) * 2, (head_r + 1) * 2)
    painter.setBrush(QBrush(blue))
    painter.drawEllipse(px - head_r, py_head - head_r, head_r * 2, head_r * 2)

    painter.restore()


def draw_flame_icon(painter: QPainter, x: int, y: int, cp: int, x_offset: int = 0) -> None:
    """Draw a small orange flame in the top-left corner of a heat-flux cell."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    s  = max(8, cp // 4)
    fw = max(5, s * 2 // 3)
    pad = 2

    fx = float(x + pad + x_offset)
    fy = float(y + pad)
    fh = float(s)
    cw = float(fw)
    cx = fx + cw / 2.0

    path = QPainterPath()
    path.moveTo(cx, fy + fh)
    path.cubicTo(fx - cw * 0.1, fy + fh * 0.7,
                 fx + cw * 0.15, fy + fh * 0.15,
                 cx, fy)
    path.cubicTo(fx + cw * 0.85, fy + fh * 0.15,
                 fx + cw * 1.1,  fy + fh * 0.7,
                 cx, fy + fh)

    grad = QLinearGradient(cx, fy + fh, cx, fy)
    grad.setColorAt(0.0, QColor(200, 40,  0,  210))
    grad.setColorAt(0.5, QColor(255, 130, 0,  220))
    grad.setColorAt(1.0, QColor(255, 230, 50, 230))

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(grad))
    painter.drawPath(path)

    painter.restore()
