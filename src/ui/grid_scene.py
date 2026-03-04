from __future__ import annotations

from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene

from src.rendering import units as _units
from src.rendering.heatmap_renderer import heatmap_color, text_color_for_bg
from src.rendering.material_renderer import cell_color, draw_lock_icon
from src.simulation.grid import Grid

# Scene coordinate size of each cell at 1:1 zoom.
# Zoom is handled by QGraphicsView's transform — the scene itself never changes scale.
CELL_PX = 32

# Minimum on-screen cell size (pixels) before temperature labels are drawn in heatmap mode.
_LABEL_THRESHOLD_PX = 30


class GridScene(QGraphicsScene):
    def __init__(self, grid: Grid) -> None:
        super().__init__()
        self._grid = grid
        self.show_grid_lines = True
        self._preview_rect: tuple[int, int, int, int] | None = None   # (r1,c1,r2,c2)
        self._preview_cells: list[tuple[int, int]] | None = None       # Bresenham line
        self._selected_cell: tuple[int, int] | None = None
        self._multi_selection: set[tuple[int, int]] = set()

        # Heatmap state
        self._view_mode: str = "material"   # "material" | "heatmap"
        self._heatmap_auto: bool = True
        self._heatmap_t_min: float = 273.15  # 0 °C in K
        self._heatmap_t_max: float = 373.15  # 100 °C in K

        self._sync_scene_rect()

    def _sync_scene_rect(self) -> None:
        self.setSceneRect(0, 0, self._grid.cols * CELL_PX, self._grid.rows * CELL_PX)

    # --- Public API ---

    def set_grid(self, grid: Grid) -> None:
        self._grid = grid
        self._preview_rect = None
        self._preview_cells = None
        self._selected_cell = None
        self._multi_selection = set()
        self._sync_scene_rect()
        self.update()

    def refresh(self) -> None:
        self.update()

    def set_preview_rect(self, r1: int, c1: int, r2: int, c2: int) -> None:
        self._preview_rect = (min(r1, r2), min(c1, c2), max(r1, r2), max(c1, c2))
        self._preview_cells = None
        self.update()

    def set_line_preview(self, cells: list[tuple[int, int]]) -> None:
        self._preview_cells = list(cells)
        self._preview_rect = None
        self.update()

    def clear_preview(self) -> None:
        changed = self._preview_rect is not None or self._preview_cells is not None
        self._preview_rect = None
        self._preview_cells = None
        if changed:
            self.update()

    def set_selected_cell(self, row: int, col: int) -> None:
        self._selected_cell = (row, col)
        self.update()

    def clear_selected_cell(self) -> None:
        if self._selected_cell is not None:
            self._selected_cell = None
            self.update()

    def set_multi_selection(self, cells: set[tuple[int, int]]) -> None:
        self._multi_selection = set(cells)
        self.update()

    def set_view_mode(self, mode: str) -> None:
        self._view_mode = mode
        self.update()

    def set_heatmap_auto(self, auto: bool) -> None:
        self._heatmap_auto = auto
        self.update()

    def set_heatmap_range(self, t_min_k: float, t_max_k: float) -> None:
        self._heatmap_t_min = t_min_k
        self._heatmap_t_max = t_max_k
        if not self._heatmap_auto:
            self.update()

    # --- Rendering ---

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        # Dark fill for any area outside the grid (visible when zoomed out)
        painter.fillRect(rect, QColor(25, 25, 25))

        g  = self._grid
        cp = CELL_PX

        if self._view_mode == "heatmap":
            self._draw_heatmap(painter, g, cp)
        else:
            for r in range(g.rows):
                for c in range(g.cols):
                    painter.fillRect(c * cp, r * cp, cp, cp, cell_color(g.cell(r, c)))

        # Grid lines — cosmetic pen stays 1 screen pixel regardless of zoom level
        if self.show_grid_lines:
            pen = QPen(QColor(50, 50, 50))
            pen.setCosmetic(True)
            painter.setPen(pen)
            for r in range(g.rows + 1):
                painter.drawLine(0, r * cp, g.cols * cp, r * cp)
            for c in range(g.cols + 1):
                painter.drawLine(c * cp, 0, c * cp, g.rows * cp)

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        cp = CELL_PX

        # Multi-selection highlight (blue overlay, drawn below previews)
        if self._multi_selection:
            for r, c in self._multi_selection:
                painter.fillRect(c * cp, r * cp, cp, cp, QColor(80, 140, 220, 55))
            sel_pen = QPen(QColor(100, 160, 255))
            sel_pen.setCosmetic(True)
            sel_pen.setWidth(1)
            painter.setPen(sel_pen)
            for r, c in self._multi_selection:
                painter.drawRect(c * cp, r * cp, cp - 1, cp - 1)

        # Shift-drag rectangle preview — semi-transparent teal fill with border
        if self._preview_rect is not None:
            r1, c1, r2, c2 = self._preview_rect
            x, y = c1 * cp, r1 * cp
            w, h = (c2 - c1 + 1) * cp, (r2 - r1 + 1) * cp
            painter.fillRect(x, y, w, h, QColor(0, 150, 136, 70))
            pen = QPen(QColor(0, 200, 180))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(x, y, w - 1, h - 1)

        # Ctrl-drag Bresenham line preview — per-cell teal fill with border
        if self._preview_cells is not None:
            pen = QPen(QColor(0, 200, 180))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            for r, c in self._preview_cells:
                painter.fillRect(c * cp, r * cp, cp, cp, QColor(0, 150, 136, 70))
                painter.drawRect(c * cp + 1, r * cp + 1, cp - 2, cp - 2)

        # Lock icons on fixed-temperature cells
        g = self._grid
        for r in range(g.rows):
            for c in range(g.cols):
                if g.cell(r, c).is_fixed:
                    draw_lock_icon(painter, c * cp, r * cp, cp)

        # Selected cell — white border highlight (single-cell select)
        if self._selected_cell is not None:
            r, c = self._selected_cell
            x, y = c * cp, r * cp
            pen = QPen(QColor(255, 255, 255))
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawRect(x + 1, y + 1, cp - 2, cp - 2)

    # --- Heatmap helpers ---

    def _heatmap_bounds(self) -> tuple[float, float]:
        if self._heatmap_auto:
            temps = [
                self._grid.cell(r, c).temperature
                for r in range(self._grid.rows)
                for c in range(self._grid.cols)
            ]
            t_min, t_max = min(temps), max(temps)
            # Avoid zero-width range — add a tiny spread so the gradient always renders
            if t_max - t_min < 0.1:
                t_max = t_min + 0.1
            return t_min, t_max
        return self._heatmap_t_min, self._heatmap_t_max

    def _draw_heatmap(self, painter: QPainter, g: Grid, cp: int) -> None:
        t_min, t_max = self._heatmap_bounds()

        for r in range(g.rows):
            for c in range(g.cols):
                color = heatmap_color(g.cell(r, c).temperature, t_min, t_max)
                painter.fillRect(c * cp, r * cp, cp, cp, color)

        # Temperature labels when cells are large enough on screen
        zoom = painter.deviceTransform().m11()
        if cp * zoom >= _LABEL_THRESHOLD_PX:
            font = QFont()
            font.setPixelSize(max(8, int(cp * 0.32)))
            painter.setFont(font)

            for r in range(g.rows):
                for c in range(g.cols):
                    cell = g.cell(r, c)
                    bg   = heatmap_color(cell.temperature, t_min, t_max)
                    painter.setPen(text_color_for_bg(bg))
                    temp_disp = _units.to_display(cell.temperature)
                    painter.drawText(
                        QRectF(c * cp, r * cp, cp, cp),
                        Qt.AlignmentFlag.AlignCenter,
                        f"{temp_disp:.0f}°",
                    )
